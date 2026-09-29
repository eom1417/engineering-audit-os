"""The architecture maps of the report for people (eaos/human_report.py): what depends on what, drawn, and the target.

Reads only records the audit already wrote, and never raises for a missing or broken one (a missing piece is None):
    facts/graph.json       graph_node: a file, the files it imports (depends_on), its cycle group; graph_cycle: a loop
    target-architecture.json   current_components (today's parts and their files), target_components, target_edges
    facts/flows.json       flow: a page or an endpoint and the chain of calls it starts
    facts/structure.json   scope: the functions of a file; call_site: a call, inside the function that makes it

The component map:
    edge A -> B          A's files import B's files; its strength is the number of such imports
    cohesion of A        imports that stay inside A / all imports A's files make (to A or to another part)
    instability of A     Ce / (Ca + Ce): Ce the imports going out of A, Ca the imports coming in (Robert C. Martin)
    a cycle edge         both ends are in one strongly connected group: each can reach the other through imports
    a wrong-way edge     the parts' target layers are known and the reference architecture forbids that direction
Layout: layers left to right, a part to the left of what it uses. Inside a cycle the lightest edges are set aside
(Eades' greedy order) so that the rest can be layered by the longest path; the set-aside edges are drawn going back.
Then a few barycentre passes order each layer to cross fewer edges.
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

NODE_W, NODE_H, COL_GAP, ROW_GAP, PAD = 186, 50, 70, 16, 16
MAX_COMPONENTS, MAX_FILES, MAX_CALLS, MAX_FUNCTIONS = 60, 400, 3000, 120
STOP = ('unresolved', 'ambiguous', 'method_or_external')     # the trace cannot follow these calls
LIBRARY = ('external', 'builtin')


def _load(path, default):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


def facts(report, name, kind):
    record = _load(Path(report) / 'facts' / f'{name}.json', {})
    rows = record.get('facts') if isinstance(record, dict) else None
    return [f for f in rows or [] if isinstance(f, dict) and f.get('kind') == kind]


def path_of(fact):
    return (fact.get('location') or {}).get('path') or ''


# ---------------------------------------------------------------- graphs

def strong_groups(ids, edges):
    """{id: group number} of Tarjan's strongly connected groups, iteratively (a deep project must not hit recursion)."""
    out = defaultdict(list)
    for a, b in edges: out[a].append(b)
    index, low, stack, on, group, counter = {}, {}, [], set(), {}, [0]
    for root in ids:
        if root in index: continue
        work = [(root, iter(out[root]))]
        index[root] = low[root] = counter[0]; counter[0] += 1; stack.append(root); on.add(root)
        while work:
            node, children = work[-1]
            child = next(children, None)
            if child is not None:
                if child not in index:
                    index[child] = low[child] = counter[0]; counter[0] += 1; stack.append(child); on.add(child)
                    work.append((child, iter(out[child])))
                elif child in on: low[node] = min(low[node], index[child])
                continue
            work.pop()
            if work: low[work[-1][0]] = min(low[work[-1][0]], low[node])
            if low[node] == index[node]:
                number = len(set(group.values()))
                while True:
                    member = stack.pop(); on.discard(member); group[member] = number
                    if member == node: break
    return group


def feedback_edges(ids, weights):
    """The edges to set aside so the rest has no cycle: Eades' greedy order, weighted, kept inside each cycle only."""
    group = strong_groups(ids, list(weights))
    inside = {e: n for e, n in weights.items() if group[e[0]] == group[e[1]] and e[0] != e[1]}
    remaining, order_left, order_right = set(ids), [], []
    while remaining:
        sinks = [v for v in remaining if not any(a == v and b in remaining for a, b in inside)]
        sources = [v for v in remaining if not any(b == v and a in remaining for a, b in inside)]
        if sinks or sources:
            for v in sorted(sinks): order_right.insert(0, v); remaining.discard(v)
            for v in sorted(set(sources) - set(sinks)): order_left.append(v); remaining.discard(v)
            continue
        best = max(sorted(remaining), key=lambda v: sum(n for (a, b), n in inside.items() if a == v and b in remaining)
                   - sum(n for (a, b), n in inside.items() if b == v and a in remaining))
        order_left.append(best); remaining.discard(best)
    rank = {v: i for i, v in enumerate(order_left + order_right)}
    return {e for e in inside if rank[e[0]] > rank[e[1]]}


