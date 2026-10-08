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

The overview is laid out here (callers and stores in two lanes, ordered by barycentre sweeps with
eaos/arch_map.order_columns; the target's components ordered against the same, pinned, stores), so every view and
every reader draws the same places. Above MAX_LANE nodes a lane is clustered and each cluster expands on request.
"""
import re
from collections import Counter, defaultdict
from pathlib import Path

from .. import arch_map
from .system import owner_of

MAX_LANE = 40
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
LANE_X = {'caller': 0, 'store': 1}
BOX_W, BOX_H, ROW_GAP, LANE_GAP, PAD = 220, 34, 10, 300, 24
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
    if client == 'supabase':
        if target == AUTH or op in ('getSession', 'getUser', 'signOut', 'signUp', 'signIn', 'signInWithPassword',
                                    'signInWithOAuth', 'resetPasswordForEmail', 'updateUser', 'onAuthStateChange'):
            return 'auth:supabase', 'auth', 'Supabase Auth'
        if op == 'storage': return f'bucket:{target}', 'bucket', target
        if op == 'rpc': return f'rpc:{target}', 'rpc', target
        return f'table:{table_name(target)}', 'table', table_name(target)
    if client == 'http':
        if target in ('', '{dynamic}', '/{}'): return 'api:{dynamic}', 'resource', '{dynamic}'
        head = route_key(target).split('/')[1] if route_key(target) != '/' else ''
        return f'api:/{head}', 'resource', '/' + next((p for p in target.split('/') if p), head)
    return None


def _endpoint_of(value):
    client, target, op = value.get('client'), str(value.get('target') or ''), str(value.get('operation') or '')
    if client == 'http': return f'ep:{op.upper()} {route_key(target)}', f'{op.upper()} {target}'
    return f'ep:{client}:{op} {target}', f'{op} {target}'


def _site(fact):
    location = fact.get('location') or {}
    return {'path': location.get('path') or '', 'line': location.get('start_line'), 'fact': fact.get('id')}


def _component_of(report):
    """(owner(path) -> current component name | None, {current name: target name}, target known)."""
    record = arch_map._load(Path(report) / 'target-architecture.json', {}) or {}
    comps = [c for c in record.get('current_components') or [] if isinstance(c, dict) and c.get('name')]
    owner = owner_of([c['name'] for c in comps]) if comps else (lambda path: None)
    goes = {c['name']: c.get('target_component') for c in comps}
    return owner, goes, bool(record.get('target_components'))


def _servers(report):
    """{(METHOD, route key): {handler, path, line, fact, writes: [(store id, columns, fact)]}} from the server routes the
    repository declares, with the writes their flows reach."""
    access_by_file = defaultdict(list)
    for fact in arch_map.facts(report, 'entrypoints', 'data_access'):
        access_by_file[arch_map.path_of(fact)].append(fact)
    touched = {}
    for flow in arch_map.facts(report, 'flows', 'flow'):
        value = flow.get('value') or {}
        entry = value.get('entry') or {}
        if entry.get('surface') == 'http' and entry.get('route'):
            touched[(str(entry.get('http_method') or '').upper(), route_key(entry['route']))] = (flow.get('id'), value.get('touched_files') or [])
    out = {}
    for fact in arch_map.facts(report, 'entrypoints', 'entry_point'):
        value = fact.get('value') or {}
        if value.get('surface') != 'http' or not value.get('route') or value.get('category') == 'test': continue
        key = (str(value.get('http_method') or 'GET').upper(), route_key(value['route']))
        flow_id, files = touched.get(key, (None, [arch_map.path_of(fact)]))
        writes = []
        for path in sorted(set(files)):
            for access in access_by_file.get(path, []):
                v = access.get('value') or {}
                store = _store_of(v)
                if store and v.get('operation') in WRITES and store[1] == 'table':
                    writes.append({'store': store[0], 'columns': v.get('keys'), 'fact': access.get('id')})
        out.setdefault(key, {'handler': value.get('handler'), **_site(fact), 'flow': flow_id, 'writes': writes})
    return out


def _cluster(ids, family, limit=MAX_LANE):
    """{id: cluster id} when a lane holds more than `limit` nodes: by family, then families folded alphabetically into
    at most `limit` buckets. {} when the lane fits."""
    if len(ids) <= limit: return {}
    families = defaultdict(list)
    for node in sorted(ids): families[family(node)].append(node)
    names = sorted(families)
    if len(names) > limit:
        size = -(-len(names) // limit)
        groups = {name: f'{names[i - i % size]}…{names[min(i - i % size + size, len(names)) - 1]}' for i, name in enumerate(names)}
    else:
        groups = {name: name for name in names}
    return {node: f'cluster:{groups[family(node)]}' for node in ids}


def _lane_positions(columns):
    """{id: (x, y)}: each lane a column of boxes, top-aligned, in its order."""
    out = {}
    for lane, column in columns.items():
        for p, node in enumerate(column):
            out[node] = (PAD + LANE_X[lane] * (BOX_W + LANE_GAP), PAD + p * (BOX_H + ROW_GAP))
    return out


def _layout(callers, stores, edges, pinned=None):
    """Lane orders and positions. Stores keep `pinned` order when given (the target view), callers follow them."""
    if pinned is None:
        layer = {**{c: 0 for c in callers}, **{s: 1 for s in stores}}
        columns = arch_map.order_columns(layer, sorted(edges)) if layer else [[], []]
        columns = (columns + [[], []])[:2]
        order = {'caller': columns[0], 'store': columns[1]}
    else:
        place = {s: i for i, s in enumerate(pinned)}
        near = defaultdict(list)
        for a, b in edges: near[a].append(place.get(b, len(place)))
        order = {'caller': sorted(callers, key=lambda c: (sum(near[c]) / len(near[c]) if near[c] else len(place), c)),
                 'store': list(pinned)}
    xy = _lane_positions(order)
    tallest = max((len(v) for v in order.values()), default=0)
    size = [PAD * 2 + 2 * BOX_W + LANE_GAP, PAD * 2 + max(tallest, 1) * (BOX_H + ROW_GAP) - ROW_GAP]
    return order, xy, size


def _view(writers_of, readers_of, stores, group_of, store_family, caller_family, pinned=None):
    """One overview: lanes of callers (grouped as `group_of` says) and stores, clustered above MAX_LANE, with their
    weighted write and read edges, laid out."""
    callers = sorted({group_of(m) for s in stores for m in writers_of.get(s, set()) | readers_of.get(s, set())} - {None})
    caller_cluster = _cluster(callers, caller_family)
    store_cluster = _cluster(list(stores), store_family) if pinned is None else pinned['clusters']
    lane_caller = lambda c: caller_cluster.get(c, c)
    lane_store = lambda s: store_cluster.get(s, s)
    weight = Counter()
    for s in stores:
        for kind, modules in (('write', writers_of.get(s, set())), ('read', readers_of.get(s, set()) - writers_of.get(s, set()))):
            for m in modules:
                group = group_of(m)
                if group is not None: weight[(lane_caller(group), lane_store(s), kind)] += 1
    caller_nodes = sorted({lane_caller(c) for c in callers})
    store_nodes = sorted({lane_store(s) for s in stores})
    pairs = {(a, b) for a, b, _ in weight}
    order, xy, size = _layout(caller_nodes, store_nodes, pairs, pinned and pinned['order'])
    edges = [{'from': a, 'to': b, 'kind': kind, 'modules': n} for (a, b, kind), n in sorted(weight.items())]
    clusters = []
    for lane, mapping in (('caller', caller_cluster), ('store', store_cluster if pinned is None else {})):
        members = defaultdict(list)
        for node, cluster in mapping.items(): members[cluster].append(node)
        clusters += [{'id': cid, 'lane': lane, 'members': sorted(m)} for cid, m in sorted(members.items())]
    return {'lanes': {'caller': order['caller'], 'store': order['store']},
            'place': {node: [round(x), round(y)] for node, (x, y) in sorted(xy.items())},
            'size': size, 'box': [BOX_W, BOX_H], 'edges': edges, 'clusters': clusters}, store_cluster


def data_paths(report, lang='ar'):
    """The section's body: {counts, tiers, stores, endpoints, paths, violations, current, target, change, src}."""
    report = Path(report)
    access = [f for f in arch_map.facts(report, 'entrypoints', 'data_access')
              if (f.get('value') or {}).get('category') != 'test']
    declared = {}
    for fact in arch_map.facts(report, 'domain', 'data_table'):
        value = fact.get('value') or {}
        if value.get('dropped'): continue
        declared.setdefault(f"table:{table_name(value.get('name'))}", {**_site(fact), 'rls': value.get('rls_enabled')})
    owner, goes, has_target = _component_of(report)
    servers = _servers(report)
    has_server = bool(servers)

    stores, endpoints = {}, {}
    writers_of, readers_of = defaultdict(set), defaultdict(set)
    paths = []
    for fact in sorted(access, key=lambda f: (arch_map.path_of(f), (f.get('location') or {}).get('start_line') or 0, f.get('id') or '')):
        value = fact.get('value') or {}
        store = _store_of(value)
        if not store: continue
        sid, kind, name = store
        op = str(value.get('operation') or '')
        module = arch_map.path_of(fact)
        stores.setdefault(sid, {'id': sid, 'kind': kind, 'name': name, 'client': value.get('client'),
                                'declared': declared.get(sid), 'endpoints': [], 'sites': 0})
        stores[sid]['sites'] += 1
        eid, label = _endpoint_of(value)
        endpoint = endpoints.setdefault(eid, {'id': eid, 'label': label, 'store': sid, 'operation': op,
                                              'method': op.upper() if value.get('client') == 'http' else None,
                                              'writers': set(), 'readers': set(), 'keys': set(), 'sites': []})
        if eid not in stores[sid]['endpoints']: stores[sid]['endpoints'].append(eid)
        endpoint['sites'].append(_site(fact))
        writes = op in WRITES
        (endpoint['writers'] if writes else endpoint['readers']).add(module)
        (writers_of if writes else readers_of)[sid].add(module)
        if not writes: continue
        keys = value.get('keys')
        if keys: endpoint['keys'].update(keys)
        server = servers.get((op.upper(), route_key(value.get('target')))) if value.get('client') == 'http' else None
        steps = {'field': {'state': 'gap', 'reason': 'no_ui_extractor'},
                 'form': {'state': 'gap', 'reason': 'no_ui_extractor'},
                 'key': ({'state': 'known', 'keys': keys, 'partial': bool(value.get('keys_partial'))} if keys is not None
                         else {'state': 'gap', 'reason': 'payload_not_literal'}),
                 'caller': {'state': 'known', 'component': owner(module)},  # the module is the path's site
                 'endpoint': {'state': 'known'}}                           # the endpoint is the path's own
        if value.get('client') != 'http':
            steps['handler'] = {'state': 'direct', 'reason': 'direct_database_client'}
            steps['column'] = ({'state': 'known', 'columns': keys} if kind == 'table' and keys is not None else
                               {'state': 'known', 'columns': None} if kind != 'table' else
                               {'state': 'gap', 'reason': 'payload_not_literal'})
        elif server:
            steps['handler'] = {'state': 'known', 'handler': server['handler'], 'path': server['path'],
                                'line': server['line'], 'fact': server['fact'], 'flow': server['flow']}
            reached = [w for w in server['writes'] if w['store']]
            steps['column'] = ({'state': 'known', 'stores': sorted({w['store'] for w in reached}),
                                'columns': sorted({c for w in reached for c in w['columns'] or []}) or None}
                               if reached else {'state': 'gap', 'reason': 'handler_writes_unseen'})
        else:
            steps['handler'] = {'state': 'gap', 'reason': 'no_matching_route' if has_server else 'backend_outside_snapshot'}
            steps['column'] = {'state': 'gap', 'reason': 'behind_handler'}
        paths.append({'store': sid, 'endpoint': eid, 'site': _site(fact), 'steps': steps})

    for sid, entry in declared.items():  # a table the code declares but no call reaches is still a store
        stores.setdefault(sid, {'id': sid, 'kind': 'table', 'name': sid.split(':', 1)[1], 'client': None,
                                'declared': entry, 'endpoints': [], 'sites': 0})

    group_today = lambda module: owner(module) or module
    group_target = lambda module: goes.get(owner(module)) if owner(module) else None
    violations = []
    for eid, endpoint in sorted(endpoints.items()):
        if len(endpoint['writers']) > 1:
            violations.append({'id': f'own:{eid}', 'subject': eid, 'kind': 'endpoint', 'tier': 'client',
                               'writers': sorted(endpoint['writers'])})
    for sid, store in sorted(stores.items()):
        writers = writers_of.get(sid, set())
        if store['kind'] == 'table' and len(writers) > 1:
            violations.append({'id': f'own:{sid}', 'subject': sid, 'kind': 'table', 'tier': 'client', 'writers': sorted(writers)})
        today = sorted({group_today(m) for m in writers})
        later = sorted({group_target(m) for m in writers} - {None}) if has_target else None
        store.update(
            writers=sorted(writers), readers=sorted(readers_of.get(sid, set())),
            multi_writer=len(writers) > 1,
            today={'writers': len(writers), 'components': today},
            target=None if later is None else {'components': later, 'single': len(later) <= 1 if writers else None,
                                               'unmapped': sorted(m for m in writers if group_target(m) is None)},
        )
        store['change'] = (None if later is None or not writers else
                           'single_already' if len(writers) == 1 else
                           'merged_in_target' if len(later) == 1 and not store['target']['unmapped'] else 'still_multiple')

    def family_store(sid):
        kind, _, name = sid.partition(':')
        return f"{kind}:{re.split(r'[_/.]', name.lstrip('/'))[0][:12] or name}"

    def family_caller(name):
        return '/'.join(str(name).split('/')[:2])

    store_ids = sorted(stores)
    current, clusters = _view(writers_of, readers_of, store_ids, group_today, family_store, family_caller)
    target = None
    if has_target:
        target, _ = _view(writers_of, readers_of, store_ids, group_target, family_store, family_caller,
                          pinned={'order': current['lanes']['store'], 'clusters': clusters})

    gap_count = Counter((tier, step['reason']) for p in paths for tier, step in p['steps'].items() if step['state'] == 'gap')
    tiers = []
    for tier in TIERS:
        known = sum(p['steps'][tier]['state'] in ('known', 'direct') for p in paths)
        reasons = sorted({reason for (t, reason) in gap_count if t == tier})
        state = 'empty' if not paths else 'not_measured' if not known else 'partial' if known < len(paths) else 'measured'
        tiers.append({'id': tier, 'state': state,
                      'known': _measure(known if paths else None, f'paths[].steps.{tier}.state in known, direct'),
                      'gaps': [{'reason': r, 'paths': gap_count[(tier, r)], 'step': GAPS[r]} for r in reasons]})
    for item in endpoints.values():
        item.update(writers=sorted(item['writers']), readers=sorted(item['readers']), keys=sorted(item['keys']) or None,
                    multi_writer=len(item['writers']) > 1)
    attributes = Counter()
    for p in paths:
        for key in p['steps']['key'].get('keys') or []: attributes[(p['store'], key)] += 1
    writers_total = {m for s in writers_of.values() for m in s}
    readers_total = {m for s in readers_of.values() for m in s}
    return {
        'counts': {
            'stores': _measure(len(stores), SRC['stores']),
            'tables': _measure(sum(s['kind'] == 'table' for s in stores.values()), SRC['stores'] + ' (kind table)'),
            'endpoints': _measure(len(endpoints), SRC['endpoints']),
            'writers': _measure(len(writers_total), SRC['writers']),
            'readers': _measure(len(readers_total), SRC['readers']),
            'write_paths': _measure(len(paths), SRC['writers'] + ' (call sites)'),
            'attributes': _measure(len(attributes), SRC['keys'] + ' (distinct store and key)'),
            'multi_writer_endpoints': _measure(sum(v['kind'] == 'endpoint' for v in violations), 'violations[kind=endpoint]'),
            'multi_writer_tables': _measure(sum(v['kind'] == 'table' for v in violations), 'violations[kind=table]'),
            'gaps': _measure(sum(gap_count.values()), 'paths[].steps[state=gap] (count)'),
            'single_in_target': _measure(sum(1 for s in stores.values() if (s.get('target') or {}).get('single')) if has_target else None,
                                         SRC['target'] + ': stores written from one target component'),
        },
        'tiers': tiers,
        'stores': [stores[s] for s in store_ids],
        'endpoints': [endpoints[e] for e in sorted(endpoints)],
        'paths': paths,
        'violations': violations,
        'current': current,
        'target': target,
        'src': SRC,
    }
