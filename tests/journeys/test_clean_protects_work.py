"""`eaos clean` removes a copy only when it is proved to hold nothing of anyone's: no work open or waiting on it, no change
uncommitted, no commit that exists nowhere else. Whatever it cannot prove stays, and is named. Real repositories, copies
and states, through the command itself."""
import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.core.project import jobs, state as project_state
from eaos.interfaces import cli
from eaos.journeys import agent_tools
from eaos.journeys.guided import copies

UNIQUE = 'written nowhere else\n'


def git(where, *argv):
    return subprocess.run(['git', '-C', str(where), '-c', 'user.name=t', '-c', 'user.email=t@t', *argv], check=True, capture_output=True, text=True).stdout.strip()


class Clean(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        env = mock.patch.dict(os.environ, {'EAOS_HOME': str(self.root / 'home'), 'EAOS_OUTPUT': str(self.root / 'out'), 'EAOS_ASSISTANT': 'none'})
        env.start()
        self.addCleanup(env.stop)
        self.project = self.make('shop')

    def make(self, name):
        project = self.root / name
        project.mkdir()
        (project / 'app.py').write_text('print(1)\n')
        (project / '.gitignore').write_text('node_modules/\n')
        git(project, 'init', '-q', '-b', 'main')
        git(project, 'add', '-A')
        git(project, 'commit', '-qm', 'first')
        agent_tools.state_of(str(project))
        agent_tools.choose_branch('main', str(project), 'the work goes on here')
        return project

    def state(self, project=None):
        return project_state.load(project or self.project)

    def copy(self, name='WAVE-1', project=None, runtime='runtime'):
        project = project or self.project
        where = Path(self.state(project)['workspace']) / runtime / 'candidates' / name
        where.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'clone', '-q', '--no-hardlinks', str(project), str(where)], check=True, capture_output=True)
        return where

    def clean(self, *argv):
        said = io.StringIO()
        with contextlib.redirect_stdout(said):
            self.assertEqual(cli.main(['clean', '--lang', 'en', *argv]), 0)
        return said.getvalue()

    def assertKept(self, copy, said):
        self.assertTrue(copy.is_dir(), f'{copy.name} was removed')
        self.assertIn(str(copy), said, 'what stays is named, not counted as cleaned')

    def assertRemoved(self, copy):
        self.assertFalse(copy.exists(), f'{copy.name} stayed')


class WorkStillOpen(Clean):
    def test_an_open_fix_batch_with_nothing_changed_yet(self):
        copy = self.copy()
        state = self.state()
        state['open_wave'] = {'number': 1, 'root': str(copy), 'cards': [], 'kept': {}, 'failed': {}, 'tools': {}}
        project_state.write(state)
        self.assertKept(copy, self.clean())

    def test_an_open_build_milestone(self):
        copy = self.copy('BUILD-1')
        state = self.state()
        state['open_build'] = {'number': 1, 'milestone': 'M01', 'root': str(copy)}
        project_state.write(state)
        self.assertKept(copy, self.clean())

    def test_it_goes_by_the_batchs_folder_not_by_its_name(self):
        copy = self.copy('not-a-name-eaos-knows')
        state = self.state()
        state['open_wave'] = {'number': 7, 'root': str(copy), 'cards': [], 'kept': {}, 'failed': {}, 'tools': {}}
        project_state.write(state)
        self.assertKept(copy, self.clean())

    def test_a_batch_open_on_a_branch_not_worked_on_now(self):
        copy = self.copy('WAVE-1', runtime='runtime-feature')
        state = self.state()
        state['by_branch'] = {'feature': {'open_wave': {'number': 1, 'root': str(copy), 'cards': [], 'kept': {}, 'failed': {}, 'tools': {}}}}
        project_state.write(state)
        self.assertKept(copy, self.clean())

    def test_an_open_batch_that_does_not_say_where_it_is_keeps_every_copy(self):
        copy = self.copy('WAVE-1')
        state = self.state()
        state['open_wave'] = {'number': 1, 'cards': [], 'kept': {}, 'failed': {}, 'tools': {}}
        project_state.write(state)
        self.assertKept(copy, self.clean())

    def test_a_copy_beside_an_open_batch_that_holds_nothing_still_goes(self):
        open_copy, done = self.copy('WAVE-2'), self.copy('WAVE-1')
        state = self.state()
        state['open_wave'] = {'number': 2, 'root': str(open_copy), 'cards': [], 'kept': {}, 'failed': {}, 'tools': {}}
        project_state.write(state)
        self.assertKept(open_copy, self.clean())
        self.assertRemoved(done)


class WorkRunningOrWaiting(Clean):
    def job(self, status='running'):
        jobs._write({'id': 'fix_edit-1', 'kind': 'fix_edit', 'project': str(self.project), 'status': status, 'pid': os.getpid(), 'arguments': {}})

    def run_record(self, state):
        folder = Path(self.state()['workspace']) / 'runs' / 'r1'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'run.json').write_text(json.dumps({'id': 'r1', 'state': state}))

    def test_a_running_job_keeps_every_copy_until_it_ended(self):
        copy = self.copy()
        self.job()
        self.assertKept(copy, self.clean())
        self.job('done')
        self.clean()
        self.assertRemoved(copy)

    def test_a_run_queued_or_going_on_keeps_every_copy_until_it_ended(self):
        copy = self.copy()
        for state in ('queued', 'running', 'paused', 'waiting_for_person'):
            with self.subTest(state=state):
                self.run_record(state)
                self.assertKept(copy, self.clean())
        self.run_record('done')
        self.clean()
        self.assertRemoved(copy)

    def test_a_job_or_a_run_that_does_not_read_keeps_every_copy(self):
        copy = self.copy()
        self.job()
        record = jobs.folder(self.project) / 'fix_edit-1.json'
        record.write_text('{ not json')
        self.assertKept(copy, self.clean())
        record.unlink()
        self.run_record('done')
        (Path(self.state()['workspace']) / 'runs' / 'r1' / 'run.json').write_text('{ not json')
        self.assertKept(copy, self.clean())


