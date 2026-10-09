"""The pipeline sheet of the report for people (REPORT.html, human/index.html, and its printed PDF): the flowchart of each
product pipeline, the stage table and the gap, drawn from the Studio's pipeline section (eaos/studio/pipeline.py), so the
report and System -> Pipeline show the same stages, places and numbers (docs/STUDIO.md D2, D9). Nothing here reads the
records or computes a number: the section is given, once per language, by the caller.
"""
import html

from ..studio import model as M

NODE_W, NODE_H, STEP_X, STEP_Y, PAD = 150, 46, 200, 66, 16
MOST_DRAWN = 60      # a longer pipeline is a table here; the Studio draws it with pan and zoom
MOST_ROWS = 60
OP = {'retain': ('يبقى', 'keep'), 'refactor': ('يُعدَّل', 'refactor'), 'rebuild': ('يُعاد بناؤه', 'rebuild'), 'merge': ('يُدمج', 'merge'),
      'delete': ('يُحذف', 'delete'), 'new': ('جديد', 'new')}
KIND = {'stage': ('مرحلة', 'stage'), 'router': ('موجّه', 'router'), 'fork': ('تفرّع', 'fork'), 'join': ('تجميع', 'join'),
        'ai': ('ذكاء اصطناعي', 'AI node'), 'source': ('مصدر', 'source'), 'sink': ('مَصبّ', 'sink'), 'external': ('خارجي', 'external')}


def esc(value):
    return html.escape(str(value), quote=True)


def both(ar, en, tag='span', cls=''):
    """The same words in both languages; the page shows one of them (human_report's convention)."""
    extra = f' {cls}' if cls else ''
    return f'<{tag} class="l-ar{extra}" lang="ar">{ar}</{tag}><{tag} class="l-en{extra}" lang="en">{en}</{tag}>'


def code(text):
    return f'<bdi dir="ltr" class="ps-id">{esc(text)}</bdi>'


def where(site):
    site = site or {}
    return f"{site['path']}:{site['line']}" if site.get('path') and site.get('line') else site.get('path') or ''


def fit(text, room):
    text = str(text)
    return text if len(text) <= room else '…' + text[-(room - 1):]


def number(value, meaning):
    cls = "" if meaning in ("pipeline verdict", "pipeline gap explanation") else "n"
    return f'<span class="{cls}" data-meaning="{esc(meaning)}">{esc(value)}</span>'


def flowchart(section, pipeline):
    """One pipeline left to right, every stage where EAOS placed it (layer, order): routers as diamonds, edges with the
    data's shape, failure routes dashed to their ends; drawn left to right in both languages."""
    stages = [s for s in section['stages'] if s['pipeline'] == pipeline['id']]
    at = {s['id']: (PAD + s['layer'] * STEP_X, PAD + s['order'] * STEP_Y) for s in stages}
    width = PAD * 2 + NODE_W + max([s['layer'] for s in stages] + [0]) * STEP_X
    height = PAD * 2 + NODE_H + max([s['order'] for s in stages] + [0]) * STEP_Y
    parts = []
    for e in section['edges']:
        if e['pipeline'] != pipeline['id'] or e['from'] not in at or e['to'] not in at: continue
        (ax, ay), (bx, by) = at[e['from']], at[e['to']]
        x1, y1, x2, y2 = ax + NODE_W, ay + NODE_H / 2, bx, by + NODE_H / 2
        if x2 > x1:
            m = (x1 + x2) / 2
            d = f'M{x1},{y1} C{m},{y1} {m},{y2} {x2},{y2}'
        else:
            bow = max(ay, by) + NODE_H + 18
            d = f'M{ax + NODE_W / 2},{ay + NODE_H} C{ax + NODE_W / 2},{bow} {bx + NODE_W / 2},{bow} {bx + NODE_W / 2},{by + NODE_H}'
        shape = (e.get('data') or {}).get('shape') or ''
        parts.append(f'<path d="{d}" class="ps-e ps-{esc(e["kind"])}" marker-end="url(#ps-arrow)"><title>{esc(shape)}</title></path>')
    for s in stages:
        x, y = at[s['id']]
        if s['kind'] == 'router':
            box = f'<polygon points="{x + NODE_W / 2},{y - 5} {x + NODE_W + 4},{y + NODE_H / 2} {x + NODE_W / 2},{y + NODE_H + 5} {x - 4},{y + NODE_H / 2}" class="ps-box ps-router"/>'
            anchor, tx = 'middle', x + NODE_W / 2
        else:
            box = f'<rect x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" rx="9" class="ps-box ps-{esc(s["kind"])}"/>'
            anchor, tx = 'start', x + 10
        sub = ' · '.join(s.get('tools') or []) or where(s.get('entry')).rsplit('/', 1)[-1]
        parts.append(f'<g>{box}<text x="{tx}" y="{y + 20}" text-anchor="{anchor}" class="ps-t">{esc(fit(s["label"], 17))}</text>'
                     f'<text x="{tx}" y="{y + 36}" text-anchor="{anchor}" class="ps-s">{esc(fit(sub, 24))}</text>'
                     f'<title>{esc(s["label"])} · {esc(where(s.get("entry")))}</title></g>')
    return (f'<svg class="ps-svg" data-literal="pipeline stage labels and evidence" viewBox="0 0 {width} {height}" role="img" direction="ltr" '
            f'aria-label="{esc(pipeline["title"])}: {M.pipeline_counts(section)['drawn'][pipeline['id']]} stages">'
            '<defs><marker id="ps-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto">'
            '<path d="M0,0 L8,4 L0,8 z" class="ps-arrow"/></marker></defs>' + ''.join(parts) + '</svg>')


