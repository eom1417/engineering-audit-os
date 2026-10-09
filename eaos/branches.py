"""Which branch EAOS works on (docs/MCP.md): a project often has a branch in production (main) and one where the work
goes on, far ahead of it. The check, the run, the fixes, the progress and the merges all follow one branch, the one
the person chose; the report names it, and says which other branches have a report of their own.

The branch is asked for, as a choice with a recommendation, only when it is a real choice: more than one branch of
the person's own (bots' branches such as dependabot/ and EAOS's own eaos/ are not), whose code differs. Otherwise the
branch checked out is the one, without a question.

Each branch keeps its own check, run, safety net, batches and ledger. The first branch worked on keeps the outputs
folder's top (REPORT.html, technical/, fixes/); every other one has branches/<name>/ with the same parts. This module
reads git and the state only; it writes neither.
"""
import re
import subprocess
from pathlib import Path

NOT_THE_PERSONS = ('eaos/', 'dependabot/', 'renovate/', 'snyk-', 'greenkeeper/', 'gh-pages', 'HEAD')
# Branches kept only for the record: never a choice of where the work goes on.
ARCHIVED = ('archive/', 'archived/')
# What each branch keeps of its own in state.json; the others are the project's (consent, language, questions).
KEYS = ('scanned', 'scanned_commit', 'scanned_with', 'scanned_branch', 'scanned_detached', 'scanned_dirty', 'setup', 'safety',
        'waves', 'open_wave', 'tried', 'applied')
# EAOS's own commits (eaos/waves.commit, guided.merge): code the person did not write, so a scan still holds after them.
EAOS_EMAIL = 'eaos@localhost'
FILES_SHOWN = 50


def _git(project, *args):
    return subprocess.run(['git', '-C', str(project), *args], capture_output=True, text=True)


def slug(name):
    return re.sub(r'[^A-Za-z0-9._-]+', '-', name or '').strip('-.') or 'branch'


def is_home(state):
    return not state.get('branch') or state.get('branch') == state.get('home_branch')


def home(state):
    """The branch's part of the outputs folder: its top for the first branch, branches/<name>/ for the others."""
    top = Path(state['outputs'])
    return top if is_home(state) else top / 'branches' / slug(state['branch'])


def suffix(state):
    """'' for the first branch, '-<name>' for the others: their ledger and runtime beside state.json."""
    return '' if is_home(state) else '-' + slug(state['branch'])


def ref(state):
    return f"refs/heads/{state['branch']}" if state.get('branch') else 'HEAD'


def checked_out(project):
    done = _git(project, 'symbolic-ref', '--quiet', '--short', 'HEAD')
    return done.stdout.strip() if done.returncode == 0 else None


def default_branch(project):
    """The branch the project treats as its main one: origin's HEAD, else main, else master, else the one checked out."""
    done = _git(project, 'symbolic-ref', '--quiet', '--short', 'refs/remotes/origin/HEAD')
    if done.returncode == 0: return done.stdout.strip().split('/', 1)[-1]
    local = set(_git(project, 'for-each-ref', '--format=%(refname:short)', 'refs/heads').stdout.split())
    return next((name for name in ('main', 'master', 'trunk', 'develop') if name in local), checked_out(project))


def _persons(name):
    return not any(name == bot.rstrip('/') or name.startswith(bot) for bot in NOT_THE_PERSONS)


def inventory(project):
    """The person's branches, local and on origin only: name, tip, date, whether it is checked out, and how far it is
    ahead of and behind the main branch. Newest first."""
    main = default_branch(project)
    current = checked_out(project)
    rows = {}
    for kind, pattern in (('local', 'refs/heads'), ('origin', 'refs/remotes/origin')):
        listed = _git(project, 'for-each-ref', '--format=%(refname:short)%00%(objectname)%00%(committerdate:iso-strict)%00%(subject)', pattern)
        for line in listed.stdout.splitlines():
            name, tip, when, subject = (line.split('\x00') + ['', '', ''])[:4]
            if kind == 'origin': name = name.split('/', 1)[-1] if '/' in name else ''
            if not name or not _persons(name) or name in rows: continue
            rows[name] = {'name': name, 'tip': tip, 'last_commit': when, 'last_subject': subject[:120], 'where': kind,
                          'checked_out': name == current, 'main': name == main}
    main_tip = rows.get(main, {}).get('tip')
    for row in rows.values():
        row['commits'] = int(_git(project, 'rev-list', '--count', row['tip']).stdout.strip() or 0)
        if main_tip and row['tip'] != main_tip:
            counts = _git(project, 'rev-list', '--left-right', '--count', f"{main_tip}...{row['tip']}").stdout.split()
            row['behind_main'], row['ahead_of_main'] = (int(counts[0]), int(counts[1])) if len(counts) == 2 else (None, None)
        else:
            row['behind_main'], row['ahead_of_main'] = 0, 0
    return sorted(rows.values(), key=lambda r: r['last_commit'], reverse=True)


def recommend(rows):
    """The branch where the work goes on: the one that holds the most work (commits), then the newest; whichever the
    main branch is (a project may have made its development branch the default)."""
    return max(rows, key=lambda r: (r.get('commits') or 0, r['last_commit']))['name'] if rows else None


def _a_choice(row):
    """A branch worth asking about: the main one, the one checked out, or one with code of its own that is not kept only
    for the record (archive/); a branch merged into main (nothing ahead of it) is main's code."""
    if row['main'] or row['checked_out']: return True
    return not row['name'].startswith(ARCHIVED) and row.get('ahead_of_main') != 0


