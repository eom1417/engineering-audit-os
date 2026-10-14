"""The system map drawn (eaos/system_map.py builds it): where each box sits in its column, the SVG of the report for
people, and the Mermaid text of architecture/system.mmd."""
import math
from collections import defaultdict

from .compose.markup import esc, fit, svg_text

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


# ---------------------------------------------------------------- the SVG (the report for people)

METHOD_CLASS = {'GET': 'get', 'POST': 'post', 'PUT': 'put', 'PATCH': 'put', 'DELETE': 'del'}


def _x(c, rtl):
    """The left edge of column `c`, mirrored in Arabic."""
    return (WIDTH - COLUMNS[c][0] - COLUMNS[c][1]) if rtl else COLUMNS[c][0]


def svg_heads(lay, rtl):
    """The band behind each group of APIs, and the head over the shared code that calls the server."""
    out = []
    for band in lay['bands']:
        x = _x(1, rtl)
        out.append(f'<rect x="{x - 4}" y="{band["top"] - 2}" width="{COLUMNS[1][1] + 8}" height="{band["bottom"] - band["top"]:.0f}" rx="7" class="sm-band"/>'
                   + svg_text(x + COLUMNS[1][1] - 4 if rtl else x + 4, band['top'] + 11, band['label'], 'sm-band-l', 'right' if rtl else 'left', attrs=' data-literal="1"'))
    if lay.get('callers_top'):
        x = _x(0, rtl)
        words = 'كود مشترك يستدعي الخادم' if rtl else 'Shared code that calls the server'
        out.append(svg_text(x + COLUMNS[0][1] if rtl else x, lay['callers_top'] + 12, words, 'sm-sub-head', 'right' if rtl else 'left', rtl))
    return out


def svg_edge(e, place, rtl):
    (ca, ya), (cb, yb) = place[e['from']], place[e['to']]
    ya, yb = ya + BOX_H / 2, yb + BOX_H / 2
    if ca == cb:                                    # a page and the shared code it reaches: an arc on the outer side
        ox = _x(0, rtl) + COLUMNS[0][1] if rtl else _x(0, rtl)
        bulge = (10 + min(26, abs(yb - ya) / 18)) * (1 if rtl else -1)
        d = f'M{ox:.0f},{ya:.1f} C{ox + bulge:.1f},{ya:.1f} {ox + bulge:.1f},{yb:.1f} {ox:.0f},{yb:.1f}'
    else:
        sx, ex = (_x(ca, rtl), _x(cb, rtl) + COLUMNS[cb][1]) if rtl else (_x(ca, rtl) + COLUMNS[ca][1], _x(cb, rtl))
        bend = (ex - sx) / 2
        d = f'M{sx:.0f},{ya:.1f} C{sx + bend:.1f},{ya:.1f} {ex - bend:.1f},{yb:.1f} {ex:.0f},{yb:.1f}'
    width = 1 + math.log2(e["n"]) if e["n"] > 1 and e["kind"] != "use" else 1
    return f'<path d="{d}" class="sm-edge k-{e["kind"]}" style="stroke-width:{width:.1f}" data-from="{esc(e["from"])}" data-to="{esc(e["to"])}"/>'


def _node(place, rtl, i, c, first, second='', cls='', tip='', search='', tag='', words=False):
    """One box: its tag (an API's method), its name fitted to the column, and a second line when there is room."""
    x, y = _x(c, rtl), place[i][1]
    tx, anchor = (x + COLUMNS[c][1] - 7, 'start' if words else 'end') if rtl else (x + 7, 'start')
    space = int((COLUMNS[c][1] - 14) / 6.5) - len(tag) - (1 if tag else 0)
    first = (first if len(first) <= space else first[:space - 1] + '…') if words else fit(first, max(space, 8))
    room2 = space - len(first) - 1
    second = (second if len(second) <= room2 else second[:room2 - 1] + '…') if second and room2 > 4 else ''
    spans = (f'<tspan class="sm-tag t-{METHOD_CLASS.get(tag, "any")}">{esc(tag)} </tspan>' if tag else '') + f'<tspan class="sm-l">{esc(first)}</tspan>' + (f'<tspan class="sm-s"> {esc(second)}</tspan>' if second else '')
    return (f'<g class="sm-node {cls}" data-node="{esc(i)}" data-search="{esc(search.lower())}" tabindex="0"><title data-literal="1">{esc(tip or first)}</title>'
            f'<rect x="{x}" y="{y:.1f}" width="{COLUMNS[c][1]}" height="{BOX_H}" rx="5"/>'
            f'<text x="{tx}" y="{y + 13:.1f}" text-anchor="{anchor}" direction="{"rtl" if words and rtl else "ltr"}" data-literal="1">{spans}</text></g>')


def svg_nodes(sm, place, rtl):
    """The boxes of the five columns: pages and their callers, APIs, server handlers, parts, tables and services."""
    node = lambda *args, **named: _node(place, rtl, *args, **named)
    out = []
    for p in sm['pages']:
        tip = f'{p["route"]} → {p["component"]} ({p["file"]})'
        out.append(node(p['id'], 0, p['route'], p['component'], 'n-page' + ('' if p['traced'] else ' untraced'), tip, f'{p["route"]} {p["component"]} {p["file"]}'))
    out += [node(c['id'], 0, c['short'], '', 'n-caller', c['path'], c['path']) for c in sm['callers']]
    for a in sm['apis']:
        cls = 'n-api' + ('' if a['handlers'] else ' unknown') + ('' if a['exact'] or not a['handlers'] else ' guessed')
        out.append(node(a['id'], 1, a['path'], '', cls, a['key'], a['key'] + ' ' + ' '.join(a['features']), a['method']))
    out += [node(h['id'], 2, h['short'], '', 'n-handler' + ('' if h['apis'] else ' idle'), h['path'], h['path']) for h in sm['handlers']]
    out += [node(mo['id'], 3, mo['short'], '', 'n-module', mo['name'], mo['name']) for mo in sm['modules']]
    return out + [_data_node(node, d, rtl) for d in sm['data']]


def _data_node(node, d, rtl):
    """A table, with the files that use it, or a service, named in Arabic when the drawing is."""
    table = d['id'].startswith('T:')
    text = d['name'] if table or not rtl else d.get('ar') or d['name']
    return node(d['id'], 4, text, '', 'n-table' if table else 'n-service', d['name'] + (' — ' + ', '.join(d.get('files') or []) if table else ''),
                d['name'] + ' ' + (d.get('ar') or ''), words=not table)


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
