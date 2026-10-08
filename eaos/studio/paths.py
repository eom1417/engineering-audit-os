"""studio/paths.json: the code paths of the project and the plan's timeline (contract v2, docs/STUDIO.md "Code paths").

A path follows one entry of the project through its layers, drawn as swimlanes:

    screen -> component -> handler -> call -> endpoint -> service -> data

Every node and every link is read from records the check already wrote, and carries its evidence (the fact, the file
and the line). Where the records stop, the path draws a gap node in the lane where it stopped, with the reason; it
never invents the next step. The links and how each is found (`how`):

    screen -> component    `route`: a page entry point (facts/entrypoints.json) names its component; its file is the
                           page's flow's first caller, else the one file defining that name (system_map.component_file).
                           No such file is a `component_not_found` gap.
    component -> handler   the function holding an HTTP or database call (data_access) in a file the component reaches:
                           `contains` in the component's own file, `call` when the page's flow (facts/flows.json)
                           reaches that file, `imports` when only the resolved imports (facts/graph.json, two steps) do
    handler -> call        `request`: the data_access fact itself, a method and URL or the table a database client names
    call -> endpoint       `route`: a server route entry point with the same method and path; `file_route`: a candidate,
                           a file-routed handler whose path spells the URL (system_map.find_handlers). None is a
                           `no_server_route` gap, unless the URL leaves the project (`external`, in the data lane), or
                           the client names a table (`client`, straight to the data lane)
    endpoint -> service    the parts of today (target-architecture.json current_components) holding the files the
                           handler's flow calls into (`call`), else the files its imports reach in three steps (`imports`)
    -> data                `defines`: a table defined in a file the handler reaches (facts/domain.json data_table);
                           `package`: a database or outside service a reached file imports (system_map.SERVICES)
    trace gaps             the calls an entry's flow could not resolve (unresolved or ambiguous): one `trace_stopped`
                           gap node per path, listing them; a server entry with no traceable handler is
                           `handler_not_found`

Each node names the part of today that owns its file; `components` gives that part's operation toward the target
(retain, refactor, rebuild, merge, delete), its target part and the target's layer, and `new` the target parts nothing
of today feeds. The cards on a node's file come with the plan steps holding them. The Studio draws Current, Target and
Change from the same nodes, so a node keeps its place between views.

The timeline is the fix plan (plan.json) in the order it runs: its waves, each task's step, and what each task waits
for: a prerequisite the plan names, or the last task of an earlier wave touching the same file (eaos/plan.py waves()).
"""
import re
from collections import Counter, defaultdict
from pathlib import Path

from .. import arch_map, system_map as sm
from . import system as system_section

LANES = ('screen', 'component', 'handler', 'call', 'endpoint', 'service', 'data')
OPERATION = {'retain': 'retain', 'modify': 'refactor', 'rebuild': 'rebuild', 'delete': 'delete', 'retire': 'delete'}
SERVER = ('http', 'endpoint', 'api', 'route', 'rpc', 'job', 'queue', 'cli', 'worker', 'webhook', 'cron', 'tool')
FUNCTIONS = ('function', 'method')
IMPORT_STEPS = 2          # a component reaches the files that make its calls through at most two imports
SERVER_STEPS = 3          # a handler reaches the parts behind it through at most three imports
MAX_CALLS = 60            # calls drawn per path; the rest are counted in the path's `capped`
MAX_ITEMS = 12            # unresolved calls listed on a trace gap
MAX_CARDS = 20
MAX_WAITS = 6
CLUSTER_AT = 1000         # past this many nodes the Studio never draws every step at once, only the clusters
MAX_CLUSTERS = 150        # the overview's clusters, at most (DESIGN.md §6: SVG stays readable to about 300 nodes)
SRC = {
    'paths': 'facts/entrypoints.json#entry_point (a page, or a server route, command or job with a handler)',
    'calls': 'facts/entrypoints.json#data_access',
    'flows': 'facts/flows.json#flow',
    'imports': 'facts/graph.json#graph_node.depends_on',
    'routes': 'facts/entrypoints.json#entry_point (server routes) and file routing (eaos/system_map.py find_handlers)',
    'tables': 'facts/domain.json#data_table',
    'components': 'target-architecture.json#current_components, target_components',
    'cards': 'cards.json#cards[].paths, milestone',
    'timeline': 'plan.json#waves, milestones, tasks[].prerequisites, tasks[].paths (eaos/plan.py waves())',
}


