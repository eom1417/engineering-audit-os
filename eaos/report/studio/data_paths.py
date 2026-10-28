"""studio/data_paths.json: where each piece of data enters, which code writes and reads it, and where it is kept.

Read only from records the check already wrote (A-analysis N6, the smallest part the Studio's data map needs; the
full field-to-column trace is NS40.T2). Nothing is invented: a tier the records do not reach is a gap, drawn and
counted, never a guessed link.

    stores       a table (a Supabase `.from(t)` call, or a CREATE TABLE in the code), a storage bucket, a database
                 function (rpc), the auth service, or an API resource of the app's own back end (an HTTP endpoint
                 grouped by its first path segment): facts/entrypoints.json data_access, facts/domain.json data_table
    endpoints    one per method and path (HTTP) or per operation and table (Supabase), with the modules that call it
    paths        one per call site that writes: input field -> form -> request key -> calling module -> endpoint ->
                 handler -> column. The request keys are the names of the object literal the call sends
                 (data_access value.keys); a Supabase row's keys are the table's columns; the handler is the server
                 route of the same method and path (entry_point surface http) and the columns it reaches are the
                 writes in the files its flow touches (facts/flows.json touched_files)
    violations   an endpoint or a table written from more than one module: the data has more than one owner
    target       each writer's component goes where target-architecture.json sends it (current_components
                 target_component); a store whose writers all land in one target component has a single source there

The overview is laid out in data_paths_layout.py (callers and stores in two lanes, ordered by barycentre sweeps with
eaos/analysis/maps/layout.order_columns; the target's components ordered against the same, pinned, stores), so every view and
every reader draws the same places. Above MAX_LANE nodes a lane is clustered and each cluster expands on request.
"""
import re
from collections import Counter, defaultdict
from pathlib import Path

from ...analysis.maps import architecture as arch_map
from .data_paths_layout import FAMILIES, MAX_LANE, view  # noqa: F401  (MAX_LANE: a lane's limit, read here by the tests)
from .system import owner_of
from ...core.system.files import read_json

WRITES = {'post', 'put', 'patch', 'delete', 'insert', 'update', 'upsert', 'rpc', 'storage'}
READS = {'get', 'select'}
AUTH = 'auth'
TIERS = ('field', 'form', 'key', 'caller', 'endpoint', 'handler', 'column')
# Each gap a tier can have: why the records stop there, and the step of the plan that will reach it.
GAPS = {
    'no_ui_extractor': 'NS40.T2',          # field, form: EAOS has no model of forms and fields yet
    'payload_not_literal': 'NS40.T2',      # key: the call sends a variable, so its keys are not in the call
    'backend_outside_snapshot': 'NS40.T2',  # handler: the repository holds no server route at all
    'no_matching_route': 'NS40.T1',        # handler: server routes exist, none has this method and path
    'behind_handler': 'NS40.T2',           # column: the handler's writes are not traced to columns
    'handler_writes_unseen': 'NS40.T2',    # column: the handler is known but its flow reaches no write
}
SRC = {
    'stores': 'facts/entrypoints.json#data_access (targets) + facts/domain.json#data_table',
    'endpoints': 'facts/entrypoints.json#data_access (method and path, or operation and table)',
    'writers': 'facts/entrypoints.json#data_access[operation is a write].location.path (distinct modules)',
    'readers': 'facts/entrypoints.json#data_access[operation is a read].location.path (distinct modules)',
    'keys': 'facts/entrypoints.json#data_access.value.keys (object literal the call sends; names only)',
    'handler': 'facts/entrypoints.json#entry_point[surface=http] of the same method and normalised path',
    'columns': 'Supabase row keys; or data_access writes in the files the handler\'s flow touches (facts/flows.json)',
    'component': 'target-architecture.json#current_components (deepest component holding the module)',
    'target': 'target-architecture.json#current_components[].target_component',
}


def _measure(value, src, unit='count'):
    return {'value': value, 'src': src, 'unit': unit}


