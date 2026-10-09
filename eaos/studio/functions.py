"""studio/functions.json: every function EAOS read, what calls it, what it calls and what it touches (NS46.T5).

Read only from the facts the check already wrote; nothing is guessed:

    functions   facts/syntax.json symbol (function, method): name, file, lines, parameters, exported; and the
                functions Lizard measured in a language the parser does not read (engines: symbol_metric_external)
    complexity  Lizard's cyclomatic complexity when Lizard ran (engine lizard), else the lexical branch count of
                facts/metrics.json; `src` names which
    size        Lizard's lines of code, else the metric's line count, else the symbol's span
    kind        react-docgen's exported components (engine react-docgen, with their props as the signature); a
                capitalised function in a .tsx/.jsx file is a component by React's own naming rule; use* is a hook;
                handle*/on* is a handler
    calls       facts/syntax.json call_edge, resolved the way the flow tracer resolves them (facts/flows.py): a callee
                defined in the same file, else in exactly one file this file imports. A call that does not resolve is
                left out, never guessed; the share resolved is counted
    reads and   facts/entrypoints.json data_access (a table read or written, a request sent) and facts/config.json
    writes      env_read, each in the innermost function whose lines hold it
    cards       the cards whose evidence sits on a line of the function (innermost)

Each language of the project is a row of `languages`: measured (functions and their calls), partial (functions without
calls), or not measured (source files, no function facts). A language that is not measured is written in `missing`,
so coverage.json says so and the page shows it, rather than an empty list.
"""
from collections import defaultdict
from pathlib import Path

from .. import indicators
from ..facts import flows
from .model import LANGUAGES

SRC = {
    'functions': 'facts/syntax.json#symbol[kind in function, method] + engines lizard rows the parser did not read',
    'modules': 'files holding at least one function',
    'calls': 'facts/syntax.json#call_edge resolved to a function of this project (facts/flows.py resolve_callee)',
    'call_sites': 'facts/syntax.json#call_edge inside a function',
    'reads': 'facts/entrypoints.json#data_access + facts/config.json#env_read, in the innermost function',
    'writes': 'facts/entrypoints.json#data_access[operation writes]',
}
WRITES = {'insert', 'update', 'upsert', 'delete', 'post', 'put', 'patch', 'remove', 'set', 'create'}
COMPONENT_SUFFIXES = ('.tsx', '.jsx')
STEP = 'NS40.T3'      # the plan step that brings function facts to more languages
NEAR = 3


