"""REPORT.html's summary and its gaps and risks: the score, the areas, the top problems, what was not checked."""
from collections import Counter

from ...core.language import plain
from ...core.language.words import catalog
from ...analysis.presentation import model as M
from ...core.language.markup import both as T, esc
from ...analysis.presentation.model import AREAS, CRITICAL_CAP, HALF_POINT, SEVERITIES, SEVERITY_WEIGHT, ledger_of
from .cards import gap_block
from .charts import severity_bars
from .html import lit, num, priority_words, said, sev_chip, unavailable, w
from .words import AREA_WHAT, GAP_STATUS, GRADE_MEANS, HUNDRED, RELATION, SEVERITY_MEANS, W


# ---------------------------------------------------------------- sections

def _area_sentence(area, a, rows):
    """An area card's words; an area whose every problem was accepted as a risk weighs in the score with no open row."""
    if not a['measured']: return T('لم يكتمل الفحص الذي يقيس هذا المجال، فلا نعرف حالته.', 'The check that measures this area did not complete, so its state is unknown.')
    if not a['total']: return T('لم نجد مشاكل في هذا المجال.', 'No problems found in this area.')
    worst = next(sv for sv in SEVERITIES if a['counts'][sv])
    top = next(iter(Counter(r['pattern'] for r in rows if r['area'] == area).most_common(1)), (None,))[0]
    count = num(a['total'], f'problems in {area}')
    return T(f'عدد المشاكل: {count}<br>أخطرها: {esc(W[worst][0])}<br>' + (f'أكثرها: {esc(plain.problem(top, "ar")[0])}' if top else 'كلها مخاطر قبلتها'),
             f'Problems: {count}<br>Most serious: {esc(W[worst][1].lower())}<br>' + (f'Most common: {esc(plain.problem(top, "en")[0])}' if top else 'All are risks you accepted'))


def section_summary(m, name):
    s, rows = m['score'], m['rows']
    out = []
    if s['score'] is None:
        out.append(unavailable('score'))
    else:
        grade = s['grade']
        meaning = 'health score out of 100, computed from the problems found (see How we computed)'
        out.append(
            f'<div class="hero card"><div class="hero-score"><div class="big grade-{grade}">{num(s["score"], meaning, "n big-n")}'
            f'<small>{T("من " + HUNDRED, "out of " + HUNDRED, cls="of")}</small></div>'
            f'<div class="grade-word grade-{grade}">{w(grade)}</div></div>'
            f'<div class="hero-text"><h3>{T("صحة المشروع", "Project health")}</h3>'
            f'<p class="lead">{T(*map(esc, GRADE_MEANS[grade]))}</p>'
            f'{meter(s["score"])}'
            + (f'<p class="note">{T("وُجدت مشكلة حرجة مؤكدة، فلا تتجاوز الدرجة " + num(CRITICAL_CAP, "the cap when a confirmed critical problem exists") + " مهما كانت بقية المجالات.", "A confirmed critical problem exists, so the score stays at " + num(CRITICAL_CAP, "the cap when a confirmed critical problem exists") + " or below whatever the other areas show.")}</p>' if s['capped'] else '')
            + '</div></div>')
    if isinstance(m['plan'].get('tasks'), list) or ledger_of(m):
        out.append(gap_block(m, m.get('cards') or []))
    cards = []
    for area in AREAS:
        a = s['areas'][area]
        key = 'structure_area' if area == 'structure' else area
        light_word = _light_word(a)
        sentence = _area_sentence(area, a, rows)
        area_score = (T(f'{num(a["score"], f"{area} score out of 100")} من {HUNDRED}', f'{num(a["score"], f"{area} score out of 100")} out of {HUNDRED}')
                      if a['score'] is not None else '')
        cards.append(f'<div class="card area light-{a["light"]}" data-area="{area}"><div class="area-head">'
                     f'<span class="light" aria-hidden="true"></span><h4>{w(key)}</h4></div>'
                     f'<div class="area-score">{area_score}</div>'
                     f'<p class="light-word">{T(*map(esc, light_word))}</p><p class="small">{sentence}</p>'
                     f'<p class="muted small">{T(*map(esc, AREA_WHAT[area]))}</p></div>')
    out.append(f'<h3>{T("المجالات الخمسة", "The five areas")}</h3><div class="grid areas">' + ''.join(cards) + '</div>')
    out.append(top_problems(rows))
    counts = M.group_counts(rows)
    auto, decide = counts['automatic'], counts['decision']
    out.append(f'<div class="grid two"><div class="card stat good-bg"><div class="stat-n">{num(auto, "problems EAOS can fix automatically")}</div>'
               f'<p>{T("مشاكل يستطيع EAOS إصلاحها آليًا، ويتحقق بعد كل إصلاح أن البرنامج لم ينكسر.", "problems EAOS can fix automatically, checking after each fix that the program still works.")}</p></div>'
               f'<div class="card stat warn-bg"><div class="stat-n">{num(decide, "problems that need the owner or a person to decide")}</div>'
               f'<p>{T("مشاكل تحتاج قرارك أو نظرة شخص قبل أي تغيير.", "problems need your decision, or a person to look, before any change.")}</p></div></div>')
    out.append(not_checked(m))
    out.append(how_computed(m))
    return ''.join(out)


