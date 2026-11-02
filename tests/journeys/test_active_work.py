"""What a job is doing is not taken from under it: closing a batch, starting one, opening a build, cleaning, all under the
lock jobs start by, on real repositories with real threads and processes. A job that does not answer is not assumed dead."""
import contextlib
import fcntl
import io
import json
import os
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from eaos.core.project import jobs, state as project_state
from eaos.interfaces import cli, studio_actions as actions
from eaos.interfaces.mcp_server.server import functions
from eaos.journeys import agent_tools, guided
from eaos.journeys.agent_tools import fixing
from eaos.journeys.build_from_plan import steps
from eaos.journeys.fix import execute, finish as batch_finish, lanes
from eaos.journeys.fix.waves import batch as batch_steps
from eaos.live.access import sign_in
from eaos.live.app import setup as live_setup
from tests.journeys.test_continuity import git
from tests.journeys.test_stale_batch_changes import Batch, EDIT

UNIQUE = 'written nowhere else\n'
SECONDS = 20


def _job(project, kind='fix_edit', status='running', pid=None, ident=None):
    jobs._write({'id': ident or f'{kind}-1', 'kind': kind, 'project': str(project), 'status': status, 'pid': os.getpid() if pid is None else pid,
                 'arguments': {}, 'started': '2026-01-01T00:00:00+00:00', 'result': None, 'error': None, 'progress': None, 'log': 'x'})


class Paused:
    """`work` in a thread, stopped at the point `at` of a real job until released."""

    def __init__(self, work):
        self.reached, self.go, self.outcome = threading.Event(), threading.Event(), {}
        def run():
            try: self.outcome['result'] = work()
            except BaseException as problem: self.outcome['raised'] = f'{type(problem).__name__}: {problem}'
        self.thread = threading.Thread(target=run, daemon=True)

    def at(self, value=None):
        def here(*_, **__):
            self.reached.set()
            self.go.wait(SECONDS)
            return value
        return here

    def start(self):
        self.thread.start()
        return self

    def end(self):
        self.go.set()
        self.thread.join(SECONDS)
        assert not self.thread.is_alive(), 'it never ended: a deadlock'
        return self.outcome


class Work(Batch):
    def edit_job(self):
        return fixing._fix_edit_job(self.where, {'card': 'TASK-001', 'edits': EDIT, 'summary': 'a fix'}, lambda *_: None)

    def assertBusy(self, answer):
        self.assertEqual(answer.get('status'), 'busy', answer)
        self.assertTrue(answer.get('error'))
        self.assertTrue(answer.get('what_now'))

    def stale(self):
        self.person_commits()
        guided.save(project_state.load(self.project))

    def wave(self):
        return project_state.load(self.project).get('open_wave')

    def closed(self):
        return [wave['status'] for wave in project_state.load(self.project).get('waves') or []]

    def helper(self):
        state = project_state.load(self.project)
        state['open_wave'].update(lanes=[['TASK-001'], ['TASK-002']], claims={}, helpers={'h1': 1}, later=[], released=[])
        guided.save(state)
        return mock.patch.dict(os.environ, {'EAOS_STUDIO_RUN': 'h1'})


