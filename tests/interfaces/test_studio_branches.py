"""Branch control and scan freshness (eaos/interfaces/studio_actions/branches/, eaos/core/project/branches.py freshness) on real temporary
git repositories through the command centre's own authenticated handler."""
import json
import os
import subprocess
import unittest
from pathlib import Path

from eaos.core.project import branches as reading
from eaos.journeys import guided
from eaos.interfaces import studio_actions as actions
from tests.shared_fixture import Workspace
from eaos.core.project import state as project_state


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
    def test_local_and_remote_refs_roles_policy_and_ownership_only_from_merged_provenance(self):
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
        self.app.branches.record('eaos/task-1', checks={'commit': self.work_tip, 'status': 'passed'})
        entry = self.app.branches._registry()['branches']['eaos/task-1']
        self.assertEqual((entry['kind'], entry['tip'], entry['checks'][0]['status']), ('task', self.work_tip, 'passed'), 'merged, never replaced')
        from eaos.interfaces.studio_actions import branches as control
        self.assertEqual(control.git(self.project, 'log', timeout=0.000001).returncode, 124, 'a git timeout is an exit code')

    def test_detached_head_no_origin_dirty_checkout_worktree_and_no_repository(self):
        git(self.project, 'remote', 'remove', 'origin')
        git(self.project, 'switch', '-q', '--detach', 'main')
        (self.project / 'app.py').write_text('changed\n', encoding='utf-8')
        git(self.project, 'worktree', 'add', '-q', str(self.base / 'wt'), 'eaos/task-1')
        status, inventory = self.get('/api/branches')
        self.assertEqual(status, 200)
        self.assertEqual((inventory['head']['detached'], inventory['head']['branch'], inventory['has_origin']), (True, None, False))
        self.assertEqual(inventory['default'], {'name': None, 'source': None})
        self.assertFalse(any(r['kind'] == 'remote' for r in inventory['branches']))
        self.assertEqual(inventory['context']['dirty'], {'tracked': 1, 'untracked': 0})
        held = self.row('eaos/task-1')['worktree']
        self.assertEqual((held['current'], held['dirty']), (False, {'tracked': 0, 'untracked': 0}))
        self.assertFalse(any(r['name'] == 'HEAD' for r in inventory['branches']))
        plain = self.base / 'plain'
        plain.mkdir()
        (plain / 'package.json').write_text('{}', encoding='utf-8')
        app = actions.Actions(plain, port=8765, adapters={})
        self.addCleanup(app.close)
        inventory = app.branches.inventory()
        self.assertEqual((inventory['git'], inventory['branches']), (False, []))


