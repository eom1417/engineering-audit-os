"""Branch control and scan freshness (eaos/studio/actions/branches.py, eaos/branches.py freshness; NS46.T18, NS46.T19)
on real temporary git repositories through the command centre's own authenticated handler. These are unit checks: the
tasks themselves close only on the live trial (acceptance/test_branch_control.py, acceptance/test_scan_freshness.py)."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from eaos import branches as reading
from eaos import guided
from eaos.studio import actions
from tests.shared_fixture import Workspace


def git(folder, *args, env=None):
    done = subprocess.run(['git', '-C', str(folder), *args], capture_output=True, text=True,
                          env={**os.environ, 'GIT_AUTHOR_NAME': 'Person', 'GIT_AUTHOR_EMAIL': 'person@example.com',
                               'GIT_COMMITTER_NAME': 'Person', 'GIT_COMMITTER_EMAIL': 'person@example.com', **(env or {})})
    if done.returncode: raise AssertionError(f'git {args}: {done.stderr}')
    return done.stdout.strip()


EAOS = {'GIT_AUTHOR_NAME': 'EAOS', 'GIT_AUTHOR_EMAIL': 'eaos@localhost', 'GIT_COMMITTER_NAME': 'EAOS', 'GIT_COMMITTER_EMAIL': 'eaos@localhost'}


def commit(folder, path, text, message, env=None):
    (Path(folder) / path).parent.mkdir(parents=True, exist_ok=True)
    (Path(folder) / path).write_text(text, encoding='utf-8')
    git(folder, 'add', path)
    git(folder, 'commit', '-q', '-m', message, env=env)
    return git(folder, 'rev-parse', 'HEAD')


class Repo(Workspace):
    """main and develop with a remote origin, a tool-owned work branch (provenance), a human branch named like a tool's."""

    def setUp(self):
        super().setUp()
        self.base = Path(self.tmp)
        saved = {k: os.environ.get(k) for k in ('EAOS_HOME', 'EAOS_OUTPUT')}
        self.addCleanup(lambda: [os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v) for k, v in saved.items()])
        os.environ.update(EAOS_HOME=str(self.base / 'home'), EAOS_OUTPUT=str(self.base / 'out'))
        self.origin = self.base / 'origin.git'
        git(self.base, 'init', '-q', '--bare', '-b', 'main', str(self.origin))
        self.project = self.base / 'project'
        self.project.mkdir()
        git(self.project, 'init', '-q', '-b', 'main')
        commit(self.project, 'app.py', 'print(1)\n', 'first')
        git(self.project, 'branch', 'develop')
        git(self.project, 'remote', 'add', 'origin', str(self.origin))
        git(self.project, 'push', '-q', 'origin', 'main', 'develop')
        git(self.project, 'remote', 'set-head', 'origin', 'main')
        git(self.project, 'switch', '-q', 'develop')
        git(self.project, 'switch', '-q', '-c', 'eaos/task-1')
        self.work_tip = commit(self.project, 'feature.py', 'x = 1\n', 'work', env=EAOS)
        git(self.project, 'switch', '-q', '-c', 'eaos/not-ours', 'develop')
        commit(self.project, 'other.py', 'y = 2\n', 'human work under a tool-like name')
        git(self.project, 'switch', '-q', 'develop')
        self.app = actions.Actions(self.project, port=8765, adapters={})
        self.addCleanup(self.app.close)
        self.app.branches.record('eaos/task-1', kind='task', base='develop', base_commit=git(self.project, 'rev-parse', 'develop'),
                                 tip=self.work_tip)

    def headers(self, **extra):
        return {'X-EAOS-Token': self.app.token, 'X-EAOS-CSRF': self.app.csrf, 'Origin': 'http://127.0.0.1:8765',
                'Host': '127.0.0.1:8765', **extra}

    def post(self, path, body=None, headers=None):
        return self.app.handle('POST', path, headers or self.headers(), body or {})

    def get(self, path):
        return self.app.handle('GET', path, self.headers(), None)

    def row(self, name, kind='local'):
        status, inventory = self.get('/api/branches')
        self.assertEqual(status, 200, inventory)
        return next((r for r in inventory['branches'] if r['name'] == name and r['kind'] == kind), None)


