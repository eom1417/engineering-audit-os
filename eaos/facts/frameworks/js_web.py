"""Express, Fastify, Koa and Next.js route surfaces."""
import re

LANGUAGES = ('javascript', 'typescript', 'tsx')
ROUTE = re.compile(r'\b(?P<object>app|router|server|fastify)\.(?P<method>get|post|put|patch|delete|all|use)\(\s*(?P<quote>[\'"`])(?P<route>[^\'"`]*)(?P=quote)\s*,\s*(?P<handler>[\w.]+)?', re.M)
NEXT_HANDLER = re.compile(r'export\s+(?:default\s+)?(?:async\s+)?function\s+(?P<name>\w+)', re.M)
NEXT_METHOD = re.compile(r'export\s+(?:async\s+)?function\s+(?P<method>GET|POST|PUT|PATCH|DELETE)\s*\(', re.M)


def detect(context):
    found = []
    for match in ROUTE.finditer(context.text):
        line = context.line_of(match.start())
        handler = match.group('handler')
        if handler in {'async', 'function', 'await', 'new'}: handler = None
        found.append({'surface': 'http', 'route': match.group('route'), 'http_method': match.group('method').upper(),
                      'handler': handler or context.symbol_at(line), 'framework': 'express_like', 'line': line})
    if re.search(r'(^|/)(pages/api|app)/', context.rel) and re.search(r'/route\.(t|j)sx?$|pages/api/', context.rel):
        route = '/' + context.rel.split('pages/api/')[-1].split('app/')[-1].rsplit('.', 1)[0].removesuffix('/route')
        methods = [m.group('method') for m in NEXT_METHOD.finditer(context.text)]
        for method in methods or ['ANY']:
            handler = method if methods else (NEXT_HANDLER.search(context.text).group('name') if NEXT_HANDLER.search(context.text) else None)
            found.append({'surface': 'http', 'route': route, 'http_method': method, 'handler': handler,
                          'framework': 'nextjs', 'line': 1})
    return found
