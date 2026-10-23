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

from ..facts.store import facts as facts_of
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


def _is_component(short, kind, path, components):
    return (path, short) in components or (kind == 'function' and path.endswith(COMPONENT_SUFFIXES) and short[:1].isupper())


def _is_handler(short):
    return (short.startswith('handle') and short[6:7].isupper()) or (short.startswith('on') and short[2:3].isupper())


def _kind(name, kind, path, components):
    short = name.rsplit('.', 1)[-1]
    if _is_component(short, kind, path, components): return 'component'
    if short.startswith('use') and short[3:4].isupper(): return 'hook'
    if _is_handler(short): return 'handler'
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


def _external(report):
    """({file: Lizard's function rows}, {(file, name): react-docgen's component})."""
    lizard, components = defaultdict(list), {}
    for f in facts_of(report, 'symbol_metric_external'):
        where, value = f.get('location') or {}, f.get('value') or {}
        if value.get('engine') not in ('lizard', 'react-docgen'): continue
        if value['engine'] == 'lizard' and isinstance(where.get('line'), int): lizard[where.get('path')].append(f)
        elif value.get('record') == 'react_component' and where.get('symbol'): components[(where.get('path'), where['symbol'])] = value
    return lizard, components


def _metrics(report):
    metrics = {}
    for f in facts_of(report, 'metric'):
        where, value = f.get('location') or {}, f.get('value') or {}
        if value.get('scope') in ('function', 'method'): metrics[(where.get('path'), where.get('start_line'), where.get('symbol'))] = value
    return metrics


def _symbol_row(f):
    where, value = f['location'], f['value']
    return {'path': where['path'], 'symbol': where.get('symbol') or value['name'], 'name': value['name'], 'start': where['start_line'],
            'end': where.get('end_line'), 'kind': value['kind'], 'value': value, 'lizard': None}


def _match_lizard(row, found, taken):
    """Lizard's row of a parsed function: the one on its first line, else the one of its name starting within NEAR
    lines (Lizard and the parser can disagree on where a `const name = () =>` begins). An anonymous row is never
    matched by name."""
    match = next((f for f in found if f['location']['line'] == row['start'] and f['id'] not in taken), None) or \
        next((f for f in found if f['location'].get('symbol') == row['name'] and abs(f['location']['line'] - row['start']) <= NEAR
              and f['id'] not in taken), None)
    if match: row['lizard'] = match['value']; taken.add(match['id'])


def _lizard_only(lizard, parsed, taken):
    """Lizard's rows in the files the parser did not read: functions in a language only Lizard measured."""
    rows = []
    for path, found in lizard.items():
        if path in parsed: continue          # the parser read this file; a Lizard row it did not match is not a new function
        for f in (f for f in found if f['id'] not in taken):
            name = str(f['location'].get('symbol') or '')
            rows.append({'path': path, 'symbol': name, 'name': name.rsplit('::', 1)[-1].rsplit('.', 1)[-1], 'start': f['location']['line'],
                         'end': f['value'].get('end_line'), 'kind': 'function', 'value': {}, 'lizard': f['value']})
    return rows


def _rows(symbols, lizard):
    rows, taken = [_symbol_row(f) for f in symbols], set()
    for row in rows: _match_lizard(row, lizard.get(row['path'], ()), taken)
    return rows + _lizard_only(lizard, {row['path'] for row in rows}, taken)


def _by_file(rows):
    by_file = defaultdict(list)
    for row in rows: by_file[row['path']].append(row)
    for found in by_file.values(): found.sort(key=lambda r: (r['start'], -(r['end'] or r['start'])))
    return by_file


def _assign_ids(rows):
    """One id per function: file#symbol, and the first line when the same symbol is defined twice in one file."""
    seen = defaultdict(int)
    for row in rows: seen[(row['path'], row['symbol'])] += 1
    for row in rows:
        row['id'] = f"{row['path']}#{row['symbol']}" + (f"@{row['start']}" if seen[(row['path'], row['symbol'])] > 1 else '')
    return {(row['path'], row['symbol']): row['id'] for row in rows}


def _resolve_call(call, key_of, index):
    """(the calling function's id or None when the call is not in a function, the called function's id or None)."""
    where, value = call.get('location') or {}, call.get('value') or {}
    caller = key_of.get((where.get('path'), where.get('symbol')))
    if not caller or not value.get('callee'): return None, None
    target, how = flows.resolve_callee(value['callee'], where['path'], *index, value.get('attribute', False))
    if how not in ('local', 'imported') or not target: return caller, None
    callee = key_of.get((target['path'], target['symbol']))
    return caller, (callee if callee and callee != caller else None)