def layer_of(ids, edges):
    """{id: layer}: the longest path from a part nothing uses, on an acyclic set of edges."""
    out = defaultdict(list)
    indegree = Counter()
    for a, b in edges: out[a].append(b); indegree[b] += 1
    layer = {v: 0 for v in ids}
    ready = [v for v in ids if not indegree[v]]
    while ready:
        v = ready.pop()
        for b in out[v]:
            layer[b] = max(layer[b], layer[v] + 1)
            indegree[b] -= 1
            if not indegree[b]: ready.append(b)
    return layer


def order_columns(layer, edges, passes=6):
    """[[id]] per layer, ordered by barycentre sweeps left to right and back to cross fewer edges."""
    columns = defaultdict(list)
    for v in sorted(layer): columns[layer[v]].append(v)
    columns = [columns[i] for i in range(max(columns) + 1)] if columns else []
    neighbours = defaultdict(list)
    for a, b in edges: neighbours[a].append(b); neighbours[b].append(a)
    for sweep in range(passes):
        forward = sweep % 2 == 0
        span = range(1, len(columns)) if forward else range(len(columns) - 2, -1, -1)
        for i in span:
            fixed = {v: p for p, v in enumerate(columns[i - 1 if forward else i + 1])}
            def centre(v, here=i):
                places = [fixed[u] for u in neighbours[v] if u in fixed]
                return sum(places) / len(places) if places else columns[here].index(v)
            columns[i] = sorted(columns[i], key=centre)
    return columns


def crossings(columns, edges):
    """How many pairs of edges between neighbouring layers cross: the measure the barycentre passes lower."""
    place = {v: (i, p) for i, column in enumerate(columns) for p, v in enumerate(column)}
    spans = [(place[a], place[b]) for a, b in edges if a in place and b in place and abs(place[a][0] - place[b][0]) == 1]
    spans = [(x, y) if x[0] < y[0] else (y, x) for x, y in spans]
    return sum(1 for i, (a1, b1) in enumerate(spans) for a2, b2 in spans[i + 1:]
               if a1[0] == a2[0] and (a1[1] - a2[1]) * (b1[1] - b2[1]) < 0)


def positions(columns):
    """{id: (x, y)} of each box's top left corner, every column centred on the tallest; and the drawing's size."""
    tallest = max((len(c) for c in columns), default=0)
    height = PAD * 2 + tallest * NODE_H + max(tallest - 1, 0) * ROW_GAP
    out = {}
    for i, column in enumerate(columns):
        top = (height - (len(column) * NODE_H + max(len(column) - 1, 0) * ROW_GAP)) / 2
        for p, v in enumerate(column):
            out[v] = (PAD + i * (NODE_W + COL_GAP), top + p * (NODE_H + ROW_GAP))
    width = PAD * 2 + len(columns) * NODE_W + max(len(columns) - 1, 0) * COL_GAP
    return out, width, height


# ---------------------------------------------------------------- the component map

def instability_word(ca, ce):
    if not ca and not ce: return 'alone'
    value = ce / (ca + ce)
    return 'stable' if value < 0.3 else 'unstable' if value > 0.7 else 'balanced'


def cohesion_word(share):
    return None if share is None else 'strong' if share >= 60 else 'medium' if share >= 30 else 'weak'


def allowed_layers(target):
    """{layer: layers it may use} from the reference architecture the target names; {} when it cannot be read."""
    try:
        from .reference_architecture import by_id
        return {layer['name']: set(layer['allowed_dependencies']) for layer in by_id(target.get('reference'))['layers']}
    except Exception:
        return {}


