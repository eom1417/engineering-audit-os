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

from ..plain import kind as plain_kind
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
# ux: how the screens look, from the visual reviewer's design cards; measured only in a check that pictured them.
AREAS = ('security', 'structure', 'quality', 'performance', 'ux', 'maintainability')
PATTERNS = {
    'access_gap': ('security', 'critical'), 'upgrade_dependency': ('security', 'high'),
    'broken_code': ('quality', 'high'), 'remove_dead': ('quality', 'low'), 'dead_code': ('quality', 'low'),
    'canonicalize': ('quality', 'low'), 'duplicated_rule': ('quality', 'medium'),
    'import_cycle': ('structure', 'medium'), 'mutable_state': ('structure', 'medium'), 'mutable_state_private': ('structure', 'low'),
    'hidden_coupling': ('structure', 'low'), 'external_write': ('structure', 'medium'),
    'policy_violation': ('structure', 'medium'),
    'load_blocker': ('performance', 'medium'), 'redundant_work': ('performance', 'medium'),
    'hotspot': ('maintainability', 'medium'), 'split_module': ('maintainability', 'medium'), 'trace_gap': ('maintainability', 'low'),
    'untested_path': ('maintainability', 'medium'), 'generic': ('maintainability', 'medium'),
    'design_review': ('ux', 'medium'), 'investigation': ('maintainability', 'low'),
}
CATEGORY_AREA = {'security': 'security', 'supply_chain': 'security', 'architecture': 'structure', 'data': 'structure',
                 'dead_code': 'quality', 'reliability': 'maintainability', 'maintainability': 'maintainability'}
# The stage whose failure leaves an area unmeasured.
AREA_STAGE = {'security': 'facts', 'structure': 'facts', 'quality': 'facts', 'performance': 'load', 'ux': 'visual',
              'maintainability': 'measure'}
# Areas whose stage is optional: measured only when that stage ran, never scored 100 for having looked at nothing.
AREA_OPTIONAL = {'ux'}
GRADES = ((90, 'excellent'), (75, 'good'), (60, 'fair'), (40, 'weak'), (0, 'critical'))
CLOSED = ('done',)
# eaos/ledger.py; 'resolved' is an older ledger's state (a problem no longer found), counted nowhere and shown nowhere.
CARD_STATES = ('done', 'resolved', 'on_branch', 'in_batch', 'open', 'skipped')


def _load(path, default):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


def classify(task, debt=None, category=None):
    """(area, severity) of one card: the PATTERNS table, with the debt register's severity when it has one."""
    pattern = plain_kind(task)
    area, severity = PATTERNS.get(pattern, PATTERNS['generic'])
    # An investigation (an unproven claim) stays in the area of what it is about.
    if pattern not in PATTERNS or pattern in ('generic', 'investigation'):
        area = CATEGORY_AREA.get(category, area)
    debt = debt or (task.get('design') or {}).get('severity')
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
    rows = [_problem_row(task, claims.get(task.get('claim_id')) or {}, debt.get(task.get('claim_id')) or {})
            for task in plan.get('tasks') or [] if isinstance(task, dict)]
    ranked = sorted((r['priority'] for r in rows), reverse=True)
    for row in rows:
        above = sum(1 for p in ranked if p > row['priority'])
        row['top'] = max(1, math.ceil((above + 1) * 100 / len(ranked)))
    return rows


def _problem_row(task, claim, item):
    area, severity = classify(task, item.get('severity'), item.get('category'))
    assessment = claim.get('assessment') or {}
    decision = task.get('decision') or {}
    return {'id': task.get('id', ''), 'pattern': plain_kind(task), 'area': area, 'severity': severity,
            'confidence': claim.get('confidence') or task.get('confidence') or 'CONFIRMED',
            'auto': task.get('kind') == 'remediate' and decision.get('readiness') == 'ready',
            'outcomes': decision.get('allowed_outcomes') or [], 'options': task.get('options') or [],
            'effort': task.get('effort'), 'change': assessment.get('proposed_change') or task.get('change') or '', 'priority': task.get('priority') or 0,
            'title': task.get('title') or claim.get('statement') or '', 'paths': task.get('paths') or [],
            'before': assessment.get('before') or task.get('before') or '',
            'after': assessment.get('after') or task.get('after') or ''}


def stage_status(report):
    manifest = _load(Path(report) / 'run-manifest.json', {}) or {}
    return {name: (row or {}).get('status') for name, row in (manifest.get('stages') or {}).items()}