class Inventory(Repo):
    def test_local_and_remote_refs_roles_policy_and_ownership_only_from_provenance(self):
        status, inventory = self.get('/api/branches')
        self.assertEqual(status, 200)
        names = {(r['kind'], r['name']) for r in inventory['branches']}
        self.assertLessEqual({('local', 'main'), ('local', 'develop'), ('local', 'eaos/task-1'), ('remote', 'main'), ('remote', 'develop')}, names)
        self.assertEqual(inventory['default'], {'name': 'main', 'source': 'origin/HEAD'})
        self.assertIn('main', inventory['protected'])
        self.assertEqual(self.row('eaos/task-1')['ownership']['owner'], 'eaos')
        self.assertEqual(self.row('eaos/not-ours')['ownership']['owner'], 'unknown')     # a prefix is not proof
        self.assertIn('checkout', self.row('develop')['roles'])
        self.assertEqual(self.row('eaos/task-1')['compare'], {'base': 'develop', 'ahead': 1, 'behind': 0, 'merged': False})
        self.assertEqual(self.row('main', 'remote')['remote'], 'origin')
        self.assertIn('remote_as_of', self.row('main', 'remote'))

    def test_detached_head_no_origin_dirty_checkout_and_worktree(self):
        git(self.project, 'remote', 'remove', 'origin')
        git(self.project, 'switch', '-q', '--detach', 'main')
        (self.project / 'app.py').write_text('changed\n', encoding='utf-8')
        git(self.project, 'worktree', 'add', '-q', str(self.base / 'wt'), 'eaos/task-1')
        status, inventory = self.get('/api/branches')
        self.assertEqual(status, 200)
        self.assertTrue(inventory['head']['detached'])
        self.assertIsNone(inventory['head']['branch'])
        self.assertFalse(inventory['has_origin'])
        self.assertEqual(inventory['default'], {'name': None, 'source': None})
        self.assertFalse(any(r['kind'] == 'remote' for r in inventory['branches']))
        self.assertEqual(inventory['context']['dirty'], {'tracked': 1, 'untracked': 0})
        held = self.row('eaos/task-1')['worktree']
        self.assertFalse(held['current'])
        self.assertEqual(held['dirty'], {'tracked': 0, 'untracked': 0})
        self.assertFalse(any(r['name'] == 'HEAD' for r in inventory['branches']))

    def test_provenance_is_merged_never_replaced_and_git_timeouts_are_exit_codes(self):
        self.app.branches.record('eaos/task-1', checks={'commit': self.work_tip, 'status': 'passed'})
        entry = self.app.branches._registry()['branches']['eaos/task-1']
        self.assertEqual((entry['kind'], entry['tip'], entry['checks'][0]['status']), ('task', self.work_tip, 'passed'))
        from eaos.studio.actions import branches as control
        self.assertEqual(control.git(self.project, 'log', timeout=0.000001).returncode, 124)

    def test_not_a_repository_shows_no_branches(self):
        plain = self.base / 'plain'
        plain.mkdir()
        (plain / 'package.json').write_text('{}', encoding='utf-8')
        app = actions.Actions(plain, port=8765, adapters={})
        self.addCleanup(app.close)
        inventory = app.branches.inventory()
        self.assertEqual((inventory['git'], inventory['branches']), (False, []))


class Selecting(Repo):
    def test_select_changes_context_not_the_checkout_and_records_a_run(self):
        before = git(self.project, 'rev-parse', 'HEAD'), git(self.project, 'symbolic-ref', '--short', 'HEAD')
        status, out = self.post('/api/branches/analysis', {'branch': 'main'})
        self.assertEqual(status, 200, out)
        self.assertEqual((git(self.project, 'rev-parse', 'HEAD'), git(self.project, 'symbolic-ref', '--short', 'HEAD')), before)
        self.assertEqual(out['context']['analysis']['branch'], 'main')
        self.assertEqual(out['context']['checkout']['branch'], 'develop')
        self.assertEqual(out['run']['state'], 'done')
        self.assertEqual(guided.load(self.project)['branch'], 'main')

    def test_in_flight_runs_are_never_retargeted(self):
        run = {'id': 'r1', 'action': 'explain', 'state': 'waiting_for_person', 'read': False, 'created': 'x', 'label': {'en': 'a', 'ar': 'a'},
               'context': self.app.branches.run_context()}
        self.app.store.save(run, new=True)
        status, out = self.post('/api/branches/analysis', {'branch': 'main'})
        self.assertEqual(status, 409, out)
        self.assertEqual(out['needs'], 'in_flight')
        self.assertEqual(self.app.store.load('r1')['context']['analysis_branch'], 'develop')

    def test_run_keeps_its_branch_relation_after_restart_and_deletion(self):
        run = {'id': 'r2', 'action': 'fix_finish', 'state': 'done', 'read': False, 'created': 'x', 'label': {'en': 'a', 'ar': 'a'},
               'context': self.app.branches.run_context(), 'result': {'branch': 'eaos/task-1', 'branch_tip': self.work_tip}}
        self.app.store.save(run, new=True)
        again = actions.Actions(self.project, port=8765, adapters={})
        self.addCleanup(again.close)
        self.assertEqual(again.public(again.store.load('r2'))['work_branch']['state'], 'exists')
        git(self.project, 'branch', '-q', '-D', 'eaos/task-1')
        shown = again.public(again.store.load('r2'))['work_branch']
        self.assertEqual((shown['state'], shown['recorded_tip'], shown['base']), ('deleted', self.work_tip, 'develop'))


