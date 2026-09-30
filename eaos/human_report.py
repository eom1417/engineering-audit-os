"""human/index.html: the report for a person, in one self-contained page, Arabic and English.

The report's other files are written for AI agents and stay exactly as they are. This page reads the same
records (plan.json, dossier.json, debt-register.json, target-architecture.json, gap-matrix.json,
run-manifest.json, and the graph, flow and structure facts) and shows six reports on one page: the project
summary, the gaps and risks, the structure map (today's parts, their imports, files, functions and pages;
eaos/arch_map.py), the system map (every page, API, server handler, part and table; eaos/system_map.py),
the target structure with the gap each part has closed, and the plan with its progress, the work log
(progress['handover'], eaos/handover.py brief) and every task card. progress['eaos'] stamps the page with the
EAOS that built it; progress['report_errors'] and every part that failed show in a warning at the top. No external asset, no network: inline CSS, inline SVG, a little inline JS. Every
number on the page carries its meaning in words next to it.

Progress comes from the ledger when the caller passes one (progress={'waves': [...], 'ledger': L}): a card
is closed when it is 'done' (an EAOS fix merged into the person's main branch) or 'resolved' (a later check
no longer finds it); 'on_branch' waits for the person and is not closed. With no ledger, a card a batch
kept counts as done, as before.

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

SECTIONS = ('summary', 'gaps', 'structure', 'system', 'target', 'plan')
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
    'structure': ('خريطة البنية', 'Structure map'), 'system': ('خريطة النظام', 'System map'), 'target': ('البنية المستهدفة', 'Target'), 'plan': ('الخطة والتقدم', 'Plan and progress'),
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
    target = _load(report / 'target-architecture.json', {}) or {}
    return {'rows': rows, 'statuses': statuses, 'coverage': coverage,
            'score': score(rows, coverage.get('source_files'), statuses, known), 'plan': plan, 'target': target,
            'gap_matrix': _load(report / 'gap-matrix.json', {}) or {}, 'manifest': _load(report / 'run-manifest.json', {}) or {},
            'dossier': dossier, 'progress': progress or {}, **maps(report, target)}


def maps(report, target):
    """The architecture maps (eaos/arch_map.py) and the system map (eaos/system_map.py); a missing or broken fact
    record leaves its map None, and what failed is kept in map_errors for the page's warning and errors.json."""
    from . import arch_map, system_map
    out = {'cmap': None, 'drill': None, 'flows': None, 'system': None, 'system_layout': None, 'map_errors': []}
    def attempt(part, build):
        try: build()
        except Exception as error: out['map_errors'].append({'section': part, 'error': f'{type(error).__name__}: {error}'[:300]})
    def components():
        out['cmap'] = arch_map.component_map(report, target)
        out['drill'] = arch_map.drill_data(report, out['cmap'])
    def system():
        out['system'] = system_map.build(report)
        out['system_layout'] = system_map.layout(out['system'])
    attempt('architecture map', components)
    attempt('page flows', lambda: out.update(flows=arch_map.flow_charts(report)))
    attempt('system map', system)
    return out


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
    if isinstance(m['plan'].get('tasks'), list) or ledger_of(m):
        out.append(gap_block(m, m.get('cards') or []))
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
                   f'{layer_diagram(tcomps, True)}{layer_diagram(tcomps, False)}'
                   f'<p class="small"><a href="#target" data-go="target">{T("البنية المستهدفة كاملة وتقدّم كل جزء ←", "The full target structure and each part’s progress →")}</a></p></div>')
    else:
        out.append(f'<div class="card"><h4>{T("البنية المستهدفة", "The target structure")}</h4>{unavailable("target")}</div>')
    out.append('</div>')
    out.append(architecture_map(m))
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
    _, failed = waves_state(progress)
    cards = m.get('cards') or []
    t = gap_totals(m, cards)
    out = [work_log(progress), f'<div class="grid three"><div class="card stat good-bg"><div class="stat-n">{num(t["closed"], "problems fixed and merged, or no longer found, so far")}</div><p>{T("مشاكل أُغلقت حتى الآن: أُصلحت ودُمجت أو لم تعد موجودة", "problems closed so far: fixed and merged, or no longer found")}</p></div>'
           f'<div class="card stat"><div class="stat-n">{num(t["total"] - t["closed"], "problems left")}</div><p>{T("مشاكل باقية", "problems left")}</p></div>'
           f'<div class="card stat"><div class="stat-n">{num(t["on_branch"], "fixes on a branch waiting for your decision")}</div><p>{T("إصلاحات على فرع تنتظر قرارك، لا تُحسب حتى تُدمج", "fixes on a branch waiting for your decision; not counted until merged")}</p></div>'
           f'<div class="card stat warn-bg"><div class="stat-n">{num(len(failed), "fixes that were tried and did not pass")}</div><p>{T("إصلاحات جُرّبت ولم تنجح", "fixes tried that did not pass")}</p></div></div>']
    milestones = plan.get('milestones') or []
    if not milestones:
        out.append(f'<h3>{T("المراحل", "Milestones")}</h3>{unavailable("milestones")}')
    else:
        steps = []
        for index, stone in enumerate(milestones, 1):
            mine = [c for c in cards if c['milestone'] == stone.get('id')]
            tasks = mine or list(stone.get('tasks') or [])
            finished = sum(c['state'] in CLOSED for c in mine)
            share = round(100 * finished / len(tasks)) if tasks else 0
            label = milestone_label(stone)
            ready = sum(by_id[t]['auto'] for t in stone.get('tasks') or [] if t in by_id)
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
    out.append(cards_block(card_groups(m, cards)))
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


# ---------------------------------------------------------------- progress: the ledger and every task card

CLOSED = ('done', 'resolved')
CARD_STATE = {  # state: (Arabic, English, chip colour); 'on_branch' is delivered, not merged, so it is not closed
    'done': ('أُصلحت ودُمجت ✓', 'Done ✓ merged', 'good'), 'resolved': ('أُغلقت: لم تعد موجودة', 'Closed by a recheck', 'good'),
    'on_branch': ('على فرع ينتظر قرارك', 'Waiting on a branch', 'warn'), 'in_batch': ('في الدفعة الحالية', 'In the current batch', 'accent'),
    'open': ('مفتوحة', 'Open', 'plain'), 'skipped': ('تحتاج قرارًا', 'Needs a decision', 'bad')}
STATE_ORDER = ('open', 'in_batch', 'on_branch', 'skipped', 'done', 'resolved')
EVENT = {'baseline': ('الفحص الأول', 'first check'), 'merged': ('دُمجت دفعة', 'a batch merged'),
         'recheck': ('إعادة فحص', 'a recheck'), 'delivered': ('سُلّمت دفعة على فرع', 'a batch delivered on a branch')}


def ledger_of(m):
    ledger = (m.get('progress') or {}).get('ledger')
    return ledger if isinstance(ledger, dict) and isinstance(ledger.get('cards'), list) else None


def waves_state(progress):
    kept, failed = set(), {}
    for wave in (progress or {}).get('waves') or []:
        kept |= set(wave.get('kept') or [])
        failed.update(wave.get('failed') or {})
    return kept, failed


def task_cards(m):
    """Every card: the plan's rows with their ledger state, then the ledger's cards the plan no longer has (fixed ones).
    With no ledger, a card kept by a batch is done and one that failed needs a decision, as before the ledger."""
    stones = {t: s.get('id') for s in m['plan'].get('milestones') or [] if isinstance(s, dict) for t in s.get('tasks') or []}
    ledger = ledger_of(m)
    kept, failed = waves_state(m['progress'])
    mine = {c.get('id'): c for c in (ledger or {}).get('cards') or [] if isinstance(c, dict) and c.get('id')}
    out, seen = [], set()
    for r in m['rows']:
        c = mine.get(r['id']) or {}
        state = c.get('state') if ledger else 'done' if r['id'] in kept else 'skipped' if r['id'] in failed else 'open'
        seen.add(r['id'])
        out.append({'id': r['id'], 'key': c.get('key') or r['id'], 'title': r['title'], 'pattern': r['pattern'], 'severity': r['severity'],
                    'milestone': c.get('milestone') or stones.get(r['id']), 'paths': r['paths'], 'before': r['before'], 'after': r['after'] or r['change'],
                    'state': state if state in CARD_STATE else 'open', 'new': bool(c.get('new')), 'batch': c.get('batch'), 'at': c.get('at'),
                    'why': c.get('why') or ('' if ledger else failed.get(r['id'], '')), 'commit': c.get('commit')})
    for c in (ledger or {}).get('cards') or []:
        if not isinstance(c, dict) or (c.get('id') and c['id'] in seen): continue
        pattern = c.get('pattern') or 'generic'
        out.append({'id': c.get('id') or '', 'key': c.get('key') or '', 'title': c.get('title') or '', 'pattern': pattern,
                    'severity': PATTERNS.get(pattern, PATTERNS['generic'])[1], 'milestone': c.get('milestone'), 'paths': c.get('paths') or [],
                    'before': '', 'after': '', 'state': c.get('state') if c.get('state') in CARD_STATE else 'open', 'new': bool(c.get('new')),
                    'batch': c.get('batch'), 'at': c.get('at'), 'why': c.get('why') or '', 'commit': c.get('commit')})
    return out


def gap_totals(m, cards):
    """The ledger's totals when it has them, else counted from the cards; percent is closed / total."""
    counts = {s: sum(c['state'] == s for c in cards) for s in CARD_STATE}
    t = {'total': len(cards), 'closed': counts['done'] + counts['resolved'], 'new': sum(c['new'] for c in cards), **counts}
    given = (ledger_of(m) or {}).get('totals')
    if isinstance(given, dict):
        t.update({k: v for k, v in given.items() if isinstance(v, (int, float)) and not isinstance(v, bool)})
    t['percent'] = float(t['percent']) if 'percent' in (given or {}) else (100 * t['closed'] / t['total'] if t['total'] else 0.0)
    return t


def pct(value):
    """A share in words a person reads: whole percents, one decimal under ten, and "<1%" rather than 0.4%."""
    value = float(value or 0)
    if value <= 0: return '0%'
    if value < 1: return '<1%'
    return f'{value:.1f}%'.replace('.0%', '%') if value < 10 else f'{round(value)}%'


def bar(share, cls=''):
    share = max(0, min(100, round(share or 0)))
    return (f'<div class="progress {cls}" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{share}">'
            f'<span style="width:{share}%"></span></div>')


def state_chip(state, words=CARD_STATE):
    ar, en, tone = words[state]
    return f'<span class="chip st st-{tone}" data-state="{state}">{T(esc(ar), esc(en))}</span>'


def gap_block(m, cards, chart=True):
    """How much of the gap is closed: only what is merged into the person's branch, or no longer found, counts."""
    t, ledger = gap_totals(m, cards), ledger_of(m)
    head = f'<h3 id="gap-closed">{T("كم أُغلق من الفجوة", "How much of the gap is closed")}</h3>'
    if not t['total']:
        return head + f'<div class="card">{T("لا مشاكل مفتوحة في الخطة: لا فجوة لإغلاقها.", "The plan has no problem to close: there is no gap.", "p")}</div>'
    share = num(pct(t['percent']), 'share of the problems found that are closed: fixed and merged, or no longer found')
    closed, total = num(t['closed'], 'problems closed'), num(t['total'], 'problems in the plan, fixed ones included')
    parts = [(k, v) for k, v in (('done', t['done']), ('resolved', t['resolved']), ('on_branch', t['on_branch']),
                                 ('in_batch', t['in_batch']), ('skipped', t['skipped']), ('open', t['open'])) if v]
    meanings = {'done': 'problems fixed by EAOS and merged into your main branch', 'resolved': 'problems a later check no longer found',
                'on_branch': 'problems fixed on a branch that waits for your decision; not counted until merged',
                'in_batch': 'problems in the batch being fixed now', 'skipped': 'problems set aside that need your decision',
                'open': 'problems not started yet'}
    tally = ''.join(f'<li>{state_chip(k)} {num(v, meanings[k])}</li>' for k, v in parts)
    if t.get('new'):
        tally += f'<li><span class="chip st st-accent">{T("جديدة", "New")}</span> {num(t["new"], "problems a later check found for the first time")}</li>'
    branch = num(t['on_branch'], meanings['on_branch'])
    waiting = (f'<p class="small">{T(f"على فرع ينتظر قرارك: {branch}. لا تُحسب مغلقة حتى تدمجها.", f"Waiting on a branch for your decision: {branch}. They count as closed only once you merge them.")}</p>'
               if t['on_branch'] else '')
    updated = str((ledger or {}).get('updated') or '')[:10]
    when = (f'<p class="muted small">{T("آخر تحديث:", "Last updated:")} {num(updated, "the date the progress was last updated")}</p>' if updated else '')
    marker = ' data-part="progress-history"' if chart else ''
    body = (f'<div class="card gap-card"{marker}><div class="gap-head"><div class="gap-n">{share}</div><div>'
            f'<p class="lead">{T(f"من الفجوة أُغلق: {closed} من {total} مشكلة أُصلحت ودُمجت في فرعك الرئيسي، أو لم تعد موجودة.", f"of the gap is closed: {closed} of {total} problems are fixed and merged into your main branch, or no longer found.")}</p>'
            f'{bar(t["percent"], "big")}</div></div><ul class="tally">{tally}</ul>{waiting}{when}')
    if chart:
        body += history_block((ledger or {}).get('history') or [])
    return head + body + '</div>'


def history_block(history):
    points = [h for h in history if isinstance(h, dict) and h.get('at') and isinstance(h.get('percent'), (int, float))]
    title = f'<h4>{T("التقدم عبر الوقت", "Progress over time")}</h4>'
    if not points:
        return title + T('يظهر الخط هنا بعد أول دفعة تُدمج أو أول إعادة فحص.', 'The line shows here after the first merged batch or the first recheck.', 'p', 'muted small')
    rows = ''.join(f'<tr><td>{num(str(h["at"])[:10], "date of this event")}</td><td>{T(*map(esc, EVENT.get(h.get("event"), (h.get("event") or "", h.get("event") or ""))))}</td>'
                   f'<td>{num(h.get("closed", 0), "problems closed by then")}</td><td>{num(h.get("total", 0), "problems in the plan then")}</td>'
                   f'<td>{num(pct(h["percent"]), "share of the gap closed by then")}</td></tr>' for h in points)
    table = (f'<details><summary>{T("عرض كجدول", "Show as a table")}</summary><table class="tbl"><thead><tr><th>{T("التاريخ", "Date")}</th>'
             f'<th>{T("ما حدث", "What happened")}</th><th>{T("المغلق", "Closed")}</th><th>{T("المجموع", "Total")}</th><th>{T("النسبة", "Share")}</th></tr></thead>'
             f'<tbody>{rows}</tbody></table></details>')
    return title + history_chart(points) + table


