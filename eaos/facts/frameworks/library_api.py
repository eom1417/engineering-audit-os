"""The public surface of a library: what a consumer can call without reading the internals."""
import re

LANGUAGES = ('python', 'javascript', 'typescript', 'tsx')
FILENAMES = ('__init__.py', 'index.js', 'index.ts')
PY_ALL = re.compile(r'__all__\s*=\s*\[(?P<body>[^\]]*)\]', re.S)
PY_REEXPORT = re.compile(r'^[ \t]*from\s+(?!__future__)(?P<module>[.\w]+)\s+import\s+(?P<names>[^\n(]+)$', re.M)
JS_EXPORT = re.compile(r'^[ \t]*export\s+(?:const|function|class|default)\s+(?P<name>\w+)', re.M)
JS_REEXPORT = re.compile(r'^[ \t]*export\s*\{(?P<names>[^}]*)\}', re.M)


SOURCE_ROOTS = {'src', 'lib', 'app', 'packages'}


def top_level(rel):
    """Only a package a consumer can import directly counts as a public surface."""
    parts = rel.split('/')
    if len(parts) <= 2: return True
    return len(parts) == 3 and parts[0] in SOURCE_ROOTS


def _listed(context, match, group):
    """(name, line) of each comma-separated name in a match's group."""
    line = context.line_of(match.start())
    return [(entry, line) for entry in match.group(group).split(',')]


def _python_names(context):
    """The names `__all__` declares, else every name the package re-exports."""
    declared = PY_ALL.search(context.text)
    if declared: return _listed(context, declared, 'body')
    return [pair for match in PY_REEXPORT.finditer(context.text) for pair in _listed(context, match, 'names')]


def _js_names(context):
    """The names the index exports itself, then the names it re-exports."""
    return ([(match.group('name'), context.line_of(match.start())) for match in JS_EXPORT.finditer(context.text)]
            + [pair for match in JS_REEXPORT.finditer(context.text) for pair in _listed(context, match, 'names')])


def _public(pairs):
    """An entry point per public name, each once: no private name, nothing that is not an identifier."""
    found, seen = [], set()
    for symbol, line in pairs:
        symbol = symbol.strip().strip('\'"').split(' as ')[-1].strip()
        if not symbol or symbol in seen or symbol.startswith('_') or not symbol.replace('*', 'x').isidentifier(): continue
        seen.add(symbol)
        found.append({'surface': 'library', 'route': symbol, 'http_method': None, 'handler': symbol,
                      'framework': 'public_api', 'line': line})
    return found


def detect(context):
    name = context.rel.split('/')[-1]
    if name not in FILENAMES or not top_level(context.rel): return []
    return _public(_python_names(context) if name == '__init__.py' else _js_names(context))[:60]