class Selecting(Repo):
    def test_choosing_the_branch_to_analyse_changes_the_context_never_the_checkout(self):
        before = git(self.project, 'rev-parse', 'HEAD'), git(self.project, 'symbolic-ref', '--short', 'HEAD')
        status, out = self.post('/api/branches/analysis', {'branch': 'main'})
        self.assertEqual(status, 200, out)
        self.assertEqual((git(self.project, 'rev-parse', 'HEAD'), git(self.project, 'symbolic-ref', '--short', 'HEAD')), before)
        self.assertEqual((out['context']['analysis']['branch'], out['context']['checkout']['branch']), ('main', 'develop'))
        self.assertEqual(out['run']['state'], 'done')
        self.assertEqual(project_state.load(self.project)['branch'], 'main')
        made = []
        create, public = self.app.create, self.app.public
        self.app.create = lambda body: made.append(body) or {'id': 'r9', 'action': 'audit', 'state': 'queued'}
        self.app.public = lambda run: run
        status, out = self.post('/api/branches/analysis', {'branch': 'main', 'scan': True})
        self.assertEqual(status, 200, out)
        self.assertEqual(made, [{'action': 'audit', 'inputs': {'fresh': True}}], 'select and scan asks for a new check')
        self.app.create, self.app.public = create, public
        run = {'id': 'r3', 'action': 'report_decision', 'mode': 'handoff', 'state': 'waiting_for_person', 'read': False, 'created': 'x',
               'label': {'en': 'Review owner answer', 'ar': 'مراجعة إجابة المالك'}, 'context': self.app.branches.run_context()}
        self.app.store.save(run, new=True)
        status, out = self.post('/api/branches/analysis', {'branch': 'main'})
        self.assertEqual(status, 200, out)
        self.assertEqual((out['context']['analysis']['branch'], self.app.store.load('r3')['state']), ('main', 'waiting_for_person'),
                         'rescanning the branch already analysed waits for no run')

    def test_work_in_flight_is_never_retargeted_and_a_run_keeps_its_branch_after_restart_and_deletion(self):
        run = {'id': 'r1', 'action': 'explain', 'state': 'waiting_for_person', 'read': False, 'created': 'x', 'label': {'en': 'a', 'ar': 'a'},
               'context': self.app.branches.run_context()}
        self.app.store.save(run, new=True)
        status, out = self.post('/api/branches/analysis', {'branch': 'main'})
        self.assertEqual((status, out['needs']), (409, 'in_flight'))
        self.assertEqual(self.app.store.load('r1')['context']['analysis_branch'], 'develop')
        reason = out['reasons'][0]
        self.assertEqual(reason['runs'], [{'id': 'r1', 'label': {'en': 'a', 'ar': 'a'}}], 'the refusal names the work and offers its stop')
        self.assertIn('فيه شغل ما خلص على الفرع الحالي: a.', reason['ar'])
        self.assertNotIn('r1', reason['ar'] + reason['en'], 'plain words, never an id')
        done = {'id': 'r2', 'action': 'fix_finish', 'state': 'done', 'read': False, 'created': 'x', 'label': {'en': 'a', 'ar': 'a'},
                'context': self.app.branches.run_context(), 'result': {'branch': 'eaos/task-1', 'branch_tip': self.work_tip}}
        self.app.store.save(done, new=True)
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

    def test_an_isolated_preview_then_a_merge_at_the_expected_heads_one_at_a_time(self):
        develop = git(self.project, 'rev-parse', 'develop')
        preview = self.preview()
        self.assertEqual(git(self.project, 'rev-parse', 'develop'), develop)      # nothing moved
        self.assertEqual((preview['blocked'], preview['conflicts'], preview['fast_forward']), ([], [], True))
        self.assertEqual([f['path'] for f in preview['files']], ['feature.py'])
        self.assertEqual(self.merge(preview)[1]['needs'], 'unchecked_ack')
        held = self.app.branches._locked()
        try:
            status, out = self.merge(self.preview(), unchecked_ack=True)
            self.assertEqual((status, out['needs']), (409, 'refresh'), 'one change at a time')
        finally:
            held.close()
        stale = self.preview()
        git(self.project, 'switch', '-q', 'eaos/task-1')
        moved = commit(self.project, 'feature.py', 'x = 2\n', 'moved', env=EAOS)
        git(self.project, 'switch', '-q', 'develop')
        status, out = self.merge(stale, unchecked_ack=True)
        self.assertEqual((status, out['needs']), (409, 'refresh'), 'a head that moved invalidates the preview')
        self.assertEqual(git(self.project, 'rev-parse', 'develop'), develop)
        status, out = self.merge(self.preview(), unchecked_ack=True)
        self.assertEqual(status, 200, out)
        self.assertEqual(git(self.project, 'rev-parse', 'develop'), moved)
        self.assertEqual(out['run']['outcome'], 'merged')

    def test_a_protected_dirty_failed_or_conflicting_merge_is_refused_and_a_persons_branch_merges_on_their_confirmation(self):
        preview = self.preview(target='main')
        self.assertIn('protected_target', [r['code'] for r in preview['blocked']])
        self.assertIsNone(preview['confirm'])
        forged = {**preview, 'confirm': self.app.locks.confirm('branch_merge', {'source': 'eaos/task-1', 'target': 'main', 'source_head': preview['source_head'],
                                                                              'target_head': preview['target_head'], 'unchecked': True}, self.app.project)}
        self.assertEqual(self.merge(forged, unchecked_ack=True)[0], 409, 'refused by the backend, not only the page')
        self.assertNotEqual(git(self.project, 'rev-parse', 'main'), self.work_tip)
        human = self.preview('eaos/not-ours')
        self.assertEqual(human['blocked'], [])                       # their repository: their confirmation decides
        self.assertTrue(human['confirm'])
        (self.project / 'app.py').write_text('unsaved\n', encoding='utf-8')
        self.assertIn('dirty_target', [r['code'] for r in self.preview()['blocked']])
        git(self.project, 'checkout', '--', 'app.py')
        self.app.branches.record('eaos/task-1', checks={'commit': self.work_tip, 'status': 'failed', 'at': 'x'})
        self.assertIn('checks_failed', [r['code'] for r in self.preview()['blocked']])
        commit(self.project, 'feature.py', 'x = 99\n', 'conflicting')
        self.assertEqual(self.preview()['conflicts'], ['feature.py'])
        status, out = self.post('/api/branches/conflict', {'source': 'eaos/task-1', 'target': 'develop', 'assistant': 'handoff'})
        self.assertEqual((status, out['run']['action']), (200, 'branch_conflict'))
        self.assertEqual(git(self.project, 'rev-parse', 'eaos/task-1'), self.work_tip)


