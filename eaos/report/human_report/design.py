"""The design section of REPORT.html (M18.15): "your design library": what the screens are made of, each part drawn how many ways with its pictures, read
from design/inventory.json. Facts, not cards: it says what is there; nothing here asks a change."""
from ...analysis.design.inventory import CATALOG, LIBRARIES
from ...core.language.markup import both as T, esc
from .html import lit, num

SHOWN_LOOKS, SHOWN_VALUES = 8, 10


def _picture(look):
    if look.get('crop_data'): return f'<img class="crop" alt="" loading="lazy" src="data:image/png;base64,{look["crop_data"]}" style="max-width:220px;max-height:80px">'
    return T('بدون صورة', 'no picture', 'span', 'muted small')


def _look(look):
    where = look['where'][0] if look.get('where') else {}
    return (f'<tr><td>{_picture(look)}</td><td>{num(look["count"], "how many on the screens are drawn this way")}</td>'
            f'<td>{num(look["pages"], "pages showing this look")}</td><td>{lit(where.get("page", ""))}</td></tr>')


def _component(role, part):
    ar, en = CATALOG['components'][role]
    count, looks = num(part['count'], f'{en} on the screens'), num(len(part['looks']), f'distinct looks of {en}')
    rows = ''.join(_look(look) for look in part['looks'][:SHOWN_LOOKS])
    head = f'<tr><th>{T("الشكل", "The look")}</th><th>{T("كم مرة", "How many")}</th><th>{T("في كم صفحة", "On pages")}</th><th>{T("مثال", "Example")}</th></tr>'
    return (f'<div class="card" data-design-role="{esc(role)}"><h4>{T(f"{ar}: {looks} شكل لـ{count}", f"{en}: {looks} looks for {count}")}</h4>'
            f'<table>{head}{rows}</table></div>')


def _value_kind(kind, part):
    ar, en = CATALOG['values'][kind]['words']
    rows = ''.join(f'<li>{lit(row["value"])} {num(row["uses"], f"uses of this value of {en}")}</li>' for row in part['rows'][:SHOWN_VALUES])
    distinct = num(part['distinct'], f'distinct values of {en}')
    return f'<div class="card" data-design-kind="{esc(kind)}"><h4>{T(f"{ar}: {distinct} قيمة", f"{en}: {distinct} values")}</h4><ul class="small">{rows}</ul></div>'


def _formats(formats):
    if not formats: return ''
    rows = []
    for kind, found in formats.items():
        ar, en = CATALOG['formats'][kind]['words']
        forms = ', '.join(f'{lit(row["form"])} {num(row["count"], "how many times this form shows")}' for row in found)
        rows.append(f'<li>{T(esc(ar), esc(en))}: {forms}</li>')
    return f'<div class="card"><h4>{T("كيف تظهر التواريخ والأرقام", "How dates and numbers show")}</h4><ul>{"".join(rows)}</ul></div>'


def _libraries(found):
    if not found: return ''
    rows = ''.join(f'<li>{T(*map(esc, LIBRARIES["jobs"][job]["words"]))}: {", ".join(lit(name) for name in names)}</li>' for job, names in found.items())
    return f'<div class="card"><h4>{T("مكتبتين أو أكثر لنفس الشغلة", "Two or more libraries for one job")}</h4><ul>{rows}</ul></div>'


def _near(groups):
    if not groups: return ''
    rows = ''.join(f'<li>{", ".join(lit(value) for value in group)}</li>' for group in groups[:SHOWN_VALUES])
    return f'<div class="card"><h4>{T("ألوان متقاربة تبدو كأنها لون واحد", "Near colours that read as one")}</h4><ul class="small">{rows}</ul></div>'


def section_design(m):
    drawn = m.get('design')
    if not drawn: return f'<div class="card">{T("التطبيق ما اشتغل في هذا الفحص، فما انقرأت شاشاته.", "The app did not run in this check, so its screens were not read.")}</div>'
    pages = num(drawn['pages'], 'pages the inventory read')
    head = f'<div class="card"><p>{T(f"من {pages} صفحة، في حالاتها: عادي، hover، focus، ضغط.", f"From {pages} pages, in their states: normal, hover, focus, pressed.")}</p></div>'
    order = sorted(drawn['components'].items(), key=lambda item: -len(item[1]['looks']))
    return (head + ''.join(_component(role, part) for role, part in order) + _libraries(drawn['libraries']) + _formats(drawn['formats']) + _near(drawn['near_colours'])
            + ''.join(_value_kind(kind, part) for kind, part in drawn['values'].items()))