def _measure(value, src):
    return {'value': value, 'src': src, 'unit': 'count'}


def _line(value):
    return value if isinstance(value, int) and value >= 0 else None


def _slug(text):
    return re.sub(r'[^a-z0-9]+', '-', str(text).lower()).strip('-') or 'root'


def _fact_id(fact):
    return fact.get('id') if isinstance(fact, dict) and isinstance(fact.get('id'), str) else None


# ---------------------------------------------------------------- reading

def _enclosing(functions, path, line):
    """The function holding a line: the outermost top-level function around it, else the innermost one; None outside."""
    around = [f for f in functions.get(path, ()) if f['start'] <= (line or 0) <= f['end']]
    top = [f for f in around if not f['parent']]
    pick = min(top, key=lambda f: f['start']) if top else (max(around, key=lambda f: f['start']) if around else None)
    return pick['name'] if pick else None


def _read(report):
    """The records the paths read, each piece empty when its record is missing or broken."""
    report = Path(report)
    r = {'pages': [], 'servers': [], 'routes': [], 'calls': defaultdict(list), 'flows': {}, 'flow_of': {}, 'flow_list': [],
         'functions': defaultdict(list), 'names': defaultdict(set), 'methods': defaultdict(set), 'packages': defaultdict(set),
         'imports': {}, 'tables': defaultdict(list)}
    for fact in sm._facts(report, 'syntax', 'symbol', 'import_edge'):
        value, loc, path = fact.get('value') or {}, fact.get('location') or {}, sm._path(fact)
        if sm.is_test(path): continue
        if fact['kind'] == 'import_edge':
            if value.get('style') == 'absolute' and value.get('module'): r['packages'][path].add(str(value['module']))
            continue
        name = str(value.get('name') or '')
        if value.get('exported') and name.upper() in sm.METHODS and name.isupper(): r['methods'][path].add(name)
        if name and not value.get('parent'): r['names'][name].add(path)
        if value.get('kind') in FUNCTIONS and isinstance(loc.get('start_line'), int):
            r['functions'][path].append({'name': name, 'parent': value.get('parent'), 'start': loc['start_line'],
                                         'end': loc.get('end_line') or loc['start_line']})
    for node in sm._facts(report, 'graph', 'graph_node'):
        r['imports'][sm._path(node)] = [d for d in (node.get('value') or {}).get('depends_on') or [] if isinstance(d, str)]
    for fact in sm._facts(report, 'entrypoints', 'entry_point', 'data_access'):
        value, path, loc = fact.get('value') or {}, sm._path(fact), fact.get('location') or {}
        if not isinstance(value, dict) or not path or sm.is_test(path) or value.get('category') == 'test': continue
        line = _line(loc.get('start_line'))
        if fact['kind'] == 'entry_point':
            entry = {'fact': fact, 'path': path, 'line': line, 'surface': str(value.get('surface') or ''),
                     'route': str(value.get('route') or ''), 'method': value.get('http_method'), 'handler': value.get('handler')}
            if entry['surface'] == 'page': r['pages'].append(entry)
            elif entry['surface'] in SERVER or entry['method']:
                if entry['surface'] in ('http', 'endpoint', 'api', 'route', 'rpc') or entry['method']:
                    r['routes'].append({'route': sm.clean_path(entry['route']), 'method': str(entry['method'] or 'ANY').upper(),
                                        'handler': entry['handler'], 'file': path, 'fact': fact})
                if entry['handler']: r['servers'].append(entry)
            continue
        if not value.get('target'): continue
        client = str(value.get('client') or 'http')
        if client in ('http', 'fetch', 'axios'):
            method = str(value.get('operation') or 'get').upper()
            method = method if method in sm.METHODS else 'GET'
            url = sm.clean_path(value['target']) or '…'      # a URL built at run time: the call stays, its route unknown
            call = {'id': f'A:{method} {url}', 'label': f'{method} {url}', 'url': url, 'method': method, 'table': None,
                    'group': sm.api_group(url)}
        else:
            operation, table = str(value.get('operation') or 'query'), str(value['target'])
            call = {'id': f'A:{client} {operation} {table}', 'label': f'{client} {operation} {table}', 'url': None,
                    'method': operation, 'table': table, 'group': client}
        r['calls'][path].append({**call, 'fact': fact, 'path': path, 'line': line,
                                 'function': _enclosing(r['functions'], path, line)})
    for rows in r['calls'].values(): rows.sort(key=lambda c: (c['line'] or 0, c['id']))
    for fact in sm._facts(report, 'flows', 'flow'):
        value = fact.get('value') or {}
        entry = value.get('entry') or {}
        for route in [entry.get('route')] + [a.get('route') for a in value.get('also_reached_by') or [] if isinstance(a, dict)]:
            r['flows'].setdefault((entry.get('path'), entry.get('handler'), route), fact)
        r['flow_of'].setdefault((entry.get('path'), entry.get('handler')), fact)
        first = next((s.get('from_path') for s in value.get('steps') or [] if isinstance(s, dict) and s.get('from') == entry.get('handler')), None)
        r['flow_list'].append({'surface': entry.get('surface'), 'route': entry.get('route'), 'handler': entry.get('handler'),
                               'file': first})
    for fact in sm._facts(report, 'domain', 'data_table'):
        name, path = str((fact.get('value') or {}).get('name') or ''), sm._path(fact)
        if len(name) > 1 and name.lower() not in sm.NOT_TABLES and not sm.is_test(path): r['tables'][path].append((name, fact))
    return r


