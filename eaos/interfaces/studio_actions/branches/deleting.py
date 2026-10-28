"""Deleting a branch (kept for undoing), the clean-up of merged work branches and old worktrees, and restoring one."""
import hashlib
import json
import secrets
from datetime import datetime, timezone

from ....core.project.runs import _write_json, now
from .common import Blocked, COMMITS_SHOWN, RECOVERY, _out, git, say, valid_name
from ....core.system.files import read_json


class Deleting:
    # ------------------------------------------------------------------ deleting and recovering
    def _remove_worktree_of(self, name):
        """Remove the clean worktree (not the project folder) that has `name` checked out: `git worktree remove` without
        --force, so git itself refuses when anything unsaved is in it. None when no worktree holds the branch."""
        held = next((w for w in self._worktrees() if w['branch'] == name and not w['current']), None)
        if not held: return None
        return self._remove_worktree(held['path'])

    def _remove_worktree(self, path):
        done = git(self.project, 'worktree', 'remove', path)
        if done.returncode:
            return {'error': f"git kept the worktree {self.store.scrub(path)}: {done.stderr.strip()[-200:]}",
                    'ar': f"git أبقى نسخة العمل {self.store.scrub(path)}: {done.stderr.strip()[-200:]}"}
        return {'path': self.store.scrub(path)}

    def _cleanup_plan(self):
        """What "clean up" would remove, from what git says now: every local branch whose last commit is already in the
        base or a protected branch (so no commit is lost), that is not protected, the default, the analysis branch,
        checked out in the project folder or in a worktree with unsaved changes, nor used by a run; and every clean,
        detached worktree whose commit is in one of those branches. Everything else is listed with why it stays."""
        inventory = self.inventory()
        keepers = {row['name']: row['tip'] for row in inventory['branches']
                   if row['kind'] == 'local' and (row['name'] == inventory['base'] or row['protected'])}
        def holder(tip):
            return next((name for name, kept in keepers.items() if git(self.project, 'merge-base', '--is-ancestor', tip, kept).returncode == 0), None)
        branches, kept = self._merged_branches(inventory, keepers, holder)
        worktrees = self._old_worktrees(holder)
        selection = {'branches': [[b['branch'], b['tip'], b['_worktree']] for b in branches], 'worktrees': [[w['_path'], w['head']] for w in worktrees]}
        digest = hashlib.sha256(json.dumps(selection, sort_keys=True).encode('utf-8')).hexdigest()
        return {'base': inventory['base'], 'kept_branches': sorted(keepers), 'branches': branches, 'worktrees': worktrees,
                'kept': kept, 'digest': digest}

    def _merged_branches(self, inventory, keepers, holder):
        """(the local branches the clean-up removes, each with the kept branch that holds its commits; those that stay,
        with why)."""
        branches, kept = [], []
        for row in inventory['branches']:
            if row['kind'] != 'local' or row['name'] in keepers: continue
            into = holder(row['tip'])
            reasons = self._delete_blocks(row, inventory)
            if not into:
                ahead = len(git(self.project, 'rev-list', row['tip'], '--not', *keepers.values()).stdout.split()) if keepers else None
                reasons = [say(f'{ahead} commit(s) of it are in no kept branch: merge it or delete it on its own.',
                               f'فيه {ahead} commit ليست في أي فرع باقٍ: ادمجه أو احذفه وحده.', 'not_merged')] + reasons
            if reasons:
                kept.append({'branch': row['name'], 'reasons': reasons})
                continue
            worktree = bool(row['worktree'])
            branches.append({'branch': row['name'], 'tip': row['tip'], 'merged_into': into, 'whose': self.whose(row),
                             'worktree': row['worktree']['path'] if worktree else None, '_worktree': worktree})
        return branches, kept

    def _old_worktrees(self, holder):
        """The detached worktrees the clean-up removes: the prunable ones, and the clean ones whose commit a kept branch
        holds."""
        worktrees = []
        for row in self._worktrees():
            if row['current'] or row['branch'] or row['locked']: continue
            if row['prunable'] or self._clean_and_kept(row, holder):
                worktrees.append({'path': self.store.scrub(row['path']), '_path': row['path'], 'head': row['head'],
                                  'prunable': bool(row['prunable'])})
        return worktrees

    @staticmethod
    def _clean_and_kept(row, holder):
        """Whether a worktree has nothing unsaved and its commit is in a kept branch."""
        return not (row['dirty'] is None or row['dirty']['tracked'] or row['dirty']['untracked'] or not row['head'] or not holder(row['head']))

    @staticmethod
    def _public(plan):
        return {**plan, 'branches': [{k: v for k, v in b.items() if not k.startswith('_')} for b in plan['branches']],
                'worktrees': [{k: v for k, v in w.items() if not k.startswith('_')} for w in plan['worktrees']]}

    def preview_cleanup(self, body=None):
        """The cleanup's preview: what goes, what stays and why, and a confirm token bound to exactly that list."""
        plan = self._cleanup_plan()
        empty = not plan['branches'] and not plan['worktrees']
        return {**self._public(plan), 'confirm': None if empty or self._busy([]) else self.locks.confirm('branch_cleanup', {'digest': plan['digest']}, self.project),
                'blocked': self._busy([]), 'checked_at': now()}

    def cleanup(self, body):
        """Remove the merged branches and the clean worktrees the preview listed, only if git still says exactly that:
        a recovery ref for each branch first, each worktree removed by git without --force, each branch removed only at
        the commit the preview showed. One run in the history, with what was done and how to restore each branch."""
        self._spend(body, 'branch_cleanup', {'digest': body.get('digest')})
        handle = self._locked()
        try:
            plan = self._cleanup_plan()
            if plan['digest'] != body.get('digest'):
                raise Blocked([say('The branches changed since the preview: look again.', 'الفروع تغيّرت بعد المعاينة: شوف من جديد.', 'stale')], needs='refresh')
            if busy := self._busy([]): raise Blocked(busy, needs='blocked')
            names = [b['branch'] for b in plan['branches']]
            run = self._start('branch_cleanup', {'en': f'Clean up {len(names)} merged branch(es) and {len(plan["worktrees"])} old worktree(s)',
                                                 'ar': f'نظّف {len(names)} فرعًا مدموجًا و{len(plan["worktrees"])} نسخة عمل قديمة'}, names,
                              {'branches': names, 'worktrees': [w['path'] for w in plan['worktrees']]})
            done = {'deleted': [], 'worktrees_removed': [], 'failed': []}
            for worktree in plan['worktrees']: self._remove_old_worktree(worktree, done)
            for branch in plan['branches']: self._delete_merged(branch, run, done)
            git(self.project, 'worktree', 'prune')
            return {'run': self._cleaned(run, names, done)}
        finally:
            handle.close()

    def _cleaned(self, run, names, done):
        """The clean-up's run finished with what it deleted, removed and could not do."""
        deleted, removed, failed = done['deleted'], done['worktrees_removed'], done['failed']
        text = {'en': f"Deleted {len(deleted)} merged branch(es) and removed {len(removed)} worktree(s); each branch can be restored." + (f" {len(failed)} could not be done." if failed else ''),
                'ar': f"حُذف {len(deleted)} فرع مدموج وأُزيلت {len(removed)} نسخة عمل، وكل فرع يمكن استرجاعه." + (f" وما تم {len(failed)}." if failed else '')}
        return self._finish(run, not failed, text, {**done, 'branches': names, 'reason': f'{len(failed)} item(s) could not be removed' if failed else None},
                            outcome=None if failed else 'cleaned')

    def _remove_old_worktree(self, worktree, done):
        out = git(self.project, 'worktree', 'prune') if worktree['prunable'] else git(self.project, 'worktree', 'remove', worktree['_path'])
        done['failed' if out.returncode else 'worktrees_removed'].append({'worktree': worktree['path'], **({'reason': out.stderr.strip()[-200:]} if out.returncode else {})})

    def _delete_merged(self, branch, run, done):
        kept = self._keep(branch['branch'], 'local', None, branch['tip'], run)
        out = self._remove_worktree_of(branch['branch']) if branch['_worktree'] else None
        if out and out.get('error'):
            done['failed'].append({'branch': branch['branch'], 'reason': out['error'], 'recovery': kept['id']})
            return
        if out: done['worktrees_removed'].append({'worktree': out['path']})
        gone = git(self.project, 'update-ref', '-m', f"EAOS Studio: clean up {branch['branch']} (run {run})", '-d', f"refs/heads/{branch['branch']}", branch['tip'])
        if gone.returncode: return done['failed'].append({'branch': branch['branch'], 'reason': 'the branch moved', 'recovery': kept['id']})
        self.record(branch['branch'], history={'at': now(), 'event': 'deleted', 'where': 'local', 'run': run, 'recovery': kept['id'], 'via': 'cleanup'})
        done['deleted'].append({'branch': branch['branch'], 'tip': branch['tip'], 'merged_into': branch['merged_into'], 'recovery': kept['id']})

    def recoveries(self):
        return read_json(self.store.folder / 'branch-recovery.json', []) or []

    def _keep(self, name, where, remote, tip, run):
        """A recovery ref for the commit about to lose its branch, written before anything is deleted."""
        ident = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3)
        ref = RECOVERY + ident
        if git(self.project, 'update-ref', ref, tip, '0' * 40).returncode: raise RuntimeError('could not keep a recovery ref')
        rows = self.recoveries()
        entry = {'id': ident, 'ref': ref, 'branch': name, 'where': where, 'remote': remote, 'tip': tip, 'at': now(), 'run': run, 'restored': None}
        _write_json(self.store.folder / 'branch-recovery.json', rows + [entry])
        return entry

    def preview_delete(self, body):
        """What deleting would do: whether the branch is merged, the commits only it holds (which the recovery ref keeps),
        why it is blocked, and the confirm token(s): one for the deletion, and a second one when commits would be lost."""
        where = body.get('where') or 'local'
        name = valid_name(self.project, body.get('branch'))
        if where == 'remote': return self._preview_remote(name, body)
        if where != 'local': raise ValueError('where must be local or remote')
        row, inventory = self._row(name)
        reasons = self._delete_blocks(row, inventory)
        holders = self._holders(row, name)
        # --exclude takes the name without refs/heads/ for --branches; recovery refs are in none of these namespaces.
        lost = git(self.project, 'rev-list', f'--max-count={COMMITS_SHOWN + 1}', row['tip'], '--not', f'--exclude={name}',
                   '--branches', '--remotes', '--tags').stdout.split()
        commits = self._commits(lost[:COMMITS_SHOWN])
        unmerged = bool(lost)
        worktree = bool(row['worktree']) and not row['worktree']['current']
        bound = {'branch': name, 'tip': row['tip'], 'unmerged': unmerged, 'worktree': worktree}
        return {'branch': name, 'where': 'local', 'tip': row['tip'], 'merged_into': holders, 'unmerged': unmerged, 'whose': self.whose(row),
                'worktree': row['worktree']['path'] if worktree else None,
                'lost_commits': commits, 'lost_truncated': len(lost) > COMMITS_SHOWN, 'blocked': reasons, 'remote_kept': True,
                'confirm': None if reasons else self.locks.confirm('branch_delete', bound, self.project),
                'confirm_unmerged': None if reasons or not unmerged else self.locks.confirm('branch_delete_unmerged', bound, self.project),
                'checked_at': now()}

    def _preview_remote(self, name, body):
        """What deleting the branch on one remote would do, why it is blocked, and its confirm token."""
        row, inventory = self._row(name, 'remote', body.get('remote'))
        reasons = self._remote_blocks(row, inventory)
        bound = {'branch': name, 'remote': row['remote'], 'tip': row['tip']}
        return {'branch': name, 'where': 'remote', 'remote': row['remote'], 'tip': row['tip'], 'as_of': row['remote_as_of'],
                'whose': self.whose(row), 'blocked': reasons, 'local_kept': bool(self.tip(f'refs/heads/{name}')),
                'confirm': None if reasons else self.locks.confirm('branch_delete_remote', bound, self.project), 'checked_at': now()}

    def _holders(self, row, name):
        """The other local branches that hold the branch's last commit."""
        return [line for line in (_out(self.project, 'for-each-ref', '--format=%(refname:short)', '--contains', row['tip'], 'refs/heads') or '').splitlines()
                if line and line != name]

    def _commits(self, shas):
        """Each commit's id, subject and author."""
        return [dict(zip(('commit', 'subject', 'author'), (_out(self.project, 'log', '-1', '--format=%H%x00%s%x00%an', c) or '').split('\x00')))
                for c in shas]

    def delete(self, body):
        """Delete one branch, locally or on one remote (two separate operations, each with its own consent): a recovery ref
        first, then the ref removed only if it is still at the commit the preview showed. Never a force deletion."""
        where = body.get('where') or 'local'
        name = valid_name(self.project, body.get('branch'))
        if where == 'remote': return self._delete_remote(name, body)
        if where != 'local': raise ValueError('where must be local or remote')
        bound = {'branch': name, 'tip': body.get('tip'), 'unmerged': bool(body.get('unmerged')), 'worktree': bool(body.get('worktree'))}
        self._spend(body, 'branch_delete', bound)
        if bound['unmerged'] and not self.locks.spend(body.get('confirm_unmerged'), 'branch_delete_unmerged', bound, self.project):
            raise Blocked([say('Its commits are in no other branch: confirm a second time that you delete them (they stay recoverable).',
                               'الـcommits فيه ليست في أي فرع آخر: أكّد مرة ثانية أنك تحذفها (وتبقى قابلة للاسترجاع).', 'unmerged')],
                          needs='confirm_unmerged')
        handle = self._locked()
        try:
            preview = self.preview_delete({'branch': name, 'where': 'local'})
            if preview['tip'] != bound['tip'] or preview['unmerged'] != bound['unmerged'] or bool(preview['worktree']) != bound['worktree']:
                raise Blocked([say('The branch moved since the preview: look again.', 'الفرع تغيّر بعد المعاينة: شوف من جديد.', 'stale')], needs='refresh')
            if preview['blocked']: raise Blocked(preview['blocked'], needs='blocked')
            return {'run': self._delete_local(name, bound)}
        finally:
            handle.close()

    def _delete_local(self, name, bound):
        """The local deletion, its checks passed: a recovery ref, its worktree removed when asked, then the ref; the run."""
        run = self._start('branch_delete', {'en': f'Delete the branch {name} here', 'ar': f'احذف الفرع {name} هنا'}, [name],
                          {'branch': name, 'tip': bound['tip'], 'unmerged': bound['unmerged']})
        kept = self._keep(name, 'local', None, bound['tip'], run)
        removed = self._remove_worktree_of(name) if bound['worktree'] else None
        if removed and removed.get('error'):
            return self._finish(run, False, {'en': f"Not deleted: {removed['error']}", 'ar': f"ما انحذف: {removed['ar']}"},
                                {'reason': removed['error'], 'branch': name, 'recovery': kept['id'], 'branches': [name]})
        gone = git(self.project, 'update-ref', '-m', f'EAOS Studio: delete {name} (run {run})', '-d', f'refs/heads/{name}', bound['tip'])
        if gone.returncode:
            return self._finish(run, False, {'en': 'Not deleted: the branch moved.', 'ar': 'ما انحذف: الفرع تغيّر.'},
                                {'reason': 'the branch moved', 'branch': name, 'recovery': kept['id'], 'branches': [name]})
        self.record(name, history={'at': now(), 'event': 'deleted', 'where': 'local', 'run': run, 'recovery': kept['id']})
        return self._finish(run, True, {'en': f'Deleted {name}; it can be restored ({kept["id"]}). The remote copy, if any, is untouched.',
                                        'ar': f'حُذف {name}، ويمكن استرجاعه ({kept["id"]}). والنسخة البعيدة، إن وُجدت، لم تُمس.'},
                            {'branch': name, 'where': 'local', 'tip': bound['tip'], 'recovery': kept['id'], 'unmerged': bound['unmerged'],
                             'worktree_removed': (removed or {}).get('path'), 'branches': [name]}, outcome='deleted')

    def _delete_remote(self, name, body):
        remote = body.get('remote')
        if remote not in self.remotes(): raise ValueError('no such remote')
        bound = {'branch': name, 'remote': remote, 'tip': body.get('tip')}
        self._spend(body, 'branch_delete_remote', bound)
        handle = self._locked()
        try:
            preview = self.preview_delete({'branch': name, 'where': 'remote', 'remote': remote})
            if preview['tip'] != bound['tip']:
                raise Blocked([say('The remote copy moved since the preview: look again.', 'النسخة البعيدة تغيّرت بعد المعاينة: شوف من جديد.', 'stale')], needs='refresh')
            if preview['blocked']: raise Blocked(preview['blocked'], needs='blocked')
            run = self._start('branch_delete_remote', {'en': f'Delete {name} on {remote}', 'ar': f'احذف {name} من {remote}'}, [name],
                              {'branch': name, 'remote': remote, 'tip': bound['tip']})
            kept = self._keep(name, 'remote', remote, bound['tip'], run)
            pushed = git(self.project, 'push', '--porcelain', f'--force-with-lease=refs/heads/{name}:{bound["tip"]}', remote, f':refs/heads/{name}', timeout=120)
            if pushed.returncode:
                return {'run': self._finish(run, False, {'en': f'Not deleted on {remote}: {pushed.stderr.strip()[-200:] or "the remote refused"}',
                                                         'ar': f'ما انحذف من {remote}: {pushed.stderr.strip()[-200:] or "رفض المستودع البعيد"}'},
                                            {'reason': 'the remote refused or could not be reached', 'branch': name, 'remote': remote, 'recovery': kept['id'],
                                             'branches': [name]})}
            self.record(name, history={'at': now(), 'event': 'deleted', 'where': 'remote', 'remote': remote, 'run': run, 'recovery': kept['id']})
            return {'run': self._finish(run, True, {'en': f'Deleted {name} on {remote}; the commit is kept ({kept["id"]}). Your local branch, if any, is untouched.',
                                                    'ar': f'حُذف {name} من {remote}، والـcommit محفوظ ({kept["id"]}). وفرعك المحلي، إن وُجد، لم يُمس.'},
                                        {'branch': name, 'where': 'remote', 'remote': remote, 'tip': bound['tip'], 'recovery': kept['id'], 'branches': [name]},
                                        outcome='deleted')}
        finally:
            handle.close()

    def restore(self, body):
        """A deleted branch back, locally, at its recorded commit, if no branch has its name now."""
        entry = next((r for r in self.recoveries() if r['id'] == body.get('recovery')), None)
        if entry is None: raise KeyError(body.get('recovery'))
        name = valid_name(self.project, body.get('as') or entry['branch'])
        handle = self._locked()
        try:
            if self.tip(f'refs/heads/{name}'):
                raise Blocked([say(f'A branch named {name} exists now: restore under another name.', f'فيه فرع اسمه {name} الآن: استرجعه باسم آخر.', 'exists')],
                              needs='name')
            run = self._start('branch_restore', {'en': f'Restore the branch {name}', 'ar': f'استرجع الفرع {name}'}, [name], {'recovery': entry['id'], 'branch': name})
            made = git(self.project, 'update-ref', '-m', f'EAOS Studio: restore {name} (run {run})', f'refs/heads/{name}', entry['tip'], '0' * 40)
            if made.returncode:
                return {'run': self._finish(run, False, {'en': 'Not restored.', 'ar': 'ما استُرجع.'}, {'reason': made.stderr.strip()[-200:], 'branches': [name]})}
            rows = self.recoveries()
            for row in rows:
                if row['id'] == entry['id']: row['restored'] = {'at': now(), 'as': name, 'run': run}
            _write_json(self.store.folder / 'branch-recovery.json', rows)
            self.record(name, history={'at': now(), 'event': 'restored', 'run': run, 'recovery': entry['id']}, tip=entry['tip'])
            return {'run': self._finish(run, True, {'en': f'Restored {name} at {entry["tip"][:12]}.', 'ar': f'استُرجع {name} عند {entry["tip"][:12]}.'},
                                        {'branch': name, 'tip': entry['tip'], 'recovery': entry['id'], 'branches': [name]}, outcome='restored')}
        finally:
            handle.close()