class Guarding(Repo):
    def test_refused_requests_and_hostile_names_change_nothing_and_the_project_is_the_servers_own(self):
        before = git(self.project, 'for-each-ref')
        for headers in ({**self.headers(), 'X-EAOS-CSRF': 'no'}, {**self.headers(), 'Origin': 'http://evil.example'},
                        {**self.headers(), 'X-EAOS-Token': 'no'}):
            self.assertIn(self.post('/api/branches/analysis', {'branch': 'main'}, headers)[0], (401, 403))
        self.assertEqual(git(self.project, 'for-each-ref'), before)
        self.assertIsNone((project_state.load(self.project) or {}).get('branch'))
        marker = self.base / 'pwned'
        for name in (f'x;touch {marker}', '--output=/tmp/x', '../../etc', 'a..b', '$(touch x)', 'refs/heads/../x', ''):
            self.assertIn(self.post('/api/branches/merge/preview', {'source': name, 'target': 'develop'})[0], (400, 404, 409), name)
        self.assertFalse(marker.exists())
        other = self.base / 'other'
        other.mkdir()
        git(other, 'init', '-q', '-b', 'main')
        commit(other, 'a', 'a', 'a')
        status, out = self.post('/api/branches/analysis', {'branch': 'main', 'project': str(other)})
        self.assertEqual(status, 200, out)
        self.assertIsNone(project_state.load(other))