def history_chart(points):
    """A step line of the share closed over time: it holds its value until the next event. One colour, labelled axes."""
    from datetime import datetime
    width, height, left, right, top, bottom = 760, 230, 52, 70, 16, 34
    def when(h):
        try: return datetime.fromisoformat(str(h['at']).replace('Z', '+00:00')).timestamp()
        except ValueError: return None
    times = [when(h) for h in points]
    if None in times or max(times) == min(times): times = list(range(len(points)))
    top_value = max(h['percent'] for h in points)
    scale = next((s for s in (5, 10, 20, 25, 50, 100) if s >= top_value * 1.1), 100)
    span = (max(times) - min(times)) or 1
    X = lambda t: left + (width - left - right) * ((t - min(times)) / span if len(points) > 1 else 0.5)
    Y = lambda v: top + (height - top - bottom) * (1 - min(v, scale) / scale)
    out = [f'<svg viewBox="0 0 {width} {height}" direction="ltr" role="img" class="chart history" '
           f'aria-label="{esc("share of the gap closed over time")}">']
    for tick in (0, scale / 2, scale):
        label = f'{tick:g}%'
        out.append(f'<line x1="{left}" x2="{width - right}" y1="{Y(tick):.1f}" y2="{Y(tick):.1f}" class="grid"/>'
                   f'<text x="{left - 8}" y="{Y(tick) + 4:.1f}" text-anchor="end" class="tick" data-meaning="share of the gap closed">{label}</text>')
    marks = sorted({0, len(points) - 1, (len(points) - 1) // 2})
    for i in marks:
        out.append(f'<text x="{X(times[i]):.1f}" y="{height - 10}" text-anchor="middle" class="tick" data-meaning="date of this event">{esc(str(points[i]["at"])[:10])}</text>')
    path = f'M{X(times[0]):.1f},{Y(points[0]["percent"]):.1f}'
    for t, h in zip(times[1:], points[1:]):
        path += f' H{X(t):.1f} V{Y(h["percent"]):.1f}'
    area = path + f' V{Y(0):.1f} H{X(times[0]):.1f} Z'
    out.append(f'<path d="{area}" class="area"/><path d="{path}" class="line"/>')
    for t, h in zip(times, points):
        words = f'{str(h["at"])[:10]}: {pct(h["percent"])} ({EVENT.get(h.get("event"), ("", h.get("event") or ""))[1]})'
        out.append(f'<circle cx="{X(t):.1f}" cy="{Y(h["percent"]):.1f}" r="4.5" class="dot-pt" data-meaning="share of the gap closed on this date">'
                   f'<title>{esc(words)}</title></circle>')
    last = points[-1]
    out.append(f'<text x="{X(times[-1]) + 10:.1f}" y="{Y(last["percent"]) + 4:.1f}" class="end-label" data-meaning="share of the gap closed now">{esc(pct(last["percent"]))}</text>')
    return ''.join(out) + '</svg>'


def card_item(c, words=CARD_STATE, extra=''):
    """One task card, collapsed: its state and title; open, what it is, where, now and should-be, and when."""
    new = f' <span class="chip st st-accent">{T("جديدة", "New")}</span>' if c.get('new') else ''
    where = ' '.join(lit(p) for p in c['paths'][:6])
    if len(c['paths']) > 6: where += ' ' + T(f'و{num(len(c["paths"]) - 6, "more files")} ملفات أخرى', f'and {num(len(c["paths"]) - 6, "more files")} more files')
    lines = []
    if c.get('pattern') in plain.TEXT:
        (tar, why_ar), (ten, why_en) = plain.problem(c['pattern'], 'ar'), plain.problem(c['pattern'], 'en')
        lines.append(f'<p><b>{T(esc(tar), esc(ten))}</b>: {T(esc(why_ar), esc(why_en))}</p>')
    if where: lines.append(f'<div class="where">{T("أين:", "Where:", cls="lbl")} {where}</div>')
    if c.get('before') or c.get('after'):
        lines.append(f'<div class="nowto"><div><b>{T("الآن", "Now")}</b> {said(c["before"] or c["title"])}</div>'
                     f'<div><b>{T("المطلوب", "Should be")}</b> {said(c["after"]) or T("لم يُحدَّد بعد؛ يقرره شخص.", "Not stated yet; a person decides.")}</div></div>')
    lines.append(extra + (c.get('extra') or ''))
    when = []
    if c.get('batch') is not None: when.append(T(f'الدفعة {num(c["batch"], "batch number")}', f'batch {num(c["batch"], "batch number")}'))
    if c.get('at'): when.append(T(f'بتاريخ {num(str(c["at"])[:10], "the date its state last changed")}', f'on {num(str(c["at"])[:10], "the date its state last changed")}'))
    if c.get('commit'): when.append(T('في الإيداع', 'in commit') + ' ' + lit(str(c['commit'])[:12]))
    if when: lines.append(f'<p class="muted small">{" · ".join(when)}</p>')
    if c.get('why'): lines.append(f'<p class="small">{T("السبب:", "Why:", cls="lbl")} {said(c["why"])}</p>')
    search = ' '.join([c.get('id') or '', c.get('title') or '', c.get('pattern') or '', *c['paths']]).lower()
    return (f'<details class="tcard" data-state="{c["state"]}" data-new="{int(bool(c.get("new")))}" data-search="{esc(search)}">'
            f'<summary>{state_chip(c["state"], words)}{new} {said(c["title"]) or lit(c.get("id") or c.get("key") or "")}'
            f'{(" " + lit(c["id"])) if c.get("id") else ""}</summary><div class="tbody">{"".join(lines)}</div></details>')


def cards_block(groups, words=CARD_STATE, total=None):
    """"All task cards": collapsed; inside, a status filter, a search, and one collapsed group per milestone."""
    count = num(total if total is not None else sum(len(cards) for _, _, cards in groups), 'all task cards')
    options = ''.join(f'<option value="{s}" data-ar="{esc(words[s][0])}" data-en="{esc(words[s][1])}">{esc(words[s][0])}</option>'
                      for s in STATE_ORDER if s in words)
    if words is CARD_STATE: options += '<option value="new" data-ar="جديدة" data-en="New">جديدة</option>'
    blocks = []
    for label, stone, cards in groups:
        if not cards: continue
        closed = sum(c['state'] in CLOSED for c in cards)
        tally = T(f'المغلق: {num(closed, "cards closed in this milestone")} من {num(len(cards), "cards in this milestone")}',
                  f'{num(closed, "cards closed in this milestone")} of {num(len(cards), "cards in this milestone")} closed')
        blocks.append(f'<details class="mgroup"><summary><span>{T(esc(label[0]), esc(label[1]))} {lit(stone) if stone else ""}</span>'
                      f'<span class="g-meta">{tally}</span></summary>{bar(100 * closed / len(cards), "thin")}'
                      f'<div class="tcards">{"".join(card_item(c, words) for c in cards)}</div></details>')
    return (f'<details class="card allcards" id="allcards" data-part="cards"><summary>{T("كل بطاقات المهام", "All task cards")} '
            f'<span class="g-meta">{T(f"البطاقات: {count}", f"{count} cards")}</span></summary>'
            f'<p class="muted small">{T("كل بطاقة مشكلة واحدة وحالتها. افتح المرحلة ثم البطاقة لترى التفاصيل.", "Each card is one problem and its state. Open a milestone, then a card, to see the details.")}</p>'
            f'<div class="filters cfilters" role="search"><select id="cstate"><option value="" data-ar="كل الحالات" data-en="All states">كل الحالات</option>{options}</select>'
            f'<input type="search" id="cq" data-ph-ar="ابحث بعنوان أو ملف أو رقم بطاقة…" data-ph-en="Search a title, a file or a card id…" placeholder="ابحث بعنوان أو ملف أو رقم بطاقة…">'
            f'<span class="muted" id="cshown" aria-live="polite"></span></div>{"".join(blocks) or unavailable("cards")}</details>')


def milestone_label(stone):
    name = stone.get('name') or ''
    label = MILESTONE.get(name)
    if not label and name.startswith('build:'): label = (f'بناء {name[6:]}', f'Build {name[6:]}')
    if not label and stone.get('name_ar'): label = (stone['name_ar'], name)
    return label or (name, name)


def card_groups(m, cards):
    stones = [s for s in m['plan'].get('milestones') or [] if isinstance(s, dict)]
    groups = [(milestone_label(s), s.get('id') or '', [c for c in cards if c['milestone'] == s.get('id')]) for s in stones]
    known = {s.get('id') for s in stones}
    rest = [c for c in cards if c['milestone'] not in known]
    if rest: groups.append((('بلا مرحلة', 'No milestone'), '', rest))
    return groups


# ---------------------------------------------------------------- architecture maps (the data and layout: eaos/arch_map.py)

INSTABILITY = {'stable': ('مستقر: كثيرون يعتمدون عليه وهو يعتمد على القليل', 'stable: many rely on it, it relies on little'),
               'balanced': ('متوازن: يعتمد ويُعتمد عليه بقدر متقارب', 'balanced: it relies on others about as much as they rely on it'),
               'unstable': ('متغيّر: يعتمد على كثير ولا يعتمد عليه إلا القليل', 'changeable: it relies on much, little relies on it'),
               'alone': ('منفصل: لا يستورد شيئًا ولا يستورده أحد', 'on its own: it imports nothing and nothing imports it')}
COHESION = {'strong': ('قوي', 'strong'), 'medium': ('متوسط', 'medium'), 'weak': ('ضعيف', 'weak')}


def files_word(n):
    return 'file' if n == 1 else 'files'


def fit(text, room):
    """A name cut from the left to fit `room` characters: the end of a path says the most."""
    text = str(text)
    return text if len(text) <= room else '…' + text[-(room - 1):]


def arrow_defs(suffix):
    head = '<path d="M0,0 L8,4 L0,8 z" class="arrow-head{}"/>'
    return ''.join(f'<marker id="{name}-{suffix}" viewBox="0 0 8 8" refX="7" refY="4" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10" orient="auto-start-reverse">'
                   f'{head.format(cls)}</marker>' for name, cls in (('arr', ''), ('arrc', ' cyc')))


def graph_svg(cmap, rtl):
    """Today's parts as boxes, left to right from what uses to what is used (mirrored in Arabic), and their imports."""
    from .arch_map import NODE_W as BW, NODE_H as BH
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
    from . import arch_map
    cmap = m.get('cmap')
    head = f'<h3 id="arch-map">{T("كيف تعتمد الأجزاء بعضها على بعض", "How the parts depend on each other")}</h3>'
    if not cmap:
        return head + unavailable('architecture map')
    loops = sum(e['cycle'] for e in cmap['edges'])
    wrong = sum(e['wrong'] for e in cmap['edges'])
    parts, links = num(len(cmap['nodes']), 'parts drawn'), num(len(cmap['edges']), 'links between parts')
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


def target_svg(rows, edges, progress, rtl, done=('أُغلق', 'closed')):
    """The target as layers of boxes; every allowed link drawn faint, strong for the part under the pointer.
    A component may bring its own second line as c['sub'] = (Arabic, English); `done` names what its bar counts."""
    per_line = (TWIDTH - TLABEL) // (TBOX_W + TBOX_GAP)
    boxes, y, parts, labels = {}, 8, [], []
    for layer, comps in rows:
        lines = [comps[i:i + per_line] for i in range(0, len(comps), per_line)] or [[]]
        band = len(lines) * (TBOX_H + TBOX_GAP) - TBOX_GAP
        labels.append(f'<rect x="0" y="{y - 4}" width="{TWIDTH}" height="{band + 8}" rx="8" class="t-band"/>'
                      + svg_text(TWIDTH - 10 if rtl else 10, y + band / 2 + 5, layer, 't-layer', 'right' if rtl else 'left', attrs=' data-literal="1"'))
        for line in lines:
            for p, c in enumerate(line):
                x = TLABEL + p * (TBOX_W + TBOX_GAP)
                boxes[c.get('name')] = ((TWIDTH - x - TBOX_W) if rtl else x, y)
            y += TBOX_H + TBOX_GAP
        y += TROW_GAP - TBOX_GAP
    height = y
    suffix = 't-ar' if rtl else 't-en'
    label = 'البنية المستهدفة طبقة طبقة' if rtl else 'The target structure, layer by layer'
    parts.append(f'<svg viewBox="0 0 {TWIDTH} {height}" direction="ltr" role="img" class="chart tgraph hl-graph {"l-ar" if rtl else "l-en"}" '
                 f'aria-label="{esc(label)}"><defs>{arrow_defs(suffix)}</defs>{"".join(labels)}<g class="edges">')
    for e in edges:
        if e.get('from') not in boxes or e.get('to') not in boxes: continue
        (ax, ay), (bx, by) = boxes[e['from']], boxes[e['to']]
        sx, ex = ax + TBOX_W / 2, bx + TBOX_W / 2
        if by > ay + 1: d = f'M{sx:.1f},{ay + TBOX_H:.1f} C{sx:.1f},{ay + TBOX_H + 40:.1f} {ex:.1f},{by - 40:.1f} {ex:.1f},{by:.1f}'
        elif by < ay - 1: d = f'M{sx:.1f},{ay:.1f} C{sx:.1f},{ay - 40:.1f} {ex:.1f},{by + TBOX_H + 40:.1f} {ex:.1f},{by + TBOX_H:.1f}'
        else: d = f'M{sx:.1f},{ay + TBOX_H:.1f} C{sx:.1f},{ay + TBOX_H + 22:.1f} {ex:.1f},{by + TBOX_H + 22:.1f} {ex:.1f},{by + TBOX_H:.1f}'
        count = e.get('imports') or 1
        words = f'{e["from"]} → {e["to"]}' + (f': {count}' if e.get('imports') else '')
        parts.append(f'<path d="{d}" class="edge t-edge" style="stroke-width:{1 + math.log2(count):.1f}" marker-end="url(#arr-{suffix})" '
                     f'data-from="{esc(e["from"])}" data-to="{esc(e["to"])}" data-meaning="{count} imports the target allows along this link">'
                     f'<title>{esc(words)}</title></path>')
    parts.append('</g>')
    for layer, comps in rows:
        for c in comps:
            name = c.get('name') or ''
            x, y0 = boxes[name]
            closed, total = progress.get(name, (0, 0))
            files = c.get('files') or 0
            side, edge = ('right', x + TBOX_W - 8) if rtl else ('left', x + 8)
            if total:
                words = f'{done[0]} {closed} من {total}' if rtl else f'{closed} of {total} {done[1]}'
            else:
                words = 'لا مشاكل فيه' if rtl else 'no problem in it'
            sub = (c['sub'][0 if rtl else 1] if c.get('sub') else f'ملفات {files}' if rtl else f'{files} {files_word(files)}')
            share = (TBOX_W - 16) * closed / total if total else 0
            meaning = f'{files} files; {closed} of the {total} problems in its files are closed'
            tip = f'{name}: {c.get("responsibility") or ""}'
            parts.append(f'<g class="t-node{" empty" if not files and not c.get("sub") else ""}" data-node="{esc(name)}" tabindex="0" data-meaning="{esc(meaning)}"><title>{esc(tip)}</title>'
                         f'<rect x="{x:.1f}" y="{y0:.1f}" width="{TBOX_W}" height="{TBOX_H}" rx="7"/>'
                         + svg_text(edge, y0 + 17, fit(name, 19), 't-name', side, attrs=' data-literal="1"')
                         + svg_text(edge, y0 + 33, sub + ' · ' + words, 't-sub', side, rtl)
                         + f'<rect x="{x + 8:.1f}" y="{y0 + TBOX_H - 16:.1f}" width="{TBOX_W - 16}" height="6" rx="3" class="t-track"/>'
                         + (f'<rect x="{(x + TBOX_W - 8 - share) if rtl else x + 8:.1f}" y="{y0 + TBOX_H - 16:.1f}" width="{share:.1f}" height="6" rx="3" class="t-fill"/>' if share else '')
                         + '</g>')
    return ''.join(parts) + '</svg>'


def target_detail(c, progress, sources):
    name = c.get('name') or ''
    closed, total = progress.get(name, (0, 0))
    share = 100 * closed / total if total else 0
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
    targets = []
    for c in sorted(current, key=lambda c: (order.index(c.get('target_component')) if c.get('target_component') in order else len(order), c.get('name') or '')):
        if c.get('target_component') and c.get('target_component') not in targets: targets.append(c['target_component'])
    left = sorted(current, key=lambda c: (targets.index(c['target_component']) if c.get('target_component') in targets else len(targets), c.get('name') or ''))
    height = max(len(left), len(targets), 1) * row + 20
    step = (height - 20) / max(len(targets), 1)
    ly = {c.get('id'): 10 + i * row + row / 2 for i, c in enumerate(left)}
    ty = {t: 10 + i * step + step / 2 for i, t in enumerate(targets)}
    a, b = (width - gap, gap) if rtl else (gap, width - gap)      # the line's two ends: today, and the target
    label = 'كل جزء اليوم ومكانه في البنية المستهدفة' if rtl else 'Each part today and its place in the target structure'
    out = [f'<svg viewBox="0 0 {width} {height}" direction="ltr" role="img" class="chart mapping {"l-ar" if rtl else "l-en"}" aria-label="{esc(label)}">']
    for c in left:
        t = c.get('target_component')
        relation = c.get('relation') or ''
        words = RELATION.get(relation, (relation, relation))[0 if rtl else 1]
        name = c.get('name') or c.get('id') or ''
        tip = f'{name} → {t or "—"}: {words}'
        name = name[len(root):] if root and name.startswith(root) and name != root else name
        y1 = ly[c.get('id')]
        out.append(f'<g class="map-row" data-literal="1"><title>{esc(tip)}</title>'
                   + svg_text(a + (10 if rtl else -10), y1 + 4, fit(name, 44), 'm-name', 'left' if rtl else 'right')
                   + (f'<path d="M{a},{y1:.1f} C{(a + b) / 2:.1f},{y1:.1f} {(a + b) / 2:.1f},{ty[t]:.1f} {b},{ty[t]:.1f}" class="m-line {RELATION_STYLE.get(relation, "r-modify")}"/>' if t in ty else '')
                   + '</g>')
    for t, y1 in ty.items():
        out.append(f'<g class="map-row" data-literal="1">' + svg_text(b + (-10 if rtl else 10), y1 + 4, fit(t, 40), 'm-target', 'right' if rtl else 'left') + '</g>')
    return ''.join(out) + '</svg>'


def section_target(m):
    target = m['target']
    tcomps = [c for c in target.get('target_components') or [] if isinstance(c, dict) and c.get('name')]
    cards = m.get('cards') or []
    out = [gap_block(m, cards, chart=False)]
    if not tcomps:
        return ''.join(out) + f'<h3>{T("البنية المستهدفة", "The target structure")}</h3>{unavailable("target")}'
    from .arch_map import target_progress
    progress = target_progress(target, cards, CLOSED)
    edges = [e for e in target.get('target_edges') or [] if isinstance(e, dict)]
    rows = target_rows(tcomps)
    current = [c for c in target.get('current_components') or [] if isinstance(c, dict)]
    sources = {}
    for c in current: sources.setdefault(c.get('target_component'), []).append(c.get('name') or c.get('id') or '')
    n_parts, n_layers, n_links = num(len(tcomps), 'parts in the target structure'), num(len(rows), 'layers in the target'), num(len(edges), 'links the target allows')
    out.append(f'<h3>{T("البنية المستهدفة: ما سيصبح عليه البرنامج", "The target structure: what the program will become")}</h3>'
               f'<div class="card graph-wrap" data-part="target-map"><p class="muted small">{T("كل صف طبقة، من الأعلى (ما يراه المستخدم) إلى الأسفل (الأساس)، وكل مربع جزء له مسؤولية واحدة. الشريط الأخضر في المربع: كم أُغلق من المشاكل في ملفاته. مرّر المؤشر أو اضغط على جزء لترى مسؤوليته وروابطه المسموحة ومن أين يأتي من البنية اليوم.", "Each row is a layer, from the top (what users see) to the bottom (the foundation); each box is a part with one job. The green bar in a box: how much of the problems in its files is closed. Hover or click a part to see its job, its allowed links and where it comes from in today’s structure.")}</p>'
               f'<p class="small">{T(f"الأجزاء: {n_parts} · الطبقات: {n_layers} · الروابط المسموحة: {n_links}", f"{n_parts} parts · {n_layers} layers · {n_links} allowed links")}</p>'
               f'<div class="graph-scroll">{target_svg(rows, edges, progress, True)}{target_svg(rows, edges, progress, False)}</div>'
               + ''.join(target_detail(c, progress, sources.get(c['name'], [])) for c in tcomps) + '</div>')
    if current:
        order = [c['name'] for _, comps in rows for c in comps]
        keys = ''.join(f'<span class="heat-key"><svg width="46" height="12" aria-hidden="true" class="key-line"><path d="M2,6 H44" class="m-line {RELATION_STYLE[r]}"/></svg>'
                       f'{T(*map(esc, RELATION[r]))}</span>' for r in ('retain', 'modify', 'rebuild', 'delete') if any(c.get('relation') == r for c in current))
        out.append(f'<h3>{T("من اليوم إلى المستهدف", "From today to the target")}</h3><div class="card" data-part="target-mapping"><p class="muted small">'
                   f'{T("على جانب أجزاء البرنامج اليوم، وعلى الآخر مكان كل منها في البنية المستهدفة. شكل الخط يقول ماذا يحدث للجزء.", "On one side the parts of the program today, on the other where each goes in the target structure. The style of the line says what happens to the part.")}</p>'
                   f'<div class="heat-legend">{keys}</div><div class="graph-scroll">{mapping_svg(current, order, True, target.get("root") or "")}{mapping_svg(current, order, False, target.get("root") or "")}</div></div>')
    table = ''.join(
        f'<tr><td>{lit(c["name"])}</td><td>{lit(c.get("layer") or "")}</td><td>{num(c.get("files") or 0, "files in this target part")}</td>'
        f'<td>{" ".join(lit(s) for s in sources.get(c["name"], [])) or T("جديد", "new")}</td>'
        f'<td>{num(progress.get(c["name"], (0, 0))[0], "problems closed here")} / {num(progress.get(c["name"], (0, 0))[1], "problems in this part")}'
        f'{bar(100 * progress[c["name"]][0] / progress[c["name"]][1], "thin") if progress.get(c["name"], (0, 0))[1] else ""}</td></tr>'
        for _, comps in rows for c in comps)
    out.append(f'<h3>{T("إغلاق الفجوة في كل جزء مستهدف", "The gap closed in each target part")}</h3><div class="card scroll"><p class="muted small">'
               f'{T("تُحسب المشكلة في كل جزء مستهدف تذهب إليه أحد ملفاتها. المغلق: ما أُصلح ودُمج أو لم يعد موجودًا.", "A problem counts in every target part one of its files goes to. Closed: fixed and merged, or no longer found.")}</p>'
               f'<table class="tbl"><thead><tr><th>{T("الجزء المستهدف", "Target part")}</th><th>{T("الطبقة", "Layer")}</th><th>{T("الملفات", "Files")}</th>'
               f'<th>{T("يأتي من اليوم", "Comes from today’s")}</th><th>{T("المغلق من المشاكل", "Problems closed")}</th></tr></thead><tbody>{table}</tbody></table></div>')
    return ''.join(out)


# ---------------------------------------------------------------- the system map (the data and layout: eaos/system_map.py)

SM_HEADS = (('الصفحات', 'Pages'), ('نقاط API', 'APIs'), ('ما يجيبها في الخادم', 'Server handlers'),
            ('الأجزاء التي يستخدمها', 'Parts it uses'), ('الجداول والخدمات', 'Tables and services'))
METHOD_CLASS = {'GET': 'get', 'POST': 'post', 'PUT': 'put', 'PATCH': 'put', 'DELETE': 'del'}


def system_svg(sm, lay, rtl):
    """Five columns, right to left in Arabic: pages, APIs grouped by resource, the server files that answer them, the
    parts those use, and the tables and services reached. Every link is drawn faint; the JS lights one chain."""
    from .system_map import COLUMNS, BOX_H, PAD, WIDTH
    place, height = lay['place'], lay['height']
    X = lambda c: (WIDTH - COLUMNS[c][0] - COLUMNS[c][1]) if rtl else COLUMNS[c][0]
    mid = lambda i: place[i][1] + BOX_H / 2
    label = 'خريطة النظام: الصفحات ونقاط API والخادم والبيانات' if rtl else 'The system map: pages, APIs, server and data'
    out = [f'<svg viewBox="0 0 {WIDTH} {height}" direction="ltr" role="img" class="chart smap {"l-ar" if rtl else "l-en"}" aria-label="{esc(label)}">']
    for band in lay['bands']:
        x = X(1)
        out.append(f'<rect x="{x - 4}" y="{band["top"] - 2}" width="{COLUMNS[1][1] + 8}" height="{band["bottom"] - band["top"]:.0f}" rx="7" class="sm-band"/>'
                   + svg_text(x + COLUMNS[1][1] - 4 if rtl else x + 4, band['top'] + 11, band['label'], 'sm-band-l', 'right' if rtl else 'left', attrs=' data-literal="1"'))
    if lay.get('callers_top'):
        x = X(0)
        words = 'كود مشترك يستدعي الخادم' if rtl else 'Shared code that calls the server'
        out.append(svg_text(x + COLUMNS[0][1] if rtl else x, lay['callers_top'] + 12, words, 'sm-sub-head', 'right' if rtl else 'left', rtl))
    out.append('<g class="sm-edges">')
    for e in sm['edges']:
        if e['from'] not in place or e['to'] not in place: continue
        (ca, _), (cb, _) = place[e['from']], place[e['to']]
        ya, yb = mid(e['from']), mid(e['to'])
        if ca == cb:                                    # a page and the shared code it reaches: an arc on the outer side
            ox = X(0) + COLUMNS[0][1] if rtl else X(0)
            bulge = (10 + min(26, abs(yb - ya) / 18)) * (1 if rtl else -1)
            d = f'M{ox:.0f},{ya:.1f} C{ox + bulge:.1f},{ya:.1f} {ox + bulge:.1f},{yb:.1f} {ox:.0f},{yb:.1f}'
        else:
            sx, ex = (X(ca), X(cb) + COLUMNS[cb][1]) if rtl else (X(ca) + COLUMNS[ca][1], X(cb))
            bend = (ex - sx) / 2
            d = f'M{sx:.0f},{ya:.1f} C{sx + bend:.1f},{ya:.1f} {ex - bend:.1f},{yb:.1f} {ex:.0f},{yb:.1f}'
        width = 1 + math.log2(e["n"]) if e["n"] > 1 and e["kind"] != "use" else 1
        out.append(f'<path d="{d}" class="sm-edge k-{e["kind"]}" style="stroke-width:{width:.1f}" data-from="{esc(e["from"])}" data-to="{esc(e["to"])}"/>')
    out.append('</g>')
    room = lambda c: int((COLUMNS[c][1] - 14) / 6.5)
    def node(i, c, first, second='', cls='', tip='', search='', tag='', words=False):
        x, y = X(c), place[i][1]
        tx, anchor = (x + COLUMNS[c][1] - 7, 'start' if words else 'end') if rtl else (x + 7, 'start')
        space = room(c) - len(tag) - (1 if tag else 0)
        first = (first if len(first) <= space else first[:space - 1] + '…') if words else fit(first, max(space, 8))
        room2 = space - len(first) - 1
        second = (second if len(second) <= room2 else second[:room2 - 1] + '…') if second and room2 > 4 else ''
        spans = (f'<tspan class="sm-tag t-{METHOD_CLASS.get(tag, "any")}">{esc(tag)} </tspan>' if tag else '') + f'<tspan class="sm-l">{esc(first)}</tspan>' + (f'<tspan class="sm-s"> {esc(second)}</tspan>' if second else '')
        return (f'<g class="sm-node {cls}" data-node="{esc(i)}" data-search="{esc(search.lower())}" tabindex="0"><title data-literal="1">{esc(tip or first)}</title>'
                f'<rect x="{x}" y="{y:.1f}" width="{COLUMNS[c][1]}" height="{BOX_H}" rx="5"/>'
                f'<text x="{tx}" y="{y + 13:.1f}" text-anchor="{anchor}" direction="{"rtl" if words and rtl else "ltr"}" data-literal="1">{spans}</text></g>')
    for p in sm['pages']:
        tip = f'{p["route"]} → {p["component"]} ({p["file"]})'
        out.append(node(p['id'], 0, p['route'], p['component'], 'n-page' + ('' if p['traced'] else ' untraced'), tip, f'{p["route"]} {p["component"]} {p["file"]}'))
    for c in sm['callers']:
        out.append(node(c['id'], 0, c['short'], '', 'n-caller', c['path'], c['path']))
    for a in sm['apis']:
        cls = 'n-api' + ('' if a['handlers'] else ' unknown') + ('' if a['exact'] or not a['handlers'] else ' guessed')
        out.append(node(a['id'], 1, a['path'], '', cls, a['key'], a['key'] + ' ' + ' '.join(a['features']), a['method']))
    for h in sm['handlers']:
        name = h['short']
        out.append(node(h['id'], 2, name, '', 'n-handler' + ('' if h['apis'] else ' idle'), h['path'], h['path']))
    for mo in sm['modules']:
        out.append(node(mo['id'], 3, mo['short'], '', 'n-module', mo['name'], mo['name']))
    for d in sm['data']:
        table = d['id'].startswith('T:')
        text = d['name'] if table or not rtl else d.get('ar') or d['name']
        out.append(node(d['id'], 4, text, '', 'n-table' if table else 'n-service', d['name'] + (' — ' + ', '.join(d.get('files') or []) if table else ''),
                        d['name'] + ' ' + (d.get('ar') or ''), words=not table))
    return ''.join(out) + '</svg>'


def api_table(sm):
    """Every API, collapsed: its method and path, who calls it, the server file that answers it, what it reaches."""
    pages = {p['id']: p for p in sm['pages']}
    short = {h['path']: h['short'] for h in sm['handlers']}
    def some(items, meaning, limit=5):
        shown = ' '.join(lit(i) for i in items[:limit])
        more = len(items) - limit
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
            f'<span class="g-meta">{T(f"النقاط: {num(len(sm["apis"]), "APIs in the table")}", f"{num(len(sm["apis"]), "APIs in the table")} APIs")}</span></summary>'
            f'<div class="scroll"><table class="tbl sm-table"><thead><tr><th>{T("الطريقة", "Method")}</th><th>{T("المسار", "Path")}</th>'
            f'<th>{T("من يستدعيها (صفحات، ثم ملفات)", "Called from (pages, then files)")}</th><th>{T("ما يجيبها في الخادم", "Server handler")}</th>'
            f'<th>{T("الجداول والخدمات", "Tables and services")}</th><th>{T("الميزة", "Feature")}</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></details>')


def section_system(m):
    """The whole system in one drawing, with a search, a feature filter, what a click reaches, and every API as a table."""
    sm, lay = m.get('system'), m.get('system_layout')
    if not sm or not lay:
        if (m.get('coverage') or {}).get('source_files') and not any(e.get('section') == 'system map' for e in m.get('map_errors') or []):
            return (f'<div class="card" data-part="system-map"><h3>{T("كل الروابط: من الصفحة إلى البيانات", "Every link: from the page to the data")}</h3>'
                    + T('لم نجد في هذا المشروع صفحات ويب ولا نقاط API يستدعيها أحد: هو مكتبة أو أداة أوامر أو خدمة بلا واجهة. '
                        'أجزاؤه والعلاقات بينها، وملفاته ودواله، مرسومة في «خريطة البنية».',
                        'This project has no web pages and no API that anything calls: it is a library, a command-line tool or a '
                        'service without a front end. Its parts and the links between them, its files and functions, are drawn in '
                        'the "Structure map".', 'p') + '</div>')
        return unavailable('system map')
    from .system_map import COLUMNS, WIDTH
    from .arch_map import json_script
    answered = sum(1 for a in sm['apis'] if a['handlers'])
    tables = sum(1 for d in sm['data'] if d['id'].startswith('T:'))
    n = lambda v, meaning: num(v, meaning)
    summary = T(f'الصفحات: {n(len(sm["pages"]), "pages")} · نقاط API: {n(len(sm["apis"]), "APIs")} · وجدنا في الخادم ما يجيب {n(answered, "APIs with a server handler found")} منها · '
                f'ملفات الخادم: {n(len(sm["handlers"]), "server files that answer requests")} · الجداول: {n(tables, "tables")} · الخدمات: {n(len(sm["data"]) - tables, "services and storage")}',
                f'{n(len(sm["pages"]), "pages")} pages · {n(len(sm["apis"]), "APIs")} APIs · a server handler found for {n(answered, "APIs with a server handler found")} of them · '
                f'{n(len(sm["handlers"]), "server files that answer requests")} server files · {n(tables, "tables")} tables · {n(len(sm["data"]) - tables, "services and storage")} services')
    notes = []
    if sm['unknown']:
        notes.append(T(f'لم نجد في الخادم ما يجيب {n(sm["unknown"], "APIs whose handler is unknown")} من نقاط API: قد يأتي جوابها من خادم آخر أو من مسار يُبنى وقت التشغيل. تظهر منقّطة.',
                       f'For {n(sm["unknown"], "APIs whose handler is unknown")} APIs no server code was found that answers them: the answer may come from another server, or from a route built at run time. They are drawn dotted.'))
    if sm['guessed']:
        notes.append(T(f'{n(sm["guessed"], "APIs matched by file name only")} منها رُبطت بملف من اسمه فقط؛ تحقق منها.', f'{n(sm["guessed"], "APIs matched by file name only")} of them are matched to a file by its name only; check them.'))
    untraced = sum(1 for p in sm['pages'] if not p['traced'])
    if untraced:
        notes.append(T(f'{n(untraced, "pages whose component file was not found")} صفحة لم نجد ملف مكوّنها، فلم نتتبع ما تستدعيه (تظهر باهتة).',
                       f'{n(untraced, "pages whose component file was not found")} pages: their component file was not found, so what they call is not traced (drawn faded).'))
    capped = {k: v for k, v in (sm.get('capped') or {}).items() if v}
    words = {'pages': ('صفحة', 'pages'), 'callers': ('ملفًا مشتركًا', 'shared files'), 'apis': ('نقطة API', 'APIs'),
             'handlers': ('ملف خادم', 'server files'), 'modules': ('جزءًا', 'parts'), 'data': ('جدولًا أو خدمة', 'tables or services')}
    if capped:
        ar = '، '.join(f'{n(v, "items left out of the drawing")} {words[k][0]}' for k, v in capped.items())
        en = ', '.join(f'{n(v, "items left out of the drawing")} {words[k][1]}' for k, v in capped.items())
        notes.append(T(f'الرسم محدود الحجم ليبقى مقروءًا؛ لم يُرسم: {ar}.', f'The drawing is capped to stay readable; left out: {en}.'))
    notes.append(T('الجداول: المعرّفة في ملفات البيانات التي يستخدمها كود الخادم؛ لا نفرّق هنا بين القراءة والكتابة.',
                   'Tables: those defined in the data files the server code uses; reading and writing are not told apart here.'))
    features = ''.join(f'<option value="{esc(f["name"])}" data-literal="1">{esc(f["name"])}</option>' for f in sm['features'])
    controls = (f'<div class="filters sm-tools" role="search"><input type="search" id="smq" data-ph-ar="ابحث عن صفحة أو API أو ملف أو جدول…" '
                f'data-ph-en="Search a page, an API, a file or a table…" placeholder="ابحث عن صفحة أو API أو ملف أو جدول…">'
                + (f'<select id="smf"><option value="" data-ar="كل الميزات" data-en="All features">كل الميزات</option>{features}</select>' if features else '')
                + f'<button type="button" class="btn ghost" id="smclear">{T("إظهار الكل", "Show all")}</button>'
                f'<span class="muted" id="smshown" aria-live="polite"></span></div>')
    sample = lambda cls: f'<svg width="40" height="12" aria-hidden="true" class="key-line"><path d="M2,6 H38" class="sm-edge {cls}"/></svg>'
    legend = (f'<div class="heat-legend">'
              f'<span class="heat-key">{sample("k-call")}{T("صفحة أو ملف يستدعي API", "a page or a file calls an API")}</span>'
              f'<span class="heat-key">{sample("k-uses")}{T("صفحة تستخدم كودًا مشتركًا", "a page uses shared code")}</span>'
              f'<span class="heat-key">{sample("k-answer")}{T("ملف في الخادم يجيبها", "a server file answers it")}</span>'
              f'<span class="heat-key">{sample("k-use")}{T("يستخدم جزءًا آخر", "uses another part")}</span>'
              f'<span class="heat-key">{sample("k-data")}{T("يصل إلى جدول أو خدمة", "reaches a table or a service")}</span>'
              f'<span class="heat-key"><i class="key-box sm-unknown"></i>{T("لا نعرف من يجيبها", "no known handler")}</span></div>')
    spans, edge = [], 0                          # the columns and the gaps between them, as the drawing has them
    for x, width in COLUMNS:
        spans += [x - edge, width]; edge = x + width
    spans.append(WIDTH - edge)
    fr = ' '.join(f'{max(s, 0)}fr' for s in spans)
    counts = (len(sm['pages']), len(sm['apis']), len(sm['handlers']), len(sm['modules']), len(sm['data']))
    meanings = ('pages and shared files drawn', 'APIs drawn', 'server files drawn', 'parts drawn', 'tables and services drawn')
    heads = ''.join(f'<div></div><div>{T(esc(ar), esc(en))} {num(counts[c] + (len(sm["callers"]) if c == 0 else 0), meanings[c])}</div>'
                    for c, (ar, en) in enumerate(SM_HEADS)) + '<div></div>'
    info = {x['id']: x for group in ('pages', 'callers', 'apis', 'handlers', 'modules', 'data') for x in sm[group]}
    info = {k: {kk: vv for kk, vv in v.items() if kk not in ('reach',)} for k, v in info.items()}
    data = {'rel': sm['related'], 'info': info, 'features': {f['name']: f['pages'] for f in sm['features']}}
    return (f'<div class="card graph-wrap sm-wrap" data-part="system-map"><h3 class="sm-title">{T("كل الروابط: من الصفحة إلى البيانات", "Every link: from the page to the data")}</h3>'
            f'<p class="muted small">{T("من اليمين إلى اليسار: الصفحة، ونقطة API التي تستدعيها، والملف في الخادم الذي يجيبها، والأجزاء التي يستخدمها، والجداول والخدمات التي يصل إليها. مرّر المؤشر على أي مربع لتضيء سلسلته كلها، أو اضغط عليه لتثبيتها وترى تفاصيله تحت الرسم.", "From left to right: the page, the API it calls, the server file that answers it, the parts that file uses, and the tables and services it reaches. Hover any box to light its whole chain, or click it to keep it and see its details under the drawing.")}</p>'
            f'<p class="small">{summary}</p>' + ''.join(f'<p class="muted small">{x}</p>' for x in notes) + controls + legend
            + f'<div class="graph-scroll sm-scroll"><div class="sm-heads" style="grid-template-columns:{fr}">{heads}</div>'
            f'{system_svg(sm, lay, True)}{system_svg(sm, lay, False)}</div>'
            f'<div id="smd" class="node-detail card sm-detail">{T("اضغط على صفحة أو نقطة API أو ملف أو جدول لترى ما يصل إليه ومن يصل إليه.", "Click a page, an API, a file or a table to see what it reaches and what reaches it.", "p", "muted small")}</div>'
            f'</div>{api_table(sm)}' + json_script('eaos-system', data))


# ---------------------------------------------------------------- the work log: who did what, when, and where it stopped

TOOL_WORDS = {
    'audit': ('فحص المشروع كله', 'checked the whole project'), 'choose_branch': ('اختار الفرع', 'chose the branch'),
    'run_setup': ('جهّز تشغيل البرنامج في نسخة معزولة', 'prepared running the app in an isolated copy'),
    'run_try': ('جرّب تشغيل البرنامج', 'tried running the app'), 'safety_net': ('سجّل شاشات البرنامج وسرعته', 'recorded the app’s screens and speed'),
    'fix_start': ('فتح دفعة إصلاح', 'opened a fix batch'), 'fix_edit': ('أصلح بطاقة وتحقق منها', 'fixed a card and checked it'),
    'fix_skip': ('ترك بطاقة مع السبب', 'left a card out, with the reason'), 'fix_finish': ('أغلق الدفعة وفحصها كلها', 'closed the batch and checked it whole'),
    'accept': ('أدخل الفرع في فرعك', 'took the branch into yours'), 'undo': ('ألغى الفرع المنتظر', 'threw the waiting branch away'),
    'note': ('كتب ملاحظة', 'wrote a note'), 'blueprint_start': ('بدأ مشروعًا من خطته', 'started a project from its plan'),
    'blueprint_spec': ('راجع مواصفات المنتج', 'checked the product spec'), 'blueprint_design': ('رسم البنية المستهدفة', 'drew the target'),
    'build_start': ('فتح مرحلة بناء', 'opened a build milestone'), 'build_edit': ('بنى بطاقة', 'built a card'),
    'build_skip': ('ترك بطاقة بناء', 'left a build card out'), 'build_finish': ('أغلق مرحلة البناء', 'closed the build milestone'),
    'wait': ('تابع عملًا جاريًا', 'followed a running job'), 'status': ('قرأ أين وصل العمل', 'read where the work is'),
}
JOB_WORDS = {'fix batch': ('دفعة الإصلاح', 'fix batch'), 'build milestone': ('مرحلة البناء', 'build milestone')}


def when(at):
    """An ISO time as a person reads it: the date and the minute, UTC."""
    return str(at or '').replace('T', ' ')[:16]


def who(name):
    return f'<span class="chip who" data-literal="1">{esc(name or "?")}</span>'


def work_log(progress):
    """Where the work stopped, what is open and left, the next step, then the last steps and the notes, newest first."""
    h = (progress or {}).get('handover')
    head = f'<h3 id="work-log">{T("سجل العمل وأين وقفنا", "Work log and where we stopped")}</h3>'
    if not isinstance(h, dict) or not (h.get('last_steps') or h.get('open_work') or h.get('last_assistant') or h.get('notes') or h.get('in_progress')):
        return head + (f'<div class="card" data-part="work-log">{T("لم يبدأ أي عمل بعد: حين يبدأ مساعد ذكي (Claude Code أو Codex) الفحص أو الإصلاح، تظهر هنا كل خطوة، ومن قام بها، ومتى، وأين وقف.", "No work has started yet: when an AI assistant (Claude Code or Codex) starts the check or the fixes, every step shows here, who took it, when, and where it stopped.", "p")}</div>')
    now, work = [], h.get('open_work') if isinstance(h.get('open_work'), dict) else None
    job = h.get('running_job') if isinstance(h.get('running_job'), dict) else None
    waiting = h.get('waiting_for_the_person') if isinstance(h.get('waiting_for_the_person'), dict) else None
    cards = lambda ids: ' '.join(lit(c) for c in list(ids)[:20]) or T('لا شيء', 'none')
    if job:
        now.append(T(f'عمل جارٍ الآن: {lit(job.get("kind") or job.get("id") or "")}', f'A job is running now: {lit(job.get("kind") or job.get("id") or "")}', 'li'))
    if work:
        kind = JOB_WORDS.get(work.get('kind'), (work.get('kind') or '', work.get('kind') or ''))
        number = work.get('number') if work.get('number') is not None else work.get('milestone')
        label = (T(f'{esc(kind[0])} مفتوحة', f'Open {esc(kind[1])}') + (' ' + (num(number, 'the number of the open batch') if isinstance(number, int) else lit(number)) if number is not None else ''))
        kept, not_kept, left = work.get('kept') or [], work.get('not_kept') or {}, work.get('left') or []
        now.append(f'<li>{label}: ' + T(f'نجح {num(len(kept), "cards kept in the open batch")}، ولم ينجح {num(len(not_kept), "cards not kept in the open batch")}، وبقي {num(len(left), "cards left in the open batch")}',
                                         f'{num(len(kept), "cards kept in the open batch")} kept, {num(len(not_kept), "cards not kept in the open batch")} not kept, {num(len(left), "cards left in the open batch")} left') + '</li>')
        if left: now.append(f'<li>{T("الباقي:", "Left:", cls="lbl")} {cards(left)}</li>')
        for card, why in list(not_kept.items())[:8] if isinstance(not_kept, dict) else []:
            now.append(f'<li>{T("لم ينجح:", "Not kept:", cls="lbl")} {lit(card)} {tech(str(why)[:200])}</li>')
    if waiting:
        now.append(T(f'ينتظر قرارك: أدخل الفرع {lit(waiting.get("branch") or "")} في فرعك أو ألغِه.', f'Waiting for you: take branch {lit(waiting.get("branch") or "")} into yours, or throw it away.', 'li'))
    busy = h.get('in_progress') if isinstance(h.get('in_progress'), dict) else None
    if busy and busy.get('card'):
        since = (T(f' منذ {num(when(busy.get("since")), "when this card was started (UTC)")}', f' since {num(when(busy.get("since")), "when this card was started (UTC)")}')
                 if busy.get('since') else '')
        by = f' {who(busy["by"])}' if busy.get('by') else ''
        read = [f for f in busy.get('files_read') or [] if isinstance(f, str)]
        now.append(f'<li>{T(f"كان يعمل على البطاقة {lit(busy["card"])}", f"Was working on card {lit(busy["card"])}")}{by}{since}'
                   + (f'<div class="small">{T("قرأ من الملفات:", "Files it read:", cls="lbl")} {" ".join(lit(f) for f in read[:8])}'
                      + (T(f' و{num(len(read) - 8, "more files read")} غيرها', f' and {num(len(read) - 8, "more files read")} more') if len(read) > 8 else '') + '</div>' if read else '')
                   + (f'<div class="small">{T("آخر محاولة:", "Last try:", cls="lbl")} {tech(str(busy["last_try"])[:300])}</div>' if busy.get('last_try') else '')
                   + '</li>')
    if not now: now.append(T('لا شيء مفتوح الآن.', 'Nothing is open now.', 'li'))
    if job: step = T('انتظار العمل الجاري حتى ينتهي، ثم المتابعة.', 'Wait for the running job to finish, then go on.')
    elif busy and busy.get('card'): step = T(f'إكمال البطاقة {lit(busy["card"])} من حيث توقفت، ثم البقية.', f'Finish card {lit(busy["card"])} from where it stopped, then the rest.')
    elif work and work.get('left'): step = T('إصلاح البطاقات الباقية واحدة واحدة، ثم إغلاق الدفعة وفحصها كلها.', 'Fix the cards left one by one, then close the batch and check it whole.')
    elif work: step = T('إغلاق الدفعة المفتوحة وفحصها كلها.', 'Close the open batch and check it whole.')
    elif waiting: step = T('قرارك في الفرع المنتظر: أدخله أو ألغِه.', 'Your decision on the waiting branch: take it in or throw it away.')
    else: step = T('بدء الدفعة التالية من الخطة.', 'Start the next batch of the plan.')
    p = h.get('progress') if isinstance(h.get('progress'), dict) else {}
    tally = (f'<p class="small">{T(f"التقدم في فرعك: أُغلق {num(p.get("closed", 0), "cards closed")} من {num(p.get("total", 0), "cards in the plan")}", f"Progress in your branch: {num(p.get("closed", 0), "cards closed")} of {num(p.get("total", 0), "cards in the plan")} closed")}</p>' if p else '')
    last = (f'<p class="small">{T("آخر من عمل:", "Last to work:", cls="lbl")} {who(h.get("last_assistant"))} '
            + (T(f'في {num(when(h.get("last_activity")), "the time of the last step (UTC)")}', f'at {num(when(h.get("last_activity")), "the time of the last step (UTC)")}') if h.get('last_activity') else '')
            + (f' · {T("الفرع:", "branch:", cls="lbl")} {lit(h["branch"])}' if isinstance(h.get('branch'), str) and h.get('branch') else '') + '</p>')
    status = (f'<div class="card wl-status"><h4>{T("أين وقفنا", "Where we stopped")}</h4>{last}<ul class="small wl-now">{"".join(now)}</ul>'
              f'<p class="small"><b>{T("الخطوة التالية:", "The next step:")}</b> {step}</p>{tally}'
              + (f'<details><summary>{T("للمساعد الذكي الذي يكمل", "For the AI assistant that continues")}</summary>{tech(h["how_to_continue"])}</details>' if h.get('how_to_continue') else '')
              + '</div>')
    steps = [s for s in h.get('last_steps') or [] if isinstance(s, dict)]
    items = []
    for s in reversed(steps):
        tool = s.get('tool') or ''
        words = TOOL_WORDS.get(tool)
        what = T(*map(esc, words)) if words else lit(tool)
        items.append(f'<li class="wl-step"><span class="wl-dot" aria-hidden="true"></span><div><div class="wl-head">{who(s.get("by"))} '
                     f'<span class="muted small">{num(when(s.get("at")), "the time of this step (UTC)")}</span></div>'
                     f'<div>{what}{(" " + lit(s["card"])) if s.get("card") else ""}</div>'
                     + (f'<div class="small muted">{T("النتيجة:", "Result:", cls="lbl")} {tech(str(s["outcome"])[:300])}</div>' if s.get('outcome') else '') + '</div></li>')
    timeline = (f'<h4>{T("آخر الخطوات، الأحدث أولًا", "The last steps, newest first")}</h4><ol class="timeline">{"".join(items)}</ol>' if items
                else T('لا خطوات مسجلة بعد.', 'No step recorded yet.', 'p', 'muted small'))
    notes = [x for x in h.get('notes') or [] if isinstance(x, dict) and x.get('note')]
    notes_html = (f'<h4>{T("ملاحظات المساعدين", "Notes from the assistants")}</h4><ul class="wl-notes">'
                  + ''.join(f'<li>{who(x.get("by"))} <span class="muted small">{num(when(x.get("at")), "the time of this note (UTC)")}</span>'
                            f'{(" " + lit(x["card"])) if x.get("card") else ""}<div>{said(x["note"])}</div></li>' for x in reversed(notes)) + '</ul>') if notes else ''
    return head + f'<div class="card wl" data-part="work-log">{status}<div class="wl-body">{timeline}{notes_html}</div></div>'


# ---------------------------------------------------------------- page

def branch_line(branch):
    """Which branch this report is for (the check, the fixes and the progress follow it), and the reports of the others."""
    if not branch: return ''
    main = (T(' (الفرع الرئيسي)', ' (the main branch)') if branch.get('main') == branch['name'] else
            T(f' · الفرع الرئيسي: {lit(branch["main"])}', f' · main branch: {lit(branch["main"])}') if branch.get('main') else '')
    others = ' '.join(f'<a href="{esc(o["href"])}">{lit(o["name"])}</a>' for o in branch.get('others') or [])
    return (f'<div class="branch" data-part="branch">{T("الفرع:", "Branch:")} <b>{lit(branch["name"])}</b>{main}'
            + (f' · {T("تقارير فروع أخرى:", "Other branches:")} {others}' if others else '') + '</div>')



def stamp(eaos, cls='stamp'):
    """Which EAOS built the page, from progress['eaos'] = {'version', 'commit', 'built' (ISO time)}; '' without it."""
    if not isinstance(eaos, dict) or not (eaos.get('version') or eaos.get('commit')): return ''
    built = str(eaos.get('built') or '').replace('T', ' ')[:16]
    bits = [lit(eaos['version']) if eaos.get('version') else '', lit(str(eaos['commit'])[:12]) if eaos.get('commit') else '',
            f'<span title="{esc(eaos["digest"])}">{lit(str(eaos["digest"])[:12])}</span>' if eaos.get('digest') else '',
            num(built, 'when this page was built (UTC)') if built else '']
    line = ' · '.join(b for b in bits if b)
    part = ' data-part="stamp"' if cls == 'stamp' else ''
    return f'<div class="{cls} muted small"{part}>{T("بنته نسخة EAOS", "Built by EAOS")} {line}</div>'


def error_banner(errors):
    """What could not be built, and why, at the top of the page; '' when everything was built."""
    if not errors: return ''
    items = ''.join(f'<li>{T("لم يُبنَ:", "Not built:", cls="lbl")} <b>{esc(e.get("section") or "")}</b> {tech(e.get("error"))}</li>' if isinstance(e, dict)
                    else f'<li>{tech(str(e))}</li>' for e in errors)
    return (f'<div class="wrap"><div class="card errors" data-part="report-errors" role="alert"><h4>{T("أجزاء من هذا التقرير لم تُبنَ", "Parts of this report could not be built")}</h4>'
            f'<p class="small">{T("بقية الصفحة سليمة. هذه الأجزاء تقول «غير متاح» حتى يُصلح سببها:", "The rest of the page is sound. These parts say “not available” until their cause is fixed:")}</p>'
            f'<ul class="small">{items}</ul></div></div>')


INTRO = {'summary': ('صحة المشروع في صفحة واحدة: الدرجة، والمجالات الخمسة، وأهم المشاكل، وما لم نفحصه.',
                     'The health of the project on one page: the score, the five areas, the main problems, and what we did not check.'),
         'gaps': ('كل مشكلة: أين هي، وما حالها الآن وما المطلوب، وخطورتها، وهل يصلحها EAOS آليًا.',
                  'Every problem: where it is, what it is now and what it should be, how serious it is, and whether EAOS fixes it.'),
         'structure': ('أجزاء المشروع اليوم وأين تتركز المشاكل، وكيف يعتمد كل جزء على غيره، حتى الملفات والدوال والصفحات.',
                       'The parts of the project today, where problems gather, and how each depends on the others, down to files, functions and pages.'),
         'system': ('النظام من أوله إلى آخره: كل صفحة، وكل نقطة API تستدعيها، والكود في الخادم الذي يجيبها، وما يستخدمه، والجداول والخدمات التي يصل إليها.',
                    'The system end to end: every page, every API it calls, the server code that answers it, what that code uses, and the tables and services it reaches.'),
         'target': ('ما سيصبح عليه البرنامج: طبقاته وأجزاؤه، ومن أين يأتي كل جزء من اليوم، وكم أُغلق من الفجوة في كل جزء.',
                    'What the program will become: its layers and parts, where each part comes from today, and how much of the gap each has closed.'),
         'plan': ('أين وقف العمل ومن عمل ماذا، وترتيب العمل مرحلة بعد مرحلة، وما أُنجز، وكل بطاقة مهمة وحالتها، وما ينتظر قرارك.',
                  'Where the work stopped and who did what, the order of the work milestone by milestone, what is done, every task card and its state, and what waits for your decision.')}


def failure(section, error):
    return {'section': section, 'error': f'{type(error).__name__}: {error}'[:300]}


def render_parts(m, name, lang='ar'):
    """(the page, [{section, error}] of every part that could not be built): a section that fails shows "not available"."""
    parts, errors = {}, list(m.get('map_errors') or [])
    try: m = dict(m, cards=task_cards(m))
    except Exception as error:
        m = dict(m, cards=[])
        errors.append(failure('cards', error))
    for section, build in (('summary', lambda: section_summary(m, name)), ('gaps', lambda: section_gaps(m)),
                           ('structure', lambda: section_structure(m)), ('system', lambda: section_system(m)),
                           ('target', lambda: section_target(m)), ('plan', lambda: section_plan(m))):
        try: parts[section] = build()
        except Exception as error:     # one broken record costs its section, not the page or the audit
            parts[section] = unavailable(section, error)
            errors.append(failure(section, error))
    progress = m.get('progress') or {}
    told = [e for e in progress.get('report_errors') or [] if isinstance(e, str) and e.strip()]
    nav = ''.join(f'<a href="#{s}" data-tab="{s}">{w(s)}</a>' for s in SECTIONS)
    body = ''.join(f'<section id="{s}" class="report" data-report="{s}"><header class="sec-head"><h2>{w(s)}</h2>'
                   f'<p class="muted">{T(*map(esc, INTRO[s]))}</p></header>{parts[s]}</section>' for s in SECTIONS)
    generated = ((m['dossier'].get('provenance') or {}).get('generated_at') or '')[:10]
    date = (f'<span class="muted">{T("تاريخ الفحص:", "Audit date:")} {num(generated, "the date of the audit")}</span>' if generated else '')
    date += branch_line(progress.get('branch')) + stamp(progress.get('eaos'))
    direction = 'rtl' if lang == 'ar' else 'ltr'
    text = (f'<!doctype html><html lang="{lang}" dir="{direction}" data-lang="{lang}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(W["title"][0 if lang == "ar" else 1])}: {esc(name)}</title>'
            f'<style>{CSS}</style></head><body><header class="top"><div class="wrap top-in"><div class="brand">'
            f'<div class="kicker">{T("تقرير EAOS", "EAOS report")}</div><h1>{w("title")}: {lit(name)}</h1>{date}</div>'
            f'<div class="actions"><button type="button" id="lang" class="btn">{T("English", "العربية")}</button>'
            f'<button type="button" id="print" class="btn ghost">{T("طباعة / PDF", "Print / PDF")}</button></div></div>'
            f'<nav class="tabs wrap" aria-label="reports">{nav}</nav></header>{error_banner(told + errors)}'
            f'<main class="wrap">{body}</main><footer class="wrap muted small">'
            f'{T("هذه الصفحة للقراءة. الملفات التقنية في المجلد نفسه مكتوبة للمساعد الذكي ولم تتغير.", "This page is for reading. The technical files in the same folder are written for the AI assistant and are unchanged.")}'
            f'{stamp(progress.get("eaos"), "stamp-foot")}</footer><script>{JS}{MAP_JS}{SYSTEM_JS}</script></body></html>')
    return text, errors


def render(m, name, lang='ar'):
    return render_parts(m, name, lang)[0]


def empty(progress=None):
    return {'rows': [], 'statuses': {}, 'coverage': {}, 'score': score([], 0, known=False), 'plan': {}, 'target': {},
            'gap_matrix': {}, 'manifest': {}, 'dossier': {}, 'progress': progress or {}, 'cmap': None, 'drill': None, 'flows': None,
            'system': None, 'system_layout': None, 'map_errors': []}


def write(report, lang='ar', name=None, progress=None):
    """Write <report>/human/index.html from the report's records and return its path.

    Never raises for missing or broken records: a section it cannot build says "not available".
    What could not be built is also written to <report>/human/errors.json as [{section, error}], [] when all was.
    """
    report = Path(report)
    errors = []
    try:
        m = model(report, progress)
    except Exception as error:
        m = empty(progress)
        errors.append(failure('records', error))
    if name is None:
        name = Path(str((m['manifest'] or {}).get('target') or report)).name
    page = report / 'human' / 'index.html'
    page.parent.mkdir(parents=True, exist_ok=True)
    lang = 'ar' if lang == 'ar' else 'en'
    try:
        text, failed = render_parts(dict(m, map_errors=errors + list(m.get('map_errors') or [])), name, lang)
    except Exception as error:
        failed = errors + [failure('page', error)]
        text = render(dict(empty(progress), map_errors=failed), name, lang)
    page.write_text(text, encoding='utf-8')
    try: (page.parent / 'errors.json').write_text(json.dumps(failed, ensure_ascii=False, indent=1), encoding='utf-8')
    except OSError: pass
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

    The rules: the five reports exist (section ids summary, gaps, structure, target, plan, each with data-report);
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
.gap-card{display:block}.gap-head{display:grid;grid-template-columns:auto 1fr;gap:22px;align-items:center}
.gap-n{font-size:54px;font-weight:800;color:var(--good);line-height:1;min-width:120px;text-align:center}.gap-card .lead{margin:0 0 10px}
.progress.big{height:16px}.progress.thin{height:6px;margin:6px 0}
.tally{list-style:none;padding:0;margin:14px 0 4px;display:flex;flex-wrap:wrap;gap:8px 18px;font-size:14px}.tally li{display:flex;gap:6px;align-items:center}
.tally .n{font-weight:800;font-size:16px}
.chip.st{font-weight:600}.st-good{background:var(--good-soft);color:var(--good)}.st-warn{background:var(--warn-soft);color:var(--warn)}
.st-accent{background:var(--accent-soft);color:var(--accent)}.st-bad{background:var(--bad-soft);color:var(--bad)}.st-plain{background:var(--surface-2);color:var(--ink-2)}
.chart.history{max-width:760px;margin-top:6px}.history .grid{stroke:var(--line);stroke-width:1}.history .tick{font-size:12px;fill:var(--muted)}
.history .line{fill:none;stroke:var(--accent);stroke-width:2.5;stroke-linejoin:round}.history .area{fill:var(--accent);opacity:.08}
.history .dot-pt{fill:var(--accent);stroke:var(--surface);stroke-width:2}.history .end-label{font-size:13px;font-weight:700;fill:var(--ink)}
.allcards>summary{font-size:17px;display:flex;justify-content:space-between;gap:10px}.cfilters{position:static;margin:10px 0;box-shadow:none;border:0;padding:0}
.mgroup{border:1px solid var(--line);border-radius:12px;padding:8px 14px;margin:8px 0;background:var(--bg)}
.mgroup>summary{display:flex;justify-content:space-between;gap:10px;color:var(--ink)}.mgroup[hidden],.tcard[hidden]{display:none!important}
.tcards{display:grid;gap:6px;margin-top:6px}.tcard{border:1px solid var(--line);border-radius:10px;background:var(--surface);padding:4px 12px}
.tcard>summary{color:var(--ink);font-weight:500;font-size:14px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}.tcard>summary .lit{margin-inline-start:auto}
.tcard>summary .said{flex:1 1 320px;min-width:0;font-size:14px;color:var(--ink)}.tbody{font-size:14px;padding:4px 0 8px}.tbody p{margin:6px 0}.bad-ink{color:var(--bad);font-weight:600}
.graph-scroll{overflow:auto;max-height:78vh;border:1px solid var(--line);border-radius:10px;background:var(--bg);margin-top:10px}
.graph-scroll .chart{max-width:none}.fit .graph-scroll .cgraph{width:100%!important;height:auto}
.graph-tools{display:flex;gap:14px;align-items:center;margin-top:8px;flex-wrap:wrap}
.cgraph .cg-node rect{fill:var(--surface);stroke:var(--line);stroke-width:1.5}.cgraph .cg-node.cyc rect{stroke:var(--bad);stroke-width:2}
.cg-node{cursor:pointer}.cg-node:focus{outline:none}.cg-node:focus rect,.t-node:focus rect{stroke:var(--accent);stroke-width:2.5}
.cg-name{font:600 12px ui-monospace,Menlo,Consolas,monospace;fill:var(--ink)}.cg-sub{font-size:11px;fill:var(--ink-2)}
.edge{fill:none;stroke:var(--ink-2);opacity:.28}.edge.cyc{stroke:var(--bad);opacity:.5}.edge.wrong{stroke-dasharray:6 4}
.arrow-head{fill:var(--ink-2)}.arrow-head.cyc{fill:var(--bad)}.arrow-head.acc{fill:var(--accent)}
.hl-graph.focus .edge{opacity:.06}.hl-graph.focus .edge.on{opacity:.95}.hl-graph.focus .cg-node,.hl-graph.focus .t-node{opacity:.35}
.hl-graph.focus .cg-node.on,.hl-graph.focus .t-node.on{opacity:1}.hl-graph .on rect{stroke:var(--accent);stroke-width:2.5}
.loops .edge:not(.cyc){display:none}
.key-line{vertical-align:middle}.key-line .edge{opacity:.9;stroke-width:2.5}.key-box{width:16px;height:12px;border-radius:3px;display:inline-block;border:2px solid var(--line)}.key-box.cyc{border-color:var(--bad)}
.node-detail{margin-top:10px;background:var(--surface-2);box-shadow:none}.node-detail h4 .lit{font-size:14px}.link{display:inline-flex;gap:4px;align-items:center;margin:2px 8px 2px 0}
.drill,.graph-wrap{margin-bottom:16px}.pick{display:flex;gap:8px;align-items:center;margin:8px 0;font-weight:600}
.pick select{font:13px ui-monospace,Menlo,Consolas,monospace;padding:6px 10px;border:1px solid var(--line);border-radius:10px;background:var(--surface);color:var(--ink);max-width:100%}
.ego-heads{display:grid;grid-template-columns:240fr 140fr 290fr 190fr 240fr;font-size:13px;font-weight:700;color:var(--ink-2);margin-top:8px}
.ego-heads>div:nth-child(2){grid-column:3}.ego-heads>div:nth-child(3){grid-column:5}
.egograph{width:100%;height:auto;margin-top:4px}.e-box rect{fill:var(--surface);stroke:var(--line)}.e-box.cyc rect{stroke:var(--bad);stroke-width:1.5}
.e-box[data-pick]{cursor:pointer}.e-box[data-pick]:hover rect{stroke:var(--accent)}.e-box.quiet{opacity:.55}
.e-l{font:600 12px ui-monospace,Menlo,Consolas,monospace;fill:var(--ink)}.e-s{font-size:11px;fill:var(--muted)}
.e-link{fill:none;stroke:var(--ink-2);opacity:.28}.e-arc{fill:none;stroke:var(--accent);stroke-width:1.2;opacity:.5}
#dfile{margin-top:14px;border-top:1px solid var(--line);padding-top:6px}
.flowsvg{display:block;margin:0 auto}.f-node rect{fill:var(--surface);stroke:var(--line);stroke-width:1.5}
.f-entry rect{fill:var(--accent);stroke:var(--accent)}.f-entry .f-l,.f-entry .f-s{fill:var(--on-accent)}.f-handler rect{stroke:var(--accent);stroke-width:2.5}
.f-stop rect{fill:var(--bg);stroke:var(--muted);stroke-dasharray:5 4}.f-stop .f-l{fill:var(--muted)}
.f-l{font:600 12.5px ui-monospace,Menlo,Consolas,monospace;fill:var(--ink)}.f-s{font-size:11.5px;fill:var(--ink-2)}
.f-edge{fill:none;stroke:var(--ink-2);stroke-width:1.6;opacity:.6}.f-edge.stop{stroke-dasharray:4 4}
.f-group{fill:none;stroke:var(--accent);stroke-opacity:.35;stroke-dasharray:3 3}.f-gname{font:600 11px ui-monospace,Menlo,Consolas,monospace;fill:var(--accent)}
.tgraph{min-width:900px}.t-band{fill:var(--surface-2);opacity:.6}.t-layer{font:700 13px ui-monospace,Menlo,Consolas,monospace;fill:var(--accent)}
.t-node{cursor:pointer}.t-node rect:first-of-type{fill:var(--surface);stroke:var(--line);stroke-width:1.5}.t-node.empty rect:first-of-type{stroke-dasharray:4 3}
.t-name{font:600 12px ui-monospace,Menlo,Consolas,monospace;fill:var(--ink)}.t-sub{font-size:11px;fill:var(--ink-2)}
.t-track{fill:var(--surface-2)}.t-fill{fill:var(--good)}.t-edge{opacity:.12}
.mapping{min-width:900px}.m-name,.m-target{font:12px ui-monospace,Menlo,Consolas,monospace;fill:var(--ink)}.m-target{font-weight:700;fill:var(--accent)}
.m-line{fill:none;stroke-width:1.8}.r-keep{stroke:var(--muted);opacity:.7}.r-modify{stroke:var(--accent);opacity:.8}
.r-rebuild{stroke:var(--accent);stroke-width:3;stroke-dasharray:7 4;opacity:.8}.r-remove{stroke:var(--bad);stroke-dasharray:2 4;opacity:.8}
.map-row:hover .m-line{stroke-width:4;opacity:1}
@media (max-width:760px){.gap-head{grid-template-columns:1fr}.ego-heads{display:none}}
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
document.querySelectorAll('option[data-en]').forEach(function(o){o.textContent=o.getAttribute('data-'+l)});
var names={'':['كل درجات الخطورة','All severities'],critical:['حرجة','Critical'],high:['عالية','High'],medium:['متوسطة','Medium'],low:['منخفضة','Low']};
var areas={'':['كل المجالات','All areas'],security:['الأمان','Security'],structure:['البنية','Structure'],quality:['جودة الكود','Code quality'],performance:['الأداء تحت الضغط','Performance under load'],maintainability:['سهولة التطوير والاختبار','Ease of change and testing']};
var i=l==='ar'?0:1;document.querySelectorAll('#fsev option').forEach(function(o){o.textContent=names[o.value][i]});
document.querySelectorAll('#farea option').forEach(function(o){o.textContent=areas[o.value][i]});count()}
function show(id){document.querySelectorAll('section.report').forEach(function(s){s.classList.toggle('on',s.id===id)});
document.querySelectorAll('.tabs a').forEach(function(a){a.classList.toggle('on',a.dataset.tab===id)})}
var tabs=Array.prototype.map.call(document.querySelectorAll('.tabs a'),function(a){return a.dataset.tab});function route(){var h=location.hash.slice(1);show(tabs.indexOf(h)>=0?h:'summary')}
window.addEventListener('hashchange',function(){route();window.scrollTo(0,0)});
document.querySelectorAll('[data-go]').forEach(function(a){a.addEventListener('click',function(e){e.preventDefault();history.replaceState(null,'','#'+a.dataset.go);show(a.dataset.go);window.scrollTo(0,0)})});
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

