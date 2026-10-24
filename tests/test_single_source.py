"""Report numbers and data access stay with the Studio model: the view only draws."""
import ast
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.report import human_report
from eaos.analysis import model as M
from tests.test_human_report import report



class SingleSource(unittest.TestCase):
    def test_progress_and_milestones_are_counted_once_in_the_model(self):
        with tempfile.TemporaryDirectory() as folder:
            progress = {'ledger': {'cards': [{'id': 'TASK-1', 'state': 'on_branch'}, {'id': 'TASK-2', 'state': 'done'}]}}
            m = human_report.model(report(folder), progress)
        cards = M.task_cards(m)
        totals = M.gap_totals(m, cards)
        self.assertEqual((totals['closed'], totals['on_branch']), (1, 1))
        counts = M.milestone_counts(m['plan']['milestones'][0], cards, {r['id']: r for r in m['rows']})
        self.assertEqual((counts['closed'], counts['total'], counts['percent']), (1, 3, 33))
        # An unmeasured area stays unknown.
        self.assertIsNone(m['score']['areas']['performance']['score'])
        self.assertNotIn('data-meaning="performance score out of 100"', human_report.render(m, 'example'))

    def test_the_view_reads_no_record_and_computes_no_count(self):
        with tempfile.TemporaryDirectory() as folder:
            m = human_report.model(report(folder))
            before = human_report.render(m, 'example')
            with mock.patch.object(Path, 'read_text', side_effect=AssertionError('view read a report file')):
                self.assertEqual(human_report.render(m, 'example'), before)
        trees = [ast.parse(path.read_text()) for path in Path(human_report.__file__).parent.glob('*.py')]
        for node in (node for tree in trees for node in ast.walk(tree)):
            if not isinstance(node, ast.FunctionDef): continue
            for call in ast.walk(node):
                if not isinstance(call, ast.Call): continue
                if isinstance(call.func, ast.Attribute):
                    self.assertNotIn(call.func.attr, ('read_text', 'read_bytes', 'open', 'component_map', 'drill_data', 'flow_charts', 'build'))
                if isinstance(call.func, ast.Name) and call.func.id == 'sum':
                    self.assertEqual(node.name, 'squarify', 'only drawing geometry belongs in the view')
                if isinstance(call.func, ast.Name) and call.func.id == 'num':
                    self.assertFalse(any(isinstance(n, ast.BinOp) for n in ast.walk(call.args[0])))
                    self.assertFalse(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'len' for n in ast.walk(call.args[0])))
        for script in (human_report.MAP_JS, human_report.SYSTEM_JS):
            self.assertNotRegex(script, r'N\([^,]*\.length')

    def test_map_counts_follow_what_is_drawn(self):
        sm = {'pages': [{'traced': True}], 'callers': [{}, {}], 'apis': [{'handlers': ['h']}],
              'handlers': [{}], 'modules': [], 'data': [{'id': 'T:a'}, {'id': 'S:a'}]}
        counts = M.system_counts(sm)
        self.assertEqual(counts['columns'], (3, 1, 1, 0, 2))
        self.assertEqual((counts['answered'], counts['tables'], counts['services']), (1, 1, 1))
        drill = {'files': ['a', 'b', 'c'], 'imports': [[1, 2], [0], []], 'functions': [['a'], ['b'], []],
                 'calls': [(0, 'a', 1, 'b', 2)],
                 'comps': [{'files': [0, 1], 'used_by': [], 'uses': [[1, 2]]}]}
        M.drill_counts(drill)
        self.assertEqual(drill['comps'][0]['counts'], {'inside': 2, 'shown': 2, 'more': 0, 'used_by': 0, 'uses': 1})
        self.assertEqual(drill['file_counts'], [{'own': 1, 'left': 0, 'right': 1}, {'own': 1, 'left': 1, 'right': 0},
                                                {'own': 0, 'left': 0, 'right': 0}])