class AbandoningDuringAJob(Work):
    def test_a_running_edit_keeps_its_copy_and_ends_and_the_batch_closes_after(self):
        _job(self.project)
        worker = Paused(self.edit_job)
        with mock.patch('eaos.journeys.fix.waves.edit_gates', worker.at(([], 0, None))):
            worker.start()
            self.assertTrue(worker.reached.wait(SECONDS))
            began = time.monotonic()
            self.assertBusy(agent_tools.fix_abandon(self.where))
            self.assertLess(time.monotonic() - began, 5, 'it answers at once, it does not wait for the job')
            self.assertTrue(self.copy.is_dir())
            outcome = worker.end()
        self.assertTrue(outcome['result']['kept'], outcome)
        self.assertEqual(list(self.wave()['kept']), ['TASK-001'])
        _job(self.project, status='done')
        self.assertEqual(agent_tools.fix_abandon(self.where)['status'], 'abandoned')
        self.assertFalse(self.copy.exists())

    def test_a_running_hand_over_keeps_its_copy_and_delivers(self):
        self.keep_one()
        state = project_state.load(self.project)
        state['open_wave']['failed']['TASK-002'] = 'skipped: x'
        guided.save(state)
        _job(self.project, 'fix_finish')
        worker = Paused(lambda: batch_finish.finish_job(self.where, {}, lambda *_: None))
        patches = [mock.patch.object(batch_steps, '_accepted', side_effect=lambda b, cards, kept, *_: kept), mock.patch.object(batch_steps, '_secure', side_effect=lambda b, kept, *_: kept),
                   mock.patch.object(batch_steps, '_through_gates', side_effect=lambda b, kept, *_: worker.at(kept)()), mock.patch.object(batch_steps, '_declare'), mock.patch.object(batch_steps, '_new_truth'),
                   mock.patch('eaos.journeys.fix.regenerate.regenerate'), mock.patch('eaos.journeys.fix.regenerate.keep_guide')]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        worker.start()
        self.assertTrue(worker.reached.wait(SECONDS))
        self.assertBusy(agent_tools.fix_abandon(self.where))
        self.assertTrue(self.copy.is_dir())
        worker.end()
        self.assertEqual(self.closed(), ['applied'])
        self.assertTrue(self.branches())

    def test_a_queued_run_holds_it_and_its_end_frees_it(self):
        run = Path(project_state.load(self.project)['workspace']) / 'runs' / 'r1'
        run.mkdir(parents=True)
        (run / 'run.json').write_text('{"id": "r1", "state": "queued"}')
        self.assertBusy(agent_tools.fix_abandon(self.where))
        self.assertTrue(self.copy.is_dir())
        (run / 'run.json').write_text('{"id": "r1", "state": "done"}')
        self.assertEqual(agent_tools.fix_abandon(self.where)['status'], 'abandoned')

    def test_the_run_asking_for_it_does_not_hold_it(self):
        run = Path(project_state.load(self.project)['workspace']) / 'runs' / 'r1'
        run.mkdir(parents=True)
        (run / 'run.json').write_text('{"id": "r1", "state": "running"}')
        self.assertEqual(agent_tools.fix_abandon(self.where)['status'], 'abandoned')

    def test_it_answers_at_once_while_another_waits_with_the_lock(self):
        _job(self.project)
        waiting = threading.Thread(target=self.waits_its_turn, daemon=True)
        waiting.start()
        time.sleep(0.3)
        began = time.monotonic()
        self.assertBusy(agent_tools.fix_abandon(self.where))
        self.assertLess(time.monotonic() - began, 1.5, 'waited behind the other')
        waiting.join(SECONDS)

    def waits_its_turn(self):
        with contextlib.suppress(jobs.Busy):
            with jobs.alone(self.where, 3): pass

    def test_a_write_of_the_lanes_going_on_does_not_bring_it_back(self):
        state = project_state.load(self.project)
        state['open_wave'].update(lanes=[['TASK-001'], ['TASK-002']], claims={}, helpers={}, later=[], released=[])
        guided.save(state)
        writing = Paused(lambda: lanes.take(self.where, 'TASK-001', EDIT))
        with mock.patch.object(lanes, 'held', side_effect=lambda *_: writing.at([])()):
            writing.start()
            self.assertTrue(writing.reached.wait(SECONDS))
            closing = Paused(lambda: agent_tools.fix_abandon(self.where)).start()
            closing.thread.join(0.5)
            writing.end()
            closing.thread.join(SECONDS)
        self.assertEqual(closing.outcome['result']['status'], 'abandoned')
        state = project_state.load(self.project)
        self.assertEqual((state.get('open_wave'), self.closed()), (None, ['abandoned']), 'an older save came back over the closing')

    def test_a_helper_still_may_not(self):
        with self.helper():
            self.assertEqual(agent_tools.fix_abandon(self.where)['status'], 'not_yours')
        self.assertTrue(self.copy.is_dir())

    def test_two_at_once_close_it_once(self):
        real, entered = jobs.alone, threading.Barrier(2)
        @contextlib.contextmanager
        def together(*args):
            entered.wait(SECONDS)
            with real(*args): yield
        answers = []
        def abandon():
            try: answers.append(agent_tools.fix_abandon(self.where)['status'])
            except LookupError: answers.append('none open')       # the other came first and ended; else it was still at it: busy
        with mock.patch.object(jobs, 'alone', together):
            threads = [threading.Thread(target=abandon) for _ in range(2)]
            for thread in threads: thread.start()
            for thread in threads: thread.join(SECONDS)
        self.assertEqual(answers.count('abandoned'), 1, answers)
        self.assertLessEqual(set(answers), {'abandoned', 'none open', 'busy'})
        self.assertEqual(self.closed(), ['abandoned'])

    def test_it_closes_the_batch_as_the_lock_finds_it_not_as_it_was_asked(self):
        real = jobs.alone
        @contextlib.contextmanager
        def meanwhile(*args):
            with real(*args):
                state = project_state.load(self.project)
                state['open_wave']['last_error'] = 'written while it waited'
                guided.save(state)
                yield
        with mock.patch.object(jobs, 'alone', meanwhile):
            agent_tools.fix_abandon(self.where)
        self.assertIn('written while it waited', project_state.load(self.project)['waves'][-1].get('why', ''))