MAP_JS = r"""
(function(){var d=document.documentElement,lang=d.getAttribute('data-lang')||'ar';
document.querySelectorAll('option[data-en]').forEach(function(o){o.textContent=o.getAttribute('data-'+lang)});
document.querySelectorAll('[data-ph-ar]').forEach(function(e){e.placeholder=e.getAttribute('data-ph-'+lang)});
function E(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function B(ar,en){return '<span class="l-ar" lang="ar">'+ar+'</span><span class="l-en" lang="en">'+en+'</span>'}
function J(id){var e=document.getElementById(id);if(!e)return null;try{return JSON.parse(e.textContent)}catch(x){return null}}
function base(p){return String(p).split('/').pop()}
function cut(s,n){s=String(s);return s.length>n?'…'+s.slice(s.length-n+1):s}
function N(v,m){return '<span class="n" data-meaning="'+E(m)+'">'+E(v)+'</span>'}
function sel(v){return '[data-node="'+String(v).replace(/["\\]/g,'\\$&')+'"]'}
function wire(root){(root||document).querySelectorAll('.hl-graph').forEach(function(svg){if(svg.dataset.wired)return;svg.dataset.wired='1';
var wrap=svg.closest('.graph-wrap'),pinned=null;
function mark(id,on){svg.classList.toggle('focus',!!on);svg.querySelectorAll('.on').forEach(function(e){e.classList.remove('on')});if(!on)return;
svg.querySelectorAll(sel(id)).forEach(function(e){e.classList.add('on')});
svg.querySelectorAll('[data-from]').forEach(function(e){if(e.dataset.from===id||e.dataset.to===id){e.classList.add('on');
svg.querySelectorAll(sel(e.dataset.from===id?e.dataset.to:e.dataset.from)).forEach(function(n){n.classList.add('on')})}})}
svg.querySelectorAll('[data-node]').forEach(function(n){var id=n.dataset.node;
n.addEventListener('mouseenter',function(){if(!pinned)mark(id,true)});n.addEventListener('mouseleave',function(){if(!pinned)mark(id,false)});
function pick(){pinned=pinned===id?null:id;mark(pinned||id,!!pinned);if(n.dataset.pick){n.dispatchEvent(new CustomEvent('pick',{bubbles:true}));return}
if(wrap)wrap.querySelectorAll('.node-detail').forEach(function(x){x.hidden=x.dataset.for!==pinned})}
n.addEventListener('click',pick);n.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();pick()}})})})}
document.querySelectorAll('.only-loops').forEach(function(c){c.addEventListener('change',function(){c.closest('.graph-wrap').classList.toggle('loops',c.checked)})});
document.querySelectorAll('.fit-btn').forEach(function(b){b.addEventListener('click',function(){b.closest('.graph-wrap').classList.toggle('fit')})});
// a three-column picture: what points in, the subject's own items (with arcs between them), what they point to
function ego(o,rtl){var W=1100,rh=30,bh=24,cols=[[0,240],[380,290],[860,240]],gut=16;
var n=Math.max(o.mid.length,o.left.length,o.right.length,1),H=n*rh+12,out=[];
function X(c){var x=cols[c][0],w=cols[c][1];return rtl?W-x-w:x}
function Y(list,i){var step=(H-12)/Math.max(list.length,1);return 6+i*step+(step-bh)/2}
function yMid(i){return 6+i*rh+(rh-bh)/2}
function link(c1,y1,c2,y2,cls,w){var a=X(c1),b=X(c2),wa=cols[c1][1],wb=cols[c2][1],sx,ex;if(a<b){sx=a+wa;ex=b}else{sx=a;ex=b+wb}
var mx=(sx+ex)/2;return '<path class="'+cls+'" style="stroke-width:'+w.toFixed(1)+'" d="M'+sx+','+(y1+bh/2)+' C'+mx+','+(y1+bh/2)+' '+mx+','+(y2+bh/2)+' '+ex+','+(y2+bh/2)+'"/>'}
function sw(k){return 1+Math.log2(Math.max(k||1,1))}
o.lm.forEach(function(l){out.push(link(0,Y(o.left,l[0]),1,yMid(l[1]),'e-link',sw(l[2])))});
o.mr.forEach(function(l){out.push(link(1,yMid(l[0]),2,Y(o.right,l[1]),'e-link',sw(l[2])))});
var edge=rtl?X(1):X(1)+cols[1][1],dir=rtl?-1:1;
o.mm.forEach(function(l){var y1=yMid(l[0])+bh/2,y2=yMid(l[1])+bh/2,bulge=Math.min(150,gut+Math.abs(y2-y1)*0.3)*dir;
out.push('<path class="e-arc" d="M'+edge+','+y1+' C'+(edge+bulge)+','+y1+' '+(edge+bulge)+','+y2+' '+edge+','+y2+'" marker-end="url(#ego-arr)"/>')});
function box(c,y,it,i){var x=X(c),w=cols[c][1],tx=rtl?x+w-8:x+8,anchor=rtl?'end':'start',room=Math.floor((w-16)/7);
return '<g class="e-box'+(it.cls?' '+it.cls:'')+'"'+(it.pick!=null?' data-pick="'+it.pick+'" tabindex="0"':'')+'><title>'+E(it.title||it.label)+'</title><rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+bh+'" rx="6"/>'+
'<text x="'+tx+'" y="'+(y+16)+'" text-anchor="'+anchor+'" direction="ltr"><tspan class="e-l">'+E(cut(it.label,room-(it.sub?Math.min(14,it.sub.length+2):0)))+'</tspan>'+(it.sub?'<tspan class="e-s"> '+E(cut(it.sub,14))+'</tspan>':'')+'</text></g>'}
o.left.forEach(function(it,i){out.push(box(0,Y(o.left,i),it,i))});o.mid.forEach(function(it,i){out.push(box(1,yMid(i),it,i))});o.right.forEach(function(it,i){out.push(box(2,Y(o.right,i),it,i))});
return '<svg viewBox="0 0 '+W+' '+H+'" class="chart egograph" direction="ltr" role="img" aria-label="'+E(o.label)+'"><defs><marker id="ego-arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" class="arrow-head acc"/></marker></defs>'+out.join('')+'</svg>'}
function heads(a,b,c){return '<div class="ego-heads"><div>'+a+'</div><div>'+b+'</div><div>'+c+'</div></div>'}
function both(o){return '<div class="l-ar">'+ego(o,true)+'</div><div class="l-en">'+ego(o,false)+'</div>'}
var D=J('eaos-drill');
if(D){var rev=D.files.map(function(){return[]});D.imports.forEach(function(list,f){list.forEach(function(g){rev[g].push(f)})});
var fnOut={},fnIn={};D.calls.forEach(function(c,i){(fnOut[c[0]]=fnOut[c[0]]||[]).push(i);(fnIn[c[2]]=fnIn[c[2]]||[]).push(i)});
function comp(ci){var C=D.comps[ci],mine={},view=document.getElementById('dview');C.files.forEach(function(f){mine[f]=1});
var left=C.used_by.slice().sort(function(a,b){return b[1]-a[1]}).slice(0,12),right=C.uses.slice().sort(function(a,b){return b[1]-a[1]}).slice(0,12);
var li={},ri={};left.forEach(function(p,i){li[p[0]]=i});right.forEach(function(p,i){ri[p[0]]=i});
var files=C.files.slice().sort(function(a,b){return (rev[b].length+D.imports[b].length)-(rev[a].length+D.imports[a].length)}).slice(0,30),mi={};files.forEach(function(f,i){mi[f]=i});
var lm={},mr={},mm=[];files.forEach(function(f,i){rev[f].forEach(function(g){var o=D.owner[g];if(o!==ci&&o in li){var k=li[o]+':'+i;lm[k]=(lm[k]||0)+1}});
D.imports[f].forEach(function(g){var o=D.owner[g];if(o===ci){if(g in mi)mm.push([i,mi[g]])}else if(o in ri){var k=i+':'+ri[o];mr[k]=(mr[k]||0)+1}})});
function pairs(m){return Object.keys(m).map(function(k){var p=k.split(':');return[+p[0],+p[1],m[k]]})}
var root=C.name.replace(/\/?$/,'/');
var o={label:C.name,left:left.map(function(p){return{label:D.comps[p[0]].name,title:D.comps[p[0]].name+' → '+C.name+': '+p[1]}}),
right:right.map(function(p){return{label:D.comps[p[0]].name,title:C.name+' → '+D.comps[p[0]].name+': '+p[1]}}),
mid:files.map(function(f){var p=D.files[f];return{label:p.indexOf(root)===0?p.slice(root.length):p,title:p,pick:f,cls:D.cycle[f]?'cyc':''}}),lm:pairs(lm),mr:pairs(mr),mm:mm};
var inside=mm.length,more=C.files.length-files.length,coh=C.cohesion==null?B('لا يستورد شيئًا','it imports nothing'):B(N(C.cohesion+'%','share of its imports that stay inside it')+' من استيراداته تبقى داخله',N(C.cohesion+'%','share of its imports that stay inside it')+' of its imports stay inside it');
view.innerHTML='<p class="small"><code class="lit" dir="ltr" data-literal="1">'+E(C.name)+'</code> — '+B('الملفات: '+N(C.filecount,'files in this part')+' · استيرادات داخلية مرسومة: '+N(inside,'imports between its files drawn'),N(C.filecount,'files in this part')+' files · '+N(inside,'imports between its files drawn')+' imports between them drawn')+' · '+coh+
(more>0?' · '+B('عُرض أكثر '+N(files.length,'files shown')+' ملفًا ارتباطًا','showing the '+N(files.length,'files shown')+' most connected files'):'')+'</p>'+
heads(B('أجزاء تستخدمه','Parts that use it')+' '+N(C.used_by.length,'parts that use it'),B('ملفاته — اضغط على ملف','Its files — click a file'),B('أجزاء يستخدمها','Parts it uses')+' '+N(C.uses.length,'parts it uses'))+both(o);
view.querySelectorAll('[data-pick]').forEach(function(g){function go(){file(+g.dataset.pick)}g.addEventListener('click',go);g.addEventListener('keydown',function(e){if(e.key==='Enter'){go()}})});
if(files.length)file(files[0]);else document.getElementById('dfile').innerHTML=''}
function file(f){var view=document.getElementById('dfile'),own=D.functions[f]||[],touched={};
(fnOut[f]||[]).forEach(function(i){touched[D.calls[i][1]]=(touched[D.calls[i][1]]||0)+1});(fnIn[f]||[]).forEach(function(i){touched[D.calls[i][3]]=(touched[D.calls[i][3]]||0)+1});
var names=own.slice().sort(function(a,b){return (touched[b]||0)-(touched[a]||0)}).slice(0,30),mi={};names.forEach(function(n,i){mi[n]=i});
var L={},R={},lm={},mr={},mm=[];
(fnOut[f]||[]).forEach(function(i){var c=D.calls[i];if(!(c[1] in mi))return;if(c[2]===f){if(c[3] in mi)mm.push([mi[c[1]],mi[c[3]]]);return}
var k=c[2]+'|'+c[3];if(!(k in R))R[k]={label:c[3],sub:base(D.files[c[2]]),title:c[3]+' — '+D.files[c[2]],n:0};R[k].n+=c[4];var q=mi[c[1]]+'|'+k;mr[q]=(mr[q]||0)+c[4]});
(fnIn[f]||[]).forEach(function(i){var c=D.calls[i];if(c[0]===f||!(c[3] in mi))return;var k=c[0]+'|'+c[1];if(!(k in L))L[k]={label:c[1],sub:base(D.files[c[0]]),title:c[1]+' — '+D.files[c[0]],n:0};L[k].n+=c[4];var q=k+'|'+mi[c[3]];lm[q]=(lm[q]||0)+c[4]});
function top(M){return Object.keys(M).sort(function(a,b){return M[b].n-M[a].n}).slice(0,14)}
var lk=top(L),rk=top(R),li={},ri={};lk.forEach(function(k,i){li[k]=i});rk.forEach(function(k,i){ri[k]=i});
var LM=[],MR=[];Object.keys(lm).forEach(function(q){var p=q.split('|'),k=p[0]+'|'+p[1];if(k in li)LM.push([li[k],+p[2],lm[q]])});
Object.keys(mr).forEach(function(q){var p=q.split('|'),k=p[1]+'|'+p[2];if(k in ri)MR.push([+p[0],ri[k],mr[q]])});
var head='<h4><code class="lit" dir="ltr" data-literal="1">'+E(D.files[f])+'</code></h4>';
if(!own.length){view.innerHTML=head+'<p class="muted small">'+B('لم نجد دوال مسمّاة في هذا الملف.','No named function was found in this file.')+'</p>';return}
var o={label:D.files[f],left:lk.map(function(k){return L[k]}),right:rk.map(function(k){return R[k]}),mid:names.map(function(n){return{label:n,cls:touched[n]?'':'quiet'}}),lm:LM,mr:MR,mm:mm};
view.innerHTML=head+'<p class="small">'+B('الدوال: '+N(own.length,'named functions in this file')+' · تستدعيها دوال من ملفات أخرى: '+N(lk.length,'functions elsewhere that call this file')+' · تستدعي هي: '+N(rk.length,'functions elsewhere this file calls'),
N(own.length,'named functions in this file')+' functions · called by '+N(lk.length,'functions elsewhere that call this file')+' functions elsewhere · they call '+N(rk.length,'functions elsewhere this file calls')+' elsewhere')+'</p>'+
heads(B('من يستدعيها','Who calls them'),B('دوال هذا الملف (الأقواس: استدعاءات بينها)','This file’s functions (arcs: calls between them)'),B('ما تستدعيه','What they call'))+both(o)}
var dc=document.getElementById('dcomp');if(dc&&D.comps.length){dc.addEventListener('change',function(){comp(+dc.value)});comp(+dc.value||0)}}
var F=J('eaos-flows');
function flow(fl,rtl){var bw=F.box[0],bh=F.box[1],W=fl.width,H=fl.height,pos={},out=[];
fl.nodes.forEach(function(n){pos[n.id]={x:rtl?W-n.x-bw:n.x,y:n.y,n:n}});
var run=[];fl.nodes.concat([{y:-1}]).forEach(function(n){var last=run[run.length-1];if(last&&(n.y!==last.y||n.sub!==last.sub||n.kind==='stop'||n.kind==='entry')){if(run.length>1&&last.sub){var xs=run.map(function(r){return pos[r.id].x}),x0=Math.min.apply(0,xs),x1=Math.max.apply(0,xs)+bw;
out.push('<rect class="f-group" x="'+(x0-6)+'" y="'+(last.y-20)+'" width="'+(x1-x0+12)+'" height="'+(bh+26)+'" rx="8"/><text class="f-gname" x="'+(rtl?x1:x0)+'" y="'+(last.y-7)+'" text-anchor="'+(rtl?'end':'start')+'" direction="ltr">'+E(base(last.sub))+'</text>')}run=[]}if(n.y>=0&&n.kind==='fn')run.push(n)});
fl.edges.forEach(function(e){var a=pos[e[0]],b=pos[e[1]];if(!a||!b)return;var sx=a.x+bw/2,sy=a.y+bh,ex=b.x+bw/2,ey=b.y,d;
if(ey>sy)d='M'+sx+','+sy+' C'+sx+','+(sy+26)+' '+ex+','+(ey-26)+' '+ex+','+ey;else{var side=rtl?-1:1,ox=a.x+(rtl?0:bw),tx=b.x+(rtl?0:bw);d='M'+ox+','+(a.y+bh/2)+' C'+(ox+60*side)+','+(a.y+bh/2)+' '+(tx+60*side)+','+(b.y+bh/2)+' '+tx+','+(b.y+bh/2)}
out.push('<path class="f-edge'+(b.n.kind==='stop'?' stop':'')+'" d="'+d+'" marker-end="url(#f-arr)"/>')});
function line(t,y,cls,words){var tx=rtl?x0+bw-10:x0+10,an=rtl&&!words?'end':'start',dir=rtl&&words?'rtl':'ltr';
return '<text x="'+tx+'" y="'+y+'" text-anchor="'+an+'" direction="'+dir+'" class="'+cls+'">'+E(t)+'</text>'}var x0;
fl.nodes.forEach(function(n){var p=pos[n.id],y=p.y,t1=n.label,t2,words=true;x0=p.x;
if(n.kind==='entry'){t1=(n.sub||'')+' '+(n.label||'');t2=rtl?'الرابط الذي تبدأ منه':'where it starts'}
else if(n.kind==='stop'){t2=rtl?'يتوقف التتبع هنا'+(n.more?' (و'+n.more+' غيرها)':''):'the trace stops here'+(n.more?' (and '+n.more+' more)':'')}
else{t2=n.library?(rtl?base(n.sub)+' · ومكتبات: '+n.library:base(n.sub)+' · and '+n.library+' library calls'):base(n.sub);words=rtl&&!!n.library}
out.push('<g class="f-node f-'+n.kind+'"><title>'+E(n.label+(n.sub?' — '+n.sub:''))+'</title><rect x="'+x0+'" y="'+y+'" width="'+bw+'" height="'+bh+'" rx="'+(n.kind==='entry'?bh/2:8)+'"/>'+
line(cut(t1,30),y+20,'f-l',false)+line(cut(t2,38),y+38,'f-s',n.kind!=='fn'||words)+'</g>')});
return '<svg viewBox="0 0 '+W+' '+H+'" class="chart flowsvg" direction="ltr" role="img" aria-label="'+E(fl.route+' '+fl.handler)+'"><defs><marker id="f-arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" class="arrow-head"/></marker></defs>'+out.join('')+'</svg>'}
function showFlow(i){var fl=F.flows[i],v=document.getElementById('fview');if(!fl||!v)return;
var what=fl.surface==='page'?B('صفحة','A page'):B('نقطة دخول','An entry point');
v.innerHTML='<p class="small">'+what+' <code class="lit" dir="ltr" data-literal="1">'+E((fl.method?fl.method+' ':'')+(fl.route||'?'))+'</code> → <code class="lit" dir="ltr" data-literal="1">'+E(fl.handler)+'</code> '+
B('في','in')+' <code class="lit" dir="ltr" data-literal="1">'+E(fl.path)+'</code> · '+B('الاستدعاءات المتتبعة: '+N(fl.steps,'calls traced from this page')+' · يتوقف التتبع عند '+N(fl.stops,'calls the trace cannot follow')+' منها',N(fl.steps,'calls traced from this page')+' calls traced · the trace stops at '+N(fl.stops,'calls the trace cannot follow')+' of them')+'</p>'+
'<div class="graph-scroll"><div class="l-ar">'+flow(fl,true)+'</div><div class="l-en">'+flow(fl,false)+'</div></div>'}
var df=document.getElementById('dflow');if(F&&df&&F.flows.length){df.addEventListener('change',function(){showFlow(+df.value)});showFlow(+df.value||0)}
function cards(){var s=(document.getElementById('cstate')||{}).value||'',q=((document.getElementById('cq')||{}).value||'').toLowerCase(),n=0,active=s||q;
document.querySelectorAll('.tcard').forEach(function(c){var ok=(!s||c.dataset.state===s||(s==='new'&&c.dataset.new==='1'))&&(!q||c.dataset.search.indexOf(q)>=0);c.hidden=!ok;if(ok)n++});
document.querySelectorAll('.mgroup').forEach(function(g){var any=g.querySelector('.tcard:not([hidden])');g.hidden=!!active&&!any;if(active&&any)g.open=true});
var out=document.getElementById('cshown');if(out)out.textContent=active?(d.getAttribute('data-lang')==='ar'?('المعروض: '+n):('Showing: '+n)):''}
['cstate','cq'].forEach(function(id){var e=document.getElementById(id);if(e){e.addEventListener('input',cards);e.addEventListener('change',cards)}});
wire(document)})();
"""

