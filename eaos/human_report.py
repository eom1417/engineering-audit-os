"""human/index.html: the report for a person, in one self-contained page, Arabic and English.

The report's other files are written for AI agents and stay exactly as they are. This page reads the same
records (plan.json, dossier.json, debt-register.json, target-architecture.json, gap-matrix.json,
run-manifest.json) and shows four reports on one page: the project summary, the gaps and risks, the
structure map, and the plan with its progress. No external asset, no network: inline CSS, inline SVG,
a little inline JS. Every number on the page carries its meaning in words next to it.

What a problem is: one task card of plan.json. Its area and severity come from one table, PATTERNS below:
    pattern             area             default severity
    access_gap          security         critical
    upgrade_dependency  security         high
    broken_code         quality          high
    remove_dead         quality          low
    dead_code           quality          low
    canonicalize        quality          low
    duplicated_rule     quality          medium
    import_cycle        structure        medium
    mutable_state       structure        medium
    hidden_coupling     structure        low
    external_write      structure        medium
    policy_violation    structure        medium
    load_blocker        performance      medium
    redundant_work      performance      medium
    hotspot             maintainability  medium
    trace_gap           maintainability  low
    untested_path       maintainability  medium
    generic             by the debt register's category (CATEGORY_AREA), else maintainability; medium
The severity recorded for the card's claim in debt-register.json wins over the default: that register
already decides severity from its witnesses (eaos/debt_register.py). Confidence is the claim's own.

The health score, derived only from those cards:
    weight of a problem   = severity weight (critical 10, high 5, medium 2, low 1)
                            x confidence weight (CONFIRMED 1.0, LIKELY 0.7, HYPOTHESIS 0.4; eaos/ranking.py)
    density of an area    = sum of its weights per 100 source files (a project under 100 files counts as 100)
    area score            = 100 x 20 / (20 + density)   (20 weighted points per 100 files halve the score)
    health score          = the mean of the measured areas' scores; a confirmed critical problem caps it at 39
An area whose checking stage failed or was not reached is left out of the mean and shown as not measured.
Grades: 90 and above excellent, 75 good, 60 fair, 40 weak, below 40 critical. An area's light is green
from 80 with no high or critical problem, red below 50 or with a critical problem, amber otherwise.

A priority (eaos/ranking.py: reach x confidence x origin / cost) is shown as its rank among all cards,
in words: "very high, in the top 7%". The raw value is kept in a data attribute, not in the text.
"""
import html
import json
import math
import re
from html.parser import HTMLParser
from pathlib import Path

from . import plain
from .ranking import CONFIDENCE_WEIGHT

SECTIONS = ('summary', 'gaps', 'structure', 'plan')
HUNDRED = '<span data-meaning="the full score, and the file count a density is measured against">100</span>'
SEVERITIES = ('critical', 'high', 'medium', 'low')
SEVERITY_WEIGHT = {'critical': 10, 'high': 5, 'medium': 2, 'low': 1}
HALF_POINT = 20          # weighted points per 100 files at which an area scores 50
CRITICAL_CAP = 39
AREAS = ('security', 'structure', 'quality', 'performance', 'maintainability')
PATTERNS = {
    'access_gap': ('security', 'critical'), 'upgrade_dependency': ('security', 'high'),
    'broken_code': ('quality', 'high'), 'remove_dead': ('quality', 'low'), 'dead_code': ('quality', 'low'),
    'canonicalize': ('quality', 'low'), 'duplicated_rule': ('quality', 'medium'),
    'import_cycle': ('structure', 'medium'), 'mutable_state': ('structure', 'medium'),
    'hidden_coupling': ('structure', 'low'), 'external_write': ('structure', 'medium'),
    'policy_violation': ('structure', 'medium'),
    'load_blocker': ('performance', 'medium'), 'redundant_work': ('performance', 'medium'),
    'hotspot': ('maintainability', 'medium'), 'trace_gap': ('maintainability', 'low'),
    'untested_path': ('maintainability', 'medium'), 'generic': ('maintainability', 'medium'),
}
CATEGORY_AREA = {'security': 'security', 'supply_chain': 'security', 'architecture': 'structure', 'data': 'structure',
                 'dead_code': 'quality', 'reliability': 'maintainability', 'maintainability': 'maintainability'}
# The stage whose failure leaves an area unmeasured.
AREA_STAGE = {'security': 'facts', 'structure': 'facts', 'quality': 'facts', 'performance': 'load', 'maintainability': 'measure'}
GRADES = ((90, 'excellent'), (75, 'good'), (60, 'fair'), (40, 'weak'), (0, 'critical'))

W = {  # every fixed word of the page: (Arabic, English)
    'title': ('تقرير المشروع', 'Project report'),
    'summary': ('ملخص المشروع', 'Project summary'), 'gaps': ('الفجوات والمخاطر', 'Gaps and risks'),
    'structure': ('خريطة البنية', 'Structure map'), 'plan': ('الخطة والتقدم', 'Plan and progress'),
    'security': ('الأمان', 'Security'), 'quality': ('جودة الكود', 'Code quality'),
    'performance': ('الأداء تحت الضغط', 'Performance under load'),
    'maintainability': ('سهولة التطوير والاختبار', 'Ease of change and testing'),
    'critical': ('حرجة', 'Critical'), 'high': ('عالية', 'High'), 'medium': ('متوسطة', 'Medium'), 'low': ('منخفضة', 'Low'),
    'excellent': ('ممتاز', 'Excellent'), 'good': ('جيد', 'Good'), 'fair': ('مقبول', 'Fair'), 'weak': ('ضعيف', 'Weak'),
    'CONFIRMED': ('مؤكدة', 'Confirmed'), 'LIKELY': ('مرجّحة', 'Likely'), 'HYPOTHESIS': ('فرضية', 'Hypothesis'),
    'S': ('صغير', 'Small'), 'M': ('متوسط', 'Medium'), 'L': ('كبير', 'Large'),
    'na': ('غير متاح في هذا التقرير.', 'Not available in this report.'),
}
W['structure_area'] = ('البنية', 'Structure')
AREA_WHAT = {
    'security': ('هل يستطيع أحد الوصول إلى ما لا يحق له، أو استغلال ثغرة معروفة؟',
                 'Can anyone reach what they should not, or use a known security hole?'),
    'structure': ('هل أجزاء البرنامج منفصلة بوضوح، أم متشابكة يصعب تعديل أحدها وحده؟',
                  'Are the parts of the program clearly separate, or tangled so that none can change alone?'),
    'quality': ('كود ميت لا يستخدمه أحد، وكود منسوخ، ومراجع مكسورة.', 'Dead code nothing uses, copied code, and broken references.'),
    'performance': ('هل يبطئ البرنامج كلما زاد المستخدمون أو البيانات؟', 'Does the program slow down as users or data grow?'),
    'maintainability': ('هل يسهل فهم الكود وتغييره واختباره دون كسر شيء؟', 'Is the code easy to understand, change and test without breaking something?'),
}
SEVERITY_MEANS = {
    'critical': ('قد تُسرّب بيانات أو توقف البرنامج الآن؛ تُصلح قبل أي شيء آخر.',
                 'Can leak data or stop the program now; fix it before anything else.'),
    'high': ('ستسبب عطلًا أو ثغرة في الاستخدام العادي؛ تُصلح في الدفعة الأولى.',
             'Will cause a failure or a security hole in normal use; fix it in the first batch.'),
    'medium': ('تُبطئ التطوير أو تسبب أخطاء مع الوقت؛ تُصلح ضمن الخطة.',
               'Slows development or causes bugs over time; fix it as part of the plan.'),
    'low': ('تنظيف يسهّل القراءة والصيانة؛ لا يؤثر على المستخدم مباشرة.',
            'Clean-up that makes reading and changing easier; users do not feel it directly.'),
}
GRADE_MEANS = {
    'excellent': ('المشروع في حالة ممتازة: المشاكل قليلة وخفيفة.', 'The project is in excellent shape: few, light problems.'),
    'good': ('المشروع في حالة جيدة: توجد مشاكل، لكن معظمها غير عاجل.', 'The project is in good shape: there are problems, but most are not urgent.'),
    'fair': ('المشروع يعمل، لكن فيه مشاكل تستحق خطة إصلاح قبل أن تكبر.', 'The project works, but has problems that deserve a fix plan before they grow.'),
    'weak': ('المشاكل كثيرة وتبطئ التطوير وتزيد احتمال الأعطال؛ الإصلاح مطلوب قريبًا.',
             'Problems are many; they slow development and make failures likelier. Fixing is needed soon.'),
    'critical': ('المشروع معرّض لأعطال أو تسريب بيانات؛ ابدأ الإصلاح فورًا.', 'The project is exposed to failures or data leaks; start fixing now.'),
}
RELATION = {'retain': ('يبقى كما هو', 'stays as it is'), 'modify': ('يُعدَّل', 'is changed'),
            'rebuild': ('يُعاد بناؤه', 'is rebuilt'), 'delete': ('يُحذف', 'is removed'),
            'retire': ('يُحذف', 'is removed'), 'introduce': ('جزء جديد', 'is new')}
GAP_STATUS = {'covered': ('الخطة تغطيه', 'the plan covers it'), 'partial': ('الخطة تغطيه جزئيًا', 'the plan covers part of it'),
              'missing': ('لا خطة له بعد', 'no plan for it yet')}
MILESTONE = {'stabilize': ('التثبيت', 'Stabilize'), 'safety_net': ('شبكة الأمان', 'Safety net'),
             'boundaries': ('ترتيب الحدود بين الأجزاء', 'Boundaries'), 'hardening': ('التحصين', 'Hardening')}
