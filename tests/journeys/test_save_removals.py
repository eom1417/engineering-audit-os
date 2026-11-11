"""A save removes only what it closes. A read that saves (its reconciling, its first settling of the branch) finds a
batch's leftovers and leaves them: a copy may hold the only trace of a change. Closing a batch still removes its copy
and logs, and the patches past the ones kept, and only once the state that says it closed is written."""
import shutil
from pathlib import Path
from unittest import mock

from eaos.kernel.project import state as project_state
from eaos.doors.mcp_server.govern import every
from eaos.doors.mcp_server.server import build
from eaos.features.guided.interface import agent_tools
from eaos.features.guided import journey as guided
from eaos.features.fix.journey import finish as batch_finish
from eaos.features.fix.journey.waves import batch as batch_steps
from tests.interfaces.test_read_only_tools import _called
from tests.journeys.test_continuity import git
from tests.journeys.test_stale_batch_changes import Batch as OpenBatch

UNIQUE = 'written nowhere else\n'
READS = ('status', 'menu', 'plan')


def _tree(root):
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in Path(root).rglob('*')
            if path.is_file() and '.git' not in path.parts}


class Leftovers(OpenBatch):
    """The project's open batch closed by a real fix_abandon, leftovers of earlier closed batches beside it."""

    def setUp(self):
        super().setUp()
        self.runtime = project_state.runtime_of(project_state.load(self.project))

    def leftovers(self, numbers=(1, 2, 3, 4)):
        """Closed batches as a removal that failed leaves them. Written whole, so no save judged them."""
        state = project_state.load(self.project)
        state.pop('open_wave', None)
        # settled: a read has no reason to save
        state['branch'] = state['home_branch'] = git(self.project, 'rev-parse', '--abbrev-ref', 'HEAD')
        self.assertEqual(project_state.runtime_of(state), self.runtime, 'the leftovers are where a save would look')
        for number in numbers:
            (self.runtime / 'candidates' / f'WAVE-{number}').mkdir(parents=True, exist_ok=True)
            (self.runtime / 'candidates' / f'WAVE-{number}' / 'only-here.py').write_text(UNIQUE)
            (self.runtime / 'waves' / f'wave-{number}').mkdir(parents=True, exist_ok=True)
            (self.runtime / 'waves' / f'wave-{number}' / '0001-fix.patch').write_text(UNIQUE)
            (self.runtime / 'runtime').mkdir(exist_ok=True)
            (self.runtime / 'runtime' / f'checks-wave-{number}-bisect-ab12-1-log.json').write_text(UNIQUE)
            state.setdefault('waves', []).append({'number': number, 'status': 'abandoned', 'cards': [],
                                                  'kept': {}, 'failed': {}})
        project_state.write(state)
        return self.kept()

    def kept(self):
        return {name: data for name, data in _tree(self.runtime).items()
                if name.startswith(('candidates/', 'waves/')) or '-bisect-' in name}

    def read(self, name):
        return _called(build(every), name, project=str(self.project))

    def merged_by_hand(self, number=5):
        branch = f'eaos/main/wave-{number}'
        git(self.project, 'checkout', '-qb', branch)
        self.person_commits('fixed.js')
        tip = git(self.project, 'rev-parse', 'HEAD')
        git(self.project, 'checkout', '-q', '-')
        state = project_state.load(self.project)
        state['waves'].append({'number': number, 'branch': branch, 'status': 'applied', 'tip': tip,
                               'merge_into': git(self.project, 'rev-parse', '--abbrev-ref', 'HEAD'),
                               'cards': [], 'kept': {}})
        project_state.write(state)
        git(self.project, '-c', 'user.name=a', '-c', 'user.email=a@b', 'merge', '-q', '--no-ff', '-m', 'by hand',
            branch)