def component_map(report, target=None):
    """The parts of the project today and the imports between them, laid out; None when the records are missing."""
    target = target if target is not None else _load(Path(report) / 'target-architecture.json', {})
    components = [c for c in (target or {}).get('current_components') or [] if isinstance(c, dict) and c.get('id')]
    nodes = facts(report, 'graph', 'graph_node')
    if not components or not nodes: return None
    owner = {p: c['id'] for c in components for p in c.get('paths') or [] if isinstance(p, str)}
    between, inside, files_of = Counter(), Counter(), defaultdict(list)
    imports = {}
    for node in nodes:
        here = owner.get(path_of(node))
        depends = [d for d in (node.get('value') or {}).get('depends_on') or [] if isinstance(d, str)]
        imports[path_of(node)] = depends
        if not here: continue
        files_of[here].append(path_of(node))
        for d in depends:
            there = owner.get(d)
            if not there: continue
            if there == here: inside[here] += 1
            else: between[(here, there)] += 1
    ranked = sorted(components, key=lambda c: -(c.get('files') or len(files_of[c['id']])))
    kept = ranked[:MAX_COMPONENTS]
    ids = [c['id'] for c in kept]
    shown = set(ids)
    edges = {e: n for e, n in between.items() if e[0] in shown and e[1] in shown}
    group = strong_groups(ids, list(edges))
    sizes = Counter(group.values())
    layer_by_name = {c.get('name'): c.get('layer') for c in target.get('target_components') or [] if isinstance(c, dict)}
    rules = allowed_layers(target)
    def wrong(a, b):
        la, lb = (layer_by_name.get(by_id[x].get('target_component')) for x in (a, b))
        return bool(rules) and la in rules and lb in rules and la != lb and lb not in rules[la]
    by_id = {c['id']: c for c in kept}
    back = feedback_edges(ids, edges)
    layer = layer_of(ids, [e for e in edges if e not in back])
    columns = order_columns(layer, list(edges))
    place, width, height = positions(columns)
    root = target.get('root') or ''
    out_nodes = []
    for c in kept:
        cid = c['id']
        ce, ca = sum(n for (a, _), n in between.items() if a == cid), sum(n for (_, b), n in between.items() if b == cid)
        total = inside[cid] + ce
        share = round(100 * inside[cid] / total) if total else None
        name = c.get('name') or cid
        x, y = place[cid]
        out_nodes.append({'id': cid, 'name': name, 'short': (name[len(root):] if root and name.startswith(root) and name != root else name) or name,
                          'files': c.get('files') or len(files_of[cid]), 'x': x, 'y': y, 'layer': layer[cid],
                          'uses': len({b for (a, b) in between if a == cid}), 'used_by': len({a for (a, b) in between if b == cid}),
                          'ca': ca, 'ce': ce, 'inside': inside[cid], 'cohesion': share, 'cohesion_word': cohesion_word(share),
                          'instability': instability_word(ca, ce), 'cycle': sizes[group[cid]] > 1,
                          'relation': c.get('relation'), 'target': c.get('target_component')})
    out_edges = [{'from': a, 'to': b, 'n': n, 'cycle': group[a] == group[b], 'back': (a, b) in back or layer[b] <= layer[a],
                  'wrong': wrong(a, b)} for (a, b), n in sorted(edges.items(), key=lambda kv: -kv[1])]
    return {'nodes': out_nodes, 'edges': out_edges, 'width': width, 'height': height, 'crossings': crossings(columns, list(edges)),
            'capped': len(components) - len(kept), 'owner': owner, 'files_of': files_of, 'imports': imports,
            'cycle_files': {path_of(n) for n in nodes if (n.get('value') or {}).get('cycle_group') is not None}}


# ---------------------------------------------------------------- functions and the calls between them

def enclosing(symbol):
    """The named function a call sits in: '<module>.<module>.save.<anon>' is inside save; None at the top of a file."""
    parts = [p for p in str(symbol or '').split('.') if p and not p.startswith('<')]
    return parts[-1] if parts else None


