"""The territory map's land (eaos/report/studio/territory.py): per region, a summed gaussian "mass" field of its dots,
cut by marching squares at three levels (filled outer land, filled inner land, a dashed inner line), smoothed by
Chaikin's corner cutting. Pure Python, as the rest of the map."""
import math
from collections import defaultdict

GRID = 6                       # world units per cell of the mass field
LEVELS = (0.32, 1.25, 2.4)     # the three contour levels

# The sides a contour crosses in each marching-squares cell (0 top, 1 right, 2 bottom, 3 left), by its corner index.
MARCH = {1: ((3, 2),), 2: ((2, 1),), 3: ((3, 1),), 4: ((0, 1),), 5: ((3, 0), (2, 1)), 6: ((0, 2),), 7: ((3, 0),),
         8: ((0, 3),), 9: ((0, 2),), 10: ((0, 1), (3, 2)), 11: ((0, 1),), 12: ((3, 1),), 13: ((2, 1),), 14: ((3, 2),)}


def _march(field, level, x0, y0):
    """Marching squares over field[row][col] (cell = GRID units, origin x0, y0): closed polylines in world units."""
    return [[(x0 + cx * GRID, y0 + cy * GRID) for _, (cx, cy) in chain]
            for chain in _chains(_segments(field, level)) if len(chain) > 6]


def _segments(field, level):
    """Every piece of the contour at `level`, cell by cell: ((edge key, point), (edge key, point))."""
    rows, cols = len(field), len(field[0])
    segs = []
    for y in range(rows - 1):
        up, down = field[y], field[y + 1]
        for x in range(cols - 1):
            corners = up[x], up[x + 1], down[x + 1], down[x]
            a, b, c, d = corners
            idx = (a >= level) * 8 + (b >= level) * 4 + (c >= level) * 2 + (d >= level)
            if idx == 0 or idx == 15: continue
            for p, q in MARCH[idx]:
                segs.append((_cut(p, x, y, corners, level), _cut(q, x, y, corners, level)))
    return segs


def _cut(side, x, y, corners, level):
    """Where the contour crosses one side of the cell at (x, y): (the side's key, the point)."""
    a, b, c, d = corners
    if side == 0: return ('h', x, y), (x + _t(a, b, level), y)
    if side == 1: return ('v', x + 1, y), (x + 1, y + _t(b, c, level))
    if side == 2: return ('h', x, y + 1), (x + _t(d, c, level), y + 1)
    return ('v', x, y), (x, y + _t(a, d, level))


def _chains(segs):
    """The segments joined end to end into chains, each segment used once."""
    ends = defaultdict(list)
    for i, (p, q) in enumerate(segs):
        ends[p[0]].append(i)
        ends[q[0]].append(i)
    used = [False] * len(segs)
    chains = []
    for i in range(len(segs)):
        if used[i]: continue
        used[i] = True
        chains.append(_follow([segs[i][0], segs[i][1]], segs, ends, used))
    return chains


def _follow(chain, segs, ends, used):
    """Grow a chain from its last point along the unused segments that share it."""
    while True:
        key = chain[-1][0]
        nxt = next((j for j in ends[key] if not used[j]), None)
        if nxt is None: return chain
        used[nxt] = True
        p, q = segs[nxt]
        chain.append(q if p[0] == key else p)


def _t(p, q, level):
    return (level - p) / (q - p) if q != p else 0.5


def _chaikin(pts, rounds=2):
    for _ in range(rounds):
        out = []
        for i, p in enumerate(pts):
            q = pts[(i + 1) % len(pts)]
            out.append((0.75 * p[0] + 0.25 * q[0], 0.75 * p[1] + 0.25 * q[1]))
            out.append((0.25 * p[0] + 0.75 * q[0], 0.25 * p[1] + 0.75 * q[1]))
        pts = out
    return pts


def path_d(pts):
    return 'M' + 'L'.join(f'{x:.0f},{y:.0f}' for x, y in pts) + 'Z'


def land(members, pos, world):
    """[{level, d}] for one region: the contours of its dots' summed gaussian field; `world`: (width, height)."""
    if not members: return []
    reach = [(pos[n['id']], n['r'] + 16, 1 + n['files'] / 11) for n in members]
    field, x0, y0 = _field(reach, world)
    out = []
    for li, level in enumerate(LEVELS):
        for line in _march(field, level, x0, y0):
            out.append({'level': li, 'd': path_d(_chaikin(line[::2] if len(line) > 24 else line, 2))})
    return out


def _frame(reach, world):
    """(x0, y0, x1, y1): the field's frame on the grid, three spreads around every dot, inside the world."""
    x0 = max(0, int(min(p[0] - 3 * s for p, s, _ in reach) // GRID * GRID) - GRID)
    y0 = max(0, int(min(p[1] - 3 * s for p, s, _ in reach) // GRID * GRID) - GRID)
    x1 = min(world[0], max(p[0] + 3 * s for p, s, _ in reach) + 2 * GRID)
    y1 = min(world[1], max(p[1] + 3 * s for p, s, _ in reach) + 2 * GRID)
    return x0, y0, x1, y1


def _field(reach, world):
    """(field[row][col], x0, y0): the summed gaussian mass of the dots `reach` ((x, y), spread, weight) on the grid."""
    x0, y0, x1, y1 = _frame(reach, world)
    cols, rows = int((x1 - x0) // GRID) + 2, int((y1 - y0) // GRID) + 2
    field = [[0.0] * cols for _ in range(rows)]
    for (px, py), sigma, weight in reach:
        two = 2 * sigma * sigma
        c0, c1 = max(1, int((px - 3 * sigma - x0) // GRID)), min(cols - 2, int((px + 3 * sigma - x0) // GRID) + 1)
        r0, r1 = max(1, int((py - 3 * sigma - y0) // GRID)), min(rows - 2, int((py + 3 * sigma - y0) // GRID) + 1)
        gx = [math.exp(-((x0 + c * GRID - px) ** 2) / two) for c in range(c0, c1 + 1)]
        for r in range(r0, r1 + 1):
            gy = weight * math.exp(-((y0 + r * GRID - py) ** 2) / two)
            row = field[r]
            for k, c in enumerate(range(c0, c1 + 1)):
                row[c] += gy * gx[k]
    return field, x0, y0
