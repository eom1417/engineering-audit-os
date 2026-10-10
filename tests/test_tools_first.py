"""The interface first, the tools in the order they are needed: the Studio opens on "Preparing the tools", the check
waits for the tools it needs on the project (eaos/toolchain.py readiness), a tool that failed stops it unless the
person starts without it, and the report records that it did."""
import os
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tests'))

from eaos import agent_tools, guided, jobs, progress, toolchain  # noqa: E402
from eaos.engines import trivy  # noqa: E402
from eaos.pipeline import report as run_report  # noqa: E402
from test_progress_server import Project  # noqa: E402

READY = {'needed': ['semgrep'], 'pending': [], 'failed': {}, 'ready': True}
FAILED = {'needed': ['semgrep'], 'pending': [], 'failed': {'semgrep': 'no network'}, 'ready': False}


class Entry(Project):
    def test_the_progress_route_carries_the_install_and_what_the_check_needs_here(self):
        log = progress.ProgressLog(toolchain.home(), 'tools', pulse=False, sampler=None)
        log.started(toolchain.stages(toolchain.registry()['tools']), ['semgrep'], {})
        _, _, app = self.client()
        log.emit('stage.started', stage='semgrep')
        body = self.get('/api/progress').json()
        self.assertEqual((body['flows']['tools']['state'], body['flows']['tools']['stages'][0]['name']), ('running', 'codegraph'))
        self.assertIn('semgrep', body['tools_needed'])
        self.assertNotIn('sqlfluff', body['tools_needed'], 'no SQL in this project')
        events = app.state.ctx.feed.poll()
        self.assertEqual([(e['data']['flow'], e['data']['event']) for e in events], [('tools', 'stage.started')], 'the feed follows the install')
        log.finish('STOPPED')

    def test_the_assistant_opens_preparing_the_tools_and_the_check_starts_once_they_are_ready(self):
        opened = {'studio': 'http://127.0.0.1:9/#/tools?token=k', 'opened_in_browser': True}
        with mock.patch.object(toolchain, 'ready', return_value=False), \
                mock.patch.object(agent_tools, 'open_studio', return_value=opened) as open_studio, \
                mock.patch.object(jobs, 'start', return_value='audit-1') as start, \
                mock.patch.object(jobs, 'wait', return_value={'status': 'running', 'progress': {}, 'started': 'now'}):
            answer = agent_tools.audit(str(self.project), fresh=True, without_tools=True)
        self.assertEqual(open_studio.call_args.kwargs['route'], '/tools')
        self.assertEqual((answer['watch'], answer['what_now']), (opened['studio'], agent_tools.TOOLS_FIRST))
        self.assertEqual(start.call_args.args[2], {'without_tools': True})

    def test_the_check_job_waits_and_a_failed_tool_stops_it_unless_the_person_starts_without_it(self):
        with mock.patch.object(toolchain, 'wait_for_check', return_value=FAILED) as waited, \
                mock.patch('eaos.pipeline.check', side_effect=RuntimeError('the check ran')) as check:
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

    def test_eaos_start_asks_before_checking_without_a_tool_and_never_keeps_the_answer(self):
        with self.assertRaises(guided.NeedsAnswer):
            self.scan(FAILED, yes=False)
        self.assertEqual(self.scan(FAILED, yes=True)[0], 'started')
        self.assertEqual(self.scan(FAILED, yes=True)[0], 'started', 'asked again each time')
        self.assertEqual(self.scan(READY, yes=False)[0], 'started')

    def test_a_no_stops_it_and_says_how_to_go_on(self):
        with mock.patch.object(guided, 'ask', side_effect=guided.Declined('start_without_tools')):
            code, box = self.scan(FAILED, yes=False)
        self.assertEqual(code, 1)
        self.assertEqual(box.call_args.kwargs['commands'], ['eaos tools install', 'eaos start .'])

    def test_eaos_start_opens_preparing_the_tools_first(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(toolchain, 'prepare') as prepare, \
                mock.patch.object(agent_tools, 'open_studio', return_value={'studio': 'http://x/#/tools'}) as open_studio, \
                mock.patch.object(guided, 'say') as said:
            guided.watch({**self.state, 'project': tmp}, Namespace(no_watch=False))
        prepare.assert_called_once_with(tmp)
        self.assertEqual(open_studio.call_args.kwargs['route'], '/tools')
        said.assert_called_once_with('Watch the work live: http://x/#/tools')


class Record(unittest.TestCase):
    def test_the_report_records_the_tools_the_check_ran_without(self):
        manifest = {'seconds': 1.0, 'status': 'COMPLETE', 'stages': {}, 'options': {'without_tools': ['semgrep', 'trivy']}}
        text = run_report.document(manifest, 'en').render()
        self.assertIn('The check started without these tools, whose install failed: semgrep, trivy', text)
        self.assertNotIn('without these tools', run_report.document({**manifest, 'options': {}}, 'en').render())

    def test_trivy_reads_the_database_it_has_and_never_downloads_one_in_a_check(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {'EAOS_ENGINE_TOOLS': tmp}), \
                mock.patch.object(trivy.tool, 'declined', return_value=None), mock.patch.object(trivy, 'version', return_value='0.74.0'), \
                mock.patch.object(trivy, 'run', return_value=(1, '', 'stop', 0.1)) as run:
            trivy.analyze(tmp, tmp)
            self.assertNotIn('--skip-db-update', run.call_args.args[0], 'none yet: Trivy fetches it')
            (Path(tmp) / 'cache/trivy/db').mkdir(parents=True)
            (Path(tmp) / 'cache/trivy/db/metadata.json').write_text('{}')
            trivy.analyze(tmp, tmp)
            self.assertIn('--skip-db-update', run.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
