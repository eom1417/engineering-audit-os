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
    return parts[0].rstrip('_')


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


def _data_access_targets(files, data_access_by_path):
    """Tables the feature's files touch: union over the files of data_access.target names."""
    targets = []
    seen = set()
    for f in files:
        for access in data_access_by_path.get(f, []):
            target = access.get('target')
            if not target or target in seen: continue
            seen.add(target)
            targets.append(target)
    return targets


def _writes_to_table(files, data_access_by_path):
    """True if any of the feature's files performs an insert/update/upsert/delete."""
    for f in files:
        for access in data_access_by_path.get(f, []):
            if access.get('operation') in _WRITE_OPERATION: return True
    return False


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
        consumed.add(fact.get('id'))
    feature_paths = {}
    for fact in surface_facts:
        if fact.get('id') not in consumed: continue
        value = fact.get('value') or {}
        if value.get('surface') == 'cli':
            feature = f"cli:{_surface_identifier(fact)}"
        else:
            feature = _feature_name(_surface_identifier(fact))
        location_path = (fact.get('location') or {}).get('path')
        if location_path: feature_paths.setdefault(feature, []).append(location_path)
    for feature, record in by_feature.items():
        surface_paths = list(feature_paths.get(feature, []))
        for identifier in record['surfaces']:
            flow = flow_index.get(identifier) or {}
            entry = flow.get('entry') or {}
            entry_path = entry.get('path') if isinstance(entry, dict) else None
            if entry_path: surface_paths.append(entry_path)
            for touched in flow.get('touched_files', []) or []: surface_paths.append(touched)
        files = list(OrderedDict.fromkeys(surface_paths))
        record['files'] = files
        record['tables'] = _data_access_targets(files, data_access_index)
        if _writes_to_table(files, data_access_index):
            record['writes'] = True
        for path in files:
            for access in data_access_index.get(path, []):
                if access.get('fact_id') and access['fact_id'] not in record['evidence']:
                    record['evidence'].append(access['fact_id'])
        record['critical'] = record['writes'] or _is_critical(record['surfaces'])
    for fact in surface_facts:
        if fact.get('id') not in consumed:
            unassigned.append((fact.get('location') or {}).get('path') or '')
    return {'schema_version': 1,
            'features': [{'name': feature,
                          'description': _describe(record),
                          'surfaces': sorted(set(record['surfaces'])),
                          'tables': sorted(set(record['tables'])),
                          'files': sorted(set(record['files'])),
                          'evidence': sorted(set(record['evidence'])),
                          'critical': bool(record['critical'])}
                         for feature, record in by_feature.items()],
            'unassigned_surfaces': sorted(set([s for s in unassigned if s]))}


def _describe(record):
    """A factual sentence from the data: how many surfaces, what they read, what they write."""
    surf = len(record['surfaces'])
    reads = sorted({t for t in record['tables']
                    if not record['writes'] or t not in record['tables'] or True})
    writes = sorted(record['tables']) if record['writes'] else []
    parts = [f"{surf} سطح" if surf != 1 else "سطح واحد"]
    parts.append(f"يقرأ {', '.join(record['tables'])}" if record['tables']
                 else "لا يقرأ جداول")
    if writes:
        parts.append(f"يكتب {', '.join(record['tables'])}")
    return '، '.join(parts)