class Deleting(Repo):
    def preview(self, **body):
        status, out = self.post('/api/branches/delete/preview', body)
        self.assertEqual(status, 200, out)
        return out

    def delete(self, branch, tip, preview, **extra):
        body = {'branch': branch, 'tip': tip, 'unmerged': preview['unmerged'], 'confirm': preview['confirm']['token'], **extra}
        return self.post('/api/branches/delete', body)

    def test_a_deleted_branch_is_kept_for_recovery_and_an_unmerged_one_needs_a_second_confirmation(self):
        preview = self.preview(branch='eaos/task-1')
        self.assertTrue(preview['unmerged'])
        self.assertEqual([c['commit'] for c in preview['lost_commits']], [self.work_tip])
        status, out = self.delete('eaos/task-1', preview['tip'], preview)
        self.assertEqual((status, out['needs']), (403, 'confirm_unmerged'))
        self.assertEqual(git(self.project, 'rev-parse', 'eaos/task-1'), self.work_tip)
        git(self.project, 'merge', '-q', '--ff-only', 'eaos/task-1')
        preview = self.preview(branch='eaos/task-1')
        self.assertEqual((preview['unmerged'], preview['confirm_unmerged']), (False, None))
        status, out = self.delete('eaos/task-1', preview['tip'], preview)
        self.assertEqual(status, 200, out)
        recovery = out['run']['result']['answer']['recovery']
        self.assertEqual(git(self.project, 'rev-parse', f'refs/eaos-recovery/{recovery}'), self.work_tip)
        self.assertIsNone(self.row('eaos/task-1'))
        self.assertEqual(self.post('/api/branches/restore', {'recovery': recovery})[0], 200)
        self.assertEqual(git(self.project, 'rev-parse', 'eaos/task-1'), self.work_tip)
        tip = git(self.project, 'rev-parse', 'eaos/not-ours')
        preview = self.preview(branch='eaos/not-ours')
        self.assertEqual((preview['blocked'], preview['whose']['code'], preview['unmerged']), ([], 'yours', True))
        status, out = self.delete('eaos/not-ours', tip, preview, worktree=False, confirm_unmerged=preview['confirm_unmerged']['token'])
        self.assertEqual(status, 200, out)
        self.assertIsNone(self.row('eaos/not-ours'))
        self.assertEqual(self.post('/api/branches/restore', {'recovery': out['run']['result']['answer']['recovery']})[0], 200)
        self.assertEqual(git(self.project, 'rev-parse', 'eaos/not-ours'), tip)

    def test_protected_checked_out_and_dirty_worktree_branches_stay_and_a_clean_worktree_goes_with_its_branch(self):
        for name, code in (('develop', 'checked_out'), ('main', 'protected')):
            self.assertIn(code, [r['code'] for r in self.preview(branch=name)['blocked']], name)
        folder = self.base / 'wt'
        git(self.project, 'worktree', 'add', '-q', str(folder), 'eaos/task-1')
        (folder / 'feature.py').write_text('unsaved\n', encoding='utf-8')
        self.assertIn('worktree_dirty', [r['code'] for r in self.preview(branch='eaos/task-1')['blocked']])
        git(folder, 'checkout', '--', 'feature.py')
        preview = self.preview(branch='eaos/task-1')
        self.assertEqual(preview['blocked'], [])
        self.assertTrue(preview['worktree'])
        stale = {'worktree': False, 'confirm_unmerged': preview['confirm_unmerged']['token']}
        self.assertEqual(self.delete('eaos/task-1', self.work_tip, preview, **stale)[0], 403, 'the worktree is part of what was confirmed')
        preview = self.preview(branch='eaos/task-1')
        status, out = self.delete('eaos/task-1', self.work_tip, preview, worktree=True, confirm_unmerged=preview['confirm_unmerged']['token'])
        self.assertEqual(status, 200, out)
        self.assertFalse(folder.exists())
        self.assertIsNone(self.row('eaos/task-1'))

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
        self.assertNotEqual(subprocess.run(['git', '-C', str(self.origin), 'rev-parse', '--verify', '--quiet', 'refs/heads/eaos/task-1']).returncode, 0)
        self.assertEqual(git(self.project, 'rev-parse', 'eaos/task-1'), self.work_tip)     # the local branch stays


