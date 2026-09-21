"""Guarantee: simulator predictions vs. observed indicator deltas."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from eaos.audit import run as run_audit
from eaos.guarantee import compare


class GuaranteeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_identical_snapshots_produce_honest_results(self):
        a = Path(self.tmp) / 'a'; b = Path(self.tmp) / 'b'
        run_audit(Path('tests/fixtures/sustainability'), a, language='en')
        run_audit(Path('tests/fixtures/sustainability'), b, language='en')
        result = compare(a, b, language='en')
        for row in result['rows']:
            if row['verdict'] != 'HONEST':
                # With identical snapshots, predicted improvement is -current, observed is 0; overstatement is expected.
                self.assertEqual(row['verdict'], 'OVERSTATED')

    def test_tolerance_zeros_out_all_differences(self):
        a = Path(self.tmp) / 'a'; b = Path(self.tmp) / 'b'
        run_audit(Path('tests/fixtures/sustainability'), a, language='en')
        run_audit(Path('tests/fixtures/sustainability'), b, language='en')
        # Tolerance of 1.0 swallows everything
        result = compare(a, b, tolerance=1.0, language='en')
        for row in result['rows']:
            self.assertEqual(row['verdict'], 'HONEST')

    def test_returns_artifact_path(self):
        a = Path(self.tmp) / 'a'; b = Path(self.tmp) / 'b'
        run_audit(Path('tests/fixtures/sustainability'), a, language='en')
        run_audit(Path('tests/fixtures/sustainability'), b, language='en')
        result = compare(a, b, language='en')
        self.assertTrue(Path(result['artifact']).is_file())
        content = Path(result['artifact']).read_text()
        self.assertIn('Verification guarantee', content)


class GuaranteeLimitationsTests(unittest.TestCase):
    def test_guarantee_does_not_run_runtime_checks(self):
        from eaos import guarantee
        self.assertIn('structural indicator deltas', ' '.join(guarantee.LIMITATIONS))