def _light_word(a):
    """An area card's word for its light; never "good" over ground this version does not check."""
    if a['partial'] and a['light'] == 'green': return W['partial']
    return {'green': ('جيد', 'Good'), 'amber': ('يحتاج انتباهًا', 'Needs attention'),
            'red': ('يحتاج إصلاحًا', 'Needs fixing'), 'grey': ('لم يُقَس', 'Not measured')}[a['light']]


def meter(value):
    bands = ((0, 40, 'critical'), (40, 60, 'weak'), (60, 75, 'fair'), (75, 90, 'good'), (90, 100, 'excellent'))
    cells = ''.join(f'<span class="band band-{g}" style="flex:{hi - lo}">{w(g)}</span>' for lo, hi, g in bands)
    return (f'<div class="meter" aria-hidden="true"><div class="bands">{cells}</div>'
            f'<div class="marker" style="inset-inline-start:{value}%"></div></div>')


def top_problems(rows):
    groups = {}
    for r in rows: groups.setdefault(r['pattern'], []).append(r)
    def weight(group): return M.group_counts(group)['weight']
    ordered = sorted(groups, key=lambda p: (min(SEVERITIES.index(r['severity']) for r in groups[p]), -weight(groups[p]),
                                            plain.ORDER.index(p) if p in plain.ORDER else len(plain.ORDER)))
    if not ordered:
        return f'<h3>{T("أهم المشاكل", "Main problems")}</h3><div class="card">{T("لم نجد مشاكل تحتاج إصلاحًا.", "No problems that need fixing were found.", "p")}</div>'
    items = []
    for index, pattern in enumerate(ordered[:5], 1):
        group = groups[pattern]
        worst = next(s for s in SEVERITIES if any(r['severity'] == s for r in group))
        ready = M.group_counts(group)['automatic']
        (tar, why_ar), (ten, why_en) = plain.problem(pattern, 'ar'), plain.problem(pattern, 'en')
        count, fixed = num(M.collection_count(group), 'cards of this kind'), num(ready, 'cases EAOS fixes automatically')
        counts = T(f'عدد الحالات: {count} · يصلحها EAOS آليًا: {fixed}', f'Cases: {count} · EAOS fixes automatically: {fixed}')
        items.append(f'<li class="card problem"><span class="rank" data-meaning="position in the list of main problems">{index}</span>'
                     f'<div><h4>{T(esc(tar), esc(ten))} {sev_chip(worst)}</h4><p>{T(esc(why_ar), esc(why_en))}</p>'
                     f'<p class="muted small">{counts}</p></div></li>')
    return f'<h3>{T("أهم خمس مشاكل", "The five main problems")}</h3><ol class="problems">' + ''.join(items) + '</ol>'


