"""The destination record: valid, rendered, and scored the way it says it is scored."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_tool():
    spec = importlib.util.spec_from_file_location('north_star', ROOT / 'tools/north_star.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NorthStarTests(unittest.TestCase):
    def setUp(self):
        self.tool = load_tool()
        self.record = json.loads((ROOT / 'docs/north-star.json').read_text(encoding='utf-8'))

    def test_the_record_is_valid(self):
        self.assertEqual(self.tool.validate(self.record), [])

    def test_the_rendered_document_is_not_stale(self):
        self.assertEqual(self.tool.main(['--check']), 0)

    def test_milestones_progress_in_roadmap_order_and_the_first_open_one_is_current(self):
        rows = self.tool.progress(self.record)
        states = [state for _, _, state in rows]
        self.assertEqual(len(rows), len(self.record['milestones']))
        self.assertLessEqual(states.count('current'), 1)
        if 'current' in states:
            self.assertTrue(all(state == 'done' for state in states[:states.index('current')]))
            self.assertNotIn('done', states[states.index('current'):])

    def test_a_milestone_needing_a_sandbox_waits_on_the_owner(self):
        record = copy.deepcopy(self.record)
        for milestone in record['milestones']:
            for task in milestone['tasks']: task['status'] = 'todo'
        states = {milestone['id']: state for _, milestone, state in self.tool.progress(record)}
        first = record['roadmap'][0]['milestones'][0]
        self.assertEqual(states[first], 'current')
        waiting = [m['id'] for m in record['milestones'] if m['id'] != first and any(t['needs'] != 'none' for t in m['tasks'])]
        self.assertTrue(waiting)
        self.assertTrue(all(states[name] == 'owner' for name in waiting))

    def test_both_readmes_carry_the_current_generated_blocks(self):
        done = self.tool.completion(self.record)
        for language, path in self.tool.READMES.items():
            text = path.read_text(encoding='utf-8')
            for name in self.tool.BLOCKS:
                block = self.tool.readme_block(self.record, name, language)
                self.assertEqual(self.tool.with_block(text, name, block), text, f'{path.name} {name} is stale')
                self.assertIn('```mermaid', block)
            progress = self.tool.readme_block(self.record, 'progress', language)
            self.assertIn(f"{done['points']} {'من' if language == 'ar' else 'of'} 100", progress)

    def test_a_stale_readme_block_fails_the_check(self):
        record = copy.deepcopy(self.record)
        for milestone in record['milestones']:
            for task in milestone['tasks']: task['status'] = 'done'
        text = self.tool.READMES['ar'].read_text(encoding='utf-8')
        self.assertNotEqual(self.tool.with_block(text, 'progress', self.tool.readme_block(record, 'progress', 'ar')), text)

    def test_every_milestone_and_phase_has_an_english_title(self):
        record = copy.deepcopy(self.record)
        del record['milestones'][0]['title_en']
        self.assertIn(f"{record['milestones'][0]['id']}: no title_en (the READMEs are bilingual)", self.tool.validate(record))

    def test_the_headline_is_points_out_of_100_and_every_step_has_a_card(self):
        text = self.tool.render(self.record)
        done = self.tool.completion(self.record)
        self.assertIn(f"### التقدم: **{done['points']} من 100 نقطة**", text)
        for sequence, milestone, _ in done['rows']:
            self.assertIn(f"### الخطوة {sequence} · {milestone['id']} — {milestone['title']}", text)
        self.assertEqual(text.count('**بوابة الانتقال إلى الخطوة التالية**'), len(self.record['milestones']))


class StepTests(unittest.TestCase):
    """The progress model: declared weights, measured completion, and a gate that is enforced."""

    def setUp(self):
        self.tool = load_tool()
        import north_star_steps
        self.steps = north_star_steps
        self.record = json.loads((ROOT / 'docs/north-star.json').read_text(encoding='utf-8'))

    def test_weights_sum_to_100_and_progress_is_the_sum_of_step_points(self):
        self.assertEqual(sum(m['weight'] for m in self.record['milestones']), 100)
        total = sum(self.steps.step(m, self.record)['points'] for m in self.record['milestones'])
        self.assertAlmostEqual(self.steps.overall(self.record), round(total, 1))

    def test_weights_that_do_not_sum_to_100_are_rejected(self):
        record = copy.deepcopy(self.record)
        record['milestones'][0]['weight'] += 1
        self.assertIn('step weights must sum to 100', self.tool.validate(record))

    def test_a_step_without_its_tools_or_output_is_rejected(self):
        record = copy.deepcopy(self.record)
        record['milestones'][0]['tools'] = []
        self.assertIn(f"{record['milestones'][0]['id']}: no tools", self.tool.validate(record))

    def test_a_closed_task_counts_whole_and_an_open_one_is_capped_below_it(self):
        task = {'status': 'todo', 'acceptance': 'python tools/north_star.py measure --only P1 --min 0.5'}
        self.assertEqual(self.steps.task_completion(dict(task, status='done'), self.record), 1.0)
        open_value = self.steps.task_completion(task, self.record)
        self.assertLessEqual(open_value, self.steps.OPEN_CAP)
        record = copy.deepcopy(self.record)
        for capability in record['capabilities']:
            for row in capability['indicators']:
                if row['id'] == 'P1': row['value'] = 0.25
        self.assertAlmostEqual(self.steps.task_completion(task, record), round(self.steps.OPEN_CAP * 0.5, 3))

    def test_measure_without_a_floor_is_a_condition_not_a_threshold(self):
        items = self.steps.criteria({'status': 'todo', 'acceptance': 'python tools/north_star.py measure --only K1'}, self.record)
        self.assertEqual([item['kind'] for item in items], ['measured'])

    def test_a_step_cannot_close_before_the_one_before_it(self):
        record = copy.deepcopy(self.record)
        first = self.tool.step_order(record)[0]
        milestone = next(m for m in record['milestones'] if m['id'] == first)
        milestone['tasks'][0]['status'] = 'todo'
        self.assertTrue(any('while an earlier step is open' in problem for problem in self.tool.validate(record)))

    def test_a_closed_step_whose_gate_fell_is_rejected(self):
        record = copy.deepcopy(self.record)
        closed = next(t for m in record['milestones'] for t in m['tasks']
                      if t['status'] == 'done' and '--min' in t['acceptance'])
        indicator = self.steps.MEASURE.search(closed['acceptance']).group(1)
        for capability in record['capabilities']:
            for row in capability['indicators']:
                if row['id'] == indicator: row['value'] = 0.0
        self.assertTrue(any(f"{closed['id']}: closed, but its gate no longer holds" in problem for problem in self.tool.validate(record)))

    def test_the_gate_on_an_arrow_names_every_threshold(self):
        milestone = next(m for m in self.record['milestones'] if m['id'] == 'NS8')
        text = self.steps.gate_text(self.steps.step(milestone, self.record)['gate'], 'en', limit=10)
        for indicator in ('P1=1', 'P3≥0.8', 'P9≥0.8'):
            self.assertIn(indicator, text)

    def test_the_charts_draw_every_step_and_stage_once(self):
        for language in ('ar', 'en'):
            chart = '\n'.join(self.tool.readme_block(self.record, 'progress', language).splitlines())
            for milestone in self.record['milestones']:
                self.assertEqual(chart.count(f"        {milestone['id']}["), 1)
            pipeline = self.tool.readme_block(self.record, 'pipeline', language)
            for stage in self.record['pipeline']:
                self.assertEqual(pipeline.count(f"        {stage['id']}["), 1)


class NorthStarScoreTests(unittest.TestCase):
    def setUp(self):
        self.tool = load_tool()
        self.record = json.loads((ROOT / 'docs/north-star.json').read_text(encoding='utf-8'))

    def test_an_unmeasured_indicator_counts_as_zero(self):
        record = copy.deepcopy(self.record)
        capability = record['capabilities'][0]
        for row in capability['indicators']: row['value'] = 1.0
        full = self.tool.score(record)['capabilities'][capability['id']]
        capability['indicators'][0]['value'] = None
        partial = self.tool.score(record)['capabilities'][capability['id']]
        self.assertEqual(full, 1.0)
        self.assertLess(partial, full)

    def test_overall_is_the_weighted_mean_in_percent(self):
        scores = self.tool.score(self.record)
        expected = sum(c['weight'] * scores['capabilities'][c['id']] for c in self.record['capabilities'])
        self.assertAlmostEqual(scores['overall_percent'], round(expected, 1))

    def test_weights_that_do_not_sum_to_100_are_rejected(self):
        record = copy.deepcopy(self.record)
        record['capabilities'][0]['weight'] += 1
        self.assertIn('capability weights must sum to 100', self.tool.validate(record))

    def test_a_task_moving_an_unknown_indicator_is_rejected(self):
        record = copy.deepcopy(self.record)
        record['milestones'][0]['tasks'][0]['moves'].append('ZZ9')
        self.assertTrue(any('unknown indicator ZZ9' in problem for problem in self.tool.validate(record)))

    def test_an_unknown_command_fails_instead_of_passing_an_acceptance_check(self):
        self.assertEqual(self.tool.main(['frobnicate', '--min', '1.0']), 2)

    def test_a_stage_no_milestone_serves_is_rejected(self):
        record = copy.deepcopy(self.record)
        for milestone in record['milestones']:
            milestone['stages'] = [stage for stage in milestone.get('stages', []) if stage != 'S12']
        self.assertIn('S12: no milestone serves this stage', self.tool.validate(record))

    def test_a_milestone_naming_an_unknown_stage_is_rejected(self):
        record = copy.deepcopy(self.record)
        record['milestones'][1]['stages'].append('S99')
        self.assertTrue(any('unknown stage S99' in problem for problem in self.tool.validate(record)))

    def test_a_milestone_outside_the_roadmap_is_rejected(self):
        record = copy.deepcopy(self.record)
        record['roadmap'][-1]['milestones'].remove('NS10')
        self.assertIn('NS10: must appear in exactly one roadmap phase', self.tool.validate(record))

    def _open_task(self, record):
        return next(t for t in self.tool.tasks(record) if t['status'] != 'done')

    def test_an_open_task_without_its_card_is_rejected(self):
        record = copy.deepcopy(self.record)
        task = self._open_task(record)
        for field in ('why', 'size', 'done_when'): task.pop(field)
        problems = self.tool.validate(record)
        for expected in ('no why', 'size must be one of', 'no done_when checklist'):
            self.assertTrue(any(task['id'] in p and expected in p for p in problems), expected)

    def test_an_acceptance_the_executor_writes_itself_is_rejected(self):
        record = copy.deepcopy(self.record)
        task = self._open_task(record)
        task['acceptance'] = 'python -m unittest tests.test_something -q'
        self.assertTrue(any(task['id'] in p and 'acceptance must run the measurement' in p for p in self.tool.validate(record)))

    def test_an_indicator_short_of_target_needs_an_open_task(self):
        record = copy.deepcopy(self.record)
        # Any indicator still short of its target will do; which one changes as the plan is executed.
        short = next(row['id'] for row in self.tool.indicators(record)
                     if row.get('value') is not None and row['value'] < row['target']
                     and any(row['id'] in task['moves'] for task in self.tool.tasks(record) if task.get('status') != 'done'))
        for task in self.tool.tasks(record):
            task['moves'] = [m for m in task['moves'] if m != short]
        self.assertIn(f'{short}: below its target and no open task moves it', self.tool.validate(record))

    def test_a_contract_that_does_not_exist_is_rejected(self):
        record = copy.deepcopy(self.record)
        task = self._open_task(record)
        task['writes'] = ['contract:nonexistent']
        self.assertTrue(any('writes unknown contract contract:nonexistent' in p for p in self.tool.validate(record)))

    def test_the_plan_is_not_finished_while_tasks_are_open(self):
        self.assertEqual(self.tool.main(['--finished']), 1)

    def test_milestones_listed_out_of_phase_order_are_rejected(self):
        record = copy.deepcopy(self.record)
        record['milestones'].append(record['milestones'].pop(0))
        self.assertIn('milestones must be listed in roadmap phase order', self.tool.validate(record))



def load_measure():
    import sys
    sys.path.insert(0, str(ROOT / 'tools'))
    import north_star_measure
    return north_star_measure


class MeasurementTests(unittest.TestCase):
    """Each automated indicator is computed from what a report contains, by its written definition."""

    def _report(self, root, claims=(), tasks=(), entry_points=(), relations=(), exit_code=0, files=()):
        root.mkdir(parents=True)
        (root / 'facts').mkdir()
        (root / 'dossier.json').write_text(json.dumps({'claims': list(claims), 'coverage': {'parse_coverage': 0.9}}))
        (root / 'plan.json').write_text(json.dumps({'tasks': list(tasks)}))
        (root / 'target-architecture.json').write_text(json.dumps({
            'current_components': [{'relation': r, 'reason': 'because'} for r in relations], 'decisions': [], 'gap_matrix': []}))
        (root / 'facts/entrypoints.json').write_text(json.dumps({'facts': [
            {'kind': 'entry_point', 'location': {'path': p}, 'value': {'surface': s, 'route': r, 'framework': f}}
            for p, s, r, f in entry_points]}))
        for name in files: (root / name).parent.mkdir(parents=True, exist_ok=True); (root / name).write_text('x')
        return root

    def _values(self, **report):
        import tempfile
        measure = load_measure()
        with tempfile.TemporaryDirectory() as tmp:
            out = self._report(Path(tmp) / 'r', **report)
            spec = {'name': 'p', 'truth': {'user_surfaces': 4, 'leftovers': ['temp_old.tsx'], 'credentials': [{'path': '.env', 'severity': 'public'}]}}
            record = {'corpus': [spec]}
            return measure.indicator_values([measure.Project(spec, out, report.get('exit_code', 0))], record)

    def test_build_scripts_and_library_exports_are_not_user_surfaces(self):
        values = self._values(entry_points=[('package.json', 'cli', 'npm run build', 'npm_script'),
                                            ('src/index.ts', 'library', 'x', 'public_api'),
                                            ('src/App.tsx', 'http', '/vehicles', 'react_router')])
        self.assertEqual(values['U2'][0], 0.25)
        self.assertEqual(values['R2'][0], 1.0)

    def test_structural_clone_claims_count_as_noise(self):
        values = self._values(claims=[{'statement': '5 symbols share the same structure up to identifier names'},
                                      {'statement': 'app.py imports db.py, which the declared policy forbids'}])
        self.assertEqual(values['S1'][0], 0.5)

    def test_a_leftover_counts_only_when_the_report_names_it(self):
        self.assertEqual(self._values()['D2'][0], 0.0)
        self.assertEqual(self._values(claims=[{'statement': 'temp_old.tsx is a leftover nothing imports'}])['D2'][0], 1.0)

    def test_a_public_key_reported_as_secret_does_not_count(self):
        import tempfile
        measure = load_measure()
        for severity, expected in (('public', 1.0), ('secret', 0.0)):
            with tempfile.TemporaryDirectory() as tmp:
                out = self._report(Path(tmp) / 'r')
                (out / 'facts/credentials.json').write_text(json.dumps({'facts': [
                    {'kind': 'committed_credential', 'location': {'path': '.env'}, 'value': {'severity': severity}}]}))
                spec = {'name': 'p', 'truth': {'user_surfaces': 1, 'credentials': [{'path': '.env', 'severity': 'public'}]}}
                values = measure.indicator_values([measure.Project(spec, out, 0)], {'corpus': [spec]})
                self.assertEqual(values['H1'][0], expected, severity)

    def test_two_of_four_dispositions_halve_the_decision_score(self):
        self.assertEqual(self._values(relations=['retain', 'modify'])['T4'][0], 0.5)

    def test_runnable_acceptance_excludes_human_review(self):
        tasks = [{'acceptance': [{'command': 'human review / مراجعة هندسية'}]},
                 {'acceptance': [{'command': 'python -m eaos policy check .'}]}]
        self.assertEqual(self._values(tasks=tasks)['P3'][0], 0.5)

    def test_a_failed_audit_lowers_reach(self):
        self.assertEqual(self._values(exit_code=2)['R1'][0], 0.0)

    def test_an_empty_checkout_is_not_at_its_commit(self):
        import subprocess, tempfile
        measure = load_measure()
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            (repo / 'a.py').write_text('x = 1\n')
            subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(repo), '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'a'], check=True)
            commit = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
            self.assertTrue(measure.checked_out(repo, commit))
            (repo / 'a.py').unlink()
            self.assertFalse(measure.checked_out(repo, commit))

    def _orchestration(self, files=(), **artifacts):
        """Measure the blueprint's stages over a report holding the given artifacts."""
        import tempfile
        measure = load_measure()
        with tempfile.TemporaryDirectory() as tmp:
            out = self._report(Path(tmp) / 'r')
            for name, content in artifacts.items():
                path = out / name.replace('__', '/')
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(content))
            corpus = Path(tmp) / 'corpus'
            for name in files:
                (corpus / 'p' / name).parent.mkdir(parents=True, exist_ok=True)
                (corpus / 'p' / name).write_text('x')
            previous, measure.CORPUS = measure.CORPUS, corpus
            try:
                spec = {'name': 'p', 'truth': {'user_surfaces': 1}}
                record = {'corpus': [spec], 'adopted_adapters': [{'name': 'syft', 'applies': 'all'},
                                                                 {'name': 'sqlfluff', 'applies': 'sql'}]}
                from eaos.indicators import orchestration_values
                return orchestration_values([measure.Project(spec, out, 0)], record.get('adopted_adapters') or [])
            finally:
                measure.CORPUS = previous

    def test_an_intake_counts_only_when_every_question_is_answered_or_defaulted(self):
        done = {'questions': [{'id': 'growth', 'status': 'answered'}, {'id': 'privacy', 'status': 'default'}]}
        open_ = {'questions': [{'id': 'growth', 'status': 'answered'}, {'id': 'privacy', 'status': 'unknown'}]}
        self.assertEqual(self._orchestration(**{'intake.json': done})['U6'][0], 1.0)
        self.assertEqual(self._orchestration(**{'intake.json': open_})['U6'][0], 0.0)

    def test_an_adapter_is_expected_only_where_it_applies(self):
        external = {'facts/external.json': {'summary': {'engines_observed': ['syft']}}}
        self.assertEqual(self._orchestration(files=['app.py'], **external)['R3'][0], 1.0)
        self.assertEqual(self._orchestration(files=['app.py', 'db/schema.sql'], **external)['R3'][0], 0.5)

    def test_a_report_counts_only_with_zero_style_and_structure_errors(self):
        quality = {'reports': [{'name': 'CURRENT-STATE.md', 'vale_errors': 0, 'markdownlint_errors': 0},
                               {'name': 'TARGET-STATE.md', 'vale_errors': 2, 'markdownlint_errors': 0}]}
        self.assertEqual(self._orchestration(**{'report-quality.json': quality})['P8'][0], 0.25)

    def test_supply_chain_needs_both_an_sbom_and_a_vulnerability_scan(self):
        sbom = {'sbom.cdx.json': {'components': [{'name': 'react'}]}}
        self.assertEqual(self._orchestration(**sbom)['H3'][0], 0.0)
        scanned = dict(sbom, **{'facts/external.json': {'summary': {'engines_observed': ['osv-scanner']}}})
        self.assertEqual(self._orchestration(**scanned)['H3'][0], 1.0)

    def _stage(self, report=None, runtime=None, plan_tasks=(), coverage=None):
        """Measure the 15-stage indicators over one report and its runtime directory."""
        import tempfile
        measure = load_measure()
        with tempfile.TemporaryDirectory() as tmp:
            out = self._report(Path(tmp) / 'r', tasks=plan_tasks)
            if coverage:
                (out / 'dossier.json').write_text(json.dumps({'claims': [], 'coverage': coverage}))
            previous = measure.RUNTIME, measure.CORPUS
            measure.RUNTIME, measure.CORPUS = Path(tmp) / 'runtime', Path(tmp) / 'corpus'
            (measure.CORPUS / 'p').mkdir(parents=True)
            (measure.CORPUS / 'p' / 'app.ts').write_text('x')
            try:
                for base, artifacts in ((out, report or {}), (measure.RUNTIME / 'p', runtime or {})):
                    for name, content in artifacts.items():
                        (base / name).parent.mkdir(parents=True, exist_ok=True)
                        (base / name).write_text(json.dumps(content))
                spec = {'name': 'p', 'truth': {'user_surfaces': 1}}
                project = measure.Project(spec, out, 0)
                from eaos.indicators import plan_values, runtime_values
                return {**plan_values([project]), **runtime_values([project])}
            finally:
                measure.RUNTIME, measure.CORPUS = previous

    def test_an_artifact_that_breaks_its_contract_counts_as_absent(self):
        good = {'schema_version': 1, 'files': [{'path': 'a.ts', 'language': 'typescript', 'loc': 10, 'complexity_max': 3,
                                                'churn': 2, 'fan_in': 1, 'missing': []}]}
        self.assertEqual(self._stage({'measurements.json': good}, coverage={'files_parsed': 2})['M1'][0], 0.5)
        bad = {'schema_version': 1, 'files': [{'path': 'a.ts', 'loc': 10}]}
        self.assertEqual(self._stage({'measurements.json': bad}, coverage={'files_parsed': 2})['M1'][0], 0.0)

    def test_high_risk_needs_two_tools_or_one_deterministic_witness(self):
        def item(id_, witnesses, severity='high'):
            return {'id': id_, 'title': 't', 'category': 'security', 'severity': severity, 'files': ['a.ts'],
                    'impact': 'i', 'recommendation': 'r', 'witnesses': [{'tool': t, 'finding_id': 'f', 'kind': k} for t, k in witnesses]}
        register = {'schema_version': 1, 'formula': 'f', 'items': [
            item('DEBT-001', [('semgrep', 'heuristic'), ('codegraph', 'heuristic')]),
            item('DEBT-002', [('secrets', 'deterministic')]),
            item('DEBT-003', [('semgrep', 'heuristic'), ('semgrep', 'heuristic')]),
            item('DEBT-004', [('semgrep', 'heuristic')], severity='medium')]}
        self.assertAlmostEqual(self._stage({'debt-register.json': register})['S3'][0], 0.667, places=3)
        self.assertEqual(self._stage()['S3'][0], 0.0)

    def test_a_kit_file_counts_only_when_its_own_tool_accepted_it(self):
        rows = [{'path': path, 'tool': 't', 'ok': True} for path, _ in __import__('eaos.indicators', fromlist=['KIT']).KIT if not path.endswith('/')]
        rows += [{'path': path + 'x.yaml', 'tool': 't', 'ok': True} for path, _ in __import__('eaos.indicators', fromlist=['KIT']).KIT if path.endswith('/')]
        full = self._stage({'handover/validation.json': {'schema_version': 1, 'files': rows}})['K1'][0]
        self.assertEqual(full, 1.0)
        rows[0]['ok'] = False
        self.assertLess(self._stage({'handover/validation.json': {'schema_version': 1, 'files': rows}})['K1'][0], 1.0)

    def test_a_mechanical_card_counts_only_when_its_codemod_changed_files(self):
        tasks = [{'pattern': 'remove_dead', 'codemod': {'tool': 'git', 'command': 'git rm a.ts', 'dry_run': {'exit': 0, 'files_changed': 1}}},
                 {'pattern': 'remove_dead', 'codemod': {'tool': 'git', 'command': 'git rm b.ts', 'dry_run': {'exit': 0, 'files_changed': 0}}},
                 {'pattern': 'canonicalize'}]
        self.assertEqual(self._stage(plan_tasks=tasks)['P9'][0], 0.5)

    def test_load_counts_only_with_both_sides_and_parity_only_for_what_passed_before(self):
        perf = {'schema_version': 1, 'conditions': {'build': 'vite build', 'warmup_s': 10, 'vus': 20, 'duration_s': 60, 'machine': 'm'},
                'scenarios': [{'id': 'QS-001', 'script': 'nfr/k6/a.js', 'threshold': {'p95_ms': 500, 'error_rate': 0.01},
                               'before': {'p95_ms': 400, 'error_rate': 0}, 'after': {'p95_ms': 300, 'error_rate': 0}},
                              {'id': 'QS-002', 'script': 'nfr/k6/b.js', 'threshold': {'p95_ms': 500, 'error_rate': 0.01},
                               'before': {'p95_ms': 400, 'error_rate': 0}, 'after': None}]}
        lock = lambda statuses: {'schema_version': 1, 'commit': 'c', 'backend': 'process',
                                 'results': [{'path': f's{i}.spec.ts', 'status': s} for i, s in enumerate(statuses)]}
        values = self._stage(runtime={'runtime/performance.json': perf,
                                      'behavior-lock/results.json': lock(['passed', 'passed', 'failed']),
                                      'behavior-lock/results-after.json': lock(['passed', 'failed', 'passed'])})
        self.assertEqual(values['E6'][0], 0.5)
        self.assertEqual(values['E7'][0], 0.5)

    def test_runtime_indicators_are_zero_for_a_project_never_run(self):
        values = self._stage()
        for indicator in ('E6', 'E7', 'E8', 'E9', 'E10', 'E11'):
            self.assertEqual(values[indicator][0], 0.0, indicator)

    def test_telemetry_counts_only_critical_surfaces(self):
        telemetry = {'schema_version': 1, 'surfaces': [{'surface': '/a', 'critical': True, 'spans': 3},
                                                        {'surface': '/b', 'critical': True, 'spans': 0},
                                                        {'surface': '/c', 'critical': False, 'spans': 0}]}
        self.assertEqual(self._stage(runtime={'runtime/telemetry.json': telemetry})['E10'][0], 0.5)

    def test_an_unknown_indicator_is_refused(self):
        self.assertEqual(load_tool().main(['measure', '--only', 'ZZ9']), 2)


if __name__ == '__main__':
    unittest.main()
