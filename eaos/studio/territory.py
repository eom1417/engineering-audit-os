"""The territory map's geometry (DESIGN.md §6), computed once here so the Studio only draws it.

A map is a set of nodes (components) with a size (files), grouped into regions, and weighted edges between them. This
module turns that into a deterministic picture in a fixed world of W x H units:

    regions      a squarified treemap gives each region its room (weight = the area its dots need); the nodes of a region
                 are kept inside the ellipse of its room
    positions    a few hundred steps of a small force layout: dots push apart (room for their labels), parent and child
                 folders attract, imports inside a region pull a little, every dot is held in its region's ellipse;
                 seeded, so the same input always gives the same map
    land         per region, a summed gaussian "mass" field of its dots, cut by marching squares at three levels (filled
                 outer land, filled inner land, a dashed inner line), smoothed by Chaikin's corner cutting
    labels       region names first; then dots in priority (the large ones first), each label trying below, above, after
                 and before its dot and placed only where it collides with no placed label and no other dot; a large
                 folder is always labelled, a small one with no free spot is labelled only when it is selected
    edges        a quadratic curve between two rims, always bent to the same side of its direction, so the two
                 directions of a pair separate; its width grows with the log of the imports

Ported from the approved mockup (eaos-dev/planning/studio-v2/directions/studio/tools/geo.py, terrain.py), without its
hand-placed regions: here the regions come from the data. Pure Python (EAOS has no numpy); the world is direction
neutral: the Studio mirrors the chrome around it in Arabic, never the geometry.
"""
import hashlib
import math
import random
from collections import defaultdict

W, H = 1000, 900
PAD = 18                       # the water between the world's edge and the land
LEVELS = (0.32, 1.25, 2.4)     # the three contour levels
GRID = 6                       # world units per cell of the mass field
MAX_REGIONS = 7


def radius(files, scale=1.0):
    """r = 4.5 + 3.1 * sqrt(files), scaled down for a crowded map so the dots never cover more than a third of it."""
    return round((4.5 + 3.1 * math.sqrt(max(files, 0))) * scale, 1)


def radius_scale(sizes):
    need = sum(math.pi * (4.5 + 3.1 * math.sqrt(max(f, 0)) + 14) ** 2 for f in sizes)
    return min(1.0, math.sqrt(0.30 * W * H / need)) if need else 1.0


def text_width(text, px, kind):
    """Advance estimate: Plex Mono 0.6em; Plex Sans Arabic about 0.6em; tracked English capitals about 0.8em."""
    return len(text) * px * {'mono': 0.6, 'ar': 0.6, 'caps': 0.8, 'sans': 0.55}[kind]


# ---------------------------------------------------------------- regions

def squarify(weights, x, y, w, h):
    """Squarified treemap (Bruls, Huizing, van Wijk): [(x, y, w, h)] in the order of weights, which must be sorted
    from the largest."""
    total = sum(weights) or 1
    scale = w * h / total
    areas = [v * scale for v in weights]
    out, i = [], 0
    while i < len(areas):
        short = min(w, h)
        row = [areas[i]]
        j = i + 1

        def worst(r):
            s = sum(r)
            return max(max(s * s / (short * short * a), short * short * a / (s * s)) for a in r) if s else math.inf
        while j < len(areas) and worst(row + [areas[j]]) <= worst(row):
            row.append(areas[j])
            j += 1
        s = sum(row)
        if w >= h:                       # a column along the left side
            cw = s / h if h else 0
            cy = y
            for a in row:
                ch = a / cw if cw else 0
                out.append((x, cy, cw, ch))
                cy += ch
            x, w = x + cw, w - cw
        else:                            # a row along the top
            rh = s / w if w else 0
            cx = x
            for a in row:
                rw = a / rh if rh else 0
                out.append((cx, y, rw, rh))
                cx += rw
            y, h = y + rh, h - rh
        i = j
    return out


