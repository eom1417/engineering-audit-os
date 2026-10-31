"""The design inventory (M18.15): how many ways each part is drawn, read from what the pages saved; two libraries for one job; a date shown three ways."""
import json
import tempfile
import unittest
from pathlib import Path

from eaos.analysis.design import findings, inventory as design
from eaos.report.human_report.design import section_design

BLUE = {'color': 'rgb(255, 255, 255)', 'background-color': 'rgb(0, 0, 255)', 'font-size': '14px', 'border-top-left-radius': '4px'}
NEAR = {**BLUE, 'background-color': 'rgb(0, 1, 255)'}
ROUND = {**BLUE, 'border-top-left-radius': '9px'}


def page(*buttons, text=''):
    sigs = list(dict.fromkeys(json.dumps(look) for look in buttons))
    els = {f'body:0>button:{i}': {'default': sigs.index(json.dumps(look))} for i, look in enumerate(buttons)}
    return {'sigs': [json.loads(s) for s in sigs], 'els': els, 'roles': {key: 'button' for key in els}, 'text': text, 'motion': {'durations': {'0.2s': 1}, 'easings': {'ease': 1}}, 'crops': {}}


def drawn_of(**more):
    return {'components': {}, 'formats': {}, 'libraries': {}, 'near_colours': [], 'values': {}, **more}


class Cards(unittest.TestCase):
    def test_a_part_drawn_many_ways_is_a_card_and_a_small_set_of_variants_is_not(self):
        part = lambda distinct, count: {'distinct': distinct, 'count': count, 'looks': [{'where': [{'page': 'a'}]}] * distinct}
        found = findings._looks(drawn_of(components={'button': part(11, 44), 'tab': part(2, 40), 'dialog': part(5, 5)}))
        self.assertEqual([row['place'] for row in found], ['button'])

    def test_a_date_in_two_forms_is_a_card_and_digits_or_one_form_are_not(self):
        rows = [{'form': 'a'}, {'form': 'b'}]
        found = findings._formats(drawn_of(formats={'date': rows, 'digits': rows, 'time': rows[:1]}))
        self.assertEqual([row['place'] for row in found], ['date'])

    def test_what_a_person_may_agree_to_merge_goes_to_the_most_used_and_the_nearest_step(self):
        values = {'color': {'rows': [{'value': 'rgb(1, 1, 1)', 'uses': 9}, {'value': 'rgb(2, 2, 2)', 'uses': 1}]},
                  'font_size': {'rows': [{'value': f'{n}px', 'uses': 50} for n in (12, 14, 16, 18, 20, 24, 28, 32)] + [{'value': '15px', 'uses': 1}]}}
        merged = findings.merges(drawn_of(values=values, near_colours=[['rgb(1, 1, 1)', 'rgb(2, 2, 2)']]))
        self.assertIn({'kind': 'color', 'from': '#020202', 'to': '#010101', 'uses': 1}, merged)
        self.assertIn({'kind': 'font_size', 'from': '15px', 'to': '14px', 'uses': 1}, merged)


class Inventory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def drawn(self, pages):
        return design.inventory(pages, self.root)

    def test_a_part_drawn_three_ways_is_counted_as_three_looks_with_where_each_is(self):
        drawn = self.drawn({'a': page(BLUE, BLUE, ROUND), 'b': page(NEAR)})
        buttons = drawn['components']['button']
        self.assertEqual((buttons['count'], buttons['distinct']), (4, 3))
        self.assertEqual((buttons['looks'][0]['count'], buttons['looks'][0]['where'][0]['page']), (2, 'a'))
        self.assertEqual(drawn['values']['radius']['distinct'], 2)

    def test_near_colours_are_named_and_a_part_used_one_way_is_one_look(self):
        self.assertEqual(self.drawn({'a': page(BLUE, BLUE)})['components']['button']['distinct'], 1)
        self.assertTrue(any({'rgb(0, 0, 255)', 'rgb(0, 1, 255)'} <= set(group) for group in self.drawn({'a': page(BLUE, NEAR)})['near_colours']))

    def test_a_date_shown_three_ways_is_three_forms_and_a_time_two(self):
        formats = self.drawn({'a': page(BLUE, text='2026-01-31 and 31/01/2026 and Jan 31, 2026 at 3:05 PM or 15:05')})['formats']
        self.assertEqual({row['form'] for row in formats['date']}, {'2026-01-31', '31/01/2026', 'Jan 31, 2026'})
        self.assertEqual({row['form'] for row in formats['time']}, {'3:05 PM', '15:05'})

    def test_two_libraries_for_one_job_are_found_and_one_is_not_and_node_modules_is_not_read(self):
        (self.root / 'package.json').write_text(json.dumps({'dependencies': {'dayjs': '1', 'moment': '2', 'lucide-react': '1'}}))
        (self.root / 'node_modules/x').mkdir(parents=True)
        (self.root / 'node_modules/x/package.json').write_text(json.dumps({'dependencies': {'react-icons': '1'}}))
        self.assertEqual(design.libraries(self.root), {'dates': ['dayjs', 'moment']})

    def test_nothing_saved_writes_nothing_and_the_report_says_the_app_did_not_run(self):
        self.assertIsNone(design.write(self.root, self.root, self.root))
        self.assertIn('did not run', section_design({}))

    def test_the_section_shows_each_part_and_its_looks(self):
        html = section_design({'design': self.drawn({'a': page(BLUE, ROUND, text='2026-01-31')})})
        self.assertIn('data-design-role="button"', html)
        self.assertIn('data-design-kind="radius"', html)


if __name__ == '__main__':
    unittest.main()
