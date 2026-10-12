"""Express, Fastify, Koa and Next.js route surfaces."""
import re

LANGUAGES = ('javascript', 'typescript', 'tsx')
# `route` is Hono's mount (app.route('/api/admin', adminRouter)): a whole group of endpoints under one path.
ROUTE = re.compile(r'\b(?P<object>app|router|server|fastify|api|hono)\.(?P<method>get|post|put|patch|delete|all|use|route)\(\s*(?P<quote>[\'"`])(?P<route>[^\'"`]*)(?P=quote)\s*,\s*(?P<handler>[\w.]+)?', re.M)
# `api.get('/x', …)` is a server route only where a server framework is in the file; in the browser it is an axios call.
SERVER_FILE = re.compile(r'''from\s+['"](?:hono|express|fastify|koa|@hono/[\w-]+)['"]|require\(\s*['"](?:express|fastify|koa|hono)['"]\s*\)|new\s+Hono\b''')
NEXT_HANDLER = re.compile(r'export\s+(?:default\s+)?(?:async\s+)?function\s+(?P<name>\w+)', re.M)
NEXT_METHOD = re.compile(r'export\s+(?:async\s+)?function\s+(?P<method>GET|POST|PUT|PATCH|DELETE)\s*\(', re.M)


def _express_route(context, match):
    """One `app.get('/x', handler)`: its method (MOUNT for Hono's route) and its handler, else the enclosing symbol."""
    line = context.line_of(match.start())
    handler = match.group('handler')
    if handler in {'async', 'function', 'await', 'new'}: handler = None
    method = 'MOUNT' if match.group('method') == 'route' else match.group('method').upper()
    return {'surface': 'http', 'route': match.group('route'), 'http_method': method,
            'handler': handler or context.symbol_at(line), 'framework': 'express_like', 'line': line}


def _express_routes(context):
    server_file = bool(SERVER_FILE.search(context.text))
    return [_express_route(context, match) for match in ROUTE.finditer(context.text)
            if server_file or match.group('object') not in ('api', 'hono')]


def _next_routes(context):
    """A Next.js API or route file: a route per exported method, else one for any method on its default handler."""
    if not (re.search(r'(^|/)(pages/api|app)/', context.rel) and re.search(r'/route\.(t|j)sx?$|pages/api/', context.rel)): return []
    route = '/' + context.rel.split('pages/api/')[-1].split('app/')[-1].rsplit('.', 1)[0].removesuffix('/route')
    methods = [m.group('method') for m in NEXT_METHOD.finditer(context.text)]
    named = NEXT_HANDLER.search(context.text)
    return [{'surface': 'http', 'route': route, 'http_method': method,
             'handler': method if methods else (named.group('name') if named else None), 'framework': 'nextjs', 'line': 1}
            for method in methods or ['ANY']]


def detect(context):
    return _express_routes(context) + _next_routes(context)
