"""The gates every change passes, whichever journey made it (eaos/journeys/catalog.py): a fix, a card of a build, a card of a
feature added to a project. One collection of facts on the changed copy (`after`) is held against the project as it
was (`before`: its check's report, whose facts it keeps; None for a project built from its plan, where nothing was
there, so everything found is the change's). A gate counts only what the change added.

  structure (the whole copy):
    layers     an import a rule of the policy forbids (the project's eaos.policy.json, or the blueprint's)
    structure  a file in no layer of that policy
    vendor     a vendor's package used outside the folders the policy keeps it in (a blueprint's adapters)
    cycle      files that import each other in a loop
    broken     a broken reference of high severity
  debt (the files the change touched, `paths`; the code laws, eaos/core/code_laws.py):
    copy       a block or function written twice outside tests and configuration
    dead       code nothing uses (`dead` false for a build card: the later cards use what it made)
    complex    more decisions past the complexity limit, summed over those files (a split is less, a move is neither)
    size       a module grown past the line limit
    security   a weakness that an engine both collections ran reports (eaos/analysis/weaknesses.py)

Each problem is {'gate', 'where', 'what'}; `what` is the sentence the assistant reads, with its place.
"""
import json
import re
from pathlib import Path

from ..core.code_laws import MAX_COMPLEXITY, MAX_LINES

ASIDE = re.compile(r'(\.test\.|\.spec\.|/tests?/|^tests?/|e2e/|\.config\.)')     # a copy here is not the code's


def found(before, after, paths, policy=None, dead=True):
    return structure(before, after, policy) + debt(before, after, paths, dead)


def structure(before, after, policy=None):
    rows = lambda folder: {**(_layers(policy, folder) if policy else {}), **(_vendors(policy, folder) if policy else {}),
                           **_cycles(folder), **_broken(folder)}
    return _added(rows, before, after)


def debt(before, after, paths, dead=True, had=None):
    """What a change adds against the code laws, from the facts `before` and `after` it; `had`: the changed files' sizes
    just before it, when the `before` facts are older (a batch's check on record)."""
    paths = set(paths)
    rows = lambda folder: {**_copies(folder, paths), **(_dead(folder, paths) if dead else {})}
    problems = _added(rows, before, after)
    was, now = (_excess(folder, paths) if folder else 0 for folder in (before, after))
    if now > was:
        problems.append({'gate': 'complex', 'where': ', '.join(sorted(paths))[:200],
                         'what': f'more complex: {now - was} decisions more past the limit of {MAX_COMPLEXITY} per function'})
    had = had if had is not None else _sizes(before, paths) if before else {}
    problems += [{'gate': 'size', 'where': path, 'what': f'{path} grew to {lines} lines, past the limit of {MAX_LINES}: split it'}
                 for path, lines in sorted(_sizes(after, paths).items()) if lines > MAX_LINES and lines > had.get(path, 0)]
    from .weaknesses import new
    return problems + [{'gate': 'security', 'where': path, 'what': f'a security finding: {rule} ({engine}) in {path}: never bring a weakness in'}
                       for engine, rule, path in new(before, after, paths)]


def words(problems):
    """The problems as the sentences a fix's answer gives."""
    return [problem['what'] for problem in problems]


def _added(rows, before, after):
    """The problems of `after` whose key `before` did not have (all of them without a before)."""
    had = rows(before) if before else {}
    return [problem for key, problem in rows(after).items() if key not in had]


def _facts(folder, name):
    file = Path(folder) / 'facts' / f'{name}.json'
    try: return json.loads(file.read_text(encoding='utf-8'))['facts'] if file.is_file() else []
    except (OSError, ValueError, KeyError): return []


# ---------------------------------------------------------------- structure

def _layers(policy, folder):
    from .policy import violations
    sets = {name: {'facts': _facts(folder, name)} for name in ('resolve', 'graph')}
    if not sets['graph']['facts']: return {}
    broken, outside = violations(policy, sets)
    rows = {('layers', r['from_path'], r['to_path'], r['reason']):
            {'gate': 'layers', 'where': f"{r['from_path']}:{r['line'] or 1}",
             'what': f"{r['from_path']}: {r['from_layer']} may not use {r['to_layer']} ({r['to_path']}): {r['reason']}"} for r in broken}
    return {**rows, **{('structure', path): {'gate': 'structure', 'where': path, 'what': f'{path} is in no layer of the policy '
                                             '(eaos.policy.json): put it where the plan says, or add it to one'} for path in outside}}


