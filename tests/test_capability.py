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

    def test_a_milestone_status_its_tasks_contradict_is_rejected(self):
        # The rendered plan showed N2..N12 as todo after every task in them was done or blocked.
        import copy
        broken = copy.deepcopy(self.plan)
        broken['milestones'][0]['status'] = 'todo'
        self.assertTrue(any(problem.startswith(broken['milestones'][0]['id'] + ': status')
                            for problem in self.renderer.validate(broken)))

    def test_totals_the_tasks_contradict_are_rejected(self):
        import copy
        broken = copy.deepcopy(self.plan)
        broken['totals']['done'] -= 1
        self.assertTrue(any(problem.startswith('totals') for problem in self.renderer.validate(broken)))

    def test_the_rendered_plan_is_not_stale(self):
        self.assertEqual(self.renderer.main(['--check']), 0)

    def test_the_next_ready_task_has_all_its_dependencies_done(self):
        done = {task['id'] for task in self.renderer.tasks(self.plan) if task['status'] == 'done'}
        for task in self.renderer.ready(self.plan):
            for reference in task.get('depends_on', []):
                self.assertIn(reference, done, task['id'])


class PolyglotDepthThresholdTests(unittest.TestCase):
    """structure_polyglot counts a language only when its measured depth meets the target."""

    def _rows(self, languages):
        """Build a minimal report dict that lets structure_polyglot find each language's stats.

        Files are marked UNSUPPORTED when they were not parsed; only OBSERVED/PARSED counts.
        """
        facts = []
        resolve = []
        for lang, files_count, parsed, resolved, imports in languages:
            for i in range(files_count):
                facts.append({'kind': 'source_file',
                               'location': {'path': f'{lang}{i}.x'},
                               'value': {'language': lang, 'parse_status': 'PARSED' if i < parsed else 'UNSUPPORTED'}})
            for i in range(imports):
                resolve.append({'kind': 'module_edge',
                                 'location': {'path': f'{lang}{i % files_count}.x'},
                                 'resolution': 'RESOLVED' if i < resolved else 'UNRESOLVED'})
        return {'facts__syntax': {'facts': facts}, 'facts__resolve': {'facts': resolve}}

    def test_one_strong_and_four_dead_languages_yield_low_score(self):
        """Five languages with >=5 files: one meets depth, four are dead -> score < 0.5."""
        with tempfile.TemporaryDirectory() as directory:
            # 'rust' has full depth: 10 files parsed, 5 imports all resolved
            # others: 10 files but 0 imports -> depth is parse-only (1.0)
            #         BUT we want them dead: parse=0 so depth is None
            rows = [
                ('rust', 10, 10, 5, 5),    # depth = (1.0 + 1.0)/2 = 1.0
                ('dart', 10, 0, 0, 0),     # depth = None
                ('ruby', 10, 0, 0, 0),     # depth = None
                ('scala', 10, 0, 0, 0),    # depth = None
                ('swift', 10, 0, 0, 0),    # depth = None
            ]
            root = report(directory, **self._rows(rows))
            result = capability.structure_polyglot(root)
            # 1 of 5 languages meets depth (>=0.80); denominator is len(rows)=5
            self.assertEqual(result['languages_with_depth'], 0.2)
            # thirdmost = third weakest of the five measured depths = 0.0 (one of the dead ones)
            self.assertEqual(result['thirdmost_language_depth'], 0.0)

    def test_all_languages_meet_the_target(self):
        """Every language with full depth => languages_with_depth == 1.0."""
        with tempfile.TemporaryDirectory() as directory:
            rows = [
                ('rust', 10, 10, 5, 5),
                ('dart', 10, 10, 5, 5),
                ('ruby', 10, 10, 5, 5),
            ]
            root = report(directory, **self._rows(rows))
            result = capability.structure_polyglot(root)
            self.assertEqual(result['languages_with_depth'], 1.0)
            self.assertEqual(result['thirdmost_language_depth'], 1.0)

    def test_thirdmost_language_depth_drops_when_one_is_weak(self):
        """Three languages with depths 1.0, 1.0, 0.3 -> thirdmost = 0.3 (the worst)."""
        with tempfile.TemporaryDirectory() as directory:
            rows = [
                ('rust', 10, 10, 5, 5),   # depth 1.0
                ('dart', 10, 10, 5, 5),   # depth 1.0
                ('ruby', 10, 2, 1, 10),   # parse 0.2, resolve 0.1 -> depth 0.15
            ]
            root = report(directory, **self._rows(rows))
            result = capability.structure_polyglot(root)
            self.assertLess(result['thirdmost_language_depth'], 0.5)

    def test_thirdmost_language_depth_is_one_when_fewer_than_three_languages_are_measured(self):
        """With only one measured language, the floor cannot be applied: it returns 1.0."""
        with tempfile.TemporaryDirectory() as directory:
            rows = [('rust', 10, 10, 5, 5)]
            root = report(directory, **self._rows(rows))
            result = capability.structure_polyglot(root)
            self.assertEqual(result['thirdmost_language_depth'], 1.0)

    def test_polyglot_domain_score_reflects_thirdmost_floor(self):
        """The aggregated domain score for polyglot pulls the floor into the average."""
        with tempfile.TemporaryDirectory() as directory:
            # One strong language, four dead ones -> languages_with_depth = 0.2 but thirdmost = 1.0
            # Mean is (0.2 + resolved + 1.0) / 3 -> not great
            rows = [
                ('rust', 10, 10, 5, 5),
                ('dart', 10, 0, 0, 0),
                ('ruby', 10, 0, 0, 0),
                ('scala', 10, 0, 0, 0),
                ('swift', 10, 0, 0, 0),
            ]
            root = report(directory, **self._rows(rows))
            card = capability.score([root])
            score = card['domains']['structure_polyglot']['score']
            # 0.2 + 0.0 (resolved=0/0 -> None? actually _ratio with 0 is 0)
            # + 1.0 = 1.2/3 = 0.4 -> below target
            self.assertLess(score, 0.5)