def components(report):
    """({part of today: {op, target, layer}}, owner of a path, the target parts nothing of today feeds)."""
    target = sm._load(Path(report) / 'target-architecture.json', {}) or {}
    target = target if isinstance(target, dict) else {}
    current = [c for c in target.get('current_components') or [] if isinstance(c, dict) and c.get('name')]
    layers = {t['name']: t.get('layer') for t in target.get('target_components') or [] if isinstance(t, dict) and t.get('name')}
    feeds = Counter(c.get('target_component') for c in current if c.get('target_component'))
    out = {}
    for c in current:
        to = c.get('target_component')
        relation = OPERATION.get(c.get('relation'), 'refactor')
        # a part kept or refactored into a target that others feed too is merged; a rebuild or a delete says more
        out[c['name']] = {'op': 'merge' if to and feeds[to] > 1 and relation in ('retain', 'refactor') else relation, 'target': to,
                          'layer': layers.get(to)}
    return out, system_section.owner_of(set(out)), sorted(name for name in layers if not feeds.get(name))


# ---------------------------------------------------------------- the graph of every path

class _Graph:
    """The nodes and links of every path, each stored once; a path lists the links it walks, in order."""

    def __init__(self, owner, cards_of):
        self.nodes, self.edges, self.index = {}, [], {}
        self.owner, self.cards_of = owner, cards_of

    def node(self, nid, lane, label, kind='step', path=None, line=None, fact=None, part=None, **extra):
        if nid not in self.nodes:
            cards, steps = self.cards_of(path) if path and kind != 'gap' else ([], [])
            self.nodes[nid] = {'id': nid, 'lane': lane, 'kind': kind, 'label': str(label)[:200], 'path': path or None,
                               'line': _line(line), 'fact': _fact_id(fact),
                               'component': None if kind == 'gap' else part or (self.owner(path) if path else None),
                               'cards': cards, 'steps': steps, 'reason': None, 'detail': None, 'items': [], 'group': None, **extra}
        return nid

    def link(self, a, b, how, fact=None, path=None, line=None):
        key = (a, b, how)
        if key not in self.index:
            self.index[key] = len(self.edges)
            self.edges.append({'from': a, 'to': b, 'how': how, 'fact': _fact_id(fact), 'path': path or None, 'line': _line(line)})
        return self.index[key]

    def gap(self, nid, lane, reason, label, detail=None, items=()):
        self.node(nid, lane, label, kind='gap')
        self.nodes[nid].update(reason=reason, detail=detail, items=list(items)[:MAX_ITEMS])
        return nid


