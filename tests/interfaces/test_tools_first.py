"""The tools in the order they are needed: the check waits for the tools it needs on the project
(eaos/kernel/toolchain/runs.py), a tool that failed stops it unless the person starts without it, and the report
records that it did."""
import os
import subprocess
import tempfile
import sys
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

from eaos.features.guided.interface import agent_tools
from eaos.features.guided import journey as guided
from eaos.kernel.project import jobs
from eaos.kernel import toolchain
from eaos.features.report.interface.documents import run as run_report

READY = {'needed': ['semgrep'], 'pending': [], 'failed': {}, 'ready': True}
FAILED = {'needed': ['semgrep'], 'pending': [], 'failed': {'semgrep': 'no network'}, 'ready': False}


class Project(unittest.TestCase):
    """A git project with its guided state and its report folder."""

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
        for argv in (['init', '-q'], ['add', '-A'],
                     ['-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'first']):
            subprocess.run(['git', '-C', str(self.project), *argv], check=True, capture_output=True)
        self.state = agent_tools.state_of(str(self.project))
        self.report = guided.report_of(self.state).parent
        self.report.mkdir(parents=True, exist_ok=True)

class Entry(Project):
    def test_a_failed_tool_stops_the_check_unless_chosen(self):
        with mock.patch.object(toolchain, 'ready', return_value=False), \
                mock.patch.object(jobs, 'start', return_value='audit-1') as start, \
                mock.patch.object(jobs, 'wait', return_value={'status': 'running', 'progress': {}, 'started': 'now'}):
            agent_tools.audit(str(self.project), fresh=True, without_tools=True)
        self.assertEqual(start.call_args.args[2], {'without_tools': True})
        # The check job waits, and a failed tool stops it unless the person starts without it.
        with mock.patch.object(toolchain, 'wait_for_check', return_value=FAILED) as waited, \
                mock.patch('eaos.features.guided.journey.check.check', side_effect=RuntimeError('the check ran')) as check:
            with self.assertRaises(guided.ToolsMissing) as stopped:
                agent_tools._audit_job(str(self.project), {}, None)
            self.assertIn('semgrep: no network', str(stopped.exception))
            self.assertEqual(guided.explain(stopped.exception)['id'], 'tools_missing')
            check.assert_not_called()
            with self.assertRaises(RuntimeError):
                agent_tools._audit_job(str(self.project), {'without_tools': True}, None)
        self.assertEqual(check.call_args.kwargs['without_tools'], ['semgrep'])
        self.assertEqual([c.args[2] for c in waited.call_args_list], [True, False],
                         'once chosen, it is not tried again first')


class Terminal(unittest.TestCase):
    def setUp(self):
        self.state = {'lang': 'en', 'project': '/p', 'workspace': '/w', 'questions': []}

    def scan(self, gate, yes):
        args = Namespace(yes=yes)
        checking = guided.checking         # the check's step (eaos/features/guided/journey/checking.py)
        with mock.patch.object(toolchain, 'wait_for_check', return_value=gate), mock.patch.object(checking, 'save'), \
                mock.patch.object(checking, 'say'), mock.patch.object(checking, 'box') as box, \
                mock.patch.object(sys.stdin, 'isatty', return_value=False), \
                mock.patch.object(checking, 'agree_to_assistant', side_effect=RuntimeError('the check goes on')):
            try: return guided.scan(self.state, args), box
            except RuntimeError: return 'started', box

    def test_eaos_start_installs_the_tools_first_and_asks_each_time_before_checking_without_one(self):
        with self.assertRaises(guided.NeedsAnswer):
            self.scan(FAILED, yes=False)
        self.assertEqual(self.scan(FAILED, yes=True)[0], 'started')
        self.assertEqual(self.scan(FAILED, yes=True)[0], 'started', 'asked again each time')
        self.assertEqual(self.scan(READY, yes=False)[0], 'started')
        # A no stops it and says how to go on.
        with mock.patch.object(guided.checking, 'ask', side_effect=guided.Declined('start_without_tools')):
            code, box = self.scan(FAILED, yes=False)
        self.assertEqual(code, 1)
        self.assertEqual(box.call_args.kwargs['commands'], ['eaos tools install', 'eaos start .'])
        # eaos start starts installing the tools first.
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(toolchain, 'prepare') as prepare:
            guided.watch({**self.state, 'project': tmp}, Namespace(no_watch=False))
        prepare.assert_called_once_with(tmp)


class Record(unittest.TestCase):
    def test_the_report_records_the_tools_the_check_ran_without(self):
        manifest = {'seconds': 1.0, 'status': 'COMPLETE', 'stages': {},
                    'options': {'without_tools': ['semgrep', 'trivy']}}
        text = run_report.document(manifest, 'en').render()
        self.assertIn('The check started without these tools, whose install failed: semgrep, trivy', text)
        self.assertNotIn('without these tools', run_report.document({**manifest, 'options': {}}, 'en').render())


if __name__ == '__main__':
    unittest.main()
