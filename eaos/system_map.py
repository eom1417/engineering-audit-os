"""The system map of the report for people (eaos/human_report.py): every page, every API it calls, the server code
that answers it, what that code uses, and the data it reaches, end to end.

Reads only records the audit already wrote, and never raises for a missing or broken one (a missing piece is empty):
    facts/entrypoints.json  entry_point: a page (route, its component) or a server route; data_access: an HTTP call
                            the code makes (target URL, method), at the file that makes it
    features.json           features: their routes (surfaces), endpoints, files; what the feature filter groups by
    facts/flows.json        flow: a page and its call chain; the first caller is the page's component file
    facts/syntax.json       symbol: exported functions (a GET or POST export is a file-routed handler, a component's
                            name finds its file); import_edge: the packages a file imports (a database, email, ...)
    facts/graph.json        graph_node: the files each file imports
    facts/domain.json       data_table: a table, at the file that defines it
    target-architecture.json  current_components: the parts, which own the files

The five columns and how each link is found:
    page -> API        a data_access call in the page's own files: its component file, or a file in the component's
                       folder, that the component reaches by imports (three steps). A calling file that several
                       pages reach, or none, is drawn once in the first column as shared code, with its own links.
    API -> handler     a server route entry point with the same method and path (a :param matches any segment);
                       else file routing: a file exporting a function named after the method (GET, POST, ...),
                       whose path under routes/ or api/ spells the URL after /api (exactly, else word for word).
                       With neither, the handler is unknown and the page says so.
    handler -> module  the parts of the files the handler reaches by imports, three steps, not its own part; a file
                       that defines tables ends the walk. Its tables: those defined in the files two steps away.
    module -> data     the tables defined in the module's files; the services (a database driver, email, payments...)
                       the files it reaches import, by package name (SERVICES).
Read and written tables are not told apart: the facts say where a table is defined, not what each query does.
Test files are left out. The drawing is capped (MAX_*), and the caps are returned so that the page says so.
"""
import json
import re
from collections import defaultdict
from pathlib import Path

MAX_PAGES, MAX_CALLERS, MAX_APIS, MAX_HANDLERS, MAX_MODULES, MAX_DATA = 80, 24, 160, 120, 30, 60
METHODS = ('GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS')
ROUTE_ROOTS = ('routes', 'api', 'pages', 'handlers', 'endpoints', 'functions')
DEPTH = 3
TEST = re.compile(r'(^|/)(tests?|__tests__|e2e|spec|fixtures?)/|\.(test|spec)\.[a-z]+$|(^|/)test_[^/]*\.py$')
NOT_TABLES = {'if', 'not', 'exists', 'a', 't', 'the', 'this', 'that', 'table', 'select', 'from', 'where', 'as', 'on', 'x'}
# package -> (kind, English, Arabic): what a file importing it talks to
SERVICES = {
    'pg': ('storage', 'PostgreSQL database', 'قاعدة بيانات PostgreSQL'), 'postgres': ('storage', 'PostgreSQL database', 'قاعدة بيانات PostgreSQL'),
    'psycopg2': ('storage', 'PostgreSQL database', 'قاعدة بيانات PostgreSQL'), 'psycopg': ('storage', 'PostgreSQL database', 'قاعدة بيانات PostgreSQL'),
    'mysql': ('storage', 'MySQL database', 'قاعدة بيانات MySQL'), 'mysql2': ('storage', 'MySQL database', 'قاعدة بيانات MySQL'),
    'mongodb': ('storage', 'MongoDB database', 'قاعدة بيانات MongoDB'), 'mongoose': ('storage', 'MongoDB database', 'قاعدة بيانات MongoDB'),
    'redis': ('storage', 'Redis', 'Redis'), 'ioredis': ('storage', 'Redis', 'Redis'),
    'better-sqlite3': ('storage', 'SQLite database', 'قاعدة بيانات SQLite'), 'sqlite3': ('storage', 'SQLite database', 'قاعدة بيانات SQLite'),
    '@prisma/client': ('storage', 'database (Prisma)', 'قاعدة البيانات (Prisma)'), 'sqlalchemy': ('storage', 'database (SQLAlchemy)', 'قاعدة البيانات (SQLAlchemy)'),
    '@supabase/supabase-js': ('storage', 'Supabase', 'Supabase'), 'firebase-admin': ('storage', 'Firebase', 'Firebase'),
    '@aws-sdk/client-s3': ('storage', 'S3 file storage', 'تخزين ملفات S3'), 'boto3': ('service', 'AWS', 'AWS'),
    'node:fs': ('storage', 'server disk files', 'ملفات على قرص الخادم'), 'fs': ('storage', 'server disk files', 'ملفات على قرص الخادم'),
    'node:fs/promises': ('storage', 'server disk files', 'ملفات على قرص الخادم'), 'fs/promises': ('storage', 'server disk files', 'ملفات على قرص الخادم'),
    'stripe': ('service', 'Stripe payments', 'مدفوعات Stripe'), 'resend': ('service', 'Resend email', 'بريد Resend'),
    'nodemailer': ('service', 'email (SMTP)', 'بريد (SMTP)'), '@sendgrid/mail': ('service', 'SendGrid email', 'بريد SendGrid'),
    'twilio': ('service', 'Twilio SMS', 'رسائل Twilio'), 'openai': ('service', 'OpenAI', 'OpenAI'),
    '@anthropic-ai/sdk': ('service', 'Anthropic', 'Anthropic'), 'anthropic': ('service', 'Anthropic', 'Anthropic'),
    '@opentelemetry/sdk-node': ('service', 'OpenTelemetry export', 'قياسات OpenTelemetry'),
}


