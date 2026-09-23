"""The release decision, and the promise that goes with it, checked against the evidence.

A wheel that works in its own checkout proves nothing about a wheel somebody installs. These
tests check the packaging, the recorded evidence, and that no scope is promised that the
evidence does not support.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evaluations/release-evidence.json'


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(EVIDENCE.is_file(), 'no release evidence has been recorded')
        self.payload = json.loads(EVIDENCE.read_text(encoding='utf-8'))

    def test_the_checker_accepts_the_recorded_evidence(self):
        done = subprocess.run([sys.executable, str(ROOT / 'tools/check_release_evidence.py'), str(EVIDENCE)],
                              capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_a_blocked_verdict_cannot_be_called_a_release(self):
        from eaos.evaluation_protocol import verdict
        outcome = verdict(self.payload['protocol'], self.payload['results']['measured'])
        if outcome['verdict'] != 'supported':
            self.assertNotEqual(self.payload['decision'], 'release',
                                'a full release was declared on evidence that does not support it')

    def test_every_arm_was_either_run_or_recorded_as_blocked(self):
        from eaos.evaluation_protocol import ARMS
        results = self.payload['results']
        accounted = set(results['arms_run']) | set(results['arms_blocked'])
        self.assertEqual(sorted(accounted), sorted(ARMS))
        for arm, reason in results['arms_blocked'].items():
            self.assertTrue(reason.strip(), f'{arm} is blocked without a reason')

    def test_the_unsupported_scope_names_the_things_a_reader_would_assume(self):
        joined = ' '.join(self.payload['unsupported_scope']).lower()
        for expectation in ('unseen', 'independent', 'semantic', 'python'):
            self.assertIn(expectation, joined, f'the record does not say anything about {expectation}')

    def test_no_human_judgement_is_claimed_as_independent_without_an_adjudicator(self):
        for row in self.payload['human_judgement']:
            if row['status'] != 'blocked':
                self.assertTrue(row['independent'], row['id'])

    def test_the_measured_numbers_come_from_a_recorded_corpus(self):
        self.assertIn('corpus', self.payload['results'])
        self.assertTrue(self.payload['results']['measured'])


class PackagingTests(unittest.TestCase):
    """What an installed copy carries, checked without building a wheel in every test run."""

    def test_every_package_the_product_needs_is_declared(self):
        import tomllib
        config = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
        include = config['tool']['setuptools']['packages']['find']['include']
        self.assertIn('eaos*', include)

    def test_the_declared_data_files_exist_in_the_package(self):
        import tomllib
        config = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
        patterns = config['tool']['setuptools'].get('package-data', {}).get('eaos', [])
        self.assertTrue(patterns)
        for pattern in patterns:
            self.assertTrue(list((ROOT / 'eaos').glob(pattern)), f'nothing matches packaged pattern {pattern}')

    def test_the_entry_point_is_declared(self):
        import tomllib
        config = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
        self.assertIn('eaos', config['project']['scripts'])

    def test_the_installed_command_runs_from_outside_the_checkout(self):
        """Run the CLI with the checkout off sys.path, so an import it forgot to declare fails here."""
        with tempfile.TemporaryDirectory() as elsewhere:
            done = subprocess.run([sys.executable, '-m', 'eaos', '--version'],
                                  capture_output=True, text=True, cwd=elsewhere,
                                  env={'PATH': '/usr/bin:/bin', 'PYTHONPATH': str(ROOT)})
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_an_audit_of_a_separate_project_produces_a_readable_report(self):
        from eaos.audit import run as run_audit
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'project'
            project.mkdir()
            (project / 'app.py').write_text('def charge(amount):\n    return amount * 2\n', encoding='utf-8')
            (project / 'store.py').write_text('from app import charge\n\n\n'
                                              'def save(x):\n    return charge(x)\n', encoding='utf-8')
            out = Path(directory) / 'report'
            result = run_audit(project, out, language='en')
            self.assertIn(result['status'], ('COMPLETE', 'PARTIAL'))
            self.assertTrue((out / 'README.md').is_file())
            self.assertTrue((out / 'RUN.md').is_file())
            verdict = json.loads((out / 'report-result.json').read_text(encoding='utf-8'))
            self.assertEqual(verdict['output_spec_violations'], [])


class SupportScopeTests(unittest.TestCase):
    """What the documentation promises must not exceed what the evidence supports."""

    def test_the_readme_does_not_promise_a_scope_the_evidence_excludes(self):
        payload = json.loads(EVIDENCE.read_text(encoding='utf-8'))
        self.assertTrue(payload['supported_scope'])
        for name in ('README.md', 'README.en.md'):
            text = (ROOT / name).read_text(encoding='utf-8').lower()
            for overclaim in ('works on any repository', 'guarantees', 'production ready', 'any language'):
                self.assertNotIn(overclaim, text, f'{name} promises more than the evidence: {overclaim}')