def function_calls(report, imports):
    """({file: [function names]}, [(file, function, file, function, calls)]): each call resolved by its name to a
    function defined in the same file, else in exactly one file this file imports; a call that is not is left out."""
    functions = defaultdict(list)
    calls = Counter()
    for scope in facts(report, 'structure', 'scope'):
        name = (scope.get('value') or {}).get('name') or ''
        if name and not name.startswith('<') and name not in functions[path_of(scope)]:
            functions[path_of(scope)].append(name)
    defined = {path: set(names) for path, names in functions.items()}
    for site in facts(report, 'structure', 'call_site'):
        value, path = site.get('value') or {}, path_of(site)
        caller, callee = enclosing((site.get('location') or {}).get('symbol')), value.get('callee')
        if not caller or not callee or value.get('attribute'): continue
        if callee in defined.get(path, ()): home = path
        else:
            homes = [d for d in imports.get(path) or [] if callee in defined.get(d, ())]
            if len(homes) != 1: continue
            home = homes[0]
        if (path, caller) != (home, callee): calls[(path, caller, home, callee)] += 1
    return functions, [(*key, n) for key, n in calls.items()]


def drill_data(report, cmap):
    """The embedded JSON the drill-down draws from: parts, their files, imports, functions and calls, capped."""
    if not cmap: return None
    files, index = [], {}
    comps, capped_files = [], 0
    for node in cmap['nodes']:
        mine = sorted(cmap['files_of'].get(node['id']) or [])
        capped_files += max(len(mine) - MAX_FILES, 0)
        for path in mine[:MAX_FILES]:
            index[path] = len(files); files.append(path)
    position = {n['id']: i for i, n in enumerate(cmap['nodes'])}
    for node in cmap['nodes']:
        comps.append({'id': node['id'], 'name': node['name'], 'files': [index[p] for p in sorted(cmap['files_of'].get(node['id']) or []) if p in index],
                      'uses': [[position[e['to']], e['n']] for e in cmap['edges'] if e['from'] == node['id']],
                      'used_by': [[position[e['from']], e['n']] for e in cmap['edges'] if e['to'] == node['id']],
                      'cohesion': node['cohesion'], 'instability': node['instability'], 'filecount': node['files']})
    owner_of = [position.get(cmap['owner'].get(p)) for p in files]
    imports = [[index[d] for d in cmap['imports'].get(p) or [] if d in index] for p in files]
    functions, calls = function_calls(report, cmap['imports'])
    calls = sorted((c for c in calls if c[0] in index and c[2] in index), key=lambda c: -c[4])
    kept = calls[:MAX_CALLS]
    return {'files': files, 'owner': owner_of, 'imports': imports, 'comps': comps,
            'functions': [functions.get(p, [])[:MAX_FUNCTIONS] for p in files],
            'calls': [[index[a], f, index[b], g, n] for a, f, b, g, n in kept],
            'cycle': [int(p in cmap['cycle_files']) for p in files],
            'capped': {'components': cmap['capped'], 'files': capped_files, 'calls': len(calls) - len(kept)}}


# ---------------------------------------------------------------- pages and their call chains

FLOW_W, FLOW_H, FLOW_GAP_X, FLOW_GAP_Y, FLOW_PER_ROW = 236, 50, 18, 46, 4