class AReadLeavesThem(Leftovers):
    def test_on_a_stable_project_however_often_it_reads(self):
        before = self.leftovers()
        for name in READS * 2:
            with self.subTest(read=name):
                self.read(name)
                self.assertEqual(self.kept(), before)

    def test_when_its_reconciling_saves_the_state(self):
        before = self.leftovers()
        self.merged_by_hand()
        for name in READS * 2:
            with self.subTest(read=name):
                self.read(name)
                self.assertEqual(project_state.load(self.project)['waves'][-1]['status'], 'accepted')
                self.assertEqual(self.kept(), before)

    def test_when_its_first_call_settles_the_branch(self):
        for name in ('status', 'menu'):
            with self.subTest(read=name):
                before = self.leftovers((1, 2, 3, 4) if name == 'status' else ())
                state = project_state.load(self.project)
                state.pop('branch', None)
                state.pop('home_branch', None)
                project_state.write(state)
                self.read(name)
                self.assertTrue(project_state.load(self.project)['branch'], 'the read did save')
                self.assertEqual(self.kept(), before)

    def test_when_it_rebuilds_a_report_an_older_eaos_made(self):
        before = self.leftovers()
        with mock.patch('eaos.features.guided.interface.agent_tools.where.tool_digest', return_value='another'), \
                mock.patch('eaos.features.guided.interface.agent_tools.project.tool_digest', return_value='another'):
            self.read('status')
        self.assertEqual(self.kept(), before)

    def test_when_it_saves_a_state_older_than_the_one_on_disk(self):
        before = self.leftovers()
        stale = project_state.load(self.project)
        stale.pop('branch')                                     # read before the branch was settled
        guided.save(stale)
        self.assertEqual(self.kept(), before)

    def test_when_its_state_holds_a_closed_batch_the_disk_lost(self):
        before = self.leftovers()
        state = project_state.load(self.project)
        on_disk = dict(state, waves=state['waves'][:-1])        # another writer's older state won
        project_state.write(on_disk)
        guided.save(state)
        self.assertEqual(self.kept(), before)

    def test_when_what_is_on_disk_is_not_a_state(self):
        for found in ('{}', '[]'):
            with self.subTest(found=found):
                before = self.leftovers((1, 2, 3, 4))
                state = project_state.load(self.project)
                state['waves'][-1]['kind'] = 'moves'
                (Path(state['workspace']) / 'state.json').write_text(found)
                guided.save(state)
                self.assertEqual(self.kept(), before)
                state['waves'] = []
                project_state.write(state)


class AnOpenBatch(OpenBatch):
    def test_keeps_its_copy_when_a_closed_batch_on_disk_has_its_number(self):
        (self.copy / 'only-here.js').write_text(UNIQUE)
        state = project_state.load(self.project)
        state['waves'] = [{'number': 1, 'status': 'abandoned', 'cards': [], 'kept': {}, 'failed': {}}]
        project_state.write(state)
        guided.save(state)
        self.assertEqual((self.copy / 'only-here.js').read_text(), UNIQUE)

    def test_stays_untouched_through_saves_and_reads_beside_a_closed_one(self):
        state = project_state.load(self.project)
        state['open_wave']['number'] = 2
        state['waves'] = [{'number': 1, 'status': 'abandoned', 'cards': [], 'kept': {}, 'failed': {}}]
        copy2 = self.copy.parent / 'WAVE-2'
        self.copy.rename(copy2)
        state['open_wave']['root'] = str(copy2)
        project_state.write(state)
        (copy2 / 'work-in-progress.js').write_text(UNIQUE)
        before = _tree(copy2)
        for _ in range(3): guided.save(project_state.load(self.project))
        agent_tools.status(self.where)
        self.assertEqual(_tree(copy2), before)


