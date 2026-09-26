"""The EAOS writing style, checked by Vale and markdownlint-cli2 with the rules EAOS ships."""
import subprocess
import unittest
from pathlib import Path

from shared_fixture import Workspace

from eaos.engines.process import which
from eaos.report_quality import MARKDOWNLINT_CONFIG, VALE_CONFIG, markdownlint_errors, vale_errors


def installed(name):
    return bool(which(name))


class ValeStyleTests(Workspace):
    def write(self, text):
        (Path(self.tmp) / 'CURRENT-STATE.md').write_text(text, encoding='utf-8')
        return vale_errors(self.tmp, 'CURRENT-STATE.md')

    @unittest.skipUnless(installed('vale'), 'vale is not installed: python -m eaos tools install --stage assessment')
    def test_vague_wording_is_an_error_in_arabic_and_english(self):
        self.assertEqual(self.write('# الوضع\n\nربما يحتاج النظام إلى تحسين عام.\n'), 2)
        self.assertEqual(self.write('# State\n\nThe service may need various fixes, etc.\n'), 2)

    @unittest.skipUnless(installed('vale'), 'vale is not installed: python -m eaos tools install --stage assessment')
    def test_evidenced_wording_passes(self):
        self.assertEqual(self.write('# الوضع\n\nصفحة `/vehicles` تنادي قاعدة البيانات 14 مرة (FACT-1a2b).\n'), 0)

    @unittest.skipUnless(installed('vale'), 'vale is not installed: python -m eaos tools install --stage assessment')
    def test_a_word_inside_a_code_span_is_not_prose(self):
        self.assertEqual(self.write('# State\n\nThe function `maybe_parse` returns 3 values.\n'), 0)


class MarkdownlintStructureTests(Workspace):
    def lint(self, text):
        (Path(self.tmp) / 'EXECUTION-PLAN.md').write_text(text, encoding='utf-8')
        return markdownlint_errors(self.tmp, 'EXECUTION-PLAN.md')

    @unittest.skipUnless(installed('markdownlint-cli2'), 'markdownlint-cli2 is not installed: python -m eaos tools install')
    def test_a_skipped_heading_level_and_a_second_title_are_errors(self):
        self.assertGreater(self.lint('# Plan\n\n### Milestones\n\n# Another title\n'), 0)

    @unittest.skipUnless(installed('markdownlint-cli2'), 'markdownlint-cli2 is not installed: python -m eaos tools install')
    def test_a_long_evidence_line_is_not_an_error(self):
        self.assertEqual(self.lint('# Plan\n\n' + ' '.join(['word'] * 60) + '\n'), 0)

    def test_the_configs_ship_where_the_tools_are_told_to_look(self):
        self.assertTrue(VALE_CONFIG.is_file() and MARKDOWNLINT_CONFIG.is_file())
        self.assertTrue((VALE_CONFIG.parent / 'styles/EAOS/VagueArabic.yml').is_file())
        self.assertTrue((VALE_CONFIG.parent / 'styles/EAOS/VagueEnglish.yml').is_file())


if __name__ == '__main__':
    unittest.main()
