"""Endpoints the framework detectors do not name: a Node server written on node:http alone, Next.js server actions and
Supabase edge functions. Each is a way into the program a person's browser reaches (M6.4)."""
import re

LANGUAGES = ('javascript', 'typescript', 'tsx')
NODE_SERVER = re.compile(r'\b(?:http|https)\.createServer\s*\(|\bcreateServer\s*\(')
# `if (url.pathname === '/api/x' && req.method === 'POST') return handler(req, res);`, or `.startsWith('/api/x/')`: a route
# followed by the rest of its path, a parameter.
PATHNAME = re.compile(r'''\b(?:url\.pathname|pathname|req\.url|request\.url)\s*(?:===?\s*(?P<q>['"`])(?P<route>/[^'"`]*)(?P=q)'''
                      r'''|\.startsWith\(\s*(?P<p>['"`])(?P<prefix>/[^'"`]*)(?P=p)\s*\))''')
METHOD = re.compile(r'''\b(?:req|request)\.method\s*===?\s*['"`](?P<method>GET|POST|PUT|PATCH|DELETE)['"`]''')
CALLED = re.compile(r'\breturn\s+(?:await\s+)?(?P<name>[A-Za-z_$][\w$]*)\s*\(\s*(?:req|request)\b')
ACTION = re.compile(r'^export\s+(?:default\s+)?async\s+function\s+(?P<name>\w+)\s*\(', re.M)
EDGE = re.compile(r'(?:^|/)supabase/functions/(?P<name>[\w-]+)/index\.(?:ts|js)$')
EDGE_SERVE = re.compile(r'\b(?:Deno\.serve|serve)\s*\(')


def _node_routes(context):
    if not NODE_SERVER.search(context.text): return []
    found = []
    for number, line in enumerate(context.text.split('\n'), start=1):
        match = PATHNAME.search(line)
        if not match: continue
        route = match.group('route') or match.group('prefix').rstrip('/') + '/:id'
        method = METHOD.search(line)
        called = CALLED.search(line[match.end():])
        found.append({'surface': 'http', 'route': route, 'http_method': method.group('method') if method else 'ANY',
                      'handler': called.group('name') if called else None, 'framework': 'node_http',
                      'line': number})
    return found


def directive(text):
    """The file's 'use client' or 'use server' directive ('client', 'server'), read after its leading comments; or None."""
    rest = text.lstrip()
    while rest.startswith(('//', '/*')):
        end = rest.find('\n') if rest.startswith('//') else rest.find('*/') + 1
        if end <= 0: return None
        rest = rest[end + 1:].lstrip()
    for kind in ('client', 'server'):
        if rest.startswith((f"'use {kind}'", f'"use {kind}"')): return kind
    return None


def _server_actions(context):
    """Every exported async function of a 'use server' file is an action the browser calls with a POST."""
    if directive(context.text) != 'server': return []
    return [{'surface': 'http', 'route': f"action:{match.group('name')}", 'http_method': 'POST', 'handler': match.group('name'),
             'framework': 'nextjs_action', 'line': context.line_of(match.start())} for match in ACTION.finditer(context.text)]


def _edge_function(context):
    match = EDGE.search(context.rel)
    if not match or not EDGE_SERVE.search(context.text): return []
    line = context.line_of(EDGE_SERVE.search(context.text).start())
    return [{'surface': 'http', 'route': f"/functions/v1/{match.group('name')}", 'http_method': 'ANY', 'handler': match.group('name'),
             'framework': 'supabase_edge', 'line': line}]


def detect(context):
    return _node_routes(context) + _server_actions(context) + _edge_function(context)
