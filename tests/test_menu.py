"""/eaos alone (eaos/interfaces/menu.py): only the options that make sense now, the recommended one first, at most four to a page."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.interfaces import menu as m
from test_mcp import git_project

CHECKED = {'project': '/p', 'branch': 'main', 'checked': True, 'progress': {'closed': 3, 'total': 10, 'percent': 30.0},
           'next': {'tool': 'fix_start'}, 'waiting_branch': None, 'handover': {'open_work': None, 'running_job': None}}


def offer(answer, lang='ar'):
    with mock.patch.object(m, '_status', return_value=answer), mock.patch('eaos.journeys.guided.looks_like_project', return_value=True):
        return m.menu(tempfile.gettempdir(), lang)


def ids(result):
    return [o['id'] for page in result['pages'] for o in page if o['id'] != m.MORE]


class WhatIsOffered(unittest.TestCase):
    def test_only_what_makes_sense_now_is_offered_the_most_pressing_first_also_while_building(self):
        work = {'kind': 'fix batch', 'number': 4, 'cards': ['A', 'B', 'C'], 'kept': ['A'], 'left': ['B', 'C']}
        never = offer({**CHECKED, 'checked': False, 'progress': None, 'next': {'tool': 'audit'}})
        self.assertEqual((ids(never), len(never['pages'])), (['audit', 'status', 'build', 'tools'], 1), 'no report before a check')
        checked = offer(CHECKED)
        first = checked['pages'][0][0]
        self.assertEqual(first['id'], 'fix')
        self.assertIn('7', first['description'], 'the problems left, from the project itself')
        self.assertIn('3 من 10', checked['state'])
        self.assertTrue({'report', 'tasks', 'ask', 'audit'} <= set(ids(checked)))
        self.assertFalse({'continue', 'decide'} & set(ids(checked)), 'no "continue" without open work, no "review" without a branch waiting')
        waiting = offer({**CHECKED, 'waiting_branch': 'eaos/wave-2'})
        self.assertEqual(ids(waiting)[0], 'decide')
        self.assertIn('eaos/wave-2', waiting['pages'][0][0]['description'])
        self.assertNotIn('fix', ids(waiting), 'no new batch while one waits for the person')
        open_work = offer({**CHECKED, 'handover': {'open_work': work, 'running_job': None}})
        self.assertEqual(ids(open_work)[0], 'continue')
        self.assertIn('4', open_work['pages'][0][0]['description'])
        self.assertIn('باقي 2', open_work['pages'][0][0]['description'])
        changed = offer({**CHECKED, 'next': {'tool': 'audit'}})
        self.assertEqual(ids(changed)[0], 'audit')
        self.assertNotIn('fix', ids(changed))
        self.assertEqual(ids(offer({'project': '/p', 'branch': None, 'status': 'needs_branch', 'handover': {}})), ['branch', 'status', 'tools'])
        result = offer({'project': '/p', 'mode': 'build from a plan', 'next': {'tool': 'build_edit, then build_finish'},
                        'handover': {'open_work': {'kind': 'build milestone', 'milestone': 'M2', 'kept': [], 'left': ['C1']}}})
        self.assertEqual(ids(result)[0], 'continue')
        self.assertIn('M2', result['pages'][0][0]['description'])
        between = offer({'project': '/p', 'mode': 'build from a plan', 'next': {'tool': 'build_start'}, 'handover': {}})
        self.assertEqual(ids(between), ['continue', 'status', 'tools'], 'its plan is read already: never "build from a plan" again')
        built = offer({'project': '/p', 'mode': 'build from a plan', 'next': {'tool': 'accept'}, 'handover': {}})
        self.assertEqual(ids(built)[0], 'decide')

class Words(unittest.TestCase):
    def test_at_most_four_to_a_page_each_option_once_and_only_the_first_recommended_in_the_persons_language(self):
        for count in range(1, 12):
            options = [f'o{n}' for n in range(count)]
            pages = m.pages(options)
            self.assertTrue(all(len(page) <= m.PAGE for page in pages))
            self.assertEqual([o for page in pages for o in page if o != m.MORE], options)
            self.assertTrue(all(page[-1] == m.MORE for page in pages[:-1]), 'every page but the last ends with "more"')
            self.assertNotIn(m.MORE, pages[-1])
        work = {'kind': 'fix batch', 'number': 1, 'cards': ['A'], 'kept': [], 'left': ['A']}
        for answer in (CHECKED, {**CHECKED, 'waiting_branch': 'eaos/wave-1'}, {**CHECKED, 'checked': False, 'progress': None},
                       {**CHECKED, 'handover': {'open_work': work}}, {'status': 'needs_branch', 'handover': {}}, None):
            for lang, mark in (('ar', '(موصى به)'), ('en', '(Recommended)')):
                result = offer(answer, lang)
                labels = [o['label'] for page in result['pages'] for o in page]
                self.assertTrue(labels[0].endswith(mark), (answer, labels))
                self.assertEqual(sum(mark in label for label in labels), 1)
        self.assertEqual(offer(CHECKED, 'en')['question'], 'What would you like to do?')

    def test_every_option_says_what_to_do_once_chosen_through_real_mcp_tools(self):
        import asyncio
        import re
        from eaos.interfaces.mcp_server import build
        registered = {tool.name for tool in asyncio.run(build().list_tools())}
        for key in m.OPTIONS:
            self.assertIn(key, m.DESCRIBE)
            self.assertTrue(m.OPTIONS[key][0] and m.OPTIONS[key][1] and m.OPTIONS[key][2])
        for key, (_, _, do) in m.OPTIONS.items():
            for name in re.findall(r'\b([a-z]+_[a-z_]+|status|audit|wait|finding|structure|plan|accept|undo|impact|ask)\b', do):
                if name in ('person_agreed', 'person_said', 'how_to_continue', 'report_errors', 'needed_here'): continue
                self.assertIn(name, registered, f'{key}: {name}')


class OnDisk(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(self.tmp.name) / 'home')})
        patcher.start(); self.addCleanup(patcher.stop)

    def test_a_real_project_and_a_folder_that_is_none(self):
        project = git_project(Path(self.tmp.name) / 'shop')
        result = m.menu(str(project), 'en')
        self.assertEqual(ids(result)[0], 'audit')
        self.assertIn('not checked yet', result['state'])
        empty = Path(self.tmp.name) / 'empty'
        empty.mkdir()
        self.assertEqual(ids(m.menu(str(empty), 'ar')), ['build', 'tools'])
        self.assertFalse((Path(self.tmp.name) / 'home').exists() and any((Path(self.tmp.name) / 'home').rglob('empty*')),
                         'a folder that is no project is left without any EAOS state')


if __name__ == '__main__':
    unittest.main()
