"""Branch control (eaos/journeys/branches/): reading, selecting, merging and guarding branches on real temporary git
repositories through the server's own authenticated handler."""
import unittest
from eaos.interfaces import runs as actions
from eaos.core.project import state as project_state
from tests.interfaces._studio_branches_fixture import EAOS, Repo, commit, git


class Inventory(Repo):
    def test_local_and_remote_refs_roles_policy_and_ownership_only_from_merged_provenance(self):
        status, inventory = self.get('/api/branches')
        self.assertEqual(status, 200)
        names = {(r['kind'], r['name']) for r in inventory['branches']}
        self.assertLessEqual({('local', 'main'), ('local', 'develop'), ('local', 'eaos/task-1'), ('remote', 'main'),
                              ('remote', 'develop')}, names)
        self.assertEqual(inventory['default'], {'name': 'main', 'source': 'origin/HEAD'})
        self.assertIn('main', inventory['protected'])
        self.assertEqual(self.row('eaos/task-1')['ownership']['owner'], 'eaos')
        self.assertEqual(self.row('eaos/not-ours')['ownership']['owner'], 'unknown')     # a prefix is not proof
        self.assertIn('checkout', self.row('develop')['roles'])
        self.assertEqual(self.row('eaos/task-1')['compare'],
                         {'base': 'develop', 'ahead': 1, 'behind': 0, 'merged': False})
        self.assertEqual(self.row('main', 'remote')['remote'], 'origin')
        self.assertIn('remote_as_of', self.row('main', 'remote'))
        self.app.branches.record('eaos/task-1', checks={'commit': self.work_tip, 'status': 'passed'})
        entry = self.app.branches._registry()['branches']['eaos/task-1']
        self.assertEqual((entry['kind'], entry['tip'], entry['checks'][0]['status']), ('task', self.work_tip, 'passed'),
                         'merged, never replaced')
        from eaos.journeys import branches as control
        self.assertEqual(control.git(self.project, 'log', timeout=0.000001).returncode, 124,
                         'a git timeout is an exit code')

    def test_detached_head_no_origin_dirty_checkout_worktree_and_no_repository(self):
        git(self.project, 'remote', 'remove', 'origin')
        git(self.project, 'switch', '-q', '--detach', 'main')
        (self.project / 'app.py').write_text('changed\n', encoding='utf-8')
        git(self.project, 'worktree', 'add', '-q', str(self.base / 'wt'), 'eaos/task-1')
        status, inventory = self.get('/api/branches')
        self.assertEqual(status, 200)
        self.assertEqual((inventory['head']['detached'], inventory['head']['branch'], inventory['has_origin']),
                         (True, None, False))
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


    def test_a_fix_on_a_detached_head_says_to_switch_to_a_branch(self):
        git(self.project, 'switch', '-q', '--detach', 'main')
        problem = self.app.branches.fix_where()['problem']
        self.assertEqual(problem['code'], 'detached', 'never "no branch named None"')
        self.assertIn('git switch', problem['en'])


class Selecting(Repo):
    def test_choosing_the_branch_to_analyse_changes_the_context_never_the_checkout(self):
        before = git(self.project, 'rev-parse', 'HEAD'), git(self.project, 'symbolic-ref', '--short', 'HEAD')
        status, out = self.post('/api/branches/analysis', {'branch': 'main'})
        self.assertEqual(status, 200, out)
        self.assertEqual((git(self.project, 'rev-parse', 'HEAD'), git(self.project, 'symbolic-ref', '--short', 'HEAD')),
                         before)
        self.assertEqual((out['context']['analysis']['branch'], out['context']['checkout']['branch']),
                         ('main', 'develop'))
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
        run = {'id': 'r3', 'action': 'report_decision', 'mode': 'handoff', 'state': 'waiting_for_person', 'read': False,
               'created': 'x',
               'label': {'en': 'Review owner answer', 'ar': 'مراجعة إجابة المالك'},
               'context': self.app.branches.run_context()}
        self.app.store.save(run, new=True)
        status, out = self.post('/api/branches/analysis', {'branch': 'main'})
        self.assertEqual(status, 200, out)
        self.assertEqual((out['context']['analysis']['branch'], self.app.store.load('r3')['state']),
                         ('main', 'waiting_for_person'),
                         'rescanning the branch already analysed waits for no run')

    def test_work_in_flight_is_never_retargeted_and_a_run_keeps_its_branch_after_restart_and_deletion(self):
        run = {'id': 'r1', 'action': 'explain', 'state': 'waiting_for_person', 'read': False, 'created': 'x',
               'label': {'en': 'a', 'ar': 'a'},
               'context': self.app.branches.run_context()}
        self.app.store.save(run, new=True)
        status, out = self.post('/api/branches/analysis', {'branch': 'main'})
        self.assertEqual((status, out['needs']), (409, 'in_flight'))
        self.assertEqual(self.app.store.load('r1')['context']['analysis_branch'], 'develop')
        reason = out['reasons'][0]
        self.assertEqual(reason['runs'], [{'id': 'r1', 'label': {'en': 'a', 'ar': 'a'}}],
                         'the refusal names the work and offers its stop')
        self.assertIn('فيه شغل ما خلص على الفرع الحالي: a.', reason['ar'])
        self.assertNotIn('r1', reason['ar'] + reason['en'], 'plain words, never an id')
        done = {'id': 'r2', 'action': 'fix_finish', 'state': 'done', 'read': False, 'created': 'x',
                'label': {'en': 'a', 'ar': 'a'},
                'context': self.app.branches.run_context(),
                'result': {'branch': 'eaos/task-1', 'branch_tip': self.work_tip}}
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
        return self.post('/api/branches/merge',
                         {'source': preview['source'], 'target': preview['target'],
                          'source_head': preview['source_head'],
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
        forged = {**preview,
                  'confirm': self.app.locks.confirm('branch_merge',
                                                    {'source': 'eaos/task-1', 'target': 'main',
                                                     'source_head': preview['source_head'],
                                                     'target_head': preview['target_head'],
                                                     'unchecked': True}, self.app.project)}
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
        status, out = self.post('/api/branches/conflict',
                                {'source': 'eaos/task-1', 'target': 'develop', 'assistant': 'handoff'})
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
            self.assertIn(self.post('/api/branches/merge/preview', {'source': name, 'target': 'develop'})[0],
                          (400, 404, 409), name)
        self.assertFalse(marker.exists())
        other = self.base / 'other'
        other.mkdir()
        git(other, 'init', '-q', '-b', 'main')
        commit(other, 'a', 'a', 'a')
        status, out = self.post('/api/branches/analysis', {'branch': 'main', 'project': str(other)})
        self.assertEqual(status, 200, out)
        self.assertIsNone(project_state.load(other))


if __name__ == '__main__':
    unittest.main()
