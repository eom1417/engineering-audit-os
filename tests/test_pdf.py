"""EXECUTIVE.pdf: one page, typeset from the report's records, with no number the records do not hold."""
import json
import re
import unittest
from pathlib import Path

from shared_fixture import Workspace

from eaos.compose import pdf


def records(out):
    """A report folder with the three records the page reads."""
    out = Path(out)
    (out / 'reports.json').write_text(json.dumps({'schema_version': 1, 'reports': {
        'CURRENT-STATE.md': {'features': {'value': 24, 'source': 'features.json'},
                             'high_or_critical': {'value': 7, 'source': 'debt-register.json'}},
        'EXECUTION-PLAN.md': {'cards': {'value': 259, 'source': 'plan.json'}, 'ready': {'value': 221, 'source': 'plan.json'}}}}))
    (out / 'debt-register.json').write_text(json.dumps({'items': [
        {'id': f'DEBT-00{n}', 'severity': 'high', 'title': f'`src/_mod{n}.ts` carries {40 + n} branches'} for n in range(1, 6)]}))
    (out / 'plan.json').write_text(json.dumps({'milestones': [
        {'id': 'M01', 'name': 'stabilize', 'goal': 'No broken reference remains.', 'goal_ar': 'لا يبقى مرجع معطّل.', 'tasks': ['T1', 'T2']},
        {'id': 'M02', 'name': 'build:`api`', 'goal': '`api` is reshaped.', 'goal_ar': 'تشكيل `api`.', 'tasks': ['T3']}]}))


def numbers(value):
    return set(re.findall(r'\d+', json.dumps(value, ensure_ascii=False)))


class ContentTests(Workspace):
    def test_every_number_on_the_page_is_in_a_source_record(self):
        records(self.tmp)
        for language in ('ar', 'en'):
            page = pdf.content(self.tmp, language)
            shown = numbers({key: page[key] for key in ('decision', 'numbers', 'risks', 'milestones')})
            source = set()
            for name in ('reports.json', 'debt-register.json', 'plan.json'):
                source |= numbers(json.loads((Path(self.tmp) / name).read_text()))
            self.assertLessEqual(shown, source, language)

    def test_three_numbers_three_risks_and_the_ready_share_in_words(self):
        records(self.tmp)
        page = pdf.content(self.tmp, 'ar')
        self.assertEqual(len(page['numbers']), 3)
        self.assertEqual(len(page['risks']), 3)
        self.assertEqual(page['numbers'][2]['value'], '221 من 259')
        self.assertTrue(all(n['source'].startswith('reports.json') for n in page['numbers']))

    def test_markdown_code_marks_do_not_reach_the_page(self):
        records(self.tmp)
        page = pdf.content(self.tmp, 'en')
        self.assertNotIn('`', json.dumps({key: page[key] for key in ('decision', 'risks', 'milestones')}, ensure_ascii=False))


class TemplateTests(unittest.TestCase):
    def test_the_template_holds_no_word_or_number_of_its_own(self):
        text = pdf.TEMPLATE.read_text(encoding='utf-8')
        code = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('//'))
        # layout values (sizes, colours, grey levels) are the only digits; no quoted prose, no figures
        layout = re.sub(r'\d+(\.\d+)?(pt|cm|em|fr)|luma\(\d+\)|rgb\("#[0-9a-f]+"\)|\(level: \d\)|size: \d+pt|\d+%|"[^"]*"', '', code)
        self.assertNotRegex(layout, r'\d', 'a number outside layout')
        quoted = set(re.findall(r'"([^"]*)"', code)) - {'executive.json', 'ar', 'a4', 'bold', 'Noto Naskh Arabic', 'Noto Sans', 'DejaVu Sans'}
        self.assertEqual({q for q in quoted if not q.startswith('#')}, set())


class TypesetTests(Workspace):
    @unittest.skipIf(pdf.available('ar') or pdf.available('en'),
                     'Typst or a Noto font is missing: python -m eaos tools install --only typst; apt-get install fonts-noto-core')
    def test_the_pdf_is_one_page_in_both_languages(self):
        records(self.tmp)
        for language in ('ar', 'en'):
            self.assertEqual(pdf.write(self.tmp, language), 1, language)
            self.assertTrue((Path(self.tmp) / 'EXECUTIVE.pdf').read_bytes().startswith(b'%PDF'))

    def test_without_typst_the_reason_is_stated(self):
        from unittest import mock
        with mock.patch.object(pdf, 'which', return_value=None):
            self.assertIn('Typst is not installed', pdf.available('ar'))


if __name__ == '__main__':
    unittest.main()