def route_key(path):
    """One spelling per route: `/items/:id`, `/items/{id}`, `/items/<int:id>` and `/items/${id}` are `/items/{}`."""
    path = re.sub(r'\$\{[^}]*\}|\{[^}]*\}|<[^>]*>|:[A-Za-z_]\w*|\*', '{}', str(path or '').split('?', 1)[0])
    path = '/' + path.strip().lstrip('/')
    return re.sub(r'/+', '/', path).rstrip('/').lower() or '/'


def table_name(name):
    """`public.Work_Orders` and `"work_orders"` are one table: quotes and the default schema dropped, lower case."""
    name = str(name or '').replace('"', '').replace('`', '').strip().lower()
    return name[len('public.'):] if name.startswith('public.') else name


def _store_of(value):
    """(store id, kind, display name) of one data_access fact's target, or None for a call with no target."""
    client, target, op = value.get('client'), str(value.get('target') or ''), value.get('operation')
    if client == 'supabase': return _supabase_store(target, op)
    if client == 'http': return _api_store(target)
    return None


def _supabase_store(target, op):
    """A Supabase call's store: its auth service, a storage bucket, a database function (rpc) or a table."""
    if target == AUTH or op in ('getSession', 'getUser', 'signOut', 'signUp', 'signIn', 'signInWithPassword',
                                'signInWithOAuth', 'resetPasswordForEmail', 'updateUser', 'onAuthStateChange'):
        return 'auth:supabase', 'auth', 'Supabase Auth'
    if op == 'storage': return f'bucket:{target}', 'bucket', target
    if op == 'rpc': return f'rpc:{target}', 'rpc', target
    return f'table:{table_name(target)}', 'table', table_name(target)


def _api_store(target):
    """An HTTP call's store: the back end's resource named by the path's first segment."""
    if target in ('', '{dynamic}', '/{}'): return 'api:{dynamic}', 'resource', '{dynamic}'
    head = route_key(target).split('/')[1] if route_key(target) != '/' else ''
    return f'api:/{head}', 'resource', '/' + next((p for p in target.split('/') if p), head)


def _endpoint_of(value):
    client, target, op = value.get('client'), str(value.get('target') or ''), str(value.get('operation') or '')
    if client == 'http': return f'ep:{op.upper()} {route_key(target)}', f'{op.upper()} {target}'
    return f'ep:{client}:{op} {target}', f'{op} {target}'


def _site(fact):
    location = fact.get('location') or {}
    return {'path': location.get('path') or '', 'line': location.get('start_line'), 'fact': fact.get('id')}


def _component_of(report):
    """(owner(path) -> current component name | None, {current name: target name}, target known)."""
    record = read_json(Path(report) / 'target-architecture.json', {}) or {}
    comps = [c for c in record.get('current_components') or [] if isinstance(c, dict) and c.get('name')]
    owner = owner_of([c['name'] for c in comps]) if comps else (lambda path: None)
    goes = {c['name']: c.get('target_component') for c in comps}
    return owner, goes, bool(record.get('target_components'))


def _touched(report):
    """{(METHOD, route key): (flow id, the files the flow touches)} of every HTTP flow."""
    touched = {}
    for flow in arch_map.facts(report, 'flows', 'flow'):
        value = flow.get('value') or {}
        entry = value.get('entry') or {}
        if entry.get('surface') == 'http' and entry.get('route'):
            touched[(str(entry.get('http_method') or '').upper(), route_key(entry['route']))] = (flow.get('id'), value.get('touched_files') or [])
    return touched


def _table_writes(files, access_by_file):
    """[{store, columns, fact}] of every table write in the files."""
    writes = []
    for access in (access for path in sorted(set(files)) for access in access_by_file.get(path, [])):
        v = access.get('value') or {}
        store = _store_of(v)
        if store and v.get('operation') in WRITES and store[1] == 'table':
            writes.append({'store': store[0], 'columns': v.get('keys'), 'fact': access.get('id')})
    return writes


