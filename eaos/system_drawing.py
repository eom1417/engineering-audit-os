"""The system map drawn (eaos/system_map.py builds it): where each box sits in its column, and the Mermaid text of
architecture/system.mmd."""
from collections import defaultdict

WIDTH, PAD, ROW, BOX_H, HEAD = 1100, 8, 22, 18, 18
COLUMNS = ((40, 176), (262, 204), (506, 192), (736, 142), (912, 188))   # (x, width): pages, APIs, handlers, modules, data


def _spread(wanted, pitch, top, bottom):
    """y for each item in order, as near its wanted y as the pitch allows, inside [top, bottom]."""
    out, last = [], top - pitch
    for y in wanted:
        last = max(y, last + pitch)
        out.append(last)
    limit = bottom - pitch
    for i in range(len(out) - 1, -1, -1):
        limit = min(out[i], limit)
        out[i] = limit
        limit -= pitch
    shift = top - min(out, default=top)
    return [y + max(shift, 0) for y in out]


def _api_rows(apis, place, bands):
    """Place the APIs grouped by resource, one row each, a band around each group of more than one; the y below them."""
    y = PAD
    groups = defaultdict(list)
    for a in apis: groups[a['group']].append(a)
    for name in sorted(groups):
        members = groups[name]
        if len(members) > 1:
            bands.append({'label': name + '*', 'top': y, 'bottom': y + HEAD + len(members) * ROW, 'n': len(members)})
            y += HEAD
        for a in members:
            place[a['id']] = (1, y); y += ROW
        y += 6 if len(members) > 1 else 0
    return y


def _centre(item, drawing, columns):
    """The mean y of what an item links to in the given columns; the bottom when it links to none."""
    place = drawing['place']
    ys = [place[o][1] for o in drawing['links'][item['id']] if o in place and place[o][0] in columns]
    return sum(ys) / len(ys) if ys else drawing['height']


def _near(items, column, drawing):
    """Each item as near its links in the column before as a row apart allows."""
    height = drawing['height']
    centre = lambda it: _centre(it, drawing, (column - 1,))
    ordered = sorted(items, key=lambda it: (centre(it), it['id']))
    for it, yy in zip(ordered, _spread([min(centre(it), height) for it in ordered], ROW, PAD, height - PAD)):
        drawing['place'][it['id']] = (column, yy)


def _stack(items, column, sources, drawing):
    ordered = sorted(items, key=lambda it: (_centre(it, drawing, sources), it['id']))
    for i, it in enumerate(ordered): drawing['place'][it['id']] = (column, PAD + i * ROW)


def layout(sm):
    """{id: (column, y)}, the API group bands, the column heights and the drawing's size. The APIs set the height:
    grouped by resource, one row each; the others sit near what they link to, a row apart, without overlap."""
    if not sm: return None
    place, bands = {}, []
    y = _api_rows(sm['apis'], place, bands)
    left = [p['id'] for p in sm['pages']] + [c['id'] for c in sm['callers']]
    height = max(y, PAD + len(left) * ROW + (HEAD if sm["callers"] else 0), PAD + len(sm["handlers"]) * ROW) + PAD
    pages_bottom = PAD + len(sm['pages']) * ROW
    for i, p in enumerate(sm['pages']): place[p["id"]] = (0, PAD + i * ROW)
    for i, c in enumerate(sm['callers']): place[c['id']] = (0, pages_bottom + HEAD + i * ROW)
    links = defaultdict(list)
    for e in sm['edges']: links[e['to']].append(e['from']); links[e['from']].append(e['to'])
    drawing = {'place': place, 'links': links, 'height': height}
    _near(sm['handlers'], 2, drawing)
    # parts and data are few and linked to most handlers: their centres all fall mid-height, so they are
    # stacked from the top in the order of those centres, where a reader starts
    _stack(sm['modules'], 3, (2,), drawing)
    _stack(sm['data'], 4, (2, 3), drawing)
    return {'place': place, 'bands': bands, 'width': WIDTH, 'height': height, 'callers_top': pages_bottom if sm['callers'] else None}


# ---------------------------------------------------------------- Mermaid

SHAPES = (('T:', '[("{}")]'), ('P:', '(["{}"])'))   # a table is a cylinder, a page a stadium, the rest a box
EDGE_WORDS = {'call': 'calls', 'uses': 'uses', 'answer': 'answers', 'guess': 'by file name'}
EDGE_ORDER = ('calls', 'answers', 'by file name', 'uses', 'reaches')


def _mermaid_columns(sm):
    """(key, title, [(id, label)]) of each column, pages to data."""
    return (('pages', 'Pages', [(p['id'], f"{p['route']} · {p['component']}") for p in sm['pages']]
             + [(c['id'], f"shared: {c['short']}") for c in sm['callers']]),
            ('apis', 'APIs', [(a['id'], a['key']) for a in sm['apis']]),
            ('handlers', 'Server handlers', [(h['id'], h['short']) for h in sm['handlers'] if h['apis']]),
            ('data', 'Tables and services', [(d['id'], d['name']) for d in sm['data']]))


def _shape(node_id, label):
    form = next((shape for prefix, shape in SHAPES if node_id.startswith(prefix)), '["{}"]')
    return form.format(str(label).replace('"', "'"))


def _mermaid_edges(sm, drawn):
    """The links between drawn boxes, each pair once, in the order of importance."""
    edges = [(e['from'], e['to'], EDGE_WORDS.get(e['kind'], '')) for e in sm['edges'] if e['from'] in drawn and e['to'] in drawn]
    handler_data = {(h['id'], d) for h in sm['handlers'] for d in ['T:' + t for t in h['tables']] + ['S:' + s for s in h['services']]}
    edges += sorted((a, b, 'reaches') for a, b in handler_data if a in drawn and b in drawn)
    rank = lambda edge: EDGE_ORDER.index(edge[2]) if edge[2] in EDGE_ORDER else len(EDGE_ORDER)
    return sorted({(a, b): (a, b, w) for a, b, w in edges}.values(), key=rank)


def mermaid(sm, limit=300):
    """architecture/system.mmd: pages -> APIs -> handlers -> tables and services, each column a subgraph; the links in
    that order of importance (calls, answers, the shared code a page uses, the data reached), capped at `limit`."""
    if not sm: return None
    ids = {}
    node = lambda i: ids.setdefault(i, f'n{len(ids) + 1}')
    lines = ['flowchart LR', f'  %% {len(sm["pages"])} pages, {len(sm["apis"])} APIs, {len(sm["handlers"])} server handlers, '
             f'{len(sm["data"])} tables and services (eaos/system_map.py)']
    drawn = set()
    for key, title, items in _mermaid_columns(sm):
        lines += [f'  subgraph {key}["{title}"]', '    direction TB', *(f'    {node(i)}{_shape(i, label)}' for i, label in items), '  end']
        drawn.update(i for i, _ in items)
    edges = _mermaid_edges(sm, drawn)
    if len(edges) > limit: lines.append(f'  %% {len(edges) - limit} of the {len(edges)} links are left out: only the first {limit} are drawn')
    lines += [f'  {node(a)} -->|{w}| {node(b)}' if w else f'  {node(a)} --> {node(b)}' for a, b, w in edges[:limit]]
    return '\n'.join(lines) + '\n'
