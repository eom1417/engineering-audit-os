"""Group user-facing surfaces into the features the program offers a person or another program.

A feature is what the program does for a user. Its inputs are the entry-point facts the
extractor produced: every fact whose surface is a person- or service-addressable channel
and whose framework is one the user can reach. The grouping rule is taken from the
project's own conventions: a layout-only segment (``/_authenticated``) and a parameter
(``$invoiceId``) collapse to the next named segment; the CLI surface groups by the
script that defined it. The facts are joined to flows (to learn which files the entry
touches) and to data_access (to learn which tables it reads and writes), and a feature
is critical when it is allowed to write to a table or when its path crosses an
authentication or payments boundary. Surfaces that did not enter any feature are
recorded in ``unassigned_surfaces``; they are never dropped silently.
"""
import re
from collections import OrderedDict

NAME = 'features'
VERSION = '1'

_LAYOUT_SEGMENT = re.compile(r'^_')           # `_authenticated`, `_app`, ...
_PARAMETER_SEGMENT = re.compile(r'^\$|^:')    # TanStack `$id`, Next.js `[id]`, Express `:id`
_WRITE_OPERATION = frozenset({'insert', 'update', 'upsert', 'delete'})
_AUTH_KEYWORD = frozenset({'auth', 'login', 'signup', 'signin', 'signout', 'payment',
                           'checkout', 'billing'})
# Pages a person reaches on the way in, or to read about the product, are one feature each, not one
# feature per page: a vibe-coded app has login, reset, reset-password and confirm-email as four routes
# of the same thing.
_GROUPS = {'auth': frozenset({'auth', 'login', 'logout', 'signin', 'signup', 'signout', 'register', 'reset',
                              'reset-password', 'forgot-password', 'confirm-email', 'verify', 'verify-email',
                              'callback', 'oauth', 'magic-link'}),
           'info': frozenset({'privacy', 'privacy-policy', 'terms', 'tos', 'terms-of-service', 'contact', 'support',
                              'about', 'faq', 'help', 'legal', 'cookies', 'pricing', '*', '404', 'not-found'})}
_TABLE_OPERATIONS = frozenset({'select', 'insert', 'update', 'upsert', 'delete'})
# How far a page's imports are followed to find the data it touches (page, hook, service), and above what
# share of features a file counts as shared infrastructure whose data belongs to no single feature.
_IMPORT_DEPTH = 3
_PROVIDER = re.compile(r'(Context|Provider)\.[jt]sx?$')


def _feature_name(route):
    """What a single route collapses to under the project conventions.

    Layout-only segments (``/_authenticated``) and parameter segments (``$invoiceId``) are
    stripped; the first remaining non-empty segment is the feature. ``/`` alone is the
    ``home`` feature.
    """
    if not route or route == '/':
        return 'home'
    parts = [segment for segment in route.split('/')
             if segment and not _LAYOUT_SEGMENT.match(segment) and not _PARAMETER_SEGMENT.match(segment)]
    if not parts:
        return 'home'
    name = parts[0].rstrip('_')
    for group, words in _GROUPS.items():
        if name.lower() in words: return group
    return name


def _is_critical(surfaces):
    """A feature is critical when its surface (route or path) names auth or payments.

    File paths like ``src/routes/_authenticated/...`` carry the substring "auth" without
    meaning it; only the route pattern the user reaches is searched, and only with
    word-boundary matches so ``signup`` does not match ``signup_state``.
    """
    boundary = re.compile(r'\b(' + '|'.join(sorted(_AUTH_KEYWORD)) + r')\b')
    for surface in surfaces:
        clean = surface.strip('/').lower() if isinstance(surface, str) else ''
        if boundary.search(clean): return True
    return False


def _caller_files_for(route, flow_by_route):
    """The files a feature's flow touches, joined with the entry-point path itself."""
    flow = flow_by_route.get(route)
    if not flow:
        return []
    return list(OrderedDict.fromkeys([flow['entry']['path'], *flow.get('touched_files', [])]))


def _table_access(files, data_access_by_path):
    """(tables read, tables written, endpoints called) by the feature's files.

    Tables come from table operations only, not rpc, auth or storage. Endpoints are the app's own HTTP
    back end, as `METHOD /path`; a POST, PUT, PATCH or DELETE writes like a table insert does.
    """
    reads, writes, endpoints = OrderedDict(), OrderedDict(), OrderedDict()
    for f in files:
        for access in data_access_by_path.get(f, []):
            target, operation = access.get('target'), access.get('operation')
            if not target: continue
            if access.get('client') == 'http':
                endpoints[f'{operation.upper()} {target}'] = operation != 'get'
            elif operation in _TABLE_OPERATIONS:
                (reads if operation == 'select' else writes)[target] = True
    return list(reads), list(writes), endpoints


def _import_graph(facts):
    """path -> the internal files it imports, from resolved module_edge facts."""
    graph = {}
    for fact in facts:
        if fact.get('kind') != 'module_edge': continue
        to_path = (fact.get('value') or {}).get('to_path')
        path = (fact.get('location') or {}).get('path')
        if path and to_path: graph.setdefault(path, set()).add(to_path)
    return graph


