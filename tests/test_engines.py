"""External engines enter as evidence, never as authority, and a missing engine never fails a run."""
import json
import tempfile
import unittest
from pathlib import Path

from eaos import correlate
from eaos.engines import ADAPTERS, analyze, health
from eaos.engines.contract import Report, UNAVAILABLE, finding, subject


def engine_fact(identifier, engine, kind, path, rule='r', sites=None, message='m'):
    return {'id': identifier, 'kind': 'engine_finding',
            'location': {'path': path, 'line': None, 'symbol': path},
            'value': {'engine': engine, 'engine_version': '1', 'rule': rule, 'kind': kind, 'method': 'heuristic',
                      'message': message, 'measurements': [], 'engine_confidence': None, 'subject_kind': 'file',
                      'sites': sites if sites is not None else [{'path': path, 'line': None}]}}


def fact_set(facts, evaluated):
    return {'external': {'facts': facts, 'summary': {'evaluated_kinds': evaluated}}}


class ContractTests(unittest.TestCase):
    def test_an_unknown_finding_kind_is_refused_rather_than_stored(self):
        with self.assertRaises(ValueError):
            finding('e', '1', 'rule', 'not_a_kind', subject('file', 'a.py'), 'message')

    def test_the_identity_of_a_finding_is_its_content(self):
        first = finding('e', '1', 'rule', 'cycle', subject('file', 'a.py'), 'message')
        again = finding('e', '1', 'rule', 'cycle', subject('file', 'a.py'), 'message')
        other = finding('e', '1', 'rule', 'cycle', subject('file', 'b.py'), 'message')
        self.assertEqual(first['id'], again['id'])
        self.assertNotEqual(first['id'], other['id'])

    def test_a_finding_about_several_places_keeps_all_of_them(self):
        row = finding('e', '1', 'rule', 'duplication', subject('file', 'a.py'), 'message',
                      sites=[{'path': 'b.py', 'line': 3}, {'path': 'a.py', 'line': None}])
        self.assertEqual([spot[0] for spot in row['sites']], ['a.py', 'b.py'])


class DegradationTests(unittest.TestCase):
    def test_health_reports_every_adapter_whether_installed_or_not(self):
        report = health()
        self.assertEqual(sorted(report), sorted(ADAPTERS))
        for detail in report.values():
            self.assertIn('version_matches_pin', detail)

    def test_an_engine_that_raises_does_not_take_the_run_down(self):
        class Exploding:
            NAME, PINNED = 'exploding', '0'
            @staticmethod
            def analyze(*_args, **_kwargs): raise RuntimeError('engine crashed')
        ADAPTERS['exploding'] = Exploding
        try:
            with tempfile.TemporaryDirectory() as workdir:
                manifest = analyze('.', workdir, only=['exploding'])
            self.assertEqual(manifest['coverage']['exploding']['status'], 'error')
            self.assertIn('engine crashed', manifest['coverage']['exploding']['reason'])
        finally:
            del ADAPTERS['exploding']

    def test_an_engine_name_nobody_implements_is_reported_not_ignored(self):
        with tempfile.TemporaryDirectory() as workdir:
            manifest = analyze('.', workdir, only=['imaginary'])
        self.assertEqual(manifest['unknown_engines'], ['imaginary'])
        self.assertEqual(manifest['findings'], [])

    def test_an_uninstalled_engine_reports_unavailable_rather_than_silence(self):
        report = Report('absent', None, '1.0', UNAVAILABLE, reason='not installed')
        self.assertEqual(report.as_dict()['status'], UNAVAILABLE)
        self.assertFalse(report.as_dict()['version_matches_pin'])


class CorrelationTests(unittest.TestCase):
    def test_two_engines_on_one_place_are_one_corroborated_cluster(self):
        sets = fact_set([engine_fact('F1', 'enola', 'complexity', 'a.py'),
                         engine_fact('F2', 'reforge', 'complexity', 'a.py')],
                        {'enola': {'complexity': 'observed'}, 'reforge': {'complexity': 'observed'}})
        [cluster] = correlate.clusters(sets)
        self.assertEqual(cluster['corroboration']['complexity']['verdict'], correlate.CORROBORATED)
        self.assertEqual(cluster['engines'], ['enola', 'reforge'])

    def test_silence_about_a_threshold_rule_is_not_a_denial(self):
        sets = fact_set([engine_fact('F1', 'enola', 'complexity', 'a.py')],
                        {'enola': {'complexity': 'observed'}, 'reforge': {'complexity': 'observed'}})
        [cluster] = correlate.clusters(sets)
        self.assertEqual(cluster['corroboration']['complexity']['verdict'], correlate.SINGLE)

    def test_silence_about_a_structural_property_is_a_denial(self):
        sets = fact_set([engine_fact('F1', 'enola', 'cycle', 'pkg')],
                        {'enola': {'cycle': 'observed'}, 'codegraph': {'cycle': 'observed'}})
        [cluster] = correlate.clusters(sets)
        detail = cluster['corroboration']['cycle']
        self.assertEqual(detail['verdict'], correlate.CONTESTED)
        self.assertEqual(detail['denied_by'], ['codegraph'])

    def test_a_partial_evaluation_does_not_deny(self):
        sets = fact_set([engine_fact('F1', 'enola', 'cycle', 'pkg')],
                        {'enola': {'cycle': 'observed'}, 'reforge': {'cycle': 'partial'}})
        [cluster] = correlate.clusters(sets)
        self.assertEqual(cluster['corroboration']['cycle']['verdict'], correlate.SINGLE)
        self.assertEqual(cluster['corroboration']['cycle']['evaluated_and_silent'], {'reforge': 'partial'})

    def test_a_multi_site_finding_belongs_to_every_site(self):
        sets = fact_set([engine_fact('F1', 'jscpd', 'literal_duplication', 'a.py',
                                     sites=[{'path': 'a.py', 'line': 1}, {'path': 'b.py', 'line': 9}])],
                        {'jscpd': {'literal_duplication': 'observed'}})
        self.assertEqual([cluster['place'] for cluster in correlate.clusters(sets)], ['a.py', 'b.py'])


