"""The system map of the report for people (eaos/report/human_report.py): every page, every API it calls, the server code
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
    for fact in _facts(report, 'entrypoints', 'entry_point', 'data_access'): _entry_record(fact, out)
    out['flows'] = [_flow_record(flow) for flow in _facts(report, 'flows', 'flow')]
    features = _load(report / 'features.json', {})
    out['features'] = [f for f in (features.get('features') if isinstance(features, dict) else None) or [] if isinstance(f, dict) and f.get('name')]
    for node in _facts(report, 'graph', 'graph_node'):
        out['imports'][_path(node)] = [d for d in (node.get('value') or {}).get('depends_on') or [] if isinstance(d, str)]
    for table in _facts(report, 'domain', 'data_table'): _table_record(table, out)
    for fact in _facts(report, 'syntax', 'symbol', 'import_edge'): _syntax_record(fact, out)
    _component_records(report, out)
    return out


def _is_route(value):
    return value.get('surface') in ('http', 'endpoint', 'api', 'route', 'rpc') or bool(value.get('http_method') and value.get('surface') != 'page')


def _call_record(value, path, out):
    method = str(value.get('operation') or 'get').upper()
    if value.get('client') not in (None, 'http', 'fetch', 'axios') or not value.get('target'): return
    out['calls'].append({'file': path, 'method': method if method in METHODS else 'GET', 'path': clean_path(value['target'])})


def _entry_record(fact, out):
    """A call the code makes, a page, or a server route."""
    value, path = fact.get('value') or {}, _path(fact)
    if not isinstance(value, dict) or is_test(path) or value.get('category') == 'test': return
    if fact['kind'] == 'data_access': _call_record(value, path, out)
    elif value.get('surface') == 'page':
        out['pages'].append({'route': str(value.get('route') or '/'), 'component': str(value.get('handler') or ''), 'router': path})
    elif _is_route(value):
        out['routes'].append({'route': clean_path(value.get('route') or ''), 'method': str(value.get('http_method') or 'ANY').upper(),
                              'handler': value.get('handler'), 'file': path})


def _flow_record(flow):
    value = flow.get('value') or {}
    entry = value.get('entry') or {}
    first = next((s.get('from_path') for s in value.get('steps') or [] if isinstance(s, dict) and s.get('from') == entry.get('handler')), None)
    return {'surface': entry.get('surface'), 'route': entry.get('route'), 'handler': entry.get('handler'),
            'method': entry.get('http_method'), 'file': first or entry.get('path') or _path(flow)}


def _table_record(table, out):
    name = str((table.get('value') or {}).get('name') or '')
    path = _path(table)
    if (path in out['imports'] or not out['imports']) and not is_test(path) and len(name) > 1 and name.lower() not in NOT_TABLES:
        out['tables'][path].add(name)


def _symbol_record(value, path, out):
    name = str(value.get('name') or '')
    if value.get('exported') and name.upper() in METHODS and name.isupper(): out['methods'][path].add(name)
    if name and not value.get('parent'): out['symbols'][name].add(path)


def _syntax_record(fact, out):
    """An exported HTTP-method function, a top-level name, or a package a file imports."""
    value, path = fact.get('value') or {}, _path(fact)
    if is_test(path): return
    if fact['kind'] == 'symbol': _symbol_record(value, path, out)
    elif value.get('style') == 'absolute' and value.get('module'):
        out['packages'][path].add(str(value['module']))


def _component_records(report, out):
    target = _load(report / 'target-architecture.json', {})
    target = target if isinstance(target, dict) else {}
    out['root'] = str(target.get('root') or '')
    for c in target.get('current_components') or []:
        if not isinstance(c, dict) or not c.get('id'): continue
        out['components'][c['id']] = str(c.get('name') or c['id'])
        out['owner'].update({p: c['id'] for p in c.get('paths') or [] if isinstance(p, str)})


# ---------------------------------------------------------------- the links

def _route_score(rel, rest):
    """3 when a file's routed words are the path's, 2 when only its words match, else 0."""
    if rel == rest or same_route(rel.replace('[', ':').replace(']', ''), rest): return 3
    return 2 if _words(rel) == _words(rest) else 0


def _best_files(rest, methods):
    best, score = [], 0
    for file in methods:
        s = _route_score(route_of_file(file), rest)
        if s > score: best, score = [file], s
        elif s and s == score: best.append(file)
    return best


def find_handlers(method, path, routes, methods):
    """([(file, function, how)], exact): who answers METHOD path on the server; [] when nothing says."""
    found = [(r['file'], r.get('handler') or method, 'entry point') for r in routes
             if same_route(r['route'], path) and r['method'] in (method, 'ANY', 'ALL', 'USE')]
    if found: return found, True
    rest = re.sub(r'^/api(?=/|$)', '', path).strip('/')
    if '://' in path or not rest: return [], False
    best = _best_files(rest, methods)
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
    # the APIs: every call the code makes, and every endpoint a feature names
    apis, feature_of_api = _apis(r)
    # the pages, their component file and the files they reach
    pages = _pages(r)
    shared, links, uses = _link_callers(apis, pages, r)
    # the server side
    table_files = set(r['tables'])
    handlers = _handlers(apis, r)
    modules, tables, services = _server_side(handlers, r, table_files)
    for a in apis.values(): _api_reach(a, handlers, pages, feature_of_api, r['components'])
    return _assemble(pages, shared, apis, handlers, modules, tables, services, links, uses, r)


def _apis(r):
    apis, feature_of_api = {}, defaultdict(set)
    def api(method, path):
        key = f'{method} {path}'
        if key not in apis: apis[key] = {'id': 'A:' + key, 'key': key, 'method': method, 'path': path, 'group': api_group(path), 'callers': set()}
        return apis[key]
    for call in r['calls']: api(call['method'], call['path'])['callers'].add(call['file'])
    for f in r['features']:
        for method, _, path in (str(e).partition(' ') for e in f.get('endpoints') or []):
            if method.upper() in METHODS and path:
                feature_of_api[api(method.upper(), clean_path(path))['id']].add(f['name'])
    return apis, feature_of_api


def _page(p, key, r, feature_of_route):
    comp = component_file(p, r['flows'], r['symbols'], r['imports'])
    if comp == p['router']: comp = None      # defined in the router, which imports every screen: its reach says nothing
    files = _reach(comp, r['imports'], DEPTH) if comp else {p['router']}
    return {'id': 'P:' + key, 'route': p['route'], 'component': p['component'], 'file': comp or p['router'],
            'features': sorted(feature_of_route.get(p['route'], ())), 'reach': files, 'traced': bool(comp)}


def _pages(r):
    feature_of_route = defaultdict(set)
    for f in r['features']:
        for s in f.get('surfaces') or []: feature_of_route[str(s)].add(f['name'])
    pages, seen = [], set()
    for p in r['pages']:
        key = f"{p['route']} {p['component']}"
        if key in seen: continue
        seen.add(key)
        pages.append(_page(p, key, r, feature_of_route))
    return pages


def _owns(page, file, routers, roots):
    """Whether a calling file belongs to one page alone: its own file, or a file in its own folder."""
    if file == page['file']: return True
    home = str(Path(page['file']).parent)
    if page['file'] in routers and page['file'] != file: return False
    inner = any(o != home and o.startswith(home + '/') for o in roots)
    return str(Path(file).parent) == home or (not inner and file.startswith(home + '/'))


def _link_callers(apis, pages, r):
    """(the callers shared by pages, links: page or caller id -> the API ids it calls itself, uses: page id -> the shared
    caller ids it reaches)."""
    roots = {str(Path(p['file']).parent) for p in pages if p['file'] and p['file'] != '.'}
    routers = {x['router'] for x in r['pages']}
    callers = defaultdict(set)
    for a in apis.values():
        for c in a['callers']: callers[c].add(a['id'])
    shared, links, uses = {}, defaultdict(set), defaultdict(set)
    for c, called in callers.items():
        users = [p for p in pages if c in p['reach'] or c == p['file']]
        owners = [p for p in users if _owns(p, c, routers, roots)]
        if users and len(owners) == len(users):
            for p in owners: links[p['id']] |= called
            continue
        shared[c] = {'id': 'C:' + c, 'path': c, 'pages': [p['id'] for p in users]}
        links['C:' + c] |= called
        for p in users: uses[p['id']].add('C:' + c)
    return shared, links, uses


def _handlers(apis, r):
    handlers = {}
    for a in apis.values():
        found, exact = find_handlers(a['method'], a['path'], r['routes'], r['methods'])
        a['handlers'] = [{'path': f, 'function': fn, 'how': how} for f, fn, how in found]
        a['exact'] = exact
        for f, _, _ in found: handlers.setdefault(f, {'id': 'H:' + f, 'path': f, 'apis': []})['apis'].append(a['id'])
    for f in set(r['methods']) | {x['file'] for x in r['routes']}:
        handlers.setdefault(f, {'id': 'H:' + f, 'path': f, 'apis': []})
    return handlers


def _via(near, deep, r):
    """A table or service: the part of the file that holds or uses it."""
    via = {}
    for f in near:
        for t in r['tables'].get(f, ()): via.setdefault('T:' + t, r['owner'].get(f))
    for f in deep:
        for p in (p for p in r['packages'].get(f, ()) if p in SERVICES): via.setdefault('S:' + SERVICES[p][1], r['owner'].get(f))
    return via


def _describe_handler(h, r, table_files):
    """The parts, tables and services a server handler reaches through its imports."""
    imports, owner = r['imports'], r['owner']
    mine = _reach(h['path'], imports, DEPTH, stop=table_files)
    near = _reach(h['path'], imports, DEPTH - 1, stop=table_files)
    deep = _reach(h['path'], imports, DEPTH + 1)
    home = owner.get(h['path'])
    h['modules'] = defaultdict(int)
    for m in (owner.get(f) for f in mine - {h['path']}):
        if m and m != home: h['modules'][m] += 1
    h['tables'] = sorted({t for f in near for t in r['tables'].get(f, ())})
    h['services'] = sorted({SERVICES[p][1] for f in deep for p in r['packages'].get(f, ()) if p in SERVICES})
    h['via'] = _via(near, deep, r)


def _register(h, r, modules, tables, services):
    for m in h['modules']: modules.setdefault(m, {'id': 'M:' + m, 'name': r['components'].get(m, m), 'handlers': []})['handlers'].append(h['id'])
    for t in h['tables']: tables.setdefault(t, {'id': 'T:' + t, 'name': t, 'files': sorted(f for f, ts in r['tables'].items() if t in ts)})
    for s in h['services']:
        kind, en, ar = next(v for v in SERVICES.values() if v[1] == s)
        services.setdefault(s, {'id': 'S:' + s, 'name': en, 'ar': ar, 'kind': kind})


def _server_side(handlers, r, table_files):
    modules, tables, services = {}, {}, {}
    for h in handlers.values():
        _describe_handler(h, r, table_files)
        _register(h, r, modules, tables, services)
    return modules, tables, services


def _api_reach(a, handlers, pages, feature_of_api, components):
    hs = [handlers[x['path']] for x in a['handlers']]
    a['tables'] = sorted({t for h in hs for t in h['tables']})
    a['services'] = sorted({s for h in hs for s in h['services']})
    a['modules'] = sorted({components.get(m, m) for h in hs for m in h['modules']})
    a['features'] = sorted(set(feature_of_api.get(a['id'], ())) | {n for c in a['callers'] for p in pages if c in p['reach'] for n in p['features']})


def _assemble(pages, shared, apis, handlers, modules, tables, services, links, uses, r):
    """Cap every column, then the links drawn and, for each node, every node it reaches or is reached from."""
    if not pages and not apis: return None
    cols, capped = _columns(pages, shared, apis, handlers, modules, tables, services, links, uses)
    view = {'cols': cols, 'links': links, 'uses': uses, 'capped': capped, 'root': r['root'],
            'kept_apis': {a['id'] for a in cols['apis']},
            'ids': {x['id'] for name in ('pages', 'callers', 'apis', 'handlers', 'modules', 'data') for x in cols[name]}}
    view['edges'], view['holds'] = _edges(view)
    # what each node reaches (down) and is reached from (up): the page's highlight
    view['related'] = _related(view, _Reach(cols, links, shared))
    return _drawn(view)


def _cap(items, limit, name, weight, capped):
    items = sorted(items, key=weight)
    capped[name] = max(len(items) - limit, 0)
    return items[:limit]


def _columns(pages, shared, apis, handlers, modules, tables, services, links, uses):
    """Every column capped and ordered, and how many each cap left out."""
    capped = {}
    api_list = _cap(apis.values(), MAX_APIS, 'apis', lambda a: (-len(a['callers']) - 2 * bool(a['handlers']), a['group'], a['path'], a['method']), capped)
    api_list.sort(key=lambda a: (a['group'], a['path'], METHODS.index(a['method']) if a['method'] in METHODS else 9))
    page_list = _cap(pages, MAX_PAGES, 'pages', lambda p: (-len(links[p['id']] | {x for c in uses[p['id']] for x in links[c]}), p['route']), capped)
    page_list.sort(key=lambda p: (p['route'] == '*', p['route'], p['component']))
    caller_list = _cap(shared.values(), MAX_CALLERS, 'callers', lambda c: (-len(links[c['id']]), c['path']), capped)
    caller_list.sort(key=lambda c: c['path'])
    return {'apis': api_list, 'pages': page_list, 'callers': caller_list,
            'handlers': _cap(handlers.values(), MAX_HANDLERS, 'handlers', lambda h: (-len(h['apis']), h['path']), capped),
            'modules': _cap(modules.values(), MAX_MODULES, 'modules', lambda m: (-len(m['handlers']), m['name']), capped),
            'data': _cap(list(tables.values()) + list(services.values()), MAX_DATA, 'data', lambda d: (d['id'][0] == 'S', d['name']), capped)}, capped


def _handler_edges(h, module_of, holds):
    """A handler's links to the parts it uses and the data it reaches; data its own part holds is linked from that part."""
    edges = [(h['id'], 'M:' + m, n, 'use') for m, n in sorted(h['modules'].items())]
    for d, m in h['via'].items():
        if m and 'M:' + m in module_of and m in h['modules']: holds['M:' + m].add(d)
        else: edges.append((h['id'], d, 1, 'data'))
    return edges


