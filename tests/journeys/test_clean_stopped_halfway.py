"""`eaos clean`: ignored files are not disposable, and a clean stopped halfway is finished by the next."""
import contextlib
import io
import os
import shutil
from pathlib import Path
from unittest import mock
from eaos.kernel.project import jobs
from eaos.doors import cli
from eaos.features.guided.journey import copies
from tests.journeys._clean_fixture import Clean, UNIQUE, git


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
        """A real clean stopped after it proved the copy, moved it aside and removed one of its files. Returns the
        folder aside."""
        unlink = Path.unlink
        def once(path, *args, **options):
            unlink(path, *args, **options)
            if '.removing-' in str(path) and not path.name.endswith('.proved'): raise KeyboardInterrupt
        with mock.patch.object(Path, 'unlink', once), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
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
        record = {'id': 'j', 'kind': 'fix_edit', 'project': str(self.project), 'status': 'running', 'pid': os.getpid(),
                  'arguments': {}}
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
