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
                 (eaos/report/studio/territory_land.py)
    labels       region names first; then dots in priority (the large ones first), each label trying below, above, after
                 and before its dot and placed only where it collides with no placed label and no other dot; a large
                 folder is always labelled, a small one with no free spot is labelled only when it is selected
    edges        a quadratic curve between two rims, always bent to the same side of its direction, so the two
                 directions of a pair separate; its width grows with the log of the imports

Ported from the approved mockup (its geo.py and terrain.py), without its
hand-placed regions: here the regions come from the data. Pure Python (EAOS has no numpy); the world is direction
neutral: the Studio mirrors the chrome around it in Arabic, never the geometry.
"""
import hashlib
import math
import random
from collections import defaultdict
from dataclasses import dataclass

from .territory_land import land

W, H = 1000, 900
PAD = 18                       # the water between the world's edge and the land
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
        while j < len(areas) and _worst(row + [areas[j]], short) <= _worst(row, short):
            row.append(areas[j])
            j += 1
        x, y, w, h = _lay_row(row, (x, y, w, h), out)
        i = j
    return out


def _worst(r, short):
    """The worst aspect ratio of a row of areas laid along a side of length `short`."""
    s = sum(r)
    return max(max(s * s / (short * short * a), short * short * a / (s * s)) for a in r) if s else math.inf


def _lay_row(row, rect, out):
    """Lay one row of areas into out, in the room `rect` (x, y, w, h); (x, y, w, h) of the room left."""
    x, y, w, h = rect
    s = sum(row)
    if w >= h:                           # a column along the left side
        cw = s / h if h else 0
        cy = y
        for a in row:
            ch = a / cw if cw else 0
            out.append((x, cy, cw, ch))
            cy += ch
        return x + cw, y, w - cw, h
    rh = s / w if w else 0               # a row along the top
    cx = x
    for a in row:
        rw = a / rh if rh else 0
        out.append((cx, y, rw, rh))
        cx += rw
    return x, y + rh, w, h - rh


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
    pos = {n['id']: _start(n, room) for n in nodes}
    links = _links(edges, by)
    iters = max(160, min(700, int(500000 / max(len(ids), 1) ** 2)))
    walk = _Walk(ids, pos, by, room, _pulls(nodes))
    for it in range(iters):
        force = {i: [0.0, 0.0] for i in ids}
        _repel(ids, pos, by, force)
        _attract(pos, by, force, links, family)
        _move(walk, force, 1.0 - it / iters)
    return {k: (round(v[0], 1), round(v[1], 1)) for k, v in pos.items()}


def _links(edges, by):
    """The imports inside one region, each pulling its two dots by the log of its weight."""
    return [(a, b, 0.0015 * math.log1p(n)) for a, b, n in edges if a in by and b in by and a != b and by[a]['region'] == by[b]['region']]


def _pulls(nodes):
    """{region: how hard its dots are held to its centre}."""
    members = defaultdict(int)
    for n in nodes: members[n['region']] += 1
    # a region of few dots is held closer to its centre, so it stays one island instead of scattered rocks
    return {r: 0.005 + 0.03 / count for r, count in members.items()}


def _start(n, room):
    """A dot's first place: seeded by its id, somewhere in the inner part of its region's ellipse."""
    rnd = random.Random(_seed(n['id']))
    cx, cy, rx, ry = room[n['region']]
    angle, dist = rnd.uniform(0, 2 * math.pi), math.sqrt(rnd.uniform(0, 1)) * 0.7
    return [cx + math.cos(angle) * rx * dist, cy + math.sin(angle) * ry * dist]


def _push(na, nb, d):
    """How hard two dots this far apart push each other: dots of one region keep a little room, every dot its size."""
    same = na['region'] == nb['region']
    push = 0.0
    if same and d < 190: push += 34.0 / d
    want = na['r'] + nb['r'] + (40 if same else 70)
    if d < want: push += (want - d) * 0.5
    return push


def _repel(ids, pos, by, force):
    count = len(ids)
    for i in range(count):
        a = ids[i]
        pa = pos[a]
        for j in range(i + 1, count):
            b = ids[j]
            dx, dy = pos[b][0] - pa[0], pos[b][1] - pa[1]
            if abs(dx) > 220 or abs(dy) > 220: continue
            d = math.hypot(dx, dy) or 0.01
            push = _push(by[a], by[b], d)
            if push:
                ux, uy = dx / d * push, dy / d * push
                force[a][0] -= ux; force[a][1] -= uy
                force[b][0] += ux; force[b][1] += uy


def _attract(pos, by, force, links, family):
    """Linked dots pull together by their links' weight; a folder and its subfolder towards a set distance."""
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


@dataclass
class _Walk:
    """What the layout's walk holds from step to step: the dots (ids in order, positions, nodes by id) and each
    region's room (its ellipse) and pull toward its centre."""
    ids: list
    pos: dict
    by: dict
    room: dict
    pull: dict


def _move(walk, force, t):
    """One step, smaller as the walk cools (t from 1 to 0): each dot pulled to its region's centre, held inside it."""
    ids, pos, by, room, pull = walk.ids, walk.pos, walk.by, walk.room, walk.pull
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


def _step_down(x, y, half, height, placed):
    """(y, box) of a name centred on x: two names that would meet, the lower one steps down; its box joins `placed`."""
    box = (x - half - 4, y - height[0], x + half + 4, y + height[1])
    while not _free(box, placed) and y < H - 20:
        y += 8
        box = (x - half - 4, y - height[0], x + half + 4, y + height[1])
    placed.append(box)
    return y, box


