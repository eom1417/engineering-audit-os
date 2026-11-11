"""EAOS inside the assistant (docs/MCP.md): the outputs, the jobs, and the questions of the tools."""
import asyncio
import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest import mock
from eaos.features.guided.interface import agent_tools
from eaos.features.guided import journey as guided
from eaos.kernel.project import jobs
ROOT = Path(__file__).resolve().parents[2]
from tests.interfaces._mcp_fixture import Home, git_project, wave_branch


class JobTests(Home):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(jobs.subprocess, 'Popen', return_value=mock.Mock(pid=os.getpid()))
        patcher.start(); self.addCleanup(patcher.stop)

    def test_work_sent_while_other_work_runs_waits_its_turn(self):
        # the assistants of one batch (eaos/features/fix/journey/lanes.py) send their changes at once: one is checked at a time
        import threading
        state = {'project': str(self.project)}
        first = agent_tools._start('fix_edit', state, {}, seconds=0)
        self.assertEqual(first['status'], 'running')
        busy = agent_tools._start('fix_edit', state, {}, seconds=0)
        self.assertEqual((busy['status'], busy['job']), ('busy', first['job']))
        ends = lambda: jobs._write({**jobs.read(first['job'], str(self.project)), 'status': 'done', 'result': {}})
        threading.Timer(0.5, ends).start()
        second = agent_tools._start('fix_edit', state, {}, seconds=5)
        self.assertNotEqual(second['job'], first['job'], 'it started once the first one ended')

    def test_a_job_runs_on_its_own_is_read_back_stops_as_an_interrupt_and_a_dead_one_has_failed(self):
        project = str(self.project)
        job = jobs.start('audit', project, {})
        record = json.loads((jobs.folder(project) / f'{job}.json').read_text())
        self.assertEqual((record['status'], record['kind']), ('running', 'audit'))
        given = jobs.subprocess.Popen.call_args.kwargs['env']['EAOS_ENGINE_CACHE']
        self.assertEqual(given, str(jobs.cache(project)), "the analyzers' caches are the project's own")
        jobs.cache(project).mkdir()
        with mock.patch.dict(agent_tools.JOBS,
                             {'audit': lambda project, arguments, progress: progress(1, 2, 'half') or {'ok': True}}):
            jobs.run(job, project)
        self.assertFalse(jobs.cache(project).exists(), 'and go when the job ends')
        self.assertEqual((jobs.read(job, project)['status'], jobs.read(job, project)['result']), ('done', {'ok': True}))
        self.assertEqual(jobs.read(job, project)['progress'], {'done': 1, 'total': 2, 'stage': 'half'})
        with self.assertRaises(ValueError): jobs.read('../state', project)
        job = jobs.start('audit', project, {})
        record = json.loads((jobs.folder(project) / f'{job}.json').read_text())
        record.update(status='running', pid=2 ** 22 + 12345)
        (jobs.folder(project) / f'{job}.json').write_text(json.dumps(record))
        self.assertEqual(jobs.read(job, project)['status'], 'failed')
        self.assertIn('start it again', jobs.read(job, project)['error'])
        import signal
        import time
        job = jobs.start('audit', project, {})
        self.addCleanup(signal.signal, signal.SIGTERM, signal.getsignal(signal.SIGTERM))
        def work(project, arguments, progress):
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(5)
        with mock.patch.dict(agent_tools.JOBS, {'audit': work}):
            self.assertEqual(jobs.run(job, project), 1)
        self.assertIn('KeyboardInterrupt', jobs.read(job, project)['error'])

    def test_where_studios_are_services_a_job_is_one_too_so_the_assistant_s_session_cannot_end_it(self):
        # a remote server ends an assistant's session with everything it started, a batch's hand-over among it
        from eaos.kernel.system import launch
        with mock.patch.object(launch, 'durable', return_value=True), \
                mock.patch.object(launch, 'as_unit',
                                  return_value=True) as unit, mock.patch.object(launch, 'unit_pid', return_value=4321):
            job = jobs.start('fix_finish', str(self.project), {})
        self.assertEqual(unit.call_args.args[0], f'eaos-job-{job}')
        self.assertEqual(json.loads((jobs.folder(str(self.project)) / f'{job}.json').read_text())['pid'], 4321)
        jobs.subprocess.Popen.assert_not_called()
        record = {**json.loads((jobs.folder(str(self.project)) / f'{job}.json').read_text()), 'pid': 2 ** 22 + 12345}
        (jobs.folder(str(self.project)) / f'{job}.json').write_text(json.dumps(record))
        self.assertIn('fix_finish goes on from them', jobs.read(job, str(self.project))['error'])

    def test_a_project_reads_only_its_own_jobs_and_keeps_only_its_last_ones(self):
        other = Path(self.tmp.name) / 'other'
        other.mkdir()
        (other / 'package.json').write_text('{}')
        theirs = jobs.start('audit', str(other), {})
        os.chdir(self.project)
        self.addCleanup(os.chdir, ROOT)
        self.assertIn(theirs, agent_tools.wait(theirs, 0, str(other))['job'])
        for read in (lambda: agent_tools.wait(theirs, 0), lambda: jobs.read(theirs, str(self.project))):
            with self.assertRaisesRegex(ValueError, 'no job named'): read()
        legacy = jobs.folder(str(self.project)).parent.parent.parent / 'jobs'
        legacy.mkdir()
        (legacy / 'audit-old.json').write_text('{}')
        os.utime(legacy / 'audit-old.json', (0, 0))
        with mock.patch.object(jobs, 'KEEP', 2), mock.patch.dict(agent_tools.JOBS, {'audit': lambda *given: {}}):
            for _ in range(3): jobs.run(jobs.start('audit', str(self.project), {}), str(self.project))
        self.assertEqual(len(list(jobs.folder(str(self.project)).glob('*.json'))), 2,
                         'a project keeps its last jobs only')
        self.assertFalse(legacy.exists(), "the folder older versions shared between projects goes")


