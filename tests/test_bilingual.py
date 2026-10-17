"""Every document whole in each language: only the pieces in the other language are sent, as templates, once, and kept."""
import json
import unittest
from pathlib import Path
from unittest import mock

from eaos import bilingual
from shared_fixture import scratch


class Dictionary:
    """A model that translates by a table and counts what it was sent."""
    def __init__(self, table): self.table, self.sent = table, []

    def complete(self, messages, small=False, stage=None):
        items = json.loads(messages[-1]['content'])['items']
        self.sent += items.values()
        return {'items': {key: self.table.get(item, item) for key, item in items.items()}}, {}


class BilingualTests(unittest.TestCase):
    def test_whole_pieces_are_sent_as_templates_once_and_the_rest_stay_as_written(self):
        # EAOS's own check, 2026-10-14: 2818 lines cut mid sentence, sent one by one, 54 minutes and $2.19
        report = Path(scratch()) / 'technical'
        report.mkdir()
        (report / 'START-HERE.md').write_text(
            '# Start here\n\nThe component has 2 live claims\nin `plan.py`.\n\n```\nkeep this code\n```\n'
            '| a | --- |\n| local | eaos/x.py |\n- The component has 7 live claims in `cli.py`.\n')
        model = Dictionary({'Start here': 'ابدأ هنا', 'local': 'محلي',
                            'The component has ⟦1⟧ live claims in ⟦2⟧.': 'للمكوّن ⟦1⟧ ادعاءات قائمة في ⟦2⟧.'})
        with mock.patch.object(bilingual, 'SEED', report / 'none.json'):
            counts = bilingual.translate(report, model)
            self.assertEqual(counts, {'pieces': 3, 'remembered': 0, 'calls': 1, 'failed': 0})
            self.assertEqual((report / 'i18n/ar/START-HERE.md').read_text(),
                             '# ابدأ هنا\n\nللمكوّن 2 ادعاءات قائمة في `plan.py`.\n\n```\nkeep this code\n```\n'
                             '| a | --- |\n| محلي | eaos/x.py |\n- للمكوّن 7 ادعاءات قائمة في `cli.py`.\n')
            again = Dictionary({})
            self.assertEqual(bilingual.translate(report, again)['remembered'], 3)
            self.assertEqual(again.sent, [], 'the next check sends nothing it translated before')
            (report.parent / bilingual.MEMORY).unlink()
            unsound = Dictionary({'The component has ⟦1⟧ live claims in ⟦2⟧.': 'للمكوّن ادعاءات قائمة.'})
            self.assertEqual(bilingual.translate(report, unsound)['failed'], 1, 'an answer that lost a slot is not kept')
            self.assertEqual(unsound.sent.count('The component has ⟦1⟧ live claims in ⟦2⟧.'), 2, 'it is asked once more')
            self.assertIn('- The component has 7 live claims in `cli.py`.', (report / 'i18n/ar/START-HERE.md').read_text())
