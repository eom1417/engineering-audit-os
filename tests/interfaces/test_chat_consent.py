"""The person's decisions stay the person's under the Studio chat's direct control (2026-10-29): a chat proposal of
rule op=approve with person_agreed=true ran an assistant's test command on the person's computer, the Studio taking the
preview's confirm token for it. Now a decision waits for the person's own press, after a preview that shows it."""
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock

from tests.shared_fixture import Workspace

from eaos.core.project.runs import TERMINAL
from eaos.interfaces.studio_actions import Actions, chat
from eaos.interfaces.studio_actions.lane_assistants import Refused


def proposal(action, **inputs):
    return {'kind': 'action', 'action': action, 'inputs': inputs, 'run': None, 'why': 'the assistant says so'}


class ChatConsent(Workspace):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(self.tmp) / 'home')})
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop('EAOS_STUDIO_RUN', None)
        self.project = Path(self.tmp) / 'app'
        self.project.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.project)], check=True)
        subprocess.run(['git', '-C', str(self.project), '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-q', '--allow-empty', '-m', 'i'], check=True)
        self.marker = Path(self.tmp) / 'marker'
        from eaos.interfaces.mcp_server import rules as tools
        tools.rule('add', words='Totals keep two decimals', project=str(self.project))
        command = [sys.executable, '-c', f"open({str(self.marker)!r}, 'w').write('x')"]
        tools.rule('guard', id='R1', guard={'kind': 'test', 'command': command}, project=str(self.project))
        self.actions = Actions(self.project, port=8765, adapters={})
        self.addCleanup(self.actions.close)

    def ran(self, seconds=15):
        end = time.monotonic() + seconds
        while time.monotonic() < end and not self.marker.exists(): time.sleep(0.2)
        return self.marker.exists()

    def test_direct_control_never_runs_the_persons_approval_even_with_person_agreed_from_the_assistant(self):
        self.assertTrue(chat.control(self.actions)['on'])
        asked = chat._allowed(self.actions, [proposal('rule', op='approve', id='R1', person_agreed=True)])
        self.assertEqual(chat._done_at_once(self.actions, asked), [], 'it stays a proposal for the person to press')
        self.assertFalse(self.ran(3))
        with self.assertRaises(Refused):      # nor can it be sent without the token of a preview the person saw
            self.actions.create({'action': 'rule', 'inputs': {'op': 'approve', 'id': 'R1', 'person_agreed': True}})
        self.assertFalse(self.ran(2))

    def test_every_decision_of_the_person_waits_and_what_is_no_decision_runs_at_once(self):
        decisions = [proposal('rule', op=op, id='R1', person_agreed=True) for op in ('approve', 'pin', 'unpin', 'change', 'hook')]
        decisions += [proposal('rule', op='add', words='x', pin=True), proposal('run_setup', person_agreed=True),
                      proposal('tools_add', entry={}, person_agreed=True), proposal('build_start', person_agreed=True),
                      proposal('logic_flaws', person_agreed=True), proposal('accept'), proposal('undo'),
                      proposal('choose_branch', branch='main', person_said='yes'), proposal('sign_in_forget')]
        self.assertEqual([p['action'] for p in decisions if chat._direct(p, self.actions)], [])
        safe = [proposal('rule', op='add', words='Prices come from one table'), proposal('note', text='checked'), proposal('status')]
        self.assertEqual([p['action'] for p in safe if not chat._direct(p, self.actions)], [])
        done = chat._done_at_once(self.actions, [safe[0]])
        self.assertTrue(done and done[0].get('run'), done)
        # it ran to its end, before the test's folder goes (its thread once outlived the folder: a KeyError, 2026-10-30)
        self.assertEqual(self.actions.wait(done[0]['run'], TERMINAL)['state'], 'done')

    def test_the_persons_own_press_after_a_preview_that_shows_the_command_runs_it(self):
        inputs = {'op': 'approve', 'id': 'R1', 'person_agreed': True}
        seen = self.actions.preview('rule', {'inputs': inputs})
        self.assertIn(str(self.marker), seen['shows']['guard'], 'the very command is shown before the press')
        run = self.actions.create({'action': 'rule', 'inputs': inputs, 'confirm': seen['confirm']['token']})
        self.assertEqual(self.actions.wait(run['id'], TERMINAL)['state'], 'done')
        self.assertTrue(self.ran())
