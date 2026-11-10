"""Reading where a project stands deletes nothing of the person's: status, menu and plan, through MCP, the run engine and
the terminal, leave a merged batch's branch and an open batch's copy where they are, and say what they found. The
cleaning stays with what writes (docs/MCP.md, Merging)."""
import contextlib
import io
import json
import shutil
import subprocess
from pathlib import Path

from eaos.core.project import state as project_state
from eaos.interfaces import cli
from eaos.interfaces.mcp_server.server import functions
from eaos.interfaces import runs as actions
from eaos.journeys import agent_tools, guided
from tests.interfaces.test_read_only_tools import Home, _called, _files

BATCH = 'eaos/main/wave-1'
READS = ('status', 'menu', 'plan')


def _git(project, *argv):
    done = subprocess.run(['git', '-C', str(project), '-c', 'user.name=t', '-c', 'user.email=t@t', *argv], check=True, capture_output=True, text=True)
    return done.stdout.strip()


class Settled(Home):
    """A real git project, checked, on its branch main."""

    def setUp(self):
        super().setUp()
        self.checked()

    def state(self):
        return project_state.load(self.project)

    def commit(self, name):
        (self.project / name).write_text('print(2)\n', encoding='utf-8')
        _git(self.project, 'add', '-A')
        _git(self.project, 'commit', '-qm', f'the person adds {name}')
        return _git(self.project, 'rev-parse', 'HEAD')

    def read(self, name):
        return _called(self.server, name, project=str(self.project))

    def offered(self):
        return [option['id'] for page in self.read('menu')['pages'] for option in page]

    def has_branch(self, branch=BATCH):
        return bool(_git(self.project, 'branch', '--list', branch))

    def waiting_batch(self, branch=BATCH, tip=None):
        """A batch handed over and waiting for the person: its record in the state, as finishing a batch writes it."""
        state = self.state()
        state.setdefault('waves', []).append({'number': 1, 'branch': branch, 'status': 'applied', 'tip': tip, 'merge_into': 'main', 'cards': [], 'kept': {}})
        guided.save(state)

    def merged_by_hand(self, name='fixed.py'):
        """The person took the batch in with git, without EAOS."""
        _git(self.project, 'checkout', '-qb', BATCH)
        tip = self.commit(name)
        _git(self.project, 'checkout', '-q', 'main')
        self.waiting_batch(tip=tip)
        _git(self.project, 'merge', '-q', '--no-ff', '-m', 'taken in by hand', BATCH)

    def open_batch(self):
        """Batch 1 open with nothing kept: its copy, a real clone where a batch's copy lives. Returns the copy."""
        state, base = self.state(), _git(self.project, 'rev-parse', 'HEAD')
        copy = project_state.runtime_of(state) / 'candidates' / 'WAVE-1'
        copy.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'clone', '-q', str(self.project), str(copy)], check=True, capture_output=True)
        state['open_wave'] = {'number': 1, 'root': str(copy), 'base': base, 'source_commit': base, 'cards': ['TASK-001'], 'kept': {}, 'failed': {}, 'tools': {}}
        guided.save(state)
        return copy


class AManuallyMergedBatch(Settled):
    def test_each_read_records_it_as_taken_in_and_leaves_its_branch(self):
        self.merged_by_hand()
        for name in READS:
            with self.subTest(read=name):
                state = self.state()
                state['waves'][0].update(status='applied', merged_at=None)
                guided.save(state)
                answer = self.read(name)
                self.assertTrue(self.has_branch(), 'the branch is the person\'s to remove, or a later explicit step\'s')
                wave = self.state()['waves'][0]
                self.assertEqual(wave['status'], 'accepted')
                self.assertTrue(wave['merged_at'])
                if name == 'status': self.assertIsNone(answer['waiting_branch'])

    def test_the_terminals_status_leaves_it_too(self):
        self.merged_by_hand()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['status', str(self.project)]), 0)
        self.assertTrue(self.has_branch())
        self.assertEqual(self.state()['waves'][0]['status'], 'accepted')

    def test_each_writing_step_still_removes_it_after_a_read_recorded_it(self):
        where = str(self.project)
        for number, (name, step) in enumerate((('fix_start', lambda: agent_tools.fix_start(where)), ('accept', lambda: agent_tools.accept(where)),
                                               ('undo', lambda: agent_tools.undo(where)), ('open_report', lambda: agent_tools.open_report(where, show=False)))):
            with self.subTest(step=name):
                self.merged_by_hand(f'fixed{number}.py')
                self.read('status')
                self.assertTrue(self.has_branch())
                step()
                self.assertFalse(self.has_branch())
                state = self.state()
                state['waves'] = []
                guided.save(state)

    def test_a_kept_branch_stays_through_the_next_batch(self):
        self.merged_by_hand()
        state = self.state()
        state['waves'][0]['keep_branch'] = True
        guided.save(state)
        self.read('status')
        agent_tools.fix_start(str(self.project))
        self.assertTrue(self.has_branch())


class ADeletedBatchBranch(Settled):
    def test_each_read_records_it_as_undone(self):
        for name in READS:
            with self.subTest(read=name):
                _git(self.project, 'checkout', '-qb', BATCH)
                tip = self.commit(f'{name}.py')
                _git(self.project, 'checkout', '-q', 'main')
                self.waiting_batch(tip=tip)
                _git(self.project, 'branch', '-qD', BATCH)
                self.read(name)
                self.assertEqual(self.state()['waves'][0]['status'], 'undone')
                state = self.state()
                state['waves'] = []
                guided.save(state)


