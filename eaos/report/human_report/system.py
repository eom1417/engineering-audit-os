"""REPORT.html's system map (its data and layout: eaos/analysis/system_map.py): pages, APIs, handlers, tables."""
from ...analysis import model as M
from .. import pipeline_sheet
from ...core.markup import both as T, esc
from ...analysis.system_drawing import COLUMNS, WIDTH, svg_edge, svg_heads, svg_nodes
from .html import lit, num, unavailable


# ---------------------------------------------------------------- the system map (the data and layout: eaos/analysis/system_map.py)

SM_HEADS = (('الصفحات', 'Pages'), ('نقاط API', 'APIs'), ('ما يجيبها في الخادم', 'Server handlers'),
            ('الأجزاء التي يستخدمها', 'Parts it uses'), ('الجداول والخدمات', 'Tables and services'))


def system_svg(sm, lay, rtl):
    """Five columns, right to left in Arabic: pages, APIs grouped by resource, the server files that answer them, the
    parts those use, and the tables and services reached. Every link is drawn faint; the JS lights one chain."""
    place = lay['place']
    label = 'خريطة النظام: الصفحات ونقاط API والخادم والبيانات' if rtl else 'The system map: pages, APIs, server and data'
    edges = ''.join(svg_edge(e, place, rtl) for e in sm['edges'] if e['from'] in place and e['to'] in place)
    return (f'<svg viewBox="0 0 {WIDTH} {lay["height"]}" direction="ltr" role="img" class="chart smap {"l-ar" if rtl else "l-en"}" aria-label="{esc(label)}">'
            + ''.join(svg_heads(lay, rtl)) + f'<g class="sm-edges">{edges}</g>' + ''.join(svg_nodes(sm, place, rtl)) + '</svg>')


def api_table(sm):
    """Every API, collapsed: its method and path, who calls it, the server file that answers it, what it reaches."""
    pages = {p['id']: p for p in sm['pages']}
    short = {h['path']: h['short'] for h in sm['handlers']}
    def some(items, meaning, limit=5):
        shown = ' '.join(lit(i) for i in items[:limit])
        more = M.remaining(items, limit)
        return shown + (' ' + T(f'و{num(more, meaning)} غيرها', f'and {num(more, meaning)} more') if more > 0 else '') if items else '—'
    rows = []
    for a in sm['apis']:
        reached = [pages[i]['route'] for i in sm['related'].get(a['id'], []) if i in pages]
        callers = sorted(a['callers'])
        if a['handlers']:
            handler = ' '.join(f'<span title="{esc(h["path"])}">{lit(short.get(h["path"], h["path"]))}</span>' + (f' {lit(h["function"])}' if h['function'] else '')
                               for h in a['handlers'][:3])
            if not a['exact']: handler += ' ' + T('(من اسم الملف فقط)', '(from the file name only)', cls='muted')
        else:
            handler = T('غير معروف: لا مسار ولا ملف في الخادم يطابقه', 'unknown: no server route or file matches it', cls='muted')
        data = a['tables'] + a['services']
        rows.append(f'<tr data-search="{esc((a["key"] + " " + " ".join(callers) + " " + " ".join(a["features"])).lower())}"><td>{lit(a["method"])}</td><td>{lit(a["path"])}</td>'
                    f'<td>{some(sorted(set(reached)), "more pages")}<div class="small muted">{some(callers, "more files", 3)}</div></td>'
                    f'<td>{handler}</td><td>{some(data, "more tables and services")}</td><td>{some(a["features"], "more features", 3)}</td></tr>')
    return (f'<details class="card" data-part="system-apis"><summary>{T("كل نقاط API كجدول", "Every API as a table")} '
            f'<span class="g-meta">{T(f"النقاط: {num(M.collection_count(sm["apis"]), "APIs in the table")}", f"{num(M.collection_count(sm["apis"]), "APIs in the table")} APIs")}</span></summary>'
            f'<div class="scroll"><table class="tbl sm-table"><thead><tr><th>{T("الطريقة", "Method")}</th><th>{T("المسار", "Path")}</th>'
            f'<th>{T("من يستدعيها (صفحات، ثم ملفات)", "Called from (pages, then files)")}</th><th>{T("ما يجيبها في الخادم", "Server handler")}</th>'
            f'<th>{T("الجداول والخدمات", "Tables and services")}</th><th>{T("الميزة", "Feature")}</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></details>')


def pipeline_part(m):
    """The pipeline sheet (eaos/report/pipeline_sheet.py) under the system map, when the project holds a pipeline."""
    return pipeline_sheet.sheet(m['pipeline']) if m.get('pipeline') else ''


