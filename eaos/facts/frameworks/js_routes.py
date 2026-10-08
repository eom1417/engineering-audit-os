"""User-facing routes of single-page and file-routed web apps: React Router, TanStack Router, Next.js pages.

These are the surfaces a person actually reaches, and the ones an app built with Lovable, Bolt or v0
is made of. Server handlers declared on a TanStack file route are http surfaces; everything else here
is a page. Only a route written in the source is reported; one assembled at runtime is not guessed.

A React Router route nested in another is reported at its full path: a child <Route> inside its parent's tags, or a
route of a descendant <Routes> drawn inside the parent's element (``<Route path="/app/*" element={...<Routes>...}>``),
is joined to the parent's path, so ``/drivers`` under ``/app/*`` is the page ``/app/drivers`` a person opens. The path
as written stays in ``declared``.
"""
import re

LANGUAGES = ('javascript', 'typescript', 'tsx')
REACT_ROUTER = re.compile(r'''from\s+['"]react-router(?:-dom)?['"]''')
JSX_ROUTE = re.compile(r'''<Route\b(?P<attributes>[^>]*?\bpath\s*=\s*(?:\{\s*)?(?P<quote>['"`])(?P<route>[^'"`]*)(?P=quote)[^>]*)>''', re.S)
# A quote opens a string only after what can precede an expression; in JSX text ("Can't") it is a letter.
STRING_BEFORE = re.compile(r'(?:^|[=(\[{,:?+!&|]|\breturn)\s*\Z')
ROUTE_TAG = re.compile(r'<Route\b')
ROUTE_CLOSE = re.compile(r'</Route\s*>')
JSX_PATH = re.compile(r'''[^>]*?\bpath\s*=\s*(?:\{\s*)?(?P<quote>['"`])(?P<route>[^'"`]*)(?P=quote)''', re.S)
ELEMENT = re.compile(r'''\b(?:element\s*=\s*\{\s*<|Component\s*=\s*\{\s*)(?P<name>[A-Z]\w*)''')
OBJECT_ROUTE = re.compile(r'''\{\s*path\s*:\s*(?P<quote>['"`])(?P<route>[^'"`]*)(?P=quote)(?P<rest>[^{}]*)''', re.S)
OBJECT_ELEMENT = re.compile(r'''\b(?:element\s*:\s*<|Component\s*:\s*)(?P<name>[A-Z]\w*)''')
TANSTACK = re.compile(r'''\bcreate(?:File|Root|Server|API)Route(?:WithContext)?\s*(?:<[^>]*>)?\s*\(\s*(?:(?P<quote>['"`])(?P<route>[^'"`]*)(?P=quote))?''')
TANSTACK_COMPONENT = re.compile(r'''\bcomponent\s*:\s*(?P<name>[A-Z]\w*)''')
SERVER_METHOD = re.compile(r'''\b(?P<method>GET|POST|PUT|PATCH|DELETE)\s*:''')
FUNCTION = re.compile(r'''\bfunction\s+(?P<name>[A-Z]\w*)\s*\(''')
NEXT_PAGE = re.compile(r'''(^|/)(?:src/)?(?:app/(?P<app>(?:.*/)?)page|pages/(?P<pages>(?!api/)(?!_)[^.]+))\.(?:t|j)sx?$''')
# A Vite or CRA app also keeps screens under src/pages/; only Next.js gives that folder routing meaning.
NEXT_MARK = re.compile(r'''from\s+['"]next/|\bget(?:ServerSide|Static)Props\b''')


def _open_tag_end(text, start):
    """(end, self_closing) of the JSX tag opening at `start`: the first '>' outside braces and quotes."""
    depth, quote, i = 0, None, start + 1
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == '\\': i += 1
            elif ch == quote: quote = None
        elif ch in '\'"`' and (depth == 0 or STRING_BEFORE.search(text, start, i)): quote = ch
        elif ch == '{': depth += 1
        elif ch == '}': depth = max(depth - 1, 0)
        elif ch == '>' and depth == 0:
            return i + 1, text[start:i].rstrip().endswith('/')
        i += 1
    return len(text), True