class WhatACopyHolds(Clean):
    def assertKeptWithIts(self, copy, name):
        self.assertKept(copy, self.clean())
        self.assertEqual((copy / name).read_text(), UNIQUE)

    def test_an_untracked_file(self):
        copy = self.copy()
        (copy / 'new.py').write_text(UNIQUE)
        self.assertKeptWithIts(copy, 'new.py')

    def test_a_changed_file(self):
        copy = self.copy()
        (copy / 'app.py').write_text(UNIQUE)
        self.assertKeptWithIts(copy, 'app.py')

    def test_a_staged_file(self):
        copy = self.copy()
        (copy / 'new.py').write_text(UNIQUE)
        git(copy, 'add', '-A')
        self.assertKeptWithIts(copy, 'new.py')

    def test_a_commit_that_exists_only_there(self):
        copy = self.copy()
        (copy / 'new.py').write_text(UNIQUE)
        git(copy, 'add', '-A')
        git(copy, 'commit', '-qm', 'only here')
        self.assertKeptWithIts(copy, 'new.py')

    def test_a_commit_on_another_branch_of_the_copy(self):
        copy = self.copy()
        git(copy, 'checkout', '-qb', 'other')
        (copy / 'new.py').write_text(UNIQUE)
        git(copy, 'add', '-A')
        git(copy, 'commit', '-qm', 'only here')
        git(copy, 'checkout', '-q', 'main')
        self.assertKept(copy, self.clean())

    def test_a_stash(self):
        copy = self.copy()
        (copy / 'app.py').write_text(UNIQUE)
        git(copy, 'stash', 'push', '-q')
        self.assertKept(copy, self.clean())

    def test_a_commit_the_project_has_but_no_branch_of_it_holds(self):
        copy = self.copy()
        (copy / 'new.py').write_text(UNIQUE)
        git(copy, 'add', '-A')
        git(copy, 'commit', '-qm', 'fetched once, then its branch deleted')
        git(self.project, 'fetch', '-q', str(copy), 'HEAD')
        self.assertTrue(git(self.project, 'cat-file', '-t', git(copy, 'rev-parse', 'HEAD')))
        self.assertKeptWithIts(copy, 'new.py')

    def test_a_copy_of_a_closed_batch_with_commits_only_there(self):
        copy = self.copy()
        state = self.state()
        state['waves'] = [{'number': 1, 'status': 'abandoned', 'cards': [], 'kept': {}, 'failed': {}}]
        project_state.write(state)
        (copy / 'new.py').write_text(UNIQUE)
        git(copy, 'add', '-A')
        git(copy, 'commit', '-qm', 'kept in a batch that closed')
        self.assertKeptWithIts(copy, 'new.py')


class WhatIsDisposable(Clean):
    def test_a_copy_of_a_batch_handed_over_its_commits_in_the_project(self):
        copy = self.copy()
        (copy / 'fixed.py').write_text('print(2)\n')
        git(copy, 'add', '-A')
        git(copy, 'commit', '-qm', 'the fix')
        git(self.project, 'fetch', '-q', str(copy), 'HEAD:refs/heads/eaos/main/wave-1')
        state = self.state()
        state['waves'] = [{'number': 1, 'status': 'applied', 'branch': 'eaos/main/wave-1', 'cards': [], 'kept': {}}]
        project_state.write(state)
        self.clean()
        self.assertRemoved(copy)

    def test_an_empty_folder(self):
        empty = Path(self.state()['workspace']) / 'runtime' / 'candidates' / 'WAVE-1'
        empty.mkdir(parents=True)
        self.clean()
        self.assertRemoved(empty)

    def test_a_branchs_runtime_too(self):
        copy = self.copy('WAVE-1', runtime='runtime-feature')
        self.clean()
        self.assertRemoved(copy)

    def test_the_project_its_files_and_its_branches_are_untouched(self):
        git(self.project, 'branch', 'eaos/main/wave-1')
        (self.project / 'unsaved.py').write_text(UNIQUE)
        refs, files = git(self.project, 'for-each-ref'), sorted(p.name for p in self.project.iterdir())
        self.copy()
        self.clean()
        self.assertEqual((git(self.project, 'for-each-ref'), sorted(p.name for p in self.project.iterdir())), (refs, files))
        self.assertEqual((self.project / 'unsaved.py').read_text(), UNIQUE)


class ManyProjects(Clean):
    def test_each_project_is_judged_by_itself(self):
        other = self.make('other')
        kept, gone = self.copy('WAVE-1'), self.copy('WAVE-1', project=other)
        state = self.state()
        state['open_wave'] = {'number': 1, 'root': str(kept), 'cards': [], 'kept': {}, 'failed': {}, 'tools': {}}
        project_state.write(state)
        self.assertKept(kept, self.clean())
        self.assertRemoved(gone)

    def test_a_job_of_one_project_holds_no_other(self):
        other = self.make('other')
        kept, gone = self.copy('WAVE-1'), self.copy('WAVE-1', project=other)
        jobs._write({'id': 'fix_edit-1', 'kind': 'fix_edit', 'project': str(self.project), 'status': 'running', 'pid': os.getpid(), 'arguments': {}})
        self.assertKept(kept, self.clean())
        self.assertRemoved(gone)