OUTCOME = {'repair': ('إصلاحه', 'fix it'), 'retain': ('إبقاؤه كما هو', 'keep it as it is'),
           'blocked_missing_requirement': ('ينقصنا تعريف المطلوب', 'we lack a stated requirement')}


# ---------------------------------------------------------------- data

def _load(path, default):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


def classify(task, debt=None, category=None):
    """(area, severity) of one card: the PATTERNS table, with the debt register's severity when it has one."""
    pattern = task.get('pattern') or 'generic'
    area, severity = PATTERNS.get(pattern, PATTERNS['generic'])
    if pattern not in PATTERNS or pattern == 'generic':
        area = CATEGORY_AREA.get(category, area)
    if debt in SEVERITY_WEIGHT: severity = debt
    return area, severity


def problems(report):
    """One row per plan card, with its area, severity, confidence and plain words."""
    report = Path(report)
    plan = _load(report / 'plan.json', {}) or {}
    dossier = _load(report / 'dossier.json', {}) or {}
    register = _load(report / 'debt-register.json', {}) or {}
    claims = {c.get('id'): c for c in dossier.get('claims') or [] if isinstance(c, dict)}
    debt = {i.get('claim_id'): i for i in register.get('items') or [] if isinstance(i, dict) and i.get('claim_id')}
    rows = []
    for task in plan.get('tasks') or []:
        if not isinstance(task, dict): continue
        claim = claims.get(task.get('claim_id')) or {}
        item = debt.get(task.get('claim_id')) or {}
        area, severity = classify(task, item.get('severity'), item.get('category'))
        assessment = claim.get('assessment') or {}
        decision = task.get('decision') or {}
        rows.append({'id': task.get('id', ''), 'pattern': task.get('pattern') or 'generic', 'area': area, 'severity': severity,
                     'confidence': claim.get('confidence') or task.get('confidence') or 'CONFIRMED',
                     'auto': task.get('kind') == 'remediate' and decision.get('readiness') == 'ready',
                     'outcomes': decision.get('allowed_outcomes') or [], 'options': task.get('options') or [],
                     'effort': task.get('effort'), 'change': assessment.get('proposed_change') or task.get('change') or '', 'priority': task.get('priority') or 0,
                     'title': task.get('title') or claim.get('statement') or '', 'paths': task.get('paths') or [],
                     'before': assessment.get('before') or task.get('before') or '',
                     'after': assessment.get('after') or task.get('after') or ''})
    ranked = sorted((r['priority'] for r in rows), reverse=True)
    for row in rows:
        above = sum(1 for p in ranked if p > row['priority'])
        row['top'] = max(1, math.ceil((above + 1) * 100 / len(ranked)))
    return rows


def stage_status(report):
    manifest = _load(Path(report) / 'run-manifest.json', {}) or {}
    return {name: (row or {}).get('status') for name, row in (manifest.get('stages') or {}).items()}


def score(rows, source_files, statuses=None, known=True):
    """The health score and each area's score, from the formula in the module docstring.

    known is False when the report has no plan: then nothing was counted, and no area gets a score.
    """
    statuses = statuses or {}
    size = max(source_files or 0, 100) / 100
    areas = {}
    for area in AREAS:
        mine = [r for r in rows if r['area'] == area]
        points = sum(SEVERITY_WEIGHT[r['severity']] * CONFIDENCE_WEIGHT.get(r['confidence'], 1.0) for r in mine)
        density = points / size
        measured = known and statuses.get(AREA_STAGE[area]) not in ('failed', 'not_reached')
        value = round(100 * HALF_POINT / (HALF_POINT + density))
        counts = {s: sum(r['severity'] == s for r in mine) for s in SEVERITIES}
        light = ('red' if value < 50 or counts['critical'] else 'green' if value >= 80 and not counts['high'] else 'amber')
        areas[area] = {'score': value if measured else None, 'points': round(points), 'density': round(density),
                       'counts': counts, 'total': len(mine), 'light': light if measured else 'grey', 'measured': measured}
    measured = [a['score'] for a in areas.values() if a['score'] is not None]
    overall = round(sum(measured) / len(measured)) if measured else None
    capped = any(r['severity'] == 'critical' and r['confidence'] == 'CONFIRMED' for r in rows)
    if overall is not None and capped: overall = min(overall, CRITICAL_CAP)
    grade = next(name for floor, name in GRADES if (overall or 0) >= floor) if overall is not None else None
    return {'score': overall, 'grade': grade, 'areas': areas, 'capped': capped, 'size': round(size * 100)}


def model(report, progress=None):
    report = Path(report)
    dossier = _load(report / 'dossier.json', {}) or {}
    rows = problems(report)
    statuses = stage_status(report)
    coverage = dossier.get('coverage') or {}
    plan = _load(report / 'plan.json', {}) or {}
    known = isinstance(plan.get('tasks'), list)
    return {'rows': rows, 'statuses': statuses, 'coverage': coverage,
            'score': score(rows, coverage.get('source_files'), statuses, known), 'plan': plan, 'target': _load(report / 'target-architecture.json', {}) or {},
            'gap_matrix': _load(report / 'gap-matrix.json', {}) or {}, 'manifest': _load(report / 'run-manifest.json', {}) or {},
            'dossier': dossier, 'progress': progress or {}}


# ---------------------------------------------------------------- html helpers

def esc(value):
    return html.escape(str(value), quote=True)


def T(ar, en, tag='span', cls=''):
    """The same words in both languages; the page shows one of them."""
    extra = f' {cls}' if cls else ''
    return f'<{tag} class="l-ar{extra}" lang="ar">{ar}</{tag}><{tag} class="l-en{extra}" lang="en">{en}</{tag}>'


def w(key, tag='span', cls=''):
    ar, en = W[key]
    return T(esc(ar), esc(en), tag, cls)


def num(value, meaning, cls='n'):
    """A number, with what it means in a data attribute; the visible words beside it say it too."""
    return f'<span class="{cls}" data-meaning="{esc(meaning)}">{esc(value)}</span>'


def lit(text):
    """A file path or an identifier, shown as it is, left to right; the readability check does not read it as a score."""
    return f'<code class="lit" dir="ltr" data-literal="1">{esc(text)}</code>'


def quoted(text):
    """A sentence the plan wrote in the reader's language, quoted as it is (it may name an identifier such as E4)."""
    return f'<span class="quote" data-literal="quote">{esc(text or "")}</span>'


def said(text):
    """A sentence the engine wrote (in English or in the report's language), shown as written."""
    return f'<span class="said" dir="auto" data-literal="quote">{esc(text)}</span>' if text else ''


def tech(text):
    """A technical sentence the engine wrote in English, kept as written."""
    return f'<span class="tech" lang="en" dir="ltr" data-literal="1">{esc(text)}</span>' if text else ''


def unavailable(section, error=None):
    note = f'<!-- {esc(type(error).__name__)} -->' if error else ''
    return f'<div class="card na">{w("na", "p")}{note}</div>'


def sev_chip(severity):
    return f'<span class="chip sev-{severity}" data-severity="{severity}"><i aria-hidden="true"></i>{w(severity)}</span>'


def priority_words(top, severity=None):
    band = 'vhigh' if top <= 10 else 'high' if top <= 30 else 'mid' if top <= 60 else 'low'
    # The ranking weighs how much of the program a problem reaches; a known security hole reaches little code and
    # is still urgent. A serious problem is never shown as low priority: its severity decides.
    if severity in ('critical', 'high') and band in ('mid', 'low'):
        return T('عاجلة بسبب خطورتها', 'Urgent because of its severity')
    ar = {'vhigh': 'أولوية عالية جدًا', 'high': 'أولوية عالية', 'mid': 'أولوية متوسطة', 'low': 'أولوية منخفضة'}[band]
    en = {'vhigh': 'Very high priority', 'high': 'High priority', 'mid': 'Medium priority', 'low': 'Low priority'}[band]
    if band == 'low':
        return T(f'{ar} — في النصف الأدنى من الترتيب', f'{en} — in the lower half of the ranking')
    rank = num(f'{top}%', f'rank among all problems: in the top {top}%')
    return T(f'{ar} — ضمن أعلى {rank} من المشاكل', f'{en} — in the top {rank} of problems')


# ---------------------------------------------------------------- charts (SVG)

def svg_text(x, y, text, cls, side='left', rtl=False, attrs=''):
    """SVG text anchored at x on its left or right side; Arabic runs right to left so its words keep their order."""
    anchor = ('end' if side == 'left' else 'start') if rtl else ('start' if side == 'left' else 'end')
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" direction="{"rtl" if rtl else "ltr"}" class="{cls}"{attrs}>'
            f'{esc(text)}</text>')