def section_system(m):
    """The whole system in one drawing, with a search, a feature filter, what a click reaches, and every API as a table."""
    sm, lay = m.get('system'), m.get('system_layout')
    if not sm or not lay: return _system_missing(m)
    from ...analysis.arch_map import json_script
    metrics = M.system_counts(sm)
    info = {x['id']: x for group in ('pages', 'callers', 'apis', 'handlers', 'modules', 'data') for x in sm[group]}
    info = {k: {kk: vv for kk, vv in v.items() if kk not in ('reach',)} for k, v in info.items()}
    data = {'rel': sm['related'], 'info': info, 'features': {f['name']: f['pages'] for f in sm['features']},
            'feature_counts': sm['feature_counts']}
    return (f'<div class="card graph-wrap sm-wrap" data-part="system-map"><h3 class="sm-title">{T("كل الروابط: من الصفحة إلى البيانات", "Every link: from the page to the data")}</h3>'
            f'<p class="muted small">{T("من اليمين إلى اليسار: الصفحة، ونقطة API التي تستدعيها، والملف في الخادم الذي يجيبها، والأجزاء التي يستخدمها، والجداول والخدمات التي يصل إليها. مرّر المؤشر على أي مربع لتضيء سلسلته كلها، أو اضغط عليه لتثبيتها وترى تفاصيله تحت الرسم.", "From left to right: the page, the API it calls, the server file that answers it, the parts that file uses, and the tables and services it reaches. Hover any box to light its whole chain, or click it to keep it and see its details under the drawing.")}</p>'
            f'<p class="small">{_system_summary(metrics)}</p>' + ''.join(f'<p class="muted small">{x}</p>' for x in _system_notes(sm, metrics))
            + _system_controls(sm) + _system_legend()
            + f'<div class="graph-scroll sm-scroll">{_system_heads(metrics)}'
            f'{system_svg(sm, lay, True)}{system_svg(sm, lay, False)}</div>'
            f'<div id="smd" class="node-detail card sm-detail">{T("اضغط على صفحة أو نقطة API أو ملف أو جدول لترى ما يصل إليه ومن يصل إليه.", "Click a page, an API, a file or a table to see what it reaches and what reaches it.", "p", "muted small")}</div>'
            f'</div>{api_table(sm)}' + json_script('eaos-system', data))


def _system_missing(m):
    """Why there is no system map: a project with no pages and no API, or a map that could not be built."""
    if (m.get('coverage') or {}).get('source_files') and not any(e.get('section') == 'system map' for e in m.get('map_errors') or []):
            return (f'<div class="card" data-part="system-map"><h3>{T("كل الروابط: من الصفحة إلى البيانات", "Every link: from the page to the data")}</h3>'
                    + T('لم نجد في هذا المشروع صفحات ويب ولا نقاط API يستدعيها أحد: هو مكتبة أو أداة أوامر أو خدمة بلا واجهة. '
                        'أجزاؤه والعلاقات بينها، وملفاته ودواله، مرسومة في «خريطة البنية».',
                        'This project has no web pages and no API that anything calls: it is a library, a command-line tool or a '
                        'service without a front end. Its parts and the links between them, its files and functions, are drawn in '
                        'the "Structure map".', 'p') + '</div>')
    return unavailable('system map')


def _system_summary(metrics):
    answered, tables = metrics['answered'], metrics['tables']
    n = lambda v, meaning: num(v, meaning)
    return T(f'الصفحات: {n(metrics["pages"], "pages")} · نقاط API: {n(metrics["apis"], "APIs")} · وجدنا في الخادم ما يجيب {n(answered, "APIs with a server handler found")} منها · '
                f'ملفات الخادم: {n(metrics["handlers"], "server files that answer requests")} · الجداول: {n(tables, "tables")} · الخدمات: {n(metrics["services"], "services and storage")}',
                f'{n(metrics["pages"], "pages")} pages · {n(metrics["apis"], "APIs")} APIs · a server handler found for {n(answered, "APIs with a server handler found")} of them · '
                f'{n(metrics["handlers"], "server files that answer requests")} server files · {n(tables, "tables")} tables · {n(metrics["services"], "services and storage")} services')


SM_LEFT_OUT = {'pages': ('صفحة', 'pages'), 'callers': ('ملفًا مشتركًا', 'shared files'), 'apis': ('نقطة API', 'APIs'),
               'handlers': ('ملف خادم', 'server files'), 'modules': ('جزءًا', 'parts'), 'data': ('جدولًا أو خدمة', 'tables or services')}


