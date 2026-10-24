"""Group user-facing surfaces into the features the program offers a person or another program.

A feature is what the program does for a user. Its inputs are the entry-point facts the
extractor produced: every fact whose surface is a person- or service-addressable channel
and whose framework is one the user can reach. The grouping rule is taken from the
project's own conventions: a layout-only segment (``/_authenticated``) and a parameter
(``$invoiceId``) collapse to the next named segment; the CLI surface groups by the
command that defines it (a program's subcommands; a lone script by its file), and dev scripts under
tools/ or scripts/ are no feature. The facts are joined to flows (to learn which files the entry
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


def _table_access(files, data_access_by_path):
    """(tables read, tables written, endpoints called) by the feature's files.

    Tables come from table operations only, not rpc, auth or storage. Endpoints are the app's own HTTP
    back end, as `METHOD /path`; a POST, PUT, PATCH or DELETE writes like a table insert does.
    """
    reads, writes, endpoints = OrderedDict(), OrderedDict(), OrderedDict()
    for f in files:
        for access in data_access_by_path.get(f, []): _note_access(access, reads, writes, endpoints)
    return list(reads), list(writes), endpoints


def _note_access(access, reads, writes, endpoints):
    """One data access: an endpoint the app calls (a write unless it is a GET), or a table read or written."""
    target, operation = access.get('target'), access.get('operation')
    if not target: return
    if access.get('client') == 'http':
        endpoints[f'{operation.upper()} {target}'] = operation != 'get'
    elif operation in _TABLE_OPERATIONS:
        (reads if operation == 'select' else writes)[target] = True


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


# Frameworks whose CLI surfaces are a program's own commands: each command (subcommand) is one feature.
_COMMANDS = frozenset({'argparse', 'click', 'console_script', 'go_command'})
# Folders of a developer's scripts: running them is maintaining the product, not using it.
_DEV_TOOLING = frozenset({'tools', 'tool', 'scripts', 'script'})


def _namer(surface_facts):
    """The feature a surface belongs to, or None when it is no product feature.

    A program with commands (argparse subparsers, click, console scripts) groups its CLI by command; a module's
    `if __name__ == '__main__'` is then a helper, not a feature. A script under tools/ or scripts/ is dev tooling.
    Route `/` is `home` only in a web app; in a program with commands, a web front end is named by its folder
    (studio/src/App.tsx is `studio`)."""
    commands = any((f.get('value') or {}).get('surface') == 'cli' and (f.get('value') or {}).get('framework') in _COMMANDS
                   and (f.get('value') or {}).get('route') for f in surface_facts)
    return lambda fact: _feature_of(fact, commands)


def _feature_of(fact, commands):
    """The feature of one surface (see _namer); `commands`: the program has commands of its own."""
    value, path = fact.get('value') or {}, (fact.get('location') or {}).get('path') or ''
    if value.get('surface') == 'cli':
        if _DEV_TOOLING & set(path.split('/')[:-1]): return None
        if value.get('framework') in _COMMANDS and value.get('route'): return f"cli:{value['route']}"
        return None if commands else f"cli:{_surface_identifier(fact)}"
    feature = _feature_name(_surface_identifier(fact))
    if feature == 'home' and commands and '/' in path: return path.split('/', 1)[0]
    return feature


def build(facts):
    """Group user-facing surfaces into features and bind them to files, tables, and evidence."""
    surface_facts = _user_facing_surfaces(facts)
    feature_of = _namer(surface_facts)
    data_access_index = _index_data_access(facts)
    by_feature, kinds_by_feature, consumed = _group(surface_facts, feature_of)
    feature_paths = _feature_paths(facts, [f for f in surface_facts if f.get('id') in consumed], feature_of)
    reached = _reached(by_feature, feature_paths, _index_flows_by_route(facts), _import_graph(facts))
    nearest = _nearest(reached)
    for feature, record in by_feature.items():
        _bind(feature, record, reached[feature], nearest, data_access_index)
        record['kinds'] = kinds_by_feature.get(feature, {})
    unassigned = [(fact.get('location') or {}).get('path') or '' for fact in surface_facts if fact.get('id') not in consumed]
    return {'schema_version': 1,
            'features': [_feature_row(feature, record) for feature, record in by_feature.items()],
            'unassigned_surfaces': sorted(set([s for s in unassigned if s]))}


def _group(surface_facts, feature_of):
    """({feature: its record}, {feature: {surface kind: count}}, the ids of the surfaces some feature took)."""
    by_feature, kinds_by_feature, consumed = OrderedDict(), {}, set()
    for fact in surface_facts:
        identifier = _surface_identifier(fact)
        if not identifier: continue
        feature = feature_of(fact)
        if not feature: continue
        record = by_feature.setdefault(feature, {'surfaces': [], 'evidence': [], 'files': [],
                                                'tables': [], 'writes': False})
        record['surfaces'].append(identifier)
        record['evidence'].append(fact.get('id'))
        kinds = kinds_by_feature.setdefault(feature, {})
        surface = (fact.get('value') or {}).get('surface')
        kinds[surface] = kinds.get(surface, 0) + 1
        consumed.add(fact.get('id'))
    return by_feature, kinds_by_feature, consumed


def _feature_paths(facts, taken, feature_of):
    """{feature: the files its surfaces start in}: a routed page's component file, else the surface's own file."""
    feature_paths = {}
    components, by_stem = _component_files(facts)
    for fact in taken:
        location_path = (fact.get('location') or {}).get('path')
        handler = (fact.get('value') or {}).get('handler')
        component = components.get((location_path, handler)) or by_stem.get((location_path, handler))
        if component or location_path: feature_paths.setdefault(feature_of(fact), []).append(component or location_path)
    return feature_paths


def _reached(by_feature, feature_paths, flow_index, graph):
    """{feature: (its own files, {file: hops} of what it reaches)}. Only the surface files are the feature's own;
    what their flows touch and what they import is reached, and goes through the shared-file rule like any other."""
    reached = {}
    for feature, record in by_feature.items():
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
    return reached


def _nearest(reached):
    """{file: the fewest hops any feature reaches it in}."""
    nearest = {}
    for _, hops in reached.values():
        for path, hop in hops.items(): nearest[path] = min(nearest.get(path, hop), hop)
    return nearest


def _owned(feature, path):
    return feature.lower() in {part.lower() for part in path.split('/')[:-1]}


def _bind(feature, record, reach, nearest, data_access_index):
    """A feature's files, tables, endpoints and evidence. A file's data belongs to the features that reach it most
    directly: a page that imports operatorsApi owns what it calls; a page that meets it three imports deep through a
    shared component does not. A context or provider (AuthContext.tsx) wraps the whole app and every page reaches it
    through a hook: its data goes only to the feature its own path names (components/auth/ belongs to `auth`)."""
    seeds, hops = reach
    kept = {path for path, hop in hops.items() if path not in seeds and hop == nearest[path]
            and (not _PROVIDER.search(path.rsplit('/', 1)[-1]) or _owned(feature, path))}
    files = list(OrderedDict.fromkeys(seeds + sorted(kept)))
    record['files'] = files
    record['tables'], record['writes_tables'], endpoints = _table_access(files, data_access_index)
    # Its own endpoints first (/operators for drivers is not guessable, /settlements for settlements is).
    stem = feature.lower().rstrip('s')
    record['endpoints'] = sorted(endpoints, key=lambda e: (stem not in e.lower(), list(endpoints).index(e)))
    record['writes'] = bool(record['writes_tables']) or any(endpoints.values())
    for path in files:
        for access in data_access_index.get(path, []):
            if access.get('fact_id') and access['fact_id'] not in record['evidence']:
                record['evidence'].append(access['fact_id'])
    record['critical'] = record['writes'] or feature == 'auth' or _is_critical(record['surfaces'])


def _feature_row(feature, record):
    return {'name': feature,
            'description': _describe(record),
            'surfaces': sorted(set(record['surfaces'])),
            'tables': sorted(set(record['tables']) | set(record['writes_tables'])),
            'writes': sorted(set(record['writes_tables'])),
            'endpoints': record['endpoints'],
            'files': sorted(set(record['files'])),
            'evidence': sorted(set(record['evidence'])),
            'critical': bool(record['critical'])}


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
