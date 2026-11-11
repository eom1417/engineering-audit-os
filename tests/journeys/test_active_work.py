"""What a job is doing is not taken from under it: abandoning a batch, a cut-short edit, skipping, and the run
engine, all under the lock jobs start by, on real repositories with real threads and processes."""
import contextlib
import threading
import time
import unittest
from pathlib import Path
from unittest import mock
from eaos.core.project import jobs, state as project_state
from eaos.interfaces import runs as actions
from eaos.interfaces.mcp_server.server import functions
from eaos.journeys import agent_tools, guided
from eaos.journeys.agent_tools import fixing
from eaos.journeys.fix import finish as batch_finish, lanes
from eaos.journeys.fix.waves import batch as batch_steps
from tests.journeys.test_continuity import git
from tests.journeys.test_stale_batch_changes import EDIT
from tests.journeys._active_work_fixture import Paused, SECONDS, Work, _job


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
        patches = [mock.patch.object(batch_steps, '_accepted', side_effect=lambda b, cards, kept, *_: kept),
                   mock.patch.object(batch_steps, '_secure', side_effect=lambda b, kept, *_: kept),
                   mock.patch.object(batch_steps, '_through_gates', side_effect=lambda b, kept, *_: worker.at(kept)()),
                   mock.patch.object(batch_steps, '_declare'), mock.patch.object(batch_steps, '_new_truth'),
                   mock.patch('eaos.journeys.fix.regenerate.regenerate'),
                   mock.patch('eaos.journeys.fix.regenerate.keep_guide')]
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
        self.assertEqual((state.get('open_wave'), self.closed()), (None, ['abandoned']),
                         'an older save came back over the closing')

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
            # the other came first and ended; else it was still at it: busy
            except LookupError: answers.append('none open')
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


class AnEditCutShort(Work):
    """A stop or a kill leaves a change in the copy no record holds: the next edit starts from what is recorded."""

    def test_the_next_edit_is_not_checked_over_a_commit_left_by_a_stop(self):
        def stopped(*_):
            raise KeyboardInterrupt
        with mock.patch('eaos.journeys.fix.waves.edit_gates', stopped), self.assertRaises(KeyboardInterrupt):
            self.edit_job()
        self.assertEqual((self.copy / 'src/a.js').read_text().splitlines()[0], 'export const a = 2;',
                         'what the stop left')
        seen = []
        def gates(*_):
            seen.append((self.copy / 'src/a.js').read_text().splitlines()[0])
            return [], 0, None
        with mock.patch('eaos.journeys.fix.waves.edit_gates', gates):
            fixing._fix_edit_job(self.where,
                                 {'card': 'TASK-002', 'edits': [{'path': 'src/n.js', 'content': 'x\n'}], 'summary': '',
                                  'beyond_why': 'a file beside the card, on purpose'}, lambda *_: None)
        self.assertEqual(seen, ['export const a = 1;'])
        self.assertEqual(list(self.wave()['kept']), ['TASK-002'])

    def test_a_kill_between_the_write_and_the_commit_leaves_nothing_behind(self):
        (self.copy / 'src/a.js').write_text('half written\n')
        (self.copy / 'src/new.js').write_text('half written\n')
        with mock.patch('eaos.journeys.fix.waves.edit_gates', return_value=([], 0, None)):
            self.assertTrue(self.edit_job()['kept'])
        self.assertFalse((self.copy / 'src/new.js').exists())

    def test_kept_changes_a_killed_hand_over_rewrote_are_not_thrown_away(self):
        self.keep_one()
        git(self.copy, '-c', 'user.name=a', '-c', 'user.email=a@b', 'commit', '-q', '--amend', '-m',
            'rebuilt by the hand-over')
        with mock.patch('eaos.journeys.fix.waves.edit_gates', return_value=([], 0, None)):
            fixing._fix_edit_job(self.where,
                                 {'card': 'TASK-002', 'edits': [{'path': 'src/n.js', 'content': 'x\n'}], 'summary': '',
                                  'beyond_why': 'a file beside the card, on purpose'}, lambda *_: None)
        self.assertTrue((self.copy / 'src/kept.js').is_file(), 'nothing says what it may drop: it drops nothing')

    def test_what_is_kept_stays_when_the_next_edit_starts(self):
        self.keep_one()
        kept = self.wave()['kept']['TASK-001']
        with mock.patch('eaos.journeys.fix.waves.edit_gates', return_value=([], 0, None)):
            self.assertTrue(fixing._fix_edit_job(self.where,
                                                 {'card': 'TASK-002', 'edits': [{'path': 'src/n.js', 'content': 'x\n'}],
                                                  'summary': '', 'beyond_why': 'a file beside the card, on purpose'},
                                                 lambda *_: None)['kept'])
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


class ThroughTheRunEngine(Work):
    """A real run of the real tool: its record says what happened."""

    def setUp(self):
        super().setUp()
        studio = Path(self.tmp.name) / 'studio'
        studio.mkdir()
        (studio / 'cards.json').write_text('{"cards": []}', encoding='utf-8')
        self.app = actions.Actions(self.project, port=8765, studio=studio, adapters={})
        self.app.manager.tools = functions
        self.addCleanup(self.app.close)

    def press(self, name):
        headers = {'X-EAOS-Token': self.app.token, 'X-EAOS-CSRF': self.app.csrf, 'Origin': 'http://127.0.0.1:8765',
                   'Host': '127.0.0.1:8765'}
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
