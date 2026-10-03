"""/eaos alone (eaos/menu.py): only the options that make sense now, the recommended one first, at most four to a page."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos import menu as m
from test_mcp import git_project

CHECKED = {'project': '/p', 'branch': 'main', 'checked': True, 'progress': {'closed': 3, 'total': 10, 'percent': 30.0},
           'next': {'tool': 'fix_start'}, 'waiting_branch': None, 'handover': {'open_work': None, 'running_job': None}}


def offer(answer, lang='ar'):
    with mock.patch.object(m, '_status', return_value=answer), mock.patch('eaos.guided.looks_like_project', return_value=True):
        return m.menu(tempfile.gettempdir(), lang)


def ids(result):
    return [o['id'] for page in result['pages'] for o in page if o['id'] != m.MORE]


class Pages(unittest.TestCase):
    def test_never_more_than_four_and_every_option_once(self):
        for count in range(1, 12):
            options = [f'o{n}' for n in range(count)]
            pages = m.pages(options)
            self.assertTrue(all(len(page) <= m.PAGE for page in pages))
            self.assertEqual([o for page in pages for o in page if o != m.MORE], options)
            self.assertTrue(all(page[-1] == m.MORE for page in pages[:-1]), 'every page but the last ends with "more"')
            self.assertNotIn(m.MORE, pages[-1])


class WhatIsOffered(unittest.TestCase):
    def test_a_project_never_checked_is_offered_the_check_first_on_one_page(self):
        result = offer({**CHECKED, 'checked': False, 'progress': None, 'next': {'tool': 'audit'}})
        self.assertEqual(ids(result), ['audit', 'status', 'build', 'tools'])
        self.assertEqual(len(result['pages']), 1)
        self.assertNotIn('report', ids(result), 'no report before a check')

    def test_a_checked_project_is_offered_the_next_batch_and_its_numbers(self):
        result = offer(CHECKED)
        first = result['pages'][0][0]
        self.assertEqual(first['id'], 'fix')
        self.assertIn('7', first['description'], 'the problems left, from the project itself')
        self.assertIn('3 من 10', result['state'])
        self.assertTrue({'report', 'tasks', 'ask', 'audit'} <= set(ids(result)))
        self.assertNotIn('continue', ids(result), 'no "continue" without open work')
        self.assertNotIn('decide', ids(result), 'no "review" without a branch waiting')

    def test_a_branch_waiting_comes_first_with_its_name(self):
        result = offer({**CHECKED, 'waiting_branch': 'eaos/wave-2'})
        first = result['pages'][0][0]
        self.assertEqual(first['id'], 'decide')
        self.assertIn('eaos/wave-2', first['description'])
        self.assertNotIn('fix', ids(result), 'no new batch while one waits for the person')

    def test_open_work_comes_first_with_what_is_left(self):
        work = {'kind': 'fix batch', 'number': 4, 'cards': ['A', 'B', 'C'], 'kept': ['A'], 'left': ['B', 'C']}
        result = offer({**CHECKED, 'handover': {'open_work': work, 'running_job': None}})
        first = result['pages'][0][0]
        self.assertEqual(first['id'], 'continue')
        self.assertIn('4', first['description'])
        self.assertIn('باقي 2', first['description'])

    def test_a_changed_project_is_offered_the_check_again(self):
        result = offer({**CHECKED, 'next': {'tool': 'audit'}})
        self.assertEqual(ids(result)[0], 'audit')
        self.assertNotIn('fix', ids(result))

    def test_several_branches_ask_which_one_first(self):
        result = offer({'project': '/p', 'branch': None, 'status': 'needs_branch', 'handover': {}})
        self.assertEqual(ids(result), ['branch', 'status', 'tools'])

    def test_a_project_being_built_continues_its_milestone(self):
        result = offer({'project': '/p', 'mode': 'build from a plan', 'next': {'tool': 'build_edit, then build_finish'},
                        'handover': {'open_work': {'kind': 'build milestone', 'milestone': 'M2', 'kept': [], 'left': ['C1']}}})
        self.assertEqual(ids(result)[0], 'continue')
        self.assertIn('M2', result['pages'][0][0]['description'])
        between = offer({'project': '/p', 'mode': 'build from a plan', 'next': {'tool': 'build_start'}, 'handover': {}})
        self.assertEqual(ids(between), ['continue', 'status', 'tools'], 'its plan is read already: never "build from a plan" again')
        built = offer({'project': '/p', 'mode': 'build from a plan', 'next': {'tool': 'accept'}, 'handover': {}})
        self.assertEqual(ids(built)[0], 'decide')


class Words(unittest.TestCase):
    def test_only_the_first_is_recommended_in_the_persons_language(self):
        work = {'kind': 'fix batch', 'number': 1, 'cards': ['A'], 'kept': [], 'left': ['A']}
        for answer in (CHECKED, {**CHECKED, 'waiting_branch': 'eaos/wave-1'}, {**CHECKED, 'checked': False, 'progress': None},
                       {**CHECKED, 'handover': {'open_work': work}}, {'status': 'needs_branch', 'handover': {}}, None):
            for lang, mark in (('ar', '(موصى به)'), ('en', '(Recommended)')):
                result = offer(answer, lang)
                labels = [o['label'] for page in result['pages'] for o in page]
                self.assertTrue(labels[0].endswith(mark), (answer, labels))
                self.assertEqual(sum(mark in label for label in labels), 1)
        self.assertEqual(offer(CHECKED, 'en')['question'], 'What would you like to do?')

    def test_every_option_says_what_to_do_once_chosen(self):
        for key in m.OPTIONS:
            self.assertIn(key, m.DESCRIBE)
            self.assertTrue(m.OPTIONS[key][0] and m.OPTIONS[key][1] and m.OPTIONS[key][2])

    def test_every_tool_an_option_names_is_an_mcp_tool(self):
        import asyncio
        import re
        from eaos.mcp_server import build
        registered = {tool.name for tool in asyncio.run(build().list_tools())}
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
