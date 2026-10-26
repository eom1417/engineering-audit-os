"""What refuses a branch change, and the one-at-a-time lock and history every change goes through."""
import fcntl
import secrets
from datetime import datetime

from ....core.project.runs import ACTIVE, now
from .common import Blocked, git, say, work_of


class Guards:
    # ------------------------------------------------------------------ guards
    @staticmethod
    def whose(row):
        """What the person is told about whose branch this is before they confirm a change to it. Ownership never blocks a
        change the person confirms (merge, delete): it is their repository. It only decides what EAOS may do on its own."""
        owner = row['ownership']
        if owner['owner'] == 'unknown':
            return say('EAOS did not make this branch: it is yours, and only your confirmation changes it.',
                       'هذا الفرع ما أنشأه EAOS: هو فرعك، ولا يتغيّر إلا بتأكيدك.', 'yours')
        if owner['owner'] == 'shared':
            return say(f"EAOS made this branch and someone else added {owner['foreign_commits']} commit(s) to it.",
                       f"أنشأ EAOS هذا الفرع وأضاف إليه غيره {owner['foreign_commits']} commit.", 'shared')
        return say(f"EAOS made this branch ({owner.get('evidence')}).", f"أنشأ EAOS هذا الفرع ({owner.get('evidence')}).", 'eaos')

    def _busy(self, names, exclude=None):
        busy = [r for r in self.active_runs(exclude) if {work_of(r), (r.get('context') or {}).get('analysis_branch')} & set(names)
                or r.get('action', '').startswith('branch_')]
        return [say(f"A run is working now ({busy[0]['id']}): wait for it to finish or stop it.",
                    f"فيه تشغيل يعمل الآن ({busy[0]['id']}): انتظره حتى ينتهي أو أوقفه.", 'active_run')] if busy else []

    def _merge_blocks(self, row, target, inventory, preview=True):
        reasons = []
        if not target: reasons.append(say('No destination: choose the branch to merge into.', 'ما فيه وجهة: اختر الفرع الذي يُدمج فيه.', 'no_target'))
        elif target == row['name']: reasons.append(say('A branch cannot be merged into itself.', 'لا يُدمج الفرع في نفسه.', 'same'))
        elif inventory['protected'].get(target):
            reasons.append(say(f"{target} is protected ({inventory['protected'][target]['en']}): nothing is merged into it from here.",
                               f"{target} محمي ({inventory['protected'][target]['ar']}): لا يُدمج فيه شيء من هنا.", 'protected_target'))
        reasons += self._busy([row['name'], target])
        return reasons

    def _delete_blocks(self, row, inventory):
        reasons = []
        name = row['name']
        if inventory['protected'].get(name): reasons.append(say('This branch is protected.', 'هذا الفرع محمي.', 'protected'))
        if 'default' in row['roles']: reasons.append(say('This is the default branch.', 'هذا الفرع الافتراضي.', 'default'))
        if 'analysis' in row['roles']: reasons.append(say('This is the analysis branch: choose another one first.', 'هذا فرع التحليل: اختر غيره أولًا.', 'analysis'))
        if (held := self._held_block(row['worktree'])): reasons.append(held)
        if any(r['state'] in ACTIVE + ('queued',) for r in row['runs']):
            reasons.append(say('A run that is not over uses this branch.', 'فيه تشغيل لم ينته يستخدم هذا الفرع.', 'run_uses_it'))
        reasons += self._busy([name])
        return reasons

    @staticmethod
    def _held_block(held):
        """Why the worktree holding a branch keeps it from deletion: it is the project folder, or has unsaved changes; None."""
        if held and held['current']:
            return say('It is checked out in your project folder.', 'مفتوح في مجلد مشروعك.', 'checked_out')
        if held and (held['dirty'] is None or held['dirty']['tracked'] or held['dirty']['untracked']):
            return say(f"It is checked out in another worktree with unsaved changes: {held['path']}. Save or remove them first.",
                       f"مفتوح في نسخة عمل أخرى فيها تعديلات غير محفوظة: {held['path']}. احفظها أو احذفها أولًا.", 'worktree_dirty')
        return None

    def _remote_blocks(self, row, inventory):
        reasons = []
        if inventory['protected'].get(row['name']): reasons.append(say('This branch is protected.', 'هذا الفرع محمي.', 'protected'))
        if 'default' in row['roles']: reasons.append(say('This is the default branch on the remote.', 'هذا الفرع الافتراضي في المستودع البعيد.', 'default'))
        recorded = row['ownership'].get('recorded_tip')
        local = self.tip(f"refs/heads/{row['name']}")
        known = {c for c in (recorded, local) if c}
        if row['ownership']['owner'] == 'eaos' and row['tip'] not in known and not any(
                git(self.project, 'merge-base', '--is-ancestor', row['tip'], c).returncode == 0 for c in known):
            reasons.append(say("The remote copy has commits EAOS did not record: it is left to you.",
                               'النسخة البعيدة فيها commit لم يسجله EAOS: هي متروكة لك.', 'remote_unrecorded'))
        reasons += self._busy([row['name']])
        return reasons

    def _row(self, name, kind='local', remote=None, base=None):
        ref = self._ref_of(name, kind, remote)
        inventory = self.inventory(base)
        row = next((r for r in inventory['branches'] if r['ref'] == ref), None)
        if row is None: raise KeyError(name)
        return row, inventory

    # ------------------------------------------------------------------ the lock and the history
    def _locked(self):
        """The project's branch lock, held for one change; LookupError when another change holds it."""
        handle = open(self.store.folder / 'branches.lock', 'a+')
        try: fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            raise Blocked([say('Another branch change is running for this project: wait a moment and refresh.',
                                'فيه تغيير آخر على الفروع يعمل لهذا المشروع: انتظر لحظة وحدّث.', 'locked')], needs='refresh')
        return handle

    def _start(self, action, label, branches, inputs):
        run = 'b' + datetime.now().strftime('%Y%m%d-%H%M%S-') + secrets.token_hex(3)
        record = {'id': run, 'action': action, 'verb': None, 'label': label, 'inputs': inputs, 'cards': [], 'selection': None,
                  'assistant': None, 'mode': 'direct', 'state': 'running', 'attempt': 1, 'created': now(), 'queued_at': now(),
                  'started': now(), 'read': False, 'context': self.run_context(), 'branch_op': {'branches': branches}}
        self.store.save(record, new=True)
        self.store.append(run, 'action', {'en': f"You asked: {label['en']}", 'ar': f"طلبت: {label['ar']}"},
                          {'action': action, 'by': 'person', 'arguments': inputs})
        return run

    def _finish(self, run, ok, text, data, outcome=None):
        # the standard run result (runs.py), in the run and in its result event, so every page reads a branch operation
        # like any run: it made no work branch of its own; what it did is the answer
        result = {'branch': None, 'diff_stat': None, 'tests': None, 'cards_closed': [], 'indicators': [], 'answer': data}
        self.store.append(run, 'result' if ok else 'error', text, result if ok else {**data, 'recoverable': True})
        fields = {'result': result, **({'outcome': outcome} if outcome else {})}
        self.manager.set_state(run, 'done' if ok else 'failed', '' if ok else str(data.get('reason') or '')[:200], **fields)
        return self.actions.public(self.store.load(run))

    def _spend(self, body, action, bound):
        if not self.locks.spend(body.get('confirm'), action, bound, self.project):
            raise Blocked([say('This needs your explicit confirmation: open its preview and confirm.', 'هذا يحتاج تأكيدك الصريح: افتح المعاينة وأكّد.', 'confirm')],
                          needs='confirm')