def _component_files(facts):
    """(file, imported name) -> the file it comes from, from import_edge names joined to resolved module_edges.

    A router that declares every route in one file (React Router in App.tsx) names each page by its
    component; that component's file, not App.tsx, is where the page's own code starts.
    """
    names = {f.get('id'): (f['location'].get('path'), (f.get('value') or {}).get('names') or [])
             for f in facts if f.get('kind') == 'import_edge'}
    table, by_stem = {}, {}
    for fact in facts:
        if fact.get('kind') != 'module_edge': continue
        value = fact.get('value') or {}
        to_path = value.get('to_path')
        if not to_path: continue
        importer, imported = names.get(value.get('import_fact_id'), (fact['location'].get('path'), []))
        for name in imported: table[(importer, name)] = to_path
        stem = to_path.rsplit('/', 1)[-1].split('.')[0]
        by_stem.setdefault((importer, stem), to_path)   # lazy(() => import("./pages/Drivers"))
    return table, by_stem


def _reach(seeds, graph, depth=_IMPORT_DEPTH):
    """{file: hops} for every file the seeds import, up to `depth` hops: a page, its hooks, their services."""
    seen = {path: 0 for path in seeds}
    frontier = set(seeds)
    for hop in range(1, depth + 1):
        frontier = {child for path in frontier for child in graph.get(path, ())} - set(seen)
        if not frontier: break
        seen.update({path: hop for path in frontier})
    return seen


def _index_data_access(facts):
    """path -> list of data_access fact records (with target/operation/client) for that file."""
    index = {}
    for fact in facts:
        if fact.get('kind') != 'data_access': continue
        path = (fact.get('location') or {}).get('path')
        value = fact.get('value') or {}
        if not path or not value: continue
        index.setdefault(path, []).append({'target': value.get('target'),
                                          'operation': value.get('operation'),
                                          'client': value.get('client'),
                                          'fact_id': fact.get('id')})
    return index


def _index_flows_by_route(facts):
    """route -> first matching flow with that route in its entry.

    Some flow facts carry the entry as a plain string (the route); others carry it as
    a dict whose ``route`` key is the same string. Both shapes agree on the answer
    we need: which surfaces the trace reaches.
    """
    index = {}
    for fact in facts:
        if fact.get('kind') != 'flow': continue
        value = fact.get('value') or {}
        entry = value.get('entry')
        if isinstance(entry, dict):
            route = entry.get('route')
        else:
            route = entry
        if route is None: continue
        index.setdefault(route, value)
    return index


def _user_facing_surfaces(facts):
    """Filter entry-point facts to person- and service-addressable channels.

    Drop framework markers (npm_script, public_api) and test-only entry points: those are
    declared so the downstream audit knows they exist, not because a user reaches them.
    """
    surfaces = []
    for fact in facts:
        if fact.get('kind') != 'entry_point': continue
        value = fact.get('value') or {}
        surface = value.get('surface')
        if surface not in {'page', 'http', 'cli'}: continue
        framework = value.get('framework')
        if framework in {'npm_script', 'public_api'}: continue
        if value.get('category') == 'test' or value.get('test_only'): continue
        surfaces.append(fact)
    return surfaces


def _surface_identifier(fact):
    """The string the grouped feature exposes: route for page/http, location.path for cli."""
    value = fact.get('value') or {}
    if value.get('surface') == 'cli':
        return (fact.get('location') or {}).get('path') or value.get('route') or ''
    return value.get('route') or ''