def _load(path, default):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


def _facts(report, name, *kinds):
    record = _load(Path(report) / 'facts' / f'{name}.json', {})
    rows = record.get('facts') if isinstance(record, dict) else None
    return [f for f in rows or [] if isinstance(f, dict) and f.get('kind') in kinds]


def _path(fact):
    return str((fact.get('location') or {}).get('path') or '')


def is_test(path):
    return bool(TEST.search(str(path)))


def clean_path(target):
    """The URL path of a call as the code wrote it: a template or query cut off ('/api/audit${before' -> '/api/audit')."""
    text = str(target or '').strip()
    for stop in ('${', '?', '#', '`', ' ', "'", '"', '{'):
        if stop in text: text = text[:text.index(stop)]
    return text.rstrip('/') or ('/' if text.startswith('/') else text)


def _segments(path):
    return ['*' if s[:1] in (':', '$', '[', '{', '*', '<') else s for s in str(path).strip('/').split('/') if s]


def same_route(a, b):
    """Two paths are one route when each segment is equal, or one of them is a parameter (:id, [id], {id}, $id)."""
    x, y = _segments(a), _segments(b)
    return len(x) == len(y) and all(p == q or '*' in (p, q) for p, q in zip(x, y))


def _words(text):
    return [w for w in re.split(r'[/\-_.]+', str(text).lower()) if w]


def api_group(path):
    """The resource an API belongs to: /api/users and /api/users/:id are both /api/users*."""
    parts = [s for s in str(path).split('/') if s]
    if not parts: return '/'
    if '://' in str(path): return '/'.join(str(path).split('/')[:3])
    head = 2 if parts[0] in ('api', 'v1', 'v2', 'rest') and len(parts) > 1 else 1
    if head == 2 and parts[1] in ('v1', 'v2', 'v3') and len(parts) > 2: head = 3
    return '/' + '/'.join(parts[:head])


def route_of_file(path):
    """(the URL words a file-routed handler answers, spelled as its path after routes/ or api/), or None."""
    parts = str(path).split('/')
    stem = re.sub(r'\.(ts|tsx|js|jsx|mjs|cjs|py)$', '', parts[-1])
    parts = parts[:-1] + [stem]
    roots = [i for i, p in enumerate(parts[:-1]) if p in ROUTE_ROOTS]
    rel = parts[roots[-1] + 1:] if roots else parts[-1:]
    while rel and rel[-1] in ('index', 'route', '+server', 'handler', '__init__'): rel = rel[:-1]
    return '/'.join(rel)


def _reach(start, imports, depth, stop=()):
    seen, front = {start}, [start]
    for _ in range(depth):
        front = [d for f in front if f not in stop or f == start for d in imports.get(f, ()) if d not in seen and not is_test(d)]
        seen.update(front)
    return seen