class _Builder:
    def __init__(self, r, owner, cards_of):
        self.r, self.owner, self.g = r, owner, _Graph(owner, cards_of)
        self.behind = {}            # endpoint node -> the links behind it, walked once and reused by every path

    def trace_gap(self, pid, lane, origin, flow, steps):
        value = (flow or {}).get('value') or {}
        stops = [s for s in value.get('steps') or [] if isinstance(s, dict) and s.get('resolution') in ('unresolved', 'ambiguous')]
        count = value.get('unresolved_steps')
        if not stops and not count: return 0
        items = [{'callee': str(s.get('callee') or ''), 'path': s.get('from_path'), 'line': _line(s.get('line')),
                  'resolution': s.get('resolution')} for s in stops]
        gid = self.g.gap(f'G:trace:{pid}', lane, 'trace_stopped', value.get('flow_id') or pid,
                         detail=str(count if isinstance(count, int) else len(stops)), items=items)
        steps.append(self.g.link(origin, gid, 'trace', flow, (flow.get('location') or {}).get('path'), (flow.get('location') or {}).get('start_line')))
        return count if isinstance(count, int) else len(stops)

    def server_side(self, origin, start, flow):
        """The links behind a server-side handler file: the parts it calls or imports, the tables and services."""
        if origin in self.behind: return self.behind[origin]
        g, r, steps = self.g, self.r, []
        called = []
        for step in ((flow or {}).get('value') or {}).get('steps') or []:
            to = step.get('to_path') if isinstance(step, dict) else None
            if step.get('resolution') in ('local', 'imported') and to and to != start and not sm.is_test(to): called.append((to, step))
        reached = {to for to, _ in called}
        home, seen = self.owner(start), set()
        for to, step in called:
            part = self.owner(to)
            if not part or part == home or part in seen: continue
            seen.add(part)
            steps.append(g.link(origin, g.node(f'M:{part}', 'service', part, part=part), 'call', flow, step.get('from_path'), step.get('line')))
        for to in sorted(sm._reach(start, r['imports'], SERVER_STEPS) - {start}):
            part = self.owner(to)
            if not part or part == home or part in seen or sm.is_test(to): continue
            seen.add(part)
            steps.append(g.link(origin, g.node(f'M:{part}', 'service', part, part=part), 'imports', None, start, None))
        near = {start} | reached | sm._reach(start, r['imports'], SERVER_STEPS - 1)
        for file in sorted(near):
            for name, fact in r['tables'].get(file, ()):
                where, line = sm._path(fact), (fact.get('location') or {}).get('start_line')
                steps.append(g.link(origin, g.node(f'T:{name}', 'data', name, kind='table', path=where, line=line, fact=fact),
                                    'defines', fact, where, line))
        services = defaultdict(set)
        for file in sorted(near | sm._reach(start, r['imports'], SERVER_STEPS + 1)):
            for package in r['packages'].get(file, ()):
                if package in sm.SERVICES: services[sm.SERVICES[package]].add(file)
        for (kind, en, ar), files in sorted(services.items()):
            nid = g.node(f'X:{en}', 'data', en, kind='store' if kind == 'storage' else 'external', ar=ar)
            steps.append(g.link(origin, nid, 'package', None, sorted(files)[0], None))
        self.behind[origin] = steps
        return steps

    def onward(self, aid, call):
        """The links after a call: its endpoint and what stands behind it, its table, its outside service, or a gap."""
        g, steps = self.g, []
        if call['table']:
            steps.append(g.link(aid, g.node(f"T:{call['table']}", 'data', call['table'], kind='table'), 'client',
                                call['fact'], call['path'], call['line']))
            return steps
        if '://' in call['url']:
            host = call['url'].split('/')[2] if call['url'].count('/') >= 2 else call['url']
            steps.append(g.link(aid, g.node(f'X:{host}', 'data', host, kind='external'), 'external', call['fact'], call['path'], call['line']))
            return steps
        found, exact = sm.find_handlers(call['method'], call['url'], self.r['routes'], self.r['methods'])
        if not found:
            gid = g.gap(f"G:endpoint:{call['id'][2:]}", 'endpoint', 'no_server_route', call['label'])
            g.nodes[gid]['group'] = call['group']
            steps.append(g.link(aid, gid, 'gap'))
            return steps
        for file, function, how in found:
            route = next((x for x in self.r['routes'] if x['file'] == file and sm.same_route(x['route'], call['url'])), None)
            eid = g.node(f"E:{file}#{function or ''}", 'endpoint', function or Path(file).name, path=file,
                         line=(route or {}).get('fact', {}).get('location', {}).get('start_line') if route else None,
                         fact=(route or {}).get('fact'))
            exact_route = how == 'entry point' and exact
            steps.append(g.link(aid, eid, 'route' if exact_route else 'file_route', (route or {}).get('fact'), file,
                                g.nodes[eid]['line']))
            flow = self.r['flow_of'].get((file, (route or {}).get('handler') or function))
            steps += self.server_side(eid, file, flow)
        return steps

    def page(self, pid, entry):
        g, r = self.g, self.r
        sid = g.node(f"S:{entry['route']} {entry['handler'] or ''}".rstrip(), 'screen', entry['route'] or '/', path=entry['path'],
                     line=entry['line'], fact=entry['fact'], group=sm.api_group(entry['route'] or '/'))
        steps, capped, unresolved = [], 0, None
        flow = r['flows'].get((entry['path'], entry['handler'], entry['route']))
        comp = sm.component_file({'route': entry['route'], 'component': str(entry['handler'] or ''), 'router': entry['path']},
                                 r['flow_list'], r['names'], r['imports'])
        if comp == entry['path']: comp = None
        if not comp:
            steps.append(g.link(sid, g.gap(f'G:component:{pid}', 'component', 'component_not_found', entry['handler'] or entry['route']),
                                'route', entry['fact'], entry['path'], entry['line']))
            return sid, steps, flow, 0, None
        cid = g.node(f'C:{comp}', 'component', entry['handler'] or Path(comp).stem, path=comp)
        steps.append(g.link(sid, cid, 'route', entry['fact'], entry['path'], entry['line']))
        traced = {}
        for step in ((flow or {}).get('value') or {}).get('steps') or []:
            if not isinstance(step, dict): continue
            for file in (step.get('to_path'), step.get('from_path')):
                if file and file not in traced: traced[file] = step
        reach = sm._reach(comp, r['imports'], IMPORT_STEPS)
        files = sorted({comp} | set(traced) | reach, key=lambda f: (f != comp, f not in traced, f))
        calls = [(file, call) for file in files if not sm.is_test(file) for call in r['calls'].get(file, ())]
        capped = max(len(calls) - MAX_CALLS, 0)
        for file, call in calls[:MAX_CALLS]:
            how = 'contains' if file == comp else 'call' if file in traced else 'imports'
            hid = g.node(f"H:{file}#{call['function'] or call['line']}", 'handler', call['function'] or Path(file).name, path=file,
                         line=next((f['start'] for f in r['functions'].get(file, ()) if f['name'] == call['function']), call['line']))
            if how == 'call':
                step = traced[file]
                steps.append(g.link(cid, hid, how, flow, step.get('from_path'), step.get('line')))
            else:
                steps.append(g.link(cid, hid, how, None, comp, None))
            aid = g.node(call['id'], 'call', call['label'], path=call['path'], line=call['line'], fact=call['fact'], group=call['group'])
            steps.append(g.link(hid, aid, 'request', call['fact'], call['path'], call['line']))
            steps += self.onward(aid, call)
        unresolved = self.trace_gap(pid, 'handler', cid, flow, steps) if flow else None
        return sid, steps, flow, capped, unresolved

    def server(self, pid, entry):
        g, r = self.g, self.r
        label = f"{entry['method']} {entry['route']}" if entry['method'] else entry['route'] or entry['handler']
        eid = g.node(f"E:{entry['path']}#{entry['handler']}", 'endpoint', label, path=entry['path'], line=entry['line'], fact=entry['fact'])
        flow = r['flows'].get((entry['path'], entry['handler'], entry['route']))
        steps = []
        if not flow:
            steps.append(g.link(eid, g.gap(f'G:handler:{pid}', 'service', 'handler_not_found', entry['handler']), 'gap'))
            return eid, steps, None, 0, None
        first = next((s.get('from_path') for s in (flow.get('value') or {}).get('steps') or [] if isinstance(s, dict)), None)
        steps += self.server_side(eid, first or entry['path'], flow)
        unresolved = self.trace_gap(pid, 'service', eid, flow, steps)
        return eid, steps, flow, 0, unresolved