def score(rows, source_files, statuses=None, known=True):
    """The health score and each area's score, from the formula in the module docstring.

    known is False when the report has no plan: then nothing was counted, and no area gets a score.
    """
    statuses = statuses or {}
    size = max(source_files or 0, 100) / 100
    areas = {area: _area_score(area, rows, size, known and _area_measured(area, statuses)) for area in AREAS}
    measured = [a['score'] for a in areas.values() if a['score'] is not None]
    overall = round(sum(measured) / len(measured)) if measured else None
    capped = any(r['severity'] == 'critical' and r['confidence'] == 'CONFIRMED' for r in rows)
    if overall is not None and capped: overall = min(overall, CRITICAL_CAP)
    grade = next(name for floor, name in GRADES if (overall or 0) >= floor) if overall is not None else None
    return {'score': overall, 'grade': grade, 'areas': areas, 'capped': capped, 'size': round(size * 100)}


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
            'counts': counts, 'total': len(mine), 'light': _light(value, counts) if measured else 'grey', 'measured': measured}


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
            'gap_matrix': {'rows': target.get('gap_matrix') or []}, 'manifest': _load(report / 'run-manifest.json', {}) or {},
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
    """Every card of the plan, with its ledger state (by its id in this plan). A ledger row without a plan card (a
    problem the check no longer finds, or one fixed and merged before it) is not a card: it never reaches a page, it
    only counts in the progress (gap_totals). With no ledger, a card kept by a batch is done and one that failed needs
    a decision, as before the ledger."""
    stones = {t: s.get('id') for s in m['plan'].get('milestones') or [] if isinstance(s, dict) for t in s.get('tasks') or []}
    ledger = ledger_of(m)
    kept, failed = waves_state(m['progress'])
    mine = {c.get('id'): c for c in (ledger or {}).get('cards') or [] if isinstance(c, dict) and c.get('id')}
    return [_task_card(r, mine.get(r['id']) or {}, stones, ledger, (kept, failed)) for r in m['rows']]


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
    if isinstance(given, dict):
        t.update({k: v for k, v in given.items() if isinstance(v, (int, float)) and not isinstance(v, bool)})
    t['percent'] = float(t['percent']) if 'percent' in (given or {}) else (100 * t['closed'] / t['total'] if t['total'] else 0.0)
    return t


def maps(report, target, pipeline_builder=None):
    """The architecture maps (eaos/arch_map.py) and the system map (eaos/system_map.py); a missing or broken fact
    record leaves its map None, and what failed is kept in map_errors for the page's warning and errors.json."""
    from .. import arch_map, system_map
    out = {'cmap': None, 'drill': None, 'flows': None, 'system': None, 'system_layout': None, 'pipeline': None, 'map_errors': []}
    def attempt(part, build):
        try: build()
        except Exception as error: out['map_errors'].append({'section': part, 'error': f'{type(error).__name__}: {error}'[:300]})
    def components():
        out['cmap'] = arch_map.component_map(report, target)
        out['drill'] = drill_counts(arch_map.drill_data(report, out['cmap']))
    def system():
        out['system'] = system_details(system_map.build(report))
        out['system_layout'] = system_map.layout(out['system'])
    attempt('architecture map', components)
    attempt('page flows', lambda: out.update(flows=arch_map.flow_charts(report)))
    attempt('system map', system)
    attempt('pipeline map', lambda: out.update(pipeline=(pipeline_builder or pipeline_sections)(report)))
    return out


def pipeline_sections(report):
    """The Studio's pipeline section in both languages (eaos/studio/pipeline.py), for the pipeline sheet; None when the
    check wrote no facts/pipeline.json."""
    from . import pipeline
    sections = {lang: pipeline.from_report(report, lang=lang) for lang in ('ar', 'en')}
    return sections if all(sections.values()) else None




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




def group_counts(rows):
    """Counts and weight for a group of problem rows, shared by report views."""
    automatic = sum(row['auto'] for row in rows)
    return {'total': len(rows), 'automatic': automatic, 'decision': len(rows) - automatic,
            'weight': sum(SEVERITY_WEIGHT[row['severity']] * CONFIDENCE_WEIGHT.get(row['confidence'], 1.0) for row in rows)}


def remaining(items, shown):
    return max(0, len(items) - shown)


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
            'state': 'done' if total and closed == total else 'active' if closed else 'todo'}


def structure_counts(target):
    current = target.get('current_components') or target.get('components') or []
    components = target.get('target_components') or []
    relations = {}
    for component in current:
        relation = component.get('relation')
        relations[relation] = relations.get(relation, 0) + 1
    return {'relations': relations, 'current': len(current), 'target': len(components),
            'layers': len({c.get('layer') for c in components}),
            'moves': sum(g.get('files_to_move') or 0 for g in target.get('gap_matrix') or [])}


def layer_counts(members):
    return {'parts': len(members), 'files': sum(c.get('files') or 0 for c in members)}


def density_counts(files, found):
    density = found / max(files, 1)
    return {'size': max(files, 1), 'density': density, 'per_ten': round(density * 10)}


