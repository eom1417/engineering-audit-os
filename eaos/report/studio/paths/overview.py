"""Every code path at once: the lanes laid out by barycentre sweeps, and the clusters the Studio draws instead of every
step on a large project."""
from collections import Counter, defaultdict

from ....analysis.maps import architecture as arch_map
from .graph import LANES

CLUSTER_AT = 1000         # past this many nodes the Studio never draws every step at once, only the clusters
MAX_CLUSTERS = 150        # the overview's clusters, at most (DESIGN.md §6: SVG stays readable to about 300 nodes)


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
    of, level = _clustering(nodes)
    members, gaps = defaultdict(list), Counter()
    for n in nodes:
        members[of[n['id']]].append(n)
        if n['kind'] == 'gap': gaps[of[n['id']]] += 1
    lane_of = {k: k.split(':', 2)[1] for k in members}
    weight = Counter((of[e['from']], of[e['to']]) for e in edges if e['from'] in of and e['to'] in of and of[e['from']] != of[e['to']])
    clusters = [_cluster(k, lane_of[k], rows, gaps[k], level) for k, rows in sorted(members.items())]
    links = [{'from': a, 'to': b, 'n': n} for (a, b), n in sorted(weight.items())]
    return {'clusters': clusters, 'links': links, 'columns': layout(set(members), lane_of, list(weight)),
            'level': level, 'all': len(nodes) <= CLUSTER_AT}


def _clustering(nodes):
    """({node id: cluster id}, level): the lowest level (8 at most) at which at most MAX_CLUSTERS clusters remain."""
    for level in range(9):
        of = {n['id']: cluster_of(n, level) for n in nodes}
        if len(set(of.values())) <= MAX_CLUSTERS: break
    return of, level


def _cluster(k, lane, rows, gaps, level):
    """One cluster of the overview: its kind and label from its nodes (`rows`), `gaps` of which are gaps."""
    head, single = rows[0], len(rows) == 1
    part = _folder(head['component'], level) if head['component'] else None
    return {'id': k, 'lane': lane, 'kind': 'gap' if gaps == len(rows) else head['kind'] if single else 'group',
            'label': _cluster_label(head, single, gaps, part),
            'component': part, 'reason': head['reason'] if gaps else None,
            'size': len(rows), 'gaps': gaps, 'nodes': sorted(n['id'] for n in rows)[:200]}


def _cluster_label(head, single, gaps, part):
    """A cluster's label: its one node's; else its route group (screens, calls, gaps), its part, its reason or kind."""
    return (head['label'] if single else (head['group'] if head['lane'] in ('screen', 'call') or gaps else None)
            or part or head['reason'] or head['kind'])
