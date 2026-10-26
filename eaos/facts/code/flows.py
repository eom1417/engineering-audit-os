"""Traced execution paths from each entry point, built only from resolved symbols and calls.

Every step carries file:line. A call we cannot resolve is recorded as an explicit gap in the trace,
never skipped, so a short flow is visibly short rather than quietly incomplete.
"""
import builtins
from collections import defaultdict
from .. import digest, make

BUILTINS = set(dir(builtins)) | {'console', 'print', 'require', 'super', 'len', 'range'}
# The globals every JavaScript runtime defines: a call to one leaves the codebase, it is not a gap in the trace.
JS_GLOBALS = {'Array', 'Boolean', 'Date', 'Error', 'JSON', 'Map', 'Math', 'Number', 'Object', 'Promise', 'Reflect', 'RegExp',
              'Set', 'String', 'Symbol', 'URL', 'URLSearchParams', 'WeakMap', 'WeakSet', 'atob', 'btoa', 'clearInterval',
              'clearTimeout', 'decodeURI', 'decodeURIComponent', 'encodeURI', 'encodeURIComponent', 'isFinite', 'isNaN',
              'parseFloat', 'parseInt', 'queueMicrotask', 'requestAnimationFrame', 'cancelAnimationFrame', 'setInterval',
              'setTimeout', 'structuredClone'}
JS_SUFFIXES = ('.js', '.jsx', '.mjs', '.cjs', '.ts', '.tsx', '.mts', '.cts')

NAME = 'flows'
VERSION = '4'
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
    if symbol_facts: _add_siblings(imports, symbol_facts)
    return imports


def _folder(path): return '/'.join(path.split('/')[:-1])


def _add_siblings(imports, symbol_facts):
    # Go's package-internal imports are implicit: any file in the same directory can call any
    # symbol defined in any other file in that directory. We treat the directory as the unit
    # of visibility, so a handler in foo/bar.go can reach a symbol in foo/baz.go.
    directories = defaultdict(set)
    for fact in (fact for fact in symbol_facts if fact['kind'] == 'symbol'):
        directories[_folder(fact['location']['path'])].add(fact['location']['path'])
    for path in list(imports.keys()):
        imports[path] |= {sibling for sibling in directories.get(_folder(path), ()) if sibling != path}


def resolve_callee(name, path, by_file, by_name, imports, external_names, attribute):
    """Distinguish a real gap in the trace from a call that simply leaves the codebase."""
    local = [row for row in by_file.get(path, []) if row['name'] == name]
    if local: return local[0], 'local'
    candidates = [row for row in by_name.get(name, []) if row['path'] in imports.get(path, set())]
    if len(candidates) == 1: return candidates[0], 'imported'
    if len(candidates) > 1: return None, 'ambiguous'
    outside = _outside(name, path, external_names)
    if outside: return None, outside
    if attribute: return None, 'method_or_external'
    return None, 'unresolved'


def _outside(name, path, external_names):
    """How a call leaves the codebase: into a library the file imports ('external'), or to a builtin or a JavaScript
    runtime global ('builtin'); None when it does not."""
    if name in external_names.get(path, set()): return 'external'
    if name in BUILTINS or (name in JS_GLOBALS and path.endswith(JS_SUFFIXES)): return 'builtin'
    return None


GAP_RESOLUTIONS = {'unresolved', 'ambiguous'}


def _resolve_handler(handler, path, by_file, by_name, imports, calls=None):
    """Locate the symbol a handler points at. Accepts bare names, receiver-qualified calls
    like `s.handleIndex`, and cross-file imports."""
    if not handler: return None
    return (_module_start(handler, path, by_file, calls) or _console_script(handler, path, by_file)
            or _in_file(handler, path, by_file) or _imported(handler, path, by_name, imports))


def _module_start(handler, path, by_file, calls):
    # A script page (Streamlit) is its module: the flow starts at the calls made at the top level.
    if handler == '<module>': return {'path': path, 'symbol': None, 'name': '<module>'}
    # A script that runs a file of the repository (`node scripts/ship.mjs`, `python -m pkg.tool`) starts at its top level.
    if not handler.endswith(('.py',) + JS_SUFFIXES): return None
    for candidate in (handler, handler[:-3] + '/__main__.py' if handler.endswith('.py') else None):
        if candidate in by_file or (candidate, None) in (calls or {}): return {'path': candidate, 'symbol': None, 'name': '<module>'}
    return None


def _named(rows, name):
    return next((row for row in rows if row['symbol'] == name or row['name'] == name), None)


