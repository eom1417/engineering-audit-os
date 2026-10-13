"""User-facing routes of single-page and file-routed web apps: React Router, TanStack Router, Next.js pages.

These are the surfaces a person actually reaches, and the ones an app built with Lovable, Bolt or v0
is made of. Server handlers declared on a TanStack file route are http surfaces; everything else here
is a page. Only a route written in the source is reported; one assembled at runtime is not guessed.

A React Router route nested in another is reported at its full path: a child <Route> inside its parent's tags, or a
route of a descendant <Routes> drawn inside the parent's element (``<Route path="/app/*" element={...<Routes>...}>``),
is joined to the parent's path, so ``/drivers`` under ``/app/*`` is the page ``/app/drivers`` a person opens. The path
as written stays in ``declared``.

A TanStack route built in code (``createRoute({ getParentRoute: () => parent, path: '/x', component: X })``) is
reported at its path joined to its parent's; with hash history (``createHashHistory``) it is served at ``/#/x``.
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
CODE_ROUTE = re.compile(r'''(?:\b(?:const|let|var)\s+(?P<var>\w+)\s*=\s*)?\bcreateRoute\s*\(\s*\{''')
OBJECT_PATH = re.compile(r'''\bpath\s*:\s*(?P<quote>['"`])(?P<route>[^'"`]*)(?P=quote)''')
OBJECT_PARENT = re.compile(r'''\bgetParentRoute\s*:\s*\(\)\s*=>\s*(?P<parent>\w+)''')
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
    _close(text, tags, events)
    return tags


def _close(text, tags, events):
    """Each open tag ends at the closing tag that pairs with it; one never closed holds the rest of the text."""
    events += [(m.start(), 'close', m.end()) for m in ROUTE_CLOSE.finditer(text)]
    stack = []
    for _, kind, item in sorted(events, key=lambda e: e[0]):
        if kind == 'open': stack.append(item)
        elif stack: stack.pop()['end'] = item
    for tag in tags:
        if tag['end'] is None: tag['end'] = len(text)


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
        tag['full'] = _full_of(tag, parent)
        out[tag['start']] = tag['full'] or '/'
    return out


def _full_of(tag, parent):
    """A route's full path: its own under no holder, else joined to its holder's (an absolute child path that already
    starts with the holder's is kept)."""
    path = tag['path']
    if parent is None: return path if path is not None else ''
    base = re.sub(r'/?\*$', '', parent['full'])
    if path is None: return base
    if tag['start'] < parent['open_end'] or not path.startswith('/'): return _join(base, path)
    return path if path.startswith(base.rstrip('/') + '/') or path == base else _join(base, path)


def detect(context):
    return [*_react_router(context), *_tanstack(context), *_tanstack_code(context), *_nextjs(context)]


def _react_router(context):
    """The pages of <Route> tags at their full path, then of route objects given to a router."""
    if not REACT_ROUTER.search(context.text): return []
    found = []
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
    return found


def _tanstack(context):
    """A TanStack file route: its server handlers as http surfaces, else the page it draws."""
    route = TANSTACK.search(context.text)
    if not (route and '@tanstack/' in context.text): return []
    path = route.group('route') if route.group('route') is not None else '__root__'
    methods = sorted({m.group('method') for m in SERVER_METHOD.finditer(context.text)}) if 'handlers' in context.text else []
    line = context.line_of(route.start())
    if methods:
        return [{'surface': 'http', 'route': path, 'http_method': method, 'handler': method,
                 'framework': 'tanstack_router', 'line': line} for method in methods]
    component = TANSTACK_COMPONENT.search(context.text) or FUNCTION.search(context.text)
    return [_page(context, route.start(), path, component and component.group('name'), 'tanstack_router')]


def _object_at(text, start):
    """The text of the object literal whose '{' is at `start`, to its matching '}'."""
    depth = 0
    for i in range(start, len(text)):
        depth += {'{': 1, '}': -1}.get(text[i], 0)
        if depth == 0: return text[start:i + 1]
    return text[start:]


def _tanstack_code(context):
    """The pages of TanStack routes built in code, each at its full path (its parent's path joined in)."""
    if '@tanstack/' not in context.text or 'createRoute(' not in context.text: return []
    prefix = '/#' if 'createHashHistory' in context.text else ''
    paths, found = {}, []
    for match in CODE_ROUTE.finditer(context.text):
        body = _object_at(context.text, match.end() - 1)
        declared, parent = OBJECT_PATH.search(body), OBJECT_PARENT.search(body)
        if not declared: continue
        path = _join(paths.get(parent.group('parent'), '/') if parent else '/', declared.group('route'))
        if match.group('var'): paths[match.group('var')] = path
        component = TANSTACK_COMPONENT.search(body)
        page = _page(context, match.start(), prefix + path, component and component.group('name'), 'tanstack_router')
        if page['route'] != declared.group('route'): page['declared'] = declared.group('route')
        found.append(page)
    return found


def _nextjs(context):
    """A Next.js page file: its route from its place under app/ or pages/."""
    page = NEXT_PAGE.search(context.rel)
    if not (page and (page.group('app') is not None or NEXT_MARK.search(context.text))): return []
    segment = page.group('app') if page.group('app') is not None else page.group('pages')
    path = '/' + re.sub(r'(^|/)index$', '', (segment or '').rstrip('/'))
    component = re.search(r'export\s+default\s+(?:async\s+)?function\s+(?P<name>\w+)', context.text)
    return [_page(context, 0, path, component and component.group('name'), 'nextjs')]


def _page(context, offset, route, handler, framework):
    line = context.line_of(offset)
    return {'surface': 'page', 'route': route, 'http_method': None, 'handler': handler or context.symbol_at(line),
            'framework': framework, 'line': line}
