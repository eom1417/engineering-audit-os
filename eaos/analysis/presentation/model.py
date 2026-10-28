"""The one model of a report: what a problem is, its area and severity, the health score, and every card with its state.

REPORT.html (eaos/report/human_report/) and the Studio (eaos/report/studio/export.py) read their numbers from here and compute none
of their own.

What a problem is: one task card of plan.json. Its area and severity come from one table, PATTERNS below:
    pattern             area             default severity
    upgrade_dependency  security         high
    security_weakness   security         high
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
    layer_boundary      by its boundary (security for the browser, endpoints and data; structure; maintainability)
    load_blocker        performance      medium
    redundant_work      performance      medium
    hotspot             maintainability  medium
    split_module        structure        medium    (a module past one responsibility is the structure's)
    trace_gap           maintainability  low
    untested_path       maintainability  medium
    generic             by the debt register's category (CATEGORY_AREA), else maintainability; medium
The severity recorded for the card's claim in debt-register.json wins over the default: that register
already decides severity from its witnesses (eaos/analysis/assessments/debt_register.py). Confidence is the claim's own.

The health score, derived only from those cards:
    weight of a problem   = severity weight (critical 10, high 5, medium 2, low 1)
                            x confidence weight (CONFIRMED 1.0, LIKELY 0.7, HYPOTHESIS 0.4; eaos/analysis/planning/ranking.py)
    density of an area    = sum of its weights per 100 source files (a project under 100 files counts as 100)
    area score            = 100 x 20 / (20 + density)   (20 weighted points per 100 files halve the score)
    health score          = the mean of the measured areas' scores; a confirmed critical problem caps it at 39
    grade                 = the score's band, but never good or excellent over ground this version does not check
                            (words.json `unchecked`): it reads `partial` there, for the whole score and for that area
An area whose checking stage failed or was not reached is left out of the mean and shown as not measured.
A security card the assistant closed as not worth changing (cards.json `closed`: a vulnerable library with no fixed
version) is an accepted risk, not a solved one: it is no longer work, but it still weighs on the security score, and
the area counts it apart (`accepted`), so the score never reads as if no risk were known.
Grades: 90 and above excellent, 75 good, 60 fair, 40 weak, below 40 critical. An area's light is green
from 80 with no high or critical problem, red below 50 or with a critical problem, amber otherwise.

A priority (eaos/analysis/planning/ranking.py: reach x confidence x origin / cost) is shown as its rank among all cards,
in words: "very high, in the top 7%". The raw value is kept in a data attribute, not in the text.
The counts and scales the views show beside them are in eaos/analysis/presentation/counts.py.
"""
import math
from pathlib import Path

from ...core.contracts.decisions import ready, waiting
from ...core.language.plain import kind as plain_kind
from ...core.language.words import unchecked
from .counts import (all_card_count, architecture_counts, collection_count, density_counts, history_scale,  # noqa: F401  (the views read them here)
                     history_ticks, layer_counts, pipeline_counts, problems_left, remaining, structure_counts,
                     system_counts, unparsed_count)
from .counts import drill_counts, system_details
from ..planning.ranking import CONFIDENCE_WEIGHT
from ...core.system.files import read_json

# The language of a source file by its suffix: the Studio's languages bar and the coverage of function facts.
LANGUAGES = {'.py': 'Python', '.ts': 'TypeScript', '.tsx': 'TypeScript', '.js': 'JavaScript', '.jsx': 'JavaScript',
             '.mjs': 'JavaScript', '.cjs': 'JavaScript', '.go': 'Go', '.rb': 'Ruby', '.java': 'Java', '.kt': 'Kotlin',
             '.cs': 'C#', '.php': 'PHP', '.rs': 'Rust', '.swift': 'Swift', '.vue': 'Vue', '.svelte': 'Svelte',
             '.sql': 'SQL', '.dart': 'Dart', '.scala': 'Scala', '.c': 'C', '.cpp': 'C++', '.h': 'C'}


def language_counts(rows):
    """{language: facts} of fact rows, each by the suffix of its file (LANGUAGES); a file of no known language aside."""
    counts = {}
    for row in rows:
        name = LANGUAGES.get(Path(str((row.get('location') or {}).get('path') or '')).suffix.lower())
        if name: counts[name] = counts.get(name, 0) + 1
    return counts

