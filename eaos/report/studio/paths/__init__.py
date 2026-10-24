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
for: a prerequisite the plan names, or the last task of an earlier wave touching the same file (eaos/analysis/plan.py waves()).

Here: the parts of today and the section; graph.py: the nodes and links and the builder that walks each entry;
overview.py: the lanes' layout and the clusters; timeline.py: the plan's timeline.
"""
import re
from collections import Counter, defaultdict
from pathlib import Path

from ....analysis import system_map as sm
from .. import path_records, system as system_section
from ..change import _objects
from .graph import LANES, _Builder, _fact_id, _measure
from .overview import CLUSTER_AT, MAX_CLUSTERS, _folder, layout, overview  # noqa: F401  (CLUSTER_AT, MAX_CLUSTERS, _folder: read here by the tests)
from .timeline import timeline

OPERATION = {'retain': 'retain', 'modify': 'refactor', 'rebuild': 'rebuild', 'delete': 'delete', 'retire': 'delete'}
MAX_CARDS = 20
SRC = {
    'paths': 'facts/entrypoints.json#entry_point (a page, or a server route, command or job with a handler)',
    'calls': 'facts/entrypoints.json#data_access',
    'flows': 'facts/flows.json#flow',
    'imports': 'facts/graph.json#graph_node.depends_on',
    'routes': 'facts/entrypoints.json#entry_point (server routes) and file routing (eaos/analysis/system_map.py find_handlers)',
    'tables': 'facts/domain.json#data_table',
    'components': 'target-architecture.json#current_components, target_components',
    'cards': 'cards.json#cards[].paths, milestone',
    'timeline': 'plan.json#waves, milestones, tasks[].prerequisites, tasks[].paths (eaos/analysis/plan.py waves())',
}


def _slug(text):
    return re.sub(r'[^a-z0-9]+', '-', str(text).lower()).strip('-') or 'root'


def _read(report):
    """The records the paths read (eaos/report/studio/path_records.py), each piece empty when its record is missing or broken."""
    report = Path(report)
    r = {'pages': [], 'servers': [], 'routes': [], 'calls': defaultdict(list), 'flows': {}, 'flow_of': {}, 'flow_list': [],
         'functions': defaultdict(list), 'names': defaultdict(set), 'methods': defaultdict(set), 'packages': defaultdict(set),
         'imports': {}, 'tables': defaultdict(list)}
    for reader in path_records.READERS: reader(report, r)
    return r


def components(report):
    """({part of today: {op, target, layer}}, owner of a path, the target parts nothing of today feeds)."""
    target = _target_record(report)
    current = _objects(target.get('current_components'), 'name')
    layers = {t['name']: t.get('layer') for t in _objects(target.get('target_components'), 'name')}
    feeds = Counter(c.get('target_component') for c in current if c.get('target_component'))
    out = {c['name']: {'op': _operation(c, feeds), 'target': c.get('target_component'), 'layer': layers.get(c.get('target_component'))}
           for c in current}
    return out, system_section.owner_of(set(out)), sorted(name for name in layers if not feeds.get(name))


def _target_record(report):
    """target-architecture.json; {} when it is missing or not an object."""
    target = sm._load(Path(report) / 'target-architecture.json', {}) or {}
    return target if isinstance(target, dict) else {}


def _operation(c, feeds):
    """A part's operation: a part kept or refactored into a target that others feed too is merged; a rebuild or a
    delete says more."""
    to = c.get('target_component')
    relation = OPERATION.get(c.get('relation'), 'refactor')
    return 'merge' if to and feeds[to] > 1 and relation in ('retain', 'refactor') else relation


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
    pages = _first_of(r['pages'], lambda e: (e['route'] == '*', e['route'], str(e['handler']), e['path'], e['line'] or 0),
                      lambda e: (e['route'], e['handler']))
    for entry in pages: out.append(_path_row(b, _unique(entry, used), b.page, entry, entry['route'] or '/'))
    servers = _first_of(r['servers'], lambda e: (e['surface'], e['route'], str(e['method']), e['path']), lambda e: (e['path'], e['handler']))
    for entry in servers: out.append(_path_row(b, _unique(entry, used), b.server, entry, _server_title(entry)))
    nodes = _on_paths(out, b.g.nodes)
    parts = sorted({n['component'] for n in nodes if n['component']})
    return out, nodes, b.g.edges, {name: comps[name] for name in parts if name in comps}, new, r


def _server_title(entry):
    """A server path's title: its method and route, else its route or handler."""
    return f"{entry['method']} {entry['route']}" if entry['method'] else entry['route'] or str(entry['handler'])


