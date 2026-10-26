"""REPORT.html's structure section: today's parts, how they differ from the target, the import cycles."""
from ...core.language import plain
from ...analysis.presentation import model as M
from ...core.language.markup import both as T, esc
from .arch import architecture_map
from .charts import HEAT, HEAT_BINS, layer_diagram, treemap
from .html import lit, num, unavailable
from .words import RELATION


def section_structure(m):
    target = m['target']
    components = target.get('current_components') or target.get('components') or []
    if not components:
        return unavailable('structure')
    counts = M.component_problems(m)
    root = target.get('root') or ''
    items = [_part_item(c, counts, root) for c in components]
    legend_steps = ''.join(
        f'<span class="heat-key"><i style="background:{HEAT[i]}"></i>{T(label_ar, label_en)}</span>'
        for i, (label_ar, label_en) in enumerate(heat_labels()))
    legend_steps = f'<span class="heat-key"><i style="background:var(--tile-empty)"></i>{T("بلا مشاكل", "no problems")}</span>' + legend_steps
    out = [f'<div class="grid map-grid"><div class="card"><h4>{T("البنية اليوم", "The structure today")}</h4>'
           f'<p class="muted small">{T("كل مربع جزء من المشروع؛ مساحته بعدد ملفاته، ولونه بكثافة المشاكل فيه (مشاكل لكل عشرة ملفات). مرّر المؤشر لترى التفاصيل.", "Each box is a part of the project; its size is its number of files, its colour the density of problems in it (problems per ten files). Hover for details.")}</p>'
           f'{treemap(items, True)}{treemap(items, False)}<div class="heat-legend">{legend_steps}</div></div>']
    out.append(_target_card(target.get('target_components') or []))
    out.append('</div>')
    out.append(architecture_map(m))
    out.append(f'<h3>{T("الفرق بين اليوم والمستهدف", "The difference between today and the target")}</h3><div class="card"><ul class="diff">{"".join(differences(m, items))}</ul></div>')
    out.append(cycles(m))
    out.append(_parts_table(items))
    return ''.join(out)


def _part_item(c, counts, root):
    """One part of today as the treemap and the table take it: its name (and without the project's root), files and
    problems."""
    files, found = counts.get(c.get('id'), (0, 0))
    name = c.get('name') or c.get('id') or ''
    short = name[len(root):] if root and name.startswith(root) and len(name) > len(root) else name
    return {'name': name, 'short': short or name, 'files': files, 'problems': found, **M.density_counts(files, found), 'relation': c.get('relation'), 'target': c.get('target_component')}


def _target_card(tcomps):
    """The target's layers beside today's parts; "not available" without a target."""
    if not tcomps: return f'<div class="card"><h4>{T("البنية المستهدفة", "The target structure")}</h4>{unavailable("target")}</div>'
    return (f'<div class="card"><h4>{T("البنية المستهدفة", "The target structure")}</h4>'
            f'<p class="muted small">{T("الطبقات من الأعلى (ما يراه المستخدم) إلى الأسفل (الأساس). كل طبقة تعتمد فقط على ما تحتها.", "Layers from the top (what users see) to the bottom (the foundation). Each layer depends only on those below it.")}</p>'
            f'{layer_diagram(tcomps, True)}{layer_diagram(tcomps, False)}'
            f'<p class="small"><a href="#target" data-go="target">{T("البنية المستهدفة كاملة وتقدّم كل جزء ←", "The full target structure and each part’s progress →")}</a></p></div>')


def _parts_table(items):
    """Every part of today as a table, the most problems first."""
    return (f'<details class="card"><summary>{T("كل الأجزاء كجدول", "All parts as a table")}</summary><table class="tbl"><thead><tr>'
            f'<th>{T("الجزء", "Part")}</th><th>{T("الملفات", "Files")}</th><th>{T("المشاكل", "Problems")}</th><th>{T("مشاكل لكل عشرة ملفات", "Problems per ten files")}</th></tr></thead><tbody>'
            + ''.join(f'<tr><td>{lit(i["name"])}</td><td>{num(i["files"], "files in this part")}</td><td>{num(i["problems"], "problems in this part")}</td>'
                      f'<td>{num(i["per_ten"], "problems per ten files in this part")}</td></tr>'
                      for i in sorted(items, key=lambda i: -i['problems'])) + '</tbody></table></details>')


def heat_labels():
    edges = HEAT_BINS
    words = (('قليلة', 'few'), ('متوسطة', 'some'), ('كثيرة', 'many'), ('كثيفة', 'dense'), ('كثيفة جدًا', 'very dense'))
    out = []
    for i, (ar, en) in enumerate(words):
        if i == 0: rng = f'< {edges[0]}'
        elif i == len(edges): rng = f'≥ {edges[-1]}'
        else: rng = f'{edges[i - 1]}–{edges[i]}'
        meaning = 'problems per ten files'
        out.append((f'{esc(ar)} ({num(rng, meaning)} لكل عشرة ملفات)', f'{esc(en)} ({num(rng, meaning)} per ten files)'))
    return out


