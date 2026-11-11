"""What a job is doing is not taken from under it: cleaning beside a job. A job that does not answer is not assumed
dead."""
import contextlib
import fcntl
import io
import json
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock
from eaos.core.project import jobs, state as project_state
from eaos.interfaces import cli
from eaos.journeys import agent_tools, guided
from eaos.live.access import sign_in
from tests.journeys._active_work_fixture import SECONDS, Work, _job


class CleaningBesideAJob(Work):
    def setUp(self):
        super().setUp()
        self.state = project_state.load(self.project)
        self.session = project_state.runtime_of(self.state) / 'session.json'
        self.session.parent.mkdir(parents=True, exist_ok=True)
        self.session.write_text(json.dumps({'cookies': [], 'origins': []}))
        self.outputs = Path(guided.outputs(self.state))
        guided.save(self.state)
        self.pictures = self.outputs / 'technical' / 'live' / 'screens'
        self.pictures.mkdir(parents=True)
        (self.pictures / 'x.png').write_text('x')

    def clean(self, *argv):
        said = io.StringIO()
        with contextlib.redirect_stdout(said): self.assertEqual(cli.main(['clean', '--lang', 'en', *argv]), 0)
        return said.getvalue()

    def starts_while(self, patch_target, name):
        """A job asks to start as `name` removes. It must wait for the removal, and only then begin."""
        real, order = getattr(patch_target, name), []
        def removing(*args, **options):
            asking = threading.Thread(target=self.job_begins, args=(order,), daemon=True)
            asking.start()
            asking.join(1)
            order.append('removal')
            answer = real(*args, **options)
            order.append('removed')
            self.waiting = asking
            return answer
        return mock.patch.object(patch_target, name, removing), order

    def job_begins(self, order):
        with jobs.alone(self.where, SECONDS): order.append('job began')     # as a job's start waits its turn

    def test_a_job_starting_during_the_session_removal_waits_for_it(self):
        patch, order = self.starts_while(sign_in, 'forget')
        with patch: self.clean()
        self.waiting.join(SECONDS)
        self.assertEqual(order[-1], 'job began', order)

    def test_a_job_starting_during_the_picture_removal_waits_for_it(self):
        from eaos.pipeline import run as pipeline_run
        patch, order = self.starts_while(pipeline_run, 'clear')
        with patch: self.clean('--pictures')
        self.waiting.join(SECONDS)
        self.assertEqual(order[-1], 'job began', order)

    def test_a_running_job_keeps_both(self):
        _job(self.project, 'audit')
        self.clean('--pictures')
        self.assertEqual((self.session.is_file(), self.pictures.is_dir()), (True, True))

    def test_a_queued_or_going_run_keeps_both(self):
        run = Path(self.state['workspace']) / 'runs' / 'r1'
        run.mkdir(parents=True)
        for state in ('queued', 'running', 'waiting_for_person'):
            with self.subTest(state=state):
                (run / 'run.json').write_text(json.dumps({'id': 'r1', 'state': state}))
                self.clean('--pictures')
                self.assertEqual((self.session.is_file(), self.pictures.is_dir()), (True, True))
        (run / 'run.json').write_text('{"id": "r1", "state": "done"}')
        self.clean('--pictures')
        self.assertEqual((self.session.exists(), self.pictures.exists()), (False, False))

    def test_a_state_naming_another_project_keeps_the_sessions_of_this_folder(self):
        other = self.root_for_other()
        record = Path(self.state['workspace']) / 'state.json'
        record.write_text(json.dumps(project_state.load(other)))
        self.clean()
        self.assertTrue(self.session.is_file())

    def test_a_mark_whose_project_state_names_another_keeps_the_pictures(self):
        record = Path(self.state['workspace']) / 'state.json'
        record.write_text(json.dumps({**json.loads(record.read_text()),
                                      'project': str(self.project.parent / 'elsewhere')}))
        self.clean('--pictures')
        self.assertTrue(self.pictures.is_dir())

    def test_with_no_work_both_go(self):
        self.clean('--pictures')
        self.assertEqual((self.session.exists(), self.pictures.exists()), (False, False))

    def test_a_folder_of_no_known_project_keeps_its_sessions_and_names_them(self):
        (Path(self.state['workspace']) / 'state.json').unlink()
        said = self.clean()
        self.assertTrue(self.session.is_file())
        self.assertIn(str(Path(self.state['workspace'])), said)

    def test_a_mark_that_does_not_tell_whose_keeps_the_pictures_and_names_them(self):
        mark = self.outputs / '.eaos-project'
        other = self.root_for_other()
        for name, change in (('missing', mark.unlink), ('unreadable', lambda: mark.write_bytes(b'\xff\xfe')),
                             ('empty', lambda: mark.write_text('')),
                             ('no project known', lambda: mark.write_text(str(self.project.parent / 'nothing-here'))),
                             ('another project\'s', lambda: mark.write_text(str(other)))):
            with self.subTest(mark=name):
                change()
                said = self.clean('--pictures')
                self.assertTrue(self.pictures.is_dir())
                self.assertIn(str(self.outputs / 'technical'), said)
                mark.write_text(str(self.project) + '\n')

    def root_for_other(self):
        from tests.interfaces.test_mcp import git_project
        other = git_project(self.project.parent / 'other')
        agent_tools.state_of(str(other))
        return other

    def test_one_project_busy_cleans_the_other_and_makes_it_wait_for_nothing(self):
        other = self.root_for_other()
        state = project_state.load(other)
        session = project_state.runtime_of(state) / 'session.json'
        session.parent.mkdir(parents=True, exist_ok=True)
        session.write_text(json.dumps({'cookies': [], 'origins': []}))
        _job(self.project, 'audit')
        lock = open(jobs.folder(self.project) / '.turn.lock', 'a')
        self.addCleanup(lock.close)
        fcntl.flock(lock,
                    fcntl.LOCK_EX)                    # this project's lock held by another hand: the other goes on
        began = time.monotonic()
        with jobs.alone(str(other)): self.assertLess(time.monotonic() - began, 2)
        self.clean()
        self.assertEqual((self.session.is_file(), session.exists()), (True, False))