class QuestionTests(Home):
    """The person's questions about their code: impact, ask and tools_check."""

    def call(self, name, arguments):
        from eaos.doors.mcp_server.server import build
        os.chdir(self.project)
        self.addCleanup(os.chdir, ROOT)
        return json.loads(asyncio.run(build().call_tool(name, arguments)).content[0].text)

    def test_questions_wait_for_a_check_then_answer_from_its_facts(self):
        import shutil
        from eaos.features.plan.analysis.dossier import assemble
        self.assertIn('audit', self.call('impact', {'target': 'src/a.js'})['error'])
        self.assertIn('audit', self.call('ask', {'question': 'pricing'})['error'])
        project = Path(self.tmp.name) / 'polyglot'
        shutil.copytree(ROOT / 'tests/fixtures/polyglot', project)
        git_project(project)
        self.project = project
        report = guided.report_of(agent_tools.state_of(str(project)))
        assemble(project, report)
        (report / 'plan.json').write_text('{}')
        touched = self.call('impact', {'target': 'core/pricing.py'})
        self.assertEqual(sorted(touched['direct_dependents']), ['cli.py', 'core/audit.py', 'worker/tasks.py'])
        self.assertTrue(touched['limits'], 'what the answer cannot see is said with it')
        found = self.call('ask', {'question': 'price_for'})
        self.assertEqual(found['status'], 'ANSWERED')
        self.assertTrue(all(answer.get('id') for answer in found['answers']))

    def test_the_tools_say_this_version_and_what_this_project_needs(self):
        from eaos import __version__
        checked = self.call('tools_check', {})
        self.assertEqual(checked['eaos']['version'], __version__)
        self.assertEqual(checked['total'], len(checked['tools']))
        if checked['for_the_check']['failed']:
            self.assertEqual(checked['install'], 'eaos tools install')


