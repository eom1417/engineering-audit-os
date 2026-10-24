"""REPORT.html's charts, drawn as inline SVG: the severity bars, the heat treemap, the layers of the target."""
from ...analysis import model as M
from ...core.markup import esc, svg_text
from ...analysis.model import AREAS, SEVERITIES
from .words import W


# ---------------------------------------------------------------- charts (SVG)
BAR_WIDTH, BAR_LABEL, BAR_ROW, BAR_HEIGHT = 900, 210, 42, 22


def severity_bars(areas, rtl):
    """Horizontal stacked bars: problems per area, split by severity. One SVG per reading direction."""
    top, plot = max([a['total'] for a in areas.values()] + [1]), BAR_WIDTH - BAR_LABEL - 120
    rows = ''.join(_bar_row(area, areas[area], index * BAR_ROW + 8, plot, top, rtl) for index, area in enumerate(AREAS))
    return (f'<svg viewBox="0 0 {BAR_WIDTH} {BAR_ROW * len(AREAS) + 10}" direction="ltr" role="img" class="chart bars {"l-ar" if rtl else "l-en"}" '
            f'aria-label="{esc("المشاكل لكل مجال حسب الخطورة" if rtl else "Problems per area by severity")}">{rows}</svg>')


def _bar_row(area, data, y, plot, top, rtl):
    """One area's row: its name, a segment per severity it has, and its total."""
    side, align = (0, 'right') if rtl else (1, 'left')
    name = W['structure_area' if area == 'structure' else area][side]
    parts = [svg_text(BAR_WIDTH - 4 if rtl else 4, y + BAR_HEIGHT / 2 + 5, name, 'axis-label', align, rtl)]
    start, segments = BAR_LABEL, [(s, data['counts'][s]) for s in SEVERITIES if data['counts'][s]]
    for position, (severity, count) in enumerate(segments):
        last = position == len(segments) - 1
        length = max(3, plot * count / top) - (0 if last else 2)
        x = (BAR_WIDTH - start - length) if rtl else start
        parts.append(_bar_segment(x, y, length, last, rtl, severity, f'{count} {severity} problems in {area}',
                                  f'{name} — {W[severity][side]}: {count}'))
        start += length + 2
    words = (f'المشاكل: {data["total"]}' if rtl else f'{data["total"]} problems') if data['total'] else ('لا مشاكل' if rtl else 'none')
    parts.append(svg_text((BAR_WIDTH - start - 6) if rtl else start + 6, y + BAR_HEIGHT / 2 + 5, words, 'value-label', align, rtl,
                          f' data-meaning="{esc(str(data["total"]) + " problems in " + area)}"'))
    return ''.join(parts)


def _bar_segment(x, y, length, last, rtl, severity, meaning, words):
    """One severity's segment of a row; the row's last one has its outer end rounded."""
    tail = f' class="seg sev-{severity}" data-meaning="{esc(meaning)}"><title>{esc(words)}</title>'
    if not (last and length > 8): return f'<rect x="{x:.1f}" y="{y}" width="{length:.1f}" height="{BAR_HEIGHT}"{tail}</rect>'
    flat, end, bottom = (x + length, x, y + BAR_HEIGHT) if rtl else (x, x + length, y + BAR_HEIGHT)
    inner = end + 4 if rtl else end - 4
    return (f'<path d="M{flat:.1f},{y} H{inner:.1f} Q{end:.1f},{y} {end:.1f},{y + 4} V{bottom - 4} '
            f'Q{end:.1f},{bottom} {inner:.1f},{bottom} H{flat:.1f} Z"{tail}</path>')


HEAT = ('#f6c9b1', '#ee9a73', '#dd6b3f', '#b84b22', '#8a3514')
HEAT_BINS = (5, 10, 20, 40)     # problems per ten files: below 5, 10, 20, 40, and 40 or more


def heat_step(density):
    return next((i for i, edge in enumerate(HEAT_BINS) if density * 10 < edge), len(HEAT_BINS))


