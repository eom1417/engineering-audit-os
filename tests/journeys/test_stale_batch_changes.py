"""A batch that no longer fits takes no change. Reading leaves it open with its copy (test_safe_reads), so fix_edit,
fix_skip and fix_finish refuse it themselves, and the jobs they start look again before applying a change or handing it
over. A refusal removes nothing: fix_start and fix_abandon close it. A batch with kept changes goes on when the code
moves on."""
import contextlib
import subprocess
from pathlib import Path
from unittest import mock

from eaos.kernel.project import jobs, state as project_state
from eaos.doors.mcp_server.govern import every
from eaos.doors.mcp_server.server import build
from eaos.features.guided.interface import agent_tools
from eaos.features.guided import journey as guided
from eaos.features.guided.interface.agent_tools import fixing
from eaos.features.fix.journey import finish as batch_finish, lanes
from eaos.features.fix.journey.waves import batch as batch_steps, commit as eaos_commit, plan as read_plan
from tests.interfaces.test_read_only_tools import _called
from tests.journeys.test_continuity import Base, FIRST, git

EDIT = [{'path': 'src/a.js', 'find': 'export const a = 1;', 'replace': 'export const a = 2;'}]


class Batch(Base):
    def setUp(self):
        super().setUp()
        self.where = str(self.project)
        state = project_state.load(self.project)
        self.copy = project_state.runtime_of(state) / 'candidates' / 'WAVE-1'
        subprocess.run(['git', 'clone', '-q', self.where, str(self.copy)], check=True)
        self.cards = {c['id']: c for c in read_plan(guided.report_of(state))['tasks']}
        ids = ['TASK-001', 'TASK-002']
        state['open_wave'] = {'number': 1, 'root': str(self.copy),
                              'base': git(self.copy, 'rev-parse', 'HEAD'), 'cards': ids, 'kept': {}, 'failed': {},
                              'tools': {}, 'keys': {c: self.cards[c]['key'] for c in ids}}
        guided.save(state)

    def person_commits(self, name='moved.js'):
        (self.project / 'src' / name).write_text('export const moved = 1;\n')
        git(self.project, 'add', '-A')
        git(self.project, '-c', 'user.name=a', '-c', 'user.email=a@b', 'commit', '-qm', 'the person works')

    def keep_one(self):
        """TASK-001 kept in the copy, as an edit leaves it: a real commit, recorded on the batch."""
        (self.copy / 'src' / 'kept.js').write_text('// kept\n')
        kept = eaos_commit(self.copy, self.cards['TASK-001'])
        state = project_state.load(self.project)
        state['open_wave']['kept']['TASK-001'] = kept
        guided.save(state)

    def numbered_again(self):
        self.state = project_state.load(self.project)
        self.check([dict(c, id=f'TASK-{6 - i:03d}') for i, c in enumerate(FIRST, 1)])

    def everything(self):
        """Every file of the project's EAOS folder (the batch's copy in it), the copy's commit, and the state's own
        bytes."""
        record = Path(project_state.load(self.project)['workspace'])
        return {path.relative_to(record).as_posix(): path.read_bytes() for path in record.rglob('*')
                if path.is_file() and '.git' not in path.parts and path.suffix != '.lock'}, \
            git(self.copy, 'rev-parse', 'HEAD')

    def assertRefused(self, answer):
        self.assertEqual((answer.get('status'), answer.get('batch')), ('stale_batch', 1), f'it went on: {answer}')
        self.assertTrue(answer['why'])
        self.assertIn('fix_start', answer['what_now'])
        self.assertIn('fix_abandon', answer['what_now'])