def _owners(report):
    """{file: component name}: the deepest component of target-architecture.json listing the file (the map's rule)."""
    import json
    try: target = json.loads((Path(report) / 'target-architecture.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): return {}
    owners = {}
    comps = [c for c in target.get('current_components') or [] if isinstance(c, dict) and c.get('name')]
    for c in sorted(comps, key=lambda c: len(str(c['name']))):
        for p in c.get('paths') or []:
            if isinstance(p, str): owners[p] = str(c['name'])
    return owners


def _language(path):
    return LANGUAGES.get(Path(path).suffix.lower())


def _kind(name, kind, path, components):
    short = name.rsplit('.', 1)[-1]
    if (path, short) in components or (kind == 'function' and path.endswith(COMPONENT_SUFFIXES) and short[:1].isupper()):
        return 'component'
    if short.startswith('use') and short[3:4].isupper(): return 'hook'
    if (short.startswith('handle') and short[6:7].isupper()) or (short.startswith('on') and short[2:3].isupper()): return 'handler'
    return 'method' if kind == 'method' else 'function'


def _innermost(rows, line):
    """The function of `rows` (sorted by start) whose lines hold `line` and that starts last."""
    best = None
    for row in rows:
        if row['start'] > line: break
        if row['end'] is not None and row['start'] <= line <= row['end']: best = row
    return best


def _touch(fact):
    """(reads|writes, {kind, name}) of one data_access or env_read fact."""
    value = fact.get('value') or {}
    if fact.get('kind') == 'env_read': return 'reads', {'kind': 'env', 'name': str(value.get('name') or '')}
    operation, target = str(value.get('operation') or '').lower(), str(value.get('target') or '')
    if value.get('client') == 'http':
        return ('writes' if operation in WRITES else 'reads'), {'kind': 'network', 'name': f'{operation.upper()} {target}'.strip()}
    kind = 'storage' if value.get('client') in ('storage', 'bucket') else 'table'
    return ('writes' if operation in WRITES else 'reads'), {'kind': kind, 'name': target}


def functions(report, card_rows=(), evidence=()):
    """The body of functions.json (without the contract fields), or None when the check read no source file and no
    engine measured a function: nothing was measured, which is not the same as "no functions"."""
    report = Path(report)
    if not indicators.facts(report, 'source_file') and not indicators.facts(report, 'symbol_metric_external'): return None
    syntax = indicators.facts(report, 'symbol')
    symbols = [f for f in syntax if (f.get('value') or {}).get('kind') in ('function', 'method')
               and isinstance((f.get('location') or {}).get('start_line'), int)]
    external = [f for f in indicators.facts(report, 'symbol_metric_external') if (f.get('value') or {}).get('engine') in ('lizard', 'react-docgen')]
    lizard = defaultdict(list)
    components = {}
    for f in external:
        where, value = f.get('location') or {}, f.get('value') or {}
        if value['engine'] == 'lizard' and isinstance(where.get('line'), int): lizard[where.get('path')].append(f)
        elif value.get('record') == 'react_component' and where.get('symbol'): components[(where.get('path'), where['symbol'])] = value
    metrics = {}
    for f in indicators.facts(report, 'metric'):
        where, value = f.get('location') or {}, f.get('value') or {}
        if value.get('scope') in ('function', 'method'): metrics[(where.get('path'), where.get('start_line'), where.get('symbol'))] = value

    rows, by_file, taken = [], defaultdict(list), set()
    for f in symbols:
        where, value = f['location'], f['value']
        path, symbol = where['path'], where.get('symbol') or value['name']
        rows.append({'path': path, 'symbol': symbol, 'name': value['name'], 'start': where['start_line'],
                     'end': where.get('end_line'), 'kind': value['kind'], 'value': value, 'lizard': None})
    # Lizard's row of each parsed function: the one on its first line, else the one of its name starting within NEAR
    # lines (Lizard and the parser can disagree on where a `const name = () =>` begins). An anonymous row is never
    # matched by name.
    for row in rows:
        found = lizard.get(row['path'], ())
        match = next((f for f in found if f['location']['line'] == row['start'] and f['id'] not in taken), None) or \
            next((f for f in found if f['location'].get('symbol') == row['name'] and abs(f['location']['line'] - row['start']) <= NEAR
                  and f['id'] not in taken), None)
        if match: row['lizard'] = match['value']; taken.add(match['id'])
    parsed = {row['path'] for row in rows}
    for path, found in lizard.items():
        if path in parsed: continue          # the parser read this file; a Lizard row it did not match is not a new function
        for f in found:
            if f['id'] in taken: continue
            name = str(f['location'].get('symbol') or '')
            rows.append({'path': path, 'symbol': name, 'name': name.rsplit('::', 1)[-1].rsplit('.', 1)[-1], 'start': f['location']['line'],
                         'end': f['value'].get('end_line'), 'kind': 'function', 'value': {}, 'lizard': f['value']})
    for row in rows: by_file[row['path']].append(row)
    for found in by_file.values(): found.sort(key=lambda r: (r['start'], -(r['end'] or r['start'])))

    # One id per function: file#symbol, and the first line when the same symbol is defined twice in one file.
    seen = defaultdict(int)
    for row in rows: seen[(row['path'], row['symbol'])] += 1
    for row in rows:
        row['id'] = f"{row['path']}#{row['symbol']}" + (f"@{row['start']}" if seen[(row['path'], row['symbol'])] > 1 else '')
    key_of = {(row['path'], row['symbol']): row['id'] for row in rows}

    # Calls, resolved as the flow tracer resolves them.
    calls = indicators.facts(report, 'call_edge')
    imports = indicators.facts(report, 'import_edge')
    edges = indicators.facts(report, 'module_edge')
    index_file, index_name = flows.index_symbols([f for f in syntax if isinstance((f.get('location') or {}).get('end_line'), int)])
    imported = flows.imported_files(edges, syntax)
    external_names = flows.external_name_index(imports, edges)
    callers, callees = defaultdict(set), defaultdict(set)
    sites = resolved = 0
    for call in calls:
        where, value = call.get('location') or {}, call.get('value') or {}
        caller = key_of.get((where.get('path'), where.get('symbol')))
        if not caller or not value.get('callee'): continue
        sites += 1
        target, how = flows.resolve_callee(value['callee'], where['path'], index_file, index_name, imported, external_names,
                                           value.get('attribute', False))
        if how not in ('local', 'imported') or not target: continue
        callee = key_of.get((target['path'], target['symbol']))
        if not callee or callee == caller: continue
        resolved += 1
        callees[caller].add(callee)
        callers[callee].add(caller)

    # What each function reads and writes, and the cards resting on it.
    touches = defaultdict(lambda: {'reads': [], 'writes': []})
    for fact in indicators.facts(report, 'data_access') + indicators.facts(report, 'env_read'):
        where = fact.get('location') or {}
        line = where.get('start_line')
        if not isinstance(line, int): continue
        holder = _innermost(by_file.get(where.get('path'), ()), line)
        if not holder: continue
        side, touch = _touch(fact)
        if touch['name'] and touch not in touches[holder['id']][side]: touches[holder['id']][side].append(touch)
    sites_of = {}
    for fact in evidence or ():
        places = [(fact.get('path'), fact.get('line'))] + [(s.get('path'), s.get('line')) for s in fact.get('sites') or []]
        sites_of[fact.get('id')] = [(p, n) for p, n in places if p and isinstance(n, int)]
    cards = defaultdict(list)
    for card in card_rows or ():
        for fact in card.get('evidence') or ():
            for path, line in sites_of.get(fact, ()):
                holder = _innermost(by_file.get(path, ()), line)
                if holder and card['id'] not in cards[holder['id']]: cards[holder['id']].append(card['id'])

    owners = _owners(report)
    out = []
    for row in sorted(rows, key=lambda r: (r['path'], r['start'], r['id'])):
        value, liz = row['value'], row['lizard']
        metric = metrics.get((row['path'], row['start'], row['symbol'])) or {}
        short = row['name']
        component = components.get((row['path'], short))
        if component is not None:
            props = component.get('props') or []
            signature = short + '({ ' + ', '.join(p['name'] + ('' if p.get('required') else '?') for p in props) + ' })' if props else f'{short}()'
        elif value.get('signature') is not None:
            signature = f"{short}({', '.join(str(p) for p in (value.get('signature') or {}).get('parameters') or [])})"
        else:
            signature = None
        span = (row['end'] - row['start'] + 1) if row['end'] else None
        if liz and liz.get('nloc') is not None: lines = {'value': liz['nloc'], 'src': 'engines lizard#nloc', 'unit': 'lines'}
        elif metric.get('lines') is not None: lines = {'value': metric['lines'], 'src': 'facts/metrics.json#metric.value.lines', 'unit': 'lines'}
        else: lines = {'value': span, 'src': 'facts/syntax.json#symbol end_line - start_line + 1', 'unit': 'lines'}
        if liz and liz.get('cyclomatic_complexity') is not None:
            complexity = {'value': liz['cyclomatic_complexity'], 'src': 'engines lizard#cyclomatic_complexity', 'unit': 'count'}
        elif metric.get('branches') is not None:
            complexity = {'value': metric['branches'] + 1, 'src': 'facts/metrics.json#metric.value.branches + 1 (lexical)', 'unit': 'count'}
        else:
            complexity = {'value': None, 'src': 'not measured: no Lizard row and no metric for this function', 'unit': 'count'}
        out.append({'id': row['id'], 'name': row['symbol'], 'module': row['path'], 'line': row['start'], 'end_line': row['end'],
                    'language': _language(row['path']), 'kind': _kind(row['symbol'], row['kind'], row['path'], components),
                    'signature': signature, 'summary': None,
                    'exported': value.get('exported') if isinstance(value.get('exported'), bool) else None,
                    'lines': lines, 'complexity': complexity,
                    'callers': sorted(callers.get(row['id'], ())), 'callees': sorted(callees.get(row['id'], ())),
                    'reads': touches[row['id']]['reads'] if row['id'] in touches else [],
                    'writes': touches[row['id']]['writes'] if row['id'] in touches else [],
                    'cards': cards.get(row['id'], [])})
    modules = defaultdict(int)
    for fn in out: modules[fn['module']] += 1
    module_rows = [{'id': path, 'component': owners.get(path), 'language': _language(path), 'functions': n} for path, n in sorted(modules.items())]

    # Each language of the project: measured (the parser read it: its functions and calls), partial (only Lizard
    # measured its functions: no calls), or not measured (its files were not read for functions).
    read, unread = set(), set()
    for f in indicators.facts(report, 'source_file'):
        name, status = _language(str((f.get('location') or {}).get('path') or '')), (f.get('value') or {}).get('parse_status')
        if name: (read if status == 'OBSERVED' else unread).add(name)
    with_functions = defaultdict(int)
    for fn in out:
        if fn['language']: with_functions[fn['language']] += 1
    languages, missing = [], []
    for name in sorted(read | unread | set(with_functions)):
        n = with_functions.get(name, 0)
        state = 'measured' if name in read else 'partial' if n else 'not_measured'
        languages.append({'id': name, 'state': state, 'functions': {'value': n if state != 'not_measured' else None,
                                                                        'src': SRC['functions'], 'unit': 'count'}})
        if state == 'not_measured':
            missing.append({'id': f'language:{name}', 'state': 'not_measured', 'step': STEP, 'count': {'value': None, 'src': SRC['functions'], 'unit': 'count'},
                            'detail': {'ar': f'{name}: لا حقائق دوال لهذه اللغة بعد', 'en': f'{name}: no function facts for this language yet'}})
        elif state == 'partial':
            missing.append({'id': f'calls:{name}', 'state': 'partial', 'step': STEP, 'count': {'value': n, 'src': SRC['functions'], 'unit': 'count'},
                            'detail': {'ar': f'{name}: {n} دالة قاسها Lizard، واستدعاءاتها لم تُتتبع', 'en': f'{name}: {n} functions measured by Lizard, their calls not traced'}})
    measure = lambda value, key: {'value': value, 'src': SRC[key], 'unit': 'count'}
    return {'modules': module_rows, 'functions': out, 'languages': languages, 'missing': missing,
            'counts': {'functions': measure(len(out), 'functions'), 'modules': measure(len(module_rows), 'modules'),
                       'calls': measure(resolved, 'calls'), 'call_sites': measure(sites, 'call_sites'),
                       'reads': measure(sum(len(f['reads']) for f in out), 'reads'),
                       'writes': measure(sum(len(f['writes']) for f in out), 'writes')}}