class CleaningUp(Repo):
    """One step removes every merged branch and old clean worktree, and nothing else; each branch stays restorable."""

    def preview(self):
        status, out = self.post('/api/branches/cleanup/preview')
        self.assertEqual(status, 200, out)
        return out

    def test_merged_branches_and_clean_detached_worktrees_go_unmerged_and_dirty_stay_and_only_the_previewed_set(self):
        git(self.project, 'branch', 'merged-a', 'develop')
        git(self.project, 'branch', 'merged-b', 'main')
        git(self.project, 'branch', 'held', 'develop')
        held = self.base / 'held'
        git(self.project, 'worktree', 'add', '-q', str(held), 'held')
        dirty = self.base / 'dirty'
        git(self.project, 'branch', 'busy', 'develop')
        git(self.project, 'worktree', 'add', '-q', str(dirty), 'busy')
        (dirty / 'note.txt').write_text('unsaved\n', encoding='utf-8')
        old = self.base / 'old'
        git(self.project, 'worktree', 'add', '-q', '--detach', str(old), 'develop')
        preview = self.preview()
        self.assertEqual(sorted(b['branch'] for b in preview['branches']), ['held', 'merged-a', 'merged-b'])
        self.assertEqual([w['prunable'] for w in preview['worktrees']], [False])
        stays = {row['branch']: [r['code'] for r in row['reasons']] for row in preview['kept']}
        self.assertIn('not_merged', stays['eaos/task-1'])
        self.assertIn('not_merged', stays['eaos/not-ours'])
        self.assertIn('worktree_dirty', stays['busy'])
        self.assertNotIn('develop', stays)                                  # the base and protected branches are never listed
        self.assertEqual(sorted(preview['kept_branches']), ['develop', 'main'])
        status, out = self.post('/api/branches/cleanup', {'digest': '0' * 64, 'confirm': preview['confirm']['token']})
        self.assertEqual((status, out['needs']), (403, 'confirm'), 'a forged digest needs its own confirmation')
        preview = self.preview()
        git(self.project, 'branch', 'merged-c', 'develop')
        status, out = self.post('/api/branches/cleanup', {'digest': preview['digest'], 'confirm': preview['confirm']['token']})
        self.assertEqual((status, out['needs']), (409, 'refresh'), 'a change after the preview changes nothing')
        self.assertTrue(git(self.project, 'rev-parse', 'merged-a'))
        git(self.project, 'branch', '-D', 'merged-c')
        preview = self.preview()
        status, out = self.post('/api/branches/cleanup', {'digest': preview['digest'], 'confirm': preview['confirm']['token']})
        self.assertEqual(status, 200, out)
        answer = out['run']['result']['answer']
        self.assertEqual((sorted(d['branch'] for d in answer['deleted']), answer['failed']), (['held', 'merged-a', 'merged-b'], []))
        left = git(self.project, 'for-each-ref', '--format=%(refname:short)', 'refs/heads').split()
        self.assertEqual(sorted(left), ['busy', 'develop', 'eaos/not-ours', 'eaos/task-1', 'main'])
        self.assertFalse(held.exists() or old.exists())
        self.assertEqual((dirty / 'note.txt').read_text(encoding='utf-8'), 'unsaved\n')
        recovery = next(d['recovery'] for d in answer['deleted'] if d['branch'] == 'merged-a')
        self.assertEqual(self.post('/api/branches/restore', {'recovery': recovery})[0], 200)
        self.assertEqual(git(self.project, 'rev-parse', 'merged-a'), git(self.project, 'rev-parse', 'develop'))


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

    def test_a_check_is_fresh_behind_dirty_rewritten_on_another_branch_or_unknown(self):
        state = self.scanned()
        self.assertEqual((state['scanned_branch'], state['scanned_detached'], state['scanned_dirty'], len(state['scanned_commit'])),
                         ('develop', False, False, 40))
        self.assertEqual(self.fresh()['state'], 'fresh')
        commit(self.project, 'new.py', 'z\n', 'later')
        found = self.fresh()
        self.assertEqual((found['state'], found['behind']['commits'], found['behind']['file_list']), ('behind', 1, ['new.py']))
        git(self.project, 'reset', '-q', '--hard', 'HEAD~1')
        (self.project / 'app.py').write_text('unsaved\n', encoding='utf-8')
        self.assertEqual(self.fresh()['state'], 'dirty')
        git(self.project, 'checkout', '-q', '--', 'app.py')
        git(self.project, 'commit', '-q', '--amend', '-m', 'rewritten')
        self.assertEqual(self.fresh()['state'], 'rewritten')
        git(self.project, 'switch', '-q', '--detach', 'main')
        state = self.scanned()
        self.assertEqual((state['scanned_branch'], state['scanned_detached']), (None, True))
        self.assertEqual(self.fresh()['state'], 'fresh')
        git(self.project, 'switch', '-q', 'develop')
        self.scanned()
        guided.save({**project_state.load(self.project), 'branch': 'main'})
        self.assertEqual(self.fresh()['state'], 'other_branch')
        self.app.studio = self.base / 'studio'
        self.app.studio.mkdir(exist_ok=True)
        (self.app.studio / 'manifest.json').write_text(json.dumps({'scanned': {'branch': 'develop', 'commit': git(self.project, 'rev-parse', 'develop'),
                                                                              'at': '2026-10-09T08:00:00+00:00', 'recorded': True, 'detached': False}}))
        guided.choose(project_state.load(self.project), 'eaos/task-1')
        found = self.fresh()
        self.assertEqual((found['state'], found['scanned_branch'], found['branch']), ('other_branch', 'develop', 'eaos/task-1'))
        guided.choose(project_state.load(self.project), 'main')
        legacy = {k: v for k, v in project_state.load(self.project).items() if k not in ('scanned_commit', 'scanned_branch', 'scanned_detached', 'scanned_dirty')}
        guided.save(legacy)
        found = self.fresh()
        self.assertEqual((found['state'], found['reason']), ('unknown', 'legacy_report'))


if __name__ == '__main__':
    unittest.main()