class WhatCannotBeTold(Clean):
    def record(self):
        return Path(self.state()['workspace']) / 'state.json'

    def test_a_state_missing_broken_or_not_a_state(self):
        copy, record = self.copy(), self.record()
        for name, change in (('missing', lambda: record.unlink()), ('broken', lambda: record.write_text('{ not json')),
                             ('empty', lambda: record.write_text('{}')), ('a list', lambda: record.write_text('[]'))):
            with self.subTest(state=name):
                change()
                self.assertKept(copy, self.clean())

    def test_a_state_that_is_another_folders(self):
        copy, record = self.copy(), self.record()
        record.write_text(json.dumps({**self.state(), 'project': str(self.root / 'moved'), 'workspace': str(self.root / 'elsewhere')}))
        self.assertKept(copy, self.clean())

    def test_a_state_of_another_project_says_nothing_of_this_folder(self):
        other = self.make('other')
        where = Path(self.state()['workspace']) / 'runtime' / 'candidates' / 'WAVE-1'
        where.parent.mkdir(parents=True)
        subprocess.run(['git', 'clone', '-q', str(other), str(where)], check=True, capture_output=True)
        self.record().write_text(json.dumps(self.state(other)))
        self.assertKept(where, self.clean())

    def test_a_project_no_longer_there_to_compare_with(self):
        copy = self.copy()
        shutil.rmtree(self.project)
        said = self.clean()
        self.assertKept(copy, said)
        self.assertIn(copies.WHY['project'][1], said)

    def test_a_folder_that_is_no_repository(self):
        folder = Path(self.state()['workspace']) / 'runtime' / 'candidates' / 'TASK-001'
        folder.mkdir(parents=True)
        (folder / 'left.py').write_text(UNIQUE)
        self.assertKept(folder, self.clean())

    def test_a_folder_is_not_taken_for_the_repository_around_it(self):
        (self.root / '.gitignore').write_text('*\n!.gitignore\n')          # EAOS's home inside the project, which ignores it
        git(self.root, 'init', '-q', '-b', 'main')
        git(self.root, 'add', '-A')
        git(self.root, 'commit', '-qm', 'first')
        agent_tools.state_of(str(self.root))
        agent_tools.choose_branch('main', str(self.root), 'here')
        folder = Path(self.state(self.root)['workspace']) / 'runtime' / 'candidates' / 'WAVE-1'
        folder.mkdir(parents=True)
        (folder / 'left.py').write_text(UNIQUE)
        self.assertKept(folder, self.clean())
        (folder / '.git').mkdir()                                       # git takes a folder this empty for no repository
        self.assertKept(folder, self.clean())

    def test_a_state_an_older_eaos_wrote_with_what_it_lacks(self):
        kept, gone = self.copy('WAVE-1'), self.copy('WAVE-2')
        (kept / 'new.py').write_text(UNIQUE)
        record = self.record()
        state = self.state()
        record.write_text(json.dumps({key: state[key] for key in ('project', 'workspace')}))
        self.assertKept(kept, self.clean())
        self.assertRemoved(gone)


class AgainAndInterrupted(Clean):
    def test_cleaning_again_changes_nothing_more(self):
        kept, gone = self.copy('WAVE-1'), self.copy('WAVE-2')
        (kept / 'new.py').write_text(UNIQUE)
        self.clean()
        said = self.clean()
        self.assertKept(kept, said)
        self.assertRemoved(gone)

    def test_a_removal_that_failed_is_said_not_counted(self):
        copy = self.copy()
        with mock.patch.object(shutil, 'rmtree'):
            said = self.clean()
        self.assertIn('WAVE-1', said)
        self.assertTrue(list(copy.parent.iterdir()))


class TheRestOfCleaning(Clean):
    def test_sandboxes_sessions_and_pictures_go_as_before_beside_a_copy_that_stays(self):
        copy = self.copy()
        (copy / 'new.py').write_text(UNIQUE)
        state = self.state()
        runtime = project_state.runtime_of(state)
        left = runtime / 'sandbox' / 'run-left-by-a-killed-run'
        left.mkdir(parents=True)
        session = runtime / 'session.json'
        session.write_text(json.dumps({'cookies': [], 'origins': []}))
        report = self.root / 'out' / 'shop' / 'technical' / 'live' / 'screens'
        report.mkdir(parents=True)
        self.assertKept(copy, self.clean('--pictures'))
        self.assertRemoved(left)
        self.assertFalse(session.exists())
        self.assertFalse(report.exists())


class WhatGitWouldHide(Clean):
    """A copy's own settings, or the computer's, must not make what it holds look like nothing."""

    def untracked(self, copy, name='new.py'):
        (copy / name).parent.mkdir(exist_ok=True)
        (copy / name).write_text(UNIQUE)

    def test_a_copy_that_hides_its_untracked_files(self):
        copy = self.copy()
        git(copy, 'config', 'status.showUntrackedFiles', 'no')
        self.untracked(copy)
        self.assertKept(copy, self.clean())

    def test_a_computer_that_hides_untracked_files(self):
        copy = self.copy()
        settings = self.root / 'gitconfig'
        excludes = self.root / 'excludes'
        excludes.write_text('new.py\n')
        settings.write_text(f'[status]\n\tshowUntrackedFiles = no\n[core]\n\texcludesFile = {excludes}\n')
        self.untracked(copy)
        with mock.patch.dict(os.environ, {'GIT_CONFIG_GLOBAL': str(settings)}):
            self.assertKept(copy, self.clean())

    def test_a_copys_own_exclude_file(self):
        copy = self.copy()
        (copy / '.git' / 'info' / 'exclude').write_text('new.py\n')
        self.untracked(copy)
        self.assertKept(copy, self.clean())

    def test_an_untracked_ignore_file_of_the_copys_own(self):
        copy = self.copy()
        self.untracked(copy, 'draft/new.py')
        (copy / 'draft' / '.gitignore').write_text('*\n')
        self.assertKept(copy, self.clean())

    def test_an_edit_git_was_told_not_to_look_at(self):
        for flag in ('--skip-worktree', '--assume-unchanged'):
            with self.subTest(flag=flag):
                copy = self.copy(flag.strip('-'))
                (copy / 'app.py').write_text(UNIQUE)
                git(copy, 'update-index', flag, 'app.py')
                self.assertKept(copy, self.clean())

    def test_a_commit_held_only_by_a_remote_ref_of_the_copy(self):
        copy = self.copy()
        self.untracked(copy)
        git(copy, 'add', '-A')
        git(copy, 'commit', '-qm', 'only here')
        git(copy, 'update-ref', 'refs/remotes/mine/work', 'HEAD')
        git(copy, 'reset', '-q', '--hard', 'HEAD~1')
        self.assertKept(copy, self.clean())

    def test_a_copy_with_repositories_of_its_own_inside_its_git_folder(self):
        for inside in ('modules', 'worktrees'):
            with self.subTest(inside=inside):
                copy = self.copy(inside)
                (copy / '.git' / inside / 'sub').mkdir(parents=True)
                self.assertKept(copy, self.clean())

    def test_a_command_in_a_copys_settings_does_not_run(self):
        copy = self.copy()
        ran = self.root / 'ran'
        git(copy, 'config', 'core.fsmonitor', f'touch {ran} #')
        self.clean()
        self.assertFalse(ran.exists())

    def test_a_link_is_not_followed_and_the_project_stays(self):
        link = Path(self.state()['workspace']) / 'runtime' / 'candidates' / 'WAVE-1'
        link.parent.mkdir(parents=True)
        link.symlink_to(self.project)
        said = self.clean()
        self.assertTrue(link.is_symlink())
        self.assertIn(str(link), said)
        self.assertTrue((self.project / 'app.py').is_file())


