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
KEYS = ('scanned', 'scanned_commit', 'scanned_with', 'setup', 'safety', 'waves', 'open_wave', 'tried', 'applied')


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
