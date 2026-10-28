"""The system map of the report for people (eaos/report/human_report/): every page, every API it calls, the server code
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
How a path is read is in eaos/analysis/maps/system_paths.py, the drawing's data in eaos/analysis/maps/system_view.py.
"""
import re
from collections import defaultdict
from pathlib import Path

from .system_paths import (METHODS, _facts, _path, _reach, _words, api_group, clean_path, is_test,
                           route_of_file, same_route)
from .system_view import assemble
from ...core.system.files import read_json

DEPTH = 3
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


# ---------------------------------------------------------------- the records

def records(report):
    """Everything the map reads, from the report's records; each piece empty when its record is missing or broken."""
    report = Path(report)
    out = {'pages': [], 'routes': [], 'calls': [], 'features': [], 'flows': [], 'imports': {}, 'tables': defaultdict(set),
           'owner': {}, 'components': {}, 'methods': defaultdict(set), 'symbols': defaultdict(set), 'packages': defaultdict(set), 'root': ''}
    for fact in _facts(report, 'entrypoints', 'entry_point', 'data_access'): _entry_record(fact, out)
    out['flows'] = [_flow_record(flow) for flow in _facts(report, 'flows', 'flow')]
    out['features'] = _named_features(read_json(report / 'features.json', {}))
    out['imports'].update(_imports(report))
    for table in _facts(report, 'domain', 'data_table'): _table_record(table, out)
    for fact in _facts(report, 'syntax', 'symbol', 'import_edge'): _syntax_record(fact, out)
    _component_records(report, out)
    return out


def _named_features(features):
    """The features of features.json that have a name."""
    return [f for f in (features.get('features') if isinstance(features, dict) else None) or [] if isinstance(f, dict) and f.get('name')]


def _imports(report):
    """{file: the files it imports} of the resolved graph."""
    return {_path(node): [d for d in (node.get('value') or {}).get('depends_on') or [] if isinstance(d, str)]
            for node in _facts(report, 'graph', 'graph_node')}


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
    elif value.get('surface') == 'page': out['pages'].append(_page_record(value, path))
    elif _is_route(value): out['routes'].append(_route_record(value, path))


def _page_record(value, path):
    return {'route': str(value.get('route') or '/'), 'component': str(value.get('handler') or ''), 'router': path}


def _route_record(value, path):
    return {'route': clean_path(value.get('route') or ''), 'method': str(value.get('http_method') or 'ANY').upper(),
            'handler': value.get('handler'), 'file': path}


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
    target = read_json(report / 'target-architecture.json', {})
    target = target if isinstance(target, dict) else {}
    out['root'] = str(target.get('root') or '')
    for c in target.get('current_components') or []: _component_record(c, out)


def _component_record(c, out):
    """One of today's parts: its name, and the files it owns."""
    if not isinstance(c, dict) or not c.get('id'): return
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
    return _routed(method, path, methods)


def _routed(method, path, methods):
    """File routing: the files whose path spells the URL after /api, those exporting the method first."""
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
    traced = _traced_file(page, flows)
    if traced: return traced
    name = page['component']
    homes = _defined_in(name, symbols)
    named = [p for p in homes if _stem(p) == name]
    if len(homes) == 1 and homes[0] != page['router']: return homes[0]
    if len(named) == 1: return named[0]
    spelled = _spelled(name, imports.get(page['router'], ()))
    return spelled[0] if len(spelled) == 1 else homes[0] if len(homes) == 1 else None


def _defined_in(name, symbols):
    """The files outside the tests that define the name at their top level, sorted."""
    return sorted(p for p in symbols.get(name, ()) if not is_test(p))


def _traced_file(page, flows):
    """The first caller of the page's flow, or None."""
    for flow in flows:
        if flow['surface'] == 'page' and flow['route'] == page['route'] and flow['handler'] == page['component'] and flow['file']:
            return flow['file']
    return None


def _spelled(name, imported):
    """The imported files the component's name spells, a screen's suffix aside (BlueprintSetup -> blueprint/Setup.tsx)."""
    bare = re.sub(r'(Screen|Page|View|Route)$', '', name).lower()
    return [f for f in imported if bare in (_stem(f).lower(), (f.split('/')[-2] + _stem(f)).lower() if '/' in f else '')]


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
    return assemble((pages, shared, apis), (handlers, modules, tables, services), (links, uses), r)


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


def _folders(pages, r):
    """(the files that route the pages, the folders of the pages' own files)."""
    return {x['router'] for x in r['pages']}, {str(Path(p['file']).parent) for p in pages if p['file'] and p['file'] != '.'}


def _users(c, pages, folders):
    """(the pages that reach a calling file, those it belongs to alone); `folders`: (the routers, the pages' folders)."""
    routers, roots = folders
    users = [p for p in pages if c in p['reach'] or c == p['file']]
    return users, [p for p in users if _owns(p, c, routers, roots)]


def _called_by(apis):
    """{calling file: the APIs it calls}."""
    callers = defaultdict(set)
    for a in apis.values():
        for c in a['callers']: callers[c].add(a['id'])
    return callers


def _link_callers(apis, pages, r):
    """(the callers shared by pages, links: page or caller id -> the API ids it calls itself, uses: page id -> the shared
    caller ids it reaches)."""
    folders = _folders(pages, r)
    shared, links, uses = {}, defaultdict(set), defaultdict(set)
    for c, called in _called_by(apis).items():
        users, owners = _users(c, pages, folders)
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
    a['features'] = _api_features(a, pages, feature_of_api)


def _api_features(a, pages, feature_of_api):
    """The features an API belongs to: those naming its endpoint, and those of the pages that reach its callers."""
    return sorted(set(feature_of_api.get(a['id'], ())) | {n for c in a['callers'] for p in pages if c in p['reach'] for n in p['features']})