class Merging(Repo):
    def preview(self, source='eaos/task-1', target='develop'):
        status, out = self.post('/api/branches/merge/preview', {'source': source, 'target': target})
        self.assertEqual(status, 200, out)
        return out

    def merge(self, preview, **extra):
        return self.post('/api/branches/merge', {'source': preview['source'], 'target': preview['target'], 'source_head': preview['source_head'],
                                                 'target_head': preview['target_head'], 'unchecked': preview['needs_unchecked_ack'],
                                                 'confirm': (preview['confirm'] or {}).get('token'), **extra})

    def test_isolated_preview_then_merge_with_expected_heads(self):
        develop = git(self.project, 'rev-parse', 'develop')
        preview = self.preview()
        self.assertEqual(git(self.project, 'rev-parse', 'develop'), develop)      # nothing moved
        self.assertEqual((preview['blocked'], preview['conflicts'], preview['fast_forward']), ([], [], True))
        self.assertEqual([f['path'] for f in preview['files']], ['feature.py'])
        status, out = self.merge(preview)
        self.assertEqual((status, out['needs']), (409, 'unchecked_ack'))
        status, out = self.merge(self.preview(), unchecked_ack=True)
        self.assertEqual(status, 200, out)
        self.assertEqual(git(self.project, 'rev-parse', 'develop'), self.work_tip)
        self.assertEqual(out['run']['outcome'], 'merged')

    def test_stale_head_invalidates_the_preview(self):
        preview = self.preview()
        git(self.project, 'switch', '-q', 'main')
        git(self.project, 'switch', '-q', 'eaos/task-1')
        commit(self.project, 'feature.py', 'x = 2\n', 'moved', env=EAOS)
        git(self.project, 'switch', '-q', 'main')
        status, out = self.merge(preview, unchecked_ack=True)
        self.assertEqual((status, out['needs']), (409, 'refresh'))
        self.assertEqual(git(self.project, 'rev-parse', 'develop'), preview['target_head'])

    def test_protected_destination_refused_by_the_backend(self):
        preview = self.preview(target='main')
        self.assertIn('protected_target', [r['code'] for r in preview['blocked']])
        self.assertIsNone(preview['confirm'])
        forged = {**preview, 'confirm': self.app.locks.confirm('branch_merge', {'source': 'eaos/task-1', 'target': 'main', 'source_head': preview['source_head'],
                                                                              'target_head': preview['target_head'], 'unchecked': True}, self.app.project)}
        status, out = self.merge(forged, unchecked_ack=True)
        self.assertEqual(status, 409, out)
        self.assertNotEqual(git(self.project, 'rev-parse', 'main'), self.work_tip)

    def test_human_branch_and_failed_checks_and_conflict_are_refused(self):
        self.assertIn('not_owned', [r['code'] for r in self.preview('eaos/not-ours')['blocked']])
        self.app.branches.record('eaos/task-1', checks={'commit': self.work_tip, 'status': 'failed', 'at': 'x'})
        self.assertIn('checks_failed', [r['code'] for r in self.preview()['blocked']])
        git(self.project, 'switch', '-q', 'develop')
        commit(self.project, 'feature.py', 'x = 99\n', 'conflicting')
        preview = self.preview()
        self.assertEqual(preview['conflicts'], ['feature.py'])
        status, out = self.post('/api/branches/conflict', {'source': 'eaos/task-1', 'target': 'develop', 'assistant': 'handoff'})
        self.assertEqual(status, 200, out)
        self.assertEqual(out['run']['action'], 'branch_conflict')
        self.assertEqual(git(self.project, 'rev-parse', 'eaos/task-1'), self.work_tip)

    def test_dirty_checked_out_target_is_refused(self):
        (self.project / 'app.py').write_text('unsaved\n', encoding='utf-8')
        self.assertIn('dirty_target', [r['code'] for r in self.preview()['blocked']])

    def test_one_change_at_a_time(self):
        held = self.app.branches._locked()
        try:
            status, out = self.merge(self.preview(), unchecked_ack=True)
            self.assertEqual((status, out['needs']), (409, 'refresh'))
        finally:
            held.close()


