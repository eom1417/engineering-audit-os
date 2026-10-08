"""The one model of a report: what a problem is, its area and severity, the health score, and every card with its state.

REPORT.html (eaos/human_report.py) and the Studio (eaos/studio/export.py) read their numbers from here and compute none
of their own (docs/STUDIO.md, D2).

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
import json
import math
from pathlib import Path

from ..ranking import CONFIDENCE_WEIGHT

# The language of a source file by its suffix: the Studio's languages bar and the coverage of function facts.
LANGUAGES = {'.py': 'Python', '.ts': 'TypeScript', '.tsx': 'TypeScript', '.js': 'JavaScript', '.jsx': 'JavaScript',
             '.mjs': 'JavaScript', '.cjs': 'JavaScript', '.go': 'Go', '.rb': 'Ruby', '.java': 'Java', '.kt': 'Kotlin',
             '.cs': 'C#', '.php': 'PHP', '.rs': 'Rust', '.swift': 'Swift', '.vue': 'Vue', '.svelte': 'Svelte',
             '.sql': 'SQL', '.dart': 'Dart', '.scala': 'Scala', '.c': 'C', '.cpp': 'C++', '.h': 'C'}

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
CLOSED = ('done', 'resolved')
CARD_STATES = ('done', 'resolved', 'on_branch', 'in_batch', 'open', 'skipped')   # eaos/ledger.py


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


def records(report, progress=None):
    """Every record the views read, with the cards and the score computed once."""
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
            'dossier': dossier, 'progress': progress or {}}


# ---------------------------------------------------------------- progress: the ledger and every task card

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
                    'state': state if state in CARD_STATES else 'open', 'new': bool(c.get('new')), 'batch': c.get('batch'), 'at': c.get('at'),
                    'why': c.get('why') or ('' if ledger else failed.get(r['id'], '')), 'commit': c.get('commit')})
    for c in (ledger or {}).get('cards') or []:
        if not isinstance(c, dict) or (c.get('id') and c['id'] in seen): continue
        pattern = c.get('pattern') or 'generic'
        out.append({'id': c.get('id') or '', 'key': c.get('key') or '', 'title': c.get('title') or '', 'pattern': pattern,
                    'severity': PATTERNS.get(pattern, PATTERNS['generic'])[1], 'milestone': c.get('milestone'), 'paths': c.get('paths') or [],
                    'before': '', 'after': '', 'state': c.get('state') if c.get('state') in CARD_STATES else 'open', 'new': bool(c.get('new')),
                    'batch': c.get('batch'), 'at': c.get('at'), 'why': c.get('why') or '', 'commit': c.get('commit')})
    return out


def gap_totals(m, cards):
    """The ledger's totals when it has them, else counted from the cards; percent is closed / total."""
    counts = {s: sum(c['state'] == s for c in cards) for s in CARD_STATES}
    t = {'total': len(cards), 'closed': counts['done'] + counts['resolved'], 'new': sum(c['new'] for c in cards), **counts}
    given = (ledger_of(m) or {}).get('totals')
    if isinstance(given, dict):
        t.update({k: v for k, v in given.items() if isinstance(v, (int, float)) and not isinstance(v, bool)})
    t['percent'] = float(t['percent']) if 'percent' in (given or {}) else (100 * t['closed'] / t['total'] if t['total'] else 0.0)
    return t