def stage_table(section, pipelines):
    ids = {p['id'] for p in pipelines}
    titles = {p['id']: p['title'] for p in pipelines}
    rows = sorted((s for s in section['stages'] if s['pipeline'] in ids), key=lambda s: (s['pipeline'] != pipelines[0]['id'], s['pipeline'], s['layer'], s['order']))
    names = lambda ports: ', '.join(code(p['name']) for p in ports[:3]) + (' …' if len(ports) > 3 else '')
    body = ''.join(
        f'<tr><td>{code(titles[s["pipeline"]])}</td><td>{code(s["label"])}</td><td>{both(*KIND.get(s["kind"], (s["kind"], s["kind"])))}</td>'
        f'<td>{names(s["inputs"])}</td><td>{names(s["outputs"])}</td><td>{", ".join(code(t) for t in s["tools"][:4])}</td>'
        f'<td>{code(where(s["entry"]))}</td></tr>' for s in rows[:MOST_ROWS])
    more_count = M.pipeline_counts(section, pipelines, MOST_ROWS)['more']
    more = (f'<p class="muted small">{both(f"و{number(more_count, "more pipeline stages in the Studio")} مرحلة أخرى في الاستوديو.", f"and {number(more_count, "more pipeline stages in the Studio")} more stages in the Studio.")}</p>'
            if more_count else '')
    head = ''.join(f'<th>{both(ar, en)}</th>' for ar, en in (('خط المعالجة', 'Pipeline'), ('المرحلة', 'Stage'), ('النوع', 'Kind'),
                                                             ('تأخذ', 'Takes'), ('تعطي', 'Gives'), ('الأدوات', 'Tools'), ('الدليل', 'Evidence')))
    return f'<div class="ps-scroll"><table class="ps-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>{more}'