def not_checked(m):
    statuses, coverage, manifest = m['statuses'], m['coverage'], m['manifest']
    items = []
    for stage, status in statuses.items():
        if status in ('failed', 'not_reached'):
            items.append(T(f'لم يكتمل: {esc(plain.stage(stage, "ar"))}. ما كان سيجده قد يكون ناقصًا.',
                           f'Did not complete: {esc(plain.stage(stage, "en"))}. What it would have found may be missing.', 'li'))
    from ..documents.run import absences
    covered = ('semantic',) if coverage else ()
    for row in absences(manifest):
        if row['status'] in ('unavailable', 'skipped') and row['stage'] not in covered:
            items.append(T(f'لم يُشغَّل: {esc(plain.stage(row["stage"], "ar"))}. {esc(row["reason"]["ar"])}',
                           f'Not run: {esc(plain.stage(row["stage"], "en"))}. {esc(row["reason"]["en"])}', 'li'))
    items += _coverage_limits(coverage)
    items += [T(f'لا يفحصه هذا الإصدار: {esc(row["one"][0])}. {esc(row["why"][0])}', f'Not checked by this version: {esc(row["one"][1])}. {esc(row["why"][1])}', 'li')
              for row in (catalog()['unchecked'][kind] for kind in m['score'].get('unchecked') or [])]
    items.append(T('الأداء الحقيقي تحت الضغط لم يُقَس بتشغيل؛ هو تقدير من شكل الكود.',
                   'Real performance under load was not measured by running it; it is an estimate from the shape of the code.', 'li'))
    return (f'<h3>{T("ما لم نفحصه", "What we did not check")}</h3><div class="card honest">'
            f'<p>{T("الأمانة مهمة: هذه حدود هذا الفحص. قد توجد مشاكل هنا لم نرها.", "Honesty matters: these are the limits of this check. There may be problems here we did not see.")}</p>'
            f'<ul>{"".join(items)}</ul></div>')


def _coverage_limits(coverage):
    """What the coverage record says was not done: the tests, watching the program run, files not read, a semantic
    review; nothing without a coverage record."""
    if not coverage: return []
    items = []
    if not coverage.get('executed_verification'):
        items.append(T('لم تُشغَّل اختبارات المشروع، فلا نعرف أي أجزاء تغطيها الاختبارات فعلًا.',
                       "The project's tests were not run, so we do not know which parts they actually cover.", 'li'))
    if not coverage.get('runtime_confirmation'):
        items.append(T('لم نراقب البرنامج وهو يعمل: كل ما هنا من قراءة الكود، لا من تشغيله.',
                       'We did not watch the program running: everything here comes from reading the code, not running it.', 'li'))
    unparsed = M.unparsed_count(coverage)
    if unparsed > 0:
        items.append(T(f'ملفات لم نستطع قراءتها: {num(unparsed, "source files that could not be read")}.',
                       f'{num(unparsed, "source files that could not be read")} source files could not be read.', 'li'))
    if not coverage.get('semantic_review'):
        items.append(T('لم يراجع مساعد ذكي معنى الكود؛ الأحكام هنا من قواعد آلية.',
                       'No AI assistant reviewed what the code means; the findings come from mechanical rules.', 'li'))
    return items