def build(facts):
    """Group user-facing surfaces into features and bind them to files, tables, and evidence."""
    surface_facts = _user_facing_surfaces(facts)
    flow_index = _index_flows_by_route(facts)
    data_access_index = _index_data_access(facts)
    by_feature = OrderedDict()
    unassigned = []
    consumed = set()
    kinds_by_feature = {}
    for fact in surface_facts:
        identifier = _surface_identifier(fact)
        if not identifier:
            continue
        fact_value = fact.get('value') or {}
        if fact_value.get('surface') == 'cli':
            feature = f"cli:{identifier}"
        else:
            feature = _feature_name(identifier)
        record = by_feature.setdefault(feature, {'surfaces': [], 'evidence': [], 'files': [],
                                                'tables': [], 'writes': False})
        record['surfaces'].append(identifier)
        record['evidence'].append(fact.get('id'))
        kinds = kinds_by_feature.setdefault(feature, {})
        kinds[fact_value.get('surface')] = kinds.get(fact_value.get('surface'), 0) + 1
        consumed.add(fact.get('id'))
    feature_paths = {}
    components, by_stem = _component_files(facts)
    for fact in surface_facts:
        if fact.get('id') not in consumed: continue
        value = fact.get('value') or {}
        if value.get('surface') == 'cli':
            feature = f"cli:{_surface_identifier(fact)}"
        else:
            feature = _feature_name(_surface_identifier(fact))
        location_path = (fact.get('location') or {}).get('path')
        handler = value.get('handler')
        component = components.get((location_path, handler)) or by_stem.get((location_path, handler))
        if component or location_path: feature_paths.setdefault(feature, []).append(component or location_path)
    graph = _import_graph(facts)
    reached = {}
    for feature, record in by_feature.items():
        # Only the surface files are the feature's own; what their flows touch and what they import is
        # reached, and goes through the shared-file rule below like any other reached file.
        seeds = list(feature_paths.get(feature, []))
        touched = []
        for identifier in record['surfaces']:
            flow = flow_index.get(identifier) or {}
            entry = flow.get('entry') or {}
            entry_path = entry.get('path') if isinstance(entry, dict) else None
            if entry_path: seeds.append(entry_path)
            touched += flow.get('touched_files', []) or []
        seeds = list(OrderedDict.fromkeys(seeds))
        hops = _reach(seeds + touched, graph)
        for path in touched: hops[path] = min(hops.get(path, 1), 1)
        for path in seeds: hops[path] = 0
        reached[feature] = (seeds, hops)
    # A file's data belongs to the features that reach it most directly. A page that imports operatorsApi
    # owns what it calls; a page that meets it three imports deep through a shared component does not.
    # A context or provider (AuthContext.tsx) wraps the whole app and every page reaches it through a hook:
    # its data goes only to the feature its own path names (components/auth/ belongs to `auth`).
    nearest = {}
    for _, hops in reached.values():
        for path, hop in hops.items(): nearest[path] = min(nearest.get(path, hop), hop)
    def owned(feature, path):
        return feature.lower() in {part.lower() for part in path.split('/')[:-1]}
    for feature, record in by_feature.items():
        seeds, hops = reached[feature]
        kept = {path for path, hop in hops.items() if path not in seeds and hop == nearest[path]
                and (not _PROVIDER.search(path.rsplit('/', 1)[-1]) or owned(feature, path))}
        files = list(OrderedDict.fromkeys(seeds + sorted(kept)))
        record['files'] = files
        record['tables'], record['writes_tables'], endpoints = _table_access(files, data_access_index)
        # Its own endpoints first (/operators for drivers is not guessable, /settlements for settlements is).
        stem = feature.lower().rstrip('s')
        record['endpoints'] = sorted(endpoints, key=lambda e: (stem not in e.lower(), list(endpoints).index(e)))
        record['writes'] = bool(record['writes_tables']) or any(endpoints.values())
        record['kinds'] = kinds_by_feature.get(feature, {})
        for path in files:
            for access in data_access_index.get(path, []):
                if access.get('fact_id') and access['fact_id'] not in record['evidence']:
                    record['evidence'].append(access['fact_id'])
        record['critical'] = record['writes'] or feature == 'auth' or _is_critical(record['surfaces'])
    for fact in surface_facts:
        if fact.get('id') not in consumed:
            unassigned.append((fact.get('location') or {}).get('path') or '')
    return {'schema_version': 1,
            'features': [{'name': feature,
                          'description': _describe(record),
                          'surfaces': sorted(set(record['surfaces'])),
                          'tables': sorted(set(record['tables']) | set(record['writes_tables'])),
                          'writes': sorted(set(record['writes_tables'])),
                          'endpoints': record['endpoints'],
                          'files': sorted(set(record['files'])),
                          'evidence': sorted(set(record['evidence'])),
                          'critical': bool(record['critical'])}
                         for feature, record in by_feature.items()],
            'unassigned_surfaces': sorted(set([s for s in unassigned if s]))}


_NOUNS = {'page': ('صفحة', 'صفحتان', 'صفحات'), 'http': ('مسار', 'مساران', 'مسارات'),
          'cli': ('أمر', 'أمران', 'أوامر')}


def _count(n, nouns):
    """Arabic counting: one, two, three to ten, eleven and above."""
    one, two, few = nouns
    if n == 1: return f'{one} واحدة' if one in ('صفحة', 'نقطة API') else f'{one} واحد'
    if n == 2: return two if one != 'نقطة API' else 'نقطتا API'
    return f'{n} {few}' if 3 <= n <= 10 else f'{n} {one}'


def _describe(record):
    """A factual sentence from the data: what the user reaches, what it reads, what it writes."""
    reach = ' و'.join(_count(n, _NOUNS.get(kind, _NOUNS['page'])) for kind, n in sorted(record.get('kinds', {}).items())) \
        or _count(len(record['surfaces']), _NOUNS['page'])
    reads = [t for t in record['tables'] if t not in record['writes_tables']]
    parts = [reach]
    if reads: parts.append('تقرأ ' + '، '.join(reads))
    if record['writes_tables']: parts.append('وتكتب ' + '، '.join(record['writes_tables']))
    endpoints = record.get('endpoints') or []
    if endpoints:
        shown = '، '.join(endpoints[:3]) + ('…' if len(endpoints) > 3 else '')
        parts.append(f'وتستدعي {_count(len(endpoints), ("نقطة API", "نقطتي API", "نقاط API"))} ({shown})')
    if len(parts) == 1: parts.append('لا تلمس بيانات')
    return parts[0] + '، ' + ' '.join(parts[1:])
