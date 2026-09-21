"""End-to-end pipeline: collect → dashboard → plan → target → executive → bundles."""
import json
import shutil
import tempfile
import unittest
from shared_fixture import Workspace
from pathlib import Path
from eaos.audit import run as run_audit


class AuditPipelineTests(Workspace):

    def test_full_pipeline_produces_all_artifacts(self):
        result = run_audit(Path('tests/fixtures/sustainability'), Path(self.tmp) / 'out', language='en')
        for key in ('sustainability', 'transform_plan', 'transform_plan_json',
                     'target_architecture', 'executive', 'bundles_dir'):
            self.assertIn(key, result)
            self.assertTrue(Path(result[key]).exists(), key)
        # Five bundle directories, plus the manifest the stage declares as its product: it records
        # which artifacts were missing, which is how a reader tells an empty bundle from a full one.
        bundles = Path(result['bundles_dir'])
        self.assertEqual({p.name for p in bundles.iterdir() if p.is_dir()},
                          {'00-ENGAGEMENT', '01-DISCOVERY', '02-ASSESSMENT',
                            '03-TARGET', '04-TRANSFORM', 'SUMMARY'})
        manifest = json.loads((bundles / 'manifest.json').read_text(encoding='utf-8'))
        self.assertIn('missing_artifacts', manifest)

    def test_pipeline_runs_in_one_process_step(self):
        """The full pipeline must succeed in a single function call without user input."""
        result = run_audit(Path('tests/fixtures/sustainability'), Path(self.tmp) / 'out', language='ar')
        self.assertIsNotNone(result['executive'])

    def test_self_audit_pipeline_runs(self):
        result = run_audit(Path('eaos'), Path(self.tmp) / 'self', language='en')
        for key in ('sustainability', 'transform_plan', 'executive'):
            self.assertTrue(Path(result[key]).exists(), key)

    def test_engagement_contract_module(self):
        from eaos.engagement import render_contract, rank
        contract = render_contract()
        self.assertIn('targets', contract); self.assertIn('priority', contract)
        scenarios = [{'id': 'SCN-1', 'name': 'refund', 'stimulus': 'order refund',
                      'response': 'return refund', 'measure': 'no orphan charge',
                      'reach': 0.7, 'confidence': 0.9, 'origin': 0.5, 'cost': 0.2}]
        ranked = rank(scenarios, contract)
        self.assertEqual(len(ranked), 1)
        self.assertGreater(ranked[0]['score'], 0)

    def test_target_architecture_module(self):
        from eaos.target_architecture import build as build_target
        result = run_audit(Path('tests/fixtures/sustainability'), Path(self.tmp) / 'out', language='en')
        target = build_target(Path(self.tmp) / 'out')
        self.assertGreater(len(target['components']), 0)
        self.assertIn('gap_matrix', target)
        self.assertGreaterEqual(len(target['decisions']), 0)

    def test_progress_module(self):
        from eaos.progress import render as render_progress
        run_audit(Path('tests/fixtures/sustainability'), Path(self.tmp) / 'a', language='en')
        run_audit(Path('tests/fixtures/sustainability'), Path(self.tmp) / 'b', language='en')
        result = render_progress(Path(self.tmp) / 'a', Path(self.tmp) / 'b', language='en')
        self.assertIsNotNone(result)
        for row in result['rows']:
            self.assertIn('indicator', row); self.assertIn('direction', row)
