"""REPORT.html's architecture map (its data and layout: eaos/analysis/arch_map.py): the graph, its legend and metrics."""
import math

from ...analysis import model as M
from ...core.markup import both as T, esc, fit, svg_text
from .html import lit, num, unavailable


# ---------------------------------------------------------------- architecture maps (the data and layout: eaos/analysis/arch_map.py)

INSTABILITY = {'stable': ('مستقر: كثيرون يعتمدون عليه وهو يعتمد على القليل', 'stable: many rely on it, it relies on little'),
               'balanced': ('متوازن: يعتمد ويُعتمد عليه بقدر متقارب', 'balanced: it relies on others about as much as they rely on it'),
               'unstable': ('متغيّر: يعتمد على كثير ولا يعتمد عليه إلا القليل', 'changeable: it relies on much, little relies on it'),
               'alone': ('منفصل: لا يستورد شيئًا ولا يستورده أحد', 'on its own: it imports nothing and nothing imports it')}
COHESION = {'strong': ('قوي', 'strong'), 'medium': ('متوسط', 'medium'), 'weak': ('ضعيف', 'weak')}


def files_word(n):
    return 'file' if n == 1 else 'files'


def arrow_defs(suffix):
    head = '<path d="M0,0 L8,4 L0,8 z" class="arrow-head{}"/>'
    return ''.join(f'<marker id="{name}-{suffix}" viewBox="0 0 8 8" refX="7" refY="4" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10" orient="auto-start-reverse">'
                   f'{head.format(cls)}</marker>' for name, cls in (('arr', ''), ('arrc', ' cyc')))


def graph_svg(cmap, rtl):
    """Today's parts as boxes, left to right from what uses to what is used (mirrored in Arabic), and their imports."""
    from ...analysis.arch_map import NODE_W as BW, NODE_H as BH
    width, height = cmap['width'], cmap['height'] + 60
    X = (lambda x: width - x - BW) if rtl else (lambda x: x)
    boxes = {n['id']: (X(n['x']), n['y']) for n in cmap['nodes']}
    names = {n['id']: n['short'] for n in cmap['nodes']}
    suffix = 'ar' if rtl else 'en'
    label = 'أجزاء المشروع اليوم وما يستورده كل جزء من غيره' if rtl else 'The parts of the project today and what each imports from the others'
    parts = [f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" style="width:{width}px" direction="ltr" role="img" '
             f'class="chart cgraph hl-graph {"l-ar" if rtl else "l-en"}" aria-label="{esc(label)}"><defs>{arrow_defs(suffix)}</defs><g class="edges">']
    for e in sorted(cmap['edges'], key=lambda e: e['cycle']):
        (ax, ay), (bx, by) = boxes[e['from']], boxes[e['to']]
        if not e['back']:
            sx, ex = (ax, bx + BW) if rtl else (ax + BW, bx)
            bend = max(30, abs(ex - sx) / 2) * (-1 if rtl else 1)
            d = f'M{sx:.1f},{ay + BH / 2:.1f} C{sx + bend:.1f},{ay + BH / 2:.1f} {ex - bend:.1f},{by + BH / 2:.1f} {ex:.1f},{by + BH / 2:.1f}'
        else:           # set aside to break a loop, or inside one layer: it goes back under the boxes
            low = max(ay, by) + BH + 24 + min(abs(ax - bx) / 12, 30)
            d = f'M{ax + BW / 2:.1f},{ay + BH:.1f} C{ax + BW / 2:.1f},{low:.1f} {bx + BW / 2:.1f},{low:.1f} {bx + BW / 2:.1f},{by + BH + 2:.1f}'
        cls = 'edge' + (' cyc' if e['cycle'] else '') + (' wrong' if e['wrong'] else '')
        count = e['n']
        words = f'{names[e["from"]]} → {names[e["to"]]}: ' + (f'الاستيرادات {count}' if rtl else f'{count} imports')
        parts.append(f'<path d="{d}" class="{cls}" style="stroke-width:{1 + 1.3 * math.log2(count):.1f}" '
                     f'marker-end="url(#{"arrc" if e["cycle"] else "arr"}-{suffix})" data-from="{esc(e["from"])}" data-to="{esc(e["to"])}" '
                     f'data-meaning="{count} imports from one part to the other"><title>{esc(words)}</title></path>')
    parts.append('</g>')
    for n in cmap['nodes']:
        x, y = boxes[n['id']]
        side, edge = ('right', x + BW - 10) if rtl else ('left', x + 10)
        files, uses, used = n['files'], n['uses'], n['used_by']
        line = f'ملفات {files} · يستخدم {uses} · يستخدمه {used}' if rtl else f'{files} {files_word(files)} · uses {uses} · used by {used}'
        meaning = f'{files} files; it uses {uses} other parts; {used} parts use it'
        parts.append(f'<g class="cg-node{" cyc" if n["cycle"] else ""}" data-node="{esc(n["id"])}" tabindex="0" data-meaning="{esc(meaning)}">'
                     f'<title>{esc(n["name"])}</title><rect x="{x:.1f}" y="{y:.1f}" width="{BW}" height="{BH}" rx="8"/>'
                     + svg_text(edge, y + 20, fit(n['short'], 24), 'cg-name', side, attrs=' data-literal="1"')
                     + svg_text(edge, y + 38, line, 'cg-sub', side, rtl) + '</g>')
    return ''.join(parts) + '</svg>'