SEVERITIES = ('critical', 'high', 'medium', 'low')
SEVERITY_WEIGHT = {'critical': 10, 'high': 5, 'medium': 2, 'low': 1}
HALF_POINT = 20          # weighted points per 100 files at which an area scores 50
CRITICAL_CAP = 39
# ux: how the screens look, from the visual reviewer's design cards; measured only in a check that pictured them.
AREAS = ('security', 'structure', 'quality', 'performance', 'ux', 'maintainability')
PATTERNS = {
    'upgrade_dependency': ('security', 'high'), 'security_weakness': ('security', 'high'),
    'broken_code': ('quality', 'high'), 'remove_dead': ('quality', 'low'), 'dead_code': ('quality', 'low'),
    'canonicalize': ('quality', 'low'), 'duplicated_rule': ('quality', 'medium'),
    'import_cycle': ('structure', 'medium'), 'mutable_state': ('structure', 'medium'), 'mutable_state_private': ('structure', 'low'),
    'hidden_coupling': ('structure', 'low'), 'external_write': ('structure', 'medium'),
    'policy_violation': ('structure', 'medium'), 'layer_boundary': ('security', 'high'),
    'load_blocker': ('performance', 'medium'), 'redundant_work': ('performance', 'medium'),
    'hotspot': ('maintainability', 'medium'), 'split_module': ('structure', 'medium'), 'trace_gap': ('maintainability', 'low'),
    'untested_path': ('maintainability', 'medium'), 'generic': ('maintainability', 'medium'),
    'design_review': ('ux', 'medium'), 'investigation': ('maintainability', 'low'),
    'repository_craft': ('maintainability', 'low'), 'real_data': ('security', 'high'),
    'old_engine': ('quality', 'medium'), 'data_keeping': ('performance', 'medium'), 'one_source': ('maintainability', 'medium'),
}
CATEGORY_AREA = {'security': 'security', 'supply_chain': 'security', 'architecture': 'structure', 'data': 'structure',
                 'dead_code': 'quality', 'reliability': 'maintainability', 'maintainability': 'maintainability'}
# The stage whose failure leaves an area unmeasured.
AREA_STAGE = {'security': 'facts', 'structure': 'facts', 'quality': 'facts', 'performance': 'baseline', 'ux': 'visual',
              'maintainability': 'measure'}
# Areas whose stage is optional: measured only when that stage ran, never scored 100 for having looked at nothing
# (performance: the speed under load measured on the running program, not the code read alone).
AREA_OPTIONAL = {'ux', 'performance'}
GRADES = ((90, 'excellent'), (75, 'good'), (60, 'fair'), (40, 'weak'), (0, 'critical'))
CLOSED = ('done',)
# eaos/core/project/ledger.py; 'resolved' is an older ledger's state (a problem no longer found), counted nowhere and shown nowhere.
CARD_STATES = ('done', 'resolved', 'on_branch', 'in_batch', 'open', 'skipped')


def classify(task, debt=None, category=None):
    """(area, severity) of one card: the PATTERNS table, with the debt register's severity when it has one."""
    pattern = plain_kind(task)
    area, severity = PATTERNS.get(pattern, PATTERNS['generic'])
    # An investigation (an unproven claim) stays in the area of what it is about.
    if pattern not in PATTERNS or pattern in ('generic', 'investigation', 'layer_boundary'):
        area = CATEGORY_AREA.get(category, area)
    debt = debt or (task.get('design') or {}).get('severity')
    if debt in SEVERITY_WEIGHT: severity = debt
    return area, severity


def _ledger(report):
    """({claim id: claim}, {claim id: debt register item}) of a report."""
    dossier = read_json(report / 'dossier.json', {}) or {}
    register = read_json(report / 'debt-register.json', {}) or {}
    return ({c.get('id'): c for c in dossier.get('claims') or [] if isinstance(c, dict)},
            {i.get('claim_id'): i for i in register.get('items') or [] if isinstance(i, dict) and i.get('claim_id')})