def architecture_counts(cmap):
    return {'parts': len(cmap['nodes']), 'links': len(cmap['edges']),
            'loops': sum(e['cycle'] for e in cmap['edges']), 'wrong': sum(e['wrong'] for e in cmap['edges'])}


def system_counts(sm):
    counts = {key: len(sm[key]) for key in ('pages', 'callers', 'apis', 'handlers', 'modules', 'data')}
    counts.update(answered=sum(bool(a['handlers']) for a in sm['apis']),
                  tables=sum(d['id'].startswith('T:') for d in sm['data']),
                  untraced=sum(not p['traced'] for p in sm['pages']))
    counts['services'] = counts['data'] - counts['tables']
    counts['columns'] = (counts['pages'] + counts['callers'], counts['apis'], counts['handlers'], counts['modules'], counts['data'])
    return counts


def collection_count(items):
    return len(items)


def all_card_count(groups):
    return sum(len(cards) for _, _, cards in groups)


def problems_left(totals):
    return totals['total'] - totals['closed']


def unparsed_count(coverage):
    return (coverage.get('source_files') or 0) - (coverage.get('files_parsed') or 0)


def history_scale(points):
    top = max(h['percent'] for h in points)
    return next((s for s in (5, 10, 20, 25, 50, 100) if s >= top * 1.1), 100)


def history_ticks(points):
    scale = history_scale(points)
    return (0, scale / 2, scale)


def drill_counts(drill):
    """Displayed drill counts, including the same truncation as the drawing."""
    if not drill: return drill
    reverse = [[] for _ in drill['files']]
    for source, imports in enumerate(drill['imports']):
        for destination in imports: reverse[destination].append(source)
    for component in drill['comps']: component['counts'] = _component_counts(component, drill['imports'], reverse)
    outgoing, incoming = {}, {}
    for call in drill['calls']:
        outgoing.setdefault(call[0], []).append(call)
        incoming.setdefault(call[2], []).append(call)
    drill['file_counts'] = [_file_counts(f, own, outgoing.get(f, []), incoming.get(f, [])) for f, own in enumerate(drill['functions'])]
    return drill


def _component_counts(component, imports, reverse):
    files = sorted(component['files'], key=lambda f: -(len(reverse[f]) + len(imports[f])))[:30]
    selected = set(files)
    return {'inside': sum(g in selected for f in files for g in imports[f]),
            'shown': len(files), 'more': len(component['files']) - len(files),
            'used_by': len(component['used_by']), 'uses': len(component['uses'])}


def _file_counts(f, own, outgoing, incoming):
    """A file's functions, and the calls in and out of the 30 it draws (at most 14 a side)."""
    touched = {}
    for call in outgoing: touched[call[1]] = touched.get(call[1], 0) + 1
    for call in incoming: touched[call[3]] = touched.get(call[3], 0) + 1
    selected = set(sorted(own, key=lambda name: -touched.get(name, 0))[:30])
    left = {(c[0], c[1]) for c in incoming if c[0] != f and c[3] in selected}
    right = {(c[2], c[3]) for c in outgoing if c[2] != f and c[1] in selected}
    return {'own': len(own), 'left': min(len(left), 14), 'right': min(len(right), 14)}


def system_details(sm):
    """Counts shown by each selectable system node and feature."""
    if not sm: return sm
    for node in (node for group in ('pages', 'callers', 'apis', 'handlers', 'modules', 'data') for node in sm[group]):
        node['counts'] = _node_counts(node, sm['related'].get(node['id'], []))
    sm['feature_counts'] = {feature['name']: len(feature['pages']) for feature in sm['features']}
    return sm



def _node_counts(node, related):
    groups = {kind: sum(item.startswith(kind) and item != node['id'] for item in related) for kind in 'PCAHMTS'}
    return {'calls': len(node.get('calls') or []), 'shared': len(node.get('shared') or []),
            'pages': len(node.get('pages') or []), 'groups': groups,
            'more': {kind: max(0, count - 40) for kind, count in groups.items()}}


def pipeline_counts(section, pipelines=None, shown=60):
    """Scalar labels for the report's selected pipelines, from the Studio section."""
    pipelines = section.get('pipelines') or [] if pipelines is None else pipelines
    ids = {p['id'] for p in pipelines}
    confidence = section.get('confidence', {}).get('value')
    return {'stages': {p['id']: len(p['stages']) for p in pipelines},
            'drawn': {p['id']: sum(s['pipeline'] == p['id'] for s in section['stages']) for p in pipelines},
            'more': max(0, sum(s['pipeline'] in ids for s in section['stages']) - shown),
            'confidence': round(confidence * 100) if confidence is not None else '—'}
