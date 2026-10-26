"""REPORT.html's target: its layers, the way from today's parts, and the gap each part has closed."""
import math

from ...analysis.presentation import model as M
from ...core.language.markup import both as T, esc, fit, svg_text
from ...analysis.presentation.model import CLOSED
from .arch import arrow_defs, files_word
from .cards import bar, gap_block, pct
from .charts import LAYER_ORDER
from .html import lit, num, tech, unavailable
from .words import RELATION


# ---------------------------------------------------------------- the target: layers, the way from today, the gap closed

TBOX_W, TBOX_H, TBOX_GAP, TLABEL, TWIDTH, TROW_GAP = 146, 62, 10, 150, 1100, 26


def target_rows(tcomps, order=None):
    """[(layer, [components])], from what users see down to the foundation."""
    layers = {}
    for c in tcomps:
        layers.setdefault(c.get('layer') or c.get('name') or '?', []).append(c)
    order = order or LAYER_ORDER
    names = sorted(layers, key=lambda name: (order.index(name) if name in order else len(order), name))
    return [(name, sorted(layers[name], key=lambda c: (c.get('name') != name, -(c.get('files') or 0), c.get('name') or ''))) for name in names]


def _target_layout(rows, rtl):
    """Where every box stands, {name: (x, y)}, the layer bands behind them, and the height of it all."""
    per_line = (TWIDTH - TLABEL) // (TBOX_W + TBOX_GAP)
    boxes, y, bands = {}, 8, []
    for layer, comps in rows:
        lines = [comps[i:i + per_line] for i in range(0, len(comps), per_line)] or [[]]
        band = len(lines) * (TBOX_H + TBOX_GAP) - TBOX_GAP
        bands.append(f'<rect x="0" y="{y - 4}" width="{TWIDTH}" height="{band + 8}" rx="8" class="t-band"/>'
                     + svg_text(TWIDTH - 10 if rtl else 10, y + band / 2 + 5, layer, 't-layer', 'right' if rtl else 'left', attrs=' data-literal="1"'))
        for line in lines:
            for p, c in enumerate(line):
                x = TLABEL + p * (TBOX_W + TBOX_GAP)
                boxes[c.get('name')] = ((TWIDTH - x - TBOX_W) if rtl else x, y)
            y += TBOX_H + TBOX_GAP
        y += TROW_GAP - TBOX_GAP
    return boxes, bands, y


def _target_edge(e, boxes, suffix):
    (ax, ay), (bx, by) = boxes[e['from']], boxes[e['to']]
    sx, ex = ax + TBOX_W / 2, bx + TBOX_W / 2
    if by > ay + 1: d = f'M{sx:.1f},{ay + TBOX_H:.1f} C{sx:.1f},{ay + TBOX_H + 40:.1f} {ex:.1f},{by - 40:.1f} {ex:.1f},{by:.1f}'
    elif by < ay - 1: d = f'M{sx:.1f},{ay:.1f} C{sx:.1f},{ay - 40:.1f} {ex:.1f},{by + TBOX_H + 40:.1f} {ex:.1f},{by + TBOX_H:.1f}'
    else: d = f'M{sx:.1f},{ay + TBOX_H:.1f} C{sx:.1f},{ay + TBOX_H + 22:.1f} {ex:.1f},{by + TBOX_H + 22:.1f} {ex:.1f},{by + TBOX_H:.1f}'
    count = e.get('imports') or 1
    words = f'{e["from"]} → {e["to"]}' + (f': {count}' if e.get('imports') else '')
    return (f'<path d="{d}" class="edge t-edge" style="stroke-width:{1 + math.log2(count):.1f}" marker-end="url(#arr-{suffix})" '
            f'data-from="{esc(e["from"])}" data-to="{esc(e["to"])}" data-meaning="{count} imports the target allows along this link">'
            f'<title>{esc(words)}</title></path>')


