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
            spec = {'name': 'p', 'truth': {'user_surfaces': 4, 'leftovers': ['temp_old.tsx'], 'secrets': ['.env']}}
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

    def test_an_unknown_indicator_is_refused(self):
        self.assertEqual(load_tool().main(['measure', '--only', 'ZZ9']), 2)


if __name__ == '__main__':
    unittest.main()