def _call_edges(cols, links, uses, kept_apis):
    """The client side's links, (from, to, weight, kind): page or caller -> API, page -> shared caller, API -> handler."""
    sources = [p['id'] for p in cols['pages']] + [c['id'] for c in cols['callers']]
    return ([(s, a, 1, 'call') for s in sources for a in sorted(links[s]) if a in kept_apis]
            + [(p['id'], c, 1, 'uses') for p in cols['pages'] for c in sorted(uses[p['id']])]
            + [(a['id'], 'H:' + h['path'], 1, 'answer' if h['function'] else 'guess') for a in cols['apis'] for h in a['handlers']])


def _edges(view):
    """(the links drawn, module id -> data ids its files hold or use)."""
    cols = view['cols']
    edges = _call_edges(cols, view['links'], view['uses'], view['kept_apis'])
    module_of = {m['id']: m for m in cols['modules']}
    holds = defaultdict(set)
    for h in cols['handlers']: edges += _handler_edges(h, module_of, holds)
    for m, ds in holds.items(): edges += [(m, d, 1, 'data') for d in sorted(ds)]
    ids = view['ids']
    return sorted({(a, b): (a, b, n, k) for a, b, n, k in edges if a in ids and b in ids}.values()), holds


class _Reach:
    """What a node reaches below it and is reached from above it, among the kept APIs and handlers."""

    def __init__(self, cols, links, shared):
        self.api_of = {a['id']: a for a in cols['apis']}
        self.handler_of = {h['id']: h for h in cols['handlers']}
        self.shared = shared
        self.callers_of = defaultdict(set)
        for source, called in links.items():
            for a in called: self.callers_of[a].add(source)

    def below_handler(self, hid):
        h = self.handler_of[hid]
        return {'M:' + m for m in h['modules']} | {'T:' + t for t in h['tables']} | {'S:' + s for s in h['services']}

    def below_api(self, a):
        out = set()
        for hid in ('H:' + h['path'] for h in self.api_of[a]['handlers']):
            if hid in self.handler_of: out |= {hid} | self.below_handler(hid)
        return out

    def above_api(self, a):
        out = set(self.callers_of[a])
        for c in list(out):
            if c.startswith('C:') and c[2:] in self.shared: out |= set(self.shared[c[2:]]['pages'])
        return out

    def below(self, apis):
        return {x for a in apis if a in self.api_of for x in self.below_api(a)}

    def above(self, apis):
        return {x for a in apis if a in self.api_of for x in {a} | self.above_api(a)}