def _cards_index(card_rows):
    on = defaultdict(list)
    for card in card_rows or []:
        for path in card.get('paths') or []:
            if isinstance(path, str): on[path].append(card)

    def cards_of(path):
        rows = on.get(path, [])
        return [c['id'] for c in rows][:MAX_CARDS], sorted({c['milestone'] for c in rows if c.get('milestone')})
    return cards_of


def code_paths(report, card_rows):
    """(paths, nodes, edges, counts) of every entry the records name."""
    r = _read(report)
    comps, owner, new = components(report)
    b = _Builder(r, owner, _cards_index(card_rows))
    out, used = [], set()

    def add(kind, entry, title):
        base = _slug(f"{entry['route']} {entry['handler'] or ''}")
        pid, n = base, 2
        while pid in used: pid, n = f'{base}-{n}', n + 1
        used.add(pid)
        start, steps, flow, capped, unresolved = (b.page if kind == 'page' else b.server)(pid, entry)
        steps = list(dict.fromkeys(steps))
        nodes = {start} | {b.g.edges[i][end] for i in steps for end in ('from', 'to')}
        lanes = {b.g.nodes[n]['lane'] for n in nodes if b.g.nodes[n]['kind'] != 'gap'}
        columns = layout(nodes, {n: b.g.nodes[n]['lane'] for n in nodes}, [(b.g.edges[i]['from'], b.g.edges[i]['to']) for i in steps])
        out.append({'id': pid, 'title': title, 'handler': entry['handler'], 'surface': entry['surface'], 'entry': start,
                    'fact': _fact_id(entry['fact']), 'flow': ((flow or {}).get('value') or {}).get('flow_id'),
                    'flow_fact': _fact_id(flow), 'steps': steps, 'columns': columns,
                    'gaps': sum(b.g.nodes[n]['kind'] == 'gap' for n in nodes), 'capped': capped,
                    'unresolved': unresolved, 'reach': max((LANES.index(l) for l in lanes), default=0)})

    seen = set()
    for entry in sorted(r['pages'], key=lambda e: (e['route'] == '*', e['route'], str(e['handler']), e['path'], e['line'] or 0)):
        if (entry['route'], entry['handler']) in seen: continue
        seen.add((entry['route'], entry['handler']))
        add('page', entry, entry['route'] or '/')
    seen = set()
    for entry in sorted(r['servers'], key=lambda e: (e['surface'], e['route'], str(e['method']), e['path'])):
        if (entry['path'], entry['handler']) in seen: continue
        seen.add((entry['path'], entry['handler']))
        add('server', entry, f"{entry['method']} {entry['route']}" if entry['method'] else entry['route'] or str(entry['handler']))
    on_path = Counter(n for p in out for column in p['columns'] for n in column)
    nodes = [{**node, 'paths': on_path[nid]} for nid, node in sorted(b.g.nodes.items()) if on_path[nid]]
    parts = sorted({n['component'] for n in nodes if n['component']})
    return out, nodes, b.g.edges, {name: comps[name] for name in parts if name in comps}, new, r


