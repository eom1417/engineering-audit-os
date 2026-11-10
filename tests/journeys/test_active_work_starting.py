"""What a job is doing is not taken from under it: starting a batch during a job, on real repositories with real
threads and processes."""
import contextlib
import fcntl
import os
import unittest
from unittest import mock
from eaos.core.project import jobs, state as project_state
from eaos.journeys import agent_tools, guided
from eaos.journeys.agent_tools import fixing
from eaos.journeys.fix import lanes
from eaos.live.app import setup as live_setup
from tests.journeys.test_continuity import git
from tests.journeys.test_stale_batch_changes import EDIT
from tests.journeys._active_work_fixture import Paused, SECONDS, UNIQUE, Work, _job


class StartingDuringAJob(Work):
    def merged_branch(self):
        git(self.project, 'checkout', '-qb', 'eaos/main/wave-9')
        self.person_commits('fixed.js')
        tip = git(self.project, 'rev-parse', 'HEAD')
        git(self.project, 'checkout', '-q', '-')
        state = project_state.load(self.project)
        state.setdefault('waves',
                         []).append({'number': 9, 'branch': 'eaos/main/wave-9', 'status': 'applied', 'tip': tip,
                                     'merge_into': git(self.project, 'rev-parse', '--abbrev-ref', 'HEAD'), 'cards': [],
                                     'kept': {}})
        project_state.write(state)
        git(self.project, 'merge', '-q', '--no-ff', '-m', 'by hand', 'eaos/main/wave-9')

    def test_every_kind_of_job_holds_it_with_nothing_closed_deleted_or_launched(self):
        self.stale()
        for kind in ('fix_edit', 'fix_finish', 'audit', 'safety_net', 'run_try', 'moves_make', 'build_edit'):
            with self.subTest(kind=kind):
                _job(self.project, kind, ident='the-job')
                with mock.patch.object(jobs, 'start') as started:
                    self.assertBusy(agent_tools.fix_start(self.where))
                started.assert_not_called()
                self.assertEqual((self.copy.is_dir(), self.closed(), self.wave()['number']), (True, [], 1))

    def test_a_job_keeps_a_merged_branch_from_going_and_its_record_unsettled(self):
        self.merged_branch()
        _job(self.project, 'audit')
        self.assertBusy(agent_tools.fix_start(self.where))
        self.assertEqual(self.branches(), ['eaos/main/wave-9'])
        self.assertEqual(self.closed(), ['applied'])

    def test_once_the_job_ended_it_settles_and_closes_as_ever(self):
        self.merged_branch()
        self.stale()
        _job(self.project, 'audit')
        self.assertBusy(agent_tools.fix_start(self.where))
        _job(self.project, 'audit', status='done')
        with mock.patch.object(fixing, '_start', return_value={'job': 'j'}):
            agent_tools.fix_start(self.where)
        self.assertEqual(self.branches(), [])
        self.assertEqual((self.closed(), self.copy.exists()), (['accepted', 'superseded'], False))

    def test_a_helper_closes_nothing(self):
        self.stale()
        with self.helper():
            self.assertEqual(agent_tools.fix_start(self.where)['status'], 'not_yours')
        self.assertEqual((self.copy.is_dir(), self.closed()), (True, []))

    def test_a_helper_is_told_so_even_while_a_job_runs(self):
        self.stale()
        with self.helper():
            _job(self.project)
            self.assertEqual(agent_tools.fix_start(self.where)['status'], 'not_yours')

    def test_a_helper_named_while_it_waited_closes_nothing(self):
        self.stale()
        real = jobs.alone
        @contextlib.contextmanager
        def meanwhile(*args):
            with real(*args):
                state = project_state.load(self.project)
                state['open_wave'].update(lanes=[['TASK-001'], ['TASK-002']], claims={}, helpers={'h1': 1}, later=[],
                                          released=[])
                guided.save(state)
                yield
        with mock.patch.dict(os.environ, {'EAOS_STUDIO_RUN': 'h1'}), mock.patch.object(jobs, 'alone', meanwhile):
            self.assertEqual(agent_tools.fix_start(self.where)['status'], 'not_yours')
        self.assertEqual((self.copy.is_dir(), self.closed()), (True, []))

    def test_it_lets_go_of_the_lock_before_it_starts_its_job(self):
        state = project_state.load(self.project)
        state.pop('open_wave')
        project_state.write(state)
        held = []
        def started(*_, **__):
            jobs.folder(self.project).mkdir(parents=True, exist_ok=True)
            with open(jobs.folder(self.project) / '.turn.lock', 'a') as lock:
                try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB); held.append(False)
                except OSError: held.append(True)
            return {'job': 'j'}
        with mock.patch.object(fixing, '_start', started), mock.patch.object(fixing, '_not_ready', return_value=None), \
                mock.patch.object(fixing, '_chosen', return_value=(None, ['TASK-001'])):
            agent_tools.fix_start(self.where)
        self.assertEqual(held, [False])

    def test_a_write_of_the_lanes_going_on_does_not_bring_back_a_retired_batch(self):
        self.stale()
        state = project_state.load(self.project)
        state['open_wave'].update(lanes=[['TASK-001'], ['TASK-002']], claims={}, helpers={}, later=[], released=[])
        guided.save(state)
        writing = Paused(lambda: lanes.take(self.where, 'TASK-001', EDIT))
        with mock.patch.object(lanes, 'held',
                               side_effect=lambda *_: writing.at([])()), mock.patch.object(fixing, '_start',
                                                                                           return_value={'job': 'j'}):
            writing.start()
            self.assertTrue(writing.reached.wait(SECONDS))
            starting = Paused(lambda: agent_tools.fix_start(self.where)).start()
            starting.thread.join(0.5)
            writing.end()
            starting.thread.join(SECONDS)
        state = project_state.load(self.project)
        self.assertEqual((state.get('open_wave'), self.closed()), (None, ['superseded']))

    def job_with_the_batch_closed(self):
        state = project_state.load(self.project)
        state.pop('open_wave')
        project_state.write(state)
        live_setup.authorize(self.where, project_state.runtime_of(state), live_setup.owner(self.where))
        return {'cards': ['TASK-001'], 'deliver_as': None, 'merge_into': None, 'assistants': 1,
                'scanned': state.get('scanned')}

    def test_a_job_finding_a_batch_waiting_for_a_decision_opens_none(self):
        arguments = self.job_with_the_batch_closed()
        state = project_state.load(self.project)
        state.setdefault('waves',
                         []).append({'number': 1, 'status': 'applied', 'branch': 'eaos/x', 'cards': [], 'kept': {},
                                     'merge_into': 'main'})
        project_state.write(state)
        answer = fixing._fix_start_job(self.where, arguments, lambda *_: None)
        self.assertIsNone(project_state.load(self.project).get('open_wave'), answer)
        self.assertTrue(answer.get('what_now'))

    def test_a_job_finding_a_newer_check_opens_none(self):
        arguments = self.job_with_the_batch_closed()
        self.numbered_again()
        state = project_state.load(self.project)
        state['scanned'] = 'a newer check'
        guided.save(state)
        answer = fixing._fix_start_job(self.where, arguments, lambda *_: None)
        self.assertEqual(answer.get('status'), 'plan_changed', answer)
        self.assertIsNone(project_state.load(self.project).get('open_wave'))

    def test_a_helper_starts_no_check_that_would_close_the_batch(self):
        self.stale()
        with self.helper(), mock.patch.object(jobs, 'start') as started:
            self.assertEqual(agent_tools.audit(self.where)['status'], 'not_yours')
        started.assert_not_called()

    def test_a_job_that_finds_a_batch_open_opens_no_other(self):
        (self.copy / 'first.js').write_text(UNIQUE)
        live_setup.authorize(self.where, project_state.runtime_of(project_state.load(self.project)),
                             live_setup.owner(self.where))
        answer = fixing._fix_start_job(self.where,
                                       {'cards': ['TASK-001'], 'deliver_as': None, 'merge_into': None, 'assistants': 1},
                                       lambda *_: None)
        self.assertEqual(answer.get('status'), 'open', answer)
        self.assertEqual((self.copy / 'first.js').read_text(), UNIQUE)
        self.assertEqual((self.wave()['number'], self.wave()['root']), (1, str(self.copy)))


class NothingComesBack(Work):
    def test_a_job_with_an_older_state_saves_after_no_closing_happened(self):
        self.stale()
        older = project_state.load(self.project)
        _job(self.project, 'audit')
        self.assertBusy(agent_tools.fix_start(self.where))
        guided.save(older)
        state = project_state.load(self.project)
        self.assertEqual((state['open_wave']['number'], state.get('waves') or [], self.copy.is_dir()), (1, [], True))

    def test_abandoned_under_a_job_no_later_save_of_that_job_brings_it_back(self):
        older = project_state.load(self.project)
        _job(self.project)
        self.assertBusy(agent_tools.fix_abandon(self.where))
        guided.save(older)
        self.assertEqual((self.wave()['number'], self.copy.is_dir()), (1, True))


if __name__ == '__main__':
    unittest.main()