def _calls(report, syntax, key_of):
    """(callers of each function, callees of each function, call sites, calls resolved), as the flow tracer resolves."""
    edges = facts_of(report, 'module_edge')
    index_file, index_name = flows.index_symbols([f for f in syntax if isinstance((f.get('location') or {}).get('end_line'), int)])
    index = (index_file, index_name, flows.imported_files(edges, syntax), flows.external_name_index(facts_of(report, 'import_edge'), edges))
    callers, callees = defaultdict(set), defaultdict(set)
    sites = resolved = 0
    for caller, callee in (_resolve_call(call, key_of, index) for call in facts_of(report, 'call_edge')):
        if not caller: continue
        sites += 1
        if not callee: continue
        resolved += 1
        callees[caller].add(callee)
        callers[callee].add(caller)
    return callers, callees, sites, resolved


def _holder(fact, by_file):
    where = fact.get('location') or {}
    line = where.get('start_line')
    return _innermost(by_file.get(where.get('path'), ()), line) if isinstance(line, int) else None


def _touches(report, by_file):
    """{function id: {reads, writes}} of the data and environment each function touches."""
    touches = defaultdict(lambda: {'reads': [], 'writes': []})
    for fact in facts_of(report, 'data_access') + facts_of(report, 'env_read'):
        holder = _holder(fact, by_file)
        if not holder: continue
        side, touch = _touch(fact)
        if touch['name'] and touch not in touches[holder['id']][side]: touches[holder['id']][side].append(touch)
    return touches


def _places(fact):
    places = [(fact.get('path'), fact.get('line'))] + [(s.get('path'), s.get('line')) for s in fact.get('sites') or []]
    return [(p, n) for p, n in places if p and isinstance(n, int)]


def _cards(card_rows, evidence, by_file):
    """{function id: the cards whose evidence sits on one of its lines}."""
    sites_of = {fact.get('id'): _places(fact) for fact in evidence or ()}
    cards = defaultdict(list)
    for card in card_rows or ():
        for path, line in (site for fact in card.get('evidence') or () for site in sites_of.get(fact, ())):
            holder = _innermost(by_file.get(path, ()), line)
            if holder and card['id'] not in cards[holder['id']]: cards[holder['id']].append(card['id'])
    return cards


def _signature(short, value, component):
    if component is not None:
        props = component.get('props') or []
        return short + '({ ' + ', '.join(p['name'] + ('' if p.get('required') else '?') for p in props) + ' })' if props else f'{short}()'
    if value.get('signature') is not None:
        return f"{short}({', '.join(str(p) for p in (value.get('signature') or {}).get('parameters') or [])})"
    return None


def _lines(row, liz, metric):
    """An engine's measure when it is a possible one (lizard said -1 for eaos/blueprint.py page, and the whole section
    failed its contract); else EAOS's own."""
    if liz and (liz.get('nloc') or -1) >= 0: return {'value': liz['nloc'], 'src': 'engines lizard#nloc', 'unit': 'lines'}
    if metric.get('lines') is not None: return {'value': metric['lines'], 'src': 'facts/metrics.json#metric.value.lines', 'unit': 'lines'}
    span = (row['end'] - row['start'] + 1) if row['end'] else None
    return {'value': span, 'src': 'facts/syntax.json#symbol end_line - start_line + 1', 'unit': 'lines'}


def _complexity(liz, metric):
    if liz and liz.get('cyclomatic_complexity') is not None:
        return {'value': liz['cyclomatic_complexity'], 'src': 'engines lizard#cyclomatic_complexity', 'unit': 'count'}
    if metric.get('branches') is not None:
        return {'value': metric['branches'] + 1, 'src': 'facts/metrics.json#metric.value.branches + 1 (lexical)', 'unit': 'count'}
    return {'value': None, 'src': 'not measured: no Lizard row and no metric for this function', 'unit': 'count'}