def cohesion_words(n):
    if n['cohesion'] is None: return T('لا يستورد شيئًا', 'it imports nothing')
    share = num(f'{n["cohesion"]}%', 'share of its imports that stay inside it')
    ar, en = COHESION[n['cohesion_word']]
    return T(f'{share} من استيراداته تبقى داخله ({esc(ar)})', f'{share} of its imports stay inside it ({esc(en)})')


def link_list(pairs, names):
    shown = sorted(pairs, key=lambda pk: -pk[1])[:8]
    def one(p, k):
        count = num(k, 'imports along this link')
        return f'<span class="link">{lit(names[p])} {T(f"(الاستيرادات: {count})", f"({count} imports)", cls="muted")}</span>'
    return ' '.join(one(p, k) for p, k in shown) or T('لا شيء', 'nothing')


def node_detail(n, cmap):
    """What a click on a part shows: its numbers in words, and the parts on each side of it."""
    names = {x['id']: x['short'] for x in cmap['nodes']}
    users = link_list([(e['from'], e['n']) for e in cmap['edges'] if e['to'] == n['id']], names)
    uses = link_list([(e['to'], e['n']) for e in cmap['edges'] if e['from'] == n['id']], names)
    files = num(n['files'], 'files in this part')
    come, go = num(n['ca'], 'imports coming into this part'), num(n['ce'], 'imports going out of this part')
    ar_i, en_i = INSTABILITY[n['instability']]
    loop = (T('هذا الجزء في حلقة: ما يستورده يمكن أن يصل إليه من جديد.', 'This part is in a loop: what it imports can reach back to it.', 'p', 'bad-ink')
            if n['cycle'] else '')
    return (f'<div class="node-detail card" data-for="{esc(n["id"])}" hidden><h4>{lit(n["name"])}</h4>'
            f'<p class="small">{T(f"الملفات: {files} · استيرادات داخلة: {come} · خارجة: {go}", f"{files} files · {come} imports come in · {go} go out")}</p>'
            f'<p class="small">{T("الترابط الداخلي:", "Cohesion:", cls="lbl")} {cohesion_words(n)} · {T("الثبات:", "Stability:", cls="lbl")} {T(esc(ar_i), esc(en_i))}</p>'
            f'{loop}<p class="small">{T("يستخدمه:", "Used by:", cls="lbl")} {users}</p><p class="small">{T("يستخدم:", "Uses:", cls="lbl")} {uses}</p></div>')


def graph_legend():
    sample = lambda cls, dash='': (f'<svg width="46" height="12" aria-hidden="true" class="key-line"><path d="M2,6 H44" class="edge {cls}"{dash}/></svg>')
    return (f'<div class="heat-legend">'
            f'<span class="heat-key">{sample("")}{T("أ ← ب: أ يستورد من ب؛ الخط الأسمك استيرادات أكثر", "A → B: A imports from B; a thicker line is more imports")}</span>'
            f'<span class="heat-key">{sample("cyc")}{T("في حلقة: كل طرف يصل إلى الآخر", "in a loop: each end reaches the other")}</span>'
            f'<span class="heat-key">{sample("wrong")}{T("عكس ترتيب الطبقات المستهدف", "against the target layering")}</span>'
            f'<span class="heat-key"><i class="key-box cyc"></i>{T("جزء داخل حلقة", "a part inside a loop")}</span></div>')