class MoreThatCannotBeTold(Clean):
    def workspace(self):
        return Path(self.state()['workspace'])

    def test_a_folder_named_like_one_being_removed_is_judged_as_any_other(self):
        copy = self.copy('.removing-mine')
        (copy / 'new.py').write_text(UNIQUE)
        self.assertKept(copy, self.clean())
        (self.workspace() / 'state.json').unlink()
        self.assertKept(copy, self.clean())

    def test_a_batch_opened_while_it_waited_for_its_turn(self):
        copy = self.copy()
        real = jobs.alone
        @contextlib.contextmanager
        def its_turn(project, *args):
            with real(project, *args):
                state = self.state()
                state['open_wave'] = {'number': 1, 'root': str(copy), 'cards': [], 'kept': {}, 'failed': {}, 'tools': {}}
                project_state.write(state)
                yield
        with mock.patch.object(jobs, 'alone', its_turn):
            self.assertKept(copy, self.clean())

    def test_a_queue_or_a_run_folder_that_says_nothing_clear(self):
        copy = self.copy()
        runs = self.workspace() / 'runs'
        runs.mkdir(exist_ok=True)
        for name, change in (('a queue that does not read', lambda: (runs / 'queue.json').write_text('{ not json')),
                             ('a queue naming an unknown run', lambda: (runs / 'queue.json').write_text('["r9"]')),
                             ('a run folder with no record', lambda: ((runs / 'queue.json').unlink(), (runs / 'r1').mkdir()))):
            with self.subTest(case=name):
                change()
                self.assertKept(copy, self.clean())

    def test_the_chat_folder_of_the_runs_is_no_run_and_a_queue_of_ended_runs_holds_nothing(self):
        copy = self.copy()
        runs = self.workspace() / 'runs'
        (runs / 'chat').mkdir(parents=True)
        (runs / 'r1').mkdir()
        (runs / 'r1' / 'run.json').write_text(json.dumps({'id': 'r1', 'state': 'done'}))
        (runs / 'queue.json').write_text('["r1"]')
        self.clean()
        self.assertRemoved(copy)

    def test_a_job_or_a_run_record_without_what_it_needs(self):
        copy = self.copy()
        folder = jobs.folder(self.project)
        folder.mkdir(parents=True, exist_ok=True)
        for text in ('{}', '[]', '{"status": "running"}'):
            with self.subTest(job=text):
                (folder / 'odd.json').write_text(text)
                self.assertKept(copy, self.clean())

    def test_a_state_with_batches_in_shapes_it_never_has(self):
        copy = self.copy()
        for change in ({'open_wave': 'WAVE-1'}, {'by_branch': 'none'}, {'by_branch': {'feature': 'none'}}):
            with self.subTest(change=change):
                record = self.workspace() / 'state.json'
                record.write_text(json.dumps({**self.state(), **change}))
                self.assertKept(copy, self.clean())

    def test_one_project_that_cannot_be_read_stops_no_other(self):
        other = self.make('other')
        gone = self.copy('WAVE-1', project=other)
        (self.workspace() / 'runtime').mkdir(exist_ok=True)
        (self.workspace() / 'runtime' / 'candidates').write_text('a file')
        self.clean()
        self.assertRemoved(gone)

    def test_a_folder_only_named_like_a_runtime_is_left(self):
        copy = self.copy('WAVE-1', runtime='runtime.bak')
        self.clean()
        self.assertTrue(copy.is_dir())

    def test_it_does_not_say_it_removed_what_stayed(self):
        copy = self.copy()
        (copy / 'new.py').write_text(UNIQUE)
        self.assertNotIn('Removed the temporary copies', self.clean())


class TheRestWaitsForWorkToo(Clean):
    def test_a_running_job_loses_no_session_and_no_picture(self):
        state = self.state()
        session = project_state.runtime_of(state) / 'session.json'
        session.parent.mkdir(parents=True, exist_ok=True)
        session.write_text(json.dumps({'cookies': [], 'origins': []}))
        guided_outputs = self.root / 'out' / 'shop'
        pictures = guided_outputs / 'technical' / 'live' / 'screens'
        pictures.mkdir(parents=True)
        (guided_outputs / '.eaos-project').write_text(str(self.project) + '\n')
        jobs._write({'id': 'audit-1', 'kind': 'audit', 'project': str(self.project), 'status': 'running', 'pid': os.getpid(), 'arguments': {}})
        said = self.clean('--pictures')
        self.assertTrue(session.is_file())
        self.assertTrue(pictures.is_dir())
        self.assertIn(str(guided_outputs / 'technical'), said)