class AStaleBatchIsRefused(Batch):
    def setUp(self):
        super().setUp()
        self.person_commits()
        guided.save(project_state.load(self.project))
        self.before = self.everything()

    def test_fix_edit_starts_no_job_and_changes_nothing(self):
        with mock.patch.object(jobs, 'start') as started:
            self.assertRefused(agent_tools.fix_edit('TASK-001', EDIT, 'a fix', self.where))
        started.assert_not_called()
        self.assertEqual(self.everything(), self.before)

    def test_fix_skip_changes_nothing(self):
        self.assertRefused(agent_tools.fix_skip('TASK-001', 'no safe change', self.where))
        self.assertEqual(self.everything(), self.before)

    def test_fix_finish_starts_no_job_and_changes_nothing(self):
        state = project_state.load(self.project)
        # nothing left to do, so only staleness stops it
        state['open_wave']['failed'] = {'TASK-001': 'skipped: x', 'TASK-002': 'skipped: y'}
        guided.save(state)
        before = self.everything()
        with mock.patch.object(jobs, 'start') as started:
            self.assertRefused(agent_tools.fix_finish(self.where))
        started.assert_not_called()
        self.assertEqual(self.everything(), before)

    def test_it_says_so_with_cards_still_left_too(self):
        self.assertRefused(agent_tools.fix_finish(self.where))

    def test_through_mcp_each_tool_refuses_it_and_only_the_journal_moves(self):
        server = build(every)
        calls = (('fix_edit', {'card': 'TASK-001', 'edits': EDIT}),
                 ('fix_skip', {'card': 'TASK-001', 'reason': 'x'}), ('fix_finish', {}))
        for name, arguments in calls:
            with self.subTest(tool=name):
                self.assertRefused(_called(server, name, project=self.where, **arguments))
                self.assertEqual(git(self.copy, 'rev-parse', 'HEAD'), self.before[1])
                state = project_state.load(self.project)
                self.assertEqual((state['open_wave']['kept'], state['open_wave']['failed'],
                                  state.get('waves') or []), ({}, {}, []))

    def test_after_a_refusal_fix_start_still_closes_it_as_superseded(self):
        agent_tools.fix_skip('TASK-001', 'no safe change', self.where)
        agent_tools.fix_start(self.where)
        state = project_state.load(self.project)
        self.assertEqual((state['waves'][-1]['status'], self.copy.exists()), ('superseded', False))

    def test_after_a_refusal_fix_abandon_still_closes_it(self):
        agent_tools.fix_edit('TASK-001', EDIT, 'a fix', self.where)
        agent_tools.fix_abandon(self.where)
        state = project_state.load(self.project)
        self.assertEqual((state['waves'][-1]['status'], self.copy.exists()), ('abandoned', False))


class WhatItsJobsSee(Batch):
    """The code moves on after the tool let the job start. A job is its own running job, so nothing but looking again
    sees it."""

    def setUp(self):
        super().setUp()
        inside = mock.patch.object(jobs, 'fixing', return_value=True)
        inside.start()
        self.addCleanup(inside.stop)

    def edit_job(self):
        return fixing._fix_edit_job(self.where, {'card': 'TASK-001', 'edits': EDIT, 'summary': 'a fix'},
                                    lambda *_: None)

    def test_an_edit_job_applies_nothing_once_the_code_moved_on(self):
        self.person_commits()
        guided.save(project_state.load(self.project))
        before = self.everything()
        with mock.patch('eaos.features.fix.journey.waves.edit_gates') as checked:
            self.assertRefused(self.edit_job())
        checked.assert_not_called()
        self.assertEqual(self.everything(), before)

    def test_an_edit_job_takes_its_change_back_when_the_code_moves_on_during_its_checks(self):
        head = git(self.copy, 'rev-parse', 'HEAD')
        def moved_meanwhile(*_):
            self.person_commits()
            return [], 0, None
        with mock.patch('eaos.features.fix.journey.waves.edit_gates', side_effect=moved_meanwhile):
            self.assertRefused(self.edit_job())
        wave = project_state.load(self.project)['open_wave']
        self.assertEqual((wave['kept'], git(self.copy, 'rev-parse', 'HEAD')), ({}, head),
                         'one kept change would let the stale batch go on')

    def test_fix_skip_records_nothing_when_the_code_moves_on_while_it_waits_its_turn(self):
        @contextlib.contextmanager
        def its_turn(*_):
            self.person_commits()
            yield
        with mock.patch.object(jobs, 'alone', its_turn):
            self.assertRefused(agent_tools.fix_skip('TASK-001', 'no safe change', self.where))
        self.assertEqual(project_state.load(self.project)['open_wave']['failed'], {})

    def test_a_finish_job_does_not_run_once_the_code_moved_on(self):
        self.person_commits()
        guided.save(project_state.load(self.project))
        before = self.everything()
        with mock.patch('eaos.features.fix.journey.waves.finish_batch') as finishing:
            self.assertRefused(batch_finish.finish_job(self.where, {}, lambda *_: None))
        finishing.assert_not_called()
        self.assertEqual(self.everything(), before)

    def test_a_finish_job_writes_and_hands_over_nothing_when_the_cards_are_numbered_again_meanwhile(self):
        self.keep_one()
        head = git(self.copy, 'rev-parse', 'HEAD')
        runtime = project_state.runtime_of(project_state.load(self.project))
        def through_the_gates(batch, kept, failed):
            (self.copy / 'src' / 'rewritten.js').write_text('// rewritten\n')
            git(self.copy, 'add', '-A')
            git(self.copy, '-c', 'user.name=a', '-c', 'user.email=a@b', 'commit', '-qm', 'the batch rewritten')
            self.numbered_again()
            return kept
        the_checks = {name: mock.patch.object(batch_steps, name, side_effect=lambda batch, kept, *_: kept)
                      for name in ('_accepted', '_secure')}
        for patcher in the_checks.values():
            patcher.start()
            self.addCleanup(patcher.stop)
        with mock.patch.object(batch_steps, '_through_gates', side_effect=through_the_gates), \
                mock.patch.object(batch_steps, '_declare'), \
                mock.patch.object(batch_steps, '_new_truth'), \
                mock.patch('eaos.features.fix.journey.regenerate.regenerate'), \
                mock.patch('eaos.features.fix.journey.regenerate.keep_guide'), \
                mock.patch('eaos.features.fix.journey.waves.apply') as handing:
            self.assertRefused(batch_finish.finish_job(self.where, {}, lambda *_: None))
        handing.assert_not_called()
        state = project_state.load(self.project)
        self.assertEqual((git(self.copy, 'rev-parse', 'HEAD'), state.get('waves') or [],
                          state['open_wave']['number'], self.branches()), (head, [], 1, []))
        self.assertFalse((runtime / 'waves' / 'wave-1').exists(),
                         'no patches of a batch never handed over: a later batch would read them')
        self.assertNotIn('phases', state['open_wave'], 'the live map shows no hand-over that never came')


