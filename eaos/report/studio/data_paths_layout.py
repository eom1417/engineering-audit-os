"""The data map's overview (studio/data_paths.json current and target, eaos/report/studio/data_paths.py): callers and
stores in two lanes, a lane longer than MAX_LANE clustered by family, the weighted write and read edges, and every
box's place, so every view and every reader draws the same places."""
import re
from collections import Counter, defaultdict

from ...analysis.maps import architecture as arch_map

MAX_LANE = 40
LANE_X = {'caller': 0, 'store': 1}
BOX_W, BOX_H, ROW_GAP, LANE_GAP, PAD = 220, 34, 10, 300, 24


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


def _weights(stores, edges_of, group_of, clusters):
    """Counter {(caller lane node, store lane node, write or read): modules}; a module that writes a store is not
    counted again as reading it."""
    writers_of, readers_of = edges_of
    caller_cluster, store_cluster = clusters
    weight = Counter()
    for s in stores:
        for kind, modules in (('write', writers_of.get(s, set())), ('read', readers_of.get(s, set()) - writers_of.get(s, set()))):
            for group in (group for group in map(group_of, modules) if group is not None):
                weight[(caller_cluster.get(group, group), store_cluster.get(s, s), kind)] += 1
    return weight


def _clustered(ids, cluster):
    """A lane's nodes: each id, or the cluster it is folded into, once."""
    return sorted({cluster.get(i, i) for i in ids})


def _cluster_rows(caller_cluster, store_cluster):
    clusters = []
    for lane, mapping in (('caller', caller_cluster), ('store', store_cluster)):
        members = defaultdict(list)
        for node, cluster in mapping.items(): members[cluster].append(node)
        clusters += [{'id': cid, 'lane': lane, 'members': sorted(m)} for cid, m in sorted(members.items())]
    return clusters


def view(edges_of, stores, group_of, families, pinned=None):
    """One overview of the data map: lanes of callers (grouped as `group_of` says) and stores, clustered above MAX_LANE, with their
    weighted write and read edges, laid out. `edges_of`: (writers of each store, readers of each store); `families`:
    (a store's family, a caller's family), what a lane too long is clustered by."""
    writers_of, readers_of = edges_of
    store_family, caller_family = families
    callers = sorted({group_of(m) for s in stores for m in writers_of.get(s, set()) | readers_of.get(s, set())} - {None})
    caller_cluster = _cluster(callers, caller_family)
    store_cluster = _cluster(list(stores), store_family) if pinned is None else pinned['clusters']
    weight = _weights(stores, edges_of, group_of, (caller_cluster, store_cluster))
    caller_nodes, store_nodes = _clustered(callers, caller_cluster), _clustered(stores, store_cluster)
    pairs = {(a, b) for a, b, _ in weight}
    order, xy, size = _layout(caller_nodes, store_nodes, pairs, pinned and pinned['order'])
    edges = [{'from': a, 'to': b, 'kind': kind, 'modules': n} for (a, b, kind), n in sorted(weight.items())]
    return {'lanes': {'caller': order['caller'], 'store': order['store']},
            'place': {node: [round(x), round(y)] for node, (x, y) in sorted(xy.items())},
            'size': size, 'box': [BOX_W, BOX_H], 'edges': edges,
            'clusters': _cluster_rows(caller_cluster, store_cluster if pinned is None else {})}, store_cluster


def _family_store(sid):
    kind, _, name = sid.partition(':')
    return f"{kind}:{re.split(r'[_/.]', name.lstrip('/'))[0][:12] or name}"


def _family_caller(name):
    return '/'.join(str(name).split('/')[:2])


FAMILIES = (_family_store, _family_caller)      # what a lane too long is clustered by: (a store's, a caller's)