def severity_bars(areas, rtl):
    """Horizontal stacked bars: problems per area, split by severity. One SVG per reading direction."""
    width, label, row, bar = 900, 210, 42, 22
    total_max = max([a['total'] for a in areas.values()] + [1])
    plot = width - label - 120
    parts = [f'<svg viewBox="0 0 {width} {row * len(AREAS) + 10}" direction="ltr" role="img" class="chart bars {"l-ar" if rtl else "l-en"}" '
             f'aria-label="{esc("المشاكل لكل مجال حسب الخطورة" if rtl else "Problems per area by severity")}">']
    for index, area in enumerate(AREAS):
        data = areas[area]
        y = index * row + 8
        name = W['structure_area' if area == 'structure' else area][0 if rtl else 1]
        tx = width - 4 if rtl else 4
        parts.append(svg_text(tx, y + bar / 2 + 5, name, 'axis-label', 'right' if rtl else 'left', rtl))
        start = label
        segments = [(s, data['counts'][s]) for s in SEVERITIES if data['counts'][s]]
        for position, (severity, count) in enumerate(segments):
            length = max(3, plot * count / total_max) - (2 if position < len(segments) - 1 else 0)
            x = (width - start - length) if rtl else start
            last = position == len(segments) - 1
            meaning = f'{count} {severity} problems in {area}'
            words = (f'{name} — {W[severity][0 if rtl else 1]}: {count}')
            radius = 4 if last else 0
            if radius and length > 8:
                if rtl:
                    d = (f'M{x + length:.1f},{y} H{x + radius:.1f} Q{x:.1f},{y} {x:.1f},{y + radius} V{y + bar - radius} '
                         f'Q{x:.1f},{y + bar} {x + radius:.1f},{y + bar} H{x + length:.1f} Z')
                else:
                    d = (f'M{x:.1f},{y} H{x + length - radius:.1f} Q{x + length:.1f},{y} {x + length:.1f},{y + radius} '
                         f'V{y + bar - radius} Q{x + length:.1f},{y + bar} {x + length - radius:.1f},{y + bar} H{x:.1f} Z')
                parts.append(f'<path d="{d}" class="seg sev-{severity}" data-meaning="{esc(meaning)}"><title>{esc(words)}</title></path>')
            else:
                parts.append(f'<rect x="{x:.1f}" y="{y}" width="{length:.1f}" height="{bar}" class="seg sev-{severity}" '
                             f'data-meaning="{esc(meaning)}"><title>{esc(words)}</title></rect>')
            start += length + 2
        end = (width - start - 6) if rtl else start + 6
        total_words = (f'المشاكل: {data["total"]}' if rtl else f'{data["total"]} problems') if data['total'] else ('لا مشاكل' if rtl else 'none')
        total_meaning = f'{data["total"]} problems in {area}'
        parts.append(svg_text(end, y + bar / 2 + 5, total_words, 'value-label', 'right' if rtl else 'left', rtl,
                              f' data-meaning="{esc(total_meaning)}"'))
    parts.append('</svg>')
    return ''.join(parts)


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
        files = sum(c.get('files') or 0 for c in members)
        y = index * row + 2
        words = (f'الأجزاء: {len(members)} · الملفات: {files}' if rtl else f'{len(members)} parts · {files} files')
        meaning = f'{len(members)} target parts and {files} files in the {name} layer'
        parts.append(f'<g data-meaning="{esc(meaning)}"><rect x="2" y="{y}" width="{width - 4}" height="{row - 4}" rx="4" class="layer"/>'
                     + svg_text(width - 12 if rtl else 12, y + 18, words, 'layer-count', 'right' if rtl else 'left', rtl)
                     + svg_text(12 if rtl else width - 12, y + 18, name, 'layer-name', 'left' if rtl else 'right') + '</g>')
    parts.append('</svg>')
    return ''.join(parts)


# ---------------------------------------------------------------- sections

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
    cards = []
    for area in AREAS:
        a = s['areas'][area]
        key = 'structure_area' if area == 'structure' else area
        light_word = {'green': ('جيد', 'Good'), 'amber': ('يحتاج انتباهًا', 'Needs attention'),
                      'red': ('يحتاج إصلاحًا', 'Needs fixing'), 'grey': ('لم يُقَس', 'Not measured')}[a['light']]
        if not a['measured']:
            sentence = T('لم يكتمل الفحص الذي يقيس هذا المجال، فلا نعرف حالته.', 'The check that measures this area did not complete, so its state is unknown.')
        elif not a['total']:
            sentence = T('لم نجد مشاكل في هذا المجال.', 'No problems found in this area.')
        else:
            worst = next(sv for sv in SEVERITIES if a['counts'][sv])
            kinds = {}
            for r in rows:
                if r['area'] == area: kinds[r['pattern']] = kinds.get(r['pattern'], 0) + 1
            top = max(kinds, key=kinds.get)
            count = num(a['total'], f'problems in {area}')
            sentence = T(f'عدد المشاكل: {count}<br>أخطرها: {esc(W[worst][0])}<br>أكثرها: {esc(plain.problem(top, "ar")[0])}',
                         f'Problems: {count}<br>Most serious: {esc(W[worst][1].lower())}<br>Most common: {esc(plain.problem(top, "en")[0])}')
        area_score = (T(f'{num(a["score"], f"{area} score out of 100")} من {HUNDRED}', f'{num(a["score"], f"{area} score out of 100")} out of {HUNDRED}')
                      if a['score'] is not None else '')
        cards.append(f'<div class="card area light-{a["light"]}" data-area="{area}"><div class="area-head">'
                     f'<span class="light" aria-hidden="true"></span><h4>{w(key)}</h4></div>'
                     f'<div class="area-score">{area_score}</div>'
                     f'<p class="light-word">{T(*map(esc, light_word))}</p><p class="small">{sentence}</p>'
                     f'<p class="muted small">{T(*map(esc, AREA_WHAT[area]))}</p></div>')
    out.append(f'<h3>{T("المجالات الخمسة", "The five areas")}</h3><div class="grid areas">' + ''.join(cards) + '</div>')
    out.append(top_problems(rows))
    auto = sum(r['auto'] for r in rows)
    decide = len(rows) - auto
    out.append(f'<div class="grid two"><div class="card stat good-bg"><div class="stat-n">{num(auto, "problems EAOS can fix automatically")}</div>'
               f'<p>{T("مشاكل يستطيع EAOS إصلاحها آليًا، ويتحقق بعد كل إصلاح أن البرنامج لم ينكسر.", "problems EAOS can fix automatically, checking after each fix that the program still works.")}</p></div>'
               f'<div class="card stat warn-bg"><div class="stat-n">{num(decide, "problems that need the owner or a person to decide")}</div>'
               f'<p>{T("مشاكل تحتاج قرارك أو نظرة شخص قبل أي تغيير.", "problems need your decision, or a person to look, before any change.")}</p></div></div>')
    out.append(not_checked(m))
    out.append(how_computed(m))
    return ''.join(out)


def meter(value):
    bands = ((0, 40, 'critical'), (40, 60, 'weak'), (60, 75, 'fair'), (75, 90, 'good'), (90, 100, 'excellent'))
    cells = ''.join(f'<span class="band band-{g}" style="flex:{hi - lo}">{w(g)}</span>' for lo, hi, g in bands)
    return (f'<div class="meter" aria-hidden="true"><div class="bands">{cells}</div>'
            f'<div class="marker" style="inset-inline-start:{value}%"></div></div>')


def top_problems(rows):
    groups = {}
    for r in rows: groups.setdefault(r['pattern'], []).append(r)
    def weight(group): return sum(SEVERITY_WEIGHT[r['severity']] * CONFIDENCE_WEIGHT.get(r['confidence'], 1.0) for r in group)
    ordered = sorted(groups, key=lambda p: (min(SEVERITIES.index(r['severity']) for r in groups[p]), -weight(groups[p]),
                                            plain.ORDER.index(p) if p in plain.ORDER else len(plain.ORDER)))
    if not ordered:
        return f'<h3>{T("أهم المشاكل", "Main problems")}</h3><div class="card">{T("لم نجد مشاكل تحتاج إصلاحًا.", "No problems that need fixing were found.", "p")}</div>'
    items = []
    for index, pattern in enumerate(ordered[:5], 1):
        group = groups[pattern]
        worst = next(s for s in SEVERITIES if any(r['severity'] == s for r in group))
        ready = sum(r['auto'] for r in group)
        (tar, why_ar), (ten, why_en) = plain.problem(pattern, 'ar'), plain.problem(pattern, 'en')
        count, fixed = num(len(group), 'cards of this kind'), num(ready, 'cases EAOS fixes automatically')
        counts = T(f'عدد الحالات: {count} · يصلحها EAOS آليًا: {fixed}', f'Cases: {count} · EAOS fixes automatically: {fixed}')
        items.append(f'<li class="card problem"><span class="rank" data-meaning="position in the list of main problems">{index}</span>'
                     f'<div><h4>{T(esc(tar), esc(ten))} {sev_chip(worst)}</h4><p>{T(esc(why_ar), esc(why_en))}</p>'
                     f'<p class="muted small">{counts}</p></div></li>')
    return f'<h3>{T("أهم خمس مشاكل", "The five main problems")}</h3><ol class="problems">' + ''.join(items) + '</ol>'