class PersonOnly(Home):
    """What only the person decides, from a terminal and from the governance tools: refused without their word, and
    refused inside a run even with it (eaos/doors/govern.py, eaos/doors/terminal/commands.py,
    eaos/doors/mcp_server/govern.py)."""

    def setUp(self):
        super().setUp()
        from eaos.doors import govern
        govern._core.cache_clear()
        self.addCleanup(govern._core.cache_clear)
        wave_branch(self.project)
        state = agent_tools.state_of(str(self.project))
        state['waves'] = [{'number': 1, 'branch': 'eaos/wave-1', 'status': 'applied'}]
        guided.save(state)

    def eaos(self, *argv, studio_run=False):
        """(exit, printed) of one eaos command, nobody at the terminal."""
        import contextlib, io
        from eaos.doors import cli
        env = {'EAOS_STUDIO_RUN': 'r1'} if studio_run else {}
        with contextlib.redirect_stdout(io.StringIO()) as printed, mock.patch.dict(os.environ, env), \
                mock.patch('sys.stdin.isatty', return_value=False):
            code = cli.main([*argv, '--lang', 'en'])
        return code, printed.getvalue()

    def has(self, branch):
        return subprocess.run(['git', '-C', str(self.project), 'rev-parse', '--verify', '-q', branch],
                              capture_output=True).returncode == 0

    def test_accept_and_undo_say_what_happens_and_wait_for_a_yes_never_given_inside_a_studio_run(self):
        code, printed = self.eaos('accept', str(self.project))
        self.assertEqual(code, 4)
        self.assertIn('merges eaos/wave-1 into', printed)
        self.assertIn('eaos accept', printed.split('copy and paste')[-1])
        self.assertEqual(self.eaos('accept', str(self.project), '--yes', studio_run=True)[0], 3)
        self.assertEqual(self.eaos('undo', str(self.project), '--yes', studio_run=True)[0], 3)
        with mock.patch('sys.stdin.isatty', return_value=True), mock.patch('builtins.input', side_effect=EOFError):
            from eaos.doors import cli
            self.assertEqual(cli.main(['accept', str(self.project), '--lang', 'en']), 5,
                             'the input ended: a no, never a traceback')
        self.assertEqual(agent_tools.undo(str(self.project))['status'], 'needs_agreement',
                         'the tool waits for the person too')
        self.assertTrue(self.has('eaos/wave-1'), 'nothing happened without the person')
        code, printed = self.eaos('undo', str(self.project), '--yes')
        self.assertEqual(code, 0, printed)
        self.assertFalse(self.has('eaos/wave-1'))

    def test_branch_changes_answers_and_a_fix_that_accepts_itself_need_the_persons_word_and_never_in_a_studio_run(self):
        from eaos.doors import govern
        from eaos.doors.mcp_server import govern as mcp_govern
        subprocess.run(['git', '-C', str(self.project), 'branch', 'feature'], check=True)
        for argv in (('branch', 'eaos/wave-1', '--yes'), ('branches', 'delete', 'feature', '--yes'),
                     ('answer', 'q1', 'yes'),
                     ('fix', 'TASK-001', '--auto-accept', '--yes')):
            self.assertEqual(self.eaos(*argv, '--project', str(self.project), studio_run=True)[0], 3, argv)
        with mock.patch.dict(os.environ, {'EAOS_STUDIO_RUN': 'r1'}):
            for call in (lambda: mcp_govern.branch_change('delete', 'feature', project=str(self.project)),
                         lambda: mcp_govern.waiting('answer', 'q1', 'yes', person_said='yes',
                                                    project=str(self.project)),
                         lambda: mcp_govern.act('fix', ['TASK-001'], op='start', auto_accept=True, person_agreed=True,
                                                project=str(self.project))):
                self.assertRaises(PermissionError, call)
        self.assertEqual(self.eaos('branches', 'delete', 'feature', '--project', str(self.project))[0], 4)
        shown = mcp_govern.branch_change('delete', 'feature', project=str(self.project))
        asked = mcp_govern.branch_change('delete', 'feature', confirm=shown['confirm'], project=str(self.project))
        self.assertEqual(asked['status'], 'needs_the_person')
        self.assertTrue(self.has('feature'), 'a confirm token proves a preview was seen, not that the person agreed')
        mcp_govern.branch_change('delete', 'feature', confirm=shown['confirm'], person_agreed=True,
                                 project=str(self.project))
        self.assertFalse(self.has('feature'))
        kept = govern.core(str(self.project)).branches.recoveries()[-1]['id']
        self.assertEqual(self.eaos('branches', 'restore', kept, '--project', str(self.project), '--yes',
                                   studio_run=True)[0], 3)
        with mock.patch.dict(os.environ, {'EAOS_STUDIO_RUN': 'r1'}):
            self.assertRaises(PermissionError,
                              lambda: mcp_govern.branch_change('restore', kept, person_agreed=True,
                                                               project=str(self.project)))
        self.assertEqual(self.eaos('branches', 'restore', kept, '--project', str(self.project))[0], 4)
        self.assertEqual(mcp_govern.branch_change('restore', kept, project=str(self.project))['status'],
                         'needs_the_person')
        self.assertFalse(self.has('feature'), 'a deleted branch comes back only with the person\'s yes')
        self.assertEqual(mcp_govern.act('fix', ['TASK-001'], op='start', auto_accept=True,
                                        project=str(self.project))['status'], 'needs_the_person')
        self.assertIn('no reply', mcp_govern.waiting('answer', 'q1', 'yes', project=str(self.project))['why'])
        govern.shown('q1')
        self.assertIn('not answered yet',
                      mcp_govern.waiting('answer', 'q1', 'yes', person_said='yes', project=str(self.project))['why'])
        govern._SHOWN['q1'] -= agent_tools.ANSWER_SECONDS
        with mock.patch.object(govern, 'answer', return_value={'status': 'answered'}) as answered:
            self.assertEqual(mcp_govern.waiting('answer', 'q1', 'yes', person_said='نعم',
                                                project=str(self.project))['status'], 'answered')
        answered.assert_called_once()

    def test_the_mcp_wait_follows_a_job_of_the_project_it_names(self):
        from eaos.doors.mcp_server import server as mcp_server
        with mock.patch.object(agent_tools, 'wait', return_value={'status': 'running'}) as waited:
            mcp_server.functions()['wait'](job='audit-1', seconds=0, project=str(self.project))
        waited.assert_called_once_with('audit-1', 0, str(self.project))


if __name__ == '__main__':
    unittest.main()