class Guarding(Repo):
    def test_auth_csrf_and_origin_failures_change_nothing(self):
        before = git(self.project, 'for-each-ref')
        for headers in ({**self.headers(), 'X-EAOS-CSRF': 'no'}, {**self.headers(), 'Origin': 'http://evil.example'},
                        {**self.headers(), 'X-EAOS-Token': 'no'}):
            status, _ = self.post('/api/branches/analysis', {'branch': 'main'}, headers)
            self.assertIn(status, (401, 403))
        self.assertEqual(git(self.project, 'for-each-ref'), before)
        self.assertIsNone((guided.load(self.project) or {}).get('branch'))

    def test_invalid_names_cannot_escape_or_run_code(self):
        marker = self.base / 'pwned'
        for name in (f'x;touch {marker}', '--output=/tmp/x', '../../etc', 'a..b', '$(touch x)', 'refs/heads/../x', ''):
            status, _ = self.post('/api/branches/merge/preview', {'source': name, 'target': 'develop'})
            self.assertIn(status, (400, 404, 409), name)
        self.assertFalse(marker.exists())

    def test_the_project_is_the_servers_own_never_the_bodys(self):
        other = self.base / 'other'
        other.mkdir()
        git(other, 'init', '-q', '-b', 'main')
        commit(other, 'a', 'a', 'a')
        status, out = self.post('/api/branches/analysis', {'branch': 'main', 'project': str(other)})
        self.assertEqual(status, 200, out)
        self.assertIsNone(guided.load(other))


class Deleting(Repo):
    def preview(self, **body):
        status, out = self.post('/api/branches/delete/preview', body)
        self.assertEqual(status, 200, out)
        return out

    def test_merged_branch_deleted_with_recovery_and_restored(self):
        git(self.project, 'merge', '-q', '--ff-only', 'eaos/task-1')
        preview = self.preview(branch='eaos/task-1')
        self.assertFalse(preview['unmerged'])
        self.assertIsNone(preview['confirm_unmerged'])
        status, out = self.post('/api/branches/delete', {'branch': 'eaos/task-1', 'tip': preview['tip'], 'unmerged': False, 'confirm': preview['confirm']['token']})
        self.assertEqual(status, 200, out)
        recovery = out['run']['result']['recovery']
        self.assertEqual(git(self.project, 'rev-parse', f'refs/eaos-recovery/{recovery}'), self.work_tip)
        self.assertIsNone(self.row('eaos/task-1'))
        status, out = self.post('/api/branches/restore', {'recovery': recovery})
        self.assertEqual(status, 200, out)
        self.assertEqual(git(self.project, 'rev-parse', 'eaos/task-1'), self.work_tip)

    def test_unmerged_needs_a_second_confirmation(self):
        preview = self.preview(branch='eaos/task-1')
        self.assertTrue(preview['unmerged'])
        self.assertEqual([c['commit'] for c in preview['lost_commits']], [self.work_tip])
        body = {'branch': 'eaos/task-1', 'tip': preview['tip'], 'unmerged': True, 'confirm': preview['confirm']['token']}
        status, out = self.post('/api/branches/delete', body)
        self.assertEqual((status, out['needs']), (403, 'confirm_unmerged'))
        self.assertEqual(git(self.project, 'rev-parse', 'eaos/task-1'), self.work_tip)
        preview = self.preview(branch='eaos/task-1')
        status, out = self.post('/api/branches/delete', {**body, 'confirm': preview['confirm']['token'], 'confirm_unmerged': preview['confirm_unmerged']['token']})
        self.assertEqual(status, 200, out)

    def test_human_protected_and_checked_out_branches_are_never_deleted(self):
        for name, code in (('eaos/not-ours', 'not_owned'), ('develop', 'not_owned'), ('main', 'protected')):
            self.assertIn(code, [r['code'] for r in self.preview(branch=name)['blocked']], name)
        git(self.project, 'switch', '-q', 'eaos/task-1')
        self.assertIn('checked_out', [r['code'] for r in self.preview(branch='eaos/task-1')['blocked']])

    def test_remote_deletion_is_its_own_consent(self):
        git(self.project, 'push', '-q', 'origin', 'eaos/task-1')
        git(self.project, 'fetch', '-q', 'origin')
        local = self.preview(branch='eaos/task-1')
        status, out = self.post('/api/branches/delete', {'branch': 'eaos/task-1', 'where': 'remote', 'remote': 'origin', 'tip': self.work_tip,
                                                         'confirm': local['confirm']['token']})
        self.assertEqual((status, out['needs']), (403, 'confirm'))
        self.assertTrue(git(self.origin, 'rev-parse', '--verify', 'eaos/task-1'))
        remote = self.preview(branch='eaos/task-1', where='remote', remote='origin')
        self.assertTrue(remote['local_kept'])
        status, out = self.post('/api/branches/delete', {'branch': 'eaos/task-1', 'where': 'remote', 'remote': 'origin', 'tip': remote['tip'],
                                                         'confirm': remote['confirm']['token']})
        self.assertEqual(status, 200, out)
        self.assertFalse(subprocess.run(['git', '-C', str(self.origin), 'rev-parse', '--verify', '--quiet', 'refs/heads/eaos/task-1']).returncode == 0)
        self.assertEqual(git(self.project, 'rev-parse', 'eaos/task-1'), self.work_tip)     # the local branch stays