class ClosingABatch(Leftovers):
    def test_abandoning_removes_its_copy_and_its_bisection_logs_and_nothing_older(self):
        self.leftovers((2, 3))                  # what earlier batches left; the one that closes is number 4
        state = project_state.load(self.project)
        state['open_wave'] = {'number': 4, 'root': str(self.runtime / 'candidates' / 'WAVE-4'),
                              'base': git(self.project, 'rev-parse', 'HEAD'),
                              'cards': ['TASK-001'], 'kept': {}, 'failed': {}, 'tools': {}}
        project_state.write(state)
        (self.runtime / 'candidates' / 'WAVE-4').mkdir()
        (self.runtime / 'runtime' / 'checks-wave-4-bisect-ab12-1-log.json').write_text('{}')
        agent_tools.fix_abandon(self.where)
        self.assertFalse((self.runtime / 'candidates' / 'WAVE-4').exists())
        self.assertFalse((self.runtime / 'runtime' / 'checks-wave-4-bisect-ab12-1-log.json').exists())
        self.assertEqual((self.runtime / 'candidates' / 'WAVE-2' / 'only-here.py').read_text(), UNIQUE)
        self.assertEqual((self.runtime / 'candidates' / 'WAVE-3' / 'only-here.py').read_text(), UNIQUE)

    def test_a_real_hand_over_removes_its_copy_keeps_its_patches_and_delivers_its_branch(self):
        self.keep_one()
        log = self.runtime / 'runtime' / 'checks-wave-1-bisect-ab12-1-log.json'
        log.parent.mkdir(exist_ok=True)
        log.write_text('{}')
        steps = [mock.patch.object(batch_steps, name, side_effect=lambda batch, kept, *_: kept)
                 for name in ('_accepted', '_secure', '_through_gates')]
        steps += [mock.patch.object(batch_steps, '_declare'), mock.patch.object(batch_steps, '_new_truth'),
                  mock.patch('eaos.features.fix.journey.regenerate.regenerate'),
                  mock.patch('eaos.features.fix.journey.regenerate.keep_guide')]
        for step in steps:
            step.start()
            self.addCleanup(step.stop)
        batch_finish.finish_job(self.where, {}, lambda *_: None)
        self.assertFalse(self.copy.exists())
        self.assertFalse(log.exists())
        self.assertTrue(list((self.runtime / 'waves' / 'wave-1').glob('*.patch')))
        wave = project_state.load(self.project)['waves'][-1]
        self.assertEqual((wave['status'], wave['branch'] in git(self.project, 'branch', '--list', wave['branch'])),
                         ('applied', True))

    def test_keeps_only_the_last_patches_over_many_closures_with_no_copy_or_log_left(self):
        state = project_state.load(self.project)
        state.pop('open_wave')
        project_state.write(state)
        shutil.rmtree(self.copy)
        for number in range(1, 6):
            state = project_state.load(self.project)
            copy = self.runtime / 'candidates' / f'WAVE-{number}'
            copy.mkdir(parents=True)
            (self.runtime / 'waves' / f'wave-{number}').mkdir(parents=True)
            (self.runtime / 'runtime').mkdir(exist_ok=True)
            (self.runtime / 'runtime' / f'checks-wave-{number}-bisect-ab12-1-log.json').write_text('{}')
            state['open_wave'] = {'number': number, 'root': str(copy),
                                  'base': git(self.project, 'rev-parse', 'HEAD'), 'cards': ['TASK-001'],
                                  'kept': {}, 'failed': {}, 'tools': {}}
            guided.save(state)
            agent_tools.fix_abandon(self.where)
        self.assertEqual(sorted(p.name for p in (self.runtime / 'candidates').iterdir()), [])
        self.assertEqual(sorted(p.name for p in (self.runtime / 'waves').iterdir()), ['wave-4', 'wave-5'])
        self.assertEqual(list((self.runtime / 'runtime').glob('checks-wave-*-bisect-*')), [])


