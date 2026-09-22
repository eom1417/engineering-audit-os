"""Regressions reproduced during the completion review; test the public path."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from eaos.pipeline import execute, SkipStage
from eaos.engagement import rank, render_contract

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/benchmarks/clean-project'


class CompletionRegressions(unittest.TestCase):
    def test_audit_cli_writes_all_report_families(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, '-m', 'eaos', 'audit', str(FIXTURE), '--out', tmp],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in ['run-manifest.json', 'dossier.json', 'PRODUCT-REPORT.md', 'index.html',
                         'TARGET-ARCHITECTURE.md', 'EXECUTIVE.md', 'bundles/manifest.json']:
                self.assertTrue((Path(tmp) / name).is_file(), name)

    def test_required_unavailable_cannot_be_complete(self):
        def fail(context): raise SkipStage('facts unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            result = execute(FIXTURE, tmp, runners={'facts': fail})
            self.assertEqual(result['status'], 'INCOMPLETE')

    def test_skipped_required_predecessor_blocks_dependent(self):
        called = []
        with tempfile.TemporaryDirectory() as tmp:
            execute(FIXTURE, tmp, only=['claims'], runners={'claims': lambda context: called.append(True)})
            self.assertEqual(called, [])

    def test_bundle_preserves_customer_contract_bytes_and_language(self):
        from eaos.audit import run
        from eaos.bundles import build
        with tempfile.TemporaryDirectory() as tmp:
            run(FIXTURE, tmp, language='en')
            path = Path(tmp) / 'engagement.json'
            original = b'{"schema_version":1,"name":"CUSTOM","targets":{"single_source":0.3}}\n'
            path.write_bytes(original)
            build(tmp, language='en')
            self.assertEqual(path.read_bytes(), original)
            self.assertIn('Waves', (Path(tmp) / 'WAVES.md').read_text())

    def test_zero_evidence_has_zero_priority(self):
        result = rank([{'reach': 0, 'confidence': 0, 'origin': 0, 'cost': 1}], render_contract())
        self.assertEqual(result[0]['score'], 0)

    def test_no_prediction_means_unavailable_not_honest(self):
        from eaos.audit import run
        from eaos.guarantee import compare
        with tempfile.TemporaryDirectory() as tmp:
            run(FIXTURE, tmp)
            result = compare(tmp, tmp, language='en')
            self.assertEqual(result['status'], 'UNAVAILABLE')
            self.assertEqual(result['rows'], [])

    def test_unreviewed_target_does_not_cover_itself(self):
        from eaos.audit import run
        from eaos.target_architecture import build
        with tempfile.TemporaryDirectory() as tmp:
            run(FIXTURE, tmp)
            result = build(tmp)
            self.assertTrue(result['gap_matrix'])
            self.assertTrue(all(row['gap'] != 'covered' for row in result['gap_matrix']))
            self.assertTrue(all(row['chosen'] in row['options'] for row in result['decisions']))

    def test_every_product_module_belongs_to_a_policy_layer(self):
        from eaos.policy import layer_of
        policy = json.loads((ROOT / 'eaos.policy.json').read_text())
        missing = [str(path.relative_to(ROOT)) for path in (ROOT / 'eaos').rglob('*.py')
                   if layer_of(path.relative_to(ROOT).as_posix(), policy['layers']) is None]
        self.assertEqual(missing, [])
