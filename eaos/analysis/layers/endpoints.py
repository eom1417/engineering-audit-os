"""Every endpoint and its guard (M6.4): one row per endpoint (method, route, handler, authentication, authorisation, input
validation, the data it touches, whether it writes), from the entry-point facts, for Next.js (routes, pages API, server
actions), Express, Fastify, Hono, Koa, a server on node:http, FastAPI, Flask, Django and Supabase edge functions.

The handler is read where it is: its function (the symbol facts give its lines), the inline function of the route, or
the whole file for an edge function; a guard the file applies to every route (`app.use(auth)`, Next.js's middleware,
FastAPI's router dependencies, Flask's before_request) counts for each. The table feeds the findings below, the tests
layer (M6.10), the API trial (M6.7) and the report.
"""
import re
from collections import defaultdict
from fnmatch import fnmatch

from . import guards

WRITE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}
PARAM = re.compile(r':\w+|\{\w+\}|\[\w+\]|<(?:\w+:)?\w+>|\(\?P<\w+>')
WRITE_TEXT = re.compile(r'\.(?:insert|update|upsert|delete|destroy|remove|save|create|createMany|updateMany|deleteMany|add|'
                        r'commit|bulk_create|set|push|put)\s*\(|\bdelete\s+\w+\[|\b\w+\[[^\]\n]+\]\s*=[^=]|'
                        r'request\.method\s*==\s*[\'"](?:POST|PUT|PATCH|DELETE)', re.I)
STORE = re.compile(r'^(?:const|let|var)\s+(?P<name>[a-z]\w*)\s*=\s*(?:\{|\[|new\s+Map\b)', re.M)
FILE_GUARD = re.compile(r'\.use\(\s*[^)\n]*\b(auth\w*|requireAuth\w*|passport\.\w+|jwt\w*|session\w*|protect\w*|ensureAuth\w*|'
                        r'requireUser\w*|clerkMiddleware|verifyToken)\b|@\w+\.before_request|APIRouter\([^)]*dependencies|'
                        r'DEFAULT_PERMISSION_CLASSES[^\]]*IsAuthenticated|LoginRequiredMiddleware', re.S)
# A middleware the app wraps around every route, wherever the file declares it (Starlette, FastAPI).
APP_GUARD = re.compile(r'(?:\bMiddleware\(|add_middleware\()\s*[\w.]*(?:Guard|Auth|Token|Session|Login)\w*')
NEXT_MIDDLEWARE = ('middleware.ts', 'middleware.js', 'src/middleware.ts', 'src/middleware.js', 'proxy.ts', 'src/proxy.ts')
MATCHER = re.compile(r'''matcher\s*:\s*\[?(?P<list>[^\]\n]*)''')


class Spans:
    """The lines of each named function of the project, from the symbol facts."""

    def __init__(self, project):
        self.by = defaultdict(list)
        for fact in project.facts('syntax', 'symbol'):
            where = fact['location']
            self.by[(where['path'], fact['value']['name'])].append((where['start_line'], where['end_line']))
        self.named = defaultdict(list)
        for (path, name), spans in self.by.items(): self.named[name] += [(path, span) for span in spans]

    def of(self, path, name, near=None):
        found = self.by.get((path, name)) or []
        if near: found = [span for span in found if span[0] >= near] or found
        return min(found, default=None, key=lambda span: span[0] - (near or 0) if span[0] >= (near or 0) else 10**6)


def _inline_end(lines, start):
    """The last line of a call that opens on `start` (its parentheses closed), 200 lines at most."""
    depth = 0
    for number in range(start, min(len(lines), start + 200) + 1):
        depth += lines[number - 1].count('(') + lines[number - 1].count('{') - lines[number - 1].count(')') - lines[number - 1].count('}')
        if depth <= 0 and number > start or depth <= 0 and lines[number - 1].rstrip().endswith((');', ')')): return number
    return start


DECORATED = ('flask_or_fastapi', 'fastapi', 'starlette')


