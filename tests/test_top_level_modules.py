"""Tests for the top-level modules: engagement, target_architecture, executive, bundles, progress."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from eaos import engagement, target_architecture, executive, bundles, progress, guarantee
from eaos.audit import run as run_audit


class EngagementTests(unittest.TestCase):
    def test_default_contract_has_priority_targets_scenarios(self):
        contract = engagement.render_contract()
        self.assertEqual(contract['schema_version'], 1)
        self.assertIn('priority', contract); self.assertIn('targets', contract)
        self.assertIn('scenarios', contract); self.assertIn('scope', contract)

    def test_rank_applies_weights_to_scenarios(self):
        contract = engagement.render_contract()
        scenarios = [
            {'id': 'A', 'name': 'cheap', 'reach': 0.1, 'confidence': 0.9,
              'origin': 0.9, 'cost': 0.1, 'stimulus': '', 'response': '', 'measure': ''},
            {'id': 'B', 'name': 'expensive', 'reach': 0.9, 'confidence': 0.9,
              'origin': 0.9, 'cost': 0.9, 'stimulus': '', 'response': '', 'measure': ''},
        ]
        ranked = engagement.rank(scenarios, contract)
        # A has lower cost, so should rank first.
        self.assertEqual(ranked[0]['id'], 'A')


class TargetArchitectureTests(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp()
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)

    def test_components_are_per_symbol(self):
        run_audit(Path('tests/fixtures/sustainability'), Path(self.tmp) / 'out', language='en')
        target = target_architecture.build(Path(self.tmp) / 'out')
        self.assertGreater(len(target['components']), 0)
        for component in target['components']:
            self.assertIn('id', component); self.assertIn('origin', component)
            self.assertIn('relation', component); self.assertIn('contracts', component)

    def test_gap_matrix_covers_every_current_component(self):
        run_audit(Path('tests/fixtures/sustainability'), Path(self.tmp) / 'out', language='en')
        target = target_architecture.build(Path(self.tmp) / 'out')
        covered = {row['current_id']: row['gap'] for row in target['gap_matrix']}
        for component in target['components']:
            self.assertIn(component['id'], covered)


class ExecutiveTests(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp()
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)

    def test_executive_md_is_one_page(self):
        run_audit(Path('tests/fixtures/sustainability'), Path(self.tmp) / 'out', language='en')
        result = executive.render(Path(self.tmp) / 'out', language='en')
        self.assertIsNotNone(result)
        content = Path(result['artifact']).read_text()
        self.assertIn('Executive summary', content)
        # The page must be small enough to read in a meeting.
        self.assertLess(len(content.splitlines()), 60)


class BundlesTests(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp()
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)

    def test_five_bundles_are_created(self):
        run_audit(Path('tests/fixtures/sustainability'), Path(self.tmp) / 'out', language='en')
        result = bundles.build(Path(self.tmp) / 'out')
        self.assertEqual(set(result['bundles']),
                          {'00-ENGAGEMENT', '01-DISCOVERY', '02-ASSESSMENT',
                            '03-TARGET', '04-TRANSFORM', 'SUMMARY'})


class ProgressTests(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp()
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)

    def test_progress_reports_per_indicator(self):
        run_audit(Path('tests/fixtures/sustainability'), Path(self.tmp) / 'a', language='en')
        run_audit(Path('tests/fixtures/sustainability'), Path(self.tmp) / 'b', language='en')
        result = progress.render(Path(self.tmp) / 'a', Path(self.tmp) / 'b', language='en')
        for row in result['rows']:
            self.assertIn('indicator', row)
            self.assertIn('direction', row)
            self.assertIn(row['direction'], {'improved', 'worsened', 'unchanged'})


class GuaranteesTests(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp()
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)

    def test_without_a_recorded_prediction_there_is_nothing_to_grade(self):
        """A verdict with no prediction behind it would be the tool inventing its own accuracy."""
        run_audit(Path('tests/fixtures/sustainability'), Path(self.tmp) / 'a', language='en')
        run_audit(Path('tests/fixtures/sustainability'), Path(self.tmp) / 'b', language='en')
        result = guarantee.compare(Path(self.tmp) / 'a', Path(self.tmp) / 'b', language='en')
        self.assertEqual(result['status'], 'UNAVAILABLE')
        self.assertEqual(result['rows'], [])
        self.assertEqual(result['summary'], {})
        self.assertIn('No recorded prediction was supplied.', result['reasons'])
        self.assertIn('UNAVAILABLE', (Path(self.tmp) / 'b' / 'GUARANTEE.md').read_text(encoding='utf-8'))

    def test_a_recorded_prediction_is_graded_against_what_was_observed(self):
        first, second = Path(self.tmp) / 'a', Path(self.tmp) / 'b'
        run_audit(Path('tests/fixtures/sustainability'), first, language='en')
        plan = json.loads((first / 'transform-plan.json').read_text(encoding='utf-8'))
        stages = plan.get('stages') or plan.get('moves') or []
        if not stages:
            self.skipTest('the fixture produced no transform stage to predict from')
        record = guarantee.predict(first, stages[0], first / 'prediction.json')
        self.assertEqual(record['schema_version'], 1)
        # Re-running over an unchanged tree observes a delta of zero for every indicator.
        run_audit(Path('tests/fixtures/sustainability'), second, language='en')
        result = guarantee.compare(first, second, language='en', prediction=first / 'prediction.json')
        self.assertEqual(result['status'], 'COMPARED')
        self.assertTrue(result['rows'], result['reasons'])
        self.assertTrue(set(result['summary']) <= {'HONEST', 'OVERSTATED', 'UNDERSTATED'})
        for row in result['rows']:
            self.assertEqual(row['observed'], 0.0)

    def test_a_prediction_from_another_snapshot_is_refused(self):
        first, second = Path(self.tmp) / 'a', Path(self.tmp) / 'b'
        run_audit(Path('tests/fixtures/sustainability'), first, language='en')
        run_audit(Path('eaos/compose'), second, language='en')
        plan = json.loads((first / 'transform-plan.json').read_text(encoding='utf-8'))
        stages = plan.get('stages') or plan.get('moves') or []
        if not stages:
            self.skipTest('the fixture produced no transform stage to predict from')
        guarantee.predict(first, stages[0], first / 'prediction.json')
        result = guarantee.compare(first, second, language='en', prediction=first / 'prediction.json')
        self.assertEqual(result['status'], 'UNAVAILABLE')
        self.assertTrue(result['reasons'])
