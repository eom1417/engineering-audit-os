"""User-facing routes of single-page and file-routed web apps: React Router, TanStack Router, Next.js pages.

These are the surfaces a person actually reaches, and the ones an app built with Lovable, Bolt or v0
is made of. Server handlers declared on a TanStack file route are http surfaces; everything else here
is a page. Only a route written in the source is reported; one assembled at runtime is not guessed.
"""
import re

LANGUAGES = ('javascript', 'typescript', 'tsx')
REACT_ROUTER = re.compile(r'''from\s+['"]react-router(?:-dom)?['"]''')
JSX_ROUTE = re.compile(r'''<Route\b(?P<attributes>[^>]*?\bpath\s*=\s*(?:\{\s*)?(?P<quote>['"`])(?P<route>[^'"`]*)(?P=quote)[^>]*)>''', re.S)
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


def detect(context):
    found = []
    if REACT_ROUTER.search(context.text):
        for match in JSX_ROUTE.finditer(context.text):
            element = ELEMENT.search(match.group('attributes'))
            found.append(_page(context, match.start(), match.group('route'), element and element.group('name'), 'react_router'))
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
