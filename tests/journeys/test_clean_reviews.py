"""`eaos clean`: the cases the successive reviews found, on real repositories and copies."""
import contextlib
import io
import json
import os
from pathlib import Path
from unittest import mock
from eaos.core.project import jobs, state as project_state
from eaos.interfaces import cli
from eaos.journeys.guided import copies
from tests.journeys._clean_fixture import Clean, UNIQUE, git


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
        jobs._write({'id': 'audit-1', 'kind': 'audit', 'project': str(self.project), 'status': 'running',
                     'pid': os.getpid(), 'arguments': {}})
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
