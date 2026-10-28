"""Fetching the remotes, the project's protection policy, and how fresh each branch is."""
from ....core.project import branches as reading
from ....core.project.runs import _write_json, now
from .common import Blocked, git, say, valid_name
from ....core.system.files import read_json


class Remotes:
    # ------------------------------------------------------------------ remotes and policy
    def fetch(self, body):
        """Bring the last-known remote refs up to date (git fetch --prune of one remote): nothing local changes."""
        remote = body.get('remote') or 'origin'
        if remote not in self.remotes(): raise ValueError('no such remote')
        handle = self._locked()
        try:
            run = self._start('branch_fetch', {'en': f'Refresh the branches of {remote}', 'ar': f'حدّث فروع {remote}'}, [], {'remote': remote})
            done = git(self.project, 'fetch', '--prune', '--no-tags', remote, timeout=180)
            ok = done.returncode == 0
            return {'run': self._finish(run, ok, {'en': f'{remote} refreshed.' if ok else f'Could not reach {remote}; the last known branches stay shown.',
                                                  'ar': f'تحدّث {remote}.' if ok else f'ما قدرت أوصل {remote}؛ تبقى آخر فروع معروفة ظاهرة.'},
                                        {'remote': remote, 'reason': None if ok else done.stderr.strip()[-300:], 'branches': []})}
        finally:
            handle.close()

    def preview_protect(self, body):
        name = valid_name(self.project, body.get('branch'))
        bound = {'branch': name, 'protected': bool(body.get('protected'))}
        return {**bound, 'confirm': self.locks.confirm('branch_protect', bound, self.project)}

    def protect(self, body):
        """Protect or unprotect one branch in this project's policy; removing protection needs its confirm token."""
        name = valid_name(self.project, body.get('branch'))
        bound = {'branch': name, 'protected': bool(body.get('protected'))}
        if not bound['protected']:
            self._spend(body, 'branch_protect', bound)
            if reading.is_eaos_itself(self.project) and name == 'main':
                raise Blocked([say("EAOS's own main stays protected.", 'main في EAOS نفسه يبقى محميًا.', 'eaos_main')])
        handle = self._locked()
        try:
            self._save_protection(name, bound['protected'])
            run = self._start('branch_protect', {'en': f"{'Protect' if bound['protected'] else 'Unprotect'} {name}", 'ar': f"{'احمِ' if bound['protected'] else 'ارفع الحماية عن'} {name}"},
                              [name], bound)
            return {'run': self._finish(run, True, {'en': 'Policy saved.', 'ar': 'حُفظت السياسة.'}, {**bound, 'branches': [name]}), 'protected': self.policy()['protected']}
        finally:
            handle.close()

    def _save_protection(self, name, protect):
        """The project's policy file with `name` protected (`protect`) or unprotected."""
        path = self.store.folder / reading.POLICY
        saved = read_json(path, {}) or {}
        protected, unprotected = set(saved.get('protected') or []), set(saved.get('unprotected') or [])
        (protected.add if protect else protected.discard)(name)
        (unprotected.discard if protect else unprotected.add)(name)
        _write_json(path, {'protected': sorted(protected), 'unprotected': sorted(unprotected), 'at': now()})

    # ------------------------------------------------------------------ freshness
    def freshness(self):
        """The live answer to "is the check current?" for the branch EAOS works on (eaos/core/project/branches.py freshness)."""
        from ....core.system.version_info import digest
        state = self.state()
        if not state: return {'state': 'unknown', 'reason': 'not_scanned', 'checked_at': now(), 'eaos_updated': False}
        found = reading.freshness(state)
        if found['reason'] == 'not_scanned':
            # the analysis branch has no scan of its own yet, but the report on screen is another branch's: say so
            shown = self.context(state)['report']
            if shown['commit'] and shown['branch'] != found['branch']:
                found = {**found, 'state': 'other_branch', 'reason': 'analysis_branch_not_scanned', 'scanned_commit': shown['commit'],
                         'scanned_branch': shown['branch'], 'scanned_detached': shown['detached'], 'scanned_at': shown['at'], 'recorded': shown['recorded']}
        stamp = {}
        try:
            from ....journeys import guided
            stamp = guided.report_stamp(state)
        except Exception:
            pass
        return {**found, 'eaos_updated': bool(state.get('scanned_with')) and state.get('scanned_with') != digest(),
                'report_built': stamp.get('built'), 'checked_at': now(), 'project': self.project.name, 'project_path': str(self.project)}