class AStaleOpenBatch(Settled):
    def test_each_read_leaves_its_copy_and_it_stays_open(self):
        copy = self.open_batch()
        before = _files(copy)
        self.commit('moved.py')
        for name in READS:
            with self.subTest(read=name):
                self.read(name)
                self.assertEqual(_files(copy), before)
                state = self.state()
                self.assertEqual((state['open_wave']['number'], state.get('waves') or []), (1, []))

    def test_status_never_calls_it_retired_and_says_why_it_no_longer_fits(self):
        self.open_batch()
        self.commit('moved.py')
        answer = self.read('status')
        self.assertIsNone(answer['retired_batch'], 'nothing was retired')
        self.assertEqual(answer['open_batch']['number'], 1, 'it is still open')
        self.assertEqual(answer['next']['tool'], 'run_setup', 'the step the new code needs, never to go on with the batch')
        self.assertIn(guided.why_stale(self.state()), answer['next']['why'])
        self.assertNotIn('retired', answer['next']['why'], 'the owner\'s rule: only detected, so not said to be closed')
        self.assertIsNone(answer['handover']['open_work'], 'fix_start would close it, not continue it')

    def test_the_menu_offers_no_going_on_with_it(self):
        self.open_batch()
        self.commit('moved.py')
        self.assertNotIn('continue', self.offered())

    def test_it_points_at_the_next_batch_when_the_app_was_run_on_the_new_code(self):
        self.open_batch()
        head = self.commit('moved.py')
        state = self.state()
        state.update(setup={'commit': head, 'ok': True}, safety={'commit': head, 'screens': 1, 'passed': 1})
        guided.save(state)
        answer = self.read('status')
        self.assertEqual(answer['next']['tool'], 'fix_start')
        self.assertIn(guided.why_stale(self.state()), answer['next']['why'])

    def test_a_batch_that_still_fits_is_unchanged(self):
        self.open_batch()
        answer = self.read('status')
        self.assertEqual(answer['next']['tool'], 'fix_edit, then fix_finish')
        self.assertEqual(answer['handover']['open_work']['number'], 1)
        self.assertIn('continue', self.offered())

    def test_reading_it_writes_nothing_but_the_journal(self):
        copy = self.open_batch()
        self.commit('moved.py')
        self.read('status')
        record = Path(self.state()['workspace']) / 'state.json'
        record.write_text(json.dumps({**json.loads(record.read_text(encoding='utf-8')), 'updated': 'an older stamp'}), encoding='utf-8')   # a save would change
        before = self._everything_but_the_journal()
        self.read('status')
        self.assertEqual(self._everything_but_the_journal(), before)
        self.assertTrue(copy.is_dir())

    def test_the_next_batch_closes_it_as_superseded_and_removes_its_copy(self):
        copy = self.open_batch()
        self.commit('moved.py')
        self.read('status')
        agent_tools.fix_start(str(self.project))
        state = self.state()
        self.assertEqual((state['waves'][-1]['status'], bool(state['waves'][-1]['why']), copy.exists()), ('superseded', True, False))

    def test_abandoning_it_closes_it_and_removes_its_copy(self):
        copy = self.open_batch()
        self.commit('moved.py')
        self.read('status')
        agent_tools.fix_abandon(str(self.project))
        state = self.state()
        self.assertEqual((state['waves'][-1]['status'], copy.exists()), ('abandoned', False))

    def test_the_next_check_closes_it_and_removes_its_copy(self):
        copy = self.open_batch()
        self.commit('moved.py')
        self.read('status')
        self.checked()
        state = self.state()
        self.assertEqual((state['waves'][-1]['status'], copy.exists()), ('superseded', False))


class ThroughTheRunEngine(Settled):
    """The run engine answers a reading action with the MCP tool itself."""

    def setUp(self):
        super().setUp()
        studio = self.root / 'studio'
        studio.mkdir()
        (studio / 'cards.json').write_text('{"cards": []}', encoding='utf-8')
        self.app = actions.Actions(self.project, port=8765, studio=studio, adapters={})
        self.app.manager.tools = functions

    def run_action(self, name):
        headers = {'X-EAOS-Token': self.app.token, 'X-EAOS-CSRF': self.app.csrf, 'Origin': 'http://127.0.0.1:8765', 'Host': '127.0.0.1:8765'}
        status, payload = self.app.handle('POST', '/api/runs', headers, {'action': name})
        self.assertEqual((status, payload['run']['state']), (200, 'done'))
        return payload['run']['result']['answer']

    def test_its_status_leaves_a_merged_batchs_branch(self):
        self.merged_by_hand()
        self.assertIsNone(self.run_action('status')['waiting_branch'])
        self.assertTrue(self.has_branch())

    def test_its_status_leaves_a_stale_batchs_copy(self):
        copy = self.open_batch()
        self.commit('moved.py')
        answer = self.run_action('status')
        self.assertEqual((answer['open_batch']['number'], answer['retired_batch']), (1, None))
        self.assertTrue(copy.is_dir())


class FirstUse(Home):
    """What a read settles the first time stays (status's branch question: test_read_only_tools)."""

    def test_each_read_makes_the_state_and_status_and_menu_pin_the_branch(self):
        for name, branch in (('status', 'main'), ('menu', 'main'), ('plan', None)):
            with self.subTest(read=name):
                shutil.rmtree(self.home, ignore_errors=True)
                _called(self.server, name, project=str(self.project))
                self.assertEqual(project_state.load(self.project).get('branch'), branch)
