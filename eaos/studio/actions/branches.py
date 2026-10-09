"""Branch control from the Studio (docs/STUDIO-BRANCH-CONTROL.md, NS46.T18) and the live freshness of the scan (NS46.T19).

    control = BranchControl(actions)          # the command centre's Actions: its store, manager, locks and project
    control.inventory(base='develop')         # every local and remote branch, the checkout, worktrees and policy
    control.preview_merge({'source': 'eaos/wave-2', 'target': 'develop'})   # isolated: nothing changes
    control.merge({..., 'confirm': token})    # only with the confirm token of that preview, at the heads it showed

Reading answers at once. A change (select the analysis branch, merge, delete, restore, fetch, protect) goes through the
command centre's locks first (launch token, CSRF, Origin: security.py), then needs a confirm token bound to the exact
heads its preview showed, holds the project's branch lock, and is written to the run history as a run of its own, with
its outcome and how to recover from it.

Git is called with argv lists, never through a shell. A branch name is checked by `git check-ref-format --branch` and
then used only inside a full ref (refs/heads/<name>). Ownership comes only from durable provenance: an EAOS wave or
build in the project's state, or an entry EAOS wrote in runs/branch-provenance.json; a name or a prefix is never proof.
What git does not say stays unknown.

    runs/branch-provenance.json    {branches: {name: {created_by, kind, run, tip, base, base_commit, at, merged_into, checks}}}
    runs/branch-recovery.json      [{id, ref, branch, where, remote, tip, at, run, restored}]
    runs/branch-policy.json        {protected: [...], unprotected: [...]}: the project's own choices over the defaults
    refs/eaos-recovery/<id>        the commit of a deleted branch, kept so the deletion can be undone
"""
import fcntl
import json
import os
import re
import secrets
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .store import ACTIVE, TERMINAL, _read_json, _write_json, now

RECOVERY = 'refs/eaos-recovery/'
EAOS_NAME, EAOS_EMAIL = 'EAOS', 'eaos@localhost'
COMMITS_SHOWN, FILES_SHOWN, REFS_SHOWN = 50, 200, 400
DIFF_LIMIT = 64 * 1024
NAME = re.compile(r'[^\x00-\x20\x7f~^:?*\[\\]{1,200}')
MAIN_NAMES = ('main', 'master')


class Blocked(LookupError):
    """A change that cannot happen now, with every reason in plain words."""

    def __init__(self, reasons, needs=None):
        super().__init__('; '.join(reason['en'] for reason in reasons))
        self.reasons, self.needs = reasons, needs


def say(en, ar, code):
    return {'code': code, 'en': en, 'ar': ar}


def git(project, *args, timeout=60, env=None):
    """git -C project <args> as argv; a timeout is an exit code of 124, never an exception."""
    environment = {**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GIT_OPTIONAL_LOCKS': '0', 'LC_ALL': 'C', **(env or {})}
    try:
        return subprocess.run(['git', '-C', str(project), *args], capture_output=True, text=True, timeout=timeout, env=environment)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, '', 'git timed out')


def _out(project, *args):
    done = git(project, *args)
    return done.stdout.strip() if done.returncode == 0 else None


def _eaos_env():
    return {'GIT_AUTHOR_NAME': EAOS_NAME, 'GIT_AUTHOR_EMAIL': EAOS_EMAIL, 'GIT_COMMITTER_NAME': EAOS_NAME, 'GIT_COMMITTER_EMAIL': EAOS_EMAIL}


def valid_name(project, name):
    """The branch name as given, when git accepts it as a branch name; ValueError otherwise (a leading dash, a control
    character, `..`, a shell metacharacter git refuses, or a name git would rewrite)."""
    if not isinstance(name, str) or name.startswith('-') or not NAME.fullmatch(name):
        raise ValueError('not a valid branch name')
    done = git(project, 'check-ref-format', '--branch', name)
    if done.returncode or done.stdout.strip() != name: raise ValueError('not a valid branch name')
    return name


def work_of(record):
    """The work branch a run made or worked on: its result's branch, except for a branch operation (select, merge,
    delete, ...), whose result names the branches it acted on, not a branch of its own."""
    if record.get('branch_op'): return None
    return (record.get('result') or {}).get('branch') or record.get('work_branch')


def _when(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec='seconds')


