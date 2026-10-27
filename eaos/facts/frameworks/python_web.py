"""Flask, FastAPI, Starlette and Django URL entry points."""
import re

LANGUAGES = ('python',)
DECORATOR = re.compile(r'^[ \t]*@(?P<object>[\w.]+)\.(?P<method>get|post|put|patch|delete|head|options|route|websocket)\(\s*(?P<quote>[\'"])(?P<route>[^\'"]*)(?P=quote)(?P<rest>[^\n]*)', re.M)
DJANGO = re.compile(r'^[ \t]*(?:re_)?path\(\s*(?P<quote>[\'"])(?P<route>[^\'"]*)(?P=quote)\s*,\s*(?P<handler>[\w.]+)', re.M)
METHODS = re.compile(r'methods\s*=\s*\[([^\]]*)\]')
# a Blueprint or an APIRouter given its prefix where it is made: its routes are under it (flaskr's /auth/register was
# read as /register, and a repair stopped on a page that is not there, 2026-10-27)
PREFIXED = re.compile(r'''^[ \t]*(?P<object>\w+)\s*=\s*(?:\w+\.)?(?:Blueprint|APIRouter)\((?P<args>[^)]*)\)''', re.M)
PREFIX = re.compile(r'''\b(?:url_)?prefix\s*=\s*(?P<quote>['"])(?P<prefix>/[^'"]*)(?P=quote)''')
STARLETTE = re.compile(r'''\bRoute\(\s*(?P<quote>['"])(?P<route>/[^'"]*)(?P=quote)\s*,\s*(?P<handler>[\w.]+)(?P<rest>[^)\n]*)''')


def detect(context):
    found = _decorated(context)
    if 'starlette' in context.text: found += _starlette(context)
    if context.rel.endswith('urls.py'): found += _django(context)
    return found


def _methods(rest, default):
    declared = METHODS.search(rest or '')
    return [v.strip(' \'"').upper() for v in declared.group(1).split(',') if v.strip()] if declared else default


def _prefixes(text):
    """{object name: the prefix it was made with}."""
    return {m.group('object'): p.group('prefix').rstrip('/') for m in PREFIXED.finditer(text) if (p := PREFIX.search(m.group('args')))}


def _decorated(context):
    found, prefixes = [], _prefixes(context.text)
    for match in DECORATOR.finditer(context.text):
        line = context.line_of(match.start())
        verb = match.group('method').upper()
        methods = _methods(match.group('rest'), [verb] if verb != 'ROUTE' else ['GET'])
        framework = 'fastapi' if 'router' in match.group('object').lower() or 'websocket' in match.group('method') else 'flask_or_fastapi'
        route = prefixes.get(match.group('object'), '') + match.group('route')
        found += [{'surface': 'http', 'route': route, 'http_method': method,
                   'handler': context.symbol_after(line), 'framework': framework, 'line': line} for method in methods]
    return found


def _starlette(context):
    return [{'surface': 'http', 'route': match.group('route'), 'http_method': method, 'handler': match.group('handler'),
             'framework': 'starlette', 'line': context.line_of(match.start())}
            for match in STARLETTE.finditer(context.text) for method in _methods(match.group('rest'), ['GET'])]


def _django(context):
    return [{'surface': 'http', 'route': match.group('route'), 'http_method': 'ANY', 'handler': match.group('handler'),
             'framework': 'django', 'line': context.line_of(match.start())} for match in DJANGO.finditer(context.text)]
