"""`eaos clean` removes a copy only when it is proved to hold nothing of anyone's: no work open or waiting on it,
no change uncommitted, no commit that exists nowhere else. Real repositories, copies and states, through the command
itself."""
import json
import os
import shutil
from pathlib import Path
from unittest import mock
from eaos.kernel.project import jobs, state as project_state
from tests.journeys._clean_fixture import Clean, UNIQUE, git


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
        state['by_branch'] = {'feature': {'open_wave': {'number': 1, 'root': str(copy), 'cards': [], 'kept': {},
                                                        'failed': {}, 'tools': {}}}}
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
        jobs._write({'id': 'fix_edit-1', 'kind': 'fix_edit', 'project': str(self.project), 'status': status,
                     'pid': os.getpid(), 'arguments': {}})

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
        self.assertEqual((git(self.project, 'for-each-ref'), sorted(p.name for p in self.project.iterdir())),
                         (refs, files))
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
        jobs._write({'id': 'fix_edit-1', 'kind': 'fix_edit', 'project': str(self.project), 'status': 'running',
                     'pid': os.getpid(), 'arguments': {}})
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
        jobs._write({'id': 'audit-1', 'kind': 'audit', 'project': str(self.project), 'status': 'running',
                     'pid': os.getpid(), 'arguments': {}})
        said = self.clean('--pictures')
        self.assertTrue(session.is_file())
        self.assertTrue(pictures.is_dir())
        self.assertIn(str(guided_outputs / 'technical'), said)