def how_computed(m):
    s = m['score']
    weights = ' · '.join(f'{esc(W[sv][0])} {num(SEVERITY_WEIGHT[sv], f"weight of a {sv} problem")}' for sv in SEVERITIES)
    weights_en = ' · '.join(f'{esc(W[sv][1])} {num(SEVERITY_WEIGHT[sv], f"weight of a {sv} problem")}' for sv in SEVERITIES)
    half = num(HALF_POINT, 'weighted points per 100 files at which an area scores 50')
    rows = ''.join(f'<tr><td>{w("structure_area" if a == "structure" else a)}</td>'
                   f'<td>{num(s["areas"][a]["total"], "problems in this area")}</td>'
                   f'<td>{num(s["areas"][a]["points"], "weighted points of this area")}</td>'
                   f'<td>{num(s["areas"][a]["density"], "weighted points per 100 files")}</td>'
                   f'<td>{num(s["areas"][a]["score"], "area score out of 100") if s["areas"][a]["score"] is not None else w("na")}</td></tr>'
                   for a in AREAS)
    ar = (f'<ol><li>كل مشكلة لها وزن حسب خطورتها: {weights}.</li>'
          f'<li>الوزن يُضرب في درجة التأكد: المؤكدة كاملة، والمرجّحة {num("70%", "share of the weight a likely problem counts")} من وزنها.</li>'
          f'<li>نجمع أوزان كل مجال ونقسمها على حجم المشروع: لكل {num(100, "files per size unit")} ملف (المشروع الأصغر يُحسب {num(100, "minimum size in files")} ملف).</li>'
          f'<li>درجة المجال تبدأ من {num(100, "full score")} وتنخفض كلما زادت أوزانه: إذا بلغت أوزانه {half} لكل {num(100, "files per size unit")} ملف صارت درجته {num(50, "half the full score")}، '
          f'وإذا بلغت ثلاثة أضعاف ذلك صارت {num(25, "a quarter of the full score")}. '
          f'<span class="formula" dir="ltr" data-literal="formula">score = 100 × {HALF_POINT} ÷ ({HALF_POINT} + points per 100 files)</span></li>'
          f'<li>درجة المشروع = متوسط درجات المجالات التي قيست. ووجود مشكلة حرجة مؤكدة يجعلها {num(CRITICAL_CAP, "the cap")} أو أقل.</li></ol>')
    en = (f'<ol><li>Each problem weighs by its severity: {weights_en}.</li>'
          f'<li>The weight is multiplied by how sure we are: confirmed counts fully, likely counts {num("70%", "share of the weight a likely problem counts")}.</li>'
          f'<li>We add the weights of each area and divide by the project size, per {num(100, "files per size unit")} files (a smaller project counts as {num(100, "minimum size in files")}).</li>'
          f'<li>An area starts at {num(100, "full score")} and falls as its weights grow: at {half} weighted points per {num(100, "files per size unit")} files it scores {num(50, "half the full score")}, '
          f'at three times that {num(25, "a quarter of the full score")}. '
          f'<span class="formula" dir="ltr" data-literal="formula">score = 100 × {HALF_POINT} ÷ ({HALF_POINT} + points per 100 files)</span></li>'
          f'<li>Project score = the mean of the measured areas. A confirmed critical problem keeps it at {num(CRITICAL_CAP, "the cap")} or below.</li></ol>')
    priority = T(f'<b>الأولوية</b>: كل مشكلة مرتبة بين غيرها حسب ثلاثة أشياء: كم تلمس من البرنامج، وكم نحن متأكدون منها، وكم يكلف إصلاحها. '
                 f'نعرض ترتيبها بالكلمات (مثل «ضمن أعلى {num("10%", "example rank")}») لا بالرقم الخام.',
                 f'<b>Priority</b>: each problem is ranked among the others by three things: how much of the program it touches, how sure we are, '
                 f'and how costly it is to fix. We show its rank in words (such as "in the top {num("10%", "example rank")}"), not the raw number.', 'p')
    size = num(s['size'], 'project size in files used by the formula')
    basis = T(f'كل رقم هنا محسوب من بيانات هذا التقرير فقط، بهذه القاعدة (حجم المشروع المستخدم: {size} ملف):',
              f"Every number here comes only from this report's data, by this rule (project size used: {size} files):")
    table = (f'<table class="tbl"><thead><tr><th>{T("المجال", "Area")}</th><th>{T("عدد المشاكل", "Problems")}</th>'
             f'<th>{T("الأوزان", "Weighted points")}</th><th>{T("الأوزان لكل " + HUNDRED + " ملف", "Points per " + HUNDRED + " files")}</th>'
             f'<th>{T("الدرجة من " + HUNDRED, "Score out of " + HUNDRED)}</th></tr></thead><tbody>{rows}</tbody></table>')
    return (f'<h3 id="how">{T("كيف حسبنا", "How we computed")}</h3><div class="card how">'
            f'<p>{basis}</p>'
            f'{T(ar, en, "div")}<details><summary>{T("الحساب على هذا المشروع", "The calculation on this project")}</summary>{table}</details>{priority}</div>')


def legend():
    items = ''.join(f'<div class="legend-item" data-severity="{sv}">{sev_chip(sv)}<span>{T(*map(esc, SEVERITY_MEANS[sv]))}</span></div>'
                    for sv in SEVERITIES)
    return f'<div class="card legend" data-legend="severity"><h4>{T("ماذا تعني الخطورة؟", "What severity means")}</h4>{items}</div>'