# ---------------------------------------------------------------- the layout

def layout(ids, lane_of, edges):
    """[[node id] per lane, top to bottom]: the lanes are the layers, ordered by EAOS's barycentre sweeps
    (arch_map.order_columns) to cross fewer links. Deterministic: the same nodes and links give the same places, and
    the Current, Target and Change views draw the same places."""
    layer = {n: LANES.index(lane_of[n]) for n in ids}
    columns = arch_map.order_columns(layer, sorted(set(edges))) if layer else []
    return [list(columns[i]) if i < len(columns) else [] for i in range(len(LANES))]


def _folder(name, level):
    """A part's name cut by `level` folders from its end, never below its first folder: src/pages/settings -> src/pages."""
    parts = str(name).split('/')
    return '/'.join(parts[:max(len(parts) - level, 1)])


def cluster_of(node, level=0):
    """The overview's cluster of a node: screens and calls by their route's first words (/drivers, /api/users), a gap
    by its reason (and its call's group), anything else by the part of today owning it, else by its kind. At a higher
    level a part is cut to its parent folders, so a large project still draws a readable number of clusters."""
    if node['kind'] == 'gap': return f"K:{node['lane']}:{node['reason']}:{node['group'] or ''}".rstrip(':')
    if node['lane'] in ('screen', 'call') and node['group']: return f"K:{node['lane']}:{node['group']}"
    return f"K:{node['lane']}:{_folder(node['component'], level) if node['component'] else node['kind']}"