def choice(project):
    """None when there is nothing to choose (one branch, or every branch has the same code, once merged and archived
    branches are left out); else the question: the branches with what each is, and the recommendation."""
    rows = [row for row in inventory(project) if _a_choice(row)]
    if len({r['tip'] for r in rows}) <= 1: return None
    return {'branches': rows, 'recommended': recommend(rows), 'main': next((r['name'] for r in rows if r['main']), None)}


def dirty(folder):
    """{'tracked': n, 'untracked': n} of a checkout's unsaved changes, or None when git cannot say."""
    done = _git(folder, '-c', 'core.quotePath=false', 'status', '--porcelain=v1', '--untracked-files=normal')
    if done.returncode: return None
    lines = [line for line in done.stdout.splitlines() if line.strip()]
    untracked = sum(1 for line in lines if line.startswith('??'))
    return {'tracked': len(lines) - untracked, 'untracked': untracked}


def scan_provenance(state, folder):
    """What a scan read, recorded beside scanned_commit: the branch (None on a detached HEAD, which is said as such),
    and whether the folder the scan read had unsaved changes. `folder` is the checkout the scan read (guided.source)."""
    if _git(state['project'], 'rev-parse', '--git-dir').returncode:
        return {'scanned_branch': None, 'scanned_detached': None, 'scanned_dirty': None}
    branch = state.get('branch') or checked_out(state['project'])
    detached = not state.get('branch') and branch is None
    changes = dirty(folder)
    return {'scanned_branch': branch, 'scanned_detached': detached,
            'scanned_dirty': None if changes is None else bool(changes['tracked'] or changes['untracked'])}


def _commits_by_others(project, since, until):
    authors = _git(project, 'log', '--no-merges', '--format=%ae', f'{since}..{until}')
    return None if authors.returncode else [a for a in authors.stdout.split() if a != EAOS_EMAIL]


def freshness(state, tip=None):
    """Whether the scan of the branch EAOS works on still holds, from git now: {state, reason, ...}.

    state: fresh (the branch is at the scanned commit, or only EAOS's own accepted fixes came after it); behind (N
    commits and M files came after it, the files listed); rewritten (the scanned commit is no longer in the branch's
    history: a reset, a rebase or a force-push); dirty (at the scanned commit, with unsaved changes in the checkout);
    other_branch (the report is of another branch than the one EAOS works on now); unknown, with the reason
    (not_scanned, legacy_report, not_git, branch_missing). `tip` is the branch's commit now (guided.tip)."""
    project = state.get('project')
    scanned, recorded = state.get('scanned_commit'), 'scanned_branch' in state or 'scanned_detached' in state
    out = {'state': 'unknown', 'reason': None, 'scanned_commit': scanned, 'scanned_branch': state.get('scanned_branch'),
           'scanned_detached': state.get('scanned_detached'), 'scanned_dirty': state.get('scanned_dirty'),
           'scanned_at': state.get('scanned'), 'recorded': recorded, 'branch': state.get('branch') or checked_out(project) if project else None,
           'tip': tip, 'behind': None, 'dirty': None}
    if not state.get('scanned'): return {**out, 'reason': 'not_scanned'}
    if not scanned: return {**out, 'reason': 'legacy_report'}
    if not project or _git(project, 'rev-parse', '--git-dir').returncode: return {**out, 'reason': 'not_git'}
    detached = bool(state.get('scanned_detached'))
    if tip is None:
        done = _git(project, 'rev-parse', '--verify', '--quiet', ('HEAD' if detached or not state.get('branch') else ref(state)) + '^{commit}')
        tip = done.stdout.strip() if done.returncode == 0 else ''
        out['tip'] = tip
    if not tip: return {**out, 'reason': 'branch_missing'}
    if recorded and not detached and state.get('scanned_branch') and out['branch'] and state['scanned_branch'] != out['branch']:
        return {**out, 'state': 'other_branch'}
    if _git(project, 'cat-file', '-e', scanned + '^{commit}').returncode:
        return {**out, 'state': 'rewritten', 'reason': 'scanned_commit_gone'}
    if tip != scanned:
        if _git(project, 'merge-base', '--is-ancestor', scanned, tip).returncode:
            base = _git(project, 'merge-base', scanned, tip).stdout.strip()
            count = _git(project, 'rev-list', '--count', f'{base}..{tip}').stdout.strip() if base else ''
            return {**out, 'state': 'rewritten', 'reason': 'not_in_history', 'since_common': int(count) if count.isdigit() else None}
        others = _commits_by_others(project, scanned, tip)
        count = _git(project, 'rev-list', '--count', f'{scanned}..{tip}').stdout.strip()
        files = _git(project, '-c', 'core.quotePath=false', 'diff', '--name-only', scanned, tip).stdout.splitlines()
        behind = {'commits': int(count) if count.isdigit() else None, 'files': len(files), 'file_list': files[:FILES_SHOWN],
                  'truncated': len(files) > FILES_SHOWN, 'eaos_only': others == []}
        if others != []: return {**out, 'state': 'behind', 'behind': behind}
        out['behind'] = behind
    here = checked_out(project)
    if (detached and here is None) or (out['branch'] and here == out['branch']):
        changes = dirty(project)
        out['dirty'] = changes
        if changes and (changes['tracked'] or changes['untracked']): return {**out, 'state': 'dirty'}
    return {**out, 'state': 'fresh'}