def not_checked(m):
    statuses, coverage, manifest = m['statuses'], m['coverage'], m['manifest']
    items = []
    stages = manifest.get('stages') or {}
    for stage, status in statuses.items():
        if status in ('failed', 'not_reached'):
            items.append(T(f'لم يكتمل: {esc(plain.stage(stage, "ar"))}. ما كان سيجده قد يكون ناقصًا.',
                           f'Did not complete: {esc(plain.stage(stage, "en"))}. What it would have found may be missing.', 'li'))
    for stage, status in statuses.items():
        covered = ('verify', 'semantic') if coverage else ()
        if status in ('unavailable', 'skipped') and stage not in ('site', 'pdf', 'quality', *covered):
            reason = (stages.get(stage) or {}).get('reason') or ''
            words = T(f'لم يُشغَّل: {esc(plain.stage(stage, "ar"))}.', f'Not run: {esc(plain.stage(stage, "en"))}.')
            items.append(f'<li title="{esc(reason)}">{words}</li>')
    if coverage:
        if not coverage.get('executed_verification'):
            items.append(T('لم تُشغَّل اختبارات المشروع، فلا نعرف أي أجزاء تغطيها الاختبارات فعلًا.',
                           "The project's tests were not run, so we do not know which parts they actually cover.", 'li'))
        if not coverage.get('runtime_confirmation'):
            items.append(T('لم نراقب البرنامج وهو يعمل: كل ما هنا من قراءة الكود، لا من تشغيله.',
                           'We did not watch the program running: everything here comes from reading the code, not running it.', 'li'))
        unparsed = (coverage.get('source_files') or 0) - (coverage.get('files_parsed') or 0)
        if unparsed > 0:
            items.append(T(f'ملفات لم نستطع قراءتها: {num(unparsed, "source files that could not be read")}.',
                           f'{num(unparsed, "source files that could not be read")} source files could not be read.', 'li'))
        if not coverage.get('semantic_review'):
            items.append(T('لم يراجع مساعد ذكي معنى الكود؛ الأحكام هنا من قواعد آلية.',
                           'No AI assistant reviewed what the code means; the findings come from mechanical rules.', 'li'))
    items.append(T('الأداء الحقيقي تحت الضغط لم يُقَس بتشغيل؛ هو تقدير من شكل الكود.',
                   'Real performance under load was not measured by running it; it is an estimate from the shape of the code.', 'li'))
    return (f'<h3>{T("ما لم نفحصه", "What we did not check")}</h3><div class="card honest">'
            f'<p>{T("الأمانة مهمة: هذه حدود هذا الفحص. قد توجد مشاكل هنا لم نرها.", "Honesty matters: these are the limits of this check. There may be problems here we did not see.")}</p>'
            f'<ul>{"".join(items)}</ul></div>')


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
    out = [legend()]
    counts_table = ''.join(f'<tr><td>{w("structure_area" if a == "structure" else a)}</td>'
                           + ''.join(f'<td>{num(s["areas"][a]["counts"][sv], f"{sv} problems in this area")}</td>' for sv in SEVERITIES)
                           + f'<td>{num(s["areas"][a]["total"], "all problems in this area")}</td></tr>' for a in AREAS)
    chips = ''.join(f'<span class="key">{sev_chip(sv)}</span>' for sv in SEVERITIES)
    out.append(f'<div class="card"><h4>{T("عدد المشاكل في كل مجال، حسب الخطورة", "Problems in each area, by severity")}</h4>'
               f'<div class="keys">{chips}</div>{severity_bars(s["areas"], True)}{severity_bars(s["areas"], False)}'
               f'<details><summary>{T("عرض كجدول", "Show as a table")}</summary><table class="tbl"><thead><tr><th>{T("المجال", "Area")}</th>'
               + ''.join(f'<th>{w(sv)}</th>' for sv in SEVERITIES) + f'<th>{T("المجموع", "Total")}</th></tr></thead><tbody>{counts_table}</tbody></table></details></div>')
    out.append(
        f'<div class="card filters" role="search"><input type="search" id="q" data-ph-ar="ابحث باسم ملف أو كلمة…" data-ph-en="Search a file name or a word…" placeholder="ابحث باسم ملف أو كلمة…">'
        f'<select id="fsev"><option value="">{esc("كل درجات الخطورة")}</option>' + ''.join(f'<option value="{sv}">{esc(W[sv][0])}</option>' for sv in SEVERITIES) + '</select>'
        f'<select id="farea"><option value="">{esc("كل المجالات")}</option>' + ''.join(f'<option value="{a}">{esc(W["structure_area" if a == "structure" else a][0])}</option>' for a in AREAS) + '</select>'
        f'<label class="check"><input type="checkbox" id="fauto"> {T("ما يُصلح آليًا فقط", "Automatic fixes only")}</label>'
        f'<span class="muted" id="shown" aria-live="polite"></span></div>')
    if not rows:
        out.append(f'<div class="card">{T("لم نجد مشاكل تحتاج إصلاحًا.", "No problems that need fixing were found.", "p")}</div>')
    for area in AREAS:
        mine = [r for r in rows if r['area'] == area]
        if not mine: continue
        groups = {}
        for r in mine: groups.setdefault(r['pattern'], []).append(r)
        blocks = []
        for pattern in sorted(groups, key=lambda p: (min(SEVERITIES.index(r['severity']) for r in groups[p]), -len(groups[p]))):
            group = sorted(groups[pattern], key=lambda r: (SEVERITIES.index(r['severity']), r['top'], r['id']))
            (tar, why_ar), (ten, why_en) = plain.problem(pattern, 'ar'), plain.problem(pattern, 'en')
            ready = sum(r['auto'] for r in group)
            count, fixed = num(len(group), 'problems of this kind'), num(ready, 'cases fixed automatically')
            meta = T(f'الحالات: {count} · آليًا: {fixed}', f'Cases: {count} · automatic: {fixed}')
            head = (f'<summary><span class="g-title">{T(esc(tar), esc(ten))}</span>'
                    f'<span class="g-meta">{meta}</span></summary>')
            items = ''.join(gap_row(r) for r in group)
            blocks.append(f'<details class="group" open>{head}<p class="why">{T(esc(why_ar), esc(why_en))}</p><div class="rows">{items}</div></details>')
        count = num(len(mine), 'problems in this area')
        out.append(f'<h3 class="area-title" data-area-block="{area}">{w("structure_area" if area == "structure" else area)} '
                   f'<span class="muted">{T(f"— عدد المشاكل: {count}", f"— problems: {count}")}</span></h3>' + ''.join(blocks))
    out.append(component_gaps(m))
    return ''.join(out)


