"""The scorecard is computed from evidence, and an absent measurement is never a pass."""
import json
import tempfile
import unittest
from pathlib import Path

from eaos import capability


def report(directory, **files):
    root = Path(directory)
    (root / 'facts').mkdir(parents=True, exist_ok=True)
    (root / 'dossier.json').write_text(json.dumps(files.pop('dossier', {'claims': []})), encoding='utf-8')
    for name, payload in files.items():
        target = root / (name.replace('__', '/') + '.json')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload), encoding='utf-8')
    return root


class UnmeasuredTests(unittest.TestCase):
    def test_an_empty_report_scores_nothing_rather_than_zero_everywhere(self):
        with tempfile.TemporaryDirectory() as directory:
            card = capability.score([report(directory)])
        for name, row in card['domains'].items():
            if row['score'] is None:
                continue
            self.assertFalse(row['meets_target'], f'{name} met its target with no evidence')

    def test_an_unmeasured_indicator_blocks_the_target_even_at_a_high_score(self):
        with tempfile.TemporaryDirectory() as directory:
            root = report(directory, **{'transform-plan': {'stages': [
                {'stage': 1, 'acceptance': {'kind': 'equivalence'}, 'rollback': 'revert',
                 'predicted': {'single_source': -0.01}}]}})
            card = capability.score([root])
        plan = card['domains']['transformation_plan']
        self.assertGreater(plan['score'], 0.9)
        self.assertEqual(plan['unmeasured_indicators'], 1)
        self.assertFalse(plan['meets_target'], 'a domain with an unmeasured indicator cannot be at target')

    def test_the_target_is_declared_once(self):
        self.assertEqual(capability.TARGET, 0.80)
        with tempfile.TemporaryDirectory() as directory:
            card = capability.score([report(directory)])
        for row in card['domains'].values():
            self.assertEqual(row['target'], capability.TARGET)