def _vendors(policy, folder):
    """Each import of a vendor's package outside the folders the policy keeps it in (tests aside)."""
    rows = {}
    for concern, vendor in (policy.get('vendors') or {}).items():
        homes = [vendor['only_in']] if isinstance(vendor['only_in'], str) else vendor['only_in']
        for edge in _facts(folder, 'resolve'):
            module, source = edge['value'].get('module') or '', edge['location']['path']
            named = any(module == package or module.startswith(package + '/') for package in vendor['packages'])
            if named and not any(source.startswith(home) for home in homes) and not ASIDE.search(source):
                rows[('vendor', source, module)] = {
                    'gate': 'vendor', 'where': f"{source}:{edge['location'].get('start_line') or 1}",
                    'what': f"{module} is used in {source}, outside {' and '.join(homes)}: only the {concern} adapter may use it, "
                            'so it can be changed in one place'}
    return rows


def _cycles(folder):
    return {('cycle', *sorted(f['value']['members'])): {'gate': 'cycle', 'where': f['value']['members'][0],
                                                        'what': 'these files import each other in a loop: ' + ', '.join(f['value']['members'][:6])}
            for f in _facts(folder, 'graph') if f['kind'] == 'graph_cycle'}


def _broken(folder):
    return {('broken', f['value']['rule'], f['location'].get('path'), f['location'].get('symbol')):
            {'gate': 'broken', 'where': f['location'].get('path'), 'what': f['value']['message']}
            for f in _facts(folder, 'broken') if f['value'].get('severity') == 'high'}


# ---------------------------------------------------------------- debt

def _copies(folder, paths):
    """The blocks and functions written twice or more outside tests and configuration, with a place in `paths`."""
    from .fact_claims import SHARED_SIZE_FOR_UI, worth_a_claim
    clusters = [(f['input_sha'], f['value']['occurrences']) for f in _facts(folder, 'metrics') if f['kind'] == 'clone_cluster']
    # a shape too small to hold a rule (`() => x.y()` in four files, a real build) is how code reads, not a copy
    clusters += [(f['value']['shape_sha'], f['value']['occurrences']) for f in _facts(folder, 'fingerprint')
                 if f['kind'] == 'duplicate_cluster' and f['value'].get('shared_size', 0) >= SHARED_SIZE_FOR_UI
                 and worth_a_claim(f['value']['occurrences'], f['value'].get('shared_size', 0))]
    rows = {}
    for key, places in clusters:
        places = [o for o in places if not ASIDE.search(o['path'])]
        if len(places) >= 2 and paths & {o['path'] for o in places}:
            rows[('copy', key)] = {'gate': 'copy', 'where': places[0]['path'], 'what': 'the same code is written in '
                                   + ', '.join(f"{o['path']}:{o.get('start_line') or 1}" for o in places[:4]) + ': give it one home and call it'}
    return rows


def _dead(folder, paths):
    return {('dead', f['value']['rule'], f['location'].get('path'), f['location'].get('symbol')):
            {'gate': 'dead', 'where': f['location'].get('path'),
             'what': f"dead code: {f['location'].get('symbol') or f['location'].get('path')} ({f['value']['rule']})"}
            for f in _facts(folder, 'deadcode') if f['location'].get('path') in paths}


def _sizes(folder, paths):
    return {f['location']['path']: f['value']['lines'] for f in _facts(folder, 'metrics')
            if f['kind'] == 'metric' and f['value']['scope'] == 'file' and f['location']['path'] in paths}


def _excess(folder, paths):
    """The decisions past the complexity limit of the functions and methods in `paths`, summed over all of them: code
    moved between the files keeps its sum, and a class (the sum of its methods) is not one more function."""
    return sum(max(0, f['value']['branches'] - MAX_COMPLEXITY) for f in _facts(folder, 'metrics')
               if f['kind'] == 'metric' and f['value']['scope'] in ('function', 'method') and f['location']['path'] in paths)