class HighWaterTests(unittest.TestCase):
    """The bar a domain has already cleared must survive the run that fails to clear it."""

    def _card(self, **scores):
        return {'domains': {name: {'score': value} for name, value in scores.items()}}

    def test_a_mark_goes_up_and_never_comes_back_down(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
        from capability_score import raise_high_water
        with tempfile.TemporaryDirectory() as tmp:
            record = Path(tmp) / 'high-water.json'
            raise_high_water(self._card(alpha=0.5, beta=0.9), record)
            self.assertEqual(json.loads(record.read_text())['domains'], {'alpha': 0.5, 'beta': 0.9})
            # A better run raises alpha; a worse one must leave beta where it was.
            raised = raise_high_water(self._card(alpha=0.8, beta=0.1), record)
            stored = json.loads(record.read_text())
            self.assertEqual(stored['domains'], {'alpha': 0.8, 'beta': 0.9})
            self.assertEqual(raised, ['alpha: 0.5 -> 0.8'])
            self.assertIn('beta', stored['reached_at'])

    def test_an_unmeasured_domain_neither_sets_nor_erases_a_mark(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
        from capability_score import raise_high_water
        with tempfile.TemporaryDirectory() as tmp:
            record = Path(tmp) / 'high-water.json'
            raise_high_water(self._card(alpha=0.7), record)
            raise_high_water(self._card(alpha=None), record)
            self.assertEqual(json.loads(record.read_text())['domains'], {'alpha': 0.7})

    def test_a_report_built_without_the_engines_is_refused_rather_than_scored(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
        from capability_score import engines_were_off
        with tempfile.TemporaryDirectory() as tmp:
            off, on = Path(tmp) / 'off', Path(tmp) / 'on'
            for folder, stage in ((off, {'status': 'unavailable',
                                         'reason': 'external engines were not requested for this run'}),
                                  (on, {'status': 'ok', 'reason': ''})):
                folder.mkdir()
                (folder / 'run-manifest.json').write_text(json.dumps({'stages': {'engines': stage}}))
            self.assertEqual(engines_were_off([off, on]), [str(off)])
            # A binary that is simply absent is a different situation and must not be refused.
            (off / 'run-manifest.json').write_text(json.dumps(
                {'stages': {'engines': {'status': 'unavailable', 'reason': 'no external engine is installed'}}}))
            self.assertEqual(engines_were_off([off, on]), [])


class CoverageFloorTests(unittest.TestCase):
    """A detector that read a corner of the snapshot must not report a clean result for all of it."""

    def _sets(self, observed, blocked):
        return {'redundancy': {'facts': [], 'summary': {'files_observed': observed,
                                                        'files_blocked': blocked}},
                'syntax': {'facts': [{'kind': 'symbol', 'value': {'kind': 'function'}}] * 50},
                'fingerprint': {'facts': [], 'summary': {'files_observed': observed,
                                                         'files_blocked': blocked}}}

    def test_a_detector_that_analysed_almost_nothing_reports_coverage_not_a_score(self):
        from eaos.sustainability import _indicator_minimal_path, _indicator_single_source
        # One Python file out of 1021 produced 0.0 and a green tick over a Go repository whose
        # language the detector cannot read.
        for compute in (_indicator_minimal_path, _indicator_single_source):
            with self.subTest(indicator=compute.__name__):
                row = compute(self._sets(observed=1, blocked=1020))
                self.assertIs(row['measured'], False)
                self.assertIsNone(row['value'])
                self.assertIn('1 of 1021', row['reason'])

    def test_a_detector_that_covered_the_snapshot_still_reports_its_number(self):
        from eaos.sustainability import _indicator_minimal_path
        row = _indicator_minimal_path(self._sets(observed=200, blocked=8))
        self.assertIs(row['measured'], True)
        self.assertEqual(row['value'], 0.0)

    def test_an_unmeasured_indicator_proposes_no_move_to_close_a_gap_nobody_measured(self):
        from eaos.sustainability import compute
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            # No facts at all: every indicator is unmeasured, and nothing may be proposed.
            (Path(tmp) / 'facts').mkdir()
            result = compute(tmp)
        self.assertEqual(result['moves'], [])