def differences(m, items):
    target = m['target']
    counts = M.structure_counts(target)
    lines = _fates(counts)
    tcomps = target.get('target_components') or []
    if tcomps:
        layers = counts['layers']
        lines.append(T(f'البنية المستهدفة فيها {num(M.collection_count(tcomps), "parts in the target structure")} جزءًا في {num(layers, "layers in the target structure")} طبقة، لكل منها مسؤولية واحدة.',
                       f'The target structure has {num(M.collection_count(tcomps), "parts in the target structure")} parts in {num(layers, "layers in the target structure")} layers, each with one responsibility.', 'li'))
    forbidden = target.get('forbidden_edges')
    if isinstance(forbidden, int) and forbidden:
        lines.append(T(f'{num(forbidden, "imports that go the wrong way between layers")} استيرادًا يسير في الاتجاه الخطأ بين الطبقات، ويجب قلبه.',
                       f'{num(forbidden, "imports that go the wrong way between layers")} imports go the wrong way between layers and have to be turned around.', 'li'))
    moves = counts['moves']
    if moves:
        lines.append(T(f'{num(moves, "files that move to another place")} ملفًا ينتقل إلى مكان آخر.', f'{num(moves, "files that move to another place")} files move to another place.', 'li'))
    lines += _worst_parts(items) + _missing(target)
    return lines or [T('لا توجد بيانات كافية للمقارنة.', 'Not enough data to compare.', 'li')]


def _fates(counts):
    """What becomes of today's parts in the target, the most common fate first; nothing when none has one."""
    relations = counts['relations']
    if not relations: return []
    ar = '، '.join(f'{num(n, "parts with this fate")} {esc(RELATION.get(k, (k, k))[0])}' for k, n in sorted(relations.items(), key=lambda kv: -kv[1]))
    en = ', '.join(f'{num(n, "parts with this fate")} {esc(RELATION.get(k, (k, k))[1])}' for k, n in sorted(relations.items(), key=lambda kv: -kv[1]))
    total = counts['current']
    return [T(f'من {num(total, "parts of the project today")} جزءًا اليوم: {ar}.', f'Of the {num(total, "parts of the project today")} parts today: {en}.', 'li')]


def _worst_parts(items):
    """The (up to) three parts with the most problems, and what each becomes."""
    lines = []
    for item in sorted(items, key=lambda i: -i['problems'])[:3]:
        if not item['problems']: break
        rel = RELATION.get(item['relation'], ('', ''))
        dest = (T(f' ← يصبح {lit(item["target"])}', f' → becomes {lit(item["target"])}') if item['target'] else '')
        lines.append(f'<li>{lit(item["name"])} ' + T(f'— المشاكل: {num(item["problems"], "problems in this part")} في ملفات عددها {num(item["files"], "files in this part")}؛ {esc(rel[0])}.',
                                                     f'{num(item["problems"], "problems in this part")} problems in {num(item["files"], "files in this part")} files; it {esc(rel[1])}.') + dest + '</li>')
    return lines


def _missing(target):
    """The basic infrastructure the target adds because the project lacks it; nothing when it lacks none."""
    missing = [i for i in target.get('infrastructure') or [] if not i.get('present')]
    if not missing: return []
    names = ' '.join(lit(i.get('area', '')) for i in missing)
    count = num(M.collection_count(missing), 'pieces of infrastructure the target adds')
    words = T(f'ينقص المشروع {count} من أساسيات البنية التحتية:', f'The project lacks {count} pieces of basic infrastructure:')
    return [f'<li>{words} {names}</li>']


def cycles(m):
    rows = [r for r in m['rows'] if r['pattern'] == 'import_cycle']
    head = f'<h3>{T("ملفات متشابكة (دورات استيراد)", "Tangled files (import cycles)")}</h3>'
    if not rows:
        return head + f'<div class="card">{T("لا توجد ملفات يعتمد بعضها على بعض في حلقة.", "No files depend on each other in a loop.", "p")}</div>'
    items = ''.join(_cycle_item(r['paths']) for r in rows)
    return head + (f'<div class="card"><p>{T(esc(plain.problem("import_cycle", "ar")[1]), esc(plain.problem("import_cycle", "en")[1]))}</p>'
                   f'<ul class="cycles">{items}</ul></div>')


def _cycle_body(names):
    if len(names) == 2:
        return f'<span dir="ltr" class="pair">{lit(names[0])}<span class="arrow" aria-hidden="true">⇄</span>{lit(names[1])}</span>'
    return '<span class="ring">' + ''.join(lit(n) for n in names) + '</span>'


def _cycle_item(paths):
    """One import loop: its files, named from the folder they share."""
    folder = paths[0].rsplit('/', 1)[0] + '/' if len(paths) > 1 and '/' in paths[0] else ''
    shared = folder if folder and all(p.startswith(folder) for p in paths) else ''
    size = num(M.collection_count(paths), 'files in this loop')
    where = T(f'في {lit(shared)}', f'in {lit(shared)}') if shared else ''
    return (f'<li class="cycle"><div class="cycle-head"><span class="loop" aria-hidden="true">↻</span>'
            f'{T(f"حلقة ملفاتها: {size}", f"A loop of {size} files")} {where}</div>{_cycle_body([p[len(shared):] for p in paths])}</li>')
