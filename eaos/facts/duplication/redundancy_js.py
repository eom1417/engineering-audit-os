"""Redundant work in JavaScript and TypeScript, judged from the recorded facts (eaos/facts/duplication/redundancy.py): a query or
request inside a loop or an iterating call (n_plus_one), and the same query twice on one unconditional path of a
function (repeated_call)."""
import re
from collections import defaultdict


ITERATORS = {'map', 'forEach', 'flatMap', 'reduce', 'filter', 'some', 'every', 'find', 'findIndex'}
JS_LANGUAGES = {'javascript', 'typescript', 'tsx', 'jsx'}


def _span(fact):
    location = fact['location']
    return (location.get('start_line') or 0), (location.get('end_line') or location.get('start_line') or 0)


def _index_call(fact, value, index):
    """An iterator call spanning lines is a loop; a fetch is an HTTP read."""
    path, span = fact['location']['path'], _span(fact)
    if value.get('callee') in ITERATORS and span[1] > span[0]: index[path]['loops'].append(span)
    elif value.get('callee') == 'fetch': index[path]['data'].append((span[0], 'http', 'get', 'fetch'))


def _index_structure(fact, index):
    path, value, kind = fact['location']['path'], fact.get('value') or {}, fact['kind']
    if kind == 'loop': index[path]['loops'].append(_span(fact))
    elif kind == 'branch': index[path]['branches'].append(_span(fact))
    elif kind == 'scope' and value.get('kind') == 'function':
        index[path]['scopes'].append((*_span(fact), fact['location'].get('symbol') or value.get('name')))
    elif kind == 'call_site': _index_call(fact, value, index)


def _index_js(structure, entrypoints):
    """{path: {'loops', 'branches', 'scopes', 'data'}} from the structure and entry-point facts."""
    index = defaultdict(lambda: {'loops': [], 'branches': [], 'scopes': [], 'data': []})
    for fact in structure or []: _index_structure(fact, index)
    for fact in entrypoints or []:
        if fact['kind'] != 'data_access': continue
        value = fact.get('value') or {}
        index[fact['location']['path']]['data'].append(
            (fact['location'].get('start_line') or 0, value.get('client', 'data'), value.get('operation', ''), value.get('target', '')))
    return index


# Between two reads, any of these puts them on different paths: another arm of a condition, a fallback
# after a failure, or an exit. The branch facts carry only the condition's line, not the arm's extent.
EXCLUSIVE = re.compile(r'^\s*(\}\s*)?(else\b|case\b|default\s*:)|\bcatch\b|\breturn\b|\bthrow\b')


def _one_path(lines, first, second):
    return not any(EXCLUSIVE.search(lines[n - 1]) for n in range(first + 1, second) if 0 < n <= len(lines))


def _innermost(spans, line):
    inside = [s for s in spans if s[0] <= line <= s[1]]
    return min(inside, key=lambda s: s[1] - s[0]) if inside else None


COUNTED = re.compile(r'^\s*(for\s*\(\s*(let|var)\s+\w+\s*=[^;]*;[^;]*;|while\s*\(|do\b)')
EXITS = re.compile(r'\breturn\b|\bbreak\b')


def _retry_loop(lines, loop):
    """A loop that counts attempts and leaves on success: a retry or a poll, not one call per item of data.

    Its header is a counter (`for (let i = 1; i <= N; i += 1)`), `while` or `do`, never an iteration over a
    collection (`of`, `in`, `.length`, an iterating call); and its body can leave (`return`, `break`).
    """
    if not lines or not 0 < loop[0] <= len(lines): return False
    header = lines[loop[0] - 1]
    if not COUNTED.search(header) or '.length' in header or re.search(r'\b(of|in)\b', header.split(';')[0]): return False
    return any(EXITS.search(lines[n - 1]) for n in range(loop[0] + 1, min(loop[1], len(lines)) + 1))


def _js_redundancies(rel, facts, text=''):
    """n_plus_one and repeated_call for one JavaScript or TypeScript file, from its recorded facts."""
    lines = text.splitlines()
    return _js_n_plus_one(rel, facts, lines) + _js_repeated(rel, facts, lines)


def _js_n_plus_one(rel, facts, lines):
    """A data call inside a loop that is not a retry: one row per line."""
    rows, seen = [], set()
    for line, client, operation, target in sorted(set(facts['data'])):
        scope = _innermost(facts['scopes'], line)
        symbol = scope[2] if scope else '<module>'
        loop = _innermost(facts['loops'], line)
        # An iterating call on the same line as the data call is the data call's own chain (`.select().filter()`)
        # unless it spans further lines: a loop must enclose the call, not be it.
        if loop and not (loop[0] == loop[1] == line) and not _retry_loop(lines, loop):
            key = ('n_plus_one', line)
            if key not in seen:
                seen.add(key)
                rows.append({'kind': 'n_plus_one', 'path': rel, 'symbol': symbol, 'start_line': line, 'end_line': line,
                             'callee': f'{client}.{operation} {target}'.strip()})
    return rows


def _js_repeated(rel, facts, source_lines):
    """The same read twice in one function and loop (or none), with nothing between them making them alternatives."""
    rows, by_place = [], defaultdict(list)
    for line, client, operation, target in sorted(set(facts['data'])):
        if operation not in ('select', 'get', 'rpc') or target in ('{dynamic}', 'fetch'): continue
        scope = _innermost(facts['scopes'], line)
        # Same function, same loop (or none): a read in a loop is already n_plus_one, not a repeat of one outside it.
        by_place[(scope, _innermost(facts['loops'], line), client, operation, target)].append(line)
    for (scope, _, client, operation, target), lines in sorted(by_place.items(), key=lambda item: str(item[0])):
        # Two reads count only on one path: nothing between them that makes them alternatives.
        for first, second in zip(lines, lines[1:]):
            if _one_path(source_lines, first, second):
                rows.append({'kind': 'repeated_call', 'path': rel, 'symbol': scope[2] if scope else '<module>',
                             'start_line': first, 'end_line': second, 'callee': f'{client}.{operation} {target}'})
    return rows