def gap_table(section):
    gap = section['views']['gap']
    if not gap:
        return both('لا قاعدة مكسورة: خط المعالجة يطابق مثاله.', 'No rule is broken: the pipeline matches its ideal.', 'p', 'muted small')
    rules = {r['id']: r for r in section['rules']}
    head = ''.join(f'<th>{both(ar, en)}</th>' for ar, en in (('#', '#'), ('القاعدة', 'Rule'), ('العملية', 'Operation'), ('ما يكسرها', 'What breaks it'),
                                                             ('الدليل', 'Evidence'), ('البطاقة', 'Card')))
    body = ''.join(
        f'<tr><td>{number(n, "pipeline gap order")}</td><td>{code(g["rule"])} <span dir="ltr" lang="en">{esc((rules.get(g["rule"]) or {}).get("title", ""))}</span></td>'
        f'<td>{both(*OP.get(g["operation"], (g["operation"], g["operation"])))}</td><td dir="ltr" lang="en">{number(g["detail"], "pipeline gap explanation")}</td>'
        f'<td>{code(where(g["evidence"]))}</td><td>{code(g["card"]) if g.get("card") else "—"}</td></tr>'
        for n, g in enumerate(gap[:MOST_ROWS], 1))
    return f'<div class="ps-scroll"><table class="ps-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def sheet(sections):
    """<section id="pipeline-sheet"> for {'ar': section, 'en': section}, or '' when the project holds no pipeline."""
    ar, en = sections.get('ar'), sections.get('en')
    if not ar or not en or not en.get('pipelines'): return ''
    product = [p for p in en['pipelines'] if p['role'] == 'product'] or en['pipelines']
    top = [p for p in product if not p.get('parent')] or product
    counts = M.pipeline_counts(en)
    def figure(p):
        n = counts['stages'][p['id']]
        label = number(n, 'stages in this pipeline')
        body = (flowchart(en, p) if n <= MOST_DRAWN else
                both('أطول من أن يُرسم في صفحة واحدة: افتحه في الاستوديو (النظام ← خط المعالجة).',
                     'Too long to draw on one page: open it in the Studio (System → Pipeline).', 'p', 'muted small'))
        return f'<figure class="ps-fig"><figcaption>{code(p["title"])} · {both(f"{label} مرحلة", f"{label} stages")}</figcaption>{body}</figure>'
    drawn = ''.join(figure(p) for p in top)
    subs = [p for p in product if p.get('parent')]
    sub_line = (f'<p class="small">{both("خطوط معالجة داخل مراحلها:", "Pipelines inside its stages:")} '
                + ', '.join(f'{code(p["title"])} ({number(counts['stages'][p['id']], "stages in this pipeline")})' for p in subs) + '</p>') if subs else ''
    confidence = counts['confidence']
    facts = (f'<p class="muted small">{both("الثقة", "Confidence")} {number(confidence, "pipeline confidence percent")}% · '
             + ' · '.join(f'{both(a, b)} {number((en["counts"].get(key) or {}).get("value", "—"), f"pipeline {key}")}'
                          for key, a, b in (('stages', 'مراحل', 'stages'), ('edges', 'روابط', 'links'), ('unresolved', 'لم يُتتبع', 'not followed'),
                                            ('gaps', 'فجوات', 'gaps')) if key in en['counts']) + '</p>')
    return (f'<section id="pipeline-sheet" class="card ps" data-part="pipeline-sheet"><h3>{both("خط المعالجة", "The pipeline")}</h3>'
            f'<p>{both(number(ar["verdict"], "pipeline verdict"), number(en["verdict"], "pipeline verdict"))}</p>{facts}'
            f'<p class="muted small">{both("كل مرحلة في مكانها الذي حسبه EAOS، من اليسار إلى اليمين: المعيّنات موجّهات، والخطوط المتقطعة تحكّم أو خطأ. التفاصيل الكاملة والعروض الثلاثة (الحالي والمثالي والفجوة) في الاستوديو.", "Every stage where EAOS placed it, left to right: diamonds are routers, dashed lines are control or failure. The full detail and the three views (current, ideal, gap) are in the Studio.")}</p>'
            f'{drawn}{sub_line}<h4>{both("المراحل", "The stages")}</h4>{stage_table(en, product)}'
            f'<h4>{both("الفجوة بين الحالي والمثالي", "The gap between the current pipeline and its ideal")}</h4>{gap_table(en)}</section>')


CSS = r"""
.ps-fig{margin:12px 0;overflow-x:auto}.ps-fig figcaption{font-size:13px;color:var(--muted);margin-bottom:6px}
.ps-svg{display:block;width:100%;min-width:640px;height:auto}.ps-id{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.92em}
.ps-box{fill:var(--surface);stroke:var(--ink-2);stroke-width:1}.ps-router{fill:var(--surface-2)}.ps-ai{stroke:var(--accent);stroke-width:1.5}
.ps-t{font:500 12px ui-monospace,Menlo,Consolas,monospace;fill:var(--ink)}.ps-s{font-size:10px;fill:var(--muted)}
.ps-e{fill:none;stroke:var(--muted);stroke-width:1.1;opacity:.7}.ps-control{stroke-dasharray:6 4}.ps-error{stroke:var(--bad);stroke-dasharray:4 3}
.ps-hidden{stroke-dasharray:1 5;stroke-linecap:round;stroke-width:2}.ps-arrow{fill:var(--muted)}
.ps-scroll{overflow-x:auto}.ps-table{border-collapse:collapse;width:100%;font-size:13px}.ps-table th,.ps-table td{text-align:start;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.ps-table th{color:var(--ink-2);font-weight:600}
@media print{.ps{break-before:page}.ps-svg{min-width:0}}
"""