def rooms(regions):
    """{region id: (cx, cy, rx, ry)}: each region's ellipse inside its treemap room. regions: [(id, weight)]."""
    ordered = sorted(regions, key=lambda r: (-r[1], r[0]))
    rects = squarify([w for _, w in ordered], PAD, PAD, W - 2 * PAD, H - 2 * PAD)
    out = {}
    for (rid, _), (x, y, w, h) in zip(ordered, rects):
        mx, my = min(26.0, w * 0.12), min(26.0, h * 0.12)
        out[rid] = (x + w / 2, y + h / 2 + min(10.0, h * 0.04), max(w / 2 - mx, 8.0), max(h / 2 - my - 10, 8.0))
    return out


# ---------------------------------------------------------------- positions

def _seed(text):
    return int(hashlib.sha256(text.encode('utf-8')).hexdigest()[:8], 16)


def layout(nodes, edges, room, family=()):
    """{id: (x, y)}. nodes: [{id, region, r}]; edges: [(from, to, weight)]; room: {region: ellipse}; family: pairs of
    ids that should sit close (a folder and its subfolder)."""
    ids = [n['id'] for n in nodes]
    if not ids: return {}
    by = {n['id']: n for n in nodes}
    pos = {}
    for n in nodes:
        rnd = random.Random(_seed(n['id']))
        cx, cy, rx, ry = room[n['region']]
        angle, dist = rnd.uniform(0, 2 * math.pi), math.sqrt(rnd.uniform(0, 1)) * 0.7
        pos[n['id']] = [cx + math.cos(angle) * rx * dist, cy + math.sin(angle) * ry * dist]
    links = [(a, b, 0.0015 * math.log1p(n)) for a, b, n in edges if a in by and b in by and a != b and by[a]['region'] == by[b]['region']]
    iters = max(160, min(700, int(500000 / max(len(ids), 1) ** 2)))
    members = defaultdict(int)
    for n in nodes: members[n['region']] += 1
    # a region of few dots is held closer to its centre, so it stays one island instead of scattered rocks
    pull = {r: 0.005 + 0.03 / count for r, count in members.items()}
    count = len(ids)
    for it in range(iters):
        t = 1.0 - it / iters
        force = {i: [0.0, 0.0] for i in ids}
        for i in range(count):
            a = ids[i]
            pa, na = pos[a], by[a]
            for j in range(i + 1, count):
                b = ids[j]
                pb, nb = pos[b], by[b]
                dx, dy = pb[0] - pa[0], pb[1] - pa[1]
                if abs(dx) > 220 or abs(dy) > 220: continue
                d = math.hypot(dx, dy) or 0.01
                same = na['region'] == nb['region']
                push = 0.0
                if same and d < 190: push += 34.0 / d
                want = na['r'] + nb['r'] + (40 if same else 70)
                if d < want: push += (want - d) * 0.5
                if push:
                    ux, uy = dx / d * push, dy / d * push
                    force[a][0] -= ux; force[a][1] -= uy
                    force[b][0] += ux; force[b][1] += uy
        for a, b, k in links:
            dx, dy = pos[b][0] - pos[a][0], pos[b][1] - pos[a][1]
            force[a][0] += dx * k; force[a][1] += dy * k
            force[b][0] -= dx * k; force[b][1] -= dy * k
        for a, b in family:
            dx, dy = pos[b][0] - pos[a][0], pos[b][1] - pos[a][1]
            d = math.hypot(dx, dy) or 0.01
            k = 0.08 * (d - (by[a]['r'] + by[b]['r'] + 24)) / d
            force[a][0] += dx * k; force[a][1] += dy * k
            force[b][0] -= dx * k; force[b][1] -= dy * k
        step, cap = 0.6 + 0.4 * t, 12 * t + 1
        for i in ids:
            cx, cy, rx, ry = room[by[i]['region']]
            p, f = pos[i], force[i]
            k = pull[by[i]['region']]
            f[0] += (cx - p[0]) * k
            f[1] += (cy - p[1]) * k
            ex, ey = (p[0] - cx) / rx, (p[1] - cy) / ry
            ed = math.hypot(ex, ey)
            if ed > 1:
                f[0] -= (p[0] - cx) * (ed - 1) * 0.8
                f[1] -= (p[1] - cy) * (ed - 1) * 0.8
            mag = math.hypot(f[0], f[1])
            if mag > cap: f[0], f[1] = f[0] / mag * cap, f[1] / mag * cap
            r = by[i]['r']
            p[0] = min(max(p[0] + f[0] * step, r + 24), W - r - 24)
            p[1] = min(max(p[1] + f[1] * step, r + 30), H - r - 24)
    return {k: (round(v[0], 1), round(v[1], 1)) for k, v in pos.items()}