def _span(project, spans, fact):
    """(path, first line, last line) of the code that answers this endpoint."""
    value, where = fact['value'], fact['location']
    path, line, handler, framework = where['path'], where.get('start_line') or 1, value.get('handler'), value['framework']
    if framework == 'supabase_edge': return path, 1, len(project.lines(path))
    if framework == 'django' and handler: return _django_span(spans, handler) or (path, line, line)
    named = _named(spans, path, handler, None if framework == 'node_http' else line)
    if named: return path, line if framework in DECORATED else named[0], named[1]      # a decorator's lines are the handler's
    return path, line, line if framework == 'node_http' else _inline_end(project.lines(path), line)


def _named(spans, path, handler, near):
    """The lines of the handler's own function in the file, or None."""
    return spans.of(path, handler.split('.')[-1], near=near) if handler else None


def _django_span(spans, handler):
    name = handler.split('.')[-2] if handler.endswith('.as_view') else handler.split('.')[-1]
    found = sorted(spans.named.get(name) or [], key=lambda item: ('views' not in item[0], item[0]))
    return (found[0][0], *found[0][1]) if found else None


def _text(project, path, first, last):
    return guards.code('\n'.join(project.lines(path)[first - 1:last]), project.language(path))


def _file_guard(project, path, line):
    """A guard the file applies to every route declared after it, or one the app wraps around every route."""
    before = '\n'.join(project.lines(path)[:max(line - 1, 0)])
    match = FILE_GUARD.search(guards.code(before, project.language(path))) or APP_GUARD.search(project.text(path))
    return match.group(0).strip()[:60] if match else None


def _in_docstring(project, fact):
    """Whether a Python route the detector read sits inside a docstring (an example written in the documentation)."""
    path, line = fact['location']['path'], fact['location'].get('start_line') or 1
    return project.language(path) == 'python' and '\n'.join(project.lines(path)[:line - 1]).count('"""') % 2 == 1


def next_middleware(project):
    """(guard words, [matcher patterns]) of Next.js's middleware when it checks a session, else (None, [])."""
    for name in NEXT_MIDDLEWARE:
        text = project.text(name)
        if not text: continue
        said = guards.AUTHENTICATION.search(text) or re.search(r'\bauth\s+as\s+middleware\b|updateSession|withAuth|clerkMiddleware', text)
        if said:
            matcher = MATCHER.search(text)
            return said.group(0), re.findall(r'''['"`]([^'"`]+)['"`]''', matcher.group('list')) if matcher else []
    return None, []


def _matched(route, patterns):
    if not patterns: return True
    for pattern in patterns:
        try:
            if re.fullmatch(pattern.replace('/:path*', '(/.*)?'), route) or fnmatch(route, pattern): return True
        except re.error:
            continue
    return False


def _stores(project, path):
    return set(STORE.findall(project.text(path)))


def _data(project, path, first, last, text):
    """The tables and in-memory stores the handler reaches."""
    tables = {f['value']['target'] for f in project.facts('entrypoints', 'data_access')
              if f['location']['path'] == path and first <= (f['location'].get('start_line') or 0) <= last and f['value'].get('target')}
    stores = {name for name in _stores(project, path) if re.search(r'\b' + re.escape(name) + r'\b', text)}
    return sorted(map(str, tables | stores))


def _route_guard(value, route_line, middleware):
    """What the route's declaration or Next.js's middleware says of the sign-in, before the handler's own text."""
    if value['framework'] in ('nextjs', 'nextjs_action') and middleware[0]:
        route = value['route'] if value['framework'] == 'nextjs' else '/'
        if _matched('/api' + route if value['framework'] == 'nextjs' and not route.startswith('/api') else route, middleware[1]):
            return f"Next.js middleware ({middleware[0]})"
    said = guards.AUTHENTICATION.search(route_line)
    return said.group(0) if said else None


def _route_line(project, where):
    lines, index = project.lines(where['path']), (where.get('start_line') or 1) - 1
    return lines[index] if 0 <= index < len(lines) else ''


def _authentication(project, fact, said, route_line, middleware):
    """Who is signed in, by what says it first: the route or the middleware, the file's guard, the handler's own text, or the
    request's own token handed to the database."""
    where = fact['location']
    return (_route_guard(fact['value'], route_line, middleware) or _file_guard(project, where['path'], where.get('start_line') or 1)
            or said['authentication'] or (said['user_client'] and "the request's own token, to the database"))


def _writes(method, framework, text):
    """A write: a writing method (a server action only when its code writes), or any method whose code writes."""
    if method in WRITE_METHODS: return framework != 'nextjs_action' or bool(WRITE_TEXT.search(text))
    return method == 'ANY' and bool(WRITE_TEXT.search(text))


