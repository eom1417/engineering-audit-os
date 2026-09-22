"""Traced execution paths from each entry point, built only from resolved symbols and calls.

Every step carries file:line. A call we cannot resolve is recorded as an explicit gap in the trace,
never skipped, so a short flow is visibly short rather than quietly incomplete.
"""
import builtins
from collections import defaultdict
from . import digest, make

BUILTINS = set(dir(builtins)) | {'console', 'print', 'require', 'super', 'len', 'range'}

NAME = 'flows'
VERSION = '1'
MAX_DEPTH = 6
MAX_STEPS = 40
LIMITATIONS = [
    'A trace follows statically resolvable calls; dispatch through variables, callbacks or DI is not followed.',
    'Order inside a function is source order, not proof of runtime order or of the branch actually taken.',
    'An unresolved step means the tracer stopped there, not that execution stops there.',
    'Nothing here proves the flow runs in production, or that its error paths behave as written.',
]


def index_symbols(symbol_facts):
    by_file, by_name = defaultdict(list), defaultdict(list)
    for fact in symbol_facts:
        location, value = fact['location'], fact['value']
        entry = {'path': location['path'], 'symbol': location.get('symbol') or value['name'], 'name': value['name'],
                 'start': location['start_line'], 'end': location['end_line'], 'kind': value['kind']}
        by_file[entry['path']].append(entry)
        by_name[entry['name']].append(entry)
    for rows in by_file.values(): rows.sort(key=lambda row: row['start'])
    return by_file, by_name


def index_calls(call_facts):
    calls = defaultdict(list)
    for fact in call_facts:
        location = fact['location']
        calls[(location['path'], location.get('symbol'))].append(
            {'callee': fact['value']['callee'], 'line': location.get('start_line'),
             'attribute': fact['value'].get('attribute', False)})
    for rows in calls.values(): rows.sort(key=lambda row: (row['line'] or 0, row['callee']))
    return calls


def imported_files(edge_facts, symbol_facts=None):
    imports = defaultdict(set)
    for fact in edge_facts:
        if fact['resolution'] == 'RESOLVED' and fact['value'].get('to_path'):
            imports[fact['location']['path']].add(fact['value']['to_path'])
    # Go's package-internal imports are implicit: any file in the same directory can call any
    # symbol defined in any other file in that directory. We treat the directory as the unit
    # of visibility, so a handler in foo/bar.go can reach a symbol in foo/baz.go.
    if symbol_facts:
        directories = defaultdict(set)
        for fact in symbol_facts:
            if fact['kind'] == 'symbol':
                rel = fact['location']['path']
                directories['/'.join(rel.split('/')[:-1])].add(rel)
        for path in list(imports.keys()):
            directory = '/'.join(path.split('/')[:-1])
            for sibling in directories.get(directory, ()):
                if sibling != path:
                    imports[path].add(sibling)
    return imports


def resolve_callee(name, path, by_file, by_name, imports, external_names, attribute):
    """Distinguish a real gap in the trace from a call that simply leaves the codebase."""
    local = [row for row in by_file.get(path, []) if row['name'] == name]
    if local: return local[0], 'local'
    candidates = [row for row in by_name.get(name, []) if row['path'] in imports.get(path, set())]
    if len(candidates) == 1: return candidates[0], 'imported'
    if len(candidates) > 1: return None, 'ambiguous'
    if name in external_names.get(path, set()): return None, 'external'
    if name in BUILTINS: return None, 'builtin'
    if attribute: return None, 'method_or_external'
    return None, 'unresolved'


GAP_RESOLUTIONS = {'unresolved', 'ambiguous'}


def _resolve_handler(handler, path, by_file, by_name, imports):
    """Locate the symbol a handler points at. Accepts bare names, receiver-qualified calls
    like `s.handleIndex`, and cross-file imports."""
    if not handler: return None
    for row in by_file.get(path, []):
        if row['symbol'] == handler or row['name'] == handler: return row
    if '.' in handler:
        suffix = handler.rsplit('.', 1)[-1]
        for row in by_file.get(path, []):
            if row['symbol'] == suffix or row['name'] == suffix: return row
    candidates = [row for row in by_name.get(handler, []) if row['path'] in imports.get(path, set())]
    if len(candidates) == 1: return candidates[0]
    if '.' in handler:
        suffix = handler.rsplit('.', 1)[-1]
        candidates = [row for row in by_name.get(suffix, []) if row['path'] in imports.get(path, set())]
        if len(candidates) == 1: return candidates[0]
    return None

def trace(entry, by_file, by_name, calls, imports, env_by_file, external_names):
    """Follow one entry point through resolvable calls, recording every stop with its reason."""
    handler = entry['value'].get('handler')
    path = entry['location']['path']
    start = _resolve_handler(handler, path, by_file, by_name, imports)
    steps, seen, unresolved = [], set(), 0
    queue = [(start, 0)] if start else []
    while queue and len(steps) < MAX_STEPS:
        current, depth = queue.pop(0)
        key = (current['path'], current['symbol'])
        if key in seen or depth > MAX_DEPTH: continue
        seen.add(key)
        for call in calls.get(key, []):
            target, how = resolve_callee(call['callee'], current['path'], by_file, by_name, imports,
                                         external_names, call.get('attribute', False))
            step = {'from': current['symbol'], 'from_path': current['path'], 'callee': call['callee'],
                    'line': call['line'], 'resolution': how,
                    'to_path': target['path'] if target else None,
                    'to_symbol': target['symbol'] if target else None, 'depth': depth}
            if how in {'local', 'imported'} and target:
                if (target['path'], target['symbol']) not in seen: queue.append((target, depth + 1))
            elif how in GAP_RESOLUTIONS:
                unresolved += 1
            if how in {'builtin'} and depth > 0: continue
            steps.append(step)
            if len(steps) >= MAX_STEPS: break
    touched = sorted({step['from_path'] for step in steps} | {step['to_path'] for step in steps if step['to_path']} | ({path} if path else set()))
    return {'entry': {'surface': entry['value']['surface'], 'route': entry['value']['route'],
                      'http_method': entry['value']['http_method'], 'framework': entry['value']['framework'],
                      'path': path, 'line': entry['location'].get('start_line'), 'handler': handler},
            'handler_found': bool(start), 'steps': steps, 'unresolved_steps': unresolved,
            'touched_files': touched,
            'environment_reads': sorted({name for file in touched for name in env_by_file.get(file, set())}),
            'truncated': len(steps) >= MAX_STEPS}


