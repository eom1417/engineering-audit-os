"""Branch control (eaos/features/studio/journey/branches/, eaos/kernel/project/branches.py freshness): deleting, cleaning up, and scan
freshness on real temporary git repositories."""
import json
import subprocess
import unittest
from eaos.kernel.project import branches as reading
from eaos.features.guided import journey as guided
from eaos.kernel.project import state as project_state
from tests.interfaces._studio_branches_fixture import Repo, commit, git


class Deleting(Repo):
    def preview(self, **body):
        status, out = self.post('/api/branches/delete/preview', body)
        self.assertEqual(status, 200, out)
        return out

    def delete(self, branch, tip, preview, **extra):
        body = {'branch': branch, 'tip': tip, 'unmerged': preview['unmerged'], 'confirm': preview['confirm']['token'],
                **extra}
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
        status, out = self.delete('eaos/not-ours', tip, preview, worktree=False,
                                  confirm_unmerged=preview['confirm_unmerged']['token'])
        self.assertEqual(status, 200, out)
        self.assertIsNone(self.row('eaos/not-ours'))
        self.assertEqual(self.post('/api/branches/restore',
                                   {'recovery': out['run']['result']['answer']['recovery']})[0], 200)
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
        self.assertEqual(self.delete('eaos/task-1', self.work_tip, preview, **stale)[0], 403,
                         'the worktree is part of what was confirmed')
        preview = self.preview(branch='eaos/task-1')
        status, out = self.delete('eaos/task-1', self.work_tip, preview, worktree=True,
                                  confirm_unmerged=preview['confirm_unmerged']['token'])
        self.assertEqual(status, 200, out)
        self.assertFalse(folder.exists())
        self.assertIsNone(self.row('eaos/task-1'))

    def test_remote_deletion_is_its_own_consent(self):
        git(self.project, 'push', '-q', 'origin', 'eaos/task-1')
        git(self.project, 'fetch', '-q', 'origin')
        local = self.preview(branch='eaos/task-1')
        status, out = self.post('/api/branches/delete',
                                {'branch': 'eaos/task-1', 'where': 'remote', 'remote': 'origin', 'tip': self.work_tip,
                                 'confirm': local['confirm']['token']})
        self.assertEqual((status, out['needs']), (403, 'confirm'))
        self.assertTrue(git(self.origin, 'rev-parse', '--verify', 'eaos/task-1'))
        remote = self.preview(branch='eaos/task-1', where='remote', remote='origin')
        self.assertTrue(remote['local_kept'])
        status, out = self.post('/api/branches/delete',
                                {'branch': 'eaos/task-1', 'where': 'remote', 'remote': 'origin', 'tip': remote['tip'],
                                 'confirm': remote['confirm']['token']})
        self.assertEqual(status, 200, out)
        self.assertNotEqual(subprocess.run(['git', '-C', str(self.origin), 'rev-parse', '--verify', '--quiet',
                                            'refs/heads/eaos/task-1']).returncode, 0)
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
        self.assertNotIn('develop',
                         stays)                                  # the base and protected branches are never listed
        self.assertEqual(sorted(preview['kept_branches']), ['develop', 'main'])
        status, out = self.post('/api/branches/cleanup', {'digest': '0' * 64, 'confirm': preview['confirm']['token']})
        self.assertEqual((status, out['needs']), (403, 'confirm'), 'a forged digest needs its own confirmation')
        preview = self.preview()
        git(self.project, 'branch', 'merged-c', 'develop')
        status, out = self.post('/api/branches/cleanup',
                                {'digest': preview['digest'], 'confirm': preview['confirm']['token']})
        self.assertEqual((status, out['needs']), (409, 'refresh'), 'a change after the preview changes nothing')
        self.assertTrue(git(self.project, 'rev-parse', 'merged-a'))
        git(self.project, 'branch', '-D', 'merged-c')
        preview = self.preview()
        status, out = self.post('/api/branches/cleanup',
                                {'digest': preview['digest'], 'confirm': preview['confirm']['token']})
        self.assertEqual(status, 200, out)
        answer = out['run']['result']['answer']
        self.assertEqual((sorted(d['branch'] for d in answer['deleted']), answer['failed']),
                         (['held', 'merged-a', 'merged-b'], []))
        left = git(self.project, 'for-each-ref', '--format=%(refname:short)', 'refs/heads').split()
        self.assertEqual(sorted(left), ['busy', 'develop', 'eaos/not-ours', 'eaos/task-1', 'main'])
        self.assertFalse(held.exists() or old.exists())
        self.assertEqual((dirty / 'note.txt').read_text(encoding='utf-8'), 'unsaved\n')
        recovery = next(d['recovery'] for d in answer['deleted'] if d['branch'] == 'merged-a')
        self.assertEqual(self.post('/api/branches/restore', {'recovery': recovery})[0], 200)
        self.assertEqual(git(self.project, 'rev-parse', 'merged-a'), git(self.project, 'rev-parse', 'develop'))


class Freshness(Repo):
    def scanned(self, **extra):
        state = {'schema_version': 1, 'project': str(self.project), 'workspace': str(guided.workspace(self.project)),
                 'questions': [],
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
        self.assertEqual((state['scanned_branch'], state['scanned_detached'], state['scanned_dirty'],
                          len(state['scanned_commit'])),
                         ('develop', False, False, 40))
        self.assertEqual(self.fresh()['state'], 'fresh')
        commit(self.project, 'new.py', 'z\n', 'later')
        found = self.fresh()
        self.assertEqual((found['state'], found['behind']['commits'], found['behind']['file_list']),
                         ('behind', 1, ['new.py']))
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
        (self.app.studio / 'manifest.json').write_text(json.dumps({'scanned': {'branch': 'develop',
                                                                               'commit': git(self.project, 'rev-parse',
                                                                                             'develop'),
                                                                              'at': '2026-10-09T08:00:00+00:00',
                                                                              'recorded': True, 'detached': False}}))
        guided.choose(project_state.load(self.project), 'eaos/task-1')
        found = self.fresh()
        self.assertEqual((found['state'], found['scanned_branch'], found['branch']),
                         ('other_branch', 'develop', 'eaos/task-1'))
        guided.choose(project_state.load(self.project), 'main')
        legacy = {k: v for k, v in project_state.load(self.project).items()
                  if k not in ('scanned_commit', 'scanned_branch', 'scanned_detached', 'scanned_dirty')}
        guided.save(legacy)
        found = self.fresh()
        self.assertEqual((found['state'], found['reason']), ('unknown', 'legacy_report'))


if __name__ == '__main__':
    unittest.main()
