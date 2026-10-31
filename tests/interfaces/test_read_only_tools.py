"""What MCP calls read-only changes nothing, and what changes something is not called read-only: reading a build's file leaves
the project's state alone, and opening the report, which rebuilds it, is handled as work by the assistants and the Studio."""
import asyncio
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.core.project import state as project_state
from eaos.interfaces.mcp_server.govern import every
from eaos.interfaces.mcp_server.server import build, reading as read_only
from eaos.interfaces.studio_actions import chat
from eaos.journeys import agent_tools, guided, handover
from eaos.pipeline.runners import by_rules
from eaos.pipeline.stages import SkipStage


def _no_engines(context):
    raise SkipStage('this test runs no external tool', code='engines_not_requested')


def _tool(server, name):
    return next(tool for tool in asyncio.run(server.list_tools()) if tool.name == name)


def _called(server, name, **arguments):
    return json.loads(asyncio.run(server.call_tool(name, arguments)).content[0].text)


def _files(root):
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob('*') if path.is_file() and '.git' not in path.parts}


class Home(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        home = self.root / 'home'
        patcher = mock.patch.dict(os.environ, {'EAOS_HOME': str(home), 'EAOS_OUTPUT': str(self.root / 'out'), 'EAOS_ASSISTANT': 'none'})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.home = home
        self.project = self.root / 'shop'
        self.project.mkdir()
        (self.project / 'app.py').write_text('print(1)\n', encoding='utf-8')
        for argv in (('init', '-q', '-b', 'main'), ('add', '-A'), ('commit', '-qm', 'first')):
            subprocess.run(['git', '-C', str(self.project), '-c', 'user.name=t', '-c', 'user.email=t@t', *argv], check=True, capture_output=True)
        self.server = build(every)


class ReadingABuildsFile(Home):
    def test_a_project_never_started_is_answered_and_nothing_is_made(self):
        before = _files(self.project)
        answer = _called(self.server, 'build_read', path='app.py', project=str(self.project))
        self.assertIn('no milestone is open', answer['error'])
        self.assertIsNone(project_state.load(self.project), 'no state is made by reading')
        self.assertEqual(_files(self.project), before)

    def test_a_folder_not_there_is_not_made(self):
        missing = self.root / 'not-there'
        self.assertIn('error', _called(self.server, 'build_read', path='app.py', project=str(missing)))
        self.assertFalse(missing.exists())

    def test_a_checked_project_keeps_its_state_byte_for_byte_and_never_turns_into_a_build(self):
        state = agent_tools.state_of(str(self.project))
        project_state.write(state)
        record = Path(state['workspace']) / 'state.json'
        before = record.read_bytes()
        self.assertIn('no milestone is open', _called(self.server, 'build_read', path='app.py', project=str(self.project))['error'])
        self.assertEqual(record.read_bytes(), before)
        self.assertNotIn('mode', json.loads(before))

    def test_a_file_of_the_open_build_is_still_read(self):
        copy = self.root / 'copy'
        copy.mkdir()
        (copy / 'made.py').write_text('x = 1\n', encoding='utf-8')
        state = agent_tools.state_of(str(self.project))
        project_state.write({**state, 'mode': 'build', 'open_build': {'root': str(copy)}})
        record = Path(state['workspace']) / 'state.json'
        before = record.read_bytes()
        answer = _called(self.server, 'build_read', path='made.py', project=str(self.project))
        self.assertEqual((answer['lines'], record.read_bytes()), (1, before))
        self.assertIn('x = 1', answer['text'])


class OpeningTheReport(Home):
    def test_mcp_does_not_call_it_read_only_and_says_it_destroys_nothing(self):
        hints = _tool(self.server, 'open_report').annotations
        self.assertFalse(hints.read_only_hint)
        self.assertFalse(hints.destructive_hint)

    def test_it_rewrites_the_page_and_saves_the_state_which_is_why_it_is_not_reading(self):
        with mock.patch.dict(by_rules.RUNNERS, engines=_no_engines, architecture=_no_engines), mock.patch.object(guided, 'tools_for_check', return_value={}):
            state = agent_tools.state_of(str(self.project))
            agent_tools.choose_branch('main', str(self.project), 'the work goes on here')
            agent_tools._audit_job(str(self.project), {}, None)
        record = Path(state['workspace']) / 'state.json'
        saved = json.loads(record.read_text(encoding='utf-8'))
        record.write_text(json.dumps({**saved, 'updated': 'an older stamp'}), encoding='utf-8')
        pages = [path for path in guided.outputs(state).rglob('REPORT.html')]
        for path in pages: path.unlink()
        answer = _called(self.server, 'open_report', show=False, project=str(self.project))
        self.assertTrue(Path(answer['report_for_people']).is_file(), 'the page is made again')
        self.assertFalse(answer['opened_in_browser'], 'and opened only when asked')
        self.assertNotEqual(json.loads(record.read_text(encoding='utf-8'))['updated'], 'an older stamp', 'the state is saved')

    def test_the_tools_the_server_calls_reading_leave_it_out_and_keep_build_read(self):
        reading = read_only()
        self.assertNotIn('open_report', reading)
        self.assertIn('build_read', reading)
        self.assertIn('status', reading)

    def test_the_conversation_inside_the_studio_cannot_reach_it(self):
        self.assertNotIn('open_report', chat.READ_TOOLS)

    def test_a_call_of_it_counts_as_a_step_in_the_handover(self):
        self.assertNotIn('open_report', handover.READING)


if __name__ == '__main__':
    unittest.main()