class StartingDuringAJob(Work):
    def merged_branch(self):
        git(self.project, 'checkout', '-qb', 'eaos/main/wave-9')
        self.person_commits('fixed.js')
        tip = git(self.project, 'rev-parse', 'HEAD')
        git(self.project, 'checkout', '-q', '-')
        state = project_state.load(self.project)
        state.setdefault('waves', []).append({'number': 9, 'branch': 'eaos/main/wave-9', 'status': 'applied', 'tip': tip, 'merge_into': git(self.project, 'rev-parse', '--abbrev-ref', 'HEAD'), 'cards': [], 'kept': {}})
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
                state['open_wave'].update(lanes=[['TASK-001'], ['TASK-002']], claims={}, helpers={'h1': 1}, later=[], released=[])
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
        with mock.patch.object(fixing, '_start', started), mock.patch.object(fixing, '_not_ready', return_value=None), mock.patch.object(fixing, '_chosen', return_value=(None, ['TASK-001'])):
            agent_tools.fix_start(self.where)
        self.assertEqual(held, [False])

    def test_a_write_of_the_lanes_going_on_does_not_bring_back_a_retired_batch(self):
        self.stale()
        state = project_state.load(self.project)
        state['open_wave'].update(lanes=[['TASK-001'], ['TASK-002']], claims={}, helpers={}, later=[], released=[])
        guided.save(state)
        writing = Paused(lambda: lanes.take(self.where, 'TASK-001', EDIT))
        with mock.patch.object(lanes, 'held', side_effect=lambda *_: writing.at([])()), mock.patch.object(fixing, '_start', return_value={'job': 'j'}):
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
        return {'cards': ['TASK-001'], 'deliver_as': None, 'merge_into': None, 'assistants': 1, 'scanned': state.get('scanned')}

    def test_a_job_finding_a_batch_waiting_for_a_decision_opens_none(self):
        arguments = self.job_with_the_batch_closed()
        state = project_state.load(self.project)
        state.setdefault('waves', []).append({'number': 1, 'status': 'applied', 'branch': 'eaos/x', 'cards': [], 'kept': {}, 'merge_into': 'main'})
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
        live_setup.authorize(self.where, project_state.runtime_of(project_state.load(self.project)), live_setup.owner(self.where))
        answer = fixing._fix_start_job(self.where, {'cards': ['TASK-001'], 'deliver_as': None, 'merge_into': None, 'assistants': 1}, lambda *_: None)
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


