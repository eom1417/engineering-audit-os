"""A read that rebuilds the report holds no old state over what a worker wrote meanwhile: open_report, opening the
Studio, and status, menu and plan when reconciling changes something. Real repositories; the worker runs in its own
thread while the read is rebuilding the report."""
import threading
from unittest import mock

from eaos.core.project import state as project_state
from eaos.interfaces.mcp_server.server import functions
from eaos.interfaces.studio_server import server as studio_server
from eaos.journeys import agent_tools, check as check_journey, guided
from eaos.journeys.agent_tools import fixing
from eaos.journeys.fix import finish as batch_finish, lanes
from eaos.journeys.fix.waves import batch as batch_steps
from eaos.journeys.guided import batches
from tests.journeys.test_continuity import git
from tests.journeys.test_stale_batch_changes import Batch, EDIT

SECONDS = 20


class Interleaved(Batch):
    def during_the_report(self, write):
        """The first rebuild of the report lets `write` run to its end in a thread of its own, as another process would.
        """
        real, done = guided.project.publish, []
        def publish(state, *args, **options):
            if not done:
                done.append(True)
                outcome = {}
                def run():
                    try: outcome['result'] = write()
                    except BaseException as problem: outcome['raised'] = problem
                thread = threading.Thread(target=run, daemon=True)
                thread.start()
                thread.join(SECONDS)
                self.assertFalse(thread.is_alive(), 'the worker waited on the reader: a lock held through the report')
                self.assertNotIn('raised', outcome, outcome)
            return real(state, *args, **options)
        patches = [mock.patch.object(guided, 'publish', publish), mock.patch.object(batches, 'publish', publish)]
        return patches

    def run_read(self, read, write):
        patches = self.during_the_report(write)
        for patch in patches: patch.start()
        try: read()
        finally:
            for patch in patches: patch.stop()

    def keep(self):
        with mock.patch('eaos.journeys.fix.waves.edit_gates', return_value=([], 0, None)):
            self.assertTrue(fixing._fix_edit_job(self.where, {'card': 'TASK-001', 'edits': EDIT, 'summary': ''}, lambda *_: None)['kept'])

    def hand_over(self):
        self.keep()
        state = project_state.load(self.project)
        state['open_wave']['failed']['TASK-002'] = 'skipped: x'
        guided.save(state)
        patches = [mock.patch.object(batch_steps, '_accepted', side_effect=lambda b, cards, kept, *_: kept), mock.patch.object(batch_steps, '_secure', side_effect=lambda b, kept, *_: kept),
                   mock.patch.object(batch_steps, '_through_gates', side_effect=lambda b, kept, *_: kept), mock.patch.object(batch_steps, '_declare'), mock.patch.object(batch_steps, '_new_truth'),
                   mock.patch('eaos.journeys.fix.regenerate.regenerate'), mock.patch('eaos.journeys.fix.regenerate.keep_guide')]
        for patch in patches: patch.start()
        try: batch_finish.finish_job(self.where, {}, lambda *_: None)
        finally:
            for patch in patches: patch.stop()

    def merged_earlier_batch(self):
        """An earlier batch taken in by hand: EAOS's own commits, so the open batch still fits, and reconciling has work
        to do."""
        self.batch(9, ['TASK-004'])
        git(self.project, 'merge', '-q', '--ff-only', 'eaos/wave-9')

    def on_disk(self):
        return project_state.load(self.project)

    def assertKept(self):
        self.assertEqual(list(self.on_disk()['open_wave']['kept']), ['TASK-001'])

    def assertHandedOver(self):
        state = self.on_disk()
        self.assertIsNone(state.get('open_wave'), 'a batch handed over came back open')
        self.assertIn('applied', [wave['status'] for wave in state['waves']])
        self.assertFalse(self.copy.exists())

    def assertAbandoned(self):
        state = self.on_disk()
        self.assertIsNone(state.get('open_wave'), 'a batch closed came back open')
        self.assertIn('abandoned', [wave['status'] for wave in state['waves']])