def gap_row(r):
    where = ' '.join(lit(p) for p in r['paths'][:3])
    more = len(r['paths']) - 3
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
    counts = component_problems(m)
    rows = []
    for g in sorted(matrix, key=lambda g: -counts.get(g.get('component'), (0, 0))[1]):
        relation = RELATION.get((g.get('current') or {}).get('relation'), (esc((g.get('current') or {}).get('relation', '')),) * 2)
        status = GAP_STATUS.get(g.get('gap'), (g.get('gap') or '', g.get('gap') or ''))
        problems_here = counts.get(g.get('component'), (0, 0))[1]
        rows.append(f'<tr><td>{lit(g.get("current_origin") or g.get("component") or "")}</td><td>{T(*map(esc, relation))}</td>'
                    f'<td>{lit(g.get("target_component") or "—")}</td><td>{T(*map(esc, status))}</td>'
                    f'<td>{num(problems_here, "problems found in this part")}</td>'
                    f'<td>{num(g.get("files_to_move") or 0, "files that move to another place")}</td>'
                    f'<td>{num(g.get("forbidden_imports") or 0, "imports that break the target layering")}</td></tr>')
    return (f'<h3>{T("الفجوات حسب أجزاء البرنامج", "Gaps by part of the program")}</h3><div class="card scroll">'
            f'<p class="muted">{T("لكل جزء من البرنامج: ماذا سيحدث له، وأين يذهب في البنية المستهدفة، وهل تغطيه الخطة.", "For each part of the program: what happens to it, where it goes in the target structure, and whether the plan covers it.")}</p>'
            f'<table class="tbl"><thead><tr><th>{T("الجزء اليوم", "Part today")}</th><th>{T("ماذا يحدث له", "What happens")}</th>'
            f'<th>{T("مكانه المستهدف", "Target place")}</th><th>{T("الخطة", "Plan")}</th><th>{T("المشاكل فيه", "Problems in it")}</th>'
            f'<th>{T("ملفات تنتقل", "Files to move")}</th><th>{T("استيرادات مخالفة", "Wrong-way imports")}</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def component_problems(m):
    """{component id: (files, problems)}: a card counts in every part one of its files belongs to."""
    target = m['target']
    components = target.get('current_components') or target.get('components') or []
    owner = {}
    for c in components:
        for path in c.get('paths') or []: owner[path] = c.get('id')
    counts = {c.get('id'): [c.get('files') or len(c.get('paths') or []), 0] for c in components}
    for r in m['rows']:
        for cid in {owner.get(p) for p in r['paths']} - {None}:
            counts[cid][1] += 1
    return {k: tuple(v) for k, v in counts.items()}


def section_structure(m):
    target = m['target']
    components = target.get('current_components') or target.get('components') or []
    if not components:
        return unavailable('structure')
    counts = component_problems(m)
    root = target.get('root') or ''
    items = []
    for c in components:
        files, found = counts.get(c.get('id'), (0, 0))
        name = c.get('name') or c.get('id') or ''
        short = name[len(root):] if root and name.startswith(root) and len(name) > len(root) else name
        items.append({'name': name, 'short': short or name, 'files': files, 'size': max(files, 1), 'problems': found,
                      'density': found / max(files, 1), 'relation': c.get('relation'), 'target': c.get('target_component')})
    legend_steps = ''.join(
        f'<span class="heat-key"><i style="background:{HEAT[i]}"></i>{T(label_ar, label_en)}</span>'
        for i, (label_ar, label_en) in enumerate(heat_labels()))
    legend_steps = f'<span class="heat-key"><i style="background:var(--tile-empty)"></i>{T("بلا مشاكل", "no problems")}</span>' + legend_steps
    out = [f'<div class="grid map-grid"><div class="card"><h4>{T("البنية اليوم", "The structure today")}</h4>'
           f'<p class="muted small">{T("كل مربع جزء من المشروع؛ مساحته بعدد ملفاته، ولونه بكثافة المشاكل فيه (مشاكل لكل عشرة ملفات). مرّر المؤشر لترى التفاصيل.", "Each box is a part of the project; its size is its number of files, its colour the density of problems in it (problems per ten files). Hover for details.")}</p>'
           f'{treemap(items, True)}{treemap(items, False)}<div class="heat-legend">{legend_steps}</div></div>']
    tcomps = target.get('target_components') or []
    if tcomps:
        out.append(f'<div class="card"><h4>{T("البنية المستهدفة", "The target structure")}</h4>'
                   f'<p class="muted small">{T("الطبقات من الأعلى (ما يراه المستخدم) إلى الأسفل (الأساس). كل طبقة تعتمد فقط على ما تحتها.", "Layers from the top (what users see) to the bottom (the foundation). Each layer depends only on those below it.")}</p>'
                   f'{layer_diagram(tcomps, True)}{layer_diagram(tcomps, False)}</div>')
    else:
        out.append(f'<div class="card"><h4>{T("البنية المستهدفة", "The target structure")}</h4>{unavailable("target")}</div>')
    out.append('</div>')
    out.append(f'<h3>{T("الفرق بين اليوم والمستهدف", "The difference between today and the target")}</h3><div class="card"><ul class="diff">{"".join(differences(m, items))}</ul></div>')
    out.append(cycles(m))
    out.append(f'<details class="card"><summary>{T("كل الأجزاء كجدول", "All parts as a table")}</summary><table class="tbl"><thead><tr>'
               f'<th>{T("الجزء", "Part")}</th><th>{T("الملفات", "Files")}</th><th>{T("المشاكل", "Problems")}</th><th>{T("مشاكل لكل عشرة ملفات", "Problems per ten files")}</th></tr></thead><tbody>'
               + ''.join(f'<tr><td>{lit(i["name"])}</td><td>{num(i["files"], "files in this part")}</td><td>{num(i["problems"], "problems in this part")}</td>'
                         f'<td>{num(round(i["density"] * 10), "problems per ten files in this part")}</td></tr>'
                         for i in sorted(items, key=lambda i: -i['problems'])) + '</tbody></table></details>')
    return ''.join(out)


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
    lines = []
    relations = {}
    for c in target.get('current_components') or target.get('components') or []:
        relations[c.get('relation')] = relations.get(c.get('relation'), 0) + 1
    if relations:
        ar = '، '.join(f'{num(n, "parts with this fate")} {esc(RELATION.get(k, (k, k))[0])}' for k, n in sorted(relations.items(), key=lambda kv: -kv[1]))
        en = ', '.join(f'{num(n, "parts with this fate")} {esc(RELATION.get(k, (k, k))[1])}' for k, n in sorted(relations.items(), key=lambda kv: -kv[1]))
        total = sum(relations.values())
        lines.append(T(f'من {num(total, "parts of the project today")} جزءًا اليوم: {ar}.', f'Of the {num(total, "parts of the project today")} parts today: {en}.', 'li'))
    tcomps = target.get('target_components') or []
    if tcomps:
        layers = len({c.get('layer') for c in tcomps})
        lines.append(T(f'البنية المستهدفة فيها {num(len(tcomps), "parts in the target structure")} جزءًا في {num(layers, "layers in the target structure")} طبقة، لكل منها مسؤولية واحدة.',
                       f'The target structure has {num(len(tcomps), "parts in the target structure")} parts in {num(layers, "layers in the target structure")} layers, each with one responsibility.', 'li'))
    forbidden = target.get('forbidden_edges')
    if isinstance(forbidden, int) and forbidden:
        lines.append(T(f'{num(forbidden, "imports that go the wrong way between layers")} استيرادًا يسير في الاتجاه الخطأ بين الطبقات، ويجب قلبه.',
                       f'{num(forbidden, "imports that go the wrong way between layers")} imports go the wrong way between layers and have to be turned around.', 'li'))
    moves = sum((g.get('files_to_move') or 0) for g in target.get('gap_matrix') or [])
    if moves:
        lines.append(T(f'{num(moves, "files that move to another place")} ملفًا ينتقل إلى مكان آخر.', f'{num(moves, "files that move to another place")} files move to another place.', 'li'))
    for item in sorted(items, key=lambda i: -i['problems'])[:3]:
        if not item['problems']: break
        rel = RELATION.get(item['relation'], ('', ''))
        dest = (T(f' ← يصبح {lit(item["target"])}', f' → becomes {lit(item["target"])}') if item['target'] else '')
        lines.append(f'<li>{lit(item["name"])} ' + T(f'— المشاكل: {num(item["problems"], "problems in this part")} في ملفات عددها {num(item["files"], "files in this part")}؛ {esc(rel[0])}.',
                                                     f'{num(item["problems"], "problems in this part")} problems in {num(item["files"], "files in this part")} files; it {esc(rel[1])}.') + dest + '</li>')
    missing = [i for i in target.get('infrastructure') or [] if not i.get('present')]
    if missing:
        names = ' '.join(lit(i.get('area', '')) for i in missing)
        count = num(len(missing), 'pieces of infrastructure the target adds')
        words = T(f'ينقص المشروع {count} من أساسيات البنية التحتية:', f'The project lacks {count} pieces of basic infrastructure:')
        lines.append(f'<li>{words} {names}</li>')
    return lines or [T('لا توجد بيانات كافية للمقارنة.', 'Not enough data to compare.', 'li')]


def cycles(m):
    rows = [r for r in m['rows'] if r['pattern'] == 'import_cycle']
    head = f'<h3>{T("ملفات متشابكة (دورات استيراد)", "Tangled files (import cycles)")}</h3>'
    if not rows:
        return head + f'<div class="card">{T("لا توجد ملفات يعتمد بعضها على بعض في حلقة.", "No files depend on each other in a loop.", "p")}</div>'
    items = []
    for r in rows:
        paths = r['paths']
        folder = paths[0].rsplit('/', 1)[0] + '/' if len(paths) > 1 and '/' in paths[0] else ''
        shared = folder if folder and all(p.startswith(folder) for p in paths) else ''
        names = [p[len(shared):] for p in paths]
        size = num(len(paths), 'files in this loop')
        where = T(f'في {lit(shared)}', f'in {lit(shared)}') if shared else ''
        if len(paths) == 2:
            body = f'<span dir="ltr" class="pair">{lit(names[0])}<span class="arrow" aria-hidden="true">⇄</span>{lit(names[1])}</span>'
        else:
            body = '<span class="ring">' + ''.join(lit(n) for n in names) + '</span>'
        items.append(f'<li class="cycle"><div class="cycle-head"><span class="loop" aria-hidden="true">↻</span>'
                     f'{T(f"حلقة ملفاتها: {size}", f"A loop of {size} files")} {where}</div>{body}</li>')
    items = ''.join(items)
    return head + (f'<div class="card"><p>{T(esc(plain.problem("import_cycle", "ar")[1]), esc(plain.problem("import_cycle", "en")[1]))}</p>'
                   f'<ul class="cycles">{items}</ul></div>')


def section_plan(m):
    plan, rows, progress = m['plan'], m['rows'], m['progress'] or {}
    by_id = {r['id']: r for r in rows}
    kept, failed = set(), {}
    for wave in progress.get('waves') or []:
        kept |= set(wave.get('kept') or [])
        failed.update(wave.get('failed') or {})
    out = []
    total, done = len(rows), len(kept & set(by_id))
    out.append(f'<div class="grid three"><div class="card stat good-bg"><div class="stat-n">{num(done, "problems fixed so far")}</div><p>{T("مشاكل أُصلحت حتى الآن", "problems fixed so far")}</p></div>'
               f'<div class="card stat"><div class="stat-n">{num(total - done, "problems left")}</div><p>{T("مشاكل باقية", "problems left")}</p></div>'
               f'<div class="card stat warn-bg"><div class="stat-n">{num(len(failed), "fixes that were tried and did not pass")}</div><p>{T("إصلاحات جُرّبت ولم تنجح", "fixes tried that did not pass")}</p></div></div>')
    milestones = plan.get('milestones') or []
    if not milestones:
        out.append(f'<h3>{T("المراحل", "Milestones")}</h3>{unavailable("milestones")}')
    else:
        steps = []
        for index, stone in enumerate(milestones, 1):
            tasks = [t for t in stone.get('tasks') or []]
            finished = sum(t in kept for t in tasks)
            share = round(100 * finished / len(tasks)) if tasks else 0
            name = stone.get('name') or ''
            label = MILESTONE.get(name)
            if not label and name.startswith('build:'):
                label = (f'بناء {name[6:]}', f'Build {name[6:]}')
            label = label or (name, name)
            ready = sum(by_id[t]['auto'] for t in tasks if t in by_id)
            state = 'done' if tasks and finished == len(tasks) else 'active' if finished else 'todo'
            n_done, n_all = num(finished, 'cards finished in this milestone'), num(len(tasks), 'cards in this milestone')
            n_share, n_auto = num(f'{share}%', 'share finished'), num(ready, 'cards EAOS can fix automatically here')
            tally = T(f'المنجز: {n_done} من {n_all} ({n_share}) · يصلحها EAOS آليًا: {n_auto}',
                      f'{n_done} of {n_all} done ({n_share}) · {n_auto} automatic')
            steps.append(
                f'<li class="stone {state}"><span class="dot" data-meaning="milestone order">{index}</span><div class="card">'
                f'<h4>{T(esc(label[0]), esc(label[1]))} {lit(stone.get("id", ""))}</h4>'
                f'<p>{T(quoted(stone.get("goal_ar") or stone.get("goal")), quoted(stone.get("goal")))}</p>'
                f'<p class="muted small">{T("تُعتبر منجزة حين: " + quoted(stone.get("exit_ar") or stone.get("exit")), "Done when: " + quoted(stone.get("exit")))}</p>'
                f'<div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{share}"><span style="width:{share}%"></span></div>'
                f'<p class="small">{tally}</p></div></li>')
        out.append(f'<h3>{T("المراحل بالترتيب", "Milestones in order")}</h3><ol class="roadmap">{"".join(steps)}</ol>')
    out.append(waves_block(progress, failed, by_id))
    out.append(decisions_block(rows))
    return ''.join(out)


def waves_block(progress, failed, by_id):
    waves = progress.get('waves') or []
    head = f'<h3>{T("دفعات الإصلاح", "Fix batches")}</h3>'
    if not waves:
        return head + f'<div class="card">{T("لم تبدأ أي دفعة إصلاح بعد. حين تبدأ، تُبنى هذه الصفحة من جديد وتظهر هنا.", "No fix batch has started yet. When one does, this page is rebuilt and it shows here.", "p")}</div>'
    status_words = {'done': ('انتهت', 'finished'), 'merged': ('دُمجت', 'merged'), 'running': ('تعمل الآن', 'running'),
                    'failed': ('فشلت', 'failed'), 'pending': ('تنتظر', 'waiting')}
    rows = ''.join(
        f'<tr><td>{num(wave.get("number", i), "batch number")}</td><td>{T(*map(esc, status_words.get(wave.get("status"), (wave.get("status") or "—",) * 2)))}</td>'
        f'<td>{num(len(wave.get("kept") or []), "fixes kept in this batch")}</td><td>{num(len(wave.get("failed") or {}), "fixes that did not pass in this batch")}</td>'
        f'<td>{lit(wave.get("branch") or "—")}</td></tr>' for i, wave in enumerate(waves, 1))
    fails = ''.join(f'<li>{lit(card)} {tech(reason)}</li>' for card, reason in sorted(failed.items()))
    return head + (f'<div class="card scroll"><table class="tbl"><thead><tr><th>{T("الدفعة", "Batch")}</th><th>{T("الحالة", "Status")}</th>'
                   f'<th>{T("أُصلح", "Fixed")}</th><th>{T("لم ينجح", "Did not pass")}</th><th>{T("الفرع", "Branch")}</th></tr></thead><tbody>{rows}</tbody></table>'
                   + (f'<h4>{T("ما لم ينجح ولماذا", "What did not pass, and why")}</h4><ul class="fails">{fails}</ul>' if fails else '') + '</div>')


def decisions_block(rows):
    waiting = [r for r in rows if not r['auto']]
    head = f'<h3>{T("قرارات تحتاجك", "Decisions that need you")}</h3>'
    if not waiting:
        return head + f'<div class="card">{T("لا توجد قرارات معلقة.", "No decision is waiting.", "p")}</div>'
    groups = {}
    for r in waiting: groups.setdefault(r['pattern'], []).append(r)
    cards = []
    for pattern in sorted(groups, key=lambda p: -len(groups[p])):
        group = groups[pattern]
        (tar, why_ar), (ten, why_en) = plain.problem(pattern, 'ar'), plain.problem(pattern, 'en')
        found = {o for r in group for o in r['outcomes']}
        outcomes = [o for o in OUTCOME if o in found] + sorted(found - set(OUTCOME))
        answers = ''.join(f'<li>{T(*map(esc, OUTCOME.get(o, (o, o))))}</li>' for o in outcomes)
        sample = next((r for r in group if r['options']), None)
        options = ''
        if sample:
            options = (f'<details><summary>{T("الخيارات المقترحة لمثال منها", "The suggested options, for one example")} {lit(sample["id"])}</summary><ul class="options">'
                       + ''.join(f'<li><b>{esc(o.get("option", ""))}</b> <span class="muted">{esc(o.get("verdict", ""))}</span></li>'
                                 for o in sample['options'] if isinstance(o, dict)) + '</ul></details>')
        ids = ' '.join(lit(r['id']) for r in group[:40]) + (T(f' و{num(len(group) - 40, "more cards")} غيرها', f' and {num(len(group) - 40, "more cards")} more') if len(group) > 40 else '')
        count = num(len(group), 'cards waiting for a decision')
        cards.append(f'<div class="card decision"><h4>{T(esc(tar), esc(ten))} <span class="count">{T(f"البطاقات: {count}", f"cards: {count}")}</span></h4>'
                     f'<p>{T(esc(why_ar), esc(why_en))}</p>'
                     + (f'<p class="small">{T("المطلوب منك أن تختار لكل حالة:", "For each case you choose:")}</p><ul class="answers">{answers}</ul>' if answers else '')
                     + options + f'<details><summary>{T("البطاقات", "The cards")}</summary><p class="ids">{ids}</p></details></div>')
    return head + (f'<p class="muted">{T("هذه المشاكل لا يغيّرها EAOS وحده: تحتاج أن يقرر شخص هل هي مطلوبة، وما الصحيح.", "EAOS does not change these alone: a person has to decide whether they are wanted, and what is right.")}</p>'
                   f'<div class="grid two">{"".join(cards)}</div>')


# ---------------------------------------------------------------- page

def render(m, name, lang='ar'):
    parts = {}
    for section, build in (('summary', lambda: section_summary(m, name)), ('gaps', lambda: section_gaps(m)),
                           ('structure', lambda: section_structure(m)), ('plan', lambda: section_plan(m))):
        try: parts[section] = build()
        except Exception as error:     # one broken record costs its section, not the page or the audit
            parts[section] = unavailable(section, error)
    intro = {'summary': ('صحة المشروع في صفحة واحدة: الدرجة، والمجالات الخمسة، وأهم المشاكل، وما لم نفحصه.',
                         'The health of the project on one page: the score, the five areas, the main problems, and what we did not check.'),
             'gaps': ('كل مشكلة: أين هي، وما حالها الآن وما المطلوب، وخطورتها، وهل يصلحها EAOS آليًا.',
                      'Every problem: where it is, what it is now and what it should be, how serious it is, and whether EAOS fixes it.'),
             'structure': ('أجزاء المشروع اليوم وأين تتركز المشاكل، والبنية التي نقترحها بجانبها.',
                           'The parts of the project today and where problems gather, with the structure we propose beside it.'),
             'plan': ('ترتيب العمل مرحلة بعد مرحلة، وما أُنجز، وما ينتظر قرارك.',
                      'The order of the work, milestone by milestone, what is done, and what waits for your decision.')}
    nav = ''.join(f'<a href="#{s}" data-tab="{s}">{w(s)}</a>' for s in SECTIONS)
    body = ''.join(f'<section id="{s}" class="report" data-report="{s}"><header class="sec-head"><h2>{w(s)}</h2>'
                   f'<p class="muted">{T(*map(esc, intro[s]))}</p></header>{parts[s]}</section>' for s in SECTIONS)
    generated = ((m['dossier'].get('provenance') or {}).get('generated_at') or '')[:10]
    date = (f'<span class="muted">{T("تاريخ الفحص:", "Audit date:")} {num(generated, "the date of the audit")}</span>' if generated else '')
    direction = 'rtl' if lang == 'ar' else 'ltr'
    return (f'<!doctype html><html lang="{lang}" dir="{direction}" data-lang="{lang}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(W["title"][0 if lang == "ar" else 1])}: {esc(name)}</title>'
            f'<style>{CSS}</style></head><body><header class="top"><div class="wrap top-in"><div class="brand">'
            f'<div class="kicker">{T("تقرير EAOS", "EAOS report")}</div><h1>{w("title")}: {lit(name)}</h1>{date}</div>'
            f'<div class="actions"><button type="button" id="lang" class="btn">{T("English", "العربية")}</button>'
            f'<button type="button" id="print" class="btn ghost">{T("طباعة / PDF", "Print / PDF")}</button></div></div>'
            f'<nav class="tabs wrap" aria-label="reports">{nav}</nav></header>'
            f'<main class="wrap">{body}</main><footer class="wrap muted small">'
            f'{T("هذه الصفحة للقراءة. الملفات التقنية في المجلد نفسه مكتوبة للمساعد الذكي ولم تتغير.", "This page is for reading. The technical files in the same folder are written for the AI assistant and are unchanged.")}'
            f'</footer><script>{JS}</script></body></html>')


def empty(progress=None):
    return {'rows': [], 'statuses': {}, 'coverage': {}, 'score': score([], 0, known=False), 'plan': {}, 'target': {},
            'gap_matrix': {}, 'manifest': {}, 'dossier': {}, 'progress': progress or {}}


def write(report, lang='ar', name=None, progress=None):
    """Write <report>/human/index.html from the report's records and return its path.

    Never raises for missing or broken records: a section it cannot build says "not available".
    """
    report = Path(report)
    try:
        m = model(report, progress)
    except Exception:
        m = empty(progress)
    if name is None:
        name = Path(str((m['manifest'] or {}).get('target') or report)).name
    page = report / 'human' / 'index.html'
    page.parent.mkdir(parents=True, exist_ok=True)
    try:
        text = render(m, name, 'ar' if lang == 'ar' else 'en')
    except Exception:
        text = render(empty(progress), name, 'ar' if lang == 'ar' else 'en')
    page.write_text(text, encoding='utf-8')
    return page


# ---------------------------------------------------------------- the readability indicator

NUMBER = re.compile(r'\d+(?:[.,]\d+)?')
RAW_FRACTION = re.compile(r'(?<![\w.@/-])0\.\d+\b')


class _Reader(HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.problems, self.ids, self.legend, self.langs, self.severities = [], [], {}, False, set(), set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('data-report') and attrs.get('id'): self.ids[attrs['id']] = attrs['data-report']
        if attrs.get('data-legend') == 'severity': self.legend = True
        if self.legend and attrs.get('data-severity') and any(t == 'div' and a.get('data-legend') for t, a in self.stack):
            self.severities.add(attrs['data-severity'])
        for cls in (attrs.get('class') or '').split():
            if cls in ('l-ar', 'l-en'): self.langs.add(cls)
        if tag not in self.VOID and not tag.endswith('/'):
            self.stack.append((tag, attrs))

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        if any(tag in ('script', 'style', 'head') for tag, _ in self.stack) or not data.strip(): return
        literal = any('data-literal' in attrs for _, attrs in self.stack)
        meaning = any((attrs.get('data-meaning') or '').strip() for _, attrs in self.stack)
        if not literal and RAW_FRACTION.search(data):
            self.problems.append(f'raw decimal score in visible text: {data.strip()[:60]!r}')
        elif NUMBER.search(data) and not literal and not meaning:
            self.problems.append(f'a number with no stated meaning: {data.strip()[:60]!r}')


def readability_problems(html_text):
    """What stops a person from reading the page; an empty list means it passes.

    The rules: the four reports exist (section ids summary, gaps, structure, plan, each with data-report);
    a severity legend (data-legend="severity") defines all four levels; both languages are present
    (class l-ar and l-en); every number in visible text sits inside an element with a non-empty
    data-meaning attribute, unless it is part of a literal (data-literal: a file path or an identifier);
    and no raw fraction such as 0.79 is shown outside a literal, with or without a meaning.
    """
    reader = _Reader()
    reader.feed(html_text)
    found = []
    for section in SECTIONS:
        if reader.ids.get(section) != section:
            found.append(f'missing report section: {section}')
    if not reader.legend:
        found.append('no severity legend')
    elif reader.severities != set(SEVERITIES):
        found.append(f'the severity legend lacks: {", ".join(sorted(set(SEVERITIES) - reader.severities))}')
    for cls in ('l-ar', 'l-en'):
        if cls not in reader.langs:
            found.append(f'no text in {cls[2:]}')
    return found + sorted(set(reader.problems))


# ---------------------------------------------------------------- style and behaviour

CSS = r"""
:root{color-scheme:light;--bg:#f6f6f3;--surface:#ffffff;--surface-2:#f0efeb;--ink:#141413;--ink-2:#52514e;--muted:#6f6d67;
--line:#e3e1da;--accent:#2a5bd7;--accent-soft:#e8eefc;--good:#0a8a0a;--good-soft:#e6f4e6;--warn:#b77900;--warn-soft:#fff4dc;
--bad:#c73232;--bad-soft:#fbe9e9;--on-accent:#ffffff;--sev-critical:#d03b3b;--sev-high:#ec835a;--sev-medium:#fab219;--sev-low:#a9a79f;--tile-empty:#e9e8e3;
--shadow:0 1px 2px rgba(20,20,19,.05),0 4px 16px rgba(20,20,19,.05);--radius:14px}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--bg:#111110;--surface:#1b1b1a;--surface-2:#242422;--ink:#f4f3ef;--ink-2:#c9c7bf;
--muted:#9a978f;--line:#2f2f2c;--accent:#7ea2ff;--accent-soft:#1f2a45;--good:#3cc23c;--good-soft:#16301a;--warn:#f0b43a;--warn-soft:#352a12;
--bad:#ff7070;--bad-soft:#3a1c1c;--on-accent:#0b1020;--sev-low:#77756e;--tile-empty:#2b2b29;--shadow:none}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 system-ui,-apple-system,"Segoe UI","Noto Sans Arabic",Tahoma,sans-serif}
html[data-lang=ar] .l-en,html[data-lang=en] .l-ar{display:none!important}
.wrap{max-width:1180px;margin:0 auto;padding:0 24px}
.top{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--surface) 92%,transparent);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.top-in{display:flex;align-items:center;justify-content:space-between;gap:16px;padding-top:14px;padding-bottom:6px}
.kicker{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--accent);font-weight:700}
h1{font-size:22px;margin:0;line-height:1.3}h1 .lit{font-size:20px;background:none;padding:0;color:var(--ink)}
h2{font-size:26px;margin:0 0 4px}h3{font-size:19px;margin:36px 0 12px}h4{font-size:16px;margin:0 0 6px}
.actions{display:flex;gap:8px}.btn{font:inherit;font-size:14px;border:1px solid var(--accent);background:var(--accent);color:var(--on-accent);border-radius:999px;padding:6px 16px;cursor:pointer}
.btn.ghost{background:transparent;color:var(--accent)}.btn:focus-visible,.tabs a:focus-visible{outline:3px solid var(--accent-soft);outline-offset:2px}
.tabs{display:flex;gap:4px;overflow-x:auto}.tabs a{padding:10px 14px;color:var(--ink-2);text-decoration:none;border-bottom:3px solid transparent;font-weight:600;white-space:nowrap}
.tabs a.on{color:var(--accent);border-color:var(--accent)}.tabs a:hover{color:var(--ink)}
main{padding-top:28px;padding-bottom:40px}.js section.report{display:none}.js section.report.on{display:block}
.sec-head{margin-bottom:20px}.muted{color:var(--muted)}.small{font-size:14px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:18px 20px;box-shadow:var(--shadow)}
.grid{display:grid;gap:16px}.grid.two{grid-template-columns:repeat(auto-fit,minmax(300px,1fr));margin-top:16px}
.grid.three{grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}.grid.areas{grid-template-columns:repeat(auto-fit,minmax(210px,1fr))}
.hero{display:grid;grid-template-columns:220px 1fr;gap:28px;align-items:center;padding:26px 28px}
.hero-score{text-align:center}.big{font-size:72px;font-weight:800;line-height:1}.big small{display:block;font-size:14px;font-weight:500;color:var(--muted);margin-top:6px}
.grade-word{display:inline-block;margin-top:10px;padding:4px 14px;border-radius:999px;font-weight:700}
.grade-excellent,.grade-good{color:var(--good)}.grade-fair{color:var(--warn)}.grade-weak,.grade-critical{color:var(--bad)}
.grade-word.grade-excellent,.grade-word.grade-good{background:var(--good-soft)}.grade-word.grade-fair{background:var(--warn-soft)}.grade-word.grade-weak,.grade-word.grade-critical{background:var(--bad-soft)}
.lead{font-size:19px;margin:4px 0 16px}.hero h3{margin:0}
.meter{position:relative;margin:8px 0 4px}.bands{display:flex;gap:2px;height:26px;border-radius:6px;overflow:hidden;font-size:12px}
.band{display:flex;align-items:center;justify-content:center;color:var(--ink-2);background:var(--surface-2)}
.band-critical{box-shadow:inset 0 -4px 0 var(--sev-critical)}.band-weak{box-shadow:inset 0 -4px 0 var(--sev-high)}.band-fair{box-shadow:inset 0 -4px 0 var(--sev-medium)}
.band-good{box-shadow:inset 0 -4px 0 #6cc56c}.band-excellent{box-shadow:inset 0 -4px 0 var(--good)}
.marker{position:absolute;top:-6px;width:4px;height:38px;background:var(--ink);border-radius:2px;transform:translateX(-50%)}
html[dir=rtl] .marker{transform:translateX(50%)}
.note{font-size:14px;color:var(--bad)}
.area{border-top:5px solid var(--line)}.area.light-green{border-top-color:var(--good)}.area.light-amber{border-top-color:var(--sev-medium)}
.area.light-red{border-top-color:var(--sev-critical)}.area-head{display:flex;align-items:center;gap:8px}.area-head h4{margin:0;flex:1}
.light{width:14px;height:14px;border-radius:50%;background:var(--sev-low);flex:none}.light-green .light{background:var(--good)}
.light-amber .light{background:var(--sev-medium)}.light-red .light{background:var(--sev-critical)}
.area-score{font-size:14px;color:var(--muted);margin-top:8px}.area-score .n{font-size:30px;font-weight:800;color:var(--ink);margin-inline-end:4px}
.n{unicode-bidi:isolate;direction:ltr}.formula{display:block;margin-top:4px;font:13px ui-monospace,Menlo,Consolas,monospace;color:var(--ink-2);text-align:left}
.said{unicode-bidi:isolate;font-size:14px;color:var(--ink-2)}.quote{unicode-bidi:plaintext}
.cycle{border:1px solid var(--line);border-radius:10px;padding:10px 12px;background:var(--bg)}.cycle-head{font-size:14px;margin-bottom:6px;display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.loop{color:var(--bad);font-weight:800;font-size:18px}.ring{display:flex;flex-wrap:wrap;gap:6px;direction:ltr}.pair{display:inline-flex;gap:8px;align-items:center}
.light-word{margin:6px 0 2px;font-weight:700;font-size:14px}.light-green .light-word{color:var(--good)}.light-amber .light-word{color:var(--warn)}.light-red .light-word{color:var(--bad)}
.area p{margin:6px 0}
.problems{list-style:none;padding:0;margin:0;display:grid;gap:10px}.problem{display:flex;gap:16px;align-items:flex-start}
.problem p{margin:4px 0}.rank{flex:none;width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:var(--accent-soft);color:var(--accent);font-weight:800}
.stat{display:flex;gap:16px;align-items:center}.stat p{margin:0}.stat-n{font-size:40px;font-weight:800;min-width:90px;text-align:center}
.good-bg{background:var(--good-soft);border-color:transparent}.good-bg .stat-n{color:var(--good)}.warn-bg{background:var(--warn-soft);border-color:transparent}.warn-bg .stat-n{color:var(--warn)}
.honest ul{margin:8px 0 0;padding-inline-start:20px}.honest li{margin:4px 0}
.how ol{padding-inline-start:22px}.how li{margin:6px 0}
.tbl{width:100%;border-collapse:collapse;font-size:14px;margin-top:10px}.tbl th,.tbl td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:start;vertical-align:top}
.tbl th{font-weight:700;color:var(--ink-2);background:var(--surface-2)}.tbl td .n{font-variant-numeric:tabular-nums}
.scroll{overflow-x:auto}details>summary{cursor:pointer;color:var(--accent);font-weight:600;margin:6px 0}
.chip{display:inline-flex;align-items:center;gap:6px;font-size:13px;font-weight:700;padding:1px 10px 1px 10px;border-radius:999px;background:var(--surface-2);white-space:nowrap}
.chip i{width:10px;height:10px;border-radius:2px;display:inline-block}
.sev-critical i{background:var(--sev-critical)}.sev-high i{background:var(--sev-high)}.sev-medium i{background:var(--sev-medium)}.sev-low i{background:var(--sev-low)}
.chip.sev-critical{color:var(--bad)}.chip.sev-critical i{border-radius:50%}.chip.sev-high i{transform:rotate(45deg)}
.legend{margin-bottom:16px}.legend-item{display:grid;grid-template-columns:120px 1fr;gap:10px;align-items:center;padding:6px 0;border-top:1px solid var(--line)}
.keys{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0 10px}
.chart{width:100%;height:auto;display:block}.chart.bars{max-width:900px}.axis-label{font-size:15px;fill:var(--ink)}.value-label{font-size:14px;fill:var(--ink-2)}
.seg.sev-critical{fill:var(--sev-critical)}.seg.sev-high{fill:var(--sev-high)}.seg.sev-medium{fill:var(--sev-medium)}.seg.sev-low{fill:var(--sev-low)}
.seg:hover{opacity:.8}
.filters{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:16px 0;position:sticky;top:112px;z-index:3}
.filters input[type=search],.filters select{font:inherit;font-size:14px;padding:7px 12px;border:1px solid var(--line);border-radius:10px;background:var(--surface);color:var(--ink)}
.filters input[type=search]{flex:1;min-width:220px}.check{font-size:14px;display:flex;gap:6px;align-items:center}
.area-title{border-bottom:2px solid var(--line);padding-bottom:6px}
.group{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:10px 16px;margin:10px 0}
.group>summary{display:flex;justify-content:space-between;gap:10px;color:var(--ink);font-size:16px}.g-meta{color:var(--muted);font-weight:500;font-size:14px}
.why{margin:0 0 8px;color:var(--ink-2);font-size:14px}.rows{display:grid;gap:8px}
.rows .row:nth-child(n+6){display:none}.rows.all .row:nth-child(n+6){display:block}.more{font:inherit;font-size:14px;background:none;border:0;color:var(--accent);cursor:pointer;padding:4px 0}
.row{border:1px solid var(--line);border-radius:10px;padding:10px 12px;background:var(--bg)}.row[hidden]{display:none!important}
.row-head{display:flex;flex-wrap:wrap;gap:10px;align-items:center;font-size:14px}.row-head .lit{margin-inline-start:auto}
.conf{color:var(--ink-2)}.prio{color:var(--ink-2)}.where{font-size:14px;margin:6px 0}.lbl{color:var(--muted)}
.nowto{display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:14px}.nowto b{display:block;font-size:12px;color:var(--muted)}
.row-foot{display:flex;gap:12px;font-size:13px;margin-top:6px}.yes{color:var(--good);font-weight:700}.no{color:var(--warn);font-weight:700}
.lit{font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--surface-2);padding:1px 6px;border-radius:6px;unicode-bidi:isolate;word-break:break-all}
.tech{font-size:13px;color:var(--ink-2);unicode-bidi:isolate;display:inline-block;text-align:left}
.map-grid{grid-template-columns:3fr 2fr;align-items:start}
.tile rect{stroke:var(--surface);stroke-width:0}.tile:hover rect{opacity:.85}.tile-name{font:600 12px ui-monospace,Menlo,Consolas,monospace}
.tile-sub{font-size:12px}.tile-name.dark,.tile-sub.dark{fill:#2a1a10}.tile-name.light,.tile-sub.light{fill:#fff}
.heat-legend{display:flex;flex-wrap:wrap;gap:12px;margin-top:10px;font-size:13px;color:var(--ink-2)}.heat-key{display:inline-flex;gap:6px;align-items:center}
.heat-key i{width:16px;height:12px;border-radius:3px;display:inline-block}
.layers .layer{fill:var(--accent-soft)}.layer-name{font:600 13px ui-monospace,Menlo,Consolas,monospace;fill:var(--accent)}.layer-count{font-size:12px;fill:var(--ink-2)}
.diff li{margin:6px 0}.cycles{list-style:none;padding:0;display:grid;gap:8px}.cycle{display:flex;flex-wrap:wrap;gap:4px;align-items:center}
.arrow{color:var(--bad);font-weight:800}
.roadmap{list-style:none;padding:0;margin:0;position:relative}.roadmap:before{content:"";position:absolute;inset-inline-start:17px;top:8px;bottom:8px;width:2px;background:var(--line)}
.stone{display:grid;grid-template-columns:36px 1fr;gap:14px;margin-bottom:14px;position:relative}
.dot{width:36px;height:36px;border-radius:50%;display:grid;place-items:center;background:var(--surface);border:2px solid var(--line);font-weight:800;color:var(--ink-2);z-index:1}
.stone.done .dot{background:var(--good);border-color:var(--good);color:#fff}.stone.active .dot{border-color:var(--accent);color:var(--accent)}
.stone h4 .lit{font-size:12px;margin-inline-start:6px}
.progress{height:10px;background:var(--surface-2);border-radius:999px;overflow:hidden;margin-top:8px}.progress span{display:block;height:100%;background:var(--good);border-radius:999px}
.decision .count{font-size:13px;color:var(--muted);font-weight:500}.answers{margin:4px 0;padding-inline-start:20px;font-size:14px}.ids{display:flex;flex-wrap:wrap;gap:4px}
.options{font-size:14px}.fails{font-size:14px}.na{color:var(--muted)}
footer{padding-top:10px;padding-bottom:40px}
@media (max-width:760px){.hero{grid-template-columns:1fr}.map-grid{grid-template-columns:1fr}.nowto{grid-template-columns:1fr}.top-in{flex-direction:column;align-items:flex-start}.filters{position:static}}
@media print{body{background:#fff;font-size:12px}.top{position:static;backdrop-filter:none}.tabs,.actions,.filters,.more{display:none!important}
.js section.report{display:block!important;break-before:page}.js section.report:first-of-type{break-before:auto}
.card,.group{box-shadow:none;break-inside:avoid}}
"""

JS = r"""
(function(){var d=document.documentElement;d.classList.add('js');
function setLang(l){d.setAttribute('data-lang',l);d.lang=l;d.dir=l==='ar'?'rtl':'ltr';try{localStorage.setItem('eaos-human-lang',l)}catch(e){}
document.querySelectorAll('[data-ph-ar]').forEach(function(e){e.placeholder=e.getAttribute('data-ph-'+l)});
document.querySelectorAll('select option').forEach(function(o){if(!o.dataset.ar){o.dataset.ar=o.textContent}});
var names={'':['كل درجات الخطورة','All severities'],critical:['حرجة','Critical'],high:['عالية','High'],medium:['متوسطة','Medium'],low:['منخفضة','Low']};
var areas={'':['كل المجالات','All areas'],security:['الأمان','Security'],structure:['البنية','Structure'],quality:['جودة الكود','Code quality'],performance:['الأداء تحت الضغط','Performance under load'],maintainability:['سهولة التطوير والاختبار','Ease of change and testing']};
var i=l==='ar'?0:1;document.querySelectorAll('#fsev option').forEach(function(o){o.textContent=names[o.value][i]});
document.querySelectorAll('#farea option').forEach(function(o){o.textContent=areas[o.value][i]});count()}
function show(id){document.querySelectorAll('section.report').forEach(function(s){s.classList.toggle('on',s.id===id)});
document.querySelectorAll('.tabs a').forEach(function(a){a.classList.toggle('on',a.dataset.tab===id)})}
var tabs=['summary','gaps','structure','plan'];function route(){var h=location.hash.slice(1);show(tabs.indexOf(h)>=0?h:'summary')}
window.addEventListener('hashchange',function(){route();window.scrollTo(0,0)});
document.querySelectorAll('.tabs a').forEach(function(a){a.addEventListener('click',function(e){e.preventDefault();history.replaceState(null,'','#'+a.dataset.tab);show(a.dataset.tab);window.scrollTo(0,0)})});
document.querySelectorAll('.rows').forEach(function(r){var n=r.children.length;if(n>5){var b=document.createElement('button');b.type='button';b.className='more';
b.innerHTML='<span class="l-ar">عرض الكل</span><span class="l-en">Show all</span>';b.onclick=function(){r.classList.toggle('all')};r.after(b)}});
function count(){var rows=document.querySelectorAll('.row'),q=(document.getElementById('q')||{}).value||'',s=(document.getElementById('fsev')||{}).value||'',
a=(document.getElementById('farea')||{}).value||'',auto=(document.getElementById('fauto')||{}).checked,n=0,active=q||s||a||auto;q=q.toLowerCase();
rows.forEach(function(r){var ok=(!q||r.dataset.search.indexOf(q)>=0)&&(!s||r.dataset.sev===s)&&(!a||r.dataset.area===a)&&(!auto||r.dataset.auto==='1');r.hidden=!ok;if(ok)n++});
document.querySelectorAll('.rows').forEach(function(r){r.classList.toggle('all',!!active);var g=r.closest('.group');if(g)g.hidden=active&&!r.querySelector('.row:not([hidden])')});
document.querySelectorAll('[data-area-block]').forEach(function(h){h.hidden=!!a&&h.dataset.areaBlock!==a});
var out=document.getElementById('shown');if(out){out.textContent=active?(d.lang==='ar'?('المعروض: '+n):('Showing: '+n)):''}}
['q','fsev','farea','fauto'].forEach(function(id){var e=document.getElementById(id);if(e){e.addEventListener('input',count);e.addEventListener('change',count)}});
var saved=null;try{saved=localStorage.getItem('eaos-human-lang')}catch(e){}setLang(saved||d.getAttribute('data-lang')||'ar');
document.getElementById('lang').onclick=function(){setLang(d.getAttribute('data-lang')==='ar'?'en':'ar')};
document.getElementById('print').onclick=function(){window.print()};
window.addEventListener('beforeprint',function(){document.querySelectorAll('section.report').forEach(function(s){s.classList.add('on')})});
window.addEventListener('afterprint',route);route();window.scrollTo(0,0)})();
"""
