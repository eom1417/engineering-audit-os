"""The interface first, the tools in the order they are needed: the Studio opens on "Preparing the tools", the check
waits for the tools it needs on the project (eaos/core/toolchain.py readiness), a tool that failed stops it unless the
person starts without it, and the report records that it did."""
import os
import subprocess
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

from eaos.journeys import agent_tools, guided
from eaos.core import jobs, progress, toolchain
from eaos.core import launch
from eaos.interfaces.api import server
from eaos.report import run as run_report
from starlette.testclient import TestClient

PORT = 8765

READY = {'needed': ['semgrep'], 'pending': [], 'failed': {}, 'ready': True}
FAILED = {'needed': ['semgrep'], 'pending': [], 'failed': {'semgrep': 'no network'}, 'ready': False}


class Project(unittest.TestCase):
    """A git project with its guided state and a Studio server over its report folder."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(self.tmp.name) / 'home'),
                                           'EAOS_ENGINE_TOOLS': str(Path(self.tmp.name) / 'tools')})
        env.start()
        self.addCleanup(env.stop)
        self.project = Path(self.tmp.name) / 'shop'
        (self.project / 'src').mkdir(parents=True)
        (self.project / 'package.json').write_text('{"name": "shop", "scripts": {"dev": "vite"}}\n')
        (self.project / 'src/a.js').write_text('export const a = 1;\n')
        for argv in (['init', '-q'], ['add', '-A'], ['-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'first']):
            subprocess.run(['git', '-C', str(self.project), *argv], check=True, capture_output=True)
        self.state = agent_tools.state_of(str(self.project))
        self.report = guided.report_of(self.state).parent
        self.report.mkdir(parents=True, exist_ok=True)

    def client(self):
        keys = server.Keys(port=PORT)
        app = server.create_app(self.report, project=self.project, keys=keys, mounts=[], watch=False)
        return TestClient(app, base_url=f'http://127.0.0.1:{PORT}'), keys, app


class Entry(Project):
    def test_the_progress_route_carries_the_install_and_what_the_check_needs_here(self):
        log = progress.ProgressLog(toolchain.home(), 'tools', pulse=False, sampler=None)
        log.started(toolchain.stages(toolchain.registry()['tools']), ['semgrep'], {})
        http, keys, app = self.client()
        log.emit('stage.started', stage='semgrep')
        body = http.get('/api/progress', headers={'X-EAOS-Token': keys.token}).json()
        self.assertEqual((body['flows']['tools']['state'], body['flows']['tools']['stages'][0]['name']), ('running', 'codegraph'))
        self.assertIn('semgrep', body['tools_needed'])
        self.assertNotIn('sqlfluff', body['tools_needed'], 'no SQL in this project')
        events = app.state.ctx.feed.poll()
        self.assertEqual([(e['data']['flow'], e['data']['event']) for e in events], [('tools', 'stage.started')], 'the feed follows the install')
        log.finish('STOPPED')

    def test_the_assistant_opens_preparing_the_tools_and_a_failed_tool_stops_the_check_unless_chosen(self):
        opened = {'studio': 'http://127.0.0.1:9/#/tools', 'opened_in_browser': True}
        with mock.patch.object(toolchain, 'ready', return_value=False), \
                mock.patch.object(agent_tools, 'open_studio', return_value=opened) as open_studio, \
                mock.patch.object(jobs, 'start', return_value='audit-1') as start, \
                mock.patch.object(jobs, 'wait', return_value={'status': 'running', 'progress': {}, 'started': 'now'}):
            answer = agent_tools.audit(str(self.project), fresh=True, without_tools=True)
        self.assertEqual(open_studio.call_args.kwargs['route'], '/tools')
        self.assertEqual((answer['watch'], answer['what_now']), (opened['studio'], agent_tools.TOOLS_FIRST))
        self.assertEqual(start.call_args.args[2], {'without_tools': True})
        # The check job waits, and a failed tool stops it unless the person starts without it.
        with mock.patch.object(toolchain, 'wait_for_check', return_value=FAILED) as waited, \
                mock.patch('eaos.journeys.check.check', side_effect=RuntimeError('the check ran')) as check:
            with self.assertRaises(guided.ToolsMissing) as stopped:
                agent_tools._audit_job(str(self.project), {}, None)
            self.assertIn('semgrep: no network', str(stopped.exception))
            self.assertEqual(guided.explain(stopped.exception)['id'], 'tools_missing')
            check.assert_not_called()
            with self.assertRaises(RuntimeError):
                agent_tools._audit_job(str(self.project), {'without_tools': True}, None)
        self.assertEqual(check.call_args.kwargs['without_tools'], ['semgrep'])
        self.assertEqual([c.args[2] for c in waited.call_args_list], [True, False], 'once chosen, it is not tried again first')


class Terminal(unittest.TestCase):
    def setUp(self):
        self.state = {'lang': 'en', 'project': '/p', 'workspace': '/w', 'questions': []}

    def scan(self, gate, yes):
        args = Namespace(yes=yes)
        with mock.patch.object(toolchain, 'wait_for_check', return_value=gate), mock.patch.object(guided, 'save'), \
                mock.patch.object(guided, 'source', return_value=Path('/p')), mock.patch.object(guided, 'tip', return_value=None), \
                mock.patch.object(guided.branches, 'scan_provenance', return_value={}), mock.patch.object(guided, 'say'), \
                mock.patch.object(guided, 'box') as box, mock.patch.object(guided.sys.stdin, 'isatty', return_value=False), \
                mock.patch.object(guided, 'agree_to_assistant', side_effect=RuntimeError('the check goes on')):
            try: return guided.scan(self.state, args), box
            except RuntimeError: return 'started', box

    def test_eaos_start_opens_the_tools_first_and_asks_each_time_before_checking_without_one(self):
        with self.assertRaises(guided.NeedsAnswer):
            self.scan(FAILED, yes=False)
        self.assertEqual(self.scan(FAILED, yes=True)[0], 'started')
        self.assertEqual(self.scan(FAILED, yes=True)[0], 'started', 'asked again each time')
        self.assertEqual(self.scan(READY, yes=False)[0], 'started')
        # A no stops it and says how to go on.
        with mock.patch.object(guided, 'ask', side_effect=guided.Declined('start_without_tools')):
            code, box = self.scan(FAILED, yes=False)
        self.assertEqual(code, 1)
        self.assertEqual(box.call_args.kwargs['commands'], ['eaos tools install', 'eaos start .'])
        # eaos start opens "Preparing the tools" first.
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(toolchain, 'prepare') as prepare, \
                mock.patch.object(toolchain, 'ready', return_value=False), \
                mock.patch.object(launch, 'start', return_value=({'port': 9, 'token': 'k'}, True)), \
                mock.patch.object(launch, '_open') as opened, mock.patch.object(guided, 'say') as said:
            guided.watch({**self.state, 'project': tmp}, Namespace(no_watch=False))
        prepare.assert_called_once_with(tmp)
        opened.assert_called_once_with('http://127.0.0.1:9/#/tools?token=k', True)
        said.assert_called_once_with('Watch the work live: http://127.0.0.1:9/#/tools?token=k')


class Record(unittest.TestCase):
    def test_the_report_records_the_tools_the_check_ran_without(self):
        manifest = {'seconds': 1.0, 'status': 'COMPLETE', 'stages': {}, 'options': {'without_tools': ['semgrep', 'trivy']}}
        text = run_report.document(manifest, 'en').render()
        self.assertIn('The check started without these tools, whose install failed: semgrep, trivy', text)
        self.assertNotIn('without these tools', run_report.document({**manifest, 'options': {}}, 'en').render())


if __name__ == '__main__':
    unittest.main()
