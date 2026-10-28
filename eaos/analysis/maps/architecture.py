"""The architecture maps of the report for people (eaos/report/human_report/): what depends on what, drawn, and the target.

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
Layout (eaos/analysis/maps/layout.py): layers left to right, a part to the left of what it uses; inside a cycle the
lightest edges are set aside so that the rest can be layered, and the set-aside edges are drawn going back.
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

from .layout import NODE_H, NODE_W  # noqa: F401  (the report draws the map's boxes at their size)
from .layout import PAD, crossings, feedback_edges, layer_of, order_columns, positions, strong_groups
from ...core.system.files import read_json


MAX_COMPONENTS, MAX_FILES, MAX_CALLS, MAX_FUNCTIONS = 60, 400, 3000, 120
STOP = ('unresolved', 'ambiguous', 'method_or_external')     # the trace cannot follow these calls
LIBRARY = ('external', 'builtin')


def facts(report, name, kind):
    record = read_json(Path(report) / 'facts' / f'{name}.json', {})
    rows = record.get('facts') if isinstance(record, dict) else None
    return [f for f in rows or [] if isinstance(f, dict) and f.get('kind') == kind]


def path_of(fact):
    return (fact.get('location') or {}).get('path') or ''


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
        from ..target_state.references import by_id
        return {layer['name']: set(layer['allowed_dependencies']) for layer in by_id(target.get('reference'))['layers']}
    except Exception:
        return {}


def _current_components(target):
    return [c for c in (target or {}).get('current_components') or [] if isinstance(c, dict) and c.get('id')]


def _file_owner(components):
    return {p: c['id'] for c in components for p in c.get('paths') or [] if isinstance(p, str)}


def _count_imports(here, depends, owner, between, inside):
    for d in depends:
        there = owner.get(d)
        if not there: continue
        if there == here: inside[here] += 1
        else: between[(here, there)] += 1


def _tally_imports(nodes, owner):
    """(imports between parts, imports inside each part, each part's files, each file's imports)."""
    between, inside, files_of, imports = Counter(), Counter(), defaultdict(list), {}
    for node in nodes:
        here = owner.get(path_of(node))
        depends = [d for d in (node.get('value') or {}).get('depends_on') or [] if isinstance(d, str)]
        imports[path_of(node)] = depends
        if not here: continue
        files_of[here].append(path_of(node))
        _count_imports(here, depends, owner, between, inside)
    return between, inside, files_of, imports


def _wrong_way(target, by_id):
    """wrong(a, b): the reference architecture forbids part a's target layer from using part b's."""
    layer_by_name = {c.get('name'): c.get('layer') for c in target.get('target_components') or [] if isinstance(c, dict)}
    rules = allowed_layers(target)
    def wrong(a, b):
        la, lb = (layer_by_name.get(by_id[x].get('target_component')) for x in (a, b))
        return bool(rules) and la in rules and lb in rules and la != lb and lb not in rules[la]
    return wrong


def _short(name, root):
    return (name[len(root):] if root and name.startswith(root) and name != root else name) or name


def _coupling(cid, between):
    """(Ca, Ce, the parts it uses, the parts that use it) of one part, from the imports between parts."""
    ce, ca = sum(n for (a, _), n in between.items() if a == cid), sum(n for (_, b), n in between.items() if b == cid)
    return ca, ce, len({b for (a, b) in between if a == cid}), len({a for (a, b) in between if b == cid})


def _component_node(c, drawing):
    cid, inside = c['id'], drawing['inside']
    ca, ce, uses, used_by = _coupling(cid, drawing['between'])
    total = inside[cid] + ce
    share = round(100 * inside[cid] / total) if total else None
    name = c.get('name') or cid
    x, y = drawing['place'][cid]
    return {'id': cid, 'name': name, 'short': _short(name, drawing['root']),
            'files': c.get('files') or len(drawing['files_of'][cid]), 'x': x, 'y': y, 'layer': drawing['layer'][cid],
            'uses': uses, 'used_by': used_by,
            'ca': ca, 'ce': ce, 'inside': inside[cid], 'cohesion': share, 'cohesion_word': cohesion_word(share),
            'instability': instability_word(ca, ce), 'cycle': drawing['sizes'][drawing['group'][cid]] > 1,
            'relation': c.get('relation'), 'target': c.get('target_component')}


def component_map(report, target=None):
    """The parts of the project today and the imports between them, laid out; None when the records are missing."""
    target = target if target is not None else read_json(Path(report) / 'target-architecture.json', {})
    components = _current_components(target)
    nodes = facts(report, 'graph', 'graph_node')
    if not components or not nodes: return None
    owner = _file_owner(components)
    between, inside, files_of, imports = _tally_imports(nodes, owner)
    kept = sorted(components, key=lambda c: -(c.get('files') or len(files_of[c['id']])))[:MAX_COMPONENTS]
    ids = [c['id'] for c in kept]
    shown = set(ids)
    edges = {e: n for e, n in between.items() if shown.issuperset(e)}
    group, back, layer, columns = _layered(ids, edges)
    place, width, height = positions(columns)
    drawing = {'between': between, 'inside': inside, 'files_of': files_of, 'place': place, 'layer': layer,
               'group': group, 'sizes': Counter(group.values()), 'root': target.get('root') or ''}
    wrong = _wrong_way(target, {c['id']: c for c in kept})
    return {'nodes': [_component_node(c, drawing) for c in kept], 'edges': _drawn_edges(edges, drawing, back, wrong),
            'width': width, 'height': height, 'crossings': crossings(columns, list(edges)),
            'capped': len(components) - len(kept), 'owner': owner, 'files_of': files_of, 'imports': imports,
            'cycle_files': _cycle_files(nodes)}


def _layered(ids, edges):
    """(strong groups, the edges set aside, each part's layer, the ordered columns) of the parts shown."""
    group = strong_groups(ids, list(edges))
    back = feedback_edges(ids, edges)
    layer = layer_of(ids, [e for e in edges if e not in back])
    return group, back, layer, order_columns(layer, list(edges))


def _drawn_edges(edges, drawing, back, wrong):
    """The links, strongest first: inside a loop, drawn going back, against the layer rules."""
    group, layer = drawing['group'], drawing['layer']
    return [{'from': a, 'to': b, 'n': n, 'cycle': group[a] == group[b], 'back': (a, b) in back or layer[b] <= layer[a],
             'wrong': wrong(a, b)} for (a, b), n in sorted(edges.items(), key=lambda kv: -kv[1])]


def _cycle_files(nodes):
    """The files in an import loop."""
    return {path_of(n) for n in nodes if (n.get('value') or {}).get('cycle_group') is not None}


# ---------------------------------------------------------------- functions and the calls between them

def enclosing(symbol):
    """The named function a call sits in: '<module>.<module>.save.<anon>' is inside save; None at the top of a file."""
    parts = [p for p in str(symbol or '').split('.') if p and not p.startswith('<')]
    return parts[-1] if parts else None


def _functions(report):
    """{file: the names of its functions}, in the order they are declared, each once."""
    functions = defaultdict(list)
    for scope in facts(report, 'structure', 'scope'):
        name = (scope.get('value') or {}).get('name') or ''
        if name and not name.startswith('<') and name not in functions[path_of(scope)]:
            functions[path_of(scope)].append(name)
    return functions


def _call(site):
    """(file, calling function, called name) of a call by a plain name from inside a named function, else None."""
    value, path = site.get('value') or {}, path_of(site)
    caller, callee = enclosing((site.get('location') or {}).get('symbol')), value.get('callee')
    if not caller or not callee or value.get('attribute'): return None
    return path, caller, callee


def _home(callee, path, defined, imports):
    """The file that defines a called name: the caller's own, else the one file it imports that does; None otherwise."""
    if callee in defined.get(path, ()): return path
    homes = [d for d in imports.get(path) or [] if callee in defined.get(d, ())]
    return homes[0] if len(homes) == 1 else None


def function_calls(report, imports):
    """({file: [function names]}, [(file, function, file, function, calls)]): each call resolved by its name to a
    function defined in the same file, else in exactly one file this file imports; a call that is not is left out."""
    functions = _functions(report)
    calls = Counter()
    defined = {path: set(names) for path, names in functions.items()}
    for call in map(_call, facts(report, 'structure', 'call_site')):
        if call is None: continue
        path, caller, callee = call
        home = _home(callee, path, defined, imports)
        if home is None: continue
        if (path, caller) != (home, callee): calls[(path, caller, home, callee)] += 1
    return functions, [(*key, n) for key, n in calls.items()]


def _drill_files(cmap):
    """Every shown part's files, in part order and capped per part: (files, file -> position, files left out)."""
    files, index, capped = [], {}, 0
    for node in cmap['nodes']:
        mine = sorted(cmap['files_of'].get(node['id']) or [])
        capped += max(len(mine) - MAX_FILES, 0)
        for path in mine[:MAX_FILES]:
            index[path] = len(files); files.append(path)
    return files, index, capped


def _drill_component(node, cmap, index, position):
    return {'id': node['id'], 'name': node['name'], 'files': [index[p] for p in sorted(cmap['files_of'].get(node['id']) or []) if p in index],
            'uses': [[position[e['to']], e['n']] for e in cmap['edges'] if e['from'] == node['id']],
            'used_by': [[position[e['from']], e['n']] for e in cmap['edges'] if e['to'] == node['id']],
            'cohesion': node['cohesion'], 'instability': node['instability'], 'filecount': node['files']}


def _drawn_imports(files, index, imports):
    """Per drawn file, the positions of the drawn files it imports."""
    return [[index[d] for d in imports.get(p) or [] if d in index] for p in files]


def _drawn_calls(calls, index):
    """The calls between two drawn files, the most frequent first."""
    return sorted((c for c in calls if c[0] in index and c[2] in index), key=lambda c: -c[4])


def drill_data(report, cmap):
    """The embedded JSON the drill-down draws from: parts, their files, imports, functions and calls, capped."""
    if not cmap: return None
    files, index, capped_files = _drill_files(cmap)
    position = {n['id']: i for i, n in enumerate(cmap['nodes'])}
    comps = [_drill_component(node, cmap, index, position) for node in cmap['nodes']]
    owner_of = [position.get(cmap['owner'].get(p)) for p in files]
    imports = _drawn_imports(files, index, cmap['imports'])
    functions, calls = function_calls(report, cmap['imports'])
    calls = _drawn_calls(calls, index)
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
    for flow in facts(report, 'flows', 'flow'): out.append(_flow_chart(flow, len(out) + 1))
    return out or None


def _flow_handler(flow, entry, steps):
    """(file, name) of the handler, the file taken from the trace when the entry record names another."""
    name = entry.get('handler') or (flow.get('location') or {}).get('symbol') or '?'
    declared = entry.get('path') or path_of(flow)
    return next((s.get('from_path') for s in steps if s.get('from') == name and s.get('from_path')), declared), name


def _fn_node(nodes, key, level):
    return {'id': f'n{len(nodes)}', 'kind': 'fn', 'label': key[1], 'sub': key[0], 'level': level, 'library': 0}


def _note_stop(step, caller, stops):
    if step.get('callee') and step['callee'] not in stops[caller]: stops[caller].append(step['callee'])


def _caller(step, nodes):
    """The calling function's key, its box added one level below the step's depth when it has none yet."""
    caller = (step.get('from_path') or '', step.get('from') or '')
    if caller not in nodes: nodes[caller] = _fn_node(nodes, caller, (step.get('depth') or 0) + 1)
    return caller


def _add_step(step, nodes, edges, stops):
    caller = _caller(step, nodes)
    resolution = step.get('resolution')
    if resolution in LIBRARY:
        nodes[caller]['library'] = nodes[caller].get('library', 0) + 1
        return
    if resolution in STOP or not step.get('to_path'):
        _note_stop(step, caller, stops)
        return
    callee = (step['to_path'], step.get('to_symbol') or step.get('callee') or '?')
    if callee not in nodes: nodes[callee] = _fn_node(nodes, callee, nodes[caller]['level'] + 1)
    if (caller, callee) not in edges and caller != callee: edges.append((caller, callee))


def _add_stops(nodes, edges, stops):
    for caller, names in stops.items():
        key = ('stop', caller)
        nodes[key] = {'id': f's{len(nodes)}', 'kind': 'stop', 'label': ', '.join(names[:3]), 'more': max(len(names) - 3, 0),
                      'sub': '', 'level': nodes[caller]['level'] + 1, 'count': len(names)}
        edges.append((caller, key))


def _place_level(nodes, members, y, drawn):
    """Lay one level's boxes out, FLOW_PER_ROW to a line; the y below the last line."""
    for start in range(0, len(members), FLOW_PER_ROW):
        line = members[start:start + FLOW_PER_ROW]
        left = PAD + (FLOW_PER_ROW - len(line)) * (FLOW_W + FLOW_GAP_X) / 2
        for p, key in enumerate(line):
            nodes[key]['x'], nodes[key]['y'] = round(left + p * (FLOW_W + FLOW_GAP_X)), y
            drawn.append(nodes[key])
        y += FLOW_H + FLOW_GAP_Y
    return y


def _place_flow(nodes):
    rows = defaultdict(list)
    for key, node in nodes.items(): rows[node['level']].append(key)
    y, drawn = PAD, []
    for level in sorted(rows):
        members = sorted(rows[level], key=lambda k: (nodes[k]['kind'] == 'stop', nodes[k].get('sub') or '', nodes[k]['label']))
        y = _place_level(nodes, members, y, drawn)
    return [{k: v for k, v in n.items() if k != 'level'} for n in drawn], y


def _start_nodes(entry, handler):
    """A chart's first two boxes: the route, and the handler it calls."""
    return {'entry': {'id': 'entry', 'kind': 'entry', 'label': entry.get('route') or '', 'sub': entry.get('http_method') or entry.get('surface') or '', 'level': 0},
            handler: {'id': 'h', 'kind': 'handler', 'label': handler[1], 'sub': handler[0], 'level': 1, 'library': 0}}


def _flow_head(flow, value, entry, number):
    """A chart's id, surface, route and method."""
    return {'id': value.get('flow_id') or flow.get('id') or f'FLOW-{number}', 'surface': entry.get('surface') or '',
            'route': entry.get('route') or '', 'method': entry.get('http_method') or ''}


def _flow_chart(flow, number):
    value = flow.get('value') or {}
    entry = value.get('entry') or {}
    steps = [s for s in value.get('steps') or [] if isinstance(s, dict)]
    handler = _flow_handler(flow, entry, steps)
    nodes = _start_nodes(entry, handler)
    edges, stops = [('entry', handler)], defaultdict(list)
    for step in sorted(steps, key=lambda s: s.get('depth') or 0): _add_step(step, nodes, edges, stops)
    _add_stops(nodes, edges, stops)
    drawn, y = _place_flow(nodes)
    width = PAD * 2 + FLOW_PER_ROW * FLOW_W + (FLOW_PER_ROW - 1) * FLOW_GAP_X
    return {**_flow_head(flow, value, entry, number), 'handler': handler[1], 'path': handler[0],
            'found': bool(value.get('handler_found', True)), 'nodes': drawn,
            'edges': [[nodes[a]['id'], nodes[b]['id']] for a, b in edges], 'width': width, 'height': y - FLOW_GAP_Y + PAD,
            'steps': len(steps), 'stops': sum(len(v) for v in stops.values())}


# ---------------------------------------------------------------- the target, and the gap closed in each part

def target_owner(target):
    """{path: target component name}: through today's part a file belongs to, else the target's own path list."""
    target, out = target or {}, {}
    for c in target.get('target_components') or []:
        for p in c.get('paths') or []: out.setdefault(p, c.get('name'))
    for c in target.get('current_components') or []:
        if c.get('target_component'): out.update(dict.fromkeys(c.get('paths') or [], c['target_component']))
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