class Building(Work):
    MILESTONE = {'id': 'M01', 'name': 'x', 'tasks': []}

    def setUp(self):
        super().setUp()
        state = project_state.load(self.project)
        state.pop('open_wave')
        project_state.write(state)
        for patch in (mock.patch.object(steps, '_plan', return_value={'milestones': [self.MILESTONE]}), mock.patch.object(steps, '_next_milestone', return_value=self.MILESTONE),
                      mock.patch.object(steps, '_cards', return_value={}), mock.patch.object(steps, 'publish'), mock.patch('eaos.journeys.build_from_plan.milestone_copy._commit_blueprint'),
                      mock.patch.object(steps, '_ensure_git', return_value=False), mock.patch.object(steps, '_open_answer', side_effect=lambda build: {'status': 'open', 'milestone': build['milestone']}),
                      mock.patch('eaos.live.app.setup.authorize')):
            patch.start()
            self.addCleanup(patch.stop)
        self.runtime = project_state.runtime_of(state)

    def start(self):
        return steps.build_start(self.where, person_agreed=True)

    def build_copy(self, name='BUILD-1'):
        return self.runtime / 'candidates' / name

    def asides(self, name='BUILD-1'):
        return sorted((self.runtime / 'candidates').glob(f'{name}.left-*'))

    def test_a_leftover_copy_is_kept_aside_and_the_build_opens_beside_it(self):
        left = self.build_copy()
        left.mkdir(parents=True)
        (left / 'mine.py').write_text(UNIQUE)
        self.assertEqual(self.start()['status'], 'opened')
        aside = self.asides()
        self.assertEqual([(path / 'mine.py').read_text() for path in aside], [UNIQUE])
        self.assertTrue((self.build_copy() / '.git').is_dir())

    def test_leftovers_set_aside_again_and_again_overwrite_none(self):
        left = self.build_copy()
        for number in range(3):
            left.mkdir(parents=True)
            (left / 'mine.py').write_text(f'{number}\n')
            execute.set_aside(left)
        self.assertEqual(sorted((path / 'mine.py').read_text() for path in self.asides()), ['0\n', '1\n', '2\n'])

    def test_a_copy_of_a_batch_of_moves_left_behind_is_kept_too(self):
        grant = self.runtime / 'authorization.json'
        grant.write_text(json.dumps({'commit': git(self.project, 'rev-parse', 'HEAD')}))
        left = self.build_copy('MOVES-1')
        left.mkdir(parents=True)
        (left / 'mine.py').write_text(UNIQUE)
        execute.candidate(self.where, self.runtime, 'MOVES-1')
        self.assertEqual([(path / 'mine.py').read_text() for path in self.asides('MOVES-1')], [UNIQUE])

    def test_clean_judges_what_was_set_aside(self):
        kept, gone = self.build_copy(), self.build_copy('BUILD-2')
        for copy in (kept, gone):
            copy.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['git', 'clone', '-q', self.where, str(copy)], check=True, capture_output=True)
        (kept / 'mine.py').write_text(UNIQUE)
        execute.set_aside(kept)
        execute.set_aside(gone)
        said = io.StringIO()
        with contextlib.redirect_stdout(said): cli.main(['clean', '--lang', 'en'])
        self.assertIn(str(self.asides()[0]), said.getvalue())
        self.assertEqual(self.asides('BUILD-2'), [], 'it held nothing')

    def test_a_clean_waits_for_the_copy_and_its_record(self):
        real = steps._milestone_copy
        worker = Paused(self.start)
        def cloned(*args):
            root = real(*args)
            worker.at()()
            return root
        with mock.patch.object(steps, '_milestone_copy', cloned):
            worker.start()
            self.assertTrue(worker.reached.wait(SECONDS))
            def clean():
                with mock.patch('eaos.journeys.guided.commands.box'): cli.main(['clean', '--lang', 'en'])
            cleaning = threading.Thread(target=clean, daemon=True)
            cleaning.start()
            cleaning.join(1)
            self.assertTrue(self.build_copy().is_dir())
            outcome = worker.end()
            cleaning.join(SECONDS)
        self.assertEqual(outcome['result']['status'], 'opened')
        build = project_state.load(self.project)['open_build']
        self.assertTrue(Path(build['root']).is_dir(), 'a clean ran between the copy and its record')
        self.assertTrue(build['base'])

    def test_two_at_once_open_one_build(self):
        real = steps._milestone_copy
        worker = Paused(self.start)
        def cloned(*args):
            root = real(*args)
            worker.at()()
            return root
        with mock.patch.object(steps, '_milestone_copy', cloned):
            worker.start()
            self.assertTrue(worker.reached.wait(SECONDS))
            (self.build_copy() / 'first.py').write_text(UNIQUE)
            second = Paused(self.start).start()
            second.thread.join(1)
            first = worker.end()
            second.go.set()
            second.thread.join(SECONDS)
        self.assertEqual(first['result']['status'], 'opened')
        self.assertIn(second.outcome['result']['status'], ('open', 'busy'), second.outcome)
        self.assertEqual((self.build_copy() / 'first.py').read_text(), UNIQUE)
        self.assertEqual(self.asides(), [])

    def test_a_job_holds_it_with_nothing_copied(self):
        _job(self.project, 'audit')
        self.assertBusy(self.start())
        self.assertFalse(self.build_copy().exists())
        self.assertIsNone(project_state.load(self.project).get('open_build'))

    def test_the_report_is_published_after_the_lock_and_with_the_build_on_record(self):
        seen = []
        def published(state):
            jobs.folder(self.project).mkdir(parents=True, exist_ok=True)
            with open(jobs.folder(self.project) / '.turn.lock', 'a') as lock:
                try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB); seen.append('free')
                except OSError: seen.append('held')
            seen.append(bool(project_state.load(self.project).get('open_build')))
        with mock.patch.object(steps, 'publish', published):
            self.start()
        self.assertEqual(seen, ['free', True])


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
        record.write_text(json.dumps({**json.loads(record.read_text()), 'project': str(self.project.parent / 'elsewhere')}))
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
        for name, change in (('missing', mark.unlink), ('unreadable', lambda: mark.write_bytes(b'\xff\xfe')), ('empty', lambda: mark.write_text('')),
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
        fcntl.flock(lock, fcntl.LOCK_EX)                    # this project's lock held by another hand: the other goes on
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
        process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)', 'eaos.core.project.jobs', 'no-pid', self.where])
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


