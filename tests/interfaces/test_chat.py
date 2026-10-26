"""The person's assistant beside the Studio reads, and does what the person asks; only what cannot be undone waits."""
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from eaos.interfaces.studio_actions import chat

ROOT = Path(__file__).resolve().parents[2]


class ChatTests(unittest.TestCase):
    def test_it_reaches_only_reading_tools_and_proposes_only_what_the_studio_can_run(self):
        # The owner, 2026-10-14: an assistant that helps inside the work, governed: it may read and diagnose, and every
        # change waits for the person
        source = ''.join((ROOT / f'eaos/interfaces/mcp_server/{name}.py').read_text(encoding='utf-8') for name in ('server', 'fix', 'build'))
        reading = {name for kind, name in re.findall(r"@server\.tool\(annotations=(\w+)[\s\S]*?def (\w+)\(", source) if kind == 'reading'}
        self.assertLessEqual(set(chat.READ_TOOLS), reading, 'a tool that works is out of the conversation\'s reach')
        actions = SimpleNamespace(contract={'actions': [{'id': 'audit'}, {'id': 'run_try'}]},
                                  store=mock.Mock(load=lambda run: {'id': run} if run == 'r1' else (_ for _ in ()).throw(KeyError(run))))
        found = chat._allowed(actions, [{'kind': 'action', 'action': 'run_try', 'inputs': {'mode': 'baseline'}, 'why': 'speed'},
                                        {'kind': 'action', 'action': 'rm -rf', 'inputs': {}, 'why': 'no'},
                                        {'kind': 'control', 'action': 'retry', 'run': 'r1', 'why': 'again'},
                                        {'kind': 'control', 'action': 'retry', 'run': 'r9', 'why': 'unknown run'},
                                        {'kind': 'control', 'action': 'accept', 'run': 'r1', 'why': 'only the person'}])
        self.assertEqual([(p['kind'], p['action']) for p in found], [('action', 'run_try'), ('control', 'retry')])
        # the owner, 2026-10-21: it could not start a new check for them; direct control is on unless turned off and
        # runs every action and control, only merging or throwing a branch away waits for the person's press
        self.assertEqual([chat._direct(p) for p in found], [True, True])
        self.assertTrue(chat._direct({'kind': 'action', 'action': 'fix_start'}))
        self.assertFalse(chat._direct({'kind': 'action', 'action': 'accept'}) or chat._direct({'kind': 'action', 'action': 'undo'}))
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            store = SimpleNamespace(store=SimpleNamespace(folder=Path(folder)))
            self.assertTrue(chat.control(store)['on'], 'on before anyone turned it on')
            self.assertFalse(chat.control(store, {'on': False})['on'])
            self.assertFalse(chat.control(store)['on'], 'off stays off')
            self.assertTrue(chat.control(store, {'on': True})['on'])

    def test_an_answer_to_a_step_s_question_acts_and_the_same_question_never_comes_back(self):
        # the owner, 2026-10-21: "your assistant is not answering" came back after every answer, picked or written
        from eaos.journeys import agent_tools
        from eaos.ai.assistant import prompts
        from eaos.interfaces.studio_actions.runs import Manager
        question = prompts.assistant_question({'assistant': {'name': 'Claude Code'}})
        direct = {'mode': 'direct'}
        self.assertEqual(prompts.picked(direct, question, None, 'رجع الاتصال، كمّل'), 'retry', 'words act: the recommended option')
        self.assertEqual(prompts.picked(direct, question, None, 'start this check without AI'), 'without_ai')
        self.assertIsNone(prompts.picked(direct, {'why': 'run consent', 'recommendation': 'yes'}, None, 'explain first'),
                          'running the app takes an explicit yes')
        self.assertIsNone(agent_tools._assistant_not_ready({}, fixed=True), 'fixed: the check starts, never asked again')
        manager = mock.Mock(store=mock.Mock(load=lambda run: {}))
        with mock.patch('threading.Thread'):
            Manager._direct_answer(manager, 'r1', {'inputs': {'fresh': True}}, question, 'retry')
        manager.store.update.assert_called_once_with('r1', inputs={'fresh': True, 'fixed': True})