# ---------------------------------------------------------------- the records

def records(report):
    """Everything the map reads, from the report's records; each piece empty when its record is missing or broken."""
    report = Path(report)
    out = {'pages': [], 'routes': [], 'calls': [], 'features': [], 'flows': [], 'imports': {}, 'tables': defaultdict(set),
           'owner': {}, 'components': {}, 'methods': defaultdict(set), 'symbols': defaultdict(set), 'packages': defaultdict(set), 'root': ''}
    for fact in _facts(report, 'entrypoints', 'entry_point', 'data_access'):
        value, path = fact.get('value') or {}, _path(fact)
        if not isinstance(value, dict) or is_test(path) or value.get('category') == 'test': continue
        if fact['kind'] == 'data_access':
            method = str(value.get('operation') or 'get').upper()
            if value.get('client') not in (None, 'http', 'fetch', 'axios') or not value.get('target'): continue
            out['calls'].append({'file': path, 'method': method if method in METHODS else 'GET', 'path': clean_path(value['target'])})
        elif value.get('surface') == 'page':
            out['pages'].append({'route': str(value.get('route') or '/'), 'component': str(value.get('handler') or ''), 'router': path})
        elif value.get('surface') in ('http', 'endpoint', 'api', 'route', 'rpc') or (value.get('http_method') and value.get('surface') != 'page'):
            out['routes'].append({'route': clean_path(value.get('route') or ''), 'method': str(value.get('http_method') or 'ANY').upper(),
                                  'handler': value.get('handler'), 'file': path})
    for flow in _facts(report, 'flows', 'flow'):
        value = flow.get('value') or {}
        entry = value.get('entry') or {}
        first = next((s.get('from_path') for s in value.get('steps') or [] if isinstance(s, dict) and s.get('from') == entry.get('handler')), None)
        out['flows'].append({'surface': entry.get('surface'), 'route': entry.get('route'), 'handler': entry.get('handler'),
                             'method': entry.get('http_method'), 'file': first or entry.get('path') or _path(flow)})
    features = _load(report / 'features.json', {})
    out['features'] = [f for f in (features.get('features') if isinstance(features, dict) else None) or [] if isinstance(f, dict) and f.get('name')]
    for node in _facts(report, 'graph', 'graph_node'):
        out['imports'][_path(node)] = [d for d in (node.get('value') or {}).get('depends_on') or [] if isinstance(d, str)]
    for table in _facts(report, 'domain', 'data_table'):
        name = str((table.get('value') or {}).get('name') or '')
        path = _path(table)
        if (path in out['imports'] or not out['imports']) and not is_test(path) and len(name) > 1 and name.lower() not in NOT_TABLES:
            out['tables'][path].add(name)
    for fact in _facts(report, 'syntax', 'symbol', 'import_edge'):
        value, path = fact.get('value') or {}, _path(fact)
        if is_test(path): continue
        if fact['kind'] == 'symbol':
            name = str(value.get('name') or '')
            if value.get('exported') and name.upper() in METHODS and name.isupper(): out['methods'][path].add(name)
            if name and not value.get('parent'): out['symbols'][name].add(path)
        elif value.get('style') == 'absolute' and value.get('module'):
            out['packages'][path].add(str(value['module']))
    target = _load(report / 'target-architecture.json', {})
    target = target if isinstance(target, dict) else {}
    out['root'] = str(target.get('root') or '')
    for c in target.get('current_components') or []:
        if not isinstance(c, dict) or not c.get('id'): continue
        out['components'][c['id']] = str(c.get('name') or c['id'])
        for p in c.get('paths') or []:
            if isinstance(p, str): out['owner'][p] = c['id']
    return out


# ---------------------------------------------------------------- the links