def _page_reach(p, links, uses):
    reach = set(links[p['id']]) | set(uses[p['id']])
    for c in uses[p['id']]: reach |= links[c]
    return reach


def _related(view, reach):
    """For each node, every node it reaches or is reached from, among the nodes drawn."""
    cols, links, uses, holds = view['cols'], view['links'], view['uses'], view['holds']
    related = {}
    for p in cols['pages']:
        down = _page_reach(p, links, uses)
        related[p['id']] = {p['id']} | down | reach.below(down)
    for c in cols['callers']:
        related[c['id']] = {c['id']} | set(c['pages']) | links[c['id']] | reach.below(links[c['id']])
    for a in cols['apis']:
        related[a['id']] = {a['id']} | reach.above_api(a['id']) | reach.below_api(a['id'])
    for h in cols['handlers']:
        related[h['id']] = {h['id']} | reach.below_handler(h['id']) | reach.above(h['apis'])
    for m in cols['modules']:
        hs = [x for x in m['handlers'] if x in reach.handler_of]
        related[m['id']] = {m['id']} | holds.get(m['id'], set()) | {x for h in hs for x in {h} | reach.above(reach.handler_of[h]['apis'])}
    for d in cols['data']:
        related[d['id']] = _data_related(d, cols['handlers'], holds, reach)
    return {k: sorted(v & view['ids']) for k, v in related.items()}


