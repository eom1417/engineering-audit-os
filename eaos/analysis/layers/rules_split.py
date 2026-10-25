"""One source of business rules (M6.8): the rules of a write compared between the browser and the server.

A number's limits the browser checks before it sends a write (zod or yup: `quantity: z.number().int().min(1).max(10)`)
must also hold where the write lands: the server's handler of that endpoint, or, when the browser writes to Supabase
itself, a check constraint of the table. When neither checks it, anyone who sends the request without the screen sets
any value: the server trusts the client. And a money value (a price, a total, a discount) the screen computes and sends to
be saved is a business calculation inside the UI.
"""
import re

LIMITED = re.compile(r'(?P<field>\w+)\s*:\s*(?:z|zod|yup|Yup)\.(?:coerce\.)?number\(\)(?P<chain>(?:\s*\.\s*\w+\([^()]*\))+)')
LIMIT_CALL = re.compile(r'\.(min|max|int|integer|positive|negative|nonnegative|nonpositive|lt|gt|lte|gte|moreThan|lessThan)\(')
FETCH = re.compile(r'''(?:fetch|axios\.(?P<verb>post|put|patch|delete)|api\.(?P<verb2>post|put|patch|delete))\(\s*[`'"](?P<url>/[^`'"?]*)''')
FETCH_METHOD = re.compile(r'''method\s*:\s*['"`](?P<method>POST|PUT|PATCH|DELETE)['"`]''', re.I)
SUPABASE_WRITE = re.compile(r'''\.from\(\s*['"`](?P<table>[\w.]+)['"`]\s*\)\s*\.\s*(?:insert|update|upsert)\b''')
COMPARISON = r'(?:\s*[<>]=?|\s*\)\s*[<>]|\.(?:min|max|lt|gt|lte|gte|between)\b)'
MONEY = re.compile(r'(?:const|let|var)\s+(?P<name>\w*(?:price|total|amount|subtotal|discount|tax|fee|cost)\w*)\s*=\s*[^;\n]*[*+\-/]\s*[\w(]', re.I)
SPREAD = re.compile(r'\.\.\.\s*(?:req\.body|request\.body|body|data|payload|input)\b')


def _limits(text):
    """[(field, limits as written, line)] of the numbers a schema in this file limits."""
    return [(m.group('field'), m.group('chain').strip(), text.count('\n', 0, m.start()) + 1)
            for m in LIMITED.finditer(text) if LIMIT_CALL.search(m.group('chain'))]


def _writes(text):
    """[('endpoint', method, url) or ('table', None, table)] this browser file sends."""
    found = []
    for match in FETCH.finditer(text):
        verb = (match.group('verb') or match.group('verb2') or '').upper()
        method = FETCH_METHOD.search(text[match.end():match.end() + 300])
        if verb or method: found.append(('endpoint', verb or method.group('method').upper(), match.group('url')))
    found += [('table', None, match.group('table')) for match in SUPABASE_WRITE.finditer(text)]
    return found


def _route_matches(route, url):
    pattern = re.sub(r':\w+|\{\w+\}|\[\w+\]|<[^>]+>', '[^/]+', str(route).rstrip('/'))
    return bool(re.fullmatch(pattern, url.rstrip('/')))


def _server_checks(field, row, project):
    """Whether the handler of `row` checks `field` (a comparison on it, or a schema it validates against); None when it
    never reads the field and does not store the whole body."""
    text = '\n'.join(project.lines(row['path'])[row['line'] - 1:row['end']])
    if row['validation']: return True
    if re.search(r'\b' + re.escape(field) + r'\b' + COMPARISON, text) or re.search(r'[<>]=?\s*\w*\.?' + re.escape(field) + r'\b', text):
        return True
    return False if re.search(r'\b' + re.escape(field) + r'\b', text) or SPREAD.search(text) else None


def _constraint(field, table, project):
    """Whether a migration puts a check constraint on the field."""
    texts = '\n'.join(project.text(path) for path in project.schemas)
    return bool(re.search(r'check\s*\([^;]*\b' + re.escape(field) + r'\b', texts, re.I))


def _unchecked(project, field, method, target, endpoints):
    """The handler of the endpoint a write is sent to, when it reads the field without checking it; else None."""
    rows = [r for r in endpoints if r['method'] in (method, 'ANY') and _route_matches(r['route'], target)]
    checked = [_server_checks(field, r, project) for r in rows]
    return rows[checked.index(False)] if False in checked and True not in checked else None


def _breach(project, rule, write, endpoints):
    """The finding of one limited field sent by one write, or None when the other side checks it."""
    kind, method, target = write
    if kind == 'endpoint':
        row = _unchecked(project, rule['field'], method, target, endpoints)
        return _finding(rule, f'{method} {target}', row) if row else None
    if _constraint(rule['field'], target, project): return None
    return _finding(rule, f'the table {target}', {'path': rule['path'], 'line': rule['line']})


def _browser_only(project, path, endpoints):
    text = project.text(path)
    writes = _writes(text)
    rules = [{'field': field, 'limits': limits, 'path': path, 'line': line} for field, limits, line in _limits(text)]
    return [found for rule in rules for write in writes for found in [_breach(project, rule, write, endpoints)] if found]


def _finding(rule, route, at):
    """`rule`: the browser's limit {field, limits, path, line}; `at`: where the write lands unchecked {path, line}."""
    where = f"{rule['path']}:{rule['line']}"
    return {'rule': 'browser-only-rule', 'path': at['path'], 'line': at['line'], 'evidence': f"{where} {rule['limits']}",
            'params': {'field': rule['field'], 'route': route, 'path': at['path'], 'where': where}}


def _calculations(project, path):
    text = project.text(path)
    if not _writes(text): return []
    found = []
    for match in MONEY.finditer(text):
        name = match.group('name')
        if re.search(r'\b' + re.escape(name) + r'\b', text[match.end():]) and re.search(r'body|insert|update|upsert', text[match.end():]):
            found.append({'rule': 'ui-calculation', 'path': path, 'line': text.count('\n', 0, match.start()) + 1,
                          'evidence': match.group(0).strip()[:160], 'params': {'what': name, 'path': path}})
    return found


def check(project, rows, endpoints):
    """The findings of the rules kept in the browser alone."""
    found = []
    for row in rows:
        if row['side'] != 'browser': continue
        found += _browser_only(project, row['path'], endpoints) + _calculations(project, row['path'])
    return found