def find_handlers(method, path, routes, methods):
    """([(file, function, how)], exact): who answers METHOD path on the server; [] when nothing says."""
    found = [(r['file'], r.get('handler') or method, 'entry point') for r in routes
             if same_route(r['route'], path) and r['method'] in (method, 'ANY', 'ALL', 'USE')]
    if found: return found, True
    rest = re.sub(r'^/api(?=/|$)', '', path).strip('/')
    if '://' in path or not rest: return [], False
    best, score = [], 0
    for file in methods:
        rel = route_of_file(file)
        s = 3 if rel == rest or same_route(rel.replace('[', ':').replace(']', ''), rest) else 2 if _words(rel) == _words(rest) else 0
        if s > score: best, score = [file], s
        elif s and s == score: best.append(file)
    if not best: return [], False
    answering = [f for f in best if method in methods[f]]
    how = 'file routing'
    if answering: return [(f, method, how) for f in sorted(answering)], len(answering) == 1
    return [(f, None, how) for f in sorted(best)], False


def _stem(path):
    return re.sub(r'\.\w+$', '', str(path).rsplit('/', 1)[-1])


def component_file(page, flows, symbols, imports):
    """The file of a page's component: its flow's first caller; else the one file defining that name; else the one file
    the router imports that the name spells, a lazy import (SettingsScreen -> settings/Settings.tsx, BlueprintSetup ->
    blueprint/Setup.tsx)."""
    for flow in flows:
        if flow['surface'] == 'page' and flow['route'] == page['route'] and flow['handler'] == page['component'] and flow['file']:
            return flow['file']
    name = page['component']
    homes = sorted(p for p in symbols.get(name, ()) if not is_test(p))
    named = [p for p in homes if _stem(p) == name]
    if len(homes) == 1 and homes[0] != page['router']: return homes[0]
    if len(named) == 1: return named[0]
    bare = re.sub(r'(Screen|Page|View|Route)$', '', name).lower()
    spelled = [f for f in imports.get(page['router'], ()) if bare in (_stem(f).lower(), (f.split('/')[-2] + _stem(f)).lower() if '/' in f else '')]
    return spelled[0] if len(spelled) == 1 else homes[0] if len(homes) == 1 else None