class WithSeveralAssistants(Batch):
    """Another lane's job running is the normal state of such a batch: it must not hide that the batch no longer fits.
    """

    def setUp(self):
        super().setUp()
        state = project_state.load(self.project)
        state['open_wave'].update(lanes=[['TASK-001'], ['TASK-002']], claims={'src/a.js': 0}, helpers={},
                                  later=[], released=[])
        guided.save(state)
        self.person_commits()
        guided.save(project_state.load(self.project))
        self.before = self.everything()

    def test_fix_edit_refuses_it_before_it_holds_any_file(self):
        with mock.patch.object(jobs, 'fixing', return_value=True):
            self.assertRefused(agent_tools.fix_edit('TASK-001', EDIT, 'a fix', self.where))
        self.assertEqual(self.everything(), self.before)

    def test_fix_finish_refuses_it_and_never_asks_to_wait_for_the_others(self):
        with mock.patch.object(lanes, 'WAIT', 0):
            self.assertRefused(agent_tools.fix_finish(self.where))
        self.assertEqual(self.everything(), self.before)

    def test_fix_skip_refuses_it_at_once_while_a_job_runs(self):
        with mock.patch.object(jobs, 'running', return_value={'id': 'j', 'kind': 'fix_edit', 'progress': None}), \
                mock.patch.object(fixing, 'WAIT', 0):
            self.assertRefused(agent_tools.fix_skip('TASK-002', 'x', self.where))
        self.assertEqual(self.everything(), self.before)

    def test_a_helper_is_told_it_closes_nothing(self):
        self.assertIn('helper', agent_tools.fix_skip('TASK-002', 'x', self.where)['what_now'])


class WhatStillWorks(Batch):
    def test_a_batch_that_fits_keeps_an_edit(self):
        with mock.patch('eaos.features.fix.journey.waves.edit_gates', return_value=([], 0, None)), \
                mock.patch.object(jobs, 'fixing', return_value=True):
            answer = fixing._fix_edit_job(self.where, {'card': 'TASK-001', 'edits': EDIT, 'summary': 'a fix'},
                                          lambda *_: None)
        self.assertTrue(answer['kept'])

    def test_a_batch_that_fits_takes_a_skip(self):
        self.assertEqual(agent_tools.fix_skip('TASK-002', 'needs a decision', self.where)['skipped'], True)

    def test_a_batch_that_fits_finishes(self):
        for card_id in ('TASK-001', 'TASK-002'): agent_tools.fix_skip(card_id, 'needs a decision', self.where)
        with mock.patch.object(fixing, '_start', return_value={'job': 'j'}) as started:
            self.assertEqual(agent_tools.fix_finish(self.where), {'job': 'j'})
        started.assert_called_once()

    def test_a_batch_with_a_kept_change_numbered_again_is_stale_as_before(self):
        self.keep_one()
        self.numbered_again()
        self.assertRefused(agent_tools.fix_skip('TASK-002', 'no safe change', self.where))

    def test_a_batch_with_a_kept_change_goes_on_when_the_code_moved_on(self):
        self.keep_one()
        self.person_commits()
        with mock.patch.object(fixing, '_start', return_value={'job': 'j'}) as started:
            self.assertEqual(agent_tools.fix_edit('TASK-002', EDIT, 'a fix', self.where), {'job': 'j'})
            self.assertEqual(agent_tools.fix_skip('TASK-002', 'no safe change', self.where)['skipped'], True)
            self.assertEqual(agent_tools.fix_finish(self.where), {'job': 'j'})
        self.assertEqual(started.call_count, 2)
        with mock.patch('eaos.features.fix.journey.waves.edit_gates', return_value=([], 0, None)), \
                mock.patch.object(jobs, 'fixing', return_value=True):
            state = project_state.load(self.project)
            state['open_wave']['failed'] = {}
            guided.save(state)
            self.assertTrue(fixing._fix_edit_job(self.where, {'card': 'TASK-002', 'edits': EDIT, 'summary': 'a fix'},
                                                 lambda *_: None)['kept'])