def problems(report):
    """One row per plan card, with its area, severity, confidence and plain words."""
    report = Path(report)
    plan = read_json(report / 'plan.json', {}) or {}
    ledger = _ledger(report)
    rows = [_row_of(task, task.get('claim_id'), ledger) for task in plan.get('tasks') or [] if isinstance(task, dict)]
    ranked = sorted((r['priority'] for r in rows), reverse=True)
    for row in rows:
        above = sum(1 for p in ranked if p > row['priority'])
        row['top'] = max(1, math.ceil((above + 1) * 100 / len(ranked)))
    return rows


def accepted_risks(report):
    """The security cards the assistant closed, as problem rows of the score only (module docstring)."""
    report = Path(report)
    closed = [c for c in (read_json(report / 'cards.json', {}) or {}).get('closed') or [] if isinstance(c, dict)]
    ledger = _ledger(report) if closed else ({}, {})
    rows = [_row_of({'id': c.get('card'), 'title': c.get('title')}, c.get('claim_id'), ledger) for c in closed]
    return [{**row, 'accepted': True} for row in rows if row['area'] == 'security']


def _row_of(task, claim_id, ledger):
    """A card's problem row, with its claim and its debt register item when the ledger has them."""
    claims, debt = ledger
    return _problem_row(task, claims.get(claim_id) or {}, debt.get(claim_id) or {})


def _words(task, claim, assessment):
    """What a card says: its change, title, before and after, the claim's assessment first."""
    return {'change': assessment.get('proposed_change') or task.get('change') or '',
            'title': task.get('title') or claim.get('statement') or '',
            'before': assessment.get('before') or task.get('before') or '',
            'after': assessment.get('after') or task.get('after') or ''}


def _problem_row(task, claim, item):
    area, severity = classify(task, item.get('severity'), item.get('category'))
    words = _words(task, claim, claim.get('assessment') or {})
    decision = task.get('decision') or {}
    return {'id': task.get('id', ''), 'pattern': plain_kind(task), 'area': area, 'severity': severity,
            'confidence': claim.get('confidence') or task.get('confidence') or 'CONFIRMED',
            'auto': ready(task),
            'outcomes': decision.get('allowed_outcomes') or [], 'options': task.get('options') or [],
            'effort': task.get('effort'), 'change': words['change'], 'priority': task.get('priority') or 0,
            'title': words['title'], 'paths': task.get('paths') or [],
            'before': words['before'], 'after': words['after'], 'prerequisites': task.get('prerequisites', [])}


def stage_status(report):
    manifest = read_json(Path(report) / 'run-manifest.json', {}) or {}
    return {name: (row or {}).get('status') for name, row in (manifest.get('stages') or {}).items()}


def score(rows, source_files, statuses=None, known=True):
    """The health score and each area's score, from the formula in the module docstring.

    known is False when the report has no plan: then nothing was counted, and no area gets a score.
    """
    statuses = statuses or {}
    size = max(source_files or 0, 100) / 100
    areas = {area: _area_score(area, rows, size, known and _area_measured(area, statuses)) for area in AREAS}
    overall, capped = _overall(areas, rows)
    kinds, grade = unchecked(), _grade(overall)
    for area, a in areas.items(): a['partial'] = any(k['area'] == area for k in kinds)
    return {'score': overall, 'grade': 'partial' if kinds and grade in ('good', 'excellent') else grade, 'areas': areas,
            'capped': capped, 'size': round(size * 100), 'unchecked': [k['id'] for k in kinds]}


def _overall(areas, rows):
    """(the mean of the measured areas' scores, capped when a confirmed critical problem is known; whether it is)."""
    measured = [a['score'] for a in areas.values() if a['score'] is not None]
    overall = round(sum(measured) / len(measured)) if measured else None
    capped = any(r['severity'] == 'critical' and r['confidence'] == 'CONFIRMED' for r in rows)
    if overall is not None and capped: overall = min(overall, CRITICAL_CAP)
    return overall, capped


def _grade(overall):
    return next(name for floor, name in GRADES if (overall or 0) >= floor) if overall is not None else None


def _area_measured(area, statuses):
    status = statuses.get(AREA_STAGE[area])
    return status not in ('failed', 'not_reached') and (area not in AREA_OPTIONAL or status == 'ok')