CSS += r"""
.sm-wrap .sm-title{margin:0 0 6px}.sm-tools{position:static;margin:10px 0 6px}
.sm-scroll{max-height:82vh;position:relative}.sm-heads{display:grid;position:sticky;top:0;z-index:2;background:var(--bg);border-bottom:1px solid var(--line);
font-size:13px;font-weight:700;color:var(--ink-2);padding:6px 0;min-width:1000px}.sm-heads>div{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.smap{min-width:1000px}.smap .sm-node{cursor:pointer}.smap .sm-node rect{fill:var(--surface);stroke:var(--line);stroke-width:1.2}
.smap .sm-node:focus{outline:none}.smap .sm-node:focus rect,.smap .sm-node:hover rect{stroke:var(--accent);stroke-width:2}
.sm-l{font:600 11px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;fill:var(--ink)}.sm-s{font:11px ui-monospace,Menlo,Consolas,monospace;fill:var(--muted)}
.sm-tag{font:700 10px ui-monospace,Menlo,Consolas,monospace}.t-get{fill:var(--good)}.t-post{fill:var(--accent)}.t-put{fill:var(--warn)}.t-del{fill:var(--bad)}.t-any{fill:var(--muted)}
.n-page rect{stroke:var(--accent)!important;stroke-opacity:.55}.n-page.untraced{opacity:.55}.n-caller rect{fill:var(--surface-2)!important;stroke-dasharray:3 2}
.n-api.unknown rect{stroke:var(--muted)!important;stroke-dasharray:4 3}.n-api.guessed rect{stroke:var(--warn)!important}
.n-handler rect{fill:var(--accent-soft)!important;stroke:transparent}.n-handler.idle{opacity:.6}.n-module rect{fill:var(--surface-2)!important}
.n-table rect{fill:var(--good-soft)!important;stroke:transparent}.n-service rect{fill:var(--warn-soft)!important;stroke:transparent}
.n-service .sm-l{font-family:system-ui,-apple-system,"Segoe UI","Noto Sans Arabic",Tahoma,sans-serif}
.sm-band{fill:var(--surface-2);opacity:.75}.sm-band-l{font:700 10.5px ui-monospace,Menlo,Consolas,monospace;fill:var(--accent)}
.sm-sub-head{font-size:12px;font-weight:700;fill:var(--ink-2)}
.sm-edge{fill:none;stroke:var(--ink-2);opacity:.22}.sm-edge.k-use{opacity:.07}.sm-edge.k-data{opacity:.12}.sm-edge.k-uses{stroke:var(--accent);stroke-dasharray:2 3;opacity:.3}.sm-edge.k-data{stroke:var(--good)}
.sm-edge.k-guess{stroke-dasharray:4 3}.key-line .sm-edge{opacity:.9;stroke-width:2.2}
.smap.focus .sm-node{opacity:.18}.smap.focus .sm-node.on{opacity:1}.smap.focus .sm-node.on rect{stroke:var(--accent)!important;stroke-width:2;stroke-opacity:1}
.smap.focus .sm-edge{opacity:.03}.smap.focus .sm-edge.on{opacity:.9;stroke:var(--accent);stroke-width:1.8}.smap.focus .sm-edge.on.k-data{stroke:var(--good)}
.smap.focus .sm-node.hit rect{stroke:var(--warn)!important;stroke-width:2.5}
.key-box.sm-unknown{border-style:dashed;border-color:var(--muted)}
.sm-detail{margin-top:12px}.sm-detail h4 .lit{font-size:14px}.sm-group{margin:6px 0;font-size:13px}.sm-group b{margin-inline-end:6px}
.sm-chip{font:12px ui-monospace,Menlo,Consolas,monospace;border:1px solid var(--line);background:var(--surface);border-radius:999px;padding:1px 9px;margin:2px;cursor:pointer;color:var(--ink);direction:ltr}
.sm-chip:hover{border-color:var(--accent);color:var(--accent)}.sm-table td{font-size:13px;max-width:240px}.sm-table .lit{word-break:normal;overflow-wrap:anywhere;display:inline-block;max-width:100%;margin:1px 0;font-size:12px}.sm-table td:first-child,.sm-table td:nth-child(2){white-space:nowrap}.sm-table tr[hidden]{display:none}
.errors{border-color:var(--bad);background:var(--bad-soft);margin-top:14px}.errors h4{color:var(--bad)}.errors ul{margin:4px 0 0;padding-inline-start:20px}
.stamp{margin-top:2px}.stamp .lit{font-size:12px}.stamp-foot{margin-top:6px}
.wl{display:grid;grid-template-columns:minmax(260px,1fr) 1.5fr;gap:18px;align-items:start}.wl-status{background:var(--accent-soft);border:0;box-shadow:none}
.wl-status h4{margin-bottom:4px}.wl-now{margin:6px 0;padding-inline-start:18px}.wl-now li{margin:3px 0}.wl-body h4{margin:0 0 10px}
.timeline{list-style:none;padding:0;margin:0 0 12px;position:relative}.timeline:before{content:"";position:absolute;inset-inline-start:6px;top:6px;bottom:6px;width:2px;background:var(--line)}
.wl-step{display:grid;grid-template-columns:14px 1fr;gap:12px;margin:0 0 12px;font-size:14px}.wl-dot{width:14px;height:14px;border-radius:50%;background:var(--surface);border:3px solid var(--accent);margin-top:5px;position:relative;z-index:1}
.wl-head{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.chip.who{background:var(--accent);color:var(--on-accent);font:600 12px system-ui,sans-serif}
.wl-notes{list-style:none;padding:0;margin:0}.wl-notes li{border-inline-start:3px solid var(--warn);padding:6px 10px;margin:6px 0;background:var(--bg);border-radius:6px;font-size:14px}
@media (max-width:760px){.wl{grid-template-columns:1fr}}
"""

