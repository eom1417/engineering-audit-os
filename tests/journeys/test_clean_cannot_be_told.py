"""`eaos clean`: whatever it cannot prove stays, and is named, also what git would hide."""
import contextlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from unittest import mock
from eaos.kernel.project import jobs, state as project_state
from eaos.features.guided.interface import agent_tools
from eaos.features.guided.journey import copies
from tests.journeys._clean_fixture import Clean, UNIQUE, git


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
        record.write_text(json.dumps({**self.state(), 'project': str(self.root / 'moved'),
                                      'workspace': str(self.root / 'elsewhere')}))
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
        # EAOS's home inside the project, which ignores it
        (self.root / '.gitignore').write_text('*\n!.gitignore\n')
        git(self.root, 'init', '-q', '-b', 'main')
        git(self.root, 'add', '-A')
        git(self.root, 'commit', '-qm', 'first')
        agent_tools.state_of(str(self.root))
        agent_tools.choose_branch('main', str(self.root), 'here')
        folder = Path(self.state(self.root)['workspace']) / 'runtime' / 'candidates' / 'WAVE-1'
        folder.mkdir(parents=True)
        (folder / 'left.py').write_text(UNIQUE)
        self.assertKept(folder, self.clean())
        # git takes a folder this empty for no repository
        (folder / '.git').mkdir()
        self.assertKept(folder, self.clean())

    def test_a_state_an_older_eaos_wrote_with_what_it_lacks(self):
        kept, gone = self.copy('WAVE-1'), self.copy('WAVE-2')
        (kept / 'new.py').write_text(UNIQUE)
        record = self.record()
        state = self.state()
        record.write_text(json.dumps({key: state[key] for key in ('project', 'workspace')}))
        self.assertKept(kept, self.clean())
        self.assertRemoved(gone)


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
                state['open_wave'] = {'number': 1, 'root': str(copy), 'cards': [], 'kept': {}, 'failed': {},
                                      'tools': {}}
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
                             ('a run folder with no record',
                              lambda: ((runs / 'queue.json').unlink(), (runs / 'r1').mkdir()))):
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
