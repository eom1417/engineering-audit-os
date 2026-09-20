"""Flask, FastAPI and Django URL entry points."""
import re

LANGUAGES = ('python',)
DECORATOR = re.compile(r'^\s*@(?P<object>[\w.]+)\.(?P<method>get|post|put|patch|delete|head|options|route|websocket)\(\s*(?P<quote>[\'"])(?P<route>[^\'"]*)(?P=quote)(?P<rest>[^\n]*)', re.M)
DJANGO = re.compile(r'^\s*(?:re_)?path\(\s*(?P<quote>[\'"])(?P<route>[^\'"]*)(?P=quote)\s*,\s*(?P<handler>[\w.]+)', re.M)
METHODS = re.compile(r'methods\s*=\s*\[([^\]]*)\]')


def detect(context):
    found = []
    for match in DECORATOR.finditer(context.text):
        line = context.line_of(match.start())
        verb = match.group('method').upper()
        declared = METHODS.search(match.group('rest') or '')
        methods = [v.strip(' \'"').upper() for v in declared.group(1).split(',') if v.strip()] if declared else ([verb] if verb != 'ROUTE' else ['GET'])
        framework = 'fastapi' if 'router' in match.group('object').lower() or 'websocket' in match.group('method') else 'flask_or_fastapi'
        for method in methods:
            found.append({'surface': 'http', 'route': match.group('route'), 'http_method': method,
                          'handler': context.symbol_after(line), 'framework': framework, 'line': line})
    if context.rel.endswith('urls.py'):
        for match in DJANGO.finditer(context.text):
            line = context.line_of(match.start())
            found.append({'surface': 'http', 'route': match.group('route'), 'http_method': 'ANY',
                          'handler': match.group('handler'), 'framework': 'django', 'line': line})
    return found