class TheSecondReview(Clean):
    def test_a_repository_inside_as_a_tracked_gitlink(self):
        copy = self.copy()
        inner = copy / 'lib'
        inner.mkdir()
        git(inner, 'init', '-q', '-b', 'main')
        (inner / 'x.py').write_text(UNIQUE)
        git(inner, 'add', '-A')
        git(inner, 'commit', '-qm', 'only here')
        git(copy, 'add', 'lib')
        git(copy, 'commit', '-qm', 'the gitlink')
        git(self.project, 'fetch', '-q', str(copy), 'HEAD:refs/heads/eaos/main/wave-1')
        self.assertKept(copy, self.clean())

    def test_a_file_hidden_by_a_copy_that_ignores_case(self):
        copy = self.copy()
        git(copy, 'config', 'core.ignoreCase', 'true')
        (copy / 'APP.PY').write_text(UNIQUE)
        self.assertKept(copy, self.clean())

    def test_a_file_named_as_the_mark_of_a_proved_copy_proves_nothing(self):
        copy = self.copy('.removing-X')
        (copy / 'new.py').write_text(UNIQUE)
        (copy.parent / '.removing-X.proved').write_text('')
        self.assertKept(copy, self.clean())
        self.assertEqual((copy / 'new.py').read_text(), UNIQUE)

    def test_a_folder_named_as_the_mark_blocks_nothing(self):
        kept, gone = self.copy('.removing-X'), self.copy('WAVE-2')
        (kept / 'new.py').write_text(UNIQUE)
        (kept.parent / '.removing-X.proved').mkdir()
        self.assertKept(kept, self.clean())
        self.assertRemoved(gone)

    def test_a_live_job_keeps_its_sessions_with_the_state_gone(self):
        session = project_state.runtime_of(self.state()) / 'session.json'
        session.parent.mkdir(parents=True, exist_ok=True)
        session.write_text(json.dumps({'cookies': [], 'origins': []}))
        record = Path(self.state()['workspace']) / 'state.json'
        jobs._write({'id': 'audit-1', 'kind': 'audit', 'project': str(self.project), 'status': 'running', 'pid': os.getpid(), 'arguments': {}})
        record.unlink()
        self.clean()
        self.assertTrue(session.is_file())

    def test_a_hook_in_a_copy_does_not_run(self):
        copy = self.copy()
        ran = self.root / 'ran'
        hook = copy / '.git' / 'hooks' / 'post-index-change'
        hook.parent.mkdir(exist_ok=True)
        hook.write_text(f'#!/bin/sh\ntouch {ran}\n')
        hook.chmod(0o755)
        (copy / 'app.py').write_text('print(1)\n')     # the same bytes, a new time: git looks and refreshes
        self.clean()
        self.assertFalse(ran.exists())

    def test_a_name_git_cannot_decode_keeps_that_copy_alone_and_says_it_could_not_read_it(self):
        kept, gone = self.copy('WAVE-1'), self.copy('WAVE-2')
        with open(os.path.join(os.fsencode(kept), b'caf\xe9.py'), 'w') as odd: odd.write(UNIQUE)
        said = self.clean()
        self.assertKept(kept, said)
        self.assertIn(copies.WHY['unreadable'][1], said)
        self.assertRemoved(gone)

    def test_an_outputs_folder_with_a_mark_that_does_not_read_stops_nothing(self):
        out = self.root / 'out' / 'shop'
        (out / 'technical').mkdir(parents=True)
        (out / '.eaos-project').write_bytes(b'\xff\xfe')
        self.clean('--pictures')

    def test_a_copy_nothing_was_done_in_goes_when_the_project_later_moved_its_branches(self):
        git(self.project, 'branch', 'gone-later')
        deleted = self.copy('WAVE-1')
        git(deleted, 'checkout', '-q', 'gone-later')
        (self.project / 'x.py').write_text('1\n')
        git(self.project, 'add', '-A')
        git(self.project, 'commit', '-qm', 'more')
        rewritten = self.copy('WAVE-2')
        git(self.project, 'branch', '-qD', 'gone-later')
        git(self.project, 'commit', '-q', '--amend', '-m', 'rewritten')
        self.clean()
        self.assertRemoved(rewritten)
        self.assertRemoved(deleted)

    def test_a_commit_made_in_the_copy_stays_when_the_project_later_moved_its_branches(self):
        copy = self.copy()
        (copy / 'new.py').write_text(UNIQUE)
        git(copy, 'add', '-A')
        git(copy, 'commit', '-qm', 'made here')
        git(self.project, 'commit', '-q', '--allow-empty', '--amend', '-m', 'rewritten')
        self.assertKept(copy, self.clean())


class TheThirdReview(Clean):
    def made_in(self, copy):
        (copy / 'new.py').write_text(UNIQUE)
        git(copy, 'add', '-A')
        git(copy, 'commit', '-qm', 'made here')

    def test_a_commit_pushed_from_the_copy_to_a_branch_since_deleted(self):
        copy = self.copy()
        self.made_in(copy)
        git(copy, 'push', '-q', 'origin', 'HEAD:refs/heads/x')
        git(self.project, 'branch', '-qD', 'x')
        self.assertKept(copy, self.clean())

    def test_a_commit_fetched_back_to_the_copy_from_a_branch_since_deleted(self):
        copy = self.copy()
        self.made_in(copy)
        git(self.project, 'fetch', '-q', str(copy), 'HEAD:refs/heads/x')
        git(copy, 'fetch', '-q', 'origin')
        git(self.project, 'branch', '-qD', 'x')
        self.assertKept(copy, self.clean())

    def test_a_tag_on_a_file_no_commit_holds(self):
        copy = self.copy()
        (copy / '.git' / 'tmp').write_text(UNIQUE)
        git(copy, 'tag', 'keep', git(copy, 'hash-object', '-w', '.git/tmp'))
        self.assertKept(copy, self.clean())

    def test_a_project_with_a_submodule_not_filled_in_the_copy_still_cleans(self):
        head = git(self.project, 'rev-parse', 'HEAD')
        git(self.project, 'update-index', '--add', '--cacheinfo', f'160000,{head},lib')
        git(self.project, 'commit', '-qm', 'a submodule')
        git(self.project, 'checkout', '-q', '--', '.')
        copy = self.copy()
        self.clean()
        self.assertRemoved(copy)

    def test_a_folder_named_what_cannot_be_printed_is_still_named(self):
        folder = os.path.join(os.fsencode(Path(self.state()['workspace']) / 'runtime' / 'candidates'), b'caf\xe9')
        os.makedirs(folder)
        with open(os.path.join(folder, b'left.py'), 'w') as left: left.write(UNIQUE)
        raw = io.BytesIO()
        strict = io.TextIOWrapper(raw, encoding='utf-8', errors='strict', write_through=True)
        self.addCleanup(strict.detach)
        with contextlib.redirect_stdout(strict):
            self.assertEqual(cli.main(['clean', '--lang', 'en']), 0)
        self.assertIn(b'caf', raw.getvalue())
        self.assertTrue(os.path.isdir(folder))

    def test_a_mark_that_cannot_be_written_stops_no_other_copy(self):
        other = self.make('other')
        kept, gone = self.copy('WAVE-1'), self.copy('WAVE-1', project=other)
        touch = Path.touch
        def full(path, *args, **options):
            if path.name.endswith('.proved') and kept.parent in path.parents: raise OSError('no space left')
            return touch(path, *args, **options)
        with mock.patch.object(Path, 'touch', full):
            said = self.clean()
        self.assertIn(str(kept.with_name('.removing-WAVE-1')), said, 'where it is now')
        self.assertRemoved(gone)


