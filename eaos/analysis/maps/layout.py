"""The layered drawing of a directed graph, shared by every map EAOS draws (eaos/analysis/maps/architecture.py, analysis/maps/pipeline.py,
the Studio's maps): Tarjan's strongly connected groups; inside a cycle the lightest edges set aside (Eades' greedy
order) so that the rest can be layered by the longest path; a few barycentre passes ordering each layer to cross fewer
edges; and the boxes' places.
"""
from collections import Counter, defaultdict

NODE_W, NODE_H, COL_GAP, ROW_GAP, PAD = 186, 50, 70, 16, 16


def strong_groups(ids, edges):
    """{id: group number} of Tarjan's strongly connected groups, iteratively (a deep project must not hit recursion)."""
    out = defaultdict(list)
    for a, b in edges: out[a].append(b)
    index, low, stack, on, group, work = {}, {}, [], set(), {}, []
    def enter(node):
        index[node] = low[node] = len(index); stack.append(node); on.add(node)
        work.append((node, iter(out[node])))
    def close(node):
        """Number the group whose root is node: its members, popped off the stack."""
        number = len(set(group.values()))
        while True:
            member = stack.pop(); on.discard(member); group[member] = number
            if member == node: return
    for root in ids:
        if root in index: continue
        enter(root)
        while work:
            node, children = work[-1]
            child = next(children, None)
            if child is not None:
                if child not in index: enter(child)
                elif child in on: low[node] = min(low[node], index[child])
                continue
            work.pop()
            if work: low[work[-1][0]] = min(low[work[-1][0]], low[node])
            if low[node] == index[node]: close(node)
    return group


def _inside_cycles(ids, weights):
    """The weighted edges between two different members of one strongly connected group."""
    group = strong_groups(ids, list(weights))
    return {e: n for e, n in weights.items() if group[e[0]] == group[e[1]] and e[0] != e[1]}


def _ends(remaining, inside):
    """(sinks, sources): the vertices left with no edge going out to another one left, and with none coming in."""
    sinks = [v for v in remaining if not any(a == v and b in remaining for a, b in inside)]
    sources = [v for v in remaining if not any(b == v and a in remaining for a, b in inside)]
    return sinks, sources


def feedback_edges(ids, weights):
    """The edges to set aside so the rest has no cycle: Eades' greedy order, weighted, kept inside each cycle only."""
    inside = _inside_cycles(ids, weights)
    remaining, order_left, order_right = set(ids), [], []
    while remaining:
        sinks, sources = _ends(remaining, inside)
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
    for sweep in range(passes): _sweep(columns, neighbours, sweep % 2 == 0)
    return columns


def _sweep(columns, neighbours, forward):
    """One barycentre pass, left to right when forward, else right to left."""
    span = range(1, len(columns)) if forward else range(len(columns) - 2, -1, -1)
    for i in span: columns[i] = _by_barycentre(columns[i], columns[i - 1 if forward else i + 1], neighbours)


def _by_barycentre(column, beside, neighbours):
    fixed = {v: p for p, v in enumerate(beside)}
    def centre(v):
        places = [fixed[u] for u in neighbours[v] if u in fixed]
        return sum(places) / len(places) if places else column.index(v)
    return sorted(column, key=centre)


def _spans(columns, edges):
    """The edges between neighbouring layers, each as its (layer, position) ends, the left end first."""
    place = {v: (i, p) for i, column in enumerate(columns) for p, v in enumerate(column)}
    spans = [(place[a], place[b]) for a, b in edges if a in place and b in place and abs(place[a][0] - place[b][0]) == 1]
    return [(x, y) if x[0] < y[0] else (y, x) for x, y in spans]


def crossings(columns, edges):
    """How many pairs of edges between neighbouring layers cross: the measure the barycentre passes lower."""
    spans = _spans(columns, edges)
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
