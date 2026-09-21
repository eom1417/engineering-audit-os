"""The tool passes its own rules, and what it says about itself is acted on or argued with."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SelfAuditTests(unittest.TestCase):
    def test_the_self_audit_gate_passes(self):
        done = subprocess.run(['bash', str(ROOT / 'tests/gate/self_audit.sh')],
                              capture_output=True, text=True, cwd=ROOT,
                              env={'PATH': '/usr/bin:/bin', 'HOME': str(ROOT),
                                   'EAOS': str(ROOT / '.venv/bin/eaos'),
                                   'PYTHON': str(ROOT / '.venv/bin/python')})
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn('PASS:', done.stdout)


class CanonicalHomeTests(unittest.TestCase):
    """The duplication the tool found in our tests has one owner now."""

    def test_no_test_class_carries_its_own_copy_of_the_teardown(self):
        """Parsed, not grepped: a check that matches its own source text is not a check."""
        import ast
        offenders = []
        for path in sorted((ROOT / 'tests').glob('test_*.py')):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                for member in node.body:
                    if not isinstance(member, ast.FunctionDef) or member.name not in ('tearDown', 'tearDownClass'):
                        continue
                    body = ast.dump(ast.Module(body=member.body, type_ignores=[]))
                    if 'cleanup' in body or 'rmtree' in body:
                        offenders.append(f'{path.name}::{node.name}::{member.name}')
        # ParityTests builds two whole reports once for the class; it owns that lifetime itself.
        allowed = {'test_report_parity.py::ParityTests::tearDownClass'}
        self.assertEqual(sorted(set(offenders) - allowed), [],
                         'the copies came back; the canonical home is tests/shared_fixture.py')

    def test_the_canonical_home_cleans_up_what_it_created(self):
        from shared_fixture import TemporaryWorkspace, Workspace
        self.assertTrue(hasattr(TemporaryWorkspace, 'tearDownClass'))
        self.assertTrue(hasattr(Workspace, 'tearDown'))

    def test_a_class_that_never_opened_a_workspace_is_not_punished(self):
        from shared_fixture import TemporaryWorkspace

        class Empty(TemporaryWorkspace):
            pass

        Empty.tearDownClass()


class RemainingDuplicationTests(unittest.TestCase):
    """What the tool still reports about us, and why it was left alone."""

    ACCEPTED = 'tests that each assert one extractor states its own limitations'

    def test_the_remaining_top_finding_is_recorded_as_deliberate(self):
        record = ROOT / 'docs/self-audit.json'
        self.assertTrue(record.is_file(), 'the self-audit outcome is not recorded')
        payload = json.loads(record.read_text(encoding='utf-8'))
        self.assertTrue(payload['closed'], 'nothing was closed, so the loop was never run')
        self.assertTrue(payload['accepted'], 'nothing was argued with, which is unlikely to be honest')
        for row in payload['accepted']:
            self.assertTrue(row['reason'].strip(), row['finding'])
        for row in payload['closed']:
            self.assertIn('before', row)
            self.assertIn('after', row)
            self.assertLess(row['after'], row['before'], row['indicator'])
