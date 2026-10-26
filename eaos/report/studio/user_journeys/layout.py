"""The journeys' grid, pinned: screens sit on columns (clicks from the start) and rows; a screen that was on the previous
journeys.json of this report keeps its cell, so a node keeps its place across scans and views (eaos/report/studio/user_journeys/).
"""
from ....analysis.maps import architecture as arch_map

COL_W, ROW_H, BOX_W, BOX_H, PAD, MAX_ROWS = 212, 84, 168, 60, 24, 12


def _pinned(previous):
    """{id: (col, row)} of the nodes the previous journeys.json placed."""
    nodes = (previous or {}).get('screens', []) + (previous or {}).get('menus', [])
    return {n['id']: (n['col'], n['row']) for n in nodes
            if isinstance(n, dict) and isinstance(n.get('col'), int) and isinstance(n.get('row'), int)}


def _free_cell(col, taken):
    row = 0
    while (col, row) in taken: row += 1
    taken.add((col, row))
    return col, row


def _place(columns, cells, taken):
    """Each node not pinned in the first free row of its column, a column of more than MAX_ROWS wrapped."""
    start, offset = {}, 0
    for c, column in enumerate(columns):
        start[c] = offset
        offset += max(1, -(-len(column) // MAX_ROWS))
    for c, column in enumerate(columns):
        for i, n in enumerate([n for n in column if n not in cells]):
            cells[n] = _free_cell(start[c] + i // MAX_ROWS, taken)


def layout(nodes, edges, depth, previous):
    """{id: (col, row)} on a grid: columns are clicks from the start (no way in: a last column), rows ordered by the
    barycentre passes of arch_map, a column of more than MAX_ROWS screens wrapped into the next grid columns; a node
    that had a cell in the previous journeys.json keeps it."""
    pinned = _pinned(previous)
    last = max(depth.values(), default=0) + 1
    layer = {n: depth.get(n, last) for n in nodes}
    pairs = [(a, b) for (a, b) in edges if a in layer and b in layer and layer[a] < layer[b]]
    columns = arch_map.order_columns(layer, pairs) if layer else []
    cells, taken = {}, set()
    for n, cell in pinned.items():
        if n in layer and cell not in taken:
            cells[n] = cell
            taken.add(cell)
    _place(columns, cells, taken)
    return cells


def xy(cell):
    return PAD + cell[0] * COL_W, PAD + cell[1] * ROW_H


def curve(a, b):
    """An SVG path from the end side of box a to the start side of box b; a link back or within a column arcs."""
    ax, ay = xy(a)
    bx, by = xy(b)
    if b[0] > a[0]:
        x1, y1, x2, y2 = ax + BOX_W, ay + BOX_H / 2, bx, by + BOX_H / 2
        mid = (x1 + x2) / 2
        return f'M{x1:.0f},{y1:.0f} C{mid:.0f},{y1:.0f} {mid:.0f},{y2:.0f} {x2:.0f},{y2:.0f}'
    x1, y1, x2, y2 = ax + BOX_W / 2, ay, bx + BOX_W / 2, by
    lift = min(28 + 10 * abs(a[0] - b[0]) + 6 * abs(a[1] - b[1]), PAD + 36)
    top = min(y1, y2) - lift
    if a[1] < b[1] and a[0] == b[0]:
        x1, y1, x2, y2 = ax + BOX_W, ay + BOX_H / 2, bx + BOX_W, by + BOX_H / 2
        side = ax + BOX_W + 24 + 6 * (b[1] - a[1])
        return f'M{x1:.0f},{y1:.0f} C{side:.0f},{y1:.0f} {side:.0f},{y2:.0f} {x2:.0f},{y2:.0f}'
    return f'M{x1:.0f},{y1:.0f} C{x1:.0f},{top:.0f} {x2:.0f},{top:.0f} {x2:.0f},{y2:.0f}'
