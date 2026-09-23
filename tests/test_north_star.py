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
        self.assertEqual(self.tool.main(['measure', '--only', 'R1', '--min', '1.0']), 2)


if __name__ == '__main__':
    unittest.main()
