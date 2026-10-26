"""What git and the state say about the branches: the head, the remotes, the worktrees, each branch's owner, the
analysis branch, and where a Fix run builds and delivers.
"""
import fcntl
from pathlib import Path

from ....core.project import branches as reading, state as project_state
from ....core.project.runs import ACTIVE, TERMINAL, _read_json, _write_json, now
from .common import EAOS_EMAIL, _out, _when, git, say, work_of


class StateView:
    # ------------------------------------------------------------------ what git and the state say
    def is_repo(self):
        return git(self.project, 'rev-parse', '--git-dir').returncode == 0

    def state(self):
        return project_state.load(self.project) or {}

    def head(self):
        """{branch, detached, commit, unborn}: the checkout of the project's own folder."""
        branch = _out(self.project, 'symbolic-ref', '--quiet', '--short', 'HEAD')
        commit = _out(self.project, 'rev-parse', '--verify', '--quiet', 'HEAD^{commit}')
        return {'branch': branch, 'detached': branch is None and bool(commit), 'commit': commit, 'unborn': commit is None}

    def remotes(self):
        return sorted((_out(self.project, 'remote') or '').split())

    def default_branch(self):
        """{name, source}: a remote's HEAD when known (eaos/core/project/branches.py remote_default)."""
        return reading.remote_default(self.project)

    def worktrees(self):
        """Every worktree of the repository, as shown: the paths without the home folder or the project's own path."""
        return [{**row, 'path': self.store.scrub(row['path'])} for row in self._worktrees()]

    def _worktrees(self):
        """Every worktree of the repository: path, branch (or detached), head, and its unsaved changes."""
        rows = _listed_worktrees(git(self.project, 'worktree', 'list', '--porcelain').stdout)
        here = Path(self.project).resolve()
        for row in rows:
            path = Path(row['path'])
            row['current'] = path.resolve() == here
            row['dirty'] = reading.dirty(path) if path.is_dir() and not row['prunable'] else None
        return rows

    def last_fetch(self):
        common = _out(self.project, 'rev-parse', '--git-common-dir')
        if not common: return None
        path = Path(common) if Path(common).is_absolute() else Path(self.project) / common
        try: return _when((path / 'FETCH_HEAD').stat().st_mtime)
        except OSError: return None

    def refs(self):
        """[(kind, remote, name, full ref, tip, date, subject, upstream, track)] of refs/heads and refs/remotes."""
        fields = '%(refname)%00%(objectname)%00%(committerdate:iso-strict)%00%(subject)%00%(upstream:short)%00%(upstream:track,nobracket)%00%(symref)'
        done = git(self.project, 'for-each-ref', f'--format={fields}', '--sort=-committerdate', 'refs/heads', 'refs/remotes')
        remotes = sorted(self.remotes(), key=len, reverse=True)
        rows = []
        for line in done.stdout.splitlines():
            ref, tip, when, subject, upstream, track, symref = (line.split('\x00') + [''] * 7)[:7]
            if symref: continue                                    # refs/remotes/origin/HEAD points at a branch
            if ref.startswith('refs/heads/'):
                rows.append(('local', None, ref[len('refs/heads/'):], ref, tip, when, subject, upstream or None, track or None))
            elif ref.startswith('refs/remotes/'):
                rest = ref[len('refs/remotes/'):]
                remote = next((r for r in remotes if rest.startswith(r + '/')), None)
                if remote: rows.append(('remote', remote, rest[len(remote) + 1:], ref, tip, when, subject, None, None))
        return rows

    def tip(self, ref):
        return _out(self.project, 'rev-parse', '--verify', '--quiet', ref + '^{commit}')

    def counts(self, base_tip, tip):
        """(behind, ahead) of tip against base_tip, or (None, None) when git cannot say."""
        if not base_tip or not tip: return None, None
        found = (_out(self.project, 'rev-list', '--left-right', '--count', f'{base_tip}...{tip}') or '').split()
        return (int(found[0]), int(found[1])) if len(found) == 2 else (None, None)

    # ------------------------------------------------------------------ provenance and policy
    def _registry(self):
        return _read_json(self.store.folder / 'branch-provenance.json', {}) or {}

    def record(self, name, **fields):
        """Durable provenance of a branch EAOS made or changed: merged into the existing entry, never replacing it."""
        path = self.store.folder / 'branch-provenance.json'
        with (self.store.folder / 'branch-provenance.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            data = _read_json(path, {}) or {}
            entry = data.setdefault('branches', {}).setdefault(name, {'created_by': 'eaos', 'at': now()})
            for key, value in fields.items():
                if key == 'checks': entry.setdefault('checks', []).append(value)
                elif key == 'history': entry.setdefault('history', []).append(value)
                else: entry[key] = value
            _write_json(path, data)
            return entry

    def waves(self, state=None):
        """{branch: wave} of every EAOS wave and build in the project's state, on every branch it worked on."""
        state = state if state is not None else self.state()
        found = {}
        parts = [(state.get('branch'), state)] + [(name, part) for name, part in (state.get('by_branch') or {}).items()]
        for target, part in parts:
            for wave in part.get('waves') or []:
                if wave.get('branch'): found[wave['branch']] = {**wave, 'target': target or state.get('home_branch')}
        return found

    def ownership(self, name, tip, state=None, waves=None, registry=None):
        """Who made the branch, from durable records only: {owner: eaos|unknown, kind, evidence, ...}. A branch EAOS made
        that has commits by anyone else since is `shared`: EAOS no longer holds all of its work."""
        waves = self.waves(state) if waves is None else waves
        registry = (self._registry() if registry is None else registry).get('branches') or {}
        wave, entry = waves.get(name), registry.get(name)
        if not wave and not (entry and entry.get('created_by') == 'eaos'):
            return {'owner': 'unknown', 'kind': None, 'evidence': None, 'base': None, 'base_commit': None, 'foreign_commits': None}
        out = _made_by_a_batch(wave, entry) if wave else _made_as_recorded(entry)
        foreign = self._foreign_commits(out['base_commit'], tip)
        out['foreign_commits'] = foreign
        if foreign: out['owner'] = 'shared'
        return out

    def _foreign_commits(self, start, tip):
        """How many commits since `start` someone other than EAOS made; None when git cannot say."""
        if not (start and tip and git(self.project, 'cat-file', '-e', start + '^{commit}').returncode == 0): return None
        authors = git(self.project, 'log', '--no-merges', '--format=%ae', f'{start}..{tip}')
        return sum(1 for a in authors.stdout.split() if a != EAOS_EMAIL) if authors.returncode == 0 else None

    def policy(self, default=None):
        """The branches protected from a merge, enforced on the server: eaos/core/project/branches.py policy."""
        return reading.policy(self.project, default or self.default_branch())

    def run_links(self):
        """{branch: [{id, role, state, label, created}]}: the runs whose recorded context or work branch is this branch."""
        links = {}
        for row in self.store.all():
            summary = {'id': row['id'], 'state': row.get('state'), 'label': row.get('label'), 'created': row.get('created'), 'action': row.get('action')}
            for name, role in _branches_of(row): links.setdefault(name, []).append({**summary, 'role': role})
        return links

    def active_runs(self, exclude=None, queued=False):
        states = ACTIVE + (('queued',) if queued else ())
        return [r for r in self.store.all() if r.get('state') in states and not r.get('read') and r['id'] != exclude]

    def context(self, state=None, head=None):
        """The four branches the Studio never mixes up: the checkout, the analysis branch, the report's branch and the
        base the person compares against (the analysis branch unless they choose another)."""
        state = state if state is not None else self.state()
        head = head or self.head()
        analysis = state.get('branch') or head['branch']
        studio = self.actions._studio()
        manifest = _read_json(Path(studio) / 'manifest.json', {}) if studio else {}
        scanned = (manifest or {}).get('scanned') or {}
        tip = self.tip(f'refs/heads/{analysis}') if analysis else head['commit']
        return {'checkout': head, 'analysis': {'branch': analysis, 'selected': bool(state.get('branch')), 'tip': tip,
                                               'detached': analysis is None and head['detached']},
                'report': {'branch': scanned.get('branch'), 'commit': scanned.get('commit'), 'at': scanned.get('at'),
                           'recorded': scanned.get('recorded', False), 'detached': scanned.get('detached')},
                'scan': {'branch': state.get('scanned_branch'), 'commit': state.get('scanned_commit'), 'at': state.get('scanned')},
                'dirty': reading.dirty(self.project) if self.is_repo() else None}

    def run_context(self):
        """What a new run is made on, recorded on it when it is created so a later change of branch never retargets it
        silently: {analysis_branch, analysis_commit, checkout, detached, at}."""
        if not self.is_repo(): return {'analysis_branch': None, 'analysis_commit': None, 'checkout': None, 'detached': None, 'at': now()}
        context = self.context()
        return {'analysis_branch': context['analysis']['branch'], 'analysis_commit': context['analysis']['tip'],
                'checkout': context['checkout']['branch'], 'detached': context['checkout']['detached'], 'at': now()}

    def work_branch(self, record):
        """A run's work branch as it is now: {name, exists, tip, recorded_tip, deleted, recovery} | {state: not_created_yet |
        not_required}."""
        base = (record.get('context') or {}).get('analysis_branch')
        if record.get('branch_op'):
            return {'state': 'not_required', 'acted_on': record['branch_op'].get('branches') or [], 'base': base}
        name = work_of(record)
        if name: return self._work_now(record, name, base)
        changes = record.get('verb') == 'fix' or record.get('action') in ('fix_start', 'fix_finish', 'build_start', 'build_finish')
        if changes and record.get('state') not in TERMINAL: return {'state': 'not_created_yet', 'base': base}
        return {'state': 'not_required' if not changes else 'none_created', 'base': base}

    def _work_now(self, record, name, base):
        """A run's work branch `name` as it is now: there, merged and deleted, or deleted (with its recovery)."""
        tip = self.tip(f'refs/heads/{name}') if self.is_repo() else None
        wave = self.waves().get(name) or {}
        return {'state': 'exists' if tip else ('merged_and_deleted' if wave.get('status') == 'accepted' else 'deleted'),
                'name': name, 'tip': tip, 'recorded_tip': (record.get('result') or {}).get('branch_tip'),
                'recovery': self._open_recovery(name), 'base': base}

    def _open_recovery(self, name):
        """The id of the last recovery of the local branch `name`, while it is not restored; None."""
        recovery = next((r for r in reversed(self.recoveries()) if r['branch'] == name and r['where'] == 'local'), None)
        return recovery['id'] if recovery and not recovery.get('restored') else None

    def blocked_target(self, name, protected=None, head=None):
        """Why nothing is merged into `name` from here, or None (eaos/core/project/branches.py blocked_target)."""
        return reading.blocked_target(self.project, name, protected, (head or self.head())['branch'])

    def fix_where(self, wanted=None, hint=None):
        """Where a Fix run builds and delivers, as its preview shows and the person may change it:
        {base: {branch, commit, short, when, checked_out}, mode, deliver_as, merge_into, branches: [{name, short, blocked}],
        continuable: [{name, short}], direct_blocked, problem}. base defaults to the analysis branch; mode is `new` (a new
        branch, by default `eaos/<base>/<group>` for a group of cards when that name is free, else `eaos/<base>/wave-N`:
        agent_tools.delivery), `continue` (an EAOS work branch still waiting for a decision: deliver_as names it) or
        `direct` (deliver_as is the base itself: the batch lands on it once it passes; never a protected one); merge_into
        defaults to the branch open in the project folder. The branches offered are the person's own (no EAOS, bot or
        archive branch); a protected one is shown with its reason, never as a base or a target. The base commit is what the
        confirm token pins, so a branch that moves after the preview is caught before anything runs."""
        from ....journeys import agent_tools
        wanted = wanted if isinstance(wanted, dict) else {}
        state, head = self.state(), self.head()
        working = state.get('branch') or head['branch']
        base = str(wanted.get('base') or '').strip() or working
        protected = self.policy()['protected']
        blocked = lambda name: self.blocked_target(name, protected, head)
        locals_, offered = self._fix_choices(blocked)
        out = {'base': None, 'mode': 'new', 'deliver_as': None, 'merge_into': None, 'problem': None, 'direct_blocked': None,
               'continuable': [], 'branches': offered}
        row = next((r for r in locals_ if r[0] == base), None)
        if row is None:
            out['problem'] = say(f'There is no branch named {base} in this project.', f'ما فيه فرع اسمه {base} في هذا المشروع.', 'no_base')
            return out
        out['base'] = {'branch': base, 'commit': row[1], 'short': row[1][:7], 'when': row[2] or None, 'checked_out': base == head['branch']}
        view = self._fix_view(state, base, working)
        out['continuable'] = _continuable(agent_tools.work_branches(view), locals_)
        out['direct_blocked'] = self._direct_blocked(base, blocked(base))
        return self._fix_delivery(out, view, base, wanted, hint, head, blocked)

    def _fix_delivery(self, out, view, base, wanted, hint, head, blocked):
        """Where the batch goes: on the base itself, on an EAOS branch waiting for a decision, or on a new one."""
        from ....journeys import agent_tools
        asked = str(wanted.get('deliver_as') or '').strip()
        merge = str(wanted.get('merge_into') or '') or head['branch']
        if asked == base and out['direct_blocked']: return out | {'mode': 'direct', 'deliver_as': base, 'merge_into': base, 'problem': out['direct_blocked']}
        try:
            out['deliver_as'], out['merge_into'] = agent_tools.delivery(view, asked or self._named_after(view, base, hint) or None, merge)
        except ValueError as problem: return _undeliverable(out, problem, asked, base, merge)
        return self._fix_merge(out, base, blocked)

    def _fix_merge(self, out, base, blocked):
        """The mode the delivery means, and a problem when the branch to merge into is protected."""
        out['mode'] = 'direct' if out['deliver_as'] == base else 'continue' if out['deliver_as'] in {c['name'] for c in out['continuable']} else 'new'
        target = blocked(out['merge_into'])
        if target:
            out['problem'] = say(f"{out['merge_into']} is protected ({target['en']}): choose another branch to merge into.",
                                 f"{out['merge_into']} محمي ({target['ar']}): اختر فرعًا ثانيًا يُدمج فيه.", 'protected_target')
        return out

    def _fix_choices(self, blocked):
        """The local branches (name, tip, when), and the person's own offered (no EAOS, bot or archive branch)."""
        locals_ = [(name, tip, when) for kind, _, name, _, tip, when, *_ in self.refs() if kind == 'local']
        return locals_, [{'name': name, 'short': tip[:7], 'blocked': blocked(name)} for name, tip, _ in locals_ if reading._persons(name) and not name.startswith(reading.ARCHIVED)]

    def _fix_view(self, state, base, working):
        """The state as fix_start sees it once the base is chosen: that branch's own batches give the next number."""
        view = dict(state, project=self.project)
        if base != working and state:
            view = {k: v for k, v in view.items() if k not in reading.KEYS}
            view.update((state.get('by_branch') or {}).get(base, {}), branch=base)
        elif not state: view['branch'] = base
        return view

    def _direct_blocked(self, base, blocked):
        """Why fixes may not land on the base directly (a protected branch, or the project's main), or None."""
        why = blocked or ({'code': 'main', 'en': reading.protected(self.project, base), 'ar': 'الفرع الرئيسي'} if reading.protected(self.project, base) else None)
        if not why: return None
        return say(f"{base} is protected ({why['en']}): fixes never land on it directly.",
                   f"{base} محمي ({why['ar']}): الإصلاحات ما تنزل عليه مباشرة أبدًا.", 'protected_direct')

    def _named_after(self, view, base, hint):
        """`eaos/<base>/<group>` for a group of cards (`hint`), when that name is free and git takes it; else ''."""
        from ....journeys import agent_tools
        if not hint: return ''
        named = f"eaos/{reading.slug(base)}/{reading.slug(str(hint)).lower()[:40]}"
        if agent_tools.guided._branch_exists(view, named) or git(self.project, 'check-ref-format', '--branch', named).returncode: return ''
        return named

    def accept_where(self):
        """What Accept shows before it merges: the waiting branch, the branch it merges into (the fix preview's choice,
        else the branch open in the project folder), the person's branches to choose from (a protected one shown with its
        reason, not choosable) and the choice to delete the branch after merging (on by default)."""
        state = self.state()
        head = self.head()
        wave = project_state.waiting_batch(state)
        protected = self.policy()['protected']
        rows = [(name, tip) for kind, _, name, _, tip, *_ in self.refs() if kind == 'local' and reading._persons(name)
                and not name.startswith(reading.ARCHIVED)]
        target = (wave or {}).get('merge_into') or head['branch'] or state.get('branch')
        return {'branch': (wave or {}).get('branch'), 'target': target, 'delete_after': True,
                'targets': [{'name': name, 'short': tip[:7], 'blocked': self.blocked_target(name, protected, head)} for name, tip in rows]}


def _listed_worktrees(porcelain):
    """The worktrees `git worktree list --porcelain` lists: path, branch (or detached), head, locked, prunable."""
    rows, row = [], {}
    for line in porcelain.splitlines() + ['']:
        if not line:
            if row: rows.append(row)
            row = {}
            continue
        key, _, value = line.partition(' ')
        if key == 'worktree': row = {'path': value, 'branch': None, 'head': None, 'detached': False, 'locked': False, 'prunable': False}
        elif key == 'HEAD': row['head'] = value
        elif key == 'branch': row['branch'] = value[len('refs/heads/'):] if value.startswith('refs/heads/') else value
        elif key == 'detached': row['detached'] = True
        elif key in ('locked', 'prunable'): row[key] = True
    return rows


def _made_by_a_batch(wave, entry):
    """The owner of a branch an EAOS batch or build made, from the state (and its provenance record, when any)."""
    kind = 'build' if wave.get('via') == 'build' else 'wave'
    return {'owner': 'eaos', 'kind': kind, 'wave': wave.get('number'),
            'status': wave.get('status'), 'evidence': f"EAOS state: {kind} {wave.get('number')} ({wave.get('status')})",
            'base': wave.get('target'), 'base_commit': wave.get('base'), 'recorded_tip': wave.get('tip') or (entry or {}).get('tip'),
            'run': (entry or {}).get('run')}


def _made_as_recorded(entry):
    """The owner of a branch EAOS made, from its provenance record."""
    return {'owner': 'eaos', 'kind': entry.get('kind') or 'task', 'evidence': f"EAOS provenance record ({entry.get('kind') or 'task'})", 'recorded_at': entry.get('at'),
            'base': entry.get('base'), 'base_commit': entry.get('base_commit'), 'recorded_tip': entry.get('tip'), 'run': entry.get('run')}


def _branches_of(row):
    """(branch, role) of each branch a run is linked to: its work branch, the base it was made on (a branch operation's
    aside), the branches a branch operation acted on."""
    context = row.get('context') or {}
    work = work_of(row)
    if work: yield work, 'work'
    if context.get('analysis_branch') and context.get('analysis_branch') != work and not row.get('branch_op'):
        yield context['analysis_branch'], 'base'
    for name in (row.get('branch_op') or {}).get('branches') or []:
        if name not in (work, context.get('analysis_branch')): yield name, 'operation'


def _continuable(names, locals_):
    """The EAOS work branches a new batch may continue on, each with its short commit."""
    tips = {name: tip for name, tip, _ in locals_}
    return [{'name': name, 'short': (tips.get(name) or '')[:7]} for name in names]


def _undeliverable(out, problem, asked, base, merge):
    """The fix preview when the delivery asked for is refused: why, and what was asked."""
    return out | {'problem': say(str(problem), str(problem), 'delivery'), 'deliver_as': asked or None, 'merge_into': merge,
                  'mode': 'direct' if asked == base else 'new'}
