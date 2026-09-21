"""The baseline separates the debt a project had from the debt a change added."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from eaos import baseline

ROOT = Path(__file__).resolve().parents[1]


def dossier(claims):
    return {'claims': claims, 'provenance': {'target': '/x', 'commit': 'abc'}, 'coverage': {}}


def claim(identifier, statement, count=2, facts=('F1',), confidence='CONFIRMED', kind='business_rule'):
    return {'id': identifier, 'statement': statement, 'claim_type': kind, 'confidence': confidence,
            'uid': identifier.lower(), 'fact_ids': list(facts),
            'render': {'key': 'structural_duplicate', 'params': {'count': count, 'where': 'a.py:1 x, b.py:2 y'}}}


class PinTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.out = Path(self.directory)

    def test_pinning_without_a_dossier_refuses(self):
        with self.assertRaises(ValueError):
            baseline.pin(self.out)

    def test_pinning_twice_refuses_rather_than_overwriting(self):
        (self.out / 'dossier.json').write_text(json.dumps(dossier([claim('CLM-001', 'a')])), encoding='utf-8')
        baseline.pin(self.out)
        with self.assertRaises(ValueError):
            baseline.pin(self.out)

    def test_show_reports_nothing_pinned_rather_than_failing(self):
        result = baseline.show(self.out)
        self.assertFalse(result['pinned'])
        self.assertIn('no baseline', result['reason'])

    def test_clear_removes_the_pin_and_says_so(self):
        (self.out / 'dossier.json').write_text(json.dumps(dossier([claim('CLM-001', 'a')])), encoding='utf-8')
        baseline.pin(self.out)
        self.assertTrue(baseline.clear(self.out)['cleared'])
        self.assertFalse(baseline.show(self.out)['pinned'])

    def test_the_document_separates_claims_from_distinct_identities(self):
        # Two records asserting the same thing are one identity; the counts must not read alike.
        twin = claim('CLM-002', 'a')
        twin['uid'] = 'clm-001'
        (self.out / 'dossier.json').write_text(
            json.dumps(dossier([claim('CLM-001', 'a'), twin])), encoding='utf-8')
        baseline.pin(self.out)
        summary = baseline.show(self.out, language='en')
        self.assertEqual(summary['claims'], 2)
        self.assertEqual(summary['accepted_identities'], 1)
        self.assertIn('distinct identities', (self.out / 'BASELINE.md').read_text(encoding='utf-8'))


class GateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.out = Path(self.directory)

    def _pin(self, claims):
        (self.out / 'dossier.json').write_text(json.dumps(dossier(claims)), encoding='utf-8')
        baseline.pin(self.out)

    def _now(self, claims):
        (self.out / 'dossier.json').write_text(json.dumps(dossier(claims)), encoding='utf-8')

    def test_without_a_baseline_the_new_gate_says_so_instead_of_passing_quietly(self):
        self._now([claim('CLM-001', 'a')])
        verdict = baseline.gate(self.out, 'new')
        self.assertEqual(verdict['status'], 'NO_BASELINE')

    def test_existing_debt_does_not_fail_the_gate(self):
        self._pin([claim('CLM-001', 'a'), claim('CLM-002', 'b')])
        self._now([claim('CLM-001', 'a'), claim('CLM-002', 'b')])
        self.assertEqual(baseline.gate(self.out, 'new')['status'], 'PASS')

    def test_a_new_finding_fails_the_gate_and_is_named(self):
        self._pin([claim('CLM-001', 'a')])
        self._now([claim('CLM-001', 'a'), claim('CLM-002', 'b')])
        verdict = baseline.gate(self.out, 'new')
        self.assertEqual(verdict['status'], 'FAIL')
        self.assertEqual([row['id'] for row in verdict['failing']], ['CLM-002'])
        self.assertEqual(verdict['failing'][0]['reason'], 'not in the baseline')

    def test_a_finding_that_grows_in_place_fails_the_gate(self):
        """A third copy of a duplicated rule keeps the cluster's identity and must still fail."""
        self._pin([claim('CLM-001', 'a', count=2)])
        self._now([claim('CLM-001', 'a', count=3)])
        verdict = baseline.gate(self.out, 'new')
        self.assertEqual(verdict['status'], 'FAIL')
        self.assertEqual(verdict['grew_in_place'], ['CLM-001'])
        self.assertEqual(verdict['failing'][0]['reason'], 'grew beyond the baseline')

    def test_a_finding_that_shrinks_does_not_fail(self):
        self._pin([claim('CLM-001', 'a', count=4)])
        self._now([claim('CLM-001', 'a', count=2)])
        self.assertEqual(baseline.gate(self.out, 'new')['status'], 'PASS')

    def test_the_all_gate_judges_every_live_finding_baseline_or_not(self):
        self._pin([claim('CLM-001', 'a')])
        self._now([claim('CLM-001', 'a')])
        self.assertEqual(baseline.gate(self.out, 'all')['status'], 'FAIL')

    def test_an_unknown_gate_mode_is_refused(self):
        with self.assertRaises(ValueError):
            baseline.gate(self.out, 'whatever')


class ScenarioTests(unittest.TestCase):
    """The end-to-end scenario, run as the plan's acceptance command does."""

    def test_the_no_new_debt_scenario_passes(self):
        script = ROOT / 'tests/gate/no_new_debt.sh'
        done = subprocess.run(['bash', str(script)], capture_output=True, text=True,
                              env={'PATH': '/usr/bin:/bin:/usr/local/bin', 'EAOS': str(ROOT / '.venv/bin/eaos'),
                                   'HOME': str(ROOT)})
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn('PASS:', done.stdout)