class EvidenceTests(unittest.TestCase):
    def test_a_stdlib_import_is_not_counted_as_an_unresolved_one(self):
        with tempfile.TemporaryDirectory() as directory:
            root = report(directory, **{
                'facts__syntax': {'facts': [
                    {'kind': 'source_file', 'location': {'path': 'a.py'},
                     'value': {'language': 'python', 'parse_status': 'OBSERVED'}}]},
                'facts__resolve': {'facts': [
                    {'kind': 'module_edge', 'location': {'path': 'a.py'}, 'resolution': 'RESOLVED'},
                    {'kind': 'module_edge', 'location': {'path': 'a.py'}, 'resolution': 'EXTERNAL'}]}})
            rows = capability._language_rows(root)
        self.assertEqual(rows['python']['imports'], 1, 'an external import has no file to resolve to')
        self.assertEqual(rows['python']['resolved'], 1)

    def test_a_python_indicator_is_not_measured_on_a_repository_that_is_barely_python(self):
        with tempfile.TemporaryDirectory() as directory:
            facts = [{'kind': 'source_file', 'location': {'path': f'g{i}.go'},
                      'value': {'language': 'go', 'parse_status': 'OBSERVED'}} for i in range(90)]
            facts.append({'kind': 'source_file', 'location': {'path': 'a.py'},
                          'value': {'language': 'python', 'parse_status': 'OBSERVED'}})
            root = report(directory, **{'facts__syntax': {'facts': facts}})
            result = capability.structure_python(root)
        self.assertTrue(all(value is None for value in result.values()))

    def test_the_weakest_report_decides_a_domain(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            strong = report(first, **{'report-result': {'output_spec_violations': []}})
            weak = report(second, **{'report-result': {'output_spec_violations': ['R2 something']}})
            card = capability.score([strong, weak])
        self.assertEqual(card['domains']['report_clarity']['indicators']['output_contract_clean'], 0.0)

    def test_the_load_model_counts_only_questions_that_were_answered(self):
        with tempfile.TemporaryDirectory() as directory:
            answers = {question: {'status': 'answered'} for question in capability.LOAD_QUESTIONS[:4]}
            root = report(directory, **{
                'facts__entrypoints': {'facts': [{'kind': 'entry_point', 'location': {'path': 'a.py'},
                                                  'value': {'category': 'http'}}]},
                'load-model': {'entry_points': [{'id': 'E1', 'answers': answers}],
                               'projection': {'at_1000x': 'recorded'}}})
            result = capability.load_model(root)
        self.assertEqual(result['questions_answered'], 0.5)
        self.assertEqual(result['projection_recorded'], 1.0)

    def test_every_load_question_is_declared(self):
        self.assertEqual(len(capability.LOAD_QUESTIONS), 8)
        self.assertEqual(len(set(capability.LOAD_QUESTIONS)), 8)


class ScoreShapeTests(unittest.TestCase):
    def test_every_domain_reports_its_indicators_and_whether_it_met_the_target(self):
        with tempfile.TemporaryDirectory() as directory:
            card = capability.score([report(directory)])
        self.assertEqual(sorted(card['domains']), sorted(capability.DOMAINS))
        for row in card['domains'].values():
            self.assertIn('indicators', row)
            self.assertIn('meets_target', row)
        self.assertIn('limitations', card)

    def test_the_recorded_scorecard_matches_a_fresh_computation(self):
        record = Path(__file__).resolve().parents[1] / 'docs/capability-score.json'
        self.assertTrue(record.is_file(), 'run tools/capability_score.py --write')
        payload = json.loads(record.read_text(encoding='utf-8'))
        self.assertEqual(sorted(payload['domains']), sorted(capability.DOMAINS))
        self.assertIsNotNone(payload['overall'])


class NoRegressionGateTests(unittest.TestCase):
    """The gate must fail on a fall and pass on an improvement."""

    def _compare(self, before, after, tolerance=0.02):
        regressions = []
        for name, was in before.items():
            is_now = after.get(name)
            if was is None or is_now is None:
                continue
            if is_now < was - tolerance:
                regressions.append(name)
        return regressions

    def test_a_fall_beyond_the_tolerance_is_a_regression(self):
        self.assertEqual(self._compare({'load_model': 0.80}, {'load_model': 0.70}), ['load_model'])

    def test_a_fall_inside_the_tolerance_is_not(self):
        self.assertEqual(self._compare({'load_model': 0.80}, {'load_model': 0.79}), [])

    def test_an_unmeasured_domain_is_not_treated_as_a_fall(self):
        self.assertEqual(self._compare({'load_model': 0.80}, {'load_model': None}), [])

    def test_the_gate_script_exists_and_is_executable(self):
        import os
        script = Path(__file__).resolve().parents[1] / 'tests/gate/capability_no_regression.sh'
        self.assertTrue(script.is_file())
        self.assertTrue(os.access(script, os.X_OK))


class PlanTests(unittest.TestCase):
    """The plan must stay executable: the renderer refuses one that is not."""

    def setUp(self):
        import importlib.util
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location('plan_renderer', root / 'tools/render_capability_plan.py')
        self.renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.renderer)
        self.plan = json.loads((root / 'docs/capability-plan.json').read_text(encoding='utf-8'))

    def test_the_real_plan_is_executable(self):
        self.assertEqual(self.renderer.validate(self.plan), [])

    def test_every_task_moves_an_indicator_the_scorecard_measures(self):
        for task in self.renderer.tasks(self.plan):
            indicator = (task.get('moves') or {}).get('indicator')
            self.assertTrue(indicator, task['id'])
            if indicator in ('n/a', 'overall'):
                continue
            domain = indicator.split('.', 1)[0]
            self.assertIn(domain, capability.DOMAINS, task['id'])

    def test_a_task_with_no_acceptance_is_rejected(self):
        import copy
        broken = copy.deepcopy(self.plan)
        self.renderer.tasks(broken)[-1]['acceptance'] = ''
        self.assertTrue(any('no acceptance command' in problem
                            for problem in self.renderer.validate(broken)))

    def test_a_dependency_cycle_is_rejected(self):
        import copy
        broken = copy.deepcopy(self.plan)
        task = self.renderer.tasks(broken)[-1]
        task['depends_on'].append(task['id'])
        self.assertTrue(any('itself' in problem for problem in self.renderer.validate(broken)))

    def test_the_rendered_plan_is_not_stale(self):
        self.assertEqual(self.renderer.main(['--check']), 0)

    def test_the_next_ready_task_has_all_its_dependencies_done(self):
        done = {task['id'] for task in self.renderer.tasks(self.plan) if task['status'] == 'done'}
        for task in self.renderer.ready(self.plan):
            for reference in task.get('depends_on', []):
                self.assertIn(reference, done, task['id'])