class ClosingOtherKinds(Leftovers):
    def test_a_closing_takes_past_the_kept_patches_only_the_one_it_puts_there(self):
        self.leftovers()
        state = project_state.load(self.project)
        state['open_wave'] = {'number': 5, 'root': str(self.runtime / 'candidates' / 'WAVE-5'),
                              'cards': [], 'kept': {}, 'failed': {}, 'tools': {}}
        project_state.write(state)
        guided.close_batch(state, 'abandoned', 'x')
        self.assertEqual(sorted(p.name for p in (self.runtime / 'waves').iterdir()),
                         ['wave-1', 'wave-2', 'wave-4'], 'wave-3 is what it put past')

    def test_a_save_does_not_take_an_old_batch_of_moves_for_a_new_one(self):
        before = self.leftovers((1, 2, 3))
        state = project_state.load(self.project)
        state['waves'][0]['kind'] = 'moves'
        project_state.write(state)
        guided.save(project_state.load(self.project))
        self.assertEqual(self.kept(), before)

    def test_a_build_removes_its_copy_and_leaves_a_fix_batch_of_its_number(self):
        before = self.leftovers((3,))
        state = project_state.load(self.project)
        state['open_build'] = {'number': 3, 'milestone': 'M01'}
        project_state.write(state)
        (self.runtime / 'candidates' / 'BUILD-3').mkdir()
        state.pop('open_build')
        state['waves'].append({'number': 3, 'via': 'build', 'status': 'applied', 'cards': [], 'kept': {}})
        guided.save(state)
        self.assertFalse((self.runtime / 'candidates' / 'BUILD-3').exists())
        self.assertEqual(self.kept(), before)

    def test_a_batch_of_moves_is_no_closing_and_takes_the_place_of_no_patches(self):
        before = self.leftovers((1, 2))
        state = project_state.load(self.project)
        state['waves'].append({'number': 3, 'kind': 'moves', 'status': 'applied', 'cards': [], 'kept': []})
        guided.save(state)
        self.assertEqual(self.kept(), before)

    def test_the_patches_kept_are_of_the_last_two_fix_batches_whatever_came_between(self):
        self.leftovers((1, 2))
        state = project_state.load(self.project)
        state['waves'].append({'number': 3, 'kind': 'moves', 'status': 'applied', 'cards': [], 'kept': []})
        state['open_wave'] = {'number': 4, 'root': str(self.runtime / 'candidates' / 'WAVE-4'),
                              'cards': [], 'kept': {}, 'failed': {}, 'tools': {}}
        project_state.write(state)
        guided.close_batch(state, 'abandoned', 'x')
        self.assertEqual(sorted(p.name for p in (self.runtime / 'waves').iterdir()), ['wave-2'],
                         'wave-1 is past the last two: 2 and 4')

    def test_a_log_that_cannot_be_removed_does_not_fail_a_closing_already_written(self):
        self.leftovers((1,))
        state = project_state.load(self.project)
        copy = self.runtime / 'candidates' / 'WAVE-2'
        copy.mkdir()
        log = self.runtime / 'runtime' / 'checks-wave-2-bisect-ab12-1-log.json'
        log.write_text('{}')
        state['open_wave'] = {'number': 2, 'root': str(copy), 'cards': [], 'kept': {}, 'failed': {}, 'tools': {}}
        project_state.write(state)
        unlink = Path.unlink
        def held(path, *args, **options):
            if path == log: raise PermissionError('held')
            return unlink(path, *args, **options)
        with mock.patch.object(Path, 'unlink', held):
            guided.close_batch(state, 'abandoned', 'x')
        self.assertEqual((project_state.load(self.project)['waves'][-1]['number'], copy.exists()), (2, False))


class WhenTheStateCannotBeWritten(OpenBatch):
    def test_a_batch_still_open_on_disk_keeps_its_only_copy(self):
        (self.copy / 'only-here.js').write_text(UNIQUE)
        with mock.patch.object(project_state, 'write', side_effect=OSError('no space left')), \
                self.assertRaises(OSError):
            agent_tools.fix_abandon(self.where)
        self.assertEqual((self.copy / 'only-here.js').read_text(), UNIQUE)
        state = project_state.load(self.project)
        self.assertEqual((state['open_wave']['number'], state.get('waves') or []), (1, []))

    def test_the_closing_goes_through_once_it_can_be_written(self):
        with mock.patch.object(project_state, 'write', side_effect=OSError('no space left')), \
                self.assertRaises(OSError):
            agent_tools.fix_abandon(self.where)
        agent_tools.fix_abandon(self.where)
        self.assertEqual((project_state.load(self.project)['waves'][-1]['status'], self.copy.exists()),
                         ('abandoned', False))