class TheLastReview(Clean):
    def test_a_filled_submodule_under_a_name_git_quotes(self):
        copy = self.copy()
        inner = copy / 'مكتبة'
        inner.mkdir()
        git(inner, 'init', '-q', '-b', 'main')
        (inner / 'x.py').write_text(UNIQUE)
        git(inner, 'add', '-A')
        git(inner, 'commit', '-qm', 'only here')
        git(copy, 'add', 'مكتبة')
        git(copy, 'commit', '-qm', 'the gitlink')
        git(self.project, 'fetch', '-q', str(copy), 'HEAD:refs/heads/eaos/main/wave-1')
        self.assertKept(copy, self.clean())

    def test_a_copy_left_as_it_was_cloned_goes_when_the_project_drops_another_branch(self):
        git(self.project, 'checkout', '-qb', 'side')
        (self.project / 'side.py').write_text('1\n')
        git(self.project, 'add', '-A')
        git(self.project, 'commit', '-qm', 'on a side branch')
        git(self.project, 'checkout', '-q', 'main')
        copy = self.copy()
        git(self.project, 'branch', '-qD', 'side')
        self.clean()
        self.assertRemoved(copy)

    def test_a_copy_of_a_project_on_no_branch_goes(self):
        git(self.project, 'checkout', '-q', '--detach')
        (self.project / 'x.py').write_text('1\n')
        git(self.project, 'add', '-A')
        git(self.project, 'commit', '-qm', 'on no branch')
        copy = self.copy()
        self.clean()
        self.assertRemoved(copy)

    def test_a_copy_that_fetched_what_the_project_rewrote_after_its_clone_goes(self):
        copy = self.copy()
        git(self.project, 'commit', '-q', '--amend', '-m', 'rewritten')
        git(copy, 'fetch', '-q', 'origin')
        self.clean()
        self.assertRemoved(copy)

    def test_a_reflog_emptied_by_time_stops_nothing(self):
        copy = self.copy()
        for log in (copy / '.git' / 'logs' / 'refs' / 'remotes' / 'origin').rglob('*'):
            if log.is_file(): log.write_text('')
        self.clean()
        self.assertRemoved(copy)

    def test_a_copy_that_keeps_no_reflog_cannot_say_what_it_came_with(self):
        copy = self.copy()
        git(copy, 'config', 'core.logAllRefUpdates', 'false')
        (copy / 'new.py').write_text(UNIQUE)
        git(copy, 'add', '-A')
        git(copy, 'commit', '-qm', 'made here')
        git(copy, 'push', '-q', 'origin', 'HEAD:refs/heads/x')
        git(self.project, 'branch', '-qD', 'x')
        self.assertKept(copy, self.clean())

    def test_a_commit_pushed_over_a_branch_it_came_with_stays(self):
        copy = self.copy()
        (copy / 'new.py').write_text(UNIQUE)
        git(copy, 'add', '-A')
        git(copy, 'commit', '-qm', 'made here')
        git(self.project, 'checkout', '-q', '--detach')
        git(copy, 'push', '-q', 'origin', 'HEAD:main')
        git(self.project, 'checkout', '-q', 'main')
        git(self.project, 'reset', '-q', '--hard', 'HEAD~1')
        self.assertKept(copy, self.clean())

    def test_many_commits_on_no_ref_of_the_copy_are_looked_at_once(self):
        copy = self.copy()
        for number in range(3):
            git(copy, 'commit', '-q', '--allow-empty', '-m', f'made {number}')
        git(self.project, 'fetch', '-q', str(copy), 'HEAD:refs/heads/kept')
        calls = []
        real = copies._git
        def counted(where, *args):
            calls.append(args)
            return real(where, *args)
        with mock.patch.object(copies, '_git', counted):
            self.clean()
        self.assertRemoved(copy)
        self.assertLessEqual(sum('--contains' in call for call in calls), 1, 'one call whatever the commits')


class IgnoredIsNotDisposable(Clean):
    """That git and the project ignore a file says nothing of what is in it."""

    def ignoring(self, line):
        with open(self.project / '.gitignore', 'a') as ignore: ignore.write(line + '\n')
        git(self.project, 'add', '-A')
        git(self.project, 'commit', '-qm', 'ignores more')

    def test_an_ignored_env_file(self):
        self.ignoring('.env')
        copy = self.copy()
        (copy / '.env').write_text(UNIQUE)
        self.assertEqual(git(copy, 'status', '--porcelain', '--ignored'), '!! .env')
        self.assertKept(copy, self.clean())
        self.assertEqual((copy / '.env').read_text(), UNIQUE)

    def test_a_custom_ignored_folder(self):
        self.ignoring('local-data/')
        copy = self.copy()
        (copy / 'local-data').mkdir()
        (copy / 'local-data' / 'backup.db').write_text(UNIQUE)
        self.assertKept(copy, self.clean())
        self.assertEqual((copy / 'local-data' / 'backup.db').read_text(), UNIQUE)

    def test_a_folder_that_looks_generated_may_hold_something_else(self):
        copy = self.copy()
        (copy / 'node_modules' / 'patched').mkdir(parents=True)
        (copy / 'node_modules' / 'patched' / 'index.js').write_text(UNIQUE)
        self.assertKept(copy, self.clean())
        self.assertEqual((copy / 'node_modules' / 'patched' / 'index.js').read_text(), UNIQUE)

    def test_it_says_why_so_the_person_can_decide(self):
        copy = self.copy()
        (copy / 'node_modules').mkdir()
        (copy / 'node_modules' / 'x.js').write_text('x')
        self.assertIn(copies.WHY['ignored'][1], self.clean())