def _servers(report):
    """{(METHOD, route key): {handler, path, line, fact, writes: [(store id, columns, fact)]}} from the server routes the
    repository declares, with the writes their flows reach."""
    access_by_file = defaultdict(list)
    for fact in arch_map.facts(report, 'entrypoints', 'data_access'):
        access_by_file[arch_map.path_of(fact)].append(fact)
    touched = _touched(report)
    out = {}
    for fact in arch_map.facts(report, 'entrypoints', 'entry_point'):
        value = fact.get('value') or {}
        if value.get('surface') != 'http' or not value.get('route') or value.get('category') == 'test': continue
        key = (str(value.get('http_method') or 'GET').upper(), route_key(value['route']))
        flow_id, files = touched.get(key, (None, [arch_map.path_of(fact)]))
        out.setdefault(key, {'handler': value.get('handler'), **_site(fact), 'flow': flow_id, 'writes': _table_writes(files, access_by_file)})
    return out


def _handler_steps(value, kind, keys, server, has_server):
    """The handler and column tiers of a write path: direct to the database, through a known server route, or a gap."""
    if value.get('client') != 'http': return _direct_steps(kind, keys)
    if server: return _server_steps(server)
    return {'handler': {'state': 'gap', 'reason': 'no_matching_route' if has_server else 'backend_outside_snapshot'},
            'column': {'state': 'gap', 'reason': 'behind_handler'}}


def _direct_steps(kind, keys):
    """The handler and column tiers of a call straight to the database: its columns are the keys it sends to a table."""
    return {'handler': {'state': 'direct', 'reason': 'direct_database_client'},
            'column': ({'state': 'known', 'columns': keys} if kind == 'table' and keys is not None else
                       {'state': 'known', 'columns': None} if kind != 'table' else
                       {'state': 'gap', 'reason': 'payload_not_literal'})}


def _server_steps(server):
    """The handler and column tiers of a call a known server route answers: the stores and columns its flow writes."""
    reached = [w for w in server['writes'] if w['store']]
    return {'handler': {'state': 'known', 'handler': server['handler'], 'path': server['path'],
                        'line': server['line'], 'fact': server['fact'], 'flow': server['flow']},
            'column': ({'state': 'known', 'stores': sorted({w['store'] for w in reached}),
                        'columns': sorted({c for w in reached for c in w['columns'] or []}) or None}
                       if reached else {'state': 'gap', 'reason': 'handler_writes_unseen'})}


def _steps(value, kind, module, context):
    """Each tier of one write path, from the input field to the column; `context`: (owner, servers, any server)."""
    owner, servers, has_server = context
    keys, op = value.get('keys'), str(value.get('operation') or '')
    server = servers.get((op.upper(), route_key(value.get('target')))) if value.get('client') == 'http' else None
    steps = {'field': {'state': 'gap', 'reason': 'no_ui_extractor'},
             'form': {'state': 'gap', 'reason': 'no_ui_extractor'},
             'key': ({'state': 'known', 'keys': keys, 'partial': bool(value.get('keys_partial'))} if keys is not None
                     else {'state': 'gap', 'reason': 'payload_not_literal'}),
             'caller': {'state': 'known', 'component': owner(module)},  # the module is the path's site
             'endpoint': {'state': 'known'}}                           # the endpoint is the path's own
    steps.update(_handler_steps(value, kind, keys, server, has_server))
    return steps


class _Inventory:
    """Every store and endpoint the calls reach, the modules that write and read each, and one path per write."""

    def __init__(self, declared, context):
        self.declared, self.context = declared, context
        self.stores, self.endpoints = {}, {}
        self.writers_of, self.readers_of = defaultdict(set), defaultdict(set)
        self.paths = []

    def endpoint(self, value, sid, op):
        eid, label = _endpoint_of(value)
        endpoint = self.endpoints.setdefault(eid, {'id': eid, 'label': label, 'store': sid, 'operation': op,
                                                   'method': op.upper() if value.get('client') == 'http' else None,
                                                   'writers': set(), 'readers': set(), 'keys': set(), 'sites': []})
        if eid not in self.stores[sid]['endpoints']: self.stores[sid]['endpoints'].append(eid)
        return endpoint

    def add(self, fact):
        value = fact.get('value') or {}
        store = _store_of(value)
        if not store: return
        sid, kind, name = store
        op = str(value.get('operation') or '')
        module = arch_map.path_of(fact)
        self.stores.setdefault(sid, {'id': sid, 'kind': kind, 'name': name, 'client': value.get('client'),
                                     'declared': self.declared.get(sid), 'endpoints': [], 'sites': 0})
        self.stores[sid]['sites'] += 1
        endpoint = self.endpoint(value, sid, op)
        endpoint['sites'].append(_site(fact))
        writes = op in WRITES
        (endpoint['writers'] if writes else endpoint['readers']).add(module)
        (self.writers_of if writes else self.readers_of)[sid].add(module)
        if not writes: return
        if value.get('keys'): endpoint['keys'].update(value['keys'])
        self.paths.append({'store': sid, 'endpoint': endpoint['id'], 'site': _site(fact), 'steps': _steps(value, kind, module, self.context)})