def flow_charts(report):
    """One vertical chart per page or endpoint: its route, its handler, then each called function by depth, grouped by
    file; where the trace cannot follow a call, a box says it stops there. None when there is no flow record."""
    out = []
    for flow in facts(report, 'flows', 'flow'):
        value = flow.get('value') or {}
        entry = value.get('entry') or {}
        steps = [s for s in value.get('steps') or [] if isinstance(s, dict)]
        handler = (entry.get('path') or path_of(flow), entry.get('handler') or (flow.get('location') or {}).get('symbol') or '?')
        handler_file = next((s.get('from_path') for s in steps if s.get('from') == handler[1] and s.get('from_path')), handler[0])
        handler = (handler_file, handler[1])
        nodes = {'entry': {'id': 'entry', 'kind': 'entry', 'label': entry.get('route') or '', 'sub': entry.get('http_method') or entry.get('surface') or '', 'level': 0},
                 handler: {'id': 'h', 'kind': 'handler', 'label': handler[1], 'sub': handler[0], 'level': 1, 'library': 0}}
        edges, stops = [('entry', handler)], defaultdict(list)
        for step in sorted(steps, key=lambda s: s.get('depth') or 0):
            caller = (step.get('from_path') or '', step.get('from') or '')
            if caller not in nodes:
                nodes[caller] = {'id': f'n{len(nodes)}', 'kind': 'fn', 'label': caller[1], 'sub': caller[0], 'level': (step.get('depth') or 0) + 1, 'library': 0}
            resolution = step.get('resolution')
            if resolution in LIBRARY: nodes[caller]['library'] = nodes[caller].get('library', 0) + 1; continue
            if resolution in STOP or not step.get('to_path'):
                if step.get('callee') and step['callee'] not in stops[caller]: stops[caller].append(step['callee'])
                continue
            callee = (step['to_path'], step.get('to_symbol') or step.get('callee') or '?')
            if callee not in nodes:
                nodes[callee] = {'id': f'n{len(nodes)}', 'kind': 'fn', 'label': callee[1], 'sub': callee[0], 'level': nodes[caller]['level'] + 1, 'library': 0}
            if (caller, callee) not in edges and caller != callee: edges.append((caller, callee))
        for caller, names in stops.items():
            key = ('stop', caller)
            nodes[key] = {'id': f's{len(nodes)}', 'kind': 'stop', 'label': ', '.join(names[:3]), 'more': max(len(names) - 3, 0),
                          'sub': '', 'level': nodes[caller]['level'] + 1, 'count': len(names)}
            edges.append((caller, key))
        rows = defaultdict(list)
        for key, node in nodes.items(): rows[node['level']].append(key)
        y, drawn = PAD, []
        for level in sorted(rows):
            members = sorted(rows[level], key=lambda k: (nodes[k]['kind'] == 'stop', nodes[k].get('sub') or '', nodes[k]['label']))
            for start in range(0, len(members), FLOW_PER_ROW):
                line = members[start:start + FLOW_PER_ROW]
                left = PAD + (FLOW_PER_ROW - len(line)) * (FLOW_W + FLOW_GAP_X) / 2
                for p, key in enumerate(line):
                    nodes[key]['x'], nodes[key]['y'] = round(left + p * (FLOW_W + FLOW_GAP_X)), y
                    drawn.append(nodes[key])
                y += FLOW_H + FLOW_GAP_Y
        width = PAD * 2 + FLOW_PER_ROW * FLOW_W + (FLOW_PER_ROW - 1) * FLOW_GAP_X
        out.append({'id': value.get('flow_id') or flow.get('id') or f'FLOW-{len(out) + 1}', 'surface': entry.get('surface') or '',
                    'route': entry.get('route') or '', 'method': entry.get('http_method') or '', 'handler': handler[1], 'path': handler[0],
                    'found': bool(value.get('handler_found', True)), 'nodes': [{k: v for k, v in n.items() if k != 'level'} for n in drawn],
                    'edges': [[nodes[a]['id'], nodes[b]['id']] for a, b in edges], 'width': width, 'height': y - FLOW_GAP_Y + PAD,
                    'steps': len(steps), 'stops': sum(len(v) for v in stops.values())})
    return out or None


# ---------------------------------------------------------------- the target, and the gap closed in each part

def target_owner(target):
    """{path: target component name}: through today's part a file belongs to, else the target's own path list."""
    out = {}
    for c in (target or {}).get('target_components') or []:
        for p in c.get('paths') or []: out.setdefault(p, c.get('name'))
    for c in (target or {}).get('current_components') or []:
        for p in c.get('paths') or []:
            if c.get('target_component'): out[p] = c['target_component']
    return out


def target_progress(target, cards, closed):
    """{target component: (closed cards, all cards)}: a card counts in every target part one of its files goes to."""
    owner = target_owner(target)
    out = defaultdict(lambda: [0, 0])
    for card in cards:
        for name in {owner.get(p) for p in card.get('paths') or []} - {None}:
            out[name][1] += 1
            out[name][0] += card.get('state') in closed
    return {k: tuple(v) for k, v in out.items()}


def json_script(element_id, data):
    """Data for the page's script, safe inside <script>: '</' cannot end the element early."""
    text = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/').replace('<!--', '<\\!--')
    return f'<script type="application/json" id="{element_id}">{text}</script>'