def squarify(items, x, y, width, height):
    """A squarified treemap: [(item, x, y, w, h)] with areas proportional to item['files']."""
    items = [i for i in items if i['size'] > 0]
    total = sum(i['size'] for i in items)
    if not items or total <= 0: return []
    scale = width * height / total
    boxes, rest = [], sorted(items, key=lambda i: -i['size'])
    while rest:
        short = min(width, height)
        row, best = [], float('inf')
        for item in rest:
            trial = row + [item]
            area = sum(i['size'] * scale for i in trial)
            side = area / short
            worst = max(max(side / (i['size'] * scale / side), (i['size'] * scale / side) / side) for i in trial)
            if worst > best: break
            row, best = trial, worst
        area = sum(i['size'] * scale for i in row)
        side = area / short
        offset = 0
        for item in row:
            length = item['size'] * scale / side
            if width >= height: boxes.append((item, x, y + offset, side, length))
            else: boxes.append((item, x + offset, y, length, side))
            offset += length
        if width >= height: x, width = x + side, width - side
        else: y, height = y + side, height - side
        rest = rest[len(row):]
    return boxes


def treemap(components, rtl):
    width, height = 720, 420
    parts = [f'<svg viewBox="0 0 {width} {height}" direction="ltr" role="img" class="chart map {"l-ar" if rtl else "l-en"}" '
             f'aria-label="{esc("أجزاء المشروع اليوم ملونة بكثافة المشاكل" if rtl else "Parts of the project today, coloured by problem density")}">']
    for item, x, y, w_, h in squarify(components, 0, 0, width, height):
        step = heat_step(item['density']) if item['problems'] else None
        fill = HEAT[step] if step is not None else 'var(--tile-empty)'
        ink = 'light' if step is not None and step >= 3 else 'dark'
        name = item['short']
        words = (f'{item["name"]} — {item["files"]} {"ملف" if rtl else "files"}، {item["problems"]} {"مشكلة" if rtl else "problems"}'
                 if rtl else f'{item["name"]} — {item["files"]} files, {item["problems"]} problems')
        meaning = f'{item["files"]} files and {item["problems"]} problems in {item["name"]}'
        parts.append(f'<g class="tile" data-meaning="{esc(meaning)}"><title>{esc(words)}</title>'
                     f'<rect x="{x + 1:.1f}" y="{y + 1:.1f}" width="{max(w_ - 2, 0):.1f}" height="{max(h - 2, 0):.1f}" rx="4" fill="{fill}"/>')
        if w_ > 70 and h > 36:
            limit = int((w_ - 16) / 7.4)
            label = name if len(name) <= limit else '…' + name[-(limit - 1):]
            edge, side = (x + w_ - 8, 'right') if rtl else (x + 8, 'left')
            parts.append(svg_text(edge, y + 19, label, f'tile-name {ink}', side))
            if h > 50 and w_ > 90:
                count = (f'المشاكل: {item["problems"]}' if rtl else f'{item["problems"]} problems') if item['problems'] else ('بلا مشاكل' if rtl else 'no problems')
                parts.append(svg_text(edge, y + 37, count, f'tile-sub {ink}', side, rtl))
        parts.append('</g>')
    parts.append('</svg>')
    return ''.join(parts)


LAYER_ORDER = ('pages', 'routes', 'server-entry', 'features', 'services', 'engine', 'server-domain', 'security',
               'data-access', 'infrastructure', 'config', 'lib', 'platform')


def layer_diagram(target_components, rtl):
    layers = {}
    for component in target_components:
        layers.setdefault(component.get('layer') or component.get('name') or '?', []).append(component)
    order = sorted(layers, key=lambda name: (LAYER_ORDER.index(name) if name in LAYER_ORDER else len(LAYER_ORDER), name))
    width, row = 360, 30
    parts = [f'<svg viewBox="0 0 {width} {row * len(order) + 4}" direction="ltr" role="img" class="chart layers {"l-ar" if rtl else "l-en"}" '
             f'aria-label="{esc("طبقات البنية المستهدفة" if rtl else "Layers of the target structure")}">']
    for index, name in enumerate(order):
        members = layers[name]
        counts = M.layer_counts(members)
        files = counts['files']
        y = index * row + 2
        words = (f'الأجزاء: {counts["parts"]} · الملفات: {files}' if rtl else f'{counts["parts"]} parts · {files} files')
        meaning = f'{counts["parts"]} target parts and {files} files in the {name} layer'
        parts.append(f'<g data-meaning="{esc(meaning)}"><rect x="2" y="{y}" width="{width - 4}" height="{row - 4}" rx="4" class="layer"/>'
                     + svg_text(width - 12 if rtl else 12, y + 18, words, 'layer-count', 'right' if rtl else 'left', rtl)
                     + svg_text(12 if rtl else width - 12, y + 18, name, 'layer-name', 'left' if rtl else 'right') + '</g>')
    parts.append('</svg>')
    return ''.join(parts)