def overview(nodes, edges):
    """Every path at once, as clusters: one per lane and part (a gap kind, tables, outside services), with the links
    between clusters counted; parts are cut to their parent folders until at most MAX_CLUSTERS remain. Drawn instead of
    every step, so the map stays readable at any size; `all` says whether every step is small enough to draw too."""
    level = 0
    while True:
        of = {n['id']: cluster_of(n, level) for n in nodes}
        if len(set(of.values())) <= MAX_CLUSTERS or level >= 8: break
        level += 1
    members, gaps = defaultdict(list), Counter()
    for n in nodes:
        members[of[n['id']]].append(n)
        if n['kind'] == 'gap': gaps[of[n['id']]] += 1
    lane_of = {k: k.split(':', 2)[1] for k in members}
    weight = Counter((of[e['from']], of[e['to']]) for e in edges if e['from'] in of and e['to'] in of and of[e['from']] != of[e['to']])
    clusters = []
    for k, rows in sorted(members.items()):
        head, single = rows[0], len(rows) == 1
        part = _folder(head['component'], level) if head['component'] else None
        clusters.append({'id': k, 'lane': lane_of[k], 'kind': 'gap' if gaps[k] == len(rows) else head['kind'] if single else 'group',
                         'label': head['label'] if single else (head['group'] if head['lane'] in ('screen', 'call') or gaps[k] else None)
                                  or part or head['reason'] or head['kind'],
                         'component': part, 'reason': head['reason'] if gaps[k] else None,
                         'size': len(rows), 'gaps': gaps[k], 'nodes': sorted(n['id'] for n in rows)[:200]})
    links = [{'from': a, 'to': b, 'n': n} for (a, b), n in sorted(weight.items())]
    return {'clusters': clusters, 'links': links, 'columns': layout(set(members), lane_of, list(weight)),
            'level': level, 'all': len(nodes) <= CLUSTER_AT}


# ---------------------------------------------------------------- the plan's timeline