class ACleanStoppedHalfway(Clean):
    def stopped(self, copy):
        """A real clean stopped after it proved the copy, moved it aside and removed one of its files. The folder aside."""
        unlink = Path.unlink
        def once(path, *args, **options):
            unlink(path, *args, **options)
            if '.removing-' in str(path) and not path.name.endswith('.proved'): raise KeyboardInterrupt
        with mock.patch.object(Path, 'unlink', once), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertNotEqual(cli.main(['clean', '--lang', 'en']), 0)
        aside = copy.with_name('.removing-' + copy.name)
        self.assertTrue(aside.is_dir(), 'stopped with the copy moved aside')
        self.assertTrue((aside / '.git').is_dir(), 'what proves the rest goes last')
        return aside

    def test_with_nothing_new_the_next_clean_ends_it(self):
        copy = self.copy()
        self.stopped(copy)
        self.clean()
        self.assertEqual(list(copy.parent.iterdir()), [])

    def test_a_new_file_stays(self):
        aside = self.stopped(self.copy())
        (aside / 'new.py').write_text(UNIQUE)
        self.assertKept(aside, self.clean())
        self.assertEqual((aside / 'new.py').read_text(), UNIQUE)

    def test_a_new_ignored_file_stays(self):
        aside = self.stopped(self.copy())
        (aside / 'node_modules').mkdir()
        (aside / 'node_modules' / 'mine.js').write_text(UNIQUE)
        self.assertKept(aside, self.clean())

    def test_a_tracked_file_changed_stays(self):
        copy = self.copy()
        (self.project / 'other.py').write_text('1\n')
        git(self.project, 'add', '-A')
        git(self.project, 'commit', '-qm', 'one more')
        git(copy, 'pull', '-q', 'origin', 'main')
        aside = self.stopped(copy)
        left = next(p for p in aside.iterdir() if p.name != '.git')
        left.write_text(UNIQUE)
        self.assertKept(aside, self.clean())
        self.assertEqual(left.read_text(), UNIQUE)

    def test_a_new_commit_stays(self):
        aside = self.stopped(self.copy())
        (aside / 'new.py').write_text(UNIQUE)
        git(aside, 'add', 'new.py')
        git(aside, 'commit', '-qm', 'made after the stop')
        self.assertKept(aside, self.clean())

    def test_the_mark_goes_only_with_the_copy(self):
        copy = self.copy()
        aside = self.stopped(copy)
        mark = copy.parent / '.removing-WAVE-1.proved'
        self.assertTrue(mark.is_file())
        (aside / 'new.py').write_text(UNIQUE)
        self.clean()
        self.assertTrue(mark.is_file(), 'the copy stayed, and so did what says its missing files were not lost')
        (aside / 'new.py').unlink()
        self.clean()
        self.assertEqual(list(copy.parent.iterdir()), [])

    def test_a_mark_with_no_folder_goes_and_blocks_nothing(self):
        copy = self.copy()
        (copy.parent / '.removing-WAVE-1.proved').touch()
        self.clean()
        self.assertEqual(list(copy.parent.iterdir()), [])

    def worktree_gone(self, aside):
        for entry in aside.iterdir():
            if entry.name != '.git': entry.unlink()

    def test_only_its_git_folder_left_and_unreadable_it_stays_and_is_named(self):
        aside = self.stopped(self.copy())
        self.worktree_gone(aside)
        shutil.rmtree(aside / '.git' / 'objects')
        self.assertKept(aside, self.clean())

    def test_only_its_git_folder_left_with_a_staged_file_it_stays(self):
        aside = self.stopped(self.copy())
        (aside / 'new.py').write_text(UNIQUE)
        git(aside, 'add', 'new.py')
        (aside / 'new.py').unlink()
        self.worktree_gone(aside)
        self.assertKept(aside, self.clean())

    def test_only_its_git_folder_left_with_a_garbled_head_it_stays(self):
        aside = self.stopped(self.copy())
        self.worktree_gone(aside)
        (aside / '.git' / 'HEAD').write_text('garbled')
        self.assertKept(aside, self.clean())

    def test_only_its_git_folder_left_with_a_repository_in_it_stays(self):
        aside = self.stopped(self.copy())
        self.worktree_gone(aside)
        (aside / '.git' / 'modules' / 'sub').mkdir(parents=True)
        self.assertKept(aside, self.clean())

    def test_only_its_git_folder_left_and_sound_it_ends(self):
        aside = self.stopped(self.copy())
        self.worktree_gone(aside)
        self.clean()
        self.assertEqual(list(aside.parent.iterdir()), [])

    def test_a_folder_that_cannot_be_removed_leaves_its_git_so_the_next_clean_can_end_it(self):
        copy = self.copy()
        (copy / 'src').mkdir()
        (copy / 'src' / 'a.py').write_text('1\n')
        git(copy, 'add', '-A')
        git(copy, 'commit', '-qm', 'a folder')
        git(self.project, 'fetch', '-q', str(copy), 'HEAD:refs/heads/kept')
        aside = copy.with_name('.removing-WAVE-1')
        rmtree = shutil.rmtree
        def held(path, *args, **options):
            if Path(path).name != 'src': rmtree(path, *args, **options)
        with mock.patch.object(shutil, 'rmtree', held):
            said = self.clean()
        self.assertIn(str(aside), said)
        self.assertTrue((aside / '.git').is_dir(), 'a failure takes no more than a stop does')
        self.clean()
        self.assertEqual(list(aside.parent.iterdir()), [])

    def test_a_copy_removed_by_hand_while_this_waits_for_its_turn_stops_nothing(self):
        gone_by_hand, gone = self.copy('WAVE-1'), self.copy('WAVE-2')
        real = jobs.alone
        @contextlib.contextmanager
        def its_turn(project, *args):
            shutil.rmtree(gone_by_hand, ignore_errors=True)
            with real(project, *args): yield
        with mock.patch.object(jobs, 'alone', its_turn):
            said = self.clean()
        self.assertNotIn(str(gone_by_hand), said, 'it is simply gone')
        self.assertRemoved(gone)

    def test_a_copy_removed_by_hand_as_it_is_moved_aside_stops_nothing(self):
        lost, other = self.copy('WAVE-1'), self.make('other')
        gone = self.copy('WAVE-1', project=other)
        rename = Path.rename
        def by_hand(path, target):
            if path == lost:
                shutil.rmtree(lost)
                raise FileNotFoundError(path)
            return rename(path, target)
        with mock.patch.object(Path, 'rename', by_hand):
            self.clean()
        self.assertRemoved(gone)

    def test_a_file_that_cannot_be_removed_names_that_copy_and_stops_no_other(self):
        stuck, gone = self.copy('WAVE-1'), self.copy('WAVE-2')
        aside = stuck.with_name('.removing-WAVE-1')
        unlink = Path.unlink
        def held(path, *args, **options):
            if aside in path.parents and not path.name.endswith('.proved'): raise PermissionError('held')
            return unlink(path, *args, **options)
        with mock.patch.object(Path, 'unlink', held):
            said = self.clean()
        self.assertIn(str(aside), said)
        self.assertIn(copies.WHY['failed'][1], said)
        self.assertRemoved(gone)
        self.assertNotIn(str(gone.with_name('.removing-WAVE-2')), said)

    def test_only_its_git_folder_left_with_a_commit_in_it_stays(self):
        aside = self.stopped(self.copy())
        (aside / 'new.py').write_text(UNIQUE)
        git(aside, 'add', 'new.py')
        git(aside, 'commit', '-qm', 'made after the stop')
        for entry in aside.iterdir():
            if entry.name != '.git': entry.unlink()
        self.assertKept(aside, self.clean())

    def test_its_git_folder_goes_after_all_the_rest(self):
        copy = self.copy()
        for number in range(40): (copy / f'file{number}.txt').write_text('x')
        git(copy, 'add', '-A')
        git(copy, 'commit', '-qm', 'more files')
        git(self.project, 'fetch', '-q', str(copy), 'HEAD:refs/heads/kept')
        unlink, seen = Path.unlink, []
        def watched(path, *args, **options):
            if path.name.startswith('file'): seen.append((path.parent / '.git').is_dir())
            return unlink(path, *args, **options)
        with mock.patch.object(Path, 'unlink', watched):
            self.clean()
        self.assertEqual((len(seen), set(seen)), (40, {True}))
        self.assertRemoved(copy)

    def test_a_mark_beside_a_folder_not_moved_aside_says_nothing(self):
        copy = self.copy()
        (copy / 'app.py').unlink()
        (copy.parent / 'WAVE-1.proved').touch()
        self.assertKept(copy, self.clean())

    def test_a_mark_left_alone_goes(self):
        left = self.copy('WAVE-2')
        stale = left.parent / '.removing-other.proved'
        stale.touch()
        self.clean()
        self.assertFalse(stale.exists())
        self.assertRemoved(left)

    def test_a_folder_named_like_a_mark_stays(self):
        left = self.copy('WAVE-2')
        folder = left.parent / '.removing-mine.proved'
        folder.mkdir()
        (folder / 'left.py').write_text(UNIQUE)
        self.assertKept(folder, self.clean())
        self.assertRemoved(left)

    def test_no_mark_means_its_missing_files_count_as_changes(self):
        aside = self.stopped(self.copy())
        (aside.parent / '.removing-WAVE-1.proved').unlink()
        self.assertKept(aside, self.clean())

    def test_a_job_or_a_run_waiting_holds_the_retry_too(self):
        aside = self.stopped(self.copy())
        record = {'id': 'j', 'kind': 'fix_edit', 'project': str(self.project), 'status': 'running', 'pid': os.getpid(), 'arguments': {}}
        jobs._write(record)
        self.assertKept(aside, self.clean())
        jobs._write({**record, 'status': 'done'})
        run = Path(self.state()['workspace']) / 'runs' / 'r1'
        run.mkdir(parents=True)
        (run / 'run.json').write_text('{"id": "r1", "state": "queued"}')
        self.assertKept(aside, self.clean())
        (run / 'run.json').write_text('{"id": "r1", "state": "done"}')
        self.clean()
        self.assertEqual(list(aside.parent.iterdir()), [])

    def test_a_state_that_does_not_read_holds_the_retry_too(self):
        aside = self.stopped(self.copy())
        (Path(self.state()['workspace']) / 'state.json').write_text('{ not json')
        self.assertKept(aside, self.clean())

    def test_the_retry_runs_under_the_jobs_lock(self):
        aside = self.stopped(self.copy())
        real, seen = jobs.alone, []
        @contextlib.contextmanager
        def watched(project, *args):
            seen.append(aside.exists())
            with real(project, *args): yield
        with mock.patch.object(jobs, 'alone', watched):
            self.clean()
        self.assertEqual((set(seen), aside.exists()), ({True}, False), 'nothing goes before the lock is held')

    def test_cleaning_again_and_again_says_what_stays_and_only_that(self):
        kept, gone = self.copy('WAVE-1'), self.copy('WAVE-2')
        (kept / 'new.py').write_text(UNIQUE)
        for _ in range(3):
            said = self.clean()
            self.assertKept(kept, said)
            self.assertNotIn(str(gone), said)
            self.assertRemoved(gone)