def _light(value, counts):
    if value < 50 or counts['critical']: return 'red'
    return 'green' if value >= 80 and not counts['high'] else 'amber'


def _area_score(area, rows, size, measured):
    mine = [r for r in rows if r['area'] == area]
    points = sum(SEVERITY_WEIGHT[r['severity']] * CONFIDENCE_WEIGHT.get(r['confidence'], 1.0) for r in mine)
    density = points / size
    value = round(100 * HALF_POINT / (HALF_POINT + density))
    counts = {s: sum(r['severity'] == s for r in mine) for s in SEVERITIES}
    return {'score': value if measured else None, 'points': round(points), 'density': round(density),
            'counts': counts, 'total': len(mine), 'accepted': sum(bool(r.get('accepted')) for r in mine),
            'light': _light(value, counts) if measured else 'grey', 'measured': measured}


def records(report, progress=None):
    """Every record the views read, with the cards and the score computed once."""
    report = Path(report)
    dossier = read_json(report / 'dossier.json', {}) or {}
    rows = problems(report)
    statuses = stage_status(report)
    coverage = dossier.get('coverage') or {}
    plan = read_json(report / 'plan.json', {}) or {}
    known = isinstance(plan.get('tasks'), list)
    target = read_json(report / 'target-architecture.json', {}) or {}
    return {'rows': rows, 'statuses': statuses, 'coverage': coverage,
            'score': score(rows + accepted_risks(report), coverage.get('source_files'), statuses, known), 'plan': plan, 'target': target,
            'gap_matrix': {'rows': target.get('gap_matrix') or []}, 'manifest': read_json(report / 'run-manifest.json', {}) or {},
            'dossier': dossier, 'progress': progress or {}, 'layers': read_json(report / 'layers.json')}


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
    """Every card of the plan, with its ledger state (by its id in this plan). A ledger row without a plan card (a
    problem the check no longer finds, or one fixed and merged before it) is not a card: it never reaches a page, it
    only counts in the progress (gap_totals). With no ledger, a card kept by a batch is done and one that failed needs
    a decision, as before the ledger."""
    stones = _milestone_of(m['plan'])
    ledger = ledger_of(m)
    kept, failed = waves_state(m['progress'])
    mine = _ledger_cards(ledger)
    done = {i for i, c in mine.items() if c.get('state') == 'done'}
    return [{**_task_card(r, mine.get(r['id']) or {}, stones, ledger, (kept, failed)), 'waits': waiting(r, done)} for r in m['rows']]


def _milestone_of(plan):
    """{card: the milestone it is in}."""
    return {t: s.get('id') for s in plan.get('milestones') or [] if isinstance(s, dict) for t in s.get('tasks') or []}


def _ledger_cards(ledger):
    """{card id: its ledger row}."""
    return {c.get('id'): c for c in (ledger or {}).get('cards') or [] if isinstance(c, dict) and c.get('id')}


def _card_state(r, c, ledger, kept, failed):
    """The ledger's state; with no ledger, done when a batch kept it, skipped when one failed it, else open."""
    if ledger: state = c.get('state')
    else: state = 'done' if r['id'] in kept else 'skipped' if r['id'] in failed else 'open'
    return state if state in CARD_STATES and state != 'resolved' else 'open'


def _task_card(r, c, stones, ledger, waves):
    kept, failed = waves
    return {'id': r['id'], 'key': c.get('key') or r['id'], 'title': r['title'], 'pattern': r['pattern'], 'severity': r['severity'],
            'milestone': c.get('milestone') or stones.get(r['id']), 'paths': r['paths'], 'before': r['before'], 'after': r['after'] or r['change'],
            'state': _card_state(r, c, ledger, kept, failed), 'new': bool(c.get('new')), 'batch': c.get('batch'), 'at': c.get('at'),
            'why': c.get('why') or ('' if ledger else failed.get(r['id'], '')), 'commit': c.get('commit')}


def problem_counts(m):
    """The one count of problems every page says (the Studio's headline and its cards): the cards of the plan
    (task_cards), and those EAOS fixes by itself."""
    return {'problems': len(m['rows']), 'fixable': sum(1 for r in m['rows'] if r['auto'])}