def _data_related(d, handlers, holds, reach):
    hs = [h for h in handlers if d['id'] in reach.below_handler(h['id'])]
    return {d['id']} | {m for m, ds in holds.items() if d['id'] in ds} | {x for h in hs for x in {h['id']} | reach.above(h['apis'])}


def _common(paths):
    """The folder every path shares, with a trailing slash; '' when none."""
    dirs = [p.split('/')[:-1] for p in paths]
    head = []
    for parts in zip(*dirs) if dirs else ():
        if len(set(parts)) != 1: break
        head.append(parts[0])
    return '/'.join(head) + '/' if head else ''


def _short(p, prefix):
    return p[len(prefix):] if prefix and p.startswith(prefix) and p != prefix else p


def _module_short(name, parts):
    if parts and (name + '/').startswith(parts) and name + '/' != parts: return (name + '/')[len(parts):].rstrip('/')
    return name.rsplit('/', 1)[-1]


def _drawn_handlers(handlers, kept_apis, prefix):
    return [{'id': h['id'], 'path': h['path'], 'short': _short(h['path'], prefix), 'apis': [a for a in h['apis'] if a in kept_apis],
             'modules': sorted(h['modules']), 'tables': h['tables'], 'services': h['services']} for h in handlers]


def _features(pages):
    """Each feature with the drawn pages that belong to it, by name."""
    features = defaultdict(list)
    for p in pages:
        for f in p['features']: features[f].append(p['id'])
    return [{'name': f, 'pages': ps} for f, ps in sorted(features.items())]


