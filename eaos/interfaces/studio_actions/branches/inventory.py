"""The Branches page's reading: every branch with its roles and how it compares with the base, and one branch in detail."""

from .common import COMMITS_SHOWN, DIFF_LIMIT, FILES_SHOWN, REFS_SHOWN, _out, _roles, git, say, valid_name
from ....core.system.clock import now


class Inventory:
    # ------------------------------------------------------------------ reading
    def inventory(self, base=None):
        """Every local and remote branch, honestly: what git says and nothing more. Remote refs are as last fetched."""
        if not self.is_repo():
            return {'git': False, 'reason': say('This folder is not a git repository.', 'هذا المجلد ليس مستودع git.', 'not_git'), 'branches': []}
        state = self.state()
        head = self.head()
        default = self.default_branch()
        policy = self.policy(default)
        context = self.context(state, head)
        base = base or context['analysis']['branch']
        if base: valid_name(self.project, base)
        base_tip = self.tip(f'refs/heads/{base}') if base else None
        worktrees = self.worktrees()
        waves, registry, links = self.waves(state), self._registry(), self.run_links()
        known = {'state': state, 'head': head, 'context': context, 'default': default, 'policy': policy, 'base': base,
                 'base_tip': base_tip, 'held': {row['branch']: row for row in worktrees if row['branch']},
                 'waves': waves, 'registry': registry, 'links': links}
        refs = self.refs()
        rows = [self._branch_row(ref_row, known) for ref_row in refs[:REFS_SHOWN]]
        return {'git': True, 'project': self.project.name, 'head': head, 'context': context, 'base': base, 'base_tip': base_tip,
                'default': default, 'remotes': self.remotes(), 'has_origin': 'origin' in self.remotes(),
                'last_fetch': self.last_fetch(), 'worktrees': worktrees, 'protected': policy['protected'],
                'branches': rows, 'truncated': len(refs) > REFS_SHOWN, 'recovery': self.recoveries(),
                'missing_linked': _missing_linked(links, rows), 'checked_at': now('milliseconds')}

    def _branch_row(self, ref_row, known):
        """One branch as the inventory shows it: its tip, roles, protection, owner, how it compares with the base, its
        worktree and the runs on it."""
        kind, remote, name, ref, tip, when, subject, upstream, track = ref_row
        base, base_tip = known['base'], known['base_tip']
        behind, ahead = self.counts(base_tip, tip) if base_tip else (None, None)
        owner = self.ownership(name, tip, known['state'], known['waves'], known['registry'])
        worktree = known['held'].get(name) if kind == 'local' else None
        return {'id': ref, 'name': name, 'kind': kind, 'remote': remote, 'ref': ref, 'tip': tip, 'last_commit': when or None,
                'subject': subject[:160], 'upstream': upstream, 'tracking': track,
                'roles': _roles(kind, name, known), 'protected': known['policy']['protected'].get(name), 'ownership': owner,
                'work': owner['owner'] != 'unknown',
                'compare': {'base': base, 'ahead': ahead, 'behind': behind, 'merged': None if ahead is None else ahead == 0},
                'worktree': {'path': worktree['path'], 'current': worktree['current'], 'dirty': worktree['dirty']} if worktree else None,
                'runs': known['links'].get(name, []) if kind == 'local' else [],
                'remote_as_of': self.last_fetch() if kind == 'remote' else None}

    def _ref_of(self, name, kind='local', remote=None):
        valid_name(self.project, name)
        if kind == 'remote':
            if remote not in self.remotes(): raise ValueError('no such remote')
            return f'refs/remotes/{remote}/{name}'
        if kind != 'local': raise ValueError('kind must be local or remote')
        return f'refs/heads/{name}'

    def checks_of(self, name, tip):
        """The checks recorded for this exact commit of the branch: {status: passed|failed|not_recorded, at, commit, ...}."""
        entry = (self._registry().get('branches') or {}).get(name) or {}
        for row in reversed(entry.get('checks') or []):
            if row.get('commit') == tip: return {**row, 'status': row.get('status') or 'not_recorded'}
        return _wave_checks(self.waves().get(name), tip) or {'status': 'not_recorded', 'commit': tip}

    def detail(self, name, kind='local', remote=None, base=None, path=None):
        """The drawer: commits ahead of the base, changed files, a bounded diff, recorded checks, runs, lineage, the merge
        destination recommended and confirmed, and every command with the reason it is blocked."""
        ref = self._ref_of(name, kind, remote)
        tip = self.tip(ref)
        if not tip: raise KeyError(name)
        inventory = self.inventory(base)
        row = next(r for r in inventory['branches'] if r['ref'] == ref)
        base_tip = inventory['base_tip']
        commits, files, diff, cut = self._against_base(base_tip, tip, path) if base_tip else ([], [], '', False)
        owner = row['ownership']
        confirmed = self._merge_confirmed(name)
        commands = self.commands(row, inventory)
        return {'branch': row, 'base': inventory['base'], 'base_tip': base_tip, 'commits': commits, 'commits_truncated': len(commits) >= COMMITS_SHOWN,
                'files': files, 'files_total': len(files), 'diff': diff, 'diff_cut': cut, 'checks': self.checks_of(name, tip),
                'runs': row['runs'], 'lineage': {'parent': owner.get('base'), 'parent_commit': owner.get('base_commit'), 'evidence': owner.get('evidence'),
                                                  'recorded_at': owner.get('recorded_at')}
                if owner['owner'] != 'unknown' else None,
                'destination': {'recommended': owner.get('base'), 'confirmed': confirmed}, 'commands': commands, 'checked_at': now('milliseconds')}

    def _against_base(self, base_tip, tip, path):
        """(the commits ahead of the base, the files changed, the diff (of `path` alone when given) cut to DIFF_LIMIT,
        whether it was cut)."""
        start = _out(self.project, 'merge-base', base_tip, tip) or base_tip
        log = git(self.project, 'log', f'--max-count={COMMITS_SHOWN}', '--format=%H%x00%an%x00%ae%x00%cI%x00%s', f'{base_tip}..{tip}')
        commits = [dict(zip(('commit', 'author', 'email', 'at', 'subject'), line.split('\x00'))) for line in log.stdout.splitlines()]
        status = git(self.project, '-c', 'core.quotePath=false', 'diff', '--name-status', start, tip).stdout.splitlines()
        files = [{'status': line.split('\t')[0], 'path': line.split('\t')[-1]} for line in status[:FILES_SHOWN]]
        args = ['diff', start, tip] + (['--', path] if path else [])
        if path and path not in {f['path'] for f in files}: raise ValueError('that file is not changed on this branch')
        diff = git(self.project, '-c', 'core.quotePath=false', *args).stdout
        return commits, files, diff[:DIFF_LIMIT], len(diff) > DIFF_LIMIT

    def _merge_confirmed(self, name):
        """Where the branch was confirmed merged: as recorded, else by the person's accept of its batch; None."""
        wave = self.waves().get(name) or {}
        entry = (self._registry().get('branches') or {}).get(name) or {}
        return entry.get('merged_into') or ({'branch': wave.get('target'), 'at': wave.get('merged_at'), 'via': 'accept'} if wave.get('status') == 'accepted' else None)

    def commands(self, row, inventory):
        """Every command for this branch, available or with the reasons it is blocked."""
        out = {}
        if row['kind'] == 'local':
            out['select_analysis'] = [] if 'analysis' not in row['roles'] else [say('Already the analysis branch.', 'هو فرع التحليل الآن.', 'already')]
            target = row['ownership'].get('base') or inventory['context']['analysis']['branch']
            out['merge'] = self._merge_blocks(row, target, inventory, preview=False)
            out['delete_local'] = self._delete_blocks(row, inventory)
        else:
            out['select_analysis'] = []
            out['delete_remote'] = self._remote_blocks(row, inventory)
        return {name: {'available': not reasons, 'blocked': reasons} for name, reasons in out.items()}


def _missing_linked(links, rows):
    """The branches runs are linked to that are no local branch any more, with their runs."""
    gone = sorted(set(links) - {r['name'] for r in rows if r['kind'] == 'local'})
    return [{'name': name, 'runs': links[name]} for name in gone]


def _wave_checks(wave, tip):
    """The checks of an EAOS batch handed over on the branch at `tip`: its gates passed, or failed; None."""
    if not (wave and wave.get('status') == 'applied' and (wave.get('tip') is None or wave.get('tip') == tip)): return None
    return {'status': 'passed' if wave.get('kept') else 'failed', 'commit': tip, 'source': 'wave',
            'summary': f"EAOS's batch gates: {len(wave.get('kept') or [])} change(s) passed, {len(wave.get('failed') or {})} left out"}
