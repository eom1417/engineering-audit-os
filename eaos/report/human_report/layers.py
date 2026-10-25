"""The layers section of REPORT.html (M6.11): the broken critical boundaries in red first, then each boundary of the
system with its state and its findings, each naming the reference's fix; read from layers.json, computed nowhere here."""
from ...analysis.layers.catalog import BOUNDARIES
from ...core.markup import both as T, esc
from .html import num, sev_chip


def _finding(f):
    return (f'<li data-boundary="{esc(f["boundary"])}">{sev_chip(f["severity"])} {T(esc(f["ar"]), esc(f["en"]))}'
            f'<p class="muted small">{T("الإصلاح: " + esc(f["fix_ar"]), "The fix: " + esc(f["fix_en"]))}</p></li>')


def _boundary(name, found):
    ar, en = BOUNDARIES[name]
    state = (T('سليم: لم أجد شيئًا', 'Sound: nothing found', 'p', 'muted') if not found
             else f'<ul class="findings">{"".join(_finding(f) for f in found)}</ul>')
    return (f'<div class="card" data-layer-boundary="{name}"><h4>{T(esc(ar), esc(en))} '
            f'{num(len(found), "findings at this boundary")}</h4>{state}</div>')


def section_layers(m):
    record = m.get('layers')
    if not record: return f'<div class="card">{T("لم تُقرأ الطبقات في هذا الفحص.", "The layers were not read in this check.", "p")}</div>'
    high = [f for f in record['findings'] if f['severity'] == 'high']
    red = (f'<div class="card alert" role="alert"><h4>{T("حدود حرجة مكسورة", "Broken critical boundaries")}</h4><ul>'
           + ''.join(f'<li>🔴 {T(esc(f["ar"]), esc(f["en"]))}</li>' for f in high[:10]) + '</ul></div>') if high else ''
    files, gaps = len(record['map']), len(record['gaps'])
    head = (f'<div class="card"><p>{T("نوع المشروع المرجعي", "Reference type")}: <b>{esc(record.get("type") or "—")}</b> · '
            f'{num(files - gaps, "files placed in a layer")} / {num(files, "files read")} {T("ملفًا في طبقته", "files in their layer")} · '
            f'{num(len(record["endpoints"]), "endpoints")} {T("نقطة طلب", "endpoints")} · {num(len(record["tables"]), "tables")} {T("جدولًا", "tables")}</p></div>')
    return red + head + ''.join(_boundary(name, [f for f in record['findings'] if f['boundary'] == name]) for name in BOUNDARIES)