def build(report):
    """The system map: its nodes by column, their links, what each node reaches, and the caps; None when there is
    neither a page nor an API in the records."""
    r = records(report)
    imports, owner, components = r['imports'], r['owner'], r['components']
    # the APIs: every call the code makes, and every endpoint a feature names
    apis, feature_of_api = {}, defaultdict(set)
    def api(method, path):
        key = f'{method} {path}'
        if key not in apis: apis[key] = {'id': 'A:' + key, 'key': key, 'method': method, 'path': path, 'group': api_group(path), 'callers': set()}
        return apis[key]
    for call in r['calls']: api(call['method'], call['path'])['callers'].add(call['file'])
    for f in r['features']:
        for e in f.get('endpoints') or []:
            method, _, path = str(e).partition(' ')
            if method.upper() in METHODS and path:
                feature_of_api[api(method.upper(), clean_path(path))['id']].add(f['name'])
    # the pages, their component file and the files they reach
    feature_of_route = defaultdict(set)
    for f in r['features']:
        for s in f.get('surfaces') or []: feature_of_route[str(s)].add(f['name'])
    pages, seen = [], set()
    for p in r['pages']:
        key = f"{p['route']} {p['component']}"
        if key in seen: continue
        seen.add(key)
        comp = component_file(p, r['flows'], r['symbols'], imports)
        if comp == p['router']: comp = None      # defined in the router, which imports every screen: its reach says nothing
        files = _reach(comp, imports, DEPTH) if comp else {p['router']}
        pages.append({'id': 'P:' + key, 'route': p['route'], 'component': p['component'], 'file': comp or p['router'],
                      'features': sorted(feature_of_route.get(p['route'], ())), 'reach': files, 'traced': bool(comp)})
    roots = {str(Path(p['file']).parent) for p in pages if p['file'] and p['file'] != '.'}
    def own(page, file):
        if file == page['file']: return True
        home = str(Path(page['file']).parent)
        if page['file'] in {x['router'] for x in r['pages']} and page['file'] != file: return False
        inner = any(o != home and o.startswith(home + '/') for o in roots)
        return str(Path(file).parent) == home or (not inner and file.startswith(home + '/'))
    callers = defaultdict(set)
    for a in apis.values():
        for c in a['callers']: callers[c].add(a['id'])
    shared, links = {}, defaultdict(set)          # links: (page or caller id) -> api ids it calls itself
    uses = defaultdict(set)                       # page id -> shared caller ids it reaches
    for c, called in callers.items():
        users = [p for p in pages if c in p['reach'] or c == p['file']]
        owners = [p for p in users if own(p, c)]
        if users and len(owners) == len(users):
            for p in owners: links[p['id']] |= called
        else:
            shared[c] = {'id': 'C:' + c, 'path': c, 'pages': [p['id'] for p in users]}
            links['C:' + c] |= called
            for p in users: uses[p['id']].add('C:' + c)
    # the server side
    table_files = set(r['tables'])
    handlers = {}
    for a in apis.values():
        found, exact = find_handlers(a['method'], a['path'], r['routes'], r['methods'])
        a['handlers'] = [{'path': f, 'function': fn, 'how': how} for f, fn, how in found]
        a['exact'] = exact
        for f, _, _ in found: handlers.setdefault(f, {'id': 'H:' + f, 'path': f, 'apis': []})['apis'].append(a['id'])
    for f in set(r['methods']) | {x['file'] for x in r['routes']}:
        handlers.setdefault(f, {'id': 'H:' + f, 'path': f, 'apis': []})
    modules, tables, services = {}, {}, {}
    for h in handlers.values():
        mine = _reach(h['path'], imports, DEPTH, stop=table_files)
        near = _reach(h['path'], imports, DEPTH - 1, stop=table_files)
        deep = _reach(h['path'], imports, DEPTH + 1)
        home = owner.get(h['path'])
        h['modules'] = defaultdict(int)
        for f in mine - {h['path']}:
            m = owner.get(f)
            if m and m != home: h['modules'][m] += 1
        h['tables'] = sorted({t for f in near for t in r['tables'].get(f, ())})
        h['services'] = sorted({SERVICES[p][1] for f in deep for p in r['packages'].get(f, ()) if p in SERVICES})
        h['via'] = {}                            # a table or service: the part of the file that holds or uses it
        for f in near:
            for t in r['tables'].get(f, ()): h['via'].setdefault('T:' + t, owner.get(f))
        for f in deep:
            for p in r['packages'].get(f, ()):
                if p in SERVICES: h['via'].setdefault('S:' + SERVICES[p][1], owner.get(f))
        for m in h['modules']: modules.setdefault(m, {'id': 'M:' + m, 'name': components.get(m, m), 'handlers': []})['handlers'].append(h['id'])
        for t in h['tables']: tables.setdefault(t, {'id': 'T:' + t, 'name': t, 'files': sorted(f for f, ts in r['tables'].items() if t in ts)})
        for s in h['services']:
            kind, en, ar = next(v for v in SERVICES.values() if v[1] == s)
            services.setdefault(s, {'id': 'S:' + s, 'name': en, 'ar': ar, 'kind': kind})
    for a in apis.values():
        hs = [handlers[x['path']] for x in a['handlers']]
        a['tables'] = sorted({t for h in hs for t in h['tables']})
        a['services'] = sorted({s for h in hs for s in h['services']})
        a['modules'] = sorted({components.get(m, m) for h in hs for m in h['modules']})
        a['features'] = sorted(set(feature_of_api.get(a['id'], ())) | {n for c in a['callers'] for p in pages if c in p['reach'] for n in p['features']})
    return _assemble(pages, shared, apis, handlers, modules, tables, services, links, uses, r)