class OpenReportAndTheStudio(Interleaved):
    def readers(self):
        return (('open_report', lambda: agent_tools.open_report(self.where, show=False)), ('opening the Studio', lambda: studio_server.prepare(self.where)))

    def test_a_change_kept_meanwhile_stays_recorded(self):
        read = dict(self.readers())
        self.run_read(read['open_report'], self.keep)
        self.assertKept()

    def test_a_change_kept_meanwhile_stays_recorded_opening_the_studio(self):
        self.run_read(dict(self.readers())['opening the Studio'], self.keep)
        self.assertKept()

    def test_a_hand_over_meanwhile_stays(self):
        self.run_read(dict(self.readers())['open_report'], self.hand_over)
        self.assertHandedOver()

    def test_a_hand_over_meanwhile_stays_opening_the_studio(self):
        self.run_read(dict(self.readers())['opening the Studio'], self.hand_over)
        self.assertHandedOver()

    def test_an_abandonment_meanwhile_stays(self):
        self.run_read(dict(self.readers())['open_report'], lambda: agent_tools.fix_abandon(self.where))
        self.assertAbandoned()

    def test_a_state_broken_or_gone_meanwhile_is_not_written_over_with_the_earlier_one(self):
        record = project_state.workspace(self.project) / 'state.json'
        for name, change, left in (('broken', lambda: record.write_text('{ not json'), '{ not json'), ('not a state', lambda: record.write_text('{}'), '{}'), ('gone', record.unlink, None)):
            with self.subTest(state=name):
                good = record.read_text()
                with self.assertRaises(LookupError):
                    self.run_read(dict(self.readers())['open_report'], change)
                self.assertEqual(record.read_text() if record.exists() else None, left)
                record.write_text(good)

    def test_it_still_saves_and_opens_with_nothing_else_going_on(self):
        answer = agent_tools.open_report(self.where, show=False)
        self.assertTrue(answer['report_for_people'])
        self.assertEqual(self.on_disk()['open_wave']['number'], 1)


class ReadsThatReconcile(Interleaved):
    def reads(self):
        tools = functions()
        return [(name, lambda name=name: tools[name](project=self.where)) for name in ('status', 'menu', 'plan')]

    def test_a_change_kept_meanwhile_stays_and_the_merge_is_recorded(self):
        self.merged_earlier_batch()
        self.run_read(self.reads()[0][1], self.keep)
        self.assertKept()
        self.assertEqual(self.on_disk()['waves'][-1]['status'], 'accepted')
        self.assertEqual(self.branches(), ['eaos/wave-9'], 'a read removes no branch')

    def test_menu_keeps_it_too(self):
        self.merged_earlier_batch()
        self.run_read(self.reads()[1][1], self.keep)
        self.assertKept()

    def test_plan_keeps_it_too(self):
        self.merged_earlier_batch()
        self.run_read(self.reads()[2][1], self.keep)
        self.assertKept()

    def test_a_hand_over_meanwhile_stays(self):
        self.merged_earlier_batch()
        self.run_read(self.reads()[0][1], self.hand_over)
        self.assertHandedOver()

    def test_an_abandonment_meanwhile_stays(self):
        self.merged_earlier_batch()
        self.run_read(self.reads()[0][1], lambda: agent_tools.fix_abandon(self.where))
        self.assertAbandoned()

    def test_a_read_with_nothing_to_settle_writes_nothing(self):
        self.reads()[0][1]()                    # its first call settles the branch
        record = self.on_disk()['workspace'] + '/state.json'
        before = open(record, 'rb').read()
        self.reads()[0][1]()
        self.assertEqual(open(record, 'rb').read(), before)


class TheLocks(Interleaved):
    def test_the_report_is_rebuilt_with_the_state_lock_free(self):
        self.merged_earlier_batch()
        taken = []
        def write():
            with lanes.changing(self.where): taken.append(True)
        self.run_read(self.reads_status(), write)
        self.assertEqual(taken, [True])

    def reads_status(self):
        return lambda: agent_tools.status(self.where)

    def test_starting_a_batch_reconciles_without_waiting_on_itself(self):
        self.merged_earlier_batch()
        done = []
        def start():
            with mock.patch.object(fixing, '_start', return_value={'job': 'j'}): done.append(agent_tools.fix_start(self.where))
        thread = threading.Thread(target=start, daemon=True)
        thread.start()
        thread.join(SECONDS)
        self.assertFalse(thread.is_alive(), 'fix_start deadlocked on the state lock')
        self.assertEqual(self.on_disk()['waves'][-1]['status'], 'accepted')

    def test_a_write_of_the_lanes_on_a_state_that_does_not_read_leaves_it_as_it_is(self):
        record = project_state.workspace(self.project) / 'state.json'
        record.write_text('{ not json')
        with self.assertRaises(LookupError):
            with lanes.changing(self.where): pass
        self.assertEqual(record.read_text(), '{ not json')


class ACheckThatClosesABatch(Interleaved):
    def test_it_keeps_what_it_stamped(self):
        self.person_commits()
        head = git(self.project, 'rev-parse', 'HEAD')
        with mock.patch('eaos.journeys.check.check', return_value={}), mock.patch('eaos.journeys.check.remedies.apply', return_value={}), mock.patch('eaos.journeys.check.source', return_value=self.project):
            check_journey.run(project_state.load(self.project), {})
        state = self.on_disk()
        self.assertEqual((state['scanned_commit'], state.get('open_wave'), state['waves'][-1]['status']), (head, None, 'superseded'))