def section_gaps(m):
    rows, s = m['rows'], m['score']
    out = [legend(), _severity_card(s), _filters()]
    if not rows:
        out.append(f'<div class="card">{T("لم نجد مشاكل تحتاج إصلاحًا.", "No problems that need fixing were found.", "p")}</div>')
    for area in AREAS:
        mine = [r for r in rows if r['area'] == area]
        if mine: out.append(_area_gaps(area, mine))
    out.append(component_gaps(m))
    return ''.join(out)


def _severity_card(s):
    """The problems of each area by severity: as bars in both reading directions, and as a table."""
    counts_table = ''.join(f'<tr><td>{w("structure_area" if a == "structure" else a)}</td>'
                           + ''.join(f'<td>{num(s["areas"][a]["counts"][sv], f"{sv} problems in this area")}</td>' for sv in SEVERITIES)
                           + f'<td>{num(s["areas"][a]["total"], "all problems in this area")}</td></tr>' for a in AREAS)
    chips = ''.join(f'<span class="key">{sev_chip(sv)}</span>' for sv in SEVERITIES)
    return (f'<div class="card"><h4>{T("عدد المشاكل في كل مجال، حسب الخطورة", "Problems in each area, by severity")}</h4>'
            f'<div class="keys">{chips}</div>{severity_bars(s["areas"], True)}{severity_bars(s["areas"], False)}'
            f'<details><summary>{T("عرض كجدول", "Show as a table")}</summary><table class="tbl"><thead><tr><th>{T("المجال", "Area")}</th>'
            + ''.join(f'<th>{w(sv)}</th>' for sv in SEVERITIES) + f'<th>{T("المجموع", "Total")}</th></tr></thead><tbody>{counts_table}</tbody></table></details></div>')


def _filters():
    """The gaps' search and filters: by severity, by area, the automatic fixes only."""
    return (f'<div class="card filters" role="search"><input type="search" id="q" data-ph-ar="ابحث باسم ملف أو كلمة…" data-ph-en="Search a file name or a word…" placeholder="ابحث باسم ملف أو كلمة…">'
            f'<select id="fsev"><option value="">{esc("كل درجات الخطورة")}</option>' + ''.join(f'<option value="{sv}">{esc(W[sv][0])}</option>' for sv in SEVERITIES) + '</select>'
            f'<select id="farea"><option value="">{esc("كل المجالات")}</option>' + ''.join(f'<option value="{a}">{esc(W["structure_area" if a == "structure" else a][0])}</option>' for a in AREAS) + '</select>'
            f'<label class="check"><input type="checkbox" id="fauto"> {T("ما يُصلح آليًا فقط", "Automatic fixes only")}</label>'
            f'<span class="muted" id="shown" aria-live="polite"></span></div>')


def _area_gaps(area, mine):
    """One area's problems `mine`, a group per kind of problem, the most serious kind first."""
    groups = {}
    for r in mine: groups.setdefault(r['pattern'], []).append(r)
    blocks = [_gap_group(pattern, groups[pattern])
              for pattern in sorted(groups, key=lambda p: (min(SEVERITIES.index(r['severity']) for r in groups[p]), -len(groups[p])))]
    count = num(M.collection_count(mine), 'problems in this area')
    return (f'<h3 class="area-title" data-area-block="{area}">{w("structure_area" if area == "structure" else area)} '
            f'<span class="muted">{T(f"— عدد المشاكل: {count}", f"— problems: {count}")}</span></h3>' + ''.join(blocks))


def _gap_group(pattern, group):
    """One kind of problem: what it is, why it matters, how many cases EAOS fixes alone, and each case."""
    group = sorted(group, key=lambda r: (SEVERITIES.index(r['severity']), r['top'], r['id']))
    (tar, why_ar), (ten, why_en) = plain.problem(pattern, 'ar'), plain.problem(pattern, 'en')
    ready = M.group_counts(group)['automatic']
    count, fixed = num(M.collection_count(group), 'problems of this kind'), num(ready, 'cases fixed automatically')
    meta = T(f'الحالات: {count} · آليًا: {fixed}', f'Cases: {count} · automatic: {fixed}')
    head = (f'<summary><span class="g-title">{T(esc(tar), esc(ten))}</span>'
            f'<span class="g-meta">{meta}</span></summary>')
    items = ''.join(gap_row(r) for r in group)
    return f'<details class="group" open>{head}<p class="why">{T(esc(why_ar), esc(why_en))}</p><div class="rows">{items}</div></details>'