# ---------------------------------------------------------------- land

def _march(field, level, x0, y0):
    """Marching squares over field[row][col] (cell = GRID units, origin x0, y0): closed polylines in world units."""
    rows, cols = len(field), len(field[0])
    segs = []
    table = {1: ((3, 2),), 2: ((2, 1),), 3: ((3, 1),), 4: ((0, 1),), 5: ((3, 0), (2, 1)), 6: ((0, 2),), 7: ((3, 0),),
             8: ((0, 3),), 9: ((0, 2),), 10: ((0, 1), (3, 2)), 11: ((0, 1),), 12: ((3, 1),), 13: ((2, 1),), 14: ((3, 2),)}
    for y in range(rows - 1):
        up, down = field[y], field[y + 1]
        for x in range(cols - 1):
            a, b, c, d = up[x], up[x + 1], down[x + 1], down[x]
            idx = (a >= level) * 8 + (b >= level) * 4 + (c >= level) * 2 + (d >= level)
            if idx == 0 or idx == 15: continue

            def cut(side):
                if side == 0: return ('h', x, y), (x + _t(a, b, level), y)
                if side == 1: return ('v', x + 1, y), (x + 1, y + _t(b, c, level))
                if side == 2: return ('h', x, y + 1), (x + _t(d, c, level), y + 1)
                return ('v', x, y), (x, y + _t(a, d, level))
            for p, q in table[idx]:
                segs.append((cut(p), cut(q)))
    ends = defaultdict(list)
    for i, (p, q) in enumerate(segs):
        ends[p[0]].append(i)
        ends[q[0]].append(i)
    used = [False] * len(segs)
    lines = []
    for i in range(len(segs)):
        if used[i]: continue
        used[i] = True
        chain = [segs[i][0], segs[i][1]]
        while True:
            key = chain[-1][0]
            nxt = next((j for j in ends[key] if not used[j]), None)
            if nxt is None: break
            used[nxt] = True
            p, q = segs[nxt]
            chain.append(q if p[0] == key else p)
        if len(chain) > 6:
            lines.append([(x0 + cx * GRID, y0 + cy * GRID) for _, (cx, cy) in chain])
    return lines


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