def _on_paths(out, nodes):
    """The nodes some path draws, each with how many paths draw it."""
    on_path = Counter(n for p in out for column in p['columns'] for n in column)
    return [{**node, 'paths': on_path[nid]} for nid, node in sorted(nodes.items()) if on_path[nid]]


def _first_of(entries, order, same):
    """The entries in `order`, the first of each `same` key only."""
    seen, kept = set(), []
    for entry in sorted(entries, key=order):
        if same(entry) in seen: continue
        seen.add(same(entry))
        kept.append(entry)
    return kept


def _unique(entry, used):
    """A path id from the entry's route and handler, numbered when another path has it."""
    base = _slug(f"{entry['route']} {entry['handler'] or ''}")
    pid, n = base, 2
    while pid in used: pid, n = f'{base}-{n}', n + 1
    used.add(pid)
    return pid


def _path_row(b, pid, walk, entry, title):
    """One path: the links `walk` (the builder's page or server) finds from the entry, laid out in lanes."""
    g = b.g
    start, steps, flow, capped, unresolved = walk(pid, entry)
    steps = list(dict.fromkeys(steps))
    nodes = {start} | {g.edges[i][end] for i in steps for end in ('from', 'to')}
    columns = layout(nodes, {n: g.nodes[n]['lane'] for n in nodes}, [(g.edges[i]['from'], g.edges[i]['to']) for i in steps])
    return {'id': pid, 'title': title, 'handler': entry['handler'], 'surface': entry['surface'], 'entry': start,
            'fact': _fact_id(entry['fact']), 'flow': ((flow or {}).get('value') or {}).get('flow_id'),
            'flow_fact': _fact_id(flow), 'steps': steps, 'columns': columns,
            'gaps': sum(g.nodes[n]['kind'] == 'gap' for n in nodes), 'capped': capped,
            'unresolved': unresolved, 'reach': _reach_of(g, nodes)}


def _reach_of(g, nodes):
    """How far down the lanes a path reaches, gaps aside (the index of its deepest lane)."""
    lanes = {g.nodes[n]['lane'] for n in nodes if g.nodes[n]['kind'] != 'gap'}
    return max((LANES.index(l) for l in lanes), default=0)


# ---------------------------------------------------------------- the section

def paths(report, card_rows, plan=None, lang='ar'):
    """The section's body: {lanes, paths, nodes, edges, components, new, counts, src, timeline}."""
    out, nodes, edges, parts, new, r = code_paths(report, card_rows)
    gaps = Counter(n['reason'] for n in nodes if n['kind'] == 'gap')
    hows = Counter(e['how'] for e in edges)
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
            **_call_counts(nodes, edges),
            'by_call': _measure(hows.get('call', 0), SRC['flows'] + ' (links the flow confirms)'),
            'by_imports': _measure(hows.get('imports', 0), SRC['imports'] + ' (links only the imports support)'),
        },
        'src': SRC,
        'timeline': timeline(plan, card_rows, lang),
    }


def _call_counts(nodes, edges):
    """The calls, and how many of them something answers: a route, a file route, a table or an outside host."""
    calls = [n for n in nodes if n['lane'] == 'call']
    reached = {e['from'] for e in edges if e['how'] in ('route', 'file_route', 'client', 'external')}
    return {'calls': _measure(len(calls), SRC['calls'] + ' (distinct method and URL, or client and table)'),
            'calls_answered': _measure(sum(c['id'] in reached for c in calls), 'paths.json#edges[how in route, file_route, client, external] (distinct calls)')}