def metrics_table(cmap):
    rows = []
    for n in sorted(cmap['nodes'], key=lambda n: -(n['ca'] + n['ce'])):
        ar_i, en_i = INSTABILITY[n['instability']]
        loop = T('نعم', 'yes', cls='bad-ink') if n['cycle'] else T('لا', 'no')
        rows.append(f'<tr><td>{lit(n["short"])}</td><td>{num(n["files"], "files in this part")}</td><td>{num(n["used_by"], "parts that use it")}</td>'
                    f'<td>{num(n["uses"], "parts it uses")}</td><td>{num(n["ca"], "imports coming in")} / {num(n["ce"], "imports going out")}</td>'
                    f'<td>{cohesion_words(n)}</td><td>{T(esc(ar_i), esc(en_i))}</td><td>{loop}</td></tr>')
    return (f'<details><summary>{T("مقاييس كل جزء كجدول", "Every part’s measures as a table")}</summary><div class="scroll"><table class="tbl"><thead><tr>'
            f'<th>{T("الجزء", "Part")}</th><th>{T("الملفات", "Files")}</th><th>{T("أجزاء تستخدمه", "Parts that use it")}</th><th>{T("أجزاء يستخدمها", "Parts it uses")}</th>'
            f'<th>{T("استيرادات داخلة / خارجة", "Imports in / out")}</th><th>{T("الترابط الداخلي", "Cohesion")}</th><th>{T("الثبات", "Stability")}</th>'
            f'<th>{T("في حلقة", "In a loop")}</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></details>'
            f'<p class="muted small">{T("الترابط الداخلي: نسبة استيرادات الجزء التي تبقى داخله؛ كلما زادت كان الجزء متماسكًا. الثبات: جزء يعتمد عليه كثيرون ولا يعتمد على غيره مستقر، وتغييره يمس الكثير؛ وجزء يعتمد على كثير متغيّر.", "Cohesion: the share of a part’s imports that stay inside it; the higher, the more the part holds together. Stability: a part many rely on and that relies on little is stable, and changing it touches much; one that relies on much is changeable.")}</p>')