class EngineClaimTests(unittest.TestCase):
    def test_one_engine_speaking_alone_produces_no_claim(self):
        from eaos.claims import from_engines
        sets = fact_set([engine_fact('F1', 'enola', 'complexity', 'a.py')], {'enola': {'complexity': 'observed'}})
        self.assertEqual(from_engines(sets), [])

    def test_corroborated_evidence_becomes_a_likely_claim_capped_at_likely(self):
        from eaos.claims import from_engines
        sets = fact_set([engine_fact('F1', 'enola', 'complexity', 'a.py'),
                         engine_fact('F2', 'reforge', 'complexity', 'a.py')],
                        {'enola': {'complexity': 'observed'}, 'reforge': {'complexity': 'observed'}})
        [claim] = from_engines(sets)
        self.assertEqual(claim['confidence'], 'LIKELY')
        self.assertEqual(claim['confidence_ceiling'], 'LIKELY')
        self.assertEqual(claim['method'], ['external_engine'])
        self.assertTrue(claim['falsifier'].strip())

    def test_a_contested_structural_finding_becomes_a_hypothesis_capped_at_hypothesis(self):
        from eaos.claims import from_engines
        sets = fact_set([engine_fact('F1', 'enola', 'cycle', 'pkg')],
                        {'enola': {'cycle': 'observed'}, 'codegraph': {'cycle': 'observed'}})
        [claim] = from_engines(sets)
        self.assertEqual(claim['confidence'], 'HYPOTHESIS')
        self.assertEqual(claim['confidence_ceiling'], 'HYPOTHESIS')

    def test_a_probe_cannot_raise_an_external_claim_to_confirmed(self):
        from eaos.probes import _apply_ceiling
        claim = {'confidence': 'CONFIRMED', 'confidence_ceiling': 'LIKELY', 'method': ['external_engine']}
        row = {'status': 'CONFIRMED', 'result': 'still reported'}
        _apply_ceiling(claim, row)
        self.assertEqual(claim['confidence'], 'LIKELY')
        self.assertEqual(row['status'], 'PARTIAL')
        self.assertIn('capped at LIKELY', row['result'])

    def test_a_claim_without_a_ceiling_is_left_alone(self):
        from eaos.probes import _apply_ceiling
        claim = {'confidence': 'CONFIRMED', 'method': ['static_fact']}
        row = {'status': 'CONFIRMED', 'result': 'proved'}
        _apply_ceiling(claim, row)
        self.assertEqual(claim['confidence'], 'CONFIRMED')
        self.assertEqual(row['status'], 'CONFIRMED')


class ReportRenderingTests(unittest.TestCase):
    def test_the_engine_artifact_says_so_when_nothing_ran(self):
        from eaos.engines_report import document
        text = document({}, 'en').render()
        self.assertIn('No external engine ran', text)

    def test_the_engine_artifact_leads_with_the_disagreements(self):
        from eaos.engines_report import document
        sets = fact_set([engine_fact('F1', 'enola', 'cycle', 'pkg')],
                        {'enola': {'cycle': 'observed'}, 'codegraph': {'cycle': 'observed'}})
        sets['external']['summary'].update({'engines_observed': ['codegraph', 'enola'], 'engines_unavailable': [],
                                            'by_engine': {'enola': 1, 'codegraph': 0}})
        text = document(sets, 'en').render()
        self.assertIn('Contested', text)
        self.assertIn('pkg', text)


class InstalledEngineTests(unittest.TestCase):
    """Runs only where the pinned engines exist; skips rather than pretending elsewhere."""

    @classmethod
    def setUpClass(cls):
        from eaos.engines import enola, jscpd
        if not (enola.version() and jscpd.version()):
            raise unittest.SkipTest('the pinned engines are not installed in this environment')

    def test_a_run_leaves_the_target_byte_identical(self):
        with tempfile.TemporaryDirectory() as workdir:
            manifest = analyze('eaos/compose', workdir, only=['enola', 'jscpd'], formats=['python'])
        self.assertTrue(manifest['target_unchanged'])

    def test_two_runs_over_an_unchanged_tree_produce_the_same_facts(self):
        from eaos.facts.run import collect
        digests = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as out:
                collect('eaos/compose', out, engines=['jscpd'])
                digests.append(Path(out, 'facts/external.json').read_bytes())
        self.assertEqual(digests[0], digests[1])

    def test_an_engine_asked_for_by_name_is_the_only_one_that_runs(self):
        with tempfile.TemporaryDirectory() as workdir:
            manifest = analyze('eaos/compose', workdir, only=['jscpd'], formats=['python'])
        self.assertEqual(manifest['requested'], ['jscpd'])
        self.assertEqual(sorted(manifest['coverage']), ['jscpd'])