def gap_totals(m, cards):
    """The ledger's totals when it has them, else counted from the cards; percent is closed / total."""
    counts = {s: sum(c['state'] == s for c in cards) for s in CARD_STATES}
    t = {'total': len(cards), 'closed': counts['done'], 'new': sum(c['new'] for c in cards), **counts}
    given = (ledger_of(m) or {}).get('totals')
    if isinstance(given, dict): t.update(_numbers(given))
    t['percent'] = float(t['percent']) if 'percent' in (given or {}) else (100 * t['closed'] / t['total'] if t['total'] else 0.0)
    return t


def _numbers(totals):
    """The ledger's totals that are numbers (a bool is not one)."""
    return {k: v for k, v in totals.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}


def maps(report, target, pipeline_builder=None):
    """The architecture maps (eaos/analysis/maps/architecture.py) and the system map (eaos/analysis/maps/system.py); a missing or broken fact
    record leaves its map None, and what failed is kept in map_errors for the page's warning and errors.json."""
    from ..maps import architecture as arch_map, system_drawing, system as system_map
    out = {'cmap': None, 'drill': None, 'flows': None, 'system': None, 'system_layout': None, 'pipeline': None, 'map_errors': []}
    def attempt(part, build):
        try: build()
        except Exception as error: out['map_errors'].append({'section': part, 'error': f'{type(error).__name__}: {error}'[:300]})
    def components():
        out['cmap'] = arch_map.component_map(report, target)
        out['drill'] = drill_counts(arch_map.drill_data(report, out['cmap']))
    def system():
        out['system'] = system_details(system_map.build(report))
        out['system_layout'] = system_drawing.layout(out['system'])
    attempt('architecture map', components)
    attempt('page flows', lambda: out.update(flows=arch_map.flow_charts(report)))
    attempt('system map', system)
    attempt('pipeline map', lambda: out.update(pipeline=(pipeline_builder or pipeline_sections)(report)))
    return out


def pipeline_sections(report):
    """The Studio's pipeline section in both languages (eaos/analysis/maps/pipeline.py), for the pipeline sheet; None when the
    check wrote no facts/pipeline.json."""
    from ..maps import pipeline
    sections = {lang: pipeline.from_report(report, lang=lang) for lang in ('ar', 'en')}
    return sections if all(sections.values()) else None


def _owners(components):
    """{path: the id of today's component it belongs to}, the last one naming it."""
    owner = {}
    for c in components:
        for path in c.get('paths') or []: owner[path] = c.get('id')
    return owner


def component_problems(m):
    """{component id: (files, problems)}: a card counts in every part one of its files belongs to."""
    target = m['target']
    components = target.get('current_components') or target.get('components') or []
    owner = _owners(components)
    counts = {c.get('id'): [c.get('files') or len(c.get('paths') or []), 0] for c in components}
    for r in m['rows']:
        for cid in {owner.get(p) for p in r['paths']} - {None}:
            counts[cid][1] += 1
    return {k: tuple(v) for k, v in counts.items()}


def group_counts(rows):
    """Counts and weight for a group of problem rows, shared by report views."""
    automatic = sum(row['auto'] for row in rows)
    return {'total': len(rows), 'automatic': automatic, 'decision': len(rows) - automatic,
            'weight': sum(SEVERITY_WEIGHT[row['severity']] * CONFIDENCE_WEIGHT.get(row['confidence'], 1.0) for row in rows)}


def closed_share(closed, total):
    return 100 * closed / total if total else 0


def card_counts(cards):
    closed = sum(card['state'] in CLOSED for card in cards)
    return {'total': len(cards), 'closed': closed, 'percent': closed_share(closed, len(cards))}


def milestone_counts(stone, cards, by_id):
    mine = [card for card in cards if card['milestone'] == stone.get('id')]
    total = len(mine or list(stone.get('tasks') or []))
    closed = card_counts(mine)['closed']
    return {'total': total, 'closed': closed, 'percent': round(closed_share(closed, total)),
            'automatic': sum(by_id[t]['auto'] for t in stone.get('tasks') or [] if t in by_id),
            'state': _milestone_state(total, closed)}


def _milestone_state(total, closed):
    return 'done' if total and closed == total else 'active' if closed else 'todo'