def route_tags(text):
    """[{start, open_end, end, path}] of every <Route> tag, `end` closing its children (or its own tag)."""
    tags, events = [], []
    for match in ROUTE_TAG.finditer(text):
        open_end, closed = _open_tag_end(text, match.start())
        path = JSX_PATH.match(text, match.end(), open_end)
        tag = {'start': match.start(), 'open_end': open_end, 'end': open_end if closed else None,
               'path': path.group('route') if path else None}
        tags.append(tag)
        if not closed: events.append((match.start(), 'open', tag))
    events += [(m.start(), 'close', m.end()) for m in ROUTE_CLOSE.finditer(text)]
    stack = []
    for _, kind, item in sorted(events, key=lambda e: e[0]):
        if kind == 'open': stack.append(item)
        elif stack: stack.pop()['end'] = item
    for tag in tags:
        if tag['end'] is None: tag['end'] = len(text)
    return tags


def _join(base, child):
    joined = '/'.join(part for part in (base.rstrip('/'), child.lstrip('/')) if part)
    return '/' + joined.lstrip('/') if joined else '/'


def full_paths(text):
    """{offset of a <Route>: its full path}: each route joined to the routes that hold it."""
    tags = route_tags(text)
    out = {}
    for tag in sorted(tags, key=lambda t: t['start']):
        holders = [t for t in tags if t is not tag and t['start'] < tag['start'] < t['end']]
        parent = max(holders, key=lambda t: t['start']) if holders else None
        path = tag['path']
        if parent is None:
            tag['full'] = path if path is not None else ''
        else:
            base = re.sub(r'/?\*$', '', parent['full'])
            if path is None: tag['full'] = base
            elif tag['start'] < parent['open_end'] or not path.startswith('/'): tag['full'] = _join(base, path)
            else: tag['full'] = path if path.startswith(base.rstrip('/') + '/') or path == base else _join(base, path)
        out[tag['start']] = tag['full'] or '/'
    return out


def detect(context):
    found = []
    if REACT_ROUTER.search(context.text):
        full = full_paths(context.text)
        for match in JSX_ROUTE.finditer(context.text):
            element = ELEMENT.search(match.group('attributes'))
            declared = match.group('route')
            page = _page(context, match.start(), full.get(match.start(), declared), element and element.group('name'), 'react_router')
            if page['route'] != declared: page['declared'] = declared
            found.append(page)
        if re.search(r'\b(createBrowserRouter|createHashRouter|createMemoryRouter|useRoutes)\b', context.text):
            for match in OBJECT_ROUTE.finditer(context.text):
                element = OBJECT_ELEMENT.search(match.group('rest'))
                found.append(_page(context, match.start(), match.group('route'), element and element.group('name'), 'react_router'))
    route = TANSTACK.search(context.text)
    if route and '@tanstack/' in context.text:
        path = route.group('route') if route.group('route') is not None else '__root__'
        methods = sorted({m.group('method') for m in SERVER_METHOD.finditer(context.text)}) if 'handlers' in context.text else []
        line = context.line_of(route.start())
        for method in methods:
            found.append({'surface': 'http', 'route': path, 'http_method': method, 'handler': method,
                          'framework': 'tanstack_router', 'line': line})
        if not methods:
            component = TANSTACK_COMPONENT.search(context.text) or FUNCTION.search(context.text)
            found.append(_page(context, route.start(), path, component and component.group('name'), 'tanstack_router'))
    page = NEXT_PAGE.search(context.rel)
    if page and (page.group('app') is not None or NEXT_MARK.search(context.text)):
        segment = page.group('app') if page.group('app') is not None else page.group('pages')
        path = '/' + re.sub(r'(^|/)index$', '', (segment or '').rstrip('/'))
        component = re.search(r'export\s+default\s+(?:async\s+)?function\s+(?P<name>\w+)', context.text)
        found.append(_page(context, 0, path, component and component.group('name'), 'nextjs'))
    return found


def _page(context, offset, route, handler, framework):
    line = context.line_of(offset)
    return {'surface': 'page', 'route': route, 'http_method': None, 'handler': handler or context.symbol_at(line),
            'framework': framework, 'line': line}