def timeline(plan, card_rows, lang='ar'):
    """The fix plan in the order it runs, or None when the plan has no waves."""
    plan = plan if isinstance(plan, dict) else {}
    waves = sorted((w for w in plan.get('waves') or [] if isinstance(w, dict) and isinstance(w.get('wave'), int)),
                   key=lambda w: w['wave'])
    if not waves: return None
    tasks = {t['id']: t for t in plan.get('tasks') or [] if isinstance(t, dict) and t.get('id')}
    stones = [m for m in plan.get('milestones') or [] if isinstance(m, dict) and m.get('id')]
    step_of = {tid: m['id'] for m in stones for tid in m.get('tasks') or []}
    card = {c['id']: c for c in card_rows or []}
    rows, wave_of, last = [], {}, {}
    for wave in waves:
        members = [tid for tid in wave.get('tasks') or [] if tid in tasks]
        for tid in members:
            task, waits = tasks[tid], []
            for ref in task.get('prerequisites') or []:
                if isinstance(ref, dict) and ref.get('task_id') in wave_of:
                    waits.append({'task': ref['task_id'], 'why': 'prerequisite', 'detail': str(ref.get('reason') or '')[:200]})
            for path in sorted({p for p in task.get('paths') or [] if isinstance(p, str)}):
                before = last.get(path)
                if before and before not in {w['task'] for w in waits}: waits.append({'task': before, 'why': 'same_file', 'detail': path})
            rows.append({'id': tid, 'step': step_of.get(tid), 'wave': wave['wave'],
                         'title': str((card.get(tid) or {}).get('title') or task.get('title') or tid)[:300],
                         'state': (card.get(tid) or {}).get('state') or 'open', 'waits': waits[:MAX_WAITS],
                         'more': max(len(waits) - MAX_WAITS, 0)})
        for tid in members:
            wave_of[tid] = wave['wave']
            for path in tasks[tid].get('paths') or []:
                if isinstance(path, str): last[path] = tid
    steps = []
    for m in stones:
        mine = [row['wave'] for row in rows if row['step'] == m['id']]
        steps.append({'id': m['id'], 'title': str(m.get('goal_ar' if lang == 'ar' else 'goal') or m.get('name') or m['id'])[:300],
                      'name': str(m.get('name') or ''), 'tasks': len(mine), 'first': min(mine) if mine else None,
                      'last': max(mine) if mine else None})
    by_wave = defaultdict(Counter)
    for row in rows: by_wave[row['wave']][row['step'] or ''] += 1
    out_waves = [{'wave': w['wave'], 'tasks': sum(by_wave[w['wave']].values()),
                  'steps': [{'step': s or None, 'tasks': n} for s, n in sorted(by_wave[w['wave']].items())]} for w in waves]
    return {'plan': 'fix', 'waves': out_waves, 'steps': steps, 'tasks': rows,
            'counts': {'waves': _measure(len(out_waves), 'plan.json#waves (count)'),
                       'tasks': _measure(len(rows), 'plan.json#waves[].tasks (count)'),
                       'waits': _measure(sum(len(row['waits']) + row['more'] for row in rows),
                                         'plan.json#tasks[].prerequisites + the last earlier task on the same file (count)')}}


# ---------------------------------------------------------------- the section

def paths(report, card_rows, plan=None, lang='ar'):
    """The section's body: {lanes, paths, nodes, edges, components, new, counts, src, timeline}."""
    out, nodes, edges, parts, new, r = code_paths(report, card_rows)
    gaps = Counter(n['reason'] for n in nodes if n['kind'] == 'gap')
    hows = Counter(e['how'] for e in edges)
    calls = [n for n in nodes if n['lane'] == 'call']
    reached = {e['from'] for e in edges if e['how'] in ('route', 'file_route', 'client', 'external')}
    have_flows = bool(r['flow_list'])
    return {
        'lanes': list(LANES),
        'paths': out, 'nodes': nodes, 'edges': edges, 'components': parts, 'new': new, 'overview': overview(nodes, edges),
        'counts': {
            'paths': _measure(len(out), SRC['paths'] + ' (count)'),
            'nodes': _measure(len(nodes), 'paths.json#nodes (count)'),
            'links': _measure(sum(n for how, n in hows.items() if how not in ('gap', 'trace')), 'paths.json#edges[how not in gap, trace] (count)'),
            'gaps': _measure(sum(gaps.values()), 'paths.json#nodes[kind=gap] (count)'),
            'no_server_route': _measure(gaps.get('no_server_route', 0), 'paths.json#nodes[reason=no_server_route] (count)'),
            'trace_stopped': _measure(gaps.get('trace_stopped', 0), 'paths.json#nodes[reason=trace_stopped] (count)'),
            'component_not_found': _measure(gaps.get('component_not_found', 0), 'paths.json#nodes[reason=component_not_found] (count)'),
            'handler_not_found': _measure(gaps.get('handler_not_found', 0), 'paths.json#nodes[reason=handler_not_found] (count)'),
            'unresolved_steps': _measure(sum(p['unresolved'] or 0 for p in out) if have_flows else None,
                                         SRC['flows'] + '.unresolved_steps, summed over the paths'),
            'calls': _measure(len(calls), SRC['calls'] + ' (distinct method and URL, or client and table)'),
            'calls_answered': _measure(sum(c['id'] in reached for c in calls), 'paths.json#edges[how in route, file_route, client, external] (distinct calls)'),
            'by_call': _measure(hows.get('call', 0), SRC['flows'] + ' (links the flow confirms)'),
            'by_imports': _measure(hows.get('imports', 0), SRC['imports'] + ' (links only the imports support)'),
        },
        'src': SRC,
        'timeline': timeline(plan, card_rows, lang),
    }