class BranchControl:
    def __init__(self, actions):
        self.actions = actions
        self.project = actions.project
        self.store = actions.store
        self.manager = actions.manager
        self.locks = actions.locks

    # ------------------------------------------------------------------ what git and the state say
    def is_repo(self):
        return git(self.project, 'rev-parse', '--git-dir').returncode == 0

    def state(self):
        from ... import guided
        return guided.load(self.project) or {}

    def head(self):
        """{branch, detached, commit, unborn}: the checkout of the project's own folder."""
        branch = _out(self.project, 'symbolic-ref', '--quiet', '--short', 'HEAD')
        commit = _out(self.project, 'rev-parse', '--verify', '--quiet', 'HEAD^{commit}')
        return {'branch': branch, 'detached': branch is None and bool(commit), 'commit': commit, 'unborn': commit is None}

    def remotes(self):
        return sorted((_out(self.project, 'remote') or '').split())

    def default_branch(self):
        """{name, source}: origin's HEAD when known; otherwise unknown (None), never guessed from a name."""
        for remote in self.remotes():
            name = _out(self.project, 'symbolic-ref', '--quiet', '--short', f'refs/remotes/{remote}/HEAD')
            if name: return {'name': name.split('/', 1)[-1], 'source': f'{remote}/HEAD'}
        return {'name': None, 'source': None}

    def worktrees(self):
        """Every worktree of the repository, as shown: the paths without the home folder or the project's own path."""
        return [{**row, 'path': self.store.scrub(row['path'])} for row in self._worktrees()]

    def _worktrees(self):
        """Every worktree of the repository: path, branch (or detached), head, and its unsaved changes."""
        from ... import branches as reading
        done = git(self.project, 'worktree', 'list', '--porcelain')
        rows, row = [], {}
        for line in done.stdout.splitlines() + ['']:
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
        if wave:
            out = {'owner': 'eaos', 'kind': 'build' if wave.get('via') == 'build' else 'wave', 'wave': wave.get('number'),
                   'status': wave.get('status'), 'evidence': f"EAOS state: {'build' if wave.get('via') == 'build' else 'wave'} {wave.get('number')} ({wave.get('status')})",
                   'base': wave.get('target'), 'base_commit': wave.get('base'), 'recorded_tip': wave.get('tip') or (entry or {}).get('tip'),
                   'run': (entry or {}).get('run')}
        else:
            out = {'owner': 'eaos', 'kind': entry.get('kind') or 'task', 'evidence': f"EAOS provenance record ({entry.get('kind') or 'task'})", 'recorded_at': entry.get('at'),
                   'base': entry.get('base'), 'base_commit': entry.get('base_commit'), 'recorded_tip': entry.get('tip'), 'run': entry.get('run')}
        start = out['base_commit']
        foreign = None
        if start and tip and git(self.project, 'cat-file', '-e', start + '^{commit}').returncode == 0:
            authors = git(self.project, 'log', '--no-merges', '--format=%ae', f'{start}..{tip}')
            if authors.returncode == 0: foreign = sum(1 for a in authors.stdout.split() if a != EAOS_EMAIL)
        out['foreign_commits'] = foreign
        if foreign: out['owner'] = 'shared'
        return out

    def policy(self, default=None):
        """{protected: {name: reason}, explicit: {...}}: the default branch on the remote, main and master, every branch
        the project's policy protects; minus the ones the owner explicitly unprotected. Enforced here, on the server."""
        default = default or self.default_branch()
        saved = _read_json(self.store.folder / 'branch-policy.json', {}) or {}
        protected = {}
        if default['name']: protected[default['name']] = say(f"the default branch ({default['source']})", f"الفرع الافتراضي ({default['source']})", 'default')
        for name in MAIN_NAMES:
            protected.setdefault(name, say('named main or master: protected unless the project policy says otherwise',
                                           'اسمه main أو master: محمي ما لم تقل سياسة المشروع غير ذلك', 'main_name'))
        for name in saved.get('protected') or []:
            protected[name] = say('protected by this project\'s policy', 'محمي بسياسة هذا المشروع', 'policy')
        for name in saved.get('unprotected') or []: protected.pop(name, None)
        if self._is_eaos_itself(): protected['main'] = say("EAOS's own main is the owner's mother copy: never changed from here",
                                                            'main في EAOS نفسه هي النسخة الأم للمالك: لا تُغيَّر من هنا', 'eaos_main')
        return {'protected': protected, 'saved': saved}

    def _is_eaos_itself(self):
        try: return 'name = "engineering-audit-os"' in (Path(self.project) / 'pyproject.toml').read_text(encoding='utf-8')
        except OSError: return False

    def run_links(self):
        """{branch: [{id, role, state, label, created}]}: the runs whose recorded context or work branch is this branch."""
        links = {}
        for row in self.store.all():
            context = row.get('context') or {}
            work = work_of(row)
            summary = {'id': row['id'], 'state': row.get('state'), 'label': row.get('label'), 'created': row.get('created'), 'action': row.get('action')}
            if work: links.setdefault(work, []).append({**summary, 'role': 'work'})
            if context.get('analysis_branch') and context.get('analysis_branch') != work and not row.get('branch_op'):
                links.setdefault(context['analysis_branch'], []).append({**summary, 'role': 'base'})
            for name in (row.get('branch_op') or {}).get('branches') or []:
                if name not in (work, context.get('analysis_branch')): links.setdefault(name, []).append({**summary, 'role': 'operation'})
        return links

    def active_runs(self, exclude=None, queued=False):
        states = ACTIVE + (('queued',) if queued else ())
        return [r for r in self.store.all() if r.get('state') in states and not r.get('read') and r['id'] != exclude]

    def context(self, state=None, head=None):
        """The four branches the Studio never mixes up: the checkout, the analysis branch, the report's branch and the
        base the person compares against (the analysis branch unless they choose another)."""
        from ... import branches as reading
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
        if record.get('branch_op'):
            return {'state': 'not_required', 'acted_on': record['branch_op'].get('branches') or [], 'base': (record.get('context') or {}).get('analysis_branch')}
        name = work_of(record)
        if name:
            tip = self.tip(f'refs/heads/{name}') if self.is_repo() else None
            recovery = next((r for r in reversed(self.recoveries()) if r['branch'] == name and r['where'] == 'local'), None)
            wave = self.waves().get(name) or {}
            return {'state': 'exists' if tip else ('merged_and_deleted' if wave.get('status') == 'accepted' else 'deleted'),
                    'name': name, 'tip': tip, 'recorded_tip': (record.get('result') or {}).get('branch_tip'),
                    'recovery': recovery['id'] if recovery and not recovery.get('restored') else None,
                    'base': (record.get('context') or {}).get('analysis_branch')}
        changes = record.get('verb') == 'fix' or record.get('action') in ('fix_start', 'fix_finish', 'build_start', 'build_finish')
        if changes and record.get('state') not in TERMINAL: return {'state': 'not_created_yet', 'base': (record.get('context') or {}).get('analysis_branch')}
        return {'state': 'not_required' if not changes else 'none_created', 'base': (record.get('context') or {}).get('analysis_branch')}

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
        held = {row['branch']: row for row in worktrees if row['branch']}
        waves, registry, links = self.waves(state), self._registry(), self.run_links()
        rows, refs = [], self.refs()
        for kind, remote, name, ref, tip, when, subject, upstream, track in refs[:REFS_SHOWN]:
            behind, ahead = self.counts(base_tip, tip) if base_tip else (None, None)
            owner = self.ownership(name, tip, state, waves, registry)
            roles = [role for role, on in (('checkout', kind == 'local' and name == head['branch']),
                                           ('analysis', kind == 'local' and name == context['analysis']['branch']),
                                           ('report', kind == 'local' and name == context['report']['branch']),
                                           ('base', kind == 'local' and name == base),
                                           ('default', name == default['name'])) if on]
            worktree = held.get(name) if kind == 'local' else None
            rows.append({'id': ref, 'name': name, 'kind': kind, 'remote': remote, 'ref': ref, 'tip': tip, 'last_commit': when or None,
                         'subject': subject[:160], 'upstream': upstream, 'tracking': track,
                         'roles': roles, 'protected': policy['protected'].get(name), 'ownership': owner,
                         'work': owner['owner'] != 'unknown',
                         'compare': {'base': base, 'ahead': ahead, 'behind': behind, 'merged': None if ahead is None else ahead == 0},
                         'worktree': {'path': worktree['path'], 'current': worktree['current'], 'dirty': worktree['dirty']} if worktree else None,
                         'runs': links.get(name, []) if kind == 'local' else [],
                         'remote_as_of': self.last_fetch() if kind == 'remote' else None})
        gone = sorted(set(links) - {r['name'] for r in rows if r['kind'] == 'local'})
        return {'git': True, 'project': self.project.name, 'head': head, 'context': context, 'base': base, 'base_tip': base_tip,
                'default': default, 'remotes': self.remotes(), 'has_origin': 'origin' in self.remotes(),
                'last_fetch': self.last_fetch(), 'worktrees': worktrees, 'protected': policy['protected'],
                'branches': rows, 'truncated': len(refs) > REFS_SHOWN, 'recovery': self.recoveries(),
                'missing_linked': [{'name': name, 'runs': links[name]} for name in gone], 'checked_at': now()}

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
        wave = self.waves().get(name)
        if wave and wave.get('status') == 'applied' and (wave.get('tip') is None or wave.get('tip') == tip):
            return {'status': 'passed' if wave.get('kept') else 'failed', 'commit': tip, 'source': 'wave',
                    'summary': f"EAOS's batch gates: {len(wave.get('kept') or [])} change(s) passed, {len(wave.get('failed') or {})} left out"}
        return {'status': 'not_recorded', 'commit': tip}

    def detail(self, name, kind='local', remote=None, base=None, path=None):
        """The drawer: commits ahead of the base, changed files, a bounded diff, recorded checks, runs, lineage, the merge
        destination recommended and confirmed, and every command with the reason it is blocked."""
        ref = self._ref_of(name, kind, remote)
        tip = self.tip(ref)
        if not tip: raise KeyError(name)
        inventory = self.inventory(base)
        row = next(r for r in inventory['branches'] if r['ref'] == ref)
        base_tip = inventory['base_tip']
        commits, files, diff, cut = [], [], '', False
        if base_tip:
            start = _out(self.project, 'merge-base', base_tip, tip) or base_tip
            log = git(self.project, 'log', f'--max-count={COMMITS_SHOWN}', '--format=%H%x00%an%x00%ae%x00%cI%x00%s', f'{base_tip}..{tip}')
            commits = [dict(zip(('commit', 'author', 'email', 'at', 'subject'), line.split('\x00'))) for line in log.stdout.splitlines()]
            status = git(self.project, '-c', 'core.quotePath=false', 'diff', '--name-status', start, tip).stdout.splitlines()
            files = [{'status': line.split('\t')[0], 'path': line.split('\t')[-1]} for line in status[:FILES_SHOWN]]
            args = ['diff', start, tip] + (['--', path] if path else [])
            if path and path not in {f['path'] for f in files}: raise ValueError('that file is not changed on this branch')
            diff = git(self.project, '-c', 'core.quotePath=false', *args).stdout
            cut = len(diff) > DIFF_LIMIT
            diff = diff[:DIFF_LIMIT]
        owner = row['ownership']
        wave = self.waves().get(name) or {}
        entry = (self._registry().get('branches') or {}).get(name) or {}
        confirmed = entry.get('merged_into') or ({'branch': wave.get('target'), 'at': wave.get('merged_at'), 'via': 'accept'} if wave.get('status') == 'accepted' else None)
        commands = self.commands(row, inventory)
        return {'branch': row, 'base': inventory['base'], 'base_tip': base_tip, 'commits': commits, 'commits_truncated': len(commits) >= COMMITS_SHOWN,
                'files': files, 'files_total': len(files), 'diff': diff, 'diff_cut': cut, 'checks': self.checks_of(name, tip),
                'runs': row['runs'], 'lineage': {'parent': owner.get('base'), 'parent_commit': owner.get('base_commit'), 'evidence': owner.get('evidence'),
                                                  'recorded_at': owner.get('recorded_at')}
                if owner['owner'] != 'unknown' else None,
                'destination': {'recommended': owner.get('base'), 'confirmed': confirmed}, 'commands': commands, 'checked_at': now()}

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

    # ------------------------------------------------------------------ guards
    def _owned(self, row):
        owner = row['ownership']
        if owner['owner'] == 'unknown':
            return [say('EAOS has no record of making this branch: a name alone is not proof, so it is left to you.',
                        'ما عند EAOS سجل أنه أنشأ هذا الفرع، والاسم وحده ليس دليلًا، فهو متروك لك.', 'not_owned')]
        if owner['owner'] == 'shared':
            return [say(f"Someone else added {owner['foreign_commits']} commit(s) to this branch: EAOS does not change it.",
                        f"أحد غير EAOS أضاف {owner['foreign_commits']} commit إلى هذا الفرع، فلا يغيّره EAOS.", 'shared')]
        return []

    def _busy(self, names, exclude=None):
        busy = [r for r in self.active_runs(exclude) if {work_of(r), (r.get('context') or {}).get('analysis_branch')} & set(names)
                or r.get('action', '').startswith('branch_')]
        return [say(f"A run is working now ({busy[0]['id']}): wait for it to finish or stop it.",
                    f"فيه تشغيل يعمل الآن ({busy[0]['id']}): انتظره حتى ينتهي أو أوقفه.", 'active_run')] if busy else []

    def _merge_blocks(self, row, target, inventory, preview=True):
        reasons = list(self._owned(row))
        if not target: reasons.append(say('No destination: choose the branch to merge into.', 'ما فيه وجهة: اختر الفرع الذي يُدمج فيه.', 'no_target'))
        elif target == row['name']: reasons.append(say('A branch cannot be merged into itself.', 'لا يُدمج الفرع في نفسه.', 'same'))
        elif inventory['protected'].get(target):
            reasons.append(say(f"{target} is protected ({inventory['protected'][target]['en']}): nothing is merged into it from here.",
                               f"{target} محمي ({inventory['protected'][target]['ar']}): لا يُدمج فيه شيء من هنا.", 'protected_target'))
        reasons += self._busy([row['name'], target])
        return reasons

    def _delete_blocks(self, row, inventory):
        reasons = list(self._owned(row))
        name = row['name']
        if inventory['protected'].get(name): reasons.append(say('This branch is protected.', 'هذا الفرع محمي.', 'protected'))
        if 'default' in row['roles']: reasons.append(say('This is the default branch.', 'هذا الفرع الافتراضي.', 'default'))
        if 'analysis' in row['roles']: reasons.append(say('This is the analysis branch: choose another one first.', 'هذا فرع التحليل: اختر غيره أولًا.', 'analysis'))
        if row['worktree']:
            reasons.append(say(f"It is checked out in {'your project folder' if row['worktree']['current'] else 'another worktree: ' + row['worktree']['path']}.",
                               f"مفتوح في {'مجلد مشروعك' if row['worktree']['current'] else 'نسخة عمل أخرى: ' + row['worktree']['path']}.", 'checked_out'))
        if any(r['state'] in ACTIVE + ('queued',) for r in row['runs']):
            reasons.append(say('A run that is not over uses this branch.', 'فيه تشغيل لم ينته يستخدم هذا الفرع.', 'run_uses_it'))
        reasons += self._busy([name])
        return reasons

    def _remote_blocks(self, row, inventory):
        reasons = list(self._owned(row))
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

    # ------------------------------------------------------------------ the analysis branch
    def select(self, body):
        """Make `branch` the analysis branch: the Studio's context changes, the person's checkout does not. Refused while
        any run is queued or working, so none is retargeted without the person deciding; `scan: true` queues the scan."""
        from ... import guided
        name = valid_name(self.project, body.get('branch'))
        local, remote = self.tip(f'refs/heads/{name}'), next((r for r in self.remotes() if self.tip(f'refs/remotes/{r}/{name}')), None)
        if not local and not remote: raise KeyError(name)
        waiting = self.active_runs(queued=True)
        if waiting:
            raise Blocked([say(f"{len(waiting)} run(s) are queued or working on the current branch ({', '.join(r['id'] for r in waiting[:3])}): "
                               'let them finish or stop them, then choose again. EAOS never moves them to another branch on its own.',
                               f"{len(waiting)} تشغيل في الانتظار أو يعمل على الفرع الحالي ({', '.join(r['id'] for r in waiting[:3])}): "
                               'اتركها تنتهي أو أوقفها ثم اختر من جديد. EAOS لا ينقلها إلى فرع آخر بنفسه.', 'in_flight')], needs='in_flight')
        expected = body.get('expected_tip')
        if expected and expected != (local or self.tip(f'refs/remotes/{remote}/{name}')):
            raise Blocked([say('The branch moved since you looked at it: refresh.', 'الفرع تغيّر منذ نظرت إليه: حدّث.', 'stale')], needs='refresh')
        handle = self._locked()
        try:
            before = self.head()
            run = self._start('branch_select', {'en': f'Analyse the branch {name}', 'ar': f'حلّل الفرع {name}'}, [name], {'branch': name})
            state = self.state()
            if not state:
                from ... import agent_tools
                state = agent_tools.project_state(str(self.project))
            try: guided.choose(state, name)
            except ValueError as problem:
                return self._finish(run, False, {'en': f'Not changed: {problem}', 'ar': f'ما تغيّر: {problem}'}, {'reason': str(problem)})
            after = self.head()
            if (after['branch'], after['commit']) != (before['branch'], before['commit']):
                return self._finish(run, False, {'en': 'Your checkout changed unexpectedly: nothing more was done.', 'ar': 'تغيّر الفرع المفتوح عندك على غير المتوقع: ما سوّيت شيئًا آخر.'},
                                    {'reason': 'checkout changed'})
            state = self.state()
            needs_scan = not state.get('scanned_commit') or state.get('scanned_commit') != self.tip(f'refs/heads/{name}')
            data = {'branch': name, 'created_local_from': remote if not local else None, 'checkout_unchanged': True, 'needs_scan': needs_scan,
                    'branches': [name]}
            result = self._finish(run, True, {'en': f'The Studio now works on {name}; your checkout stays {before["branch"] or "detached"}.',
                                              'ar': f'الاستوديو يعمل الآن على {name}؛ والفرع المفتوح عندك يبقى {before["branch"] or "منفصلًا"}.'}, data)
        finally:
            handle.close()
        scan = self.actions.create({'action': 'audit', 'inputs': {}}) if body.get('scan') and needs_scan else None
        return {'run': result, 'scan': self.actions.public(scan) if scan else None, 'context': self.context()}

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
        waves = self.waves()
        wave = waves.get(source) or {}
        latest = next((w for w in reversed(self.state().get('waves') or []) if w.get('status') == 'applied'), None)
        managed = bool(wave) and wave.get('status') == 'applied' and latest is not None and latest.get('branch') == source \
            and target == inventory['context']['analysis']['branch']
        if wave and wave.get('status') == 'applied' and not managed:
            reasons.append(say('This EAOS batch is accepted only into the branch it was made for, newest batch first.',
                               'تُعتمد دفعة EAOS فقط في الفرع الذي صُنعت له، والأحدث أولًا.', 'wave_order'))
        merged = git(self.project, 'merge-base', '--is-ancestor', source_tip, target_tip).returncode == 0
        if merged: reasons.append(say(f'Nothing to merge: {target} already has every commit of {source}.', f'لا شيء يُدمج: {target} فيه كل commit في {source}.', 'merged'))
        held = next((w for w in inventory['worktrees'] if w['branch'] == target), None)
        if held and held['dirty'] and (held['dirty']['tracked']):
            reasons.append(say(f'{target} is checked out with unsaved changes: save (commit) or set them aside first.',
                               f'{target} مفتوح وفيه تعديلات غير محفوظة: احفظها (commit) أو ضعها جانبًا أولًا.', 'dirty_target'))
        commits = [dict(zip(('commit', 'author', 'email', 'at', 'subject'), line.split('\x00'))) for line in
                   git(self.project, 'log', f'--max-count={COMMITS_SHOWN}', '--format=%H%x00%an%x00%ae%x00%cI%x00%s', f'{target_tip}..{source_tip}').stdout.splitlines()]
        files = [{'status': line.split('\t')[0], 'path': line.split('\t')[-1]} for line in
                 git(self.project, '-c', 'core.quotePath=false', 'diff', '--name-status', f'{target_tip}...{source_tip}').stdout.splitlines()[:FILES_SHOWN]]
        trial = git(self.project, 'merge-tree', '--write-tree', '--name-only', '--no-messages', target_tip, source_tip)
        lines = trial.stdout.splitlines()
        conflicts = [line for line in lines[1:] if line.strip()] if trial.returncode == 1 else []
        if trial.returncode not in (0, 1): reasons.append(say('git could not try the merge.', 'git ما قدر يجرّب الدمج.', 'merge_tree_failed'))
        if conflicts:
            reasons.append(say(f'{len(conflicts)} file(s) conflict: nothing is merged; both sides stay as they are.',
                               f'{len(conflicts)} ملف فيه تعارض: ما يُدمج شيء، والطرفان يبقيان كما هما.', 'conflict'))
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
            if preview['path'] == 'accept':
                answer = self.manager.call('accept', {'person_agreed': True})
                ok = isinstance(answer, dict) and answer.get('status') == 'accepted'
                after = self.tip(f'refs/heads/{target}')
                data = {'source': source, 'target': target, 'via': 'accept', 'answer': answer, 'target_before': bound['target_head'],
                        'target_after': after, 'branches': [source, target], 'reason': None if ok else str(answer.get('status') or answer.get('error'))}
                if ok: self.record(source, merged_into={'branch': target, 'at': now(), 'commit': after, 'run': run, 'via': 'accept'})
                return {'run': self._finish(run, ok, {'en': f'{source} is in {target}; the report and the progress are up to date.' if ok else f"Not merged: {data['reason']}",
                                                      'ar': f'{source} صار في {target}، والتقرير والتقدم محدّثان.' if ok else f"ما اندمج: {data['reason']}"},
                                            data, outcome='accepted' if ok else None)}
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

    def _merge_transaction(self, source, target, bound, run):
        message = f'Merge {source} into {target} (EAOS Studio, run {run})'
        held = next((w for w in self._worktrees() if w['branch'] == target), None)
        if held:
            from ... import branches as reading
            folder = Path(held['path'])
            changes = reading.dirty(folder)
            if changes is None or changes['tracked']: return {'error': 'the checked-out target has unsaved changes'}
            if _out(folder, 'rev-parse', 'HEAD') != bound['target_head']: return {'error': 'the target moved'}
            done = git(folder, 'merge', '--no-edit', '-m', message, bound['source_head'], env=_eaos_env())
            if done.returncode:
                git(folder, 'merge', '--abort')
                return {'error': 'git refused the merge; nothing changed'}
            return {'commit': _out(folder, 'rev-parse', 'HEAD'), 'via': 'worktree_merge'}
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

    # ------------------------------------------------------------------ deleting and recovering
    def recoveries(self):
        return _read_json(self.store.folder / 'branch-recovery.json', []) or []

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
        if where == 'remote':
            row, inventory = self._row(name, 'remote', body.get('remote'))
            reasons = self._remote_blocks(row, inventory)
            bound = {'branch': name, 'remote': row['remote'], 'tip': row['tip']}
            return {'branch': name, 'where': 'remote', 'remote': row['remote'], 'tip': row['tip'], 'as_of': row['remote_as_of'],
                    'blocked': reasons, 'local_kept': bool(self.tip(f'refs/heads/{name}')),
                    'confirm': None if reasons else self.locks.confirm('branch_delete_remote', bound, self.project), 'checked_at': now()}
        if where != 'local': raise ValueError('where must be local or remote')
        row, inventory = self._row(name)
        reasons = self._delete_blocks(row, inventory)
        holders = [line for line in (_out(self.project, 'for-each-ref', '--format=%(refname:short)', '--contains', row['tip'], 'refs/heads') or '').splitlines()
                   if line and line != name]
        # --exclude takes the name without refs/heads/ for --branches; recovery refs are in none of these namespaces.
        lost = git(self.project, 'rev-list', f'--max-count={COMMITS_SHOWN + 1}', row['tip'], '--not', f'--exclude={name}',
                   '--branches', '--remotes', '--tags').stdout.split()
        commits = [dict(zip(('commit', 'subject', 'author'), (_out(self.project, 'log', '-1', '--format=%H%x00%s%x00%an', c) or '').split('\x00')))
                   for c in lost[:COMMITS_SHOWN]]
        unmerged = bool(lost)
        bound = {'branch': name, 'tip': row['tip'], 'unmerged': unmerged}
        return {'branch': name, 'where': 'local', 'tip': row['tip'], 'merged_into': holders, 'unmerged': unmerged,
                'lost_commits': commits, 'lost_truncated': len(lost) > COMMITS_SHOWN, 'blocked': reasons, 'remote_kept': True,
                'confirm': None if reasons else self.locks.confirm('branch_delete', bound, self.project),
                'confirm_unmerged': None if reasons or not unmerged else self.locks.confirm('branch_delete_unmerged', bound, self.project),
                'checked_at': now()}

    def delete(self, body):
        """Delete one branch, locally or on one remote (two separate operations, each with its own consent): a recovery ref
        first, then the ref removed only if it is still at the commit the preview showed. Never a force deletion."""
        where = body.get('where') or 'local'
        name = valid_name(self.project, body.get('branch'))
        if where == 'remote': return self._delete_remote(name, body)
        if where != 'local': raise ValueError('where must be local or remote')
        bound = {'branch': name, 'tip': body.get('tip'), 'unmerged': bool(body.get('unmerged'))}
        self._spend(body, 'branch_delete', bound)
        if bound['unmerged'] and not self.locks.spend(body.get('confirm_unmerged'), 'branch_delete_unmerged', bound, self.project):
            raise Blocked([say('Its commits are in no other branch: confirm a second time that you delete them (they stay recoverable).',
                               'الـcommits فيه ليست في أي فرع آخر: أكّد مرة ثانية أنك تحذفها (وتبقى قابلة للاسترجاع).', 'unmerged')],
                          needs='confirm_unmerged')
        handle = self._locked()
        try:
            preview = self.preview_delete({'branch': name, 'where': 'local'})
            if preview['tip'] != bound['tip'] or preview['unmerged'] != bound['unmerged']:
                raise Blocked([say('The branch moved since the preview: look again.', 'الفرع تغيّر بعد المعاينة: شوف من جديد.', 'stale')], needs='refresh')
            if preview['blocked']: raise Blocked(preview['blocked'], needs='blocked')
            run = self._start('branch_delete', {'en': f'Delete the branch {name} here', 'ar': f'احذف الفرع {name} هنا'}, [name],
                              {'branch': name, 'tip': bound['tip'], 'unmerged': bound['unmerged']})
            kept = self._keep(name, 'local', None, bound['tip'], run)
            gone = git(self.project, 'update-ref', '-m', f'EAOS Studio: delete {name} (run {run})', '-d', f'refs/heads/{name}', bound['tip'])
            if gone.returncode:
                return {'run': self._finish(run, False, {'en': 'Not deleted: the branch moved.', 'ar': 'ما انحذف: الفرع تغيّر.'},
                                            {'reason': 'the branch moved', 'branch': name, 'recovery': kept['id'], 'branches': [name]})}
            self.record(name, history={'at': now(), 'event': 'deleted', 'where': 'local', 'run': run, 'recovery': kept['id']})
            return {'run': self._finish(run, True, {'en': f'Deleted {name}; it can be restored ({kept["id"]}). The remote copy, if any, is untouched.',
                                                    'ar': f'حُذف {name}، ويمكن استرجاعه ({kept["id"]}). والنسخة البعيدة، إن وُجدت، لم تُمس.'},
                                        {'branch': name, 'where': 'local', 'tip': bound['tip'], 'recovery': kept['id'], 'unmerged': bound['unmerged'],
                                         'branches': [name]}, outcome='deleted')}
        finally:
            handle.close()

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
            if self._is_eaos_itself() and name == 'main':
                raise Blocked([say("EAOS's own main stays protected.", 'main في EAOS نفسه يبقى محميًا.', 'eaos_main')])
        handle = self._locked()
        try:
            path = self.store.folder / 'branch-policy.json'
            saved = _read_json(path, {}) or {}
            protected, unprotected = set(saved.get('protected') or []), set(saved.get('unprotected') or [])
            (protected.add if bound['protected'] else protected.discard)(name)
            (unprotected.discard if bound['protected'] else unprotected.add)(name)
            _write_json(path, {'protected': sorted(protected), 'unprotected': sorted(unprotected), 'at': now()})
            run = self._start('branch_protect', {'en': f"{'Protect' if bound['protected'] else 'Unprotect'} {name}", 'ar': f"{'احمِ' if bound['protected'] else 'ارفع الحماية عن'} {name}"},
                              [name], bound)
            return {'run': self._finish(run, True, {'en': 'Policy saved.', 'ar': 'حُفظت السياسة.'}, {**bound, 'branches': [name]}), 'protected': self.policy()['protected']}
        finally:
            handle.close()

    # ------------------------------------------------------------------ freshness
    def freshness(self):
        """The live answer to "is the check current?" for the branch EAOS works on (eaos/branches.py freshness)."""
        from ... import branches as reading
        from ...build_info import digest
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
            from ... import guided
            stamp = guided.report_stamp(state)
        except Exception:
            pass
        return {**found, 'eaos_updated': bool(state.get('scanned_with')) and state.get('scanned_with') != digest(),
                'report_built': stamp.get('built'), 'checked_at': now(), 'project': self.project.name, 'project_path': str(self.project)}
