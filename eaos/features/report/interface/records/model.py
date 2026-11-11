"""The one model of a report the records are built from: every card with its area, severity and state, and the score.

What a problem is: one task card of plan.json. Its area and severity come from eaos/kernel/contracts/card_areas.py; the
severity recorded for the card's claim in debt-register.json wins over the pattern's default. Confidence is the claim's.

The health score, derived only from those cards:
    weight of a problem   = severity weight (critical 10, high 5, medium 2, low 1)
                            x confidence weight (CONFIRMED 1.0, LIKELY 0.7, HYPOTHESIS 0.4;
                              eaos/features/plan/analysis/ranking.py)
    density of an area    = sum of its weights per 100 source files (a project under 100 files counts as 100)
    area score            = 100 x 20 / (20 + density)   (20 weighted points per 100 files halve the score)
    health score          = the mean of the measured areas' scores; a confirmed critical problem caps it at 39
An area whose checking stage failed or was not reached is left out of the mean.
A security card the assistant closed as not worth changing (cards.json `closed`: a vulnerable library with no fixed
version) is an accepted risk, not a solved one: it still weighs on the security score.
"""
from pathlib import Path

from .....kernel.contracts.card_areas import AREAS, classify
from .....kernel.contracts.decisions import unattended
from .....kernel.language.plain import kind as plain_kind
from ....plan.analysis.ranking import CONFIDENCE_WEIGHT
from .....kernel.system.files import read_json

SEVERITY_WEIGHT = {'critical': 10, 'high': 5, 'medium': 2, 'low': 1}
HALF_POINT = 20          # weighted points per 100 files at which an area scores 50
CRITICAL_CAP = 39
# The stage whose failure leaves an area unmeasured.
AREA_STAGE = {'security': 'facts', 'structure': 'facts', 'quality': 'facts', 'performance': 'baseline', 'ux': 'visual',
              'maintainability': 'measure'}
# Areas whose stage is optional: measured only when that stage ran, never scored 100 for having looked at nothing
# (performance: the speed under load measured on the running program, not the code read alone).
AREA_OPTIONAL = {'ux', 'performance'}
CLOSED = ('done',)
# eaos/kernel/project/ledger.py; 'resolved' marks a problem the check does not find any more, counted nowhere.
CARD_STATES = ('done', 'resolved', 'on_branch', 'in_batch', 'open', 'skipped')


def _ledger(report):
    """({claim id: claim}, {claim id: debt register item}) of a report."""
    dossier = read_json(report / 'dossier.json', {}) or {}
    register = read_json(report / 'debt-register.json', {}) or {}
    return ({c.get('id'): c for c in dossier.get('claims') or [] if isinstance(c, dict)},
            {i.get('claim_id'): i for i in register.get('items') or [] if isinstance(i, dict) and i.get('claim_id')})


def problems(report):
    """One row per plan card, with its area, severity and confidence."""
    report = Path(report)
    plan = read_json(report / 'plan.json', {}) or {}
    ledger = _ledger(report)
    return [_row_of(task, task.get('claim_id'), ledger) for task in plan.get('tasks') or [] if isinstance(task, dict)]


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


def _problem_row(task, claim, item):
    area, severity = classify(task, item.get('severity'), item.get('category'))
    return {'id': task.get('id', ''), 'pattern': plain_kind(task), 'area': area, 'severity': severity,
            'confidence': claim.get('confidence') or task.get('confidence') or 'CONFIRMED',
            'auto': unattended(task),
            'title': task.get('title') or claim.get('statement') or '', 'paths': task.get('paths') or []}


def stage_status(manifest):
    return {name: (row or {}).get('status') for name, row in (manifest.get('stages') or {}).items()}


def score(rows, source_files, statuses=None, known=True):
    """The health score 0..100 or None, from the formula in the module docstring; None when the report has no plan
    (`known` False) or no area was measured."""
    statuses = statuses or {}
    size = max(source_files or 0, 100) / 100
    measured = [_area_score(area, rows, size) for area in AREAS if known and _area_measured(area, statuses)]
    overall = round(sum(measured) / len(measured)) if measured else None
    return min(overall, CRITICAL_CAP) if overall is not None and _capped(rows) else overall


def _capped(rows):
    """Whether a confirmed critical problem caps the score."""
    return any(r['severity'] == 'critical' and r['confidence'] == 'CONFIRMED' for r in rows)


def _area_measured(area, statuses):
    status = statuses.get(AREA_STAGE[area])
    return status not in ('failed', 'not_reached') and (area not in AREA_OPTIONAL or status == 'ok')


def _area_score(area, rows, size):
    points = sum(SEVERITY_WEIGHT[r['severity']] * CONFIDENCE_WEIGHT.get(r['confidence'], 1.0) for r in rows
                 if r['area'] == area)
    return round(100 * HALF_POINT / (HALF_POINT + points / size))


def records(report, progress=None):
    """Every record the sections read, with the cards and the score computed once."""
    report = Path(report)
    dossier = read_json(report / 'dossier.json', {}) or {}
    rows = problems(report)
    manifest = read_json(report / 'run-manifest.json', {}) or {}
    coverage = dossier.get('coverage') or {}
    plan = read_json(report / 'plan.json', {}) or {}
    known = isinstance(plan.get('tasks'), list)
    return {'rows': rows, 'plan': plan, 'manifest': manifest, 'dossier': dossier, 'progress': progress or {},
            'score': score(rows + accepted_risks(report), coverage.get('source_files'), stage_status(manifest), known)}


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
    problem this check does not find, or one fixed and merged before it) is not a card. With no ledger, a card kept by
    a batch is done and one that failed needs a decision."""
    stones = _milestone_of(m['plan'])
    ledger = ledger_of(m)
    kept, failed = waves_state(m['progress'])
    mine = _ledger_cards(ledger)
    return [_task_card(r, mine.get(r['id']) or {}, stones, ledger, (kept, failed)) for r in m['rows']]


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
    return {'id': r['id'], 'key': c.get('key') or r['id'], 'title': r['title'], 'pattern': r['pattern'],
            'severity': r['severity'],
            'milestone': c.get('milestone') or stones.get(r['id']), 'paths': r['paths'],
            'state': _card_state(r, c, ledger, kept, failed)}