class WhenTheEarlierStateCannotBeRead(OpenBatch):
    def _closing_finding(self, prior):
        """A real closing, when what is on disk before it cannot be told: `prior` writes that."""
        (self.copy / 'only-here.js').write_text(UNIQUE)
        state = project_state.load(self.project)
        prior(Path(state['workspace']) / 'state.json')
        with self.assertRaises(LookupError):
            guided.close_batch(state, 'abandoned', 'x')
        self.assertEqual((self.copy / 'only-here.js').read_text(), UNIQUE)

    def test_an_unreadable_one_removes_nothing(self):
        self._closing_finding(lambda record: record.write_text('{ not json'))

    def test_a_missing_one_removes_nothing(self):
        self._closing_finding(lambda record: record.unlink())


class OnAnotherBranch(Leftovers):
    """Each branch has its own runtime and its own numbers: batch 1 of one is not batch 1 of the other."""

    def test_moving_between_branches_removes_nothing_and_a_batch_closing_there_is_cleaned(self):
        here = git(self.project, 'rev-parse', '--abbrev-ref', 'HEAD')
        state = project_state.load(self.project)
        state.pop('open_wave')
        state['branch'] = state['home_branch'] = here
        state['waves'] = [{'number': 1, 'status': 'abandoned', 'cards': [], 'kept': {}, 'failed': {}}]
        project_state.write(state)
        (self.copy / 'only-here.js').write_text(UNIQUE)
        git(self.project, 'branch', 'feature')
        moved = guided.choose(project_state.load(self.project), 'feature')
        runtime = project_state.runtime_of(moved)
        self.assertNotEqual(runtime, self.runtime)
        copy = runtime / 'candidates' / 'WAVE-1'
        copy.mkdir(parents=True)
        moved['open_wave'] = {'number': 1, 'root': str(copy),
                              'base': git(self.project, 'rev-parse', 'HEAD'), 'cards': ['TASK-001'],
                              'kept': {}, 'failed': {}, 'tools': {}}
        guided.save(moved)
        guided.close_batch(project_state.load(self.project), 'abandoned', 'x')
        self.assertFalse(copy.exists(), 'its own batch 1 closed here')
        back = guided.choose(project_state.load(self.project), here)
        guided.save(back)
        self.assertEqual((self.copy / 'only-here.js').read_text(), UNIQUE,
                         'the other branch\'s closed batch 1 was closed before')

    def test_coming_back_to_a_branch_leaves_what_its_closed_batches_left(self):
        before = self.leftovers((1, 2))
        here = git(self.project, 'rev-parse', '--abbrev-ref', 'HEAD')
        git(self.project, 'branch', 'feature')
        guided.choose(project_state.load(self.project), 'feature')
        guided.choose(project_state.load(self.project), here)
        self.assertEqual(self.kept(), before)

    def test_coming_back_past_another_branchs_open_batch_of_the_same_number_leaves_this_ones_leftovers(self):
        before = self.leftovers((1,))
        here = git(self.project, 'rev-parse', '--abbrev-ref', 'HEAD')
        git(self.project, 'branch', 'feature')
        this_one = project_state.load(self.project)
        moved = guided.choose(project_state.load(self.project), 'feature')
        moved['open_wave'] = {'number': 1,
                              'root': str(project_state.runtime_of(moved) / 'candidates' / 'WAVE-1'),
                              'cards': [], 'kept': {}, 'failed': {}, 'tools': {}}
        guided.save(moved)
        guided.save(this_one)                                   # a state of this branch held in memory all along
        self.assertEqual((self.kept(), this_one['branch']), (before, here))
