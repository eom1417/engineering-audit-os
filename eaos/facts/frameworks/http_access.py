"""Detect calls from a web front end to its own HTTP back end, as data access by endpoint.

Supabase is one way a vibe-coded front end reaches its data; the other is its own API through an HTTP
client: `api.get("/vehicles")`, where `api = axios.create({ baseURL: import.meta.env.VITE_API_URL })`,
or `fetch(`${API_URL}/ai/ask`)`. The endpoint and the method are what a feature reads and writes.

Only calls whose receiver is a known HTTP client are reported: `axios` itself, a name made by
`axios.create`, `ky.create` or `ofetch.create`, or a name imported from a file that makes one. A
`fetch` counts only when its URL starts with `/` or with an interpolated base (`${API_URL}`), so
calls to third-party hosts with a literal domain stay integration targets, not the app's own data.
"""
import re

LANGUAGES = ('javascript', 'typescript', 'tsx')
FACT_KIND = 'data_access'

FACTORY = re.compile(r'''\b([A-Za-z_$][\w$]*)\s*=\s*(?:axios|ky|ofetch)\.create\s*\(''')
IMPORT = re.compile(r'''\bimport\s*(?:type\s+)?(?:([A-Za-z_$][\w$]*)\s*,?\s*)?(?:\{([^}]*)\})?\s*from\s*['"]([^'"]+)['"]''')
METHOD_CALL = re.compile(r'''\b([A-Za-z_$][\w$]*)\s*\.\s*(get|post|put|patch|delete)\s*(?:<[^>()]*>)?\s*\(\s*(['"`])([^'"`]*)\3?''')
METHOD_CALL_BY_NAME = re.compile(r'''\b([A-Za-z_$][\w$]*)\s*\.\s*(get|post|put|patch|delete)\s*(?:<[^>()]*>)?\s*\(\s*([A-Za-z_$][\w$]*)\s*[,)]''')
FETCH_CALL = re.compile(r'''\bfetch\s*\(\s*(['"`])((?:/|\$\{)[^'"`]*)''')
FETCH_METHOD = re.compile(r'''method\s*:\s*['"](GET|POST|PUT|PATCH|DELETE)['"]''', re.I)
INTERPOLATION = re.compile(r'\$\{[^}]*\}')
GENERIC_STEMS = {'index', 'types', 'utils', 'constants', 'config', 'helpers'}


def _stem(path):
    return path.rstrip('/').rsplit('/', 1)[-1].split('.')[0]


def clients(text, inherited=()):
    """HTTP client names this file can call: axios, factory results, and names it imports that are clients."""
    names = set(inherited) | set(FACTORY.findall(text))
    if re.search(r'''from\s*['"]axios['"]''', text): names.add('axios')
    return names


def prepare(texts):
    """{file: client names}. A name a file makes with axios.create reaches every file that imports it by name."""
    made = {rel: set(FACTORY.findall(text)) for rel, text in texts.items()}
    exported = {}
    for rel, names in made.items():
        if names and _stem(rel) not in GENERIC_STEMS: exported.setdefault(_stem(rel), set()).update(names)
    bound = {}
    for rel, text in texts.items():
        inherited = set()
        for default, listed, spec in IMPORT.findall(text):
            offered = exported.get(_stem(spec), set())
            names = {part.split(' as ')[0].strip() for part in listed.split(',') if part.strip()} | ({default} if default else set())
            for part in listed.split(','):
                original, _, alias = part.strip().partition(' as ')
                if original.strip() in offered: inherited.add((alias or original).strip())
            if default and offered: inherited.add(default)  # `import api from "@/lib/Api"`: the default export
        names = clients(text, inherited)
        if names: bound[rel] = names
    return bound


def endpoint(raw):
    """`/operators/${id}` -> `/operators/{}`; the interpolated base of a fetch URL is dropped."""
    path = INTERPOLATION.sub('{}', raw.split('?', 1)[0])
    if path.startswith('{}'): path = path[2:]
    path = '/' + path.lstrip('/')
    return path.rstrip('/') or '/'


def bounded(method, url):
    """A GET of one resource (`/operators/{}`) or with paging parameters is bounded; a collection GET is not
    known to be, since the server may page by default; writes are not the question."""
    if method != 'get': return None
    if re.search(r'[?&](?:limit|page|pageSize|per_page|take|top|size)=', url): return True
    return True if endpoint(url).endswith('/{}') else None


def _value_of(name, text, before):
    """The string last assigned to `name` before `before` (`const DRIVERS_ENDPOINT = "/drivers"`), or None."""
    found = None
    for match in re.finditer(r'\b' + re.escape(name) + r'''\s*=\s*(['"`])([^'"`]*)\1''', text[:before]):
        found = match.group(2)
    return found


def extract_calls(text, names=()):
    """Yield (offset, line, call_record) for every call to the app's own HTTP back end."""
    names = set(names) | clients(text)
    for match in METHOD_CALL.finditer(text):
        receiver, method, _, url = match.groups()
        # A literal absolute URL is a third-party host (an integration target), not the app's own back end.
        if receiver not in names or re.match(r'https?://', url): continue
        yield match.start(), text.count('\n', 0, match.start()) + 1, \
            {'client': 'http', 'target': endpoint(url), 'operation': method.lower(), 'symbol': receiver,
             'bounded': bounded(method.lower(), url)}
    for match in METHOD_CALL_BY_NAME.finditer(text):
        receiver, method, variable = match.groups()
        if receiver not in names: continue
        value = _value_of(variable, text, match.start())
        if value is not None and re.match(r'https?://', value): continue
        yield match.start(), text.count('\n', 0, match.start()) + 1, \
            {'client': 'http', 'target': endpoint(value) if value is not None else '{dynamic}', 'operation': method.lower(),
             'symbol': receiver, 'bounded': bounded(method.lower(), value or '')}
    for match in FETCH_CALL.finditer(text):
        window = text[match.end():match.end() + 300]
        method = FETCH_METHOD.search(window.split(');', 1)[0])
        yield match.start(), text.count('\n', 0, match.start()) + 1, \
            {'client': 'http', 'target': endpoint(match.group(2)), 'operation': (method.group(1) if method else 'get').lower(),
             'symbol': 'fetch'}


def detect(context):
    return extract_calls(context.text, context.prepared.get(__name__) or ())
