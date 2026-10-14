"""The person's assistant beside the Studio reads and proposes; it never changes anything itself."""
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from eaos.studio.actions import chat

ROOT = Path(__file__).resolve().parents[1]


class ChatTests(unittest.TestCase):
    def test_it_reaches_only_reading_tools_and_proposes_only_what_the_studio_can_run(self):
        # The owner, 2026-10-14: an assistant that helps inside the work, governed: it may read and diagnose, and every
        # change waits for the person
        source = (ROOT / 'eaos/mcp_server.py').read_text(encoding='utf-8')
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
        # direct control runs by itself only a few actions and the runs' controls; never the person's own steps
        self.assertTrue(set(chat.DIRECT).isdisjoint({'accept', 'undo', 'choose_branch', 'fix_edit', 'build_edit'}))
        self.assertEqual([chat._direct(p) for p in found], [True, True])
        self.assertFalse(chat._direct({'kind': 'action', 'action': 'accept'}))