# The height of a region's large name on the preview: (above, below) its baseline
THUMB_NAME = (40, 10)


def region_labels(regions, nodes, pos):
    """Per region: {x, y} of its name on the full map (with its counts below) and {tx, ty} on the preview (large type),
    each kept clear of the other names of its map."""
    out, placed, thumbs = {}, [], []
    for reg in regions:
        mem = [n for n in nodes if n['region'] == reg['id']]
        if not mem: continue
        xs = [pos[n['id']][0] for n in mem]
        top = min(pos[n['id']][1] - n['r'] for n in mem)
        half = max(text_width(reg['name']['ar'], 15, 'ar'), text_width(reg['name']['en'].upper(), 12, 'caps'),
                   text_width('00 folders · 000 files', 11, 'sans')) / 2
        x = _clamp_x((min(xs) + max(xs)) / 2, half)
        y, box = _step_down(x, max(top - 26, 22), half, (17, 19), placed)
        thumb_half = max(text_width(reg['name']['ar'], 40, 'ar'), text_width(reg['name']['en'].upper(), 30, 'caps')) / 2
        tx = _clamp_x(x, thumb_half)
        ty, _ = _step_down(tx, max(y + 6, 44), thumb_half, THUMB_NAME, thumbs)
        out[reg['id']] = {'x': round(x), 'y': round(y), 'tx': round(tx), 'ty': round(ty), 'box': box, 'half': thumb_half}
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
        spot = _spot((x, y, r), (w, px), placed, others)
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


def _spot(dot, label, placed, others):
    """(anchor, x, y, box) of the first free place for the label (w, px) of the dot (x, y, r): below, above, right,
    left; None when none is."""
    (x, y, r), (w, px) = dot, label
    for anchor, lx, ly in (('middle', x, y + r + px + 2), ('middle', x, y - r - 5), ('start', x + r + 5, y + px * .35),
                           ('end', x - r - 5, y + px * .35)):
        lx, box = _label_box(anchor, lx, ly, w, px)
        if box[0] < 2 or box[2] > W - 2: continue
        if _free(box, placed) and _free(box, others): return anchor, lx, ly, box
    return None


def _label_box(anchor, lx, ly, w, px):
    """(x, box) of a label of width w anchored at (lx, ly); a centred one is kept inside the world."""
    if anchor == 'middle':
        lx = _clamp_x(lx, w / 2)
        return lx, (lx - w / 2 - 2, ly - px, lx + w / 2 + 2, ly + 3)
    if anchor == 'start': return lx, (lx - 2, ly - px, lx + w + 2, ly + 3)
    return lx, (lx - w - 2, ly - px, lx + 2, ly + 3)


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
    out_edges = _edge_shapes(edges, pos, by)
    bounds = _bounds(nodes, pos, names)
    _fit_names(names, bounds)
    return {'nodes': {n['id']: {'x': pos[n['id']][0], 'y': pos[n['id']][1], 'r': n['r'], 'label': labels[n['id']]} for n in nodes},
            'bounds': [round(bounds[0]), round(bounds[1]), round(bounds[2] - bounds[0]), round(bounds[3] - bounds[1])],
            'edges': out_edges,
            'regions': _regions_out(present, names, nodes, pos),
            'scale': round(scale, 3)}


def _regions_out(present, names, nodes, pos):
    """{region: {label, land}} of the regions drawn."""
    return {r['id']: {'label': {k: v for k, v in names[r['id']].items() if k not in ('box', 'half')},
                      'land': land([n for n in nodes if n['region'] == r['id']], pos, (W, H))} for r in present}


def _edge_shapes(edges, pos, by):
    """{(from, to): {d, mid, width}} for every edge between two drawn dots."""
    out_edges = {}
    for a, b, n in edges:
        if a not in by or b not in by or a == b: continue
        d, mid = edge_path(pos[a], pos[b], by[a]['r'], by[b]['r'])
        out_edges[(a, b)] = {'d': d, 'mid': list(mid), 'width': round(0.6 + 0.6 * math.log1p(n), 2)}
    return out_edges


def _bounds(nodes, pos, names):
    """[x0, y0, x1, y1] of the drawn land: every dot with room for its label, and the region names."""
    boxes = [(x - n['r'] - 46, y - n['r'] - 40, x + n['r'] + 46, y + n['r'] + 46) for n in nodes for x, y in [pos[n['id']]]]
    boxes += [(v['box'][0], v['box'][1] - 8, v['box'][2], v['box'][3]) for v in names.values()]
    return [max(0, min(b[0] for b in boxes)), max(0, min(b[1] for b in boxes)), min(W, max(b[2] for b in boxes)),
            min(H, max(b[3] for b in boxes))] if boxes else [0, 0, W, H]


def _fit_names(names, bounds):
    """The preview's large names stay inside the drawn land's frame; a name moved in from the edge onto another steps
    down clear of it again, so no two names overlap."""
    placed = []
    for v in names.values():
        lo, hi = bounds[0] + v['half'] + 6, bounds[2] - v['half'] - 6
        v['tx'] = round(min(max(v['tx'], lo), hi) if lo <= hi else (bounds[0] + bounds[2]) / 2)
        v['ty'], _ = _step_down(v['tx'], v['ty'], v['half'], THUMB_NAME, placed)
