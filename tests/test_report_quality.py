"""report-quality.json: the four reports judged by their tools, and the generators that make them pass."""
import json
import unittest
from pathlib import Path
from unittest import mock

from shared_fixture import Workspace

from eaos import report_quality
from eaos.compose.four_reports import escape, wrap
from eaos.engines.process import which

TOOLS = bool(which('vale')) and bool(which('markdownlint-cli2'))


class RecordTests(Workspace):
    def test_a_tool_that_is_not_installed_is_null_never_zero(self):
        (Path(self.tmp) / 'CURRENT-STATE.md').write_text('# x\n', encoding='utf-8')
        with mock.patch.object(report_quality, 'which', return_value=None):
            record = report_quality.check(self.tmp)
        self.assertEqual(record['reports'], [{'name': 'CURRENT-STATE.md', 'vale_errors': None, 'markdownlint_errors': None}])
        self.assertEqual(record['passing'], 0)

    def test_only_the_four_reports_present_are_listed_and_the_record_meets_its_contract(self):
        (Path(self.tmp) / 'TARGET-STATE.md').write_text('# x\n', encoding='utf-8')
        (Path(self.tmp) / 'NOTES.md').write_text('# x\n', encoding='utf-8')
        record = report_quality.check(self.tmp)
        self.assertEqual([r['name'] for r in record['reports']], ['TARGET-STATE.md'])
        from eaos.artifact_contracts import load_valid
        self.assertEqual(load_valid('report-quality', self.tmp), json.loads((Path(self.tmp) / 'report-quality.json').read_text()))

    @unittest.skipUnless(TOOLS, 'vale and markdownlint-cli2 are not installed: python -m eaos tools install --stage assessment')
    def test_a_report_with_a_vague_word_and_a_skipped_heading_fails_both(self):
        (Path(self.tmp) / 'GAP-AND-STRATEGY.md').write_text('# Gap\n\n### Detail\n\nMaybe later.\n', encoding='utf-8')
        row = report_quality.check(self.tmp)['reports'][0]
        self.assertGreater(row['vale_errors'], 0)
        self.assertGreater(row['markdownlint_errors'], 0)


class GeneratorTests(unittest.TestCase):
    """Text from the project is literal in the reports: the fix for markdownlint lives in the generator."""

    def test_identifiers_do_not_become_emphasis_or_html(self):
        self.assertEqual(escape('_open_lock in List<Item> *x*'), '\\_open\\_lock in List\\<Item\\> \\*x\\*')

    def test_code_spans_stay_as_written_and_a_cut_span_is_closed(self):
        self.assertEqual(escape('`src/_a_b.py` and _c'), '`src/_a_b.py` and \\_c')
        self.assertEqual(escape('cut `src/_a'), 'cut `src/_a`')

    def test_a_wrapped_line_never_starts_a_heading_or_a_list(self):
        for line in wrap('x ' * 38 + '# not a heading - 3. not a list') + wrap('a ' * 39 + '1. no', initial_indent='- ', subsequent_indent='  ')[1:]:
            self.assertNotRegex(line.lstrip(), r'^(#|[-+>]\s|\d+[.)]\s)')


if __name__ == '__main__':
    unittest.main()