def _console_script(handler, path, by_file):
    # A console script `package.module:function` names its function by import path, from the manifest's folder.
    if ':' not in handler or '/' in handler: return None
    module, _, attribute = handler.partition(':')
    base = path.rsplit('/', 1)[0] + '/' if '/' in path else ''
    stem = module.replace('.', '/')
    for candidate in (stem + '.py', stem + '/__init__.py', 'src/' + stem + '.py', 'src/' + stem + '/__init__.py'):
        row = _named(by_file.get(base + candidate, []), attribute)
        if row: return row
    return None


def _in_file(handler, path, by_file):
    """The handler in its own file, by its name, else by the last part of a receiver-qualified name."""
    rows = by_file.get(path, [])
    found = _named(rows, handler)
    if found or '.' not in handler: return found
    return _named(rows, handler.rsplit('.', 1)[-1])


def _imported(handler, path, by_name, imports):
    """The one symbol of that name, else of the name's last part, in a file `path` imports."""
    reachable = imports.get(path, set())
    for name in [handler] + ([handler.rsplit('.', 1)[-1]] if '.' in handler else []):
        candidates = [row for row in by_name.get(name, []) if row['path'] in reachable]
        if len(candidates) == 1: return candidates[0]
    return None


def _step(call, current, depth, target, how):
    return {'from': current['symbol'], 'from_path': current['path'], 'callee': call['callee'],
            'line': call['line'], 'resolution': how,
            'to_path': target['path'] if target else None,
            'to_symbol': target['symbol'] if target else None, 'depth': depth}


def _note(target, how, depth, walk):
    """Queue a call the trace can follow; count a gap."""
    if how in {'local', 'imported'} and target:
        if (target['path'], target['symbol']) not in walk['seen']: walk['queue'].append((target, depth + 1))
    elif how in GAP_RESOLUTIONS:
        walk['unresolved'] += 1


def _trace_calls(current, depth, context, walk):
    """The steps of one function's calls, each resolved; the ones the trace can follow are queued."""
    called = set()
    for call in context['calls'].get((current['path'], current['symbol']), []):
        # The same callee called again from the same function adds nothing to the path: its first call stands for
        # it, so repeated hooks and helpers do not spend the step budget before the trace leaves the file.
        if call['callee'] in called: continue
        called.add(call['callee'])
        target, how = resolve_callee(call['callee'], current['path'], context['by_file'], context['by_name'], context['imports'],
                                     context['external_names'], call.get('attribute', False))
        _note(target, how, depth, walk)
        if how in {'builtin'} and depth > 0: continue
        walk['steps'].append(_step(call, current, depth, target, how))
        if len(walk['steps']) >= MAX_STEPS: break


def trace(entry, by_file, by_name, calls, imports, env_by_file, external_names):
    """Follow one entry point through resolvable calls, recording every stop with its reason."""
    handler = entry['value'].get('handler')
    path = entry['location']['path']
    start = _resolve_handler(handler, path, by_file, by_name, imports, calls)
    context = {'by_file': by_file, 'by_name': by_name, 'calls': calls, 'imports': imports, 'external_names': external_names}
    walk = {'steps': [], 'seen': set(), 'unresolved': 0, 'queue': [(start, 0)] if start else []}
    while walk['queue'] and len(walk['steps']) < MAX_STEPS:
        current, depth = walk['queue'].pop(0)
        key = (current['path'], current['symbol'])
        if key in walk['seen'] or depth > MAX_DEPTH: continue
        walk['seen'].add(key)
        _trace_calls(current, depth, context, walk)
    steps, unresolved = walk['steps'], walk['unresolved']
    touched = _touched(steps, path)
    return {'entry': {'surface': entry['value']['surface'], 'route': entry['value']['route'],
                      'http_method': entry['value']['http_method'], 'framework': entry['value']['framework'],
                      'path': path, 'line': entry['location'].get('start_line'), 'handler': handler},
            'handler_found': bool(start), 'steps': steps, 'unresolved_steps': unresolved,
            'touched_files': touched,
            'environment_reads': sorted({name for file in touched for name in env_by_file.get(file, set())}),
            'truncated': len(steps) >= MAX_STEPS}


def _touched(steps, path):
    """The files a trace passes through, the entry point's own included, sorted."""
    return sorted({step['from_path'] for step in steps} | {step['to_path'] for step in steps if step['to_path']} | ({path} if path else set()))


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


def _computed_inputs(target, source):
    from . import config as config_module, entrypoints as entry_module, resolve, syntax
    produced = syntax.run(target, source)['facts']
    symbols = [f for f in produced if f['kind'] == 'symbol']
    calls = [f for f in produced if f['kind'] == 'call_edge']
    imports = [f for f in produced if f['kind'] == 'import_edge']
    edges = resolve.run(target, source, imports=imports)['facts']
    entry_points = entry_module.run(target, source, symbols=symbols)['facts']
    env = config_module.run(target, source)['facts']
    return symbols, calls, imports, edges, entry_points, env