def _function(row, known, links):
    """One function's row; `known`: (metrics, components); `links`: (callers, callees, touches, cards)."""
    metrics, components = known
    callers, callees, touches, cards = links
    value, liz = row['value'], row['lizard']
    metric = metrics.get((row['path'], row['start'], row['symbol'])) or {}
    return {'id': row['id'], 'name': row['symbol'], 'module': row['path'], 'line': row['start'], 'end_line': row['end'],
            'language': _language(row['path']), 'kind': _kind(row['symbol'], row['kind'], row['path'], components),
            'signature': _signature(row['name'], value, components.get((row['path'], row['name']))), 'summary': None,
            'exported': value.get('exported') if isinstance(value.get('exported'), bool) else None,
            'lines': _lines(row, liz, metric), 'complexity': _complexity(liz, metric),
            'callers': sorted(callers.get(row['id'], ())), 'callees': sorted(callees.get(row['id'], ())),
            'reads': touches[row['id']]['reads'] if row['id'] in touches else [],
            'writes': touches[row['id']]['writes'] if row['id'] in touches else [],
            'cards': cards.get(row['id'], [])}


def _language_gap(name, state, n):
    """What `missing` says of a language not measured, or measured only by Lizard; None for one measured."""
    if state == 'not_measured':
        return {'id': f'language:{name}', 'state': 'not_measured', 'step': STEP, 'count': {'value': None, 'src': SRC['functions'], 'unit': 'count'},
                'detail': {'ar': f'{name}: لا حقائق دوال لهذه اللغة بعد', 'en': f'{name}: no function facts for this language yet'}}
    if state == 'partial':
        return {'id': f'calls:{name}', 'state': 'partial', 'step': STEP, 'count': {'value': n, 'src': SRC['functions'], 'unit': 'count'},
                'detail': {'ar': f'{name}: {n} دالة قاسها Lizard، واستدعاءاتها لم تُتتبع', 'en': f'{name}: {n} functions measured by Lizard, their calls not traced'}}
    return None


def _languages(report, out):
    """Each language of the project: measured (the parser read it: its functions and calls), partial (only Lizard
    measured its functions: no calls), or not measured (its files were not read for functions); and what is missing."""
    read, unread = set(), set()
    for f in facts_of(report, 'source_file'):
        name, status = _language(str((f.get('location') or {}).get('path') or '')), (f.get('value') or {}).get('parse_status')
        if name: (read if status == 'OBSERVED' else unread).add(name)
    with_functions = defaultdict(int)
    for fn in (fn for fn in out if fn['language']): with_functions[fn['language']] += 1
    languages, missing = [], []
    for name in sorted(read | unread | set(with_functions)):
        n = with_functions.get(name, 0)
        state = 'measured' if name in read else 'partial' if n else 'not_measured'
        languages.append({'id': name, 'state': state, 'functions': {'value': n if state != 'not_measured' else None,
                                                                        'src': SRC['functions'], 'unit': 'count'}})
        gap = _language_gap(name, state, n)
        if gap: missing.append(gap)
    return languages, missing


def functions(report, card_rows=(), evidence=()):
    """The body of functions.json (without the contract fields), or None when the check read no source file and no
    engine measured a function: nothing was measured, which is not the same as "no functions"."""
    report = Path(report)
    if not facts_of(report, 'source_file') and not facts_of(report, 'symbol_metric_external'): return None
    syntax = facts_of(report, 'symbol')
    symbols = [f for f in syntax if (f.get('value') or {}).get('kind') in ('function', 'method')
               and isinstance((f.get('location') or {}).get('start_line'), int)]
    lizard, components = _external(report)
    rows = _rows(symbols, lizard)
    by_file = _by_file(rows)
    key_of = _assign_ids(rows)
    # Calls, resolved as the flow tracer resolves them; what each function reads and writes, and the cards resting on it.
    callers, callees, sites, resolved = _calls(report, syntax, key_of)
    links = (callers, callees, _touches(report, by_file), _cards(card_rows, evidence, by_file))
    owners, known = _owners(report), (_metrics(report), components)
    out = [_function(row, known, links) for row in sorted(rows, key=lambda r: (r['path'], r['start'], r['id']))]
    modules = defaultdict(int)
    for fn in out: modules[fn['module']] += 1
    module_rows = [{'id': path, 'component': owners.get(path), 'language': _language(path), 'functions': n} for path, n in sorted(modules.items())]
    languages, missing = _languages(report, out)
    measure = lambda value, key: {'value': value, 'src': SRC[key], 'unit': 'count'}
    return {'modules': module_rows, 'functions': out, 'languages': languages, 'missing': missing,
            'counts': {'functions': measure(len(out), 'functions'), 'modules': measure(len(module_rows), 'modules'),
                       'calls': measure(resolved, 'calls'), 'call_sites': measure(sites, 'call_sites'),
                       'reads': measure(sum(len(f['reads']) for f in out), 'reads'),
                       'writes': measure(sum(len(f['writes']) for f in out), 'writes')}}