def _assemble(pages, shared, apis, handlers, modules, tables, services, links, uses, r):
    """Cap every column, then the links drawn and, for each node, every node it reaches or is reached from."""
    if not pages and not apis: return None
    capped = {}
    def cap(items, limit, name, weight):
        items = sorted(items, key=weight)
        capped[name] = max(len(items) - limit, 0)
        return items[:limit]
    api_list = cap(apis.values(), MAX_APIS, 'apis', lambda a: (-len(a['callers']) - 2 * bool(a['handlers']), a['group'], a['path'], a['method']))
    api_list.sort(key=lambda a: (a['group'], a['path'], METHODS.index(a['method']) if a['method'] in METHODS else 9))
    kept_apis = {a['id'] for a in api_list}
    page_list = cap(pages, MAX_PAGES, 'pages', lambda p: (-len(links[p['id']] | {x for c in uses[p['id']] for x in links[c]}), p['route']))
    page_list.sort(key=lambda p: (p['route'] == '*', p['route'], p['component']))
    caller_list = cap(shared.values(), MAX_CALLERS, 'callers', lambda c: (-len(links[c['id']]), c['path']))
    caller_list.sort(key=lambda c: c['path'])
    handler_list = cap(handlers.values(), MAX_HANDLERS, 'handlers', lambda h: (-len(h['apis']), h['path']))
    module_list = cap(modules.values(), MAX_MODULES, 'modules', lambda m: (-len(m['handlers']), m['name']))
    data = cap(list(tables.values()) + list(services.values()), MAX_DATA, 'data', lambda d: (d['id'][0] == 'S', d['name']))
    ids = {x['id'] for group in (page_list, caller_list, api_list, handler_list, module_list, data) for x in group}
    edges = []                                  # (from, to, weight, kind)
    for source in [p['id'] for p in page_list] + [c['id'] for c in caller_list]:
        edges += [(source, a, 1, 'call') for a in sorted(links[source]) if a in kept_apis]
    for p in page_list:
        edges += [(p['id'], c, 1, 'uses') for c in sorted(uses[p['id']])]
    for a in api_list:
        edges += [(a['id'], 'H:' + h['path'], 1, 'answer' if h['function'] else 'guess') for h in a['handlers']]
    module_of = {m['id']: m for m in module_list}
    holds = defaultdict(set)                    # module id -> data ids its files hold or use
    for h in handler_list:
        edges += [(h['id'], 'M:' + m, n, 'use') for m, n in sorted(h['modules'].items())]
        for d, m in h['via'].items():
            if m and 'M:' + m in module_of and m in h['modules']: holds['M:' + m].add(d)
            else: edges.append((h['id'], d, 1, 'data'))
    for m, ds in holds.items(): edges += [(m, d, 1, 'data') for d in sorted(ds)]
    edges = sorted({(a, b): (a, b, n, k) for a, b, n, k in edges if a in ids and b in ids}.values())
    # what each node reaches (down) and is reached from (up): the page's highlight
    api_of = {a['id']: a for a in api_list}
    handler_of = {h['id']: h for h in handler_list}
    def below_api(a):
        out = set()
        for h in api_of[a]['handlers']:
            hid = 'H:' + h['path']
            if hid in handler_of: out |= {hid} | below_handler(hid)
        return out
    def below_handler(hid):
        h = handler_of[hid]
        return {'M:' + m for m in h['modules']} | {'T:' + t for t in h['tables']} | {'S:' + s for s in h['services']}
    callers_of = defaultdict(set)
    for source, called in links.items():
        for a in called: callers_of[a].add(source)
    def above_api(a):
        out = set(callers_of[a])
        for c in list(out):
            if c.startswith('C:') and c[2:] in shared: out |= set(shared[c[2:]]['pages'])
        return out
    related = {}
    for p in page_list:
        reach = set(links[p['id']]) | set(uses[p['id']])
        for c in uses[p['id']]: reach |= links[c]
        related[p['id']] = {p['id']} | reach | {x for a in reach if a in api_of for x in below_api(a)}
    for c in caller_list:
        related[c['id']] = {c['id']} | set(c['pages']) | links[c['id']] | {x for a in links[c['id']] if a in api_of for x in below_api(a)}
    for a in api_list:
        related[a['id']] = {a['id']} | above_api(a['id']) | below_api(a['id'])
    for h in handler_list:
        related[h['id']] = {h['id']} | below_handler(h['id']) | {x for a in h['apis'] if a in api_of for x in {a} | above_api(a)}
    for m in module_list:
        hs = [x for x in m['handlers'] if x in handler_of]
        related[m['id']] = {m['id']} | holds.get(m['id'], set()) | {x for h in hs for x in {h} | {y for a in handler_of[h]['apis'] if a in api_of for y in {a} | above_api(a)}}
    for d in data:
        hs = [h for h in handler_list if d['id'] in below_handler(h['id'])]
        related[d['id']] = {d['id']} | {m for m, ds in holds.items() if d['id'] in ds} | {
            x for h in hs for x in {h['id']} | {y for a in h['apis'] if a in api_of for y in {a} | above_api(a)}}
    related = {k: sorted(v & ids) for k, v in related.items()}
    root = r['root']
    def common(paths):
        dirs = [p.split('/')[:-1] for p in paths]
        head = []
        for parts in zip(*dirs) if dirs else ():
            if len(set(parts)) != 1: break
            head.append(parts[0])
        return '/'.join(head) + '/' if head else ''
    def short(p, prefix=root):
        return p[len(prefix):] if prefix and p.startswith(prefix) and p != prefix else p
    server, client = common([h['path'] for h in handler_list]), common([c['path'] for c in caller_list])
    parts = common([m['name'] + '/' for m in module_list]) if len(module_list) > 1 else ''
    features = defaultdict(list)
    for p in page_list:
        for f in p['features']: features[f].append(p['id'])
    return {'pages': [{k: v for k, v in p.items() if k != 'reach'} | {'calls': sorted(links[p['id']] & kept_apis), 'shared': sorted(uses[p['id']] & ids)}
                      for p in page_list],
            'callers': [dict(c, calls=sorted(links[c['id']] & kept_apis), short=short(c['path'], client or root)) for c in caller_list],
            'apis': [{k: (sorted(v) if isinstance(v, set) else v) for k, v in a.items()} for a in api_list],
            'handlers': [{'id': h['id'], 'path': h['path'], 'short': short(h['path'], server or root), 'apis': [a for a in h['apis'] if a in kept_apis],
                          'modules': sorted(h['modules']), 'tables': h['tables'], 'services': h['services']} for h in handler_list],
            'modules': [dict(m, short=(m['name'] + '/')[len(parts):].rstrip('/') if parts and (m['name'] + '/').startswith(parts) and m['name'] + '/' != parts
                                  else m['name'].rsplit('/', 1)[-1]) for m in module_list], 'data': data,
            'features': [{'name': f, 'pages': ps} for f, ps in sorted(features.items())],
            'edges': [{'from': a, 'to': b, 'n': n, 'kind': k} for a, b, n, k in edges], 'related': related, 'capped': capped,
            'unknown': sum(1 for a in api_list if not a['handlers'] and '://' not in a['path']),
            'guessed': sum(1 for a in api_list if a['handlers'] and not a['exact']),
            'how': sorted({h['how'] for a in api_list for h in a['handlers']})}


