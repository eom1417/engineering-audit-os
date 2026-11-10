"""net/http, gorilla/mux, gin and chi route surfaces.

Gin's route groups give their routes a prefix: `v1 := r.Group("/api")` in a file, and a sub-group handed to a register
function (`users.Register(v1.Group("/users"))`, `func Register(router *gin.RouterGroup)`) in any file of the project,
followed by the function's name. A group built at runtime, or one passed on again from a register function, is not
followed: its routes keep the path as written.
"""
import re

from .js_mounts import join

LANGUAGES = ('go',)
HANDLE = re.compile(r'\b(?P<object>\w+)\.(?P<method>HandleFunc|Handle|GET|POST|PUT|PATCH|DELETE)'
                    r'\(\s*"(?P<route>[^"]*)"\s*,\s*(?P<handler>[\w.]+)?', re.M)
ROUTERS = {'http', 'mux', 'r', 'router', 'e', 'app'}
GROUP = re.compile(r'\b(?P<var>\w+)\s*:?=\s*(?P<parent>\w+)\.Group\(\s*"(?P<prefix>[^"]*)"')
PASSED = re.compile(r'\b(?P<func>\w+)\(\s*(?P<parent>\w+)(?:\.Group\(\s*"(?P<prefix>[^"]*)"\s*\))?\s*\)')
RECEIVES = re.compile(r'^func\s+(?P<func>\w+)\(\s*(?P<param>\w+)\s+\*gin\.RouterGroup\b', re.M)


def _strip_comments(text):
    """Strip Go line comments so the detector does not match example code in comments.

    Go has no block comments in the lexical sense (tree-sitter does, but the detector
    works on raw text); removing `// ...` lines is enough to drop every false positive
    that commented example code would give.
    """
    return '\n'.join('' if line.lstrip().startswith('//') else line for line in text.split('\n'))


def _groups(text):
    """{group variable: its prefix} of one file, a group made from another group of the file joined to its prefix."""
    found = {}
    for match in GROUP.finditer(text):
        found[match.group('var')] = join(found.get(match.group('parent'), ''), match.group('prefix'))
    return found


def prepare(texts):
    """{file: {'groups': {variable: prefix}, 'handed': {register function: [prefixes]}}}: each file's groups, and the
    prefixes the app's callers hand each register function the file declares."""
    cleaned = {rel: _strip_comments(text) for rel, text in texts.items()}
    groups = {rel: _groups(text) for rel, text in cleaned.items()}
    handed, out = _handed(cleaned, groups), {}
    for rel, text in cleaned.items():
        own = {m.group('func'): sorted(handed[m.group('func')])
               for m in RECEIVES.finditer(text) if m.group('func') in handed}
        if own or groups[rel]: out[rel] = {'groups': groups[rel], 'handed': own}
    return out


def _handed(cleaned, groups):
    """{function: the prefixes of the groups the app hands it}; a test's own router (a _test.go file) is not the
    app's."""
    handed = {}
    for rel, text in cleaned.items():
        for match in PASSED.finditer('' if rel.endswith('_test.go') else text):
            parent = groups[rel].get(match.group('parent'))
            if parent is None and match.group('prefix') is None: continue
            handed.setdefault(match.group('func'), set()).add(join(parent or '', match.group('prefix') or ''))
    return handed


def _prefixes(text, match, prepared):
    """The prefixes a route on `match`'s receiver is served under: the register function's when the receiver is the
    parameter of the function it is declared in, else its group's, else none."""
    receiver, start = match.group('object'), text.rfind('\nfunc ', 0, match.start()) + 1
    enclosing = RECEIVES.match(text, start) if start else None
    if enclosing and enclosing.group('param') == receiver:
        return prepared['handed'].get(enclosing.group('func')) or ['']
    group = prepared['groups'].get(receiver)
    return None if group is None and receiver not in ROUTERS else [group or '']


def detect(context):
    found = []
    cleaned = _strip_comments(context.text)
    prepared = context.prepared.get(__name__) or {'groups': {}, 'handed': {}}
    for match in HANDLE.finditer(cleaned):
        prefixes = _prefixes(cleaned, match, prepared)
        if prefixes is None: continue
        line = context.line_of(match.start())
        method = match.group('method')
        found += [{'surface': 'http', 'route': join(prefix, match.group('route')),
                   'http_method': 'ANY' if method in {'HandleFunc', 'Handle'} else method,
                   'handler': match.group('handler'), 'framework': 'go_http', 'line': line,
                   **({'declared': match.group('route')} if prefix else {})} for prefix in prefixes]
    return found