def architecture_map(m):
    """The parts of today as a flowchart of their imports, with a drill-down to files and functions."""
    from ...analysis import arch_map
    cmap = m.get('cmap')
    head = f'<h3 id="arch-map">{T("كيف تعتمد الأجزاء بعضها على بعض", "How the parts depend on each other")}</h3>'
    if not cmap:
        return head + unavailable('architecture map')
    counts = M.architecture_counts(cmap)
    loops, wrong = counts['loops'], counts['wrong']
    parts, links = num(M.collection_count(cmap['nodes']), 'parts drawn'), num(M.collection_count(cmap['edges']), 'links between parts')
    n_loops, n_wrong = num(loops, 'links inside a loop'), num(wrong, 'links against the target layering')
    summary = T(f'الأجزاء: {parts} · الروابط بينها: {links} · روابط داخل حلقات: {n_loops} · روابط عكس الطبقات المستهدفة: {n_wrong}',
                f'{parts} parts · {links} links between them · {n_loops} links inside loops · {n_wrong} links against the target layering')
    capped = (T(f'رُسمت أكبر الأجزاء فقط؛ لم يُرسم {num(cmap["capped"], "parts left out of the drawing")} جزءًا صغيرًا.',
                f'Only the largest parts are drawn; {num(cmap["capped"], "parts left out of the drawing")} small parts are left out.', 'p', 'muted small')
              if cmap['capped'] else '')
    controls = (f'<div class="graph-tools"><label class="check"><input type="checkbox" class="only-loops"> {T("الحلقات فقط", "Loops only")}</label>'
                f'<button type="button" class="btn ghost fit-btn">{T("ملاءمة الشاشة / الحجم الحقيقي", "Fit to screen / actual size")}</button></div>')
    details = ''.join(node_detail(n, cmap) for n in cmap['nodes'])
    out = [head, f'<div class="card graph-wrap" data-part="arch-map"><p class="muted small">{T("كل مربع جزء من المشروع اليوم (مجلد). السهم من الجزء الذي يستورد إلى الجزء الذي يُستورد منه، وسمكه بعدد الاستيرادات. الأجزاء التي تستخدم غيرها على اليمين، والأساس الذي يستخدمه الجميع على اليسار. مرّر المؤشر على جزء لترى روابطه، أو اضغط عليه لتثبيتها وترى مقاييسه.", "Each box is a part of the project today (a folder). An arrow goes from the part that imports to the part it imports from; its thickness is the number of imports. Parts that use others are on the left, the foundation everything uses on the right. Hover a part to see its links, or click it to keep them and see its measures.")}</p>'
           f'<p class="small">{summary}</p>{capped}{graph_legend()}{controls}<div class="graph-scroll">{graph_svg(cmap, True)}{graph_svg(cmap, False)}</div>'
           f'{details}{metrics_table(cmap)}</div>']
    drill = m.get('drill')
    if drill:
        cap = drill['capped']
        notes = []
        if cap['files']: notes.append(T(f'في الأجزاء الكبيرة عُرض أول {num(arch_map.MAX_FILES, "files shown per part at most")} ملف فقط.', f'In large parts only the first {num(arch_map.MAX_FILES, "files shown per part at most")} files are listed.'))
        if cap['calls']: notes.append(T(f'عُرضت أكثر الاستدعاءات تكرارًا فقط، وتُرك {num(cap["calls"], "calls between functions left out")} استدعاءً.', f'Only the most frequent calls are shown; {num(cap["calls"], "calls between functions left out")} are left out.'))
        first = max(range(len(cmap['nodes'])), key=lambda i: cmap['nodes'][i]['ca'], default=0)
        options = ''.join(f'<option value="{i}" data-literal="1"{" selected" if i == first else ""}>{esc(c["name"])}</option>' for i, c in enumerate(drill['comps']))
        out.append(f'<div class="card drill" data-part="arch-drill"><h4>{T("داخل جزء: ملفاته ودواله", "Inside a part: its files and functions")}</h4>'
                   f'<p class="muted small">{T("اختر جزءًا: في الوسط ملفاته والخطوط الملونة بينها استيراداتها الداخلية؛ على جانب الأجزاء التي تستخدمه، وعلى الجانب الآخر الأجزاء التي يستخدمها. اضغط على ملف لترى دواله ومن يستدعي من.", "Choose a part: in the middle its files, the coloured arcs between them the imports inside it; on one side the parts that use it, on the other the parts it uses. Click a file to see its functions and who calls whom.")}</p>'
                   f'<p class="muted small">{" ".join(notes)}</p>'
                   f'<label class="pick">{T("الجزء:", "Part:")} <select id="dcomp" data-literal="1">{options}</select></label>'
                   f'<div id="dview" class="ego"></div><div id="dfile" class="ego"></div></div>'
                   + arch_map.json_script('eaos-drill', drill))
    flows = m.get('flows')
    head = f'<h3 id="flows">{T("الصفحات وما تستدعيه", "Pages and what they call")}</h3>'
    if not flows:
        out.append(head + unavailable('flows'))
    else:
        options = ''.join(f'<option value="{i}" data-literal="1">{esc(" ".join(x for x in (f["method"], f["route"] or "?") if x))} — {esc(f["handler"])}</option>'
                          for i, f in enumerate(flows))
        out.append(head + f'<div class="card" data-part="flows"><p class="muted small">{T("اختر صفحة أو نقطة دخول: يُرسم مسارها من الرابط إلى الدالة التي تستقبله، ثم كل دالة تستدعيها بالترتيب، مجمّعة حسب الملف. حيث لا يستطيع التتبع أن يكمل، يقول المربع المنقّط إن التتبع يتوقف هنا.", "Choose a page or an entry point: its path is drawn from the route to the function that receives it, then every function it calls in order, grouped by file. Where the trace cannot go on, a dotted box says it stops there.")}</p>'
                   f'<label class="pick">{T("الصفحة:", "Page:")} <select id="dflow" data-literal="1">{options}</select></label><div id="fview" class="flowchart"></div></div>'
                   + arch_map.json_script('eaos-flows', {'box': [arch_map.FLOW_W, arch_map.FLOW_H], 'flows': flows}))
    return ''.join(out)
