"""Choosing the analysis branch, and merging one branch into another (a preview first, then the merge)."""
import secrets
from datetime import datetime
from pathlib import Path

from ....core import branches as reading, project_state
from ....core.store import now
from .common import Blocked, COMMITS_SHOWN, FILES_SHOWN, _eaos_env, _out, git, say, valid_name


class Merging:
    # ------------------------------------------------------------------ the analysis branch
    def _refuse_in_flight(self, name):
        """Blocked while any run is queued or working, naming each by its label and giving its id for its stop; choosing
        the branch already analysed moves no run, so it is never refused."""
        waiting = self.active_runs(queued=True)
        if not waiting or name == ((self.state() or {}).get('branch') or self.head()['branch']): return
        runs = [{'id': r['id'], 'label': r.get('label') or {'en': r['action'], 'ar': r['action']}} for r in waiting[:3]]
        named = {lang: ('، ' if lang == 'ar' else ', ').join(run['label'][lang] for run in runs) for lang in ('en', 'ar')}
        raise Blocked([{**say(f"Work is still open on the current branch: {named['en']}. Let it finish or stop it, then choose again. "
                              'EAOS never moves work to another branch on its own.',
                              f"فيه شغل ما خلص على الفرع الحالي: {named['ar']}. اتركه ينتهي أو أوقفه، ثم اختر من جديد. "
                              'EAOS لا ينقل الشغل إلى فرع آخر بنفسه.', 'in_flight'), 'runs': runs}], needs='in_flight')

    def select(self, body):
        """Make `branch` the analysis branch: the Studio's context changes, the person's checkout does not. Moving to
        another branch is refused while any run is queued or working, so none is retargeted without the person deciding;
        choosing the branch already analysed moves nothing. `scan: true` queues the scan."""
        name = valid_name(self.project, body.get('branch'))
        local, remote = self.tip(f'refs/heads/{name}'), next((r for r in self.remotes() if self.tip(f'refs/remotes/{r}/{name}')), None)
        if not local and not remote: raise KeyError(name)
        self._refuse_in_flight(name)
        self._still_at(body.get('expected_tip'), name, local, remote)
        handle = self._locked()
        try:
            result, needs_scan = self._select_now(name, local, remote)
            if needs_scan is None: return result           # not changed: the run says why
        finally:
            handle.close()
        # the person asked for this scan, and the check on record is of another commit: a new check, never the one on record
        scan = self.actions.create({'action': 'audit', 'inputs': {'fresh': True}}) if body.get('scan') and needs_scan else None
        return {'run': result, 'scan': self.actions.public(scan) if scan else None, 'context': self.context()}

    def _still_at(self, expected, name, local, remote):
        """Blocked when the branch moved from the commit the person looked at (`expected`, when given)."""
        if expected and expected != (local or self.tip(f'refs/remotes/{remote}/{name}')):
            raise Blocked([say('The branch moved since you looked at it: refresh.', 'الفرع تغيّر منذ نظرت إليه: حدّث.', 'stale')], needs='refresh')

    def _select_now(self, name, local, remote):
        """The analysis branch moved to `name`, the lock held: (its run, whether the branch needs a new check); the
        check None when nothing changed."""
        from ....journeys import guided
        before = self.head()
        run = self._start('branch_select', {'en': f'Analyse the branch {name}', 'ar': f'حلّل الفرع {name}'}, [name], {'branch': name})
        state = self.state()
        if not state:
            from ....journeys import agent_tools
            state = agent_tools.state_of(str(self.project))
        try: guided.choose(state, name)
        except ValueError as problem:
            return self._finish(run, False, {'en': f'Not changed: {problem}', 'ar': f'ما تغيّر: {problem}'}, {'reason': str(problem)}), None
        after = self.head()
        if (after['branch'], after['commit']) != (before['branch'], before['commit']):
            return self._finish(run, False, {'en': 'Your checkout changed unexpectedly: nothing more was done.', 'ar': 'تغيّر الفرع المفتوح عندك على غير المتوقع: ما سوّيت شيئًا آخر.'},
                                {'reason': 'checkout changed'}), None
        state = self.state()
        needs_scan = not state.get('scanned_commit') or state.get('scanned_commit') != self.tip(f'refs/heads/{name}')
        data = {'branch': name, 'created_local_from': remote if not local else None, 'checkout_unchanged': True, 'needs_scan': needs_scan,
                'branches': [name]}
        return self._finish(run, True, {'en': f'The Studio now works on {name}; your checkout stays {before["branch"] or "detached"}.',
                                        'ar': f'الاستوديو يعمل الآن على {name}؛ والفرع المفتوح عندك يبقى {before["branch"] or "منفصلًا"}.'}, data), needs_scan

    # ------------------------------------------------------------------ merging
    def preview_merge(self, body):
        """What merging source into target would do, computed in isolation (merge-tree: no index, no worktree, no ref
        moves): the commits and files, conflicts, checks, the path it takes and why it is blocked; with a confirm token
        bound to both heads when it can happen."""
        source = valid_name(self.project, body.get('source'))
        row, inventory = self._row(source)
        target = valid_name(self.project, body.get('target') or row['ownership'].get('base') or inventory['context']['analysis']['branch'])
        target_tip = self.tip(f'refs/heads/{target}')
        if not target_tip: raise KeyError(target)
        source_tip = row['tip']
        reasons = self._merge_blocks(row, target, inventory)
        managed = self._wave_path(source, target, inventory, reasons)
        merged = git(self.project, 'merge-base', '--is-ancestor', source_tip, target_tip).returncode == 0
        if merged: reasons.append(say(f'Nothing to merge: {target} already has every commit of {source}.', f'لا شيء يُدمج: {target} فيه كل commit في {source}.', 'merged'))
        held = self._held_target(inventory, target, reasons)
        commits = [dict(zip(('commit', 'author', 'email', 'at', 'subject'), line.split('\x00'))) for line in
                   git(self.project, 'log', f'--max-count={COMMITS_SHOWN}', '--format=%H%x00%an%x00%ae%x00%cI%x00%s', f'{target_tip}..{source_tip}').stdout.splitlines()]
        files = [{'status': line.split('\t')[0], 'path': line.split('\t')[-1]} for line in
                 git(self.project, '-c', 'core.quotePath=false', 'diff', '--name-status', f'{target_tip}...{source_tip}').stdout.splitlines()[:FILES_SHOWN]]
        conflicts = self._conflicts(target_tip, source_tip, reasons)
        checks = self.checks_of(source, source_tip)
        if checks['status'] == 'failed':
            reasons.append(say('The recorded checks of this exact commit failed.', 'الفحوص المسجلة لهذا الـcommit نفسه فشلت.', 'checks_failed'))
        unchecked = checks['status'] == 'not_recorded'
        fast_forward = git(self.project, 'merge-base', '--is-ancestor', target_tip, source_tip).returncode == 0
        bound = {'source': source, 'target': target, 'source_head': source_tip, 'target_head': target_tip, 'unchecked': unchecked}
        return {'source': source, 'target': target, 'source_head': source_tip, 'target_head': target_tip, 'path': 'accept' if managed else 'transaction',
                'fast_forward': fast_forward, 'commits': commits, 'files': files, 'conflicts': conflicts, 'checks': checks,
                'needs_unchecked_ack': unchecked, 'target_checked_out': bool(held), 'blocked': reasons,
                'recommended_target': row['ownership'].get('base'), 'protected': inventory['protected'].get(target),
                'confirm': None if reasons else self.locks.confirm('branch_merge', bound, self.project), 'checked_at': now()}

    @staticmethod
    def _held_target(inventory, target, reasons):
        """The worktree that has the target checked out, None; its unsaved changes added to `reasons`."""
        held = next((w for w in inventory['worktrees'] if w['branch'] == target), None)
        if held and held['dirty'] and (held['dirty']['tracked']):
            reasons.append(say(f'{target} is checked out with unsaved changes: save (commit) or set them aside first.',
                               f'{target} مفتوح وفيه تعديلات غير محفوظة: احفظها (commit) أو ضعها جانبًا أولًا.', 'dirty_target'))
        return held

    def _conflicts(self, target_tip, source_tip, reasons):
        """The files the merge would conflict on, tried in isolation (merge-tree); a failed try or a conflict added to
        `reasons`."""
        trial = git(self.project, 'merge-tree', '--write-tree', '--name-only', '--no-messages', target_tip, source_tip)
        conflicts = [line for line in trial.stdout.splitlines()[1:] if line.strip()] if trial.returncode == 1 else []
        if trial.returncode not in (0, 1): reasons.append(say('git could not try the merge.', 'git ما قدر يجرّب الدمج.', 'merge_tree_failed'))
        elif conflicts: reasons.append(say(f'{len(conflicts)} file(s) conflict: nothing is merged; both sides stay as they are.', f'{len(conflicts)} ملف فيه تعارض: ما يُدمج شيء، والطرفان يبقيان كما هما.', 'conflict'))
        return conflicts

    def _wave_path(self, source, target, inventory, reasons):
        """True for the newest applied EAOS batch into its own branch (it goes through accept); refuses any other one."""
        if (self.waves().get(source) or {}).get('status') != 'applied': return False
        latest = project_state.waiting_batch(self.state())
        if latest is not None and latest.get('branch') == source and target == inventory['context']['analysis']['branch']: return True
        reasons.append(say('This EAOS batch is accepted only into the branch it was made for, newest batch first.',
                           'تُعتمد دفعة EAOS فقط في الفرع الذي صُنعت له، والأحدث أولًا.', 'wave_order'))
        return False

    def merge(self, body):
        """Merge a tool-owned branch at the heads its preview showed. A managed EAOS batch goes through EAOS's accept
        (ledger, report and branch cleanup together); any other one by compare-and-swap of the target ref, or by a merge
        in the clean worktree that has it checked out. A conflict, a moved head or a dirty target changes nothing."""
        source, target = valid_name(self.project, body.get('source')), valid_name(self.project, body.get('target'))
        bound = {'source': source, 'target': target, 'source_head': body.get('source_head'), 'target_head': body.get('target_head'),
                 'unchecked': bool(body.get('unchecked'))}
        self._spend(body, 'branch_merge', bound)
        if bound['unchecked'] and body.get('unchecked_ack') is not True:
            raise Blocked([say('No checks are recorded for this commit: confirm that you merge it without them.',
                               'ما فيه فحوص مسجلة لهذا الـcommit: أكّد أنك تدمجه بدونها.', 'unchecked')], needs='unchecked_ack')
        handle = self._locked()
        try:
            preview = self.preview_merge({'source': source, 'target': target})
            if (preview['source_head'], preview['target_head']) != (bound['source_head'], bound['target_head']):
                raise Blocked([say('A branch moved since the preview: look at the new preview before merging.',
                                   'أحد الفرعين تغيّر بعد المعاينة: شوف المعاينة الجديدة قبل الدمج.', 'stale')], needs='refresh')
            if preview['blocked']: raise Blocked(preview['blocked'], needs='blocked')
            run = self._start('branch_merge', {'en': f'Merge {source} into {target}', 'ar': f'ادمج {source} في {target}'}, [source, target],
                              {'source': source, 'target': target, 'source_head': bound['source_head'], 'target_head': bound['target_head']})
            if preview['path'] == 'accept': return {'run': self._merge_by_accept(source, target, bound, run)}
            done = self._merge_transaction(source, target, bound, run)
            if done.get('error'):
                return {'run': self._finish(run, False, {'en': f"Not merged: {done['error']}", 'ar': f"ما اندمج: {done['error']}"},
                                            {'reason': done['error'], 'source': source, 'target': target, 'branches': [source, target]})}
            self.record(source, merged_into={'branch': target, 'at': now(), 'commit': done['commit'], 'run': run, 'via': done['via']})
            return {'run': self._finish(run, True, {'en': f'{source} is merged into {target}.', 'ar': f'اندمج {source} في {target}.'},
                                        {'source': source, 'target': target, 'via': done['via'], 'target_before': bound['target_head'],
                                         'target_after': done['commit'], 'branches': [source, target]}, outcome='merged')}
        finally:
            handle.close()

    def _merge_by_accept(self, source, target, bound, run):
        """A managed EAOS batch merged through EAOS's accept (ledger, report and branch cleanup together); the run."""
        answer = self.manager.call('accept', {'person_agreed': True})
        ok = isinstance(answer, dict) and answer.get('status') == 'accepted'
        after = self.tip(f'refs/heads/{target}')
        data = {'source': source, 'target': target, 'via': 'accept', 'answer': answer, 'target_before': bound['target_head'],
                'target_after': after, 'branches': [source, target], 'reason': None if ok else str(answer.get('status') or answer.get('error'))}
        if ok: self.record(source, merged_into={'branch': target, 'at': now(), 'commit': after, 'run': run, 'via': 'accept'})
        return self._finish(run, ok, {'en': f'{source} is in {target}; the report and the progress are up to date.' if ok else f"Not merged: {data['reason']}",
                                      'ar': f'{source} صار في {target}، والتقرير والتقدم محدّثان.' if ok else f"ما اندمج: {data['reason']}"},
                            data, outcome='accepted' if ok else None)

    def _merge_transaction(self, source, target, bound, run):
        message = f'Merge {source} into {target} (EAOS Studio, run {run})'
        held = next((w for w in self._worktrees() if w['branch'] == target), None)
        if held: return _merge_in_worktree(Path(held['path']), bound, message)
        if git(self.project, 'merge-base', '--is-ancestor', bound['target_head'], bound['source_head']).returncode == 0:
            new = bound['source_head']
            via = 'fast_forward'
        else:
            trial = git(self.project, 'merge-tree', '--write-tree', '--no-messages', bound['target_head'], bound['source_head'])
            if trial.returncode: return {'error': 'the merge has conflicts'}
            tree = trial.stdout.split()[0]
            made = git(self.project, 'commit-tree', tree, '-p', bound['target_head'], '-p', bound['source_head'], '-m', message, env=_eaos_env())
            if made.returncode: return {'error': 'git could not write the merge commit'}
            new, via = made.stdout.strip(), 'merge_commit'
        moved = git(self.project, 'update-ref', '-m', message, f'refs/heads/{target}', new, bound['target_head'])
        if moved.returncode: return {'error': 'the target moved while merging; nothing changed'}
        return {'commit': new, 'via': via}

    def propose_resolution(self, body):
        """A conflict becomes a read-only review run by the person's assistant: it proposes how to resolve, changes nothing."""
        preview = self.preview_merge(body)
        if not preview['conflicts']: raise Blocked([say('There is no conflict to resolve.', 'ما فيه تعارض يُحل.', 'no_conflict')])
        assistant = self.actions._assistant(body.get('assistant'), True)
        run = 'c' + datetime.now().strftime('%Y%m%d-%H%M%S-') + secrets.token_hex(3)
        review = {'kind': 'branch_conflict', 'source': preview['source'], 'target': preview['target'], 'source_head': preview['source_head'],
                  'target_head': preview['target_head'], 'conflicts': preview['conflicts'][:50], 'files': preview['files'][:100]}
        record = {'id': run, 'action': 'branch_conflict', 'verb': None, 'label': {'en': f"Propose how to resolve {preview['source']} into {preview['target']}",
                                                                                   'ar': f"اقترح حل تعارض {preview['source']} مع {preview['target']}"},
                  'inputs': {}, 'review': review, 'cards': [], 'assistant': None if assistant == 'handoff' else assistant,
                  'mode': 'handoff' if assistant == 'handoff' else 'assistant', 'state': 'queued', 'attempt': 1, 'created': now(),
                  'queued_at': now(), 'read': False, 'context': self.run_context(), 'branch_op': {'branches': [preview['source'], preview['target']]}}
        self.store.save(record, new=True)
        self.store.append(run, 'action', record['label'], {'action': 'branch_conflict', 'by': 'person', 'arguments': {'source': preview['source'], 'target': preview['target']}})
        self.store.set_queue(self.store.queue())
        return {'run': self.actions.public(self.store.load(run))}


def _merge_in_worktree(folder, bound, message):
    """The merge made in the clean worktree that has the target checked out: {commit, via}, or {error} with nothing
    changed."""
    changes = reading.dirty(folder)
    if changes is None or changes['tracked']: return {'error': 'the checked-out target has unsaved changes'}
    if _out(folder, 'rev-parse', 'HEAD') != bound['target_head']: return {'error': 'the target moved'}
    done = git(folder, 'merge', '--no-edit', '-m', message, bound['source_head'], env=_eaos_env())
    if done.returncode:
        git(folder, 'merge', '--abort')
        return {'error': 'git refused the merge; nothing changed'}
    return {'commit': _out(folder, 'rev-parse', 'HEAD'), 'via': 'worktree_merge'}