def _target_node(c, box, progress, rtl, done):
    name, files, (x, y0) = c.get('name') or '', c.get('files') or 0, box
    closed, total = progress.get(name, (0, 0))
    side, edge = ('right', x + TBOX_W - 8) if rtl else ('left', x + 8)
    share, meaning = (TBOX_W - 16) * closed / total if total else 0, f'{files} files; {closed} of the {total} problems in its files are closed'
    return (f'<g class="t-node{" empty" if not files and not c.get("sub") else ""}" data-node="{esc(name)}" tabindex="0" data-meaning="{esc(meaning)}">'
            f'<title>{esc(name + ": " + (c.get("responsibility") or ""))}</title><rect x="{x:.1f}" y="{y0:.1f}" width="{TBOX_W}" height="{TBOX_H}" rx="7"/>'
            + svg_text(edge, y0 + 17, fit(name, 19), 't-name', side, attrs=' data-literal="1"')
            + svg_text(edge, y0 + 33, _node_line(c, closed, total, rtl, done), 't-sub', side, rtl)
            + f'<rect x="{x + 8:.1f}" y="{y0 + TBOX_H - 16:.1f}" width="{TBOX_W - 16}" height="6" rx="3" class="t-track"/>'
            + (f'<rect x="{(x + TBOX_W - 8 - share) if rtl else x + 8:.1f}" y="{y0 + TBOX_H - 16:.1f}" width="{share:.1f}" height="6" rx="3" class="t-fill"/>' if share else '')
            + '</g>')


def _node_line(c, closed, total, rtl, done):
    """A box's second line: its files (or its own c['sub']) and how many of its problems are closed (`done` names it)."""
    files = c.get('files') or 0
    words = ((f'{done[0]} {closed} من {total}' if rtl else f'{closed} of {total} {done[1]}') if total
             else 'لا مشاكل فيه' if rtl else 'no problem in it')
    sub = (c['sub'][int(not rtl)] if c.get('sub') else f'ملفات {files}' if rtl else f'{files} {files_word(files)}')
    return sub + ' · ' + words


def target_svg(rows, edges, progress, rtl, done=('أُغلق', 'closed')):
    """The target as layers of boxes; every allowed link drawn faint, strong for the part under the pointer.
    A component may bring its own second line as c['sub'] = (Arabic, English); `done` names what its bar counts."""
    boxes, bands, height = _target_layout(rows, rtl)
    suffix, label = ('t-ar', 'البنية المستهدفة طبقة طبقة') if rtl else ('t-en', 'The target structure, layer by layer')
    return (f'<svg viewBox="0 0 {TWIDTH} {height}" direction="ltr" role="img" class="chart tgraph hl-graph {"l-ar" if rtl else "l-en"}" '
            f'aria-label="{esc(label)}"><defs>{arrow_defs(suffix)}</defs>{"".join(bands)}<g class="edges">'
            + ''.join(_target_edge(e, boxes, suffix) for e in edges if e.get('from') in boxes and e.get('to') in boxes) + '</g>'
            + ''.join(_target_node(c, boxes[c.get('name') or ''], progress, rtl, done) for _, comps in rows for c in comps) + '</svg>')


def target_detail(c, progress, sources):
    name = c.get('name') or ''
    closed, total = progress.get(name, (0, 0))
    share = M.closed_share(closed, total)
    from_today = ' '.join(lit(s) for s in sources) or T('لا جزء اليوم؛ يُبنى جديدًا', 'no part today; it is built new')
    tally = (T(f'أُغلق {num(closed, "problems closed in this target part")} من {num(total, "problems in this target part")} ({num(pct(share), "share closed")})',
               f'{num(closed, "problems closed in this target part")} of {num(total, "problems in this target part")} closed ({num(pct(share), "share closed")})')
             if total else T('لا مشاكل في ملفاته.', 'No problem in its files.'))
    files = num(c.get('files') or 0, 'files that belong to this target part')
    return (f'<div class="node-detail card" data-for="{esc(name)}" hidden><h4>{lit(name)} <span class="muted small">{T("الطبقة:", "layer:")} {lit(c.get("layer") or "")}</span></h4>'
            f'<p class="small">{T("مسؤوليته:", "Its job:", cls="lbl")} {tech(c.get("responsibility")) or T("لم تُكتب بعد.", "not written yet.")}</p>'
            f'<p class="small">{T(f"الملفات: {files}", f"{files} files")} · {tally}</p>{bar(share, "thin")}'
            f'<p class="small">{T("يأتي من اليوم:", "Comes from today’s:", cls="lbl")} {from_today}</p></div>')


RELATION_STYLE = {'retain': 'r-keep', 'modify': 'r-modify', 'rebuild': 'r-rebuild', 'delete': 'r-remove', 'retire': 'r-remove', 'introduce': 'r-modify', 'build': 'r-modify'}