def _declared(report):
    """{table store id: where the code declares it, and whether row-level security is on} of every table not dropped."""
    declared = {}
    for fact in arch_map.facts(report, 'domain', 'data_table'):
        value = fact.get('value') or {}
        if value.get('dropped'): continue
        declared.setdefault(f"table:{table_name(value.get('name'))}", {**_site(fact), 'rls': value.get('rls_enabled')})
    return declared


def _change(later, writers, store):
    if later is None or not writers: return None
    if len(writers) == 1: return 'single_already'
    return 'merged_in_target' if len(later) == 1 and not store['target']['unmapped'] else 'still_multiple'


def _ownership(store, writers, inventory, grouping):
    """A store's writers and readers, its owners today and in the target; `grouping`: ((today's group, the target's
    group), whether there is a target)."""
    (group_today, group_target), has_target = grouping
    today = sorted({group_today(m) for m in writers})
    later = sorted({group_target(m) for m in writers} - {None}) if has_target else None
    # A table has more than one owner when two modules write it; an API resource only when one of its endpoints is
    # written from two modules (POST /auth/login and POST /auth/register from two files are two inputs, one owner each).
    many = len(writers) > 1 if store['kind'] != 'resource' else any(len(inventory.endpoints[e]['writers']) > 1 for e in store['endpoints'])
    store.update(
        writers=sorted(writers), readers=sorted(inventory.readers_of.get(store['id'], set())),
        multi_writer=many,
        today={'writers': len(writers), 'components': today},
        target=None if later is None else {'components': later, 'single': len(later) <= 1 if writers else None,
                                           'unmapped': sorted(m for m in writers if group_target(m) is None)},
    )
    store['change'] = _change(later, writers, store)


def _violations(inventory, grouping):
    """The endpoints, then the tables, written from more than one module; each store's ownership on the way."""
    violations = [{'id': f'own:{eid}', 'subject': eid, 'kind': 'endpoint', 'tier': 'client', 'writers': sorted(endpoint['writers'])}
                  for eid, endpoint in sorted(inventory.endpoints.items()) if len(endpoint['writers']) > 1]
    for sid, store in sorted(inventory.stores.items()):
        writers = inventory.writers_of.get(sid, set())
        if store['kind'] == 'table' and len(writers) > 1:
            violations.append({'id': f'own:{sid}', 'subject': sid, 'kind': 'table', 'tier': 'client', 'writers': sorted(writers)})
        _ownership(store, writers, inventory, grouping)
    return violations


def _tiers(paths, gap_count):
    tiers = []
    for tier in TIERS:
        known = sum(p['steps'][tier]['state'] in ('known', 'direct') for p in paths)
        reasons = sorted({reason for (t, reason) in gap_count if t == tier})
        state = 'empty' if not paths else 'not_measured' if not known else 'partial' if known < len(paths) else 'measured'
        tiers.append({'id': tier, 'state': state,
                      'known': _measure(known if paths else None, f'paths[].steps.{tier}.state in known, direct'),
                      'gaps': [{'reason': r, 'paths': gap_count[(tier, r)], 'step': GAPS[r]} for r in reasons]})
    return tiers