SYSTEM_JS = r"""
(function(){var el=document.getElementById('eaos-system');if(!el)return;var D;try{D=JSON.parse(el.textContent)}catch(x){return}
var svgs=[].slice.call(document.querySelectorAll('svg.smap')),panel=document.getElementById('smd'),hint=panel?panel.innerHTML:'',pinned=null,base=null,hits=null;
function E(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function B(ar,en){return '<span class="l-ar" lang="ar">'+ar+'</span><span class="l-en" lang="en">'+en+'</span>'}
function N(v,m){return '<span class="n" data-meaning="'+E(m)+'">'+E(v)+'</span>'}
function L(s){return '<code class="lit" dir="ltr" data-literal="1">'+E(s)+'</code>'}
function rel(id){return new Set(D.rel[id]||[id])}
function mark(set){svgs.forEach(function(svg){svg.classList.toggle('focus',!!set);
svg.querySelectorAll('.sm-node').forEach(function(n){n.classList.toggle('on',!!set&&set.has(n.dataset.node));n.classList.toggle('hit',!!hits&&hits.has(n.dataset.node))});
svg.querySelectorAll('.sm-edge').forEach(function(e){e.classList.toggle('on',!!set&&set.has(e.dataset.from)&&set.has(e.dataset.to))})})}
var KIND={P:['صفحة','Page'],C:['كود مشترك يستدعي الخادم','Shared code that calls the server'],A:['نقطة API','API'],H:['ملف في الخادم','Server file'],M:['جزء','Part'],T:['جدول','Table'],S:['خدمة أو تخزين','Service or storage']};
var GROUP={P:['الصفحات','Pages'],C:['كود مشترك','Shared code'],A:['نقاط API','APIs'],H:['ملفات الخادم','Server files'],M:['الأجزاء','Parts'],T:['الجداول','Tables'],S:['الخدمات','Services']};
function name(id){var o=D.info[id]||{},k=id.charAt(0);if(k==='P')return o.route+' · '+o.component;if(k==="A")return o.key||id.slice(2);if(k==='H'||k==='C')return o.short||o.path||id.slice(2);if(k==='M')return o.short||o.name;return o.name||id.slice(2)}
function chip(id){return '<button type="button" class="sm-chip" data-to="'+E(id)+'">'+E(name(id))+'</button>'}
function p(x){return '<p class="small">'+x+'</p>'}
function detail(id){if(!panel)return;if(!id){panel.innerHTML=hint;return}
var o=D.info[id]||{},k=id.charAt(0),lines=[],r=D.rel[id]||[];
if(k==='P'){lines.push(B('ملف المكوّن:','Component file:')+' '+L(o.file));
if(!o.traced)lines.push(B('لم نجد ملف مكوّنها، فلم نتتبع ما تستدعيه.','Its component file was not found, so what it calls is not traced.'));
lines.push(B('تستدعي من ملفاتها: '+N(o.calls.length,'APIs called from this page’s own files')+' · تصل إلى كود مشترك يستدعي الخادم: '+N(o.shared.length,'shared files this page reaches'),
N(o.calls.length,'APIs called from this page’s own files')+' APIs called from its own files · '+N(o.shared.length,'shared files this page reaches')+' shared files that call the server'))}
if(k==='C'){lines.push(B('تصل إليه صفحات: '+N(o.pages.length,'pages that reach this file')+' · يستدعي: '+N(o.calls.length,'APIs this file calls'),N(o.pages.length,'pages that reach this file')+' pages reach it · it calls '+N(o.calls.length,'APIs this file calls')+' APIs'))}
if(k==='A'){lines.push(B('يستدعيها من الملفات:','Called in the files:')+' '+(o.callers.length?o.callers.map(L).join(' '):B('لا أحد وجدناه','none we found')));
if(o.handlers.length){lines.push(B('يجيبها في الخادم:','Answered on the server by:')+' '+o.handlers.map(function(h){return L(h.path)+(h.function?' '+L(h.function):'')}).join(' ')+(o.exact?'':' '+B('(من اسم الملف فقط؛ تحقق منه)','(from the file name only; check it)')))}
else lines.push(B('لم نجد في الخادم ما يجيبها: قد يأتي جوابها من خادم آخر، أو من مسار يُبنى وقت التشغيل.','No server code was found that answers it: the answer may come from another server, or from a route built at run time.'));
if(o.features&&o.features.length)lines.push(B('الميزة:','Feature:')+' '+o.features.map(L).join(' '))}
if(k==='H'&&!o.apis.length)lines.push(B('لم نجد في الكود من يستدعيه: قد يُستدعى من خارج البرنامج (رابط، أو webhook، أو مهمة مجدولة).','No call to it was found in the code: it may be called from outside the program (a link, a webhook, a scheduled job).'));
if(k==='T'&&o.files)lines.push(B('معرّف في:','Defined in:')+' '+o.files.map(L).join(' ')+' · '+B('لا نفرّق هنا بين القراءة والكتابة.','reading and writing are not told apart here.'));
var groups='';'PCAHMTS'.split('').forEach(function(g){var list=r.filter(function(x){return x.charAt(0)===g&&x!==id});if(!list.length)return;
groups+='<div class="sm-group"><b>'+B(GROUP[g][0],GROUP[g][1])+' '+N(list.length,'related items of this kind')+'</b>'+list.slice(0,40).map(chip).join('')+(list.length>40?' '+B('و'+N(list.length-40,'more items')+' غيرها','and '+N(list.length-40,'more items')+' more'):'')+'</div>'});
panel.innerHTML='<h4>'+B(KIND[k][0],KIND[k][1])+' '+L(name(id))+'</h4>'+lines.map(p).join('')+groups;
panel.querySelectorAll('.sm-chip').forEach(function(b){b.addEventListener('click',function(){select(b.dataset.to,true)})})}
function select(id,scroll){pinned=id;mark(id?rel(id):base);detail(id);if(scroll&&id){svgs.forEach(function(svg){if(!svg.getBoundingClientRect().width)return;
var n=svg.querySelector('[data-node="'+String(id).replace(/["\\]/g,'\\$&')+'"]');if(n&&n.scrollIntoView)n.scrollIntoView({block:'nearest',inline:'nearest'})})}}
svgs.forEach(function(svg){svg.querySelectorAll('.sm-node').forEach(function(n){var id=n.dataset.node;
n.addEventListener('mouseenter',function(){if(!pinned)mark(rel(id))});n.addEventListener('mouseleave',function(){if(!pinned)mark(base)});
function pick(){select(pinned===id?null:id)}n.addEventListener('click',pick);n.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();pick()}})})});
var q=document.getElementById('smq'),f=document.getElementById('smf'),out=document.getElementById('smshown'),lang=function(){return document.documentElement.getAttribute('data-lang')};
function filter(){var text=(q&&q.value||'').trim().toLowerCase(),feature=f&&f.value||'',set=null,count=0;hits=null;
if(feature){set=new Set();(D.features[feature]||[]).forEach(function(id){rel(id).forEach(function(x){set.add(x)})});count=(D.features[feature]||[]).length}
if(text){hits=new Set();(svgs[0]?svgs[0].querySelectorAll('.sm-node'):[]).forEach(function(n){if(n.dataset.search.indexOf(text)>=0)hits.add(n.dataset.node)});
if(!set){set=new Set(hits);if(hits.size<=5)hits.forEach(function(h){rel(h).forEach(function(x){set.add(x)})})}count=hits.size}
document.querySelectorAll('.sm-table tbody tr').forEach(function(row){row.hidden=!!text&&row.dataset.search.indexOf(text)<0});
base=set;pinned=null;mark(base);detail(null);if(out)out.textContent=(text||feature)?(lang()==='ar'?('المطابق: '+count):('Matching: '+count)):''}
if(q)q.addEventListener('input',filter);if(f)f.addEventListener('change',filter);
var c=document.getElementById('smclear');if(c)c.addEventListener('click',function(){if(q)q.value='';if(f)f.value='';filter()})})();
"""