def land(members, pos):
    """[{level, d}] for one region: the contours of its dots' summed gaussian field."""
    if not members: return []
    reach = [(pos[n['id']], n['r'] + 16, 1 + n['files'] / 11) for n in members]
    x0 = max(0, int(min(p[0] - 3 * s for p, s, _ in reach) // GRID * GRID) - GRID)
    y0 = max(0, int(min(p[1] - 3 * s for p, s, _ in reach) // GRID * GRID) - GRID)
    x1 = min(W, max(p[0] + 3 * s for p, s, _ in reach) + 2 * GRID)
    y1 = min(H, max(p[1] + 3 * s for p, s, _ in reach) + 2 * GRID)
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
    out = []
    for li, level in enumerate(LEVELS):
        for line in _march(field, level, x0, y0):
            out.append({'level': li, 'd': path_d(_chaikin(line[::2] if len(line) > 24 else line, 2))})
    return out


# ---------------------------------------------------------------- edges and labels

def edge_path(p, q, rp, rq, bend=0.16):
    """A quadratic curve between two circles, trimmed at their rims: (d, mid point)."""
    (x1, y1), (x2, y2) = p, q
    dx, dy = x2 - x1, y2 - y1
    cx, cy = (x1 + x2) / 2 - dy * bend, (y1 + y2) / 2 + dx * bend

    def toward(ax, ay, r):
        vx, vy = cx - ax, cy - ay
        length = math.hypot(vx, vy) or 1
        return ax + vx / length * r, ay + vy / length * r
    sx, sy = toward(x1, y1, rp + 1.5)
    ex, ey = toward(x2, y2, rq + 2.5)
    mid = (0.25 * sx + 0.5 * cx + 0.25 * ex, 0.25 * sy + 0.5 * cy + 0.25 * ey)
    return f'M{sx:.1f},{sy:.1f} Q{cx:.1f},{cy:.1f} {ex:.1f},{ey:.1f}', (round(mid[0], 1), round(mid[1], 1))


def _free(box, placed):
    return all(box[2] <= q[0] or box[0] >= q[2] or box[3] <= q[1] or box[1] >= q[3] for q in placed)


def _clamp_x(x, half):
    return min(max(x, half + 6), W - half - 6)


def region_labels(regions, nodes, pos):
    """Per region: {x, y} of its name on the full map (with its counts below) and on the preview (large type)."""
    out, placed = {}, []
    for reg in regions:
        mem = [n for n in nodes if n['region'] == reg['id']]
        if not mem: continue
        xs = [pos[n['id']][0] for n in mem]
        top = min(pos[n['id']][1] - n['r'] for n in mem)
        half = max(text_width(reg['name']['ar'], 15, 'ar'), text_width(reg['name']['en'].upper(), 12, 'caps'),
                   text_width('00 folders · 000 files', 11, 'sans')) / 2
        x, y = _clamp_x((min(xs) + max(xs)) / 2, half), max(top - 26, 22)
        box = (x - half - 4, y - 17, x + half + 4, y + 19)
        while not _free(box, placed) and y < H - 20:      # two regions whose names would meet: the lower one steps down
            y += 8
            box = (x - half - 4, y - 17, x + half + 4, y + 19)
        placed.append(box)
        thumb_half = max(text_width(reg['name']['ar'], 40, 'ar'), text_width(reg['name']['en'].upper(), 30, 'caps')) / 2
        out[reg['id']] = {'x': round(x), 'y': round(y), 'tx': round(_clamp_x(x, thumb_half)), 'ty': round(max(y + 6, 44)),
                          'box': box, 'half': thumb_half}
    return out


def node_labels(nodes, pos, taken):
    """{id: {x, y, anchor, size, placed}}: map labels by priority; `taken` holds the region labels' boxes."""
    placed = list(taken)
    dots = {n['id']: (pos[n['id']][0] - n['r'] - 1, pos[n['id']][1] - n['r'] - 1, pos[n['id']][0] + n['r'] + 1,
                      pos[n['id']][1] + n['r'] + 1) for n in nodes}
    big_files = sorted((n['files'] for n in nodes), reverse=True)
    big_floor = max(13, big_files[min(len(big_files) - 1, 11)] if big_files else 13)
    out = {}
    for n in sorted(nodes, key=lambda n: (-n['files'], n['id'])):
        x, y = pos[n['id']]
        r = n['r']
        big = n['files'] >= big_floor
        px = 13.5 if big else 12
        w = text_width(n['short'], px, 'mono')
        others = [b for k, b in dots.items() if k != n['id']]
        spot = None
        for anchor, lx, ly in (('middle', x, y + r + px + 2), ('middle', x, y - r - 5), ('start', x + r + 5, y + px * .35),
                               ('end', x - r - 5, y + px * .35)):
            if anchor == 'middle':
                lx = _clamp_x(lx, w / 2)
                box = (lx - w / 2 - 2, ly - px, lx + w / 2 + 2, ly + 3)
            elif anchor == 'start':
                box = (lx - 2, ly - px, lx + w + 2, ly + 3)
            else:
                box = (lx - w - 2, ly - px, lx + 2, ly + 3)
            if box[0] < 2 or box[2] > W - 2: continue
            if _free(box, placed) and _free(box, others):
                spot = (anchor, lx, ly, box)
                break
        if spot is None:
            lx = _clamp_x(x, w / 2)
            spot = ('middle', lx, y + r + px + 2, (lx - w / 2, y + r + 2, lx + w / 2, y + r + px + 5))
            if not big:
                out[n['id']] = {'x': round(lx, 1), 'y': round(spot[2], 1), 'anchor': 'middle', 'size': px, 'placed': False, 'big': False}
                continue
        anchor, lx, ly, box = spot
        placed.append(box)
        out[n['id']] = {'x': round(lx, 1), 'y': round(ly, 1), 'anchor': anchor, 'size': px, 'placed': True, 'big': big}
    return out


# ---------------------------------------------------------------- one map

def draw(nodes, edges, regions, family=()):
    """The whole picture of one map.

    nodes: [{id, short, files, region}]; edges: [(from, to, weight)]; regions: [{id, name: {ar, en}}].
    Returns {nodes: {id: {x, y, r, label}}, edges: {(from, to): {d, mid, width}}, regions: {id: {label, land}}}."""
    scale = radius_scale([n['files'] for n in nodes])
    nodes = [{**n, 'r': radius(n['files'], scale)} for n in nodes]
    weight = defaultdict(float)
    for n in nodes: weight[n['region']] += (n['r'] + 22) ** 2
    present = [r for r in regions if weight[r['id']]]
    room = rooms([(r['id'], weight[r['id']] + 2500) for r in present])
    pos = layout(nodes, edges, room, family)
    by = {n['id']: n for n in nodes}
    names = region_labels(present, nodes, pos)
    labels = node_labels(nodes, pos, [v['box'] for v in names.values()])
    out_edges = {}
    for a, b, n in edges:
        if a not in by or b not in by or a == b: continue
        d, mid = edge_path(pos[a], pos[b], by[a]['r'], by[b]['r'])
        out_edges[(a, b)] = {'d': d, 'mid': list(mid), 'width': round(0.6 + 0.6 * math.log1p(n), 2)}
    boxes = [(x - n['r'] - 46, y - n['r'] - 40, x + n['r'] + 46, y + n['r'] + 46) for n in nodes for x, y in [pos[n['id']]]]
    boxes += [(v['box'][0], v['box'][1] - 8, v['box'][2], v['box'][3]) for v in names.values()]
    bounds = [max(0, min(b[0] for b in boxes)), max(0, min(b[1] for b in boxes)), min(W, max(b[2] for b in boxes)),
              min(H, max(b[3] for b in boxes))] if boxes else [0, 0, W, H]
    for v in names.values():                # the preview's large names stay inside the drawn land's frame
        lo, hi = bounds[0] + v['half'] + 6, bounds[2] - v['half'] - 6
        v['tx'] = round(min(max(v['tx'], lo), hi) if lo <= hi else (bounds[0] + bounds[2]) / 2)
    return {'nodes': {n['id']: {'x': pos[n['id']][0], 'y': pos[n['id']][1], 'r': n['r'], 'label': labels[n['id']]} for n in nodes},
            'bounds': [round(bounds[0]), round(bounds[1]), round(bounds[2] - bounds[0]), round(bounds[3] - bounds[1])],
            'edges': out_edges,
            'regions': {r['id']: {'label': {k: v for k, v in names[r['id']].items() if k not in ('box', 'half')},
                                  'land': land([n for n in nodes if n['region'] == r['id']], pos)} for r in present},
            'scale': round(scale, 3)}