def mapping_svg(current, order, rtl, root=''):
    """Today's parts on one side, their place in the target on the other, a line for each: its style says what happens."""
    row, width, gap = 24, 1100, 380
    left, targets = _mapping_order(current, order)
    height = max(len(left), len(targets), 1) * row + 20
    step = (height - 20) / max(len(targets), 1)
    ly = {c.get('id'): 10 + i * row + row / 2 for i, c in enumerate(left)}
    ty = {t: 10 + i * step + step / 2 for i, t in enumerate(targets)}
    a, b = (width - gap, gap) if rtl else (gap, width - gap)      # the line's two ends: today, and the target
    label = 'كل جزء اليوم ومكانه في البنية المستهدفة' if rtl else 'Each part today and its place in the target structure'
    out = [f'<svg viewBox="0 0 {width} {height}" direction="ltr" role="img" class="chart mapping {"l-ar" if rtl else "l-en"}" aria-label="{esc(label)}">']
    out += [_mapping_row(c, (a, ly[c.get('id')]), (b, ty.get(c.get('target_component'))), rtl, root) for c in left]
    out += ['<g class="map-row" data-literal="1">' + svg_text(b + (-10 if rtl else 10), y1 + 4, fit(t, 40), 'm-target', 'right' if rtl else 'left') + '</g>'
            for t, y1 in ty.items()]
    return ''.join(out) + '</svg>'


def _mapping_order(current, order):
    """(today's parts in the order of their targets, the targets in the order of the target's layers `order`)."""
    targets = []
    for c in sorted(current, key=lambda c: (order.index(c.get('target_component')) if c.get('target_component') in order else len(order), c.get('name') or '')):
        if c.get('target_component') and c.get('target_component') not in targets: targets.append(c['target_component'])
    left = sorted(current, key=lambda c: (targets.index(c['target_component']) if c.get('target_component') in targets else len(targets), c.get('name') or ''))
    return left, targets


def _mapping_row(c, today, there, rtl, root):
    """One part of today at `today` (x, y), and its line to its target at `there` (x, y; y None when not drawn)."""
    (a, y1), (b, y2) = today, there
    relation = c.get('relation') or ''
    tip, name = _mapping_names(c, rtl, root)
    return (f'<g class="map-row" data-literal="1"><title>{esc(tip)}</title>'
            + svg_text(a + (10 if rtl else -10), y1 + 4, fit(name, 44), 'm-name', 'left' if rtl else 'right')
            + (f'<path d="M{a},{y1:.1f} C{(a + b) / 2:.1f},{y1:.1f} {(a + b) / 2:.1f},{y2:.1f} {b},{y2:.1f}" class="m-line {RELATION_STYLE.get(relation, "r-modify")}"/>' if y2 is not None else '')
            + '</g>')


def _mapping_names(c, rtl, root):
    """(the hover words: the part, its target and what happens to it, the part's name without the project's root)."""
    relation = c.get('relation') or ''
    words = RELATION.get(relation, (relation, relation))[0 if rtl else 1]
    name = c.get('name') or c.get('id') or ''
    tip = f'{name} → {c.get("target_component") or "—"}: {words}'
    return tip, name[len(root):] if root and name.startswith(root) and name != root else name


def section_target(m):
    target = m['target']
    tcomps = [c for c in _objects(target.get('target_components')) if c.get('name')]
    cards = m.get('cards') or []
    out = [gap_block(m, cards, chart=False)]
    if not tcomps:
        return ''.join(out) + f'<h3>{T("البنية المستهدفة", "The target structure")}</h3>{unavailable("target")}'
    from ...analysis.maps.architecture import target_progress
    progress = target_progress(target, cards, CLOSED)
    edges, rows = _objects(target.get('target_edges')), target_rows(tcomps)
    current = _objects(target.get('current_components'))
    sources = _sources(current)
    out.append(_target_map(tcomps, rows, edges, progress, sources))
    if current: out.append(_mapping_card(current, rows, target.get('root') or ''))
    out.append(_closed_table(rows, sources, progress))
    return ''.join(out)


def _objects(items):
    """The entries of a record's list that are objects; none when the list is missing."""
    return [x for x in items or [] if isinstance(x, dict)]


def _sources(current):
    """{target part: the names of today's parts that go to it}."""
    sources = {}
    for c in current: sources.setdefault(c.get('target_component'), []).append(c.get('name') or c.get('id') or '')
    return sources


