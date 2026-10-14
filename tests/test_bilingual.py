"""Every document whole in each language: only the lines in the other language are sent, once, and kept."""
import json
import tempfile
import unittest
from pathlib import Path

from eaos import bilingual


class Dictionary:
    """A model that translates by a table and counts what it was sent."""
    def __init__(self, table, broken=False): self.table, self.broken, self.sent = table, broken, []

    def complete(self, messages, small=False, stage=None):
        lines = json.loads(messages[-1]['content'])['lines']
        self.sent += lines
        return ({'lines': []} if self.broken else {'lines': [self.table[line] for line in lines]}), {}


class BilingualTests(unittest.TestCase):
    def test_only_the_lines_in_the_other_language_are_sent_once_and_the_rest_stay_as_written(self):
        # EAOS's own report, 2026-10-14: 153 documents, the median 42% Arabic in an Arabic report, START-HERE wholly English
        report = Path(tempfile.mkdtemp()) / 'technical'
        report.mkdir()
        (report / 'START-HERE.md').write_text('# Start here\n\nسطر عربي فيه `plan.py`\n\n```\nkeep this code\n```\n| --- |\n')
        model = Dictionary({'# Start here': '# ابدأ هنا', 'سطر عربي فيه `plan.py`': 'An Arabic line with `plan.py`'})
        self.assertEqual(bilingual.translate(report, model), {'lines': 2, 'remembered': 0, 'failed': 0, 'calls': 2})
        self.assertEqual((report / 'i18n/ar/START-HERE.md').read_text(), '# ابدأ هنا\n\nسطر عربي فيه `plan.py`\n\n```\nkeep this code\n```\n| --- |\n')
        self.assertEqual((report / 'i18n/en/START-HERE.md').read_text().split('\n')[2], 'An Arabic line with `plan.py`')
        again = Dictionary({})
        self.assertEqual(bilingual.translate(report, again)['remembered'], 2)
        self.assertEqual(again.sent, [], 'the next check sends nothing it translated before')
        (report.parent / bilingual.MEMORY).unlink()
        self.assertEqual(bilingual.translate(report, Dictionary({}, broken=True))['failed'], 2)
        self.assertEqual((report / 'i18n/ar/START-HERE.md').read_text().split('\n')[0], '# Start here', 'a failed batch keeps its lines')