SURFACE_ORDER = {'http': 0, 'page': 0, 'job': 1, 'queue': 2, 'cli': 3, 'container': 4, 'library': 5}


def _ranked(entry_points):
    # Routes declared inside a test suite are fixtures for the tests, not the product's own surface.
    return sorted([f for f in entry_points or [] if f['value'].get('handler') and f['value'].get('category') != 'test'],
                  key=lambda f: (SURFACE_ORDER.get(f['value']['surface'], 9), str(f['value']['route']), f['location']['path']))


def _one_per_handler(ranked):
    """One handler is one flow, however many routes reach it; five identical traces are noise, not coverage."""
    seen_handlers = {}
    deduplicated = []
    for entry in ranked:
        key = (entry['location']['path'], entry['value'].get('handler'), entry['value'].get('framework'))
        if key in seen_handlers:
            seen_handlers[key]['value'].setdefault('also_reached_by', []).append(
                {'surface': entry['value']['surface'], 'route': entry['value']['route'],
                 'line': entry['location'].get('start_line')})
            continue
        copy = {**entry, 'value': dict(entry['value'])}
        seen_handlers[key] = copy
        deduplicated.append(copy)
    return deduplicated


def _flow_fact(index, entry, traced):
    traced['also_reached_by'] = entry['value'].get('also_reached_by', [])
    traced['in_codebase_steps'] = sum(1 for step in traced['steps'] if step['resolution'] in {'local', 'imported'})
    return make('flow', NAME, VERSION, entry['input_sha'],
                {'path': entry['location']['path'], 'start_line': entry['location'].get('start_line'),
                 'symbol': entry['value'].get('handler')},
                {'flow_id': 'FLOW-%03d' % index, **traced},
                resolution='RESOLVED' if not traced['unresolved_steps'] else 'UNRESOLVED',
                limitations=LIMITATIONS)


def _summary(facts, ranked, deduplicated, entry_points):
    traced_into_code = sum(1 for fact in facts if fact['value']['in_codebase_steps'])
    return {'flows': len(facts), 'entry_points_considered': len(ranked),
            'distinct_handlers': len(deduplicated),
            'flows_reaching_other_code': traced_into_code,
            'flows_stopping_at_the_first_boundary': len(facts) - traced_into_code,
            'test_entry_points_excluded': sum(1 for f in entry_points or [] if f['value'].get('category') == 'test'),
            'entry_points_without_traceable_handler': len(ranked) - len(facts),
            'total_steps': sum(len(f['value']['steps']) for f in facts),
            'unresolved_steps': sum(f['value']['unresolved_steps'] for f in facts),
            'steps_by_resolution': _by_resolution(facts),
            'max_depth': MAX_DEPTH, 'max_steps_per_flow': MAX_STEPS,
            'interpretation': 'Statically traced paths. Unresolved steps mark where the trace stopped, not where execution stops.'}


def _by_resolution(facts):
    """How many steps of all the flows each resolution holds."""
    return {key: sum(1 for f in facts for step in f['value']['steps'] if step['resolution'] == key)
            for key in ['local', 'imported', 'external', 'builtin', 'method_or_external', 'ambiguous', 'unresolved']}


def _env_by_file(env):
    """{file: the environment variables it reads}."""
    env_by_file = defaultdict(set)
    for fact in (fact for fact in env or [] if fact['kind'] == 'env_read'):
        env_by_file[fact['location']['path']].add(fact['value']['name'])
    return env_by_file


def run(target, source, symbols=None, calls=None, edges=None, entry_points=None, env=None, imports=None, **options):
    if symbols is None: symbols, calls, imports, edges, entry_points, env = _computed_inputs(target, source)
    by_file, by_name = index_symbols(symbols)
    call_index = index_calls(calls or [])
    imported_map = imported_files(edges or [], symbols)
    env_by_file = _env_by_file(env)
    external_names = external_name_index(imports, edges)
    ranked = _ranked(entry_points)
    deduplicated = _one_per_handler(ranked)
    facts = []
    for index, entry in enumerate(deduplicated, start=1):
        traced = trace(entry, by_file, by_name, call_index, imported_map, env_by_file, external_names)
        if traced['handler_found']: facts.append(_flow_fact(index, entry, traced))
    facts.sort(key=lambda f: f['value']['flow_id'])
    summary = _summary(facts, ranked, deduplicated, entry_points)
    return {'facts': facts, 'summary': summary, 'available': True,
            'input_sha': digest(''.join(sorted(f['id'] for f in facts)).encode('utf-8')), 'reason': None}
