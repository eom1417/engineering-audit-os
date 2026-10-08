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
NEXT_ARGUMENT = re.compile(r'''['"`]?\s*,\s*''')
FETCH_BODY = re.compile(r'''\bbody\s*:\s*JSON\.stringify\s*\(\s*''')
PROPERTY = re.compile(r'''\s*(?:(?P<spread>\.\.\.)|(?P<q>['"])(?P<quoted>[^'"\n]+)(?P=q)|(?P<name>[A-Za-z_$][\w$]*))''')
WRITES = ('post', 'put', 'patch')
SCAN = 4000  # characters an object literal may span before it is left unread
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


def object_keys(text, start):
    """The top-level keys of the object literal opening at text[start] (`{ name, plate: p, 'vin': v }` -> name, plate,
    vin), sorted; None when no literal opens there or it does not close within SCAN characters. A spread (`...rest`)
    hides keys, so the keys come back with `partial` true. Request keys are the payload's names, never its values."""
    if start >= len(text) or text[start] != '{': return None
    keys, partial, depth, i, end = set(), False, 0, start, min(len(text), start + SCAN)
    expect = True  # at the start of a property
    while i < end:
        ch = text[i]
        if ch in '\'"`':
            close = text.find(ch, i + 1)
            while close != -1 and text[close - 1] == '\\': close = text.find(ch, close + 1)
            if close == -1: return None
            if depth == 1 and expect:
                after = text[close + 1:close + 40].lstrip()
                if after[:1] == ':' and ch != '`': keys.add(text[i + 1:close])
                expect = False
            i = close + 1
            continue
        if ch in '{([':
            if depth == 1 and expect and ch == '[': partial = True  # a computed key: its name is known at run time
            depth += 1
            if depth == 1: expect = True
        elif ch in '})]':
            depth -= 1
            if depth == 0: return {'keys': sorted(keys), 'partial': partial}
        elif depth == 1 and ch == ',': expect = True
        elif depth == 1 and expect and not ch.isspace():
            found = PROPERTY.match(text, i)
            if found and found.group('spread'): partial = True
            elif found and found.group('name'):
                after = text[found.end():found.end() + 2].lstrip()[:1]
                if after in (':', ',', '}', '(', ''): keys.add(found.group('name'))
            expect = False
            if found and found.group('name'): i = found.end(); continue
        i += 1
    return None


def payload(text, after):
    """The keys of the object literal passed as the next argument after `after` (the end of the URL argument), or
    None when the payload is a variable, a call, or absent: the keys are then unknown, not empty."""
    found = NEXT_ARGUMENT.match(text, after)
    return object_keys(text, found.end()) if found else None


def _with_keys(record, found):
    if found is not None: record.update(keys=found['keys'], keys_partial=found['partial'])
    return record


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
        yield match.start(), text.count('\n', 0, match.start()) + 1, _with_keys(
            {'client': 'http', 'target': endpoint(url), 'operation': method.lower(), 'symbol': receiver,
             'bounded': bounded(method.lower(), url)}, payload(text, match.end()) if method.lower() in WRITES else None)
    for match in METHOD_CALL_BY_NAME.finditer(text):
        receiver, method, variable = match.groups()
        if receiver not in names: continue
        value = _value_of(variable, text, match.start())
        if value is not None and re.match(r'https?://', value): continue
        yield match.start(), text.count('\n', 0, match.start()) + 1, _with_keys(
            {'client': 'http', 'target': endpoint(value) if value is not None else '{dynamic}', 'operation': method.lower(),
             'symbol': receiver, 'bounded': bounded(method.lower(), value or '')},
            payload(text, match.end() - 1) if method.lower() in WRITES else None)
    for match in FETCH_CALL.finditer(text):
        window = text[match.end():match.end() + 300]
        method = FETCH_METHOD.search(window.split(');', 1)[0])
        operation = (method.group(1) if method else 'get').lower()
        following = text.find('fetch(', match.end())
        body = FETCH_BODY.search(text, match.end(), min(match.end() + 600, following if following != -1 else len(text))) \
            if operation in WRITES else None
        yield match.start(), text.count('\n', 0, match.start()) + 1, _with_keys(
            {'client': 'http', 'target': endpoint(match.group(2)), 'operation': operation, 'symbol': 'fetch'},
            object_keys(text, body.end()) if body else None)


def detect(context):
    return extract_calls(context.text, context.prepared.get(__name__) or ())
