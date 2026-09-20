"""The public surface of a library: what a consumer can call without reading the internals."""
import re

LANGUAGES = ('python', 'javascript', 'typescript', 'tsx')
FILENAMES = ('__init__.py', 'index.js', 'index.ts')
PY_ALL = re.compile(r'__all__\s*=\s*\[(?P<body>[^\]]*)\]', re.S)
PY_REEXPORT = re.compile(r'^\s*from\s+(?!__future__)(?P<module>[.\w]+)\s+import\s+(?P<names>[^\n(]+)$', re.M)
JS_EXPORT = re.compile(r'^\s*export\s+(?:const|function|class|default)\s+(?P<name>\w+)', re.M)
JS_REEXPORT = re.compile(r'^\s*export\s*\{(?P<names>[^}]*)\}', re.M)


SOURCE_ROOTS = {'src', 'lib', 'app', 'packages'}


def top_level(rel):
    """Only a package a consumer can import directly counts as a public surface."""
    parts = rel.split('/')
    if len(parts) <= 2: return True
    return len(parts) == 3 and parts[0] in SOURCE_ROOTS


def detect(context):
    name = context.rel.split('/')[-1]
    if name not in FILENAMES or not top_level(context.rel): return []
    found, seen = [], set()

    def add(symbol, line):
        symbol = symbol.strip().strip('\'"').split(' as ')[-1].strip()
        if not symbol or symbol in seen or symbol.startswith('_') or not symbol.replace('*', 'x').isidentifier(): return
        seen.add(symbol)
        found.append({'surface': 'library', 'route': symbol, 'http_method': None, 'handler': symbol,
                      'framework': 'public_api', 'line': line})

    if name == '__init__.py':
        declared = PY_ALL.search(context.text)
        if declared:
            line = context.line_of(declared.start())
            for entry in declared.group('body').split(','): add(entry, line)
        if not declared:
            for match in PY_REEXPORT.finditer(context.text):
                line = context.line_of(match.start())
                for entry in match.group('names').split(','): add(entry, line)
    else:
        for match in JS_EXPORT.finditer(context.text): add(match.group('name'), context.line_of(match.start()))
        for match in JS_REEXPORT.finditer(context.text):
            line = context.line_of(match.start())
            for entry in match.group('names').split(','): add(entry, line)
    return found[:60]