def _system_capped(sm, n):
    """What the drawing left out to stay readable; None when nothing was."""
    capped = {k: v for k, v in (sm.get('capped') or {}).items() if v}
    if not capped: return None
    words = SM_LEFT_OUT
    ar = '، '.join(f'{n(v, "items left out of the drawing")} {words[k][0]}' for k, v in capped.items())
    en = ', '.join(f'{n(v, "items left out of the drawing")} {words[k][1]}' for k, v in capped.items())
    return T(f'الرسم محدود الحجم ليبقى مقروءًا؛ لم يُرسم: {ar}.', f'The drawing is capped to stay readable; left out: {en}.')


def _system_notes(sm, metrics):
    n = lambda v, meaning: num(v, meaning)
    notes = []
    if sm['unknown']:
        notes.append(T(f'لم نجد في الخادم ما يجيب {n(sm["unknown"], "APIs whose handler is unknown")} من نقاط API: قد يأتي جوابها من خادم آخر أو من مسار يُبنى وقت التشغيل. تظهر منقّطة.',
                       f'For {n(sm["unknown"], "APIs whose handler is unknown")} APIs no server code was found that answers them: the answer may come from another server, or from a route built at run time. They are drawn dotted.'))
    if sm['guessed']:
        notes.append(T(f'{n(sm["guessed"], "APIs matched by file name only")} منها رُبطت بملف من اسمه فقط؛ تحقق منها.', f'{n(sm["guessed"], "APIs matched by file name only")} of them are matched to a file by its name only; check them.'))
    untraced = metrics['untraced']
    if untraced:
        notes.append(T(f'{n(untraced, "pages whose component file was not found")} صفحة لم نجد ملف مكوّنها، فلم نتتبع ما تستدعيه (تظهر باهتة).',
                       f'{n(untraced, "pages whose component file was not found")} pages: their component file was not found, so what they call is not traced (drawn faded).'))
    capped = _system_capped(sm, n)
    if capped: notes.append(capped)
    notes.append(T('الجداول: المعرّفة في ملفات البيانات التي يستخدمها كود الخادم؛ لا نفرّق هنا بين القراءة والكتابة.',
                   'Tables: those defined in the data files the server code uses; reading and writing are not told apart here.'))
    return notes


def _system_controls(sm):
    features = ''.join(f'<option value="{esc(f["name"])}" data-literal="1">{esc(f["name"])}</option>' for f in sm['features'])
    controls = ('<div class="filters sm-tools" role="search"><input type="search" id="smq" data-ph-ar="ابحث عن صفحة أو API أو ملف أو جدول…" '
                'data-ph-en="Search a page, an API, a file or a table…" placeholder="ابحث عن صفحة أو API أو ملف أو جدول…">'
                + (f'<select id="smf"><option value="" data-ar="كل الميزات" data-en="All features">كل الميزات</option>{features}</select>' if features else '')
                + f'<button type="button" class="btn ghost" id="smclear">{T("إظهار الكل", "Show all")}</button>'
                f'<span class="muted" id="smshown" aria-live="polite"></span></div>')
    return controls


def _system_legend():
    sample = lambda cls: f'<svg width="40" height="12" aria-hidden="true" class="key-line"><path d="M2,6 H38" class="sm-edge {cls}"/></svg>'
    legend = (f'<div class="heat-legend">'
              f'<span class="heat-key">{sample("k-call")}{T("صفحة أو ملف يستدعي API", "a page or a file calls an API")}</span>'
              f'<span class="heat-key">{sample("k-uses")}{T("صفحة تستخدم كودًا مشتركًا", "a page uses shared code")}</span>'
              f'<span class="heat-key">{sample("k-answer")}{T("ملف في الخادم يجيبها", "a server file answers it")}</span>'
              f'<span class="heat-key">{sample("k-use")}{T("يستخدم جزءًا آخر", "uses another part")}</span>'
              f'<span class="heat-key">{sample("k-data")}{T("يصل إلى جدول أو خدمة", "reaches a table or a service")}</span>'
              f'<span class="heat-key"><i class="key-box sm-unknown"></i>{T("لا نعرف من يجيبها", "no known handler")}</span></div>')
    return legend


def _system_heads(metrics):
    """The columns' titles over the drawing, spaced as the drawing spaces its columns."""
    spans, edge = [], 0                          # the columns and the gaps between them, as the drawing has them
    for x, width in COLUMNS:
        spans += [x - edge, width]; edge = x + width
    spans.append(WIDTH - edge)
    fr = ' '.join(f'{max(s, 0)}fr' for s in spans)
    counts = metrics['columns']
    meanings = ('pages and shared files drawn', 'APIs drawn', 'server files drawn', 'parts drawn', 'tables and services drawn')
    heads = ''.join(f'<div></div><div>{T(esc(ar), esc(en))} {num(counts[c], meanings[c])}</div>'
                    for c, (ar, en) in enumerate(SM_HEADS)) + '<div></div>'
    return f'<div class="sm-heads" style="grid-template-columns:{fr}">{heads}</div>'