def _counts(inventory, violations, gap_count, has_target):
    stores, paths = inventory.stores, inventory.paths
    writers_total, readers_total = _modules(inventory.writers_of), _modules(inventory.readers_of)
    return {
        'stores': _measure(len(stores), SRC['stores']),
        'tables': _measure(sum(s['kind'] == 'table' for s in stores.values()), SRC['stores'] + ' (kind table)'),
        'endpoints': _measure(len(inventory.endpoints), SRC['endpoints']),
        'writers': _measure(len(writers_total), SRC['writers']),
        'readers': _measure(len(readers_total), SRC['readers']),
        'write_paths': _measure(len(paths), SRC['writers'] + ' (call sites)'),
        'attributes': _measure(len(_attributes(paths)), SRC['keys'] + ' (distinct store and key)'),
        'multi_writer_endpoints': _measure(sum(v['kind'] == 'endpoint' for v in violations), 'violations[kind=endpoint]'),
        'multi_writer_tables': _measure(sum(v['kind'] == 'table' for v in violations), 'violations[kind=table]'),
        'gaps': _measure(sum(gap_count.values()), 'paths[].steps[state=gap] (count)'),
        'single_in_target': _measure(sum(1 for s in stores.values() if (s.get('target') or {}).get('single')) if has_target else None,
                                     SRC['target'] + ': stores written from one target component'),
    }


def _modules(of):
    """The distinct modules of {store: the modules that write (or read) it}."""
    return {m for s in of.values() for m in s}


def _attributes(paths):
    """Counter {(store, key): write paths sending that key to that store}."""
    attributes = Counter()
    for p in paths:
        for key in p['steps']['key'].get('keys') or []: attributes[(p['store'], key)] += 1
    return attributes


def _app_access(report):
    """The data_access facts outside the tests."""
    return [f for f in arch_map.facts(report, 'entrypoints', 'data_access') if (f.get('value') or {}).get('category') != 'test']


def _gap_count(paths):
    """Counter {(tier, reason): the write paths that stop at that tier for that reason}."""
    return Counter((tier, step['reason']) for p in paths for tier, step in p['steps'].items() if step['state'] == 'gap')


def data_paths(report, lang='ar'):
    """The section's body: {counts, tiers, stores, endpoints, paths, violations, current, target, change, src}."""
    report = Path(report)
    access = _app_access(report)
    declared = _declared(report)
    owner, goes, has_target = _component_of(report)
    servers = _servers(report)
    inventory = _Inventory(declared, (owner, servers, bool(servers)))
    for fact in sorted(access, key=lambda f: (arch_map.path_of(f), (f.get('location') or {}).get('start_line') or 0, f.get('id') or '')):
        inventory.add(fact)
    stores, endpoints, paths = inventory.stores, inventory.endpoints, inventory.paths
    for sid, entry in declared.items():  # a table the code declares but no call reaches is still a store
        stores.setdefault(sid, {'id': sid, 'kind': 'table', 'name': sid.split(':', 1)[1], 'client': None,
                                'declared': entry, 'endpoints': [], 'sites': 0})

    group_today = lambda module: owner(module) or module
    group_target = lambda module: goes.get(owner(module)) if owner(module) else None
    violations = _violations(inventory, ((group_today, group_target), has_target))

    store_ids = sorted(stores)
    edges_of, families = (inventory.writers_of, inventory.readers_of), FAMILIES
    current, clusters = view(edges_of, store_ids, group_today, families)
    target = None
    if has_target:
        target, _ = view(edges_of, store_ids, group_target, families,
                          pinned={'order': current['lanes']['store'], 'clusters': clusters})

    gap_count = _gap_count(paths)
    tiers = _tiers(paths, gap_count)
    for item in endpoints.values():
        item.update(writers=sorted(item['writers']), readers=sorted(item['readers']), keys=sorted(item['keys']) or None,
                    multi_writer=len(item['writers']) > 1)
    return {
        'counts': _counts(inventory, violations, gap_count, has_target),
        'tiers': tiers,
        'stores': [stores[s] for s in store_ids],
        'endpoints': [endpoints[e] for e in sorted(endpoints)],
        'paths': paths,
        'violations': violations,
        'current': current,
        'target': target,
        'src': SRC,
    }