def _target_map(tcomps, rows, edges, progress, sources):
    """The target's layers in both reading directions, its counts, and what a click on each part shows."""
    n_parts, n_layers, n_links = num(M.collection_count(tcomps), 'parts in the target structure'), num(M.collection_count(rows), 'layers in the target'), num(M.collection_count(edges), 'links the target allows')
    return (f'<h3>{T("البنية المستهدفة: ما سيصبح عليه البرنامج", "The target structure: what the program will become")}</h3>'
            f'<div class="card graph-wrap" data-part="target-map"><p class="muted small">{T("كل صف طبقة، من الأعلى (ما يراه المستخدم) إلى الأسفل (الأساس)، وكل مربع جزء له مسؤولية واحدة. الشريط الأخضر في المربع: كم أُغلق من المشاكل في ملفاته. مرّر المؤشر أو اضغط على جزء لترى مسؤوليته وروابطه المسموحة ومن أين يأتي من البنية اليوم.", "Each row is a layer, from the top (what users see) to the bottom (the foundation); each box is a part with one job. The green bar in a box: how much of the problems in its files is closed. Hover or click a part to see its job, its allowed links and where it comes from in today’s structure.")}</p>'
            f'<p class="small">{T(f"الأجزاء: {n_parts} · الطبقات: {n_layers} · الروابط المسموحة: {n_links}", f"{n_parts} parts · {n_layers} layers · {n_links} allowed links")}</p>'
            f'<div class="graph-scroll">{target_svg(rows, edges, progress, True)}{target_svg(rows, edges, progress, False)}</div>'
            + ''.join(target_detail(c, progress, sources.get(c['name'], [])) for c in tcomps) + '</div>')


def _mapping_card(current, rows, root):
    """From today to the target: the key of the line styles used, and the mapping in both reading directions."""
    order = [c['name'] for _, comps in rows for c in comps]
    keys = ''.join(f'<span class="heat-key"><svg width="46" height="12" aria-hidden="true" class="key-line"><path d="M2,6 H44" class="m-line {RELATION_STYLE[r]}"/></svg>'
                   f'{T(*map(esc, RELATION[r]))}</span>' for r in ('retain', 'modify', 'rebuild', 'delete') if any(c.get('relation') == r for c in current))
    return (f'<h3>{T("من اليوم إلى المستهدف", "From today to the target")}</h3><div class="card" data-part="target-mapping"><p class="muted small">'
            f'{T("على جانب أجزاء البرنامج اليوم، وعلى الآخر مكان كل منها في البنية المستهدفة. شكل الخط يقول ماذا يحدث للجزء.", "On one side the parts of the program today, on the other where each goes in the target structure. The style of the line says what happens to the part.")}</p>'
            f'<div class="heat-legend">{keys}</div><div class="graph-scroll">{mapping_svg(current, order, True, root)}{mapping_svg(current, order, False, root)}</div></div>')


def _closed_table(rows, sources, progress):
    """The gap closed in each target part, as a table: its layer, files, where it comes from today, problems closed."""
    table = ''.join(
        f'<tr><td>{lit(c["name"])}</td><td>{lit(c.get("layer") or "")}</td><td>{num(c.get("files") or 0, "files in this target part")}</td>'
        f'<td>{" ".join(lit(s) for s in sources.get(c["name"], [])) or T("جديد", "new")}</td>'
        f'<td>{num(progress.get(c["name"], (0, 0))[0], "problems closed here")} / {num(progress.get(c["name"], (0, 0))[1], "problems in this part")}'
        f'{bar(M.closed_share(*progress[c["name"]]), "thin") if progress.get(c["name"], (0, 0))[1] else ""}</td></tr>'
        for _, comps in rows for c in comps)
    return (f'<h3>{T("إغلاق الفجوة في كل جزء مستهدف", "The gap closed in each target part")}</h3><div class="card scroll"><p class="muted small">'
            f'{T("تُحسب المشكلة في كل جزء مستهدف تذهب إليه أحد ملفاتها. المغلق: ما أُصلح ودُمج.", "A problem counts in every target part one of its files goes to. Closed: fixed and merged.")}</p>'
            f'<table class="tbl"><thead><tr><th>{T("الجزء المستهدف", "Target part")}</th><th>{T("الطبقة", "Layer")}</th><th>{T("الملفات", "Files")}</th>'
            f'<th>{T("يأتي من اليوم", "Comes from today’s")}</th><th>{T("المغلق من المشاكل", "Problems closed")}</th></tr></thead><tbody>{table}</tbody></table></div>')
