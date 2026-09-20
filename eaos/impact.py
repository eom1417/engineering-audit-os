"""What a change to one file or symbol actually touches.

Every number here comes from facts already collected: the resolved import graph, the traced flows,
the executed coverage and the repository history. Nothing is estimated.
"""
from collections import deque
from pathlib import Path
from .facts.store import read_set

SETS = ['syntax', 'resolve', 'entrypoints', 'config', 'metrics', 'domain', 'history', 'graph', 'flows', 'verification']
DEFAULT_DEPTH = 3
LIMITS = [
    'Only statically resolved dependencies are followed; dynamic dispatch and injection are invisible.',
    'A dependent is a file that could be affected, not proof that it must change.',
    'Coverage reflects the command that was executed, not every behaviour of the dependents.',
]


def load(out):
    out = Path(out)
    sets = {}
    for name in SETS:
        if (out / 'facts' / (name + '.json')).is_file(): sets[name] = read_set(out, name)
    if 'graph' not in sets: raise ValueError('No graph facts in ' + str(out) + '; run eaos facts or eaos dossier first')
    return sets


def dependents(sets, paths, depth=DEFAULT_DEPTH):
    """Files that reach the given paths through resolved imports, with their distance."""
    nodes = {fact['location']['path']: fact['value'] for fact in sets['graph']['facts'] if fact['kind'] == 'graph_node'}
    reverse = {}
    for path, value in nodes.items():
        for target in value['depends_on']: reverse.setdefault(target, set()).add(path)
    distance, queue = {}, deque((path, 0) for path in paths if path in nodes)
    seen = set(paths)
    while queue:
        current, level = queue.popleft()
        if level >= depth: continue
        for consumer in sorted(reverse.get(current, ())):
            if consumer in seen: continue
            seen.add(consumer)
            distance[consumer] = level + 1
            queue.append((consumer, level + 1))
    return distance, nodes


def flows_through(sets, paths):
    rows = []
    for fact in sets.get('flows', {}).get('facts', []):
        value = fact['value']
        if set(value['touched_files']) & set(paths):
            rows.append({'flow_id': value['flow_id'], 'surface': value['entry']['surface'],
                         'route': value['entry']['route'], 'entry': f"{value['entry']['path']}:{value['entry']['line']}"})
    return rows


def entry_points_in(sets, paths):
    return [{'surface': fact['value']['surface'], 'route': fact['value']['route'],
             'location': f"{fact['location']['path']}:{fact['location'].get('start_line') or 1}"}
            for fact in sets.get('entrypoints', {}).get('facts', []) if fact['location']['path'] in paths]


def coverage_of(sets, paths):
    rows = {}
    for fact in sets.get('verification', {}).get('facts', []):
        if fact['location']['path'] in paths: rows[fact['location']['path']] = fact['value']
    return rows


def covering_tests(sets, paths):
    """Test files that import the given paths, directly or through one hop."""
    from .discovery import classify
    distance, _ = dependents(sets, paths, depth=2)
    return sorted(path for path in distance if classify(path) == 'test')


def change_partners(sets, paths):
    rows = []
    for fact in sets.get('history', {}).get('facts', []):
        if fact['kind'] != 'history_cochange': continue
        left, right = fact['location']['path'], fact['location']['paired_path']
        if left in paths or right in paths:
            other = right if left in paths else left
            rows.append({'path': other, 'support': fact['value']['support'], 'confidence': fact['value']['confidence']})
    return sorted(rows, key=lambda row: (-row['support'], row['path']))[:10]


def symbols_in(sets, paths, symbol=None):
    rows = []
    for fact in sets.get('syntax', {}).get('facts', []):
        if fact['kind'] != 'symbol' or fact['location']['path'] not in paths: continue
        name = fact['location'].get('symbol') or fact['value']['name']
        if symbol and symbol not in {name, fact['value']['name']}: continue
        rows.append({'symbol': name, 'kind': fact['value']['kind'],
                     'location': f"{fact['location']['path']}:{fact['location']['start_line']}-{fact['location']['end_line']}"})
    return rows


def resolve_target(sets, target):
    """A target is a path in the snapshot, or a symbol name; both resolve to a set of files."""
    nodes = {fact['location']['path'] for fact in sets['graph']['facts'] if fact['kind'] == 'graph_node'}
    if target in nodes: return [target], None
    matches = sorted({fact['location']['path'] for fact in sets.get('syntax', {}).get('facts', [])
                      if fact['kind'] == 'symbol'
                      and target in {fact['location'].get('symbol'), fact['value']['name']}})
    if matches: return matches, target
    suffix = sorted(path for path in nodes if path.endswith('/' + target.lstrip('/')))
    if suffix: return suffix, None
    raise ValueError('Unknown path or symbol: ' + target)


def assess(out, target, depth=DEFAULT_DEPTH, sets=None):
    """target is a path, a symbol, or a list of them; the radius covers all of them together."""
    sets = sets or load(out)
    if isinstance(target, (list, tuple, set)):
        paths, symbol = [], None
        for item in sorted(target):
            resolved, found = resolve_target(sets, item)
            paths += resolved
            symbol = symbol or found
        paths = sorted(set(paths))
        target = ', '.join(sorted(target))
    else:
        paths, symbol = resolve_target(sets, target)
    distance, nodes = dependents(sets, paths, depth)
    coverage = coverage_of(sets, paths)
    direct = sorted(path for path, level in distance.items() if level == 1)
    tests = covering_tests(sets, paths)
    return {
        'target': target, 'resolved_paths': paths, 'symbol': symbol, 'depth': depth,
        'symbols': symbols_in(sets, paths, symbol)[:40],
        'direct_dependents': direct,
        'transitive_dependents': sorted(path for path in distance if path not in direct),
        'depends_on': sorted({other for path in paths for other in nodes.get(path, {}).get('depends_on', [])}),
        'flows': flows_through(sets, paths),
        'entry_points': entry_points_in(sets, paths),
        'covering_tests': tests,
        'coverage': coverage,
        'change_partners': change_partners(sets, paths),
        'attention': {path: nodes[path]['attention_rank'] for path in paths if path in nodes},
        'blast_radius': len(distance),
        'limits': LIMITS,
        'interpretation': 'Potential reach of a change, computed from resolved facts. A dependent may still be unaffected.',
    }