def external_name_index(import_facts, edge_facts):
    external_modules = defaultdict(set)
    for fact in edge_facts or []:
        if fact['resolution'] == 'EXTERNAL': external_modules[fact['location']['path']].add(fact['value']['module'])
    names = defaultdict(set)
    for fact in import_facts or []:
        path, value = fact['location']['path'], fact['value']
        if value['module'] in external_modules.get(path, set()):
            names[path].update(value.get('names') or [])
            names[path].add(value['module'].split('.')[-1].split('/')[-1])
    return names


def run(target, source, symbols=None, calls=None, edges=None, entry_points=None, env=None, imports=None, **options):
    from . import config as config_module, entrypoints as entry_module, resolve, syntax
    if symbols is None:
        produced = syntax.run(target, source)['facts']
        symbols = [f for f in produced if f['kind'] == 'symbol']
        calls = [f for f in produced if f['kind'] == 'call_edge']
        imports = [f for f in produced if f['kind'] == 'import_edge']
        edges = resolve.run(target, source, imports=imports)['facts']
        entry_points = entry_module.run(target, source, symbols=symbols)['facts']
        env = config_module.run(target, source)['facts']
    by_file, by_name = index_symbols(symbols)
    call_index = index_calls(calls or [])
    imported_map = imported_files(edges or [], symbols)
    env_by_file = defaultdict(set)
    for fact in env or []:
        if fact['kind'] == 'env_read': env_by_file[fact['location']['path']].add(fact['value']['name'])
    external_names = external_name_index(imports, edges)
    facts = []
    order = {'http': 0, 'job': 1, 'queue': 2, 'cli': 3, 'container': 4, 'library': 5}
    # Routes declared inside a test suite are fixtures for the tests, not the product's own surface.
    ranked = sorted([f for f in entry_points or [] if f['value'].get('handler') and f['value'].get('category') != 'test'],
                    key=lambda f: (order.get(f['value']['surface'], 9), str(f['value']['route']), f['location']['path']))
    # One handler is one flow, however many routes reach it; five identical traces are noise, not coverage.
    seen_handlers = {}
    deduplicated = []
    for entry in ranked:
        key = (entry['location']['path'], entry['value'].get('handler'),
                 entry['value'].get('framework'))
        if key in seen_handlers:
            seen_handlers[key]['value'].setdefault('also_reached_by', []).append(
                {'surface': entry['value']['surface'], 'route': entry['value']['route'],
                 'line': entry['location'].get('start_line')})
            continue
        copy = {**entry, 'value': dict(entry['value'])}
        seen_handlers[key] = copy
        deduplicated.append(copy)
    for index, entry in enumerate(deduplicated, start=1):
        traced = trace(entry, by_file, by_name, call_index, imported_map, env_by_file, external_names)
        if not traced['handler_found']: continue
        traced['also_reached_by'] = entry['value'].get('also_reached_by', [])
        traced['in_codebase_steps'] = sum(1 for step in traced['steps'] if step['resolution'] in {'local', 'imported'})
        facts.append(make('flow', NAME, VERSION, entry['input_sha'],
                          {'path': entry['location']['path'], 'start_line': entry['location'].get('start_line'),
                           'symbol': entry['value'].get('handler')},
                          {'flow_id': 'FLOW-%03d' % index, **traced},
                          resolution='RESOLVED' if not traced['unresolved_steps'] else 'UNRESOLVED',
                          limitations=LIMITATIONS))
    facts.sort(key=lambda f: f['value']['flow_id'])
    traced_into_code = sum(1 for fact in facts if fact['value']['in_codebase_steps'])
    summary = {'flows': len(facts), 'entry_points_considered': len(ranked),
               'distinct_handlers': len(deduplicated),
               'flows_reaching_other_code': traced_into_code,
               'flows_stopping_at_the_first_boundary': len(facts) - traced_into_code,
               'test_entry_points_excluded': sum(1 for f in entry_points or [] if f['value'].get('category') == 'test'),
               'entry_points_without_traceable_handler': len(ranked) - len(facts),
               'total_steps': sum(len(f['value']['steps']) for f in facts),
               'unresolved_steps': sum(f['value']['unresolved_steps'] for f in facts),
               'steps_by_resolution': {key: sum(1 for f in facts for step in f['value']['steps'] if step['resolution'] == key)
                                       for key in ['local', 'imported', 'external', 'builtin', 'method_or_external', 'ambiguous', 'unresolved']},
               'max_depth': MAX_DEPTH, 'max_steps_per_flow': MAX_STEPS,
               'interpretation': 'Statically traced paths. Unresolved steps mark where the trace stopped, not where execution stops.'}
    return {'facts': facts, 'summary': summary, 'available': True,
            'input_sha': digest(''.join(sorted(f['id'] for f in facts)).encode('utf-8')), 'reason': None}