# ---------------------------------------------------------------- the drawing

WIDTH, PAD, ROW, BOX_H, HEAD = 1100, 8, 22, 18, 18
COLUMNS = ((40, 176), (262, 204), (506, 192), (736, 142), (912, 188))   # (x, width): pages, APIs, handlers, modules, data


def _spread(wanted, pitch, top, bottom):
    """y for each item in order, as near its wanted y as the pitch allows, inside [top, bottom]."""
    out, last = [], top - pitch
    for y in wanted:
        last = max(y, last + pitch)
        out.append(last)
    limit = bottom - pitch
    for i in range(len(out) - 1, -1, -1):
        limit = min(out[i], limit)
        out[i] = limit
        limit -= pitch
    shift = top - min(out, default=top)
    return [y + max(shift, 0) for y in out]


def layout(sm):
    """{id: (column, y)}, the API group bands, the column heights and the drawing's size. The APIs set the height:
    grouped by resource, one row each; the others sit near what they link to, a row apart, without overlap."""
    if not sm: return None
    place, bands, y = {}, [], PAD
    groups = defaultdict(list)
    for a in sm['apis']: groups[a['group']].append(a)
    for name in sorted(groups):
        members = groups[name]
        if len(members) > 1:
            bands.append({'label': name + '*', 'top': y, 'bottom': y + HEAD + len(members) * ROW, 'n': len(members)})
            y += HEAD
        for a in members:
            place[a['id']] = (1, y); y += ROW
        y += 6 if len(members) > 1 else 0
    left = [p['id'] for p in sm['pages']] + [c['id'] for c in sm['callers']]
    height = max(y, PAD + len(left) * ROW + (HEAD if sm["callers"] else 0), PAD + len(sm["handlers"]) * ROW) + PAD
    pages_bottom = PAD + len(sm['pages']) * ROW
    for i, p in enumerate(sm['pages']): place[p["id"]] = (0, PAD + i * ROW)
    for i, c in enumerate(sm['callers']): place[c['id']] = (0, pages_bottom + HEAD + i * ROW)
    links = defaultdict(list)
    for e in sm['edges']: links[e['to']].append(e['from']); links[e['from']].append(e['to'])
    def near(items, column):
        def centre(item):
            ys = [place[o][1] for o in links[item['id']] if o in place and place[o][0] == column - 1]
            return sum(ys) / len(ys) if ys else height
        ordered = sorted(items, key=lambda it: (centre(it), it['id']))
        for it, yy in zip(ordered, _spread([min(centre(it), height) for it in ordered], ROW, PAD, height - PAD)):
            place[it['id']] = (column, yy)
    near(sm['handlers'], 2)
    def stack(items, column, sources):
        # parts and data are few and linked to most handlers: their centres all fall mid-height, so they are
        # stacked from the top in the order of those centres, where a reader starts
        def centre(item):
            ys = [place[o][1] for o in links[item['id']] if o in place and place[o][0] in sources]
            return sum(ys) / len(ys) if ys else height
        for i, it in enumerate(sorted(items, key=lambda it: (centre(it), it['id']))): place[it['id']] = (column, PAD + i * ROW)
    stack(sm['modules'], 3, (2,))
    stack(sm['data'], 4, (2, 3))
    return {'place': place, 'bands': bands, 'width': WIDTH, 'height': height, 'callers_top': pages_bottom if sm['callers'] else None}