def gap_row(r):
    where = ' '.join(lit(p) for p in r['paths'][:3])
    more = M.remaining(r['paths'], 3)
    if more > 0: where += ' ' + T(f'و{num(more, "more files")} ملفات أخرى', f'and {num(more, "more files")} more files')
    auto = (T('يصلحه EAOS آليًا', 'EAOS fixes it automatically', cls='yes') if r['auto']
            else T('يحتاج قرار شخص', 'Needs a person to decide', cls='no'))
    effort = (T(f'الجهد: {esc(W[r["effort"]][0])}', f'Effort: {esc(W[r["effort"]][1])}') if r['effort'] in W else '')
    conf = W.get(r['confidence'], (r['confidence'], r['confidence']))
    search = ' '.join([r['id'], r['title'], *r['paths'], r['pattern']]).lower()
    return (f'<article class="row" data-sev="{r["severity"]}" data-area="{r["area"]}" data-auto="{int(r["auto"])}" '
            f'data-priority="{esc(r["priority"])}" data-search="{esc(search)}">'
            f'<div class="row-head">{sev_chip(r["severity"])}<span class="conf">{T(esc(conf[0]), esc(conf[1]))}</span>'
            f'<span class="prio">{priority_words(r["top"], r["severity"])}</span>{lit(r["id"])}</div>'
            f'<div class="where">{T("أين:", "Where:", cls="lbl")} {where}</div>'
            f'<div class="nowto"><div><b>{T("الآن", "Now")}</b> {said(r["before"] or r["title"])}</div>'
            f'<div><b>{T("المطلوب", "Should be")}</b> {said(r["after"] or r["change"]) or T("لم يُحدَّد بعد؛ يقرره شخص.", "Not stated yet; a person decides.")}</div></div>'
            f'<div class="row-foot">{auto}<span class="muted">{effort}</span></div></article>')


def component_gaps(m):
    target = m['target']
    matrix = target.get('gap_matrix') or (m['gap_matrix'] or {}).get('rows') or []
    if not matrix:
        return f'<h3>{T("الفجوات حسب أجزاء البرنامج", "Gaps by part of the program")}</h3>{unavailable("components")}'
    counts = M.component_problems(m)
    rows = [_component_row(g, counts) for g in sorted(matrix, key=lambda g: -counts.get(g.get('component'), (0, 0))[1])]
    return (f'<h3>{T("الفجوات حسب أجزاء البرنامج", "Gaps by part of the program")}</h3><div class="card scroll">'
            f'<p class="muted">{T("لكل جزء من البرنامج: ماذا سيحدث له، وأين يذهب في البنية المستهدفة، وهل تغطيه الخطة.", "For each part of the program: what happens to it, where it goes in the target structure, and whether the plan covers it.")}</p>'
            f'<table class="tbl"><thead><tr><th>{T("الجزء اليوم", "Part today")}</th><th>{T("ماذا يحدث له", "What happens")}</th>'
            f'<th>{T("مكانه المستهدف", "Target place")}</th><th>{T("الخطة", "Plan")}</th><th>{T("المشاكل فيه", "Problems in it")}</th>'
            f'<th>{T("ملفات تنتقل", "Files to move")}</th><th>{T("استيرادات مخالفة", "Wrong-way imports")}</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def _component_row(g, counts):
    """One part's row of the gap matrix: what happens to it, its target place, the plan, its problems and moves."""
    current = g.get('current') or {}
    relation = RELATION.get(current.get('relation'), (esc(current.get('relation', '')),) * 2)
    status = GAP_STATUS.get(g.get('gap'), (g.get('gap') or '', g.get('gap') or ''))
    problems_here = counts.get(g.get('component'), (0, 0))[1]
    return (f'<tr><td>{lit(g.get("current_origin") or g.get("component") or "")}</td><td>{T(*map(esc, relation))}</td>'
            f'<td>{lit(g.get("target_component") or "—")}</td><td>{T(*map(esc, status))}</td>'
            f'<td>{num(problems_here, "problems found in this part")}</td>'
            f'<td>{num(g.get("files_to_move") or 0, "files that move to another place")}</td>'
            f'<td>{num(g.get("forbidden_imports") or 0, "imports that break the target layering")}</td></tr>')