class AnEditCutShort(Work):
    """A stop or a kill leaves a change in the copy no record holds: the next edit starts from what is recorded."""

    def test_the_next_edit_is_not_checked_over_a_commit_left_by_a_stop(self):
        def stopped(*_):
            raise KeyboardInterrupt
        with mock.patch('eaos.journeys.fix.waves.edit_gates', stopped), self.assertRaises(KeyboardInterrupt):
            self.edit_job()
        self.assertEqual((self.copy / 'src/a.js').read_text().splitlines()[0], 'export const a = 2;', 'what the stop left')
        seen = []
        def gates(*_):
            seen.append((self.copy / 'src/a.js').read_text().splitlines()[0])
            return [], 0, None
        with mock.patch('eaos.journeys.fix.waves.edit_gates', gates):
            fixing._fix_edit_job(self.where, {'card': 'TASK-002', 'edits': [{'path': 'src/n.js', 'content': 'x\n'}], 'summary': ''}, lambda *_: None)
        self.assertEqual(seen, ['export const a = 1;'])
        self.assertEqual(list(self.wave()['kept']), ['TASK-002'])

    def test_a_kill_between_the_write_and_the_commit_leaves_nothing_behind(self):
        (self.copy / 'src/a.js').write_text('half written\n')
        (self.copy / 'src/new.js').write_text('half written\n')
        with mock.patch('eaos.journeys.fix.waves.edit_gates', return_value=([], 0, None)):
            self.assertTrue(self.edit_job()['kept'])
        self.assertFalse((self.copy / 'src/new.js').exists())

    def test_what_is_kept_stays_when_the_next_edit_starts(self):
        self.keep_one()
        kept = self.wave()['kept']['TASK-001']
        with mock.patch('eaos.journeys.fix.waves.edit_gates', return_value=([], 0, None)):
            self.assertTrue(fixing._fix_edit_job(self.where, {'card': 'TASK-002', 'edits': [{'path': 'src/n.js', 'content': 'x\n'}], 'summary': ''}, lambda *_: None)['kept'])
        self.assertTrue(git(self.copy, 'merge-base', '--is-ancestor', kept, 'HEAD') == '')
        self.assertTrue((self.copy / 'src/kept.js').is_file())


class SkippingDuringAJob(Work):
    def test_it_answers_busy_and_records_nothing(self):
        _job(self.project)
        with mock.patch.object(fixing, 'WAIT', 0):
            self.assertBusy(agent_tools.fix_skip('TASK-002', 'x', self.where))
        self.assertEqual(self.wave()['failed'], {})

    def test_with_no_job_it_skips(self):
        self.assertTrue(agent_tools.fix_skip('TASK-002', 'x', self.where)['skipped'])

    def test_a_stale_batch_is_still_refused_first(self):
        self.stale()
        _job(self.project)
        with mock.patch.object(fixing, 'WAIT', 0):
            self.assertEqual(agent_tools.fix_skip('TASK-002', 'x', self.where)['status'], 'stale_batch')


class ThroughTheStudio(Work):
    """A real Studio run of the real tool: its record says what happened."""

    def setUp(self):
        super().setUp()
        studio = Path(self.tmp.name) / 'studio'
        studio.mkdir()
        (studio / 'cards.json').write_text('{"cards": []}', encoding='utf-8')
        self.app = actions.Actions(self.project, port=8765, studio=studio, adapters={})
        self.app.manager.tools = functions
        self.addCleanup(self.app.close)

    def press(self, name):
        headers = {'X-EAOS-Token': self.app.token, 'X-EAOS-CSRF': self.app.csrf, 'Origin': 'http://127.0.0.1:8765', 'Host': '127.0.0.1:8765'}
        status, payload = self.app.handle('POST', '/api/runs', headers, {'action': name, 'inputs': {}})
        self.assertEqual(status, 200, payload)
        return self.app.wait(payload['run']['id'], ('done', 'failed', 'stopped'), SECONDS)

    def test_a_refused_close_ends_as_a_failed_run_saying_what_to_do_and_the_batch_stays(self):
        _job(self.project)
        run = self.press('fix_abandon')
        self.assertEqual(run['state'], 'failed', run)
        self.assertTrue(self.copy.is_dir())
        self.assertEqual(self.wave()['number'], 1)

    def test_with_nothing_running_it_closes_and_ends_done(self):
        run = self.press('fix_abandon')
        self.assertEqual(run['state'], 'done', run)
        self.assertFalse(self.copy.exists())


if __name__ == '__main__':
    unittest.main()