# ---------------------------------------------------------------- Mermaid

def mermaid(sm, limit=300):
    """architecture/system.mmd: pages -> APIs -> handlers -> tables and services, each column a subgraph; the links in
    that order of importance (calls, answers, the shared code a page uses, the data reached), capped at `limit`."""
    if not sm: return None
    ids = {}
    def node(i):
        if i not in ids: ids[i] = f'n{len(ids) + 1}'
        return ids[i]
    q = lambda text: str(text).replace('"', "'")
    lines = ['flowchart LR', f'  %% {len(sm["pages"])} pages, {len(sm["apis"])} APIs, {len(sm["handlers"])} server handlers, '
             f'{len(sm["data"])} tables and services (eaos/system_map.py)']
    columns = (('pages', 'Pages', [(p['id'], f"{p['route']} · {p['component']}") for p in sm['pages']]
                + [(c['id'], f"shared: {c['short']}") for c in sm['callers']]),
               ('apis', 'APIs', [(a['id'], a['key']) for a in sm['apis']]),
               ('handlers', 'Server handlers', [(h['id'], h['short']) for h in sm['handlers'] if h['apis']]),
               ('data', 'Tables and services', [(d['id'], d['name']) for d in sm['data']]))
    drawn = set()
    for key, title, items in columns:
        lines.append(f'  subgraph {key}["{title}"]')
        lines.append('    direction TB')
        for i, label in items:
            shape = ('[("{}")]' if i.startswith('T:') else '(["{}"])' if i.startswith('P:') else '["{}"]').format(q(label))
            lines.append(f'    {node(i)}{shape}'); drawn.add(i)
        lines.append('  end')
    words = {'call': 'calls', 'uses': 'uses', 'answer': 'answers', 'guess': 'by file name'}
    edges = [(e['from'], e['to'], words.get(e['kind'], '')) for e in sm['edges'] if e['from'] in drawn and e['to'] in drawn]
    handler_data = {(h['id'], d) for h in sm['handlers'] for d in ['T:' + t for t in h['tables']] + ['S:' + s for s in h['services']]}
    edges += sorted((a, b, 'reaches') for a, b in handler_data if a in drawn and b in drawn)
    order = ('calls', 'answers', 'by file name', 'uses', 'reaches')
    edges = sorted({(a, b): (a, b, w) for a, b, w in edges}.values(), key=lambda e: order.index(e[2]) if e[2] in order else len(order))
    if len(edges) > limit: lines.append(f'  %% {len(edges) - limit} of the {len(edges)} links are left out: only the first {limit} are drawn')
    lines += [f'  {node(a)} -->|{w}| {node(b)}' if w else f'  {node(a)} --> {node(b)}' for a, b, w in edges[:limit]]
    return '\n'.join(lines) + '\n'
