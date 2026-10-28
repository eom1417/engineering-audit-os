"""The diff-scoped check (M16.7): on a change, before it lands, the guards of the person's rules and EAOS's fast gates
over the files it touches and the files that depend on them (the import graph), each rule's smallest check that
suffices: a pattern reads only those files, a test runs only when the change reaches its files, a detector reads only
what the gates found the change added. A test runs on the working tree, the commit's files and any not yet staged
alike; it is compared with the same test at the base commit, so only a failure the change brought refuses. Seconds and no token as the target; a full check stays for the release.

    changed(project, base, staged)   the files a change touches: the staged ones (a commit), else those that differ
                                     from `base` (HEAD by default) in the working tree, new files included
    reached(project, paths)          those files and every file that imports them, further and further (bounded)
    check(...)                       {changed, reached, rules: what each rule found, laws: what the gates found, refused}
"""
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from . import held

REACH = 300                 # files followed through the import graph at most: past it, the change is wide and a full check reads it
GATE_ENGINES = ('jscpd', 'ast-grep', 'bandit', 'gitleaks')      # the gates' engines that answer in seconds (eaos/journeys/fix/execute.py)


def _git(project, *args):
    return subprocess.run(['git', '-C', str(project), *args], capture_output=True, text=True)


def changed(project, base=None, staged=False):
    if staged: names = _git(project, 'diff', '--cached', '--name-only', '--diff-filter=ACMR').stdout.split('\n')
    else:
        names = _git(project, 'diff', '--name-only', '--diff-filter=ACMR', base or 'HEAD').stdout.split('\n')
        names += _git(project, 'ls-files', '--others', '--exclude-standard').stdout.split('\n')
    return sorted({n for n in names if n.strip()})


def _graph(project):
    """{file: the files it imports} of the project now (its syntax and imports read again: about three seconds a
    thousand files)."""
    from ...facts.run import collect
    from ...core.system.files import read_json
    with tempfile.TemporaryDirectory(prefix='eaos-changed-graph-') as out:
        collect(Path(project), out, ['syntax', 'resolve'])
        edges = (read_json(Path(out) / 'facts/resolve.json') or {}).get('facts') or []
    graph = {}
    for edge in edges:
        if edge.get('resolution') == 'RESOLVED' and edge['value'].get('to_path'):
            graph.setdefault(edge['location']['path'], set()).add(edge['value']['to_path'])
    return graph


def reached(project, paths, graph=None):
    """`paths` and the files that import any of them, directly or not, up to REACH files: (files, whether it stopped)."""
    graph = _graph(project) if graph is None else graph
    importers = {}
    for source, targets in graph.items():
        for target in targets: importers.setdefault(target, set()).add(source)
    found, frontier = list(dict.fromkeys(paths)), list(paths)
    while frontier and len(found) < REACH:
        for source in sorted(importers.get(frontier.pop(0), ())):
            if source not in found:
                found.append(source)
                frontier.append(source)
    return found[:REACH], len(found) >= REACH


def snapshot(project, paths, folder, revision=None):
    """`paths` written into `folder` as they are in the index (revision ':'), at `revision`, or in the working tree
    (None); a file not there (new, or deleted) is left out."""
    for path in paths:
        target = Path(folder) / path
        if revision is None:
            source = Path(project) / path
            if not source.is_file(): continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            continue
        shown = subprocess.run(['git', '-C', str(project), 'show', f'{revision}{path}' if revision == ':' else f'{revision}:{path}'],
                               capture_output=True)
        if shown.returncode: continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(shown.stdout)


def laws(before, after, paths):
    """What the change adds against the code laws over `paths` (eaos/analysis/repair/gates.py debt), from the facts of
    the two snapshots: [{gate, where, what}]."""
    from ...facts.run import collect
    from ..repair.gates import debt
    with tempfile.TemporaryDirectory(prefix='eaos-changed-facts-') as facts:
        folders = {}
        for name, root in (('before', before), ('after', after)):
            folders[name] = Path(facts) / name
            collect(Path(root), folders[name], engines=list(GATE_ENGINES))
        return debt(folders['before'], folders['after'], [p for p in paths if (Path(after) / p).is_file()])


def found_of(problems):
    """The gates' problems as a detector guard reads them."""
    return [{'detector': p['gate'], 'places': [part.strip() for part in p['where'].split(',') if part.strip()], 'said': p['what']}
            for p in problems]


def _sides(project, files, since, scratch):
    """(after, before): `files` as the change leaves them (the index for a commit) and as they were (its base)."""
    base, staged = since
    after, before = Path(scratch) / 'after', Path(scratch) / 'before'
    snapshot(project, files, after, ':' if staged else None)
    snapshot(project, files, before, 'HEAD' if staged or not base else base)
    return after, before


def _held(project, rules, change, since, gates):
    """(each rule's result, the gates' problems) on the change: `change` {changed, reached}, `since` (base, staged)."""
    paths, files = change['changed'], change['reached']
    with tempfile.TemporaryDirectory(prefix='eaos-changed-') as scratch:
        after, before = _sides(project, files, since, scratch)
        problems = laws(before, after, paths) if gates else []
        tested = [r for r in rules if (r.get('guard') or {}).get('kind') == 'test']
        results = held.on_change([r for r in rules if r not in tested], after, files, before, found_of(problems))
        with held.at_commit(project, since[0] or 'HEAD') as earlier:
            results += held.on_change(tested, project, files, earlier)
    return results, problems


def check(project, rules, base=None, staged=False, gates=True):  # limits: parameters -- the change (its project, base or index), the rules to hold and whether the gates run
    """The change checked: each rule of `rules` on what it brought, and the code laws' gates when `gates`. `refused`:
    a rule broken (the caller decides which rules may refuse: the hook only the pinned ones)."""
    started = time.monotonic()
    found = {'changed': changed(project, base, staged), 'reached': [], 'wide': False, 'results': [], 'laws': []}
    if found['changed']:
        found['reached'], found['wide'] = reached(project, found['changed'])
        found['results'], found['laws'] = _held(project, rules, found, (base, staged), gates)
    broken = held.broken(found['results'])
    return {**found, 'rules': broken, 'refused': bool(broken), 'seconds': round(time.monotonic() - started, 2)}
