"""The boundaries between layers, enforced by default (M6.2): each layer of the reference type may use only the layers its
`allowed_dependencies` name. Every resolved import between two placed files is checked (a type-only import is not one:
the compiler erases it); a breach is a finding at the import's line naming the boundary it breaks, and a breach where
either file's placement is a low-confidence guess is a question. When the project declares its own eaos.policy.json,
its rules are the policy stage's (eaos/analysis/policy.py) and are not checked twice here.

The same rules are written for dependency-cruiser (`rules(...)`), which the engines stage runs on JavaScript and
TypeScript: the layers barred from each other, and browser code reaching server code through any chain of files
(`reachable`), which EAOS's own graph checks one import at a time.
"""
import re
from pathlib import PurePosixPath

from .placement import LOW, allowed

DEPCRUISE_FILE = 'layers-depcruise.json'
SCRIPT = ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs')


def _import_line(project, source, target):
    stem = PurePosixPath(target).stem
    return next((number for number, line in enumerate(project.lines(source), start=1)
                 if stem in line and ('import' in line or 'require' in line or 'from' in line)), None)


def _checked(layer_map):
    """({layer: layers it may use}, {path: placed row}) of a map whose files the reference type places, else None."""
    reference = layer_map['reference']
    if not reference or layer_map.get('declared_policy'): return None
    may = allowed(reference)
    return may, {row['path']: row for row in layer_map['rows'] if row['layer'] in may}


def _question(source, target, one, other):
    return {'boundary': 'layers', 'path': source, 'line': None,
            'question': f"{source} ({one['layer']}) uses {target} ({other['layer']}); is {source} really part of "
                        f"{one['layer']} ({one['reason']})?",
            'question_ar': f"{source} ({one['layer']}) يستخدم {target} ({other['layer']})؛ هل {source} فعلًا من طبقة "
                           f"{one['layer']} ({one['reason']})؟"}


def _breach(project, layer_map, one, other):
    source, target = one['path'], other['path']
    return {'rule': 'layer-breach', 'path': source, 'line': _import_line(project, source, target), 'evidence': f'{source} → {target}',
            'params': {'path': source, 'to': target, 'from_layer': one['layer'], 'to_layer': other['layer'], 'type': layer_map['type']}}


def _crossings(project, may, placed):
    """(importing row, imported row) of every import into a layer the importer's layer may not use."""
    for source, targets in sorted(project.edges.items()):
        one = placed.get(source)
        for target in sorted(targets):
            other = placed.get(target)
            if one and other and other['layer'] not in may[one['layer']]: yield one, other


def check(project, layer_map):
    """(findings, questions) for every import that crosses into a layer its own layer may not use."""
    checked = _checked(layer_map)
    if checked is None: return [], []
    findings, questions = [], []
    for one, other in _crossings(project, *checked):
        if LOW in (one['confidence'], other['confidence']): questions.append(_question(one['path'], other['path'], one, other))
        else: findings.append(_breach(project, layer_map, one, other))
    return findings, questions


def _regex(paths):
    return '^(' + '|'.join(re.escape(path) for path in sorted(paths)) + ')$'


def _files_by_layer(rows, may):
    files = {}
    for row in rows:
        if row['layer'] in may and row['confidence'] != LOW and row['path'].endswith(SCRIPT):
            files.setdefault(row['layer'], []).append(row['path'])
    return files


def rules(layer_map):
    """dependency-cruiser's `forbidden` rules for the layer map: one per layer whose files may not reach another layer's,
    type-only imports allowed, and browser code reaching server code. [] when no reference type placed the files."""
    checked = _checked(layer_map)
    if checked is None: return []
    may = checked[0]
    files = _files_by_layer(layer_map['rows'], may)
    found = []
    for layer, paths in sorted(files.items()):
        barred = sorted({path for other, others in files.items() if other not in may[layer] for path in others})
        if barred:
            found.append({'name': f'eaos-layer-{layer}', 'severity': 'error', 'comment': f'{layer} may use only {", ".join(sorted(may[layer]))}',
                          'from': {'path': _regex(paths)}, 'to': {'path': _regex(barred), 'dependencyTypesNot': ['type-only']}})
    return found + _browser_reach(layer_map['rows'])


def _server_own(row):
    """A file whose own code is the server's (a 'use server' file excepted: the browser calls a server action by design)."""
    return row['side'] == 'server' and bool({'endpoint', 'data', 'node'} & set(row['marks'])) and 'server' not in row['marks']


def _browser_reach(rows):
    """A rule that browser code reaches no server code through any chain of files."""
    browser = [r['path'] for r in rows if r['side'] == 'browser' and r['path'].endswith(SCRIPT)]
    server = [r['path'] for r in rows if _server_own(r) and r['path'].endswith(SCRIPT)]
    if not (browser and server): return []
    return [{'name': 'eaos-browser-reaches-server', 'severity': 'error', 'comment': 'browser code reaches server code',
             'from': {'path': _regex(browser)}, 'to': {'path': _regex(server), 'reachable': True}}]