class Freshness(Repo):
    def scanned(self, **extra):
        state = {'schema_version': 1, 'project': str(self.project), 'workspace': str(guided.workspace(self.project)), 'questions': [],
                 'scanned': '2026-10-09T08:00:00+00:00', 'scanned_commit': git(self.project, 'rev-parse', 'HEAD'),
                 **reading.scan_provenance({'project': str(self.project)}, self.project), **extra}
        guided.save(state)
        return state

    def fresh(self):
        status, out = self.get('/api/freshness')
        self.assertEqual(status, 200, out)
        return out['freshness']

    def test_records_branch_commit_and_dirty_state(self):
        state = self.scanned()
        self.assertEqual((state['scanned_branch'], state['scanned_detached'], state['scanned_dirty']), ('develop', False, False))
        self.assertEqual(len(state['scanned_commit']), 40)
        self.assertEqual(self.fresh()['state'], 'fresh')

    def test_behind_with_files_then_dirty_then_rewritten(self):
        self.scanned()
        commit(self.project, 'new.py', 'z\n', 'later')
        found = self.fresh()
        self.assertEqual((found['state'], found['behind']['commits'], found['behind']['file_list']), ('behind', 1, ['new.py']))
        git(self.project, 'reset', '-q', '--hard', 'HEAD~1')
        (self.project / 'app.py').write_text('unsaved\n', encoding='utf-8')
        self.assertEqual(self.fresh()['state'], 'dirty')
        git(self.project, 'checkout', '-q', '--', 'app.py')
        git(self.project, 'commit', '-q', '--amend', '-m', 'rewritten')
        self.assertEqual(self.fresh()['state'], 'rewritten')

    def test_detached_head_legacy_and_other_branch(self):
        git(self.project, 'switch', '-q', '--detach', 'main')
        state = self.scanned()
        self.assertEqual((state['scanned_branch'], state['scanned_detached']), (None, True))
        self.assertEqual(self.fresh()['state'], 'fresh')
        git(self.project, 'switch', '-q', 'develop')
        self.scanned()
        guided.save({**guided.load(self.project), 'branch': 'main'})
        self.assertEqual(self.fresh()['state'], 'other_branch')
        legacy = {k: v for k, v in guided.load(self.project).items() if k not in ('scanned_commit', 'scanned_branch', 'scanned_detached', 'scanned_dirty')}
        guided.save(legacy)
        found = self.fresh()
        self.assertEqual((found['state'], found['reason']), ('unknown', 'legacy_report'))


if __name__ == '__main__':
    unittest.main()