def _api_counts(apis):
    """The APIs no handler answers (an outside URL aside), those matched by a guess, and the ways they were matched."""
    return {'unknown': sum(1 for a in apis if not a['handlers'] and '://' not in a['path']),
            'guessed': sum(1 for a in apis if a['handlers'] and not a['exact']),
            'how': sorted({h['how'] for a in apis for h in a['handlers']})}


def _drawn_pages(pages, links, uses, ids, kept_apis):
    return [{k: v for k, v in p.items() if k != 'reach'} | {'calls': sorted(links[p['id']] & kept_apis), 'shared': sorted(uses[p['id']] & ids)}
            for p in pages]


def _drawn_callers(callers, links, kept_apis, prefix):
    return [dict(c, calls=sorted(links[c['id']] & kept_apis), short=_short(c['path'], prefix)) for c in callers]


def _drawn(view):
    """The system map as the report and the Studio read it."""
    cols, links, uses, ids, kept_apis, root = view['cols'], view['links'], view['uses'], view['ids'], view['kept_apis'], view['root']
    server, client = _common([h['path'] for h in cols['handlers']]), _common([c['path'] for c in cols['callers']])
    parts = _common([m['name'] + '/' for m in cols['modules']]) if len(cols['modules']) > 1 else ''
    return {'pages': _drawn_pages(cols['pages'], links, uses, ids, kept_apis),
            'callers': _drawn_callers(cols['callers'], links, kept_apis, client or root),
            'apis': [{k: (sorted(v) if isinstance(v, set) else v) for k, v in a.items()} for a in cols['apis']],
            'handlers': _drawn_handlers(cols['handlers'], kept_apis, server or root),
            'modules': [dict(m, short=_module_short(m['name'], parts)) for m in cols['modules']], 'data': cols['data'],
            'features': _features(cols['pages']),
            'edges': [{'from': a, 'to': b, 'n': n, 'kind': k} for a, b, n, k in view['edges']], 'related': view['related'], 'capped': view['capped'],
            **_api_counts(cols['apis'])}