class AJobWithNoProcessKnown(Work):
    def pidless(self):
        _job(self.project, pid=0, ident='no-pid')
        record = json.loads(jobs._path('no-pid', self.where).read_text())
        record['pid'] = None
        jobs._write(record)

    def worker(self):
        process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)', 'eaos.core.project.jobs',
                                    'no-pid', self.where])
        self.addCleanup(process.wait)
        self.addCleanup(process.kill)
        return process

    def test_its_process_there_it_is_running_however_old_the_record(self):
        self.pidless()
        self.worker()
        with self.assertRaises(jobs.Busy):
            with jobs.alone(self.where): pass
        self.assertEqual(jobs.read('no-pid', self.where)['status'], 'running')
        self.assertEqual(agent_tools.fix_abandon(self.where)['status'], 'busy')
        self.assertTrue(self.copy.is_dir())

    def test_the_launcher_at_work_it_is_never_failed(self):
        self.pidless()
        with open(jobs.folder(self.project) / '.turn.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self.assertEqual(jobs.read('no-pid', self.where)['status'], 'running')
            self.assertTrue(jobs.running(self.where))

    def test_no_process_and_no_launcher_it_failed_and_the_work_goes_on(self):
        self.pidless()
        self.assertEqual(agent_tools.fix_abandon(self.where)['status'], 'abandoned')
        record = jobs.read('no-pid', self.where)
        self.assertEqual(record['status'], 'failed')
        self.assertTrue(record['error'])

    def test_its_process_gone_later_it_fails_then(self):
        self.pidless()
        process = self.worker()
        self.assertEqual(agent_tools.fix_abandon(self.where)['status'], 'busy')
        process.kill()
        process.wait()
        self.assertEqual(agent_tools.fix_abandon(self.where)['status'], 'abandoned')

    def test_a_worker_writing_its_end_as_it_is_looked_at_keeps_its_result(self):
        self.pidless()
        def ended_meanwhile(_):
            record = json.loads(jobs._path('no-pid', self.where).read_text())
            record.update(status='done', result={'kept': True})
            jobs._write(record)
            return False
        with mock.patch.object(jobs, '_has_process', ended_meanwhile):
            with jobs.alone(self.where): pass
        record = jobs.read('no-pid', self.where)
        self.assertEqual((record['status'], record['result']), ('done', {'kept': True}))

    def test_when_processes_cannot_be_listed_it_stays_running(self):
        self.pidless()
        with mock.patch.object(jobs.subprocess, 'run', side_effect=FileNotFoundError('pgrep')):
            with self.assertRaises(jobs.Busy):
                with jobs.alone(self.where): pass
        self.assertEqual(jobs.read('no-pid', self.where)['status'], 'running')

    def test_when_listing_processes_fails_it_stays_running(self):
        self.pidless()
        with mock.patch.object(jobs.subprocess, 'run', return_value=subprocess.CompletedProcess([], 2)):
            with self.assertRaises(jobs.Busy):
                with jobs.alone(self.where): pass

    def test_clean_leaves_the_copies_of_a_worker_with_no_pid(self):
        self.pidless()
        self.worker()
        with contextlib.redirect_stdout(io.StringIO()): cli.main(['clean', '--lang', 'en'])
        self.assertTrue(self.copy.is_dir())


if __name__ == '__main__':
    unittest.main()
