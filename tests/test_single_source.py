"""Report numbers and data access stay with the Studio model (NS37.T4 / F7)."""
import ast
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos import human_report
from eaos.studio import model as M
from tests.test_human_report import report


from tools.report_source import compare_numbers


class SingleSource(unittest.TestCase):
    def test_every_number_span_matches_the_model_in_both_languages(self):
        with tempfile.TemporaryDirectory() as folder:
            m = human_report.model(report(folder), {'waves': [{'number': 1, 'kept': ['TASK-1'], 'failed': {'TASK-2': 'failed'}}]})
            for lang in ('ar', 'en'):
                with self.subTest(lang=lang):
                    page, errors = human_report.render_parts(m, 'example', lang)
                    self.assertFalse(errors)
                    result = compare_numbers(page, M.number_catalog(m), M.chart_catalog(m))
                    self.assertGreater(result['total'], 150)
                    self.assertEqual(result['mismatches'], [])

    def test_wrong_or_unowned_number_is_rejected(self):
        catalog = {'pages': ['12']}
        self.assertEqual(compare_numbers('<span data-meaning="pages">13</span>', catalog)['matched'], 0)
        self.assertEqual(compare_numbers('<span data-meaning="unknown">12</span>', catalog)['matched'], 0)
        self.assertEqual(compare_numbers('<p>12</p>', catalog)['matched'], 0)
        self.assertEqual(compare_numbers('<code>file.py:12</code>', catalog)['total'], 0)

    def test_rendering_keeps_the_model_after_the_report_files_disappear(self):
        with tempfile.TemporaryDirectory() as folder:
            m = human_report.model(report(folder))
            before = human_report.render(m, 'example')
            with mock.patch.object(Path, 'read_text', side_effect=AssertionError('view read a report file')):
                after = human_report.render(m, 'example')
            self.assertEqual(before, after)

    def test_report_has_no_record_readers_or_count_formulas(self):
        source = Path(human_report.__file__).read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
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

    def test_unmeasured_area_stays_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            m = human_report.model(report(folder))
            self.assertIsNone(m['score']['areas']['performance']['score'])
            self.assertIn('performance score out of 100', M.number_catalog(m), M.chart_catalog(m))
            self.assertNotIn('data-meaning="performance score out of 100"', human_report.render(m, 'example'))

    def test_ledger_progress_and_milestones_share_the_model(self):
        with tempfile.TemporaryDirectory() as folder:
            progress = {'ledger': {'cards': [{'id': 'TASK-1', 'state': 'on_branch'}, {'id': 'TASK-2', 'state': 'resolved'}]}}
            m = human_report.model(report(folder), progress)
            cards = M.task_cards(m)
            totals = M.gap_totals(m, cards)
            self.assertEqual((totals['closed'], totals['on_branch']), (1, 1))
            counts = M.milestone_counts(m['plan']['milestones'][0], cards, {r['id']: r for r in m['rows']})
            self.assertEqual((counts['closed'], counts['total'], counts['percent']), (1, 3, 33))
            result = compare_numbers(human_report.render(m, 'example'), M.number_catalog(m), M.chart_catalog(m))
            self.assertEqual(result['mismatches'], [])

    def test_system_columns_include_shared_callers_only_once(self):
        sm = {'pages': [{'traced': True}], 'callers': [{}, {}], 'apis': [{'handlers': ['h']}],
              'handlers': [{}], 'modules': [], 'data': [{'id': 'T:a'}, {'id': 'S:a'}]}
        counts = M.system_counts(sm)
        self.assertEqual(counts['columns'], (3, 1, 1, 0, 2))
        self.assertEqual((counts['answered'], counts['tables'], counts['services']), (1, 1, 1))

    def test_drill_counts_follow_the_drawn_subset(self):
        drill = {'files': ['a', 'b', 'c'], 'imports': [[1, 2], [0], []], 'functions': [['a'], ['b'], []],
                 'calls': [(0, 'a', 1, 'b', 2)],
                 'comps': [{'files': [0, 1], 'used_by': [], 'uses': [[1, 2]]}]}
        M.drill_counts(drill)
        self.assertEqual(drill['comps'][0]['counts'], {'inside': 2, 'shown': 2, 'more': 0, 'used_by': 0, 'uses': 1})
        self.assertEqual(drill['file_counts'], [{'own': 1, 'left': 0, 'right': 1}, {'own': 1, 'left': 1, 'right': 0}, {'own': 0, 'left': 0, 'right': 0}])


    def test_pipeline_sheet_numbers_match_the_same_model(self):
        from tests.test_pipeline_sheet import fixture
        with tempfile.TemporaryDirectory() as folder:
            m = human_report.model(report(folder))
            m['pipeline'] = {'ar': fixture(), 'en': fixture()}
            for lang in ('ar', 'en'):
                page, errors = human_report.render_parts(m, 'example', lang)
                self.assertFalse(errors)
                result = compare_numbers(page, M.number_catalog(m), M.chart_catalog(m))
                self.assertEqual(result['mismatches'], [])
                self.assertIn('data-meaning="pipeline confidence percent"', page)

    def test_saved_measurement_rejects_stale_and_incomplete_results(self):
        from tools import report_source
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report-source' / 'example'
            output.mkdir(parents=True)
            stamp = output / 'comparison.json'
            data = {'project': 'example', 'source_sha256': 'old', 'complete': True, 'total': 4, 'matched': 4}
            with mock.patch.object(report_source, 'source_digest', return_value='current'):
                stamp.write_text(json.dumps(data))
                self.assertIsNone(report_source.value(folder)[0])
                data.update(source_sha256='current', complete=False)
                stamp.write_text(json.dumps(data))
                self.assertIsNone(report_source.value(folder)[0])
                data.update(complete=True, matched=3)
                stamp.write_text(json.dumps(data))
                self.assertEqual(report_source.value(folder)[0], .75)