def row(project, spans, fact, middleware):
    value, where = fact['value'], fact['location']
    path, first, last = _span(project, spans, fact)
    text, route_line = _text(project, path, first, last), _route_line(project, where)
    said, method = guards.read(text), value.get('http_method') or 'ANY'
    return {'method': method, 'route': value['route'], 'path': path, 'line': first, 'end': last, 'declared_at': [where['path'], where.get('start_line')],
            'handler': value.get('handler'), 'framework': value['framework'],
            'authentication': _authentication(project, fact, said, route_line, middleware),
            'authorisation': said['authorisation'] or (said['user_client'] and 'row-level security'),
            'validation': said['validation'] or _file_validation(project, where['path']), 'signature': said['signature'],
            'service_key': said['service_client'], 'data': _data(project, path, first, last, text), 'writes': _writes(method, value['framework'], text),
            'by_id': bool(PARAM.search(str(value['route']))), 'public': guards.public(value['route']),
            'unknown_guards': guards.unknown_middleware(route_line), 'empty': not text.strip() or _empty_body(text)}


def _empty_body(text):
    body = text.split('{', 1)[1] if '{' in text else text
    return not re.sub(r'[\s{}();]', '', body)


def _file_validation(project, path):
    return 'OpenApiValidator' if 'OpenApiValidator' in project.text(path) else None


def table(project):
    """The endpoint table: one row per HTTP endpoint the entry-point facts name, tests left out."""
    spans, middleware = Spans(project), next_middleware(project)
    facts = [f for f in project.facts('entrypoints', 'entry_point') if f['value'].get('surface') == 'http'
             and f['value'].get('category') != 'test' and f['value'].get('http_method') != 'MOUNT' and f['location']['path'] not in project.tests]
    return [row(project, spans, fact, middleware) for fact in facts if not _in_docstring(project, fact)]


def _guarded(row):
    return bool(row['authentication'] or row['signature'])


def _question(row, names):
    listed = ', '.join(names)
    return {'boundary': 'endpoints', 'path': row['path'], 'line': row['line'],
            'question': f"{row['method']} {row['route']} writes, and its route passes {listed} before the handler: does it "
                        'check who is signed in?',
            'question_ar': f"{row['method']} {row['route']} يكتب، ومساره يمرّ على {listed} قبل المعالج: هل يتحقق ممن سجّل الدخول؟"}


def _finding(rule, row, **params):
    return {'rule': rule, 'path': row['path'], 'line': row['line'], 'evidence': f"{row['framework']} {row['method']} {row['route']}",
            'params': {'method': row['method'], 'route': row['route'], 'path': row['path'], **params}}


def _unguarded_write(row):
    if not row['writes'] or _guarded(row): return None
    return ('question', row['unknown_guards']) if row['unknown_guards'] else ('finding', 'unguarded-write', {})


def _unowned(row):
    if not (row['by_id'] and row['authentication'] and row['data']) or row['authorisation']: return None
    return 'finding', 'unowned-row', {'verb': 'changes' if row['writes'] else 'returns'}


def _private_read(row, guarded_data):
    exposed = sorted(set(row['data']) & guarded_data)
    if row['writes'] or _guarded(row) or row['authorisation'] or not exposed: return None
    return 'finding', 'unguarded-private-read', {'data': ', '.join(exposed)}


def _judge(row, guarded_data):
    """('finding', rule, params) or ('question', names) or None for one endpoint."""
    if row['empty'] or row['public']: return None
    return _unguarded_write(row) or _unowned(row) or _private_read(row, guarded_data)


def judged(rows):
    """(findings, questions) of the endpoint table: a write nobody signs in for, a row by its id with no owner check, and
    a read that hands anyone data other endpoints guard. A handler with no code (commented out) is left alone."""
    guarded_data = {name for row in rows if _guarded(row) or row['authorisation'] for name in row['data']}
    findings, questions = [], []
    for row in rows:
        verdict = _judge(row, guarded_data) or ('',)
        if verdict[0] == 'finding': findings.append(_finding(verdict[1], row, **verdict[2]))
        if verdict[0] == 'question': questions.append(_question(row, verdict[1]))
    return findings, questions
