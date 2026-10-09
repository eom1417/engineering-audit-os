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
    for component in drill['comps']:
        files = sorted(component['files'], key=lambda f: -(len(reverse[f]) + len(drill['imports'][f])))[:30]
        selected = set(files)
        component['counts'] = {'inside': sum(g in selected for f in files for g in drill['imports'][f]),
                               'shown': len(files), 'more': len(component['files']) - len(files),
                               'used_by': len(component['used_by']), 'uses': len(component['uses'])}
    outgoing, incoming = {}, {}
    for call in drill['calls']:
        outgoing.setdefault(call[0], []).append(call)
        incoming.setdefault(call[2], []).append(call)
    counts = []
    for f, own in enumerate(drill['functions']):
        touched = {}
        for call in outgoing.get(f, []): touched[call[1]] = touched.get(call[1], 0) + 1
        for call in incoming.get(f, []): touched[call[3]] = touched.get(call[3], 0) + 1
        selected = set(sorted(own, key=lambda name: -touched.get(name, 0))[:30])
        left = {(c[0], c[1]) for c in incoming.get(f, []) if c[0] != f and c[3] in selected}
        right = {(c[2], c[3]) for c in outgoing.get(f, []) if c[2] != f and c[1] in selected}
        counts.append({'own': len(own), 'left': min(len(left), 14), 'right': min(len(right), 14)})
    drill['file_counts'] = counts
    return drill


def system_details(sm):
    """Counts shown by each selectable system node and feature."""
    if not sm: return sm
    for group in ('pages', 'callers', 'apis', 'handlers', 'modules', 'data'):
        for node in sm[group]:
            related = sm['related'].get(node['id'], [])
            groups = {kind: sum(item.startswith(kind) and item != node['id'] for item in related) for kind in 'PCAHMTS'}
            node['counts'] = {'calls': len(node.get('calls') or []), 'shared': len(node.get('shared') or []),
                              'pages': len(node.get('pages') or []), 'groups': groups,
                              'more': {kind: max(0, count - 40) for kind, count in groups.items()}}
    sm['feature_counts'] = {feature['name']: len(feature['pages']) for feature in sm['features']}
    return sm


def percentage_text(value):
    value = float(value or 0)
    if value <= 0: return '0%'
    if value < 1: return '<1%'
    return f'{value:.1f}%'.replace('.0%', '%') if value < 10 else f'{round(value)}%'


def number_catalog(m):
    """Values by displayed meaning, from the report model; repeated contexts retain their candidate values."""
    values = {}
    def add(meaning, value):
        values.setdefault(meaning, set()).add(str(value))
    def fields(row, mapping):
        for key, meaning in mapping.items(): add(meaning, row[key])
    for meaning, value in {
        'the full score, and the file count a density is measured against': 100,
        'the cap when a confirmed critical problem exists': CRITICAL_CAP, 'the cap': CRITICAL_CAP,
        'weighted points per 100 files at which an area scores 50': HALF_POINT,
        'share of the weight a likely problem counts': '70%', 'files per size unit': 100,
        'minimum size in files': 100, 'full score': 100, 'half the full score': 50,
        'a quarter of the full score': 25, 'example rank': '10%',
    }.items(): add(meaning, value)
    for severity, weight in SEVERITY_WEIGHT.items(): add(f'weight of a {severity} problem', weight)
    for text in ('< 5', '5–10', '10–20', '20–40', '≥ 40'): add('problems per ten files', text)
    score_data, rows = m['score'], m['rows']
    add('health score out of 100, computed from the problems found (see How we computed)', score_data['score'])
    add('project size in files used by the formula', score_data['size'])
    add('source files that could not be read', unparsed_count(m['coverage']))
    for area, row in score_data['areas'].items():
        add(f'problems in {area}', row['total']); add(f'{area} score out of 100', row['score'])
        fields(row, {'total': 'problems in this area', 'points': 'weighted points of this area',
                     'density': 'weighted points per 100 files', 'score': 'area score out of 100'})
        add('all problems in this area', row['total'])
        for severity, count in row['counts'].items(): add(f'{severity} problems in this area', count)
    counts = group_counts(rows)
    fields(counts, {'automatic': 'problems EAOS can fix automatically', 'decision': 'problems that need the owner or a person to decide'})
    groups = {}
    for row in rows:
        groups.setdefault(row['pattern'], []).append(row)
        add(f'rank among all problems: in the top {row["top"]}%', f'{row["top"]}%')
        add('more files', remaining(row['paths'], 3))
    for index in range(1, min(len(groups), 5) + 1): add('position in the list of main problems', index)
    for index in range(1, len(m['plan'].get('milestones') or []) + 1): add('milestone order', index)
    for group in groups.values():
        counts = group_counts(group)
        for meaning in ('cards of this kind',): add(meaning, counts['total'])
        add('cases EAOS fixes automatically', counts['automatic'])
        waiting = [r for r in group if not r['auto']]
        add('cards waiting for a decision', len(waiting)); add('more cards', remaining(waiting, 40))
        for area in AREAS:
            mine = [r for r in group if r['area'] == area]
            add('problems of this kind', len(mine)); add('cases fixed automatically', group_counts(mine)['automatic'])
    target = m['target']; counts = structure_counts(target)
    for count in counts['relations'].values(): add('parts with this fate', count)
    fields(counts, {'current': 'parts of the project today', 'target': 'parts in the target structure',
                   'layers': 'layers in the target structure', 'moves': 'files that move to another place'})
    add('imports that go the wrong way between layers', target.get('forbidden_edges'))
    components = target.get('current_components') or target.get('components') or []
    component_counts = component_problems(m)
    for component in components:
        files, found = component_counts.get(component.get('id'), (0, 0))
        add('files in this part', files); add('problems in this part', found)
        add('problems per ten files in this part', density_counts(files, found)['per_ten'])
    for gap in target.get('gap_matrix') or []:
        add('problems found in this part', component_counts.get(gap.get('component'), (0, 0))[1])
        add('files that move to another place', gap.get('files_to_move') or 0)
        add('imports that break the target layering', gap.get('forbidden_imports') or 0)
    add('pieces of infrastructure the target adds', len([i for i in target.get('infrastructure') or [] if not i.get('present')]))
    # Cycle paths are the plan's witnesses, rather than all import edges.
    for row in rows:
        if row['pattern'] == 'import_cycle': add('files in this loop', len(row['paths']))
    cards = task_cards(m); totals = gap_totals(m, cards)
    fields(totals, {'closed': 'problems closed', 'total': 'problems in the plan, fixed ones included',
                   'new': 'problems a later check found for the first time'})
    add('share of the problems found that are closed: fixed and merged, or no longer found', percentage_text(totals['percent']))
    add('problems fixed and merged, or no longer found, so far', totals['closed'])
    add('problems left', problems_left(totals)); add('fixes on a branch waiting for your decision', totals['on_branch'])
    state_meanings = {'done': 'problems fixed by EAOS and merged into your main branch',
                     'resolved': 'problems a later check no longer found',
                     'on_branch': 'problems fixed on a branch that waits for your decision; not counted until merged',
                     'in_batch': 'problems in the batch being fixed now', 'skipped': 'problems set aside that need your decision',
                     'open': 'problems not started yet'}
    fields(totals, state_meanings)
    add('all task cards', len(cards)); add('fixes that were tried and did not pass', len(waves_state(m['progress'])[1]))
    by_id = {r['id']: r for r in rows}
    for stone in m['plan'].get('milestones') or []:
        counts = milestone_counts(stone, cards, by_id)
        fields(counts, {'closed': 'cards finished in this milestone', 'total': 'cards in this milestone',
                       'automatic': 'cards EAOS can fix automatically here'})
        add('share finished', f'{counts["percent"]}%')
    groups = {}
    for card in cards:
        groups.setdefault(card['milestone'], []).append(card)
        add('more files', remaining(card['paths'], 6)); add('batch number', card.get('batch'))
        add('the date its state last changed', str(card.get('at') or '')[:10])
    for group in groups.values():
        add('cards closed in this milestone', card_counts(group)['closed']); add('cards in this milestone', len(group))
    for index, wave in enumerate(m['progress'].get('waves') or [], 1):
        add('batch number', wave.get('number', index)); add('fixes kept in this batch', len(wave.get('kept') or []))
        add('fixes that did not pass in this batch', len(wave.get('failed') or {}))
    ledger = ledger_of(m) or {}
    add('the date the progress was last updated', str(ledger.get('updated') or '')[:10])
    for point in ledger.get('history') or []:
        add('date of this event', str(point.get('at') or '')[:10])
        add('problems closed by then', point.get('closed', 0)); add('problems in the plan then', point.get('total', 0))
        add('share of the gap closed by then', percentage_text(point.get('percent')))
    from ..arch_map import MAX_FILES, target_progress
    add('files shown per part at most', MAX_FILES)
    cmap = m.get('cmap')
    if cmap:
        counts = architecture_counts(cmap)
        fields(counts, {'parts': 'parts drawn', 'links': 'links between parts', 'loops': 'links inside a loop',
                       'wrong': 'links against the target layering'})
        add('parts left out of the drawing', cmap['capped'])
        for node in cmap['nodes']:
            fields(node, {'files': 'files in this part', 'used_by': 'parts that use it', 'uses': 'parts it uses',
                          'ca': 'imports coming in', 'ce': 'imports going out'})
            add('imports coming into this part', node['ca']); add('imports going out of this part', node['ce'])
            add('share of its imports that stay inside it', f'{node["cohesion"]}%')
        for edge in cmap['edges']: add('imports along this link', edge['n'])
    drill = m.get('drill')
    if drill:
        add('calls between functions left out', drill['capped']['calls'])
        for component in drill['comps']:
            add('files in this part', component['filecount'])
            add('share of its imports that stay inside it', f'{component["cohesion"]}%')
            fields(component['counts'], {'inside': 'imports between its files drawn', 'shown': 'files shown',
                                         'used_by': 'parts that use it', 'uses': 'parts it uses'})
        for counts in drill['file_counts']:
            fields(counts, {'own': 'named functions in this file', 'left': 'functions elsewhere that call this file',
                           'right': 'functions elsewhere this file calls'})
    for flow in m.get('flows') or []:
        add('calls traced from this page', flow['steps']); add('calls the trace cannot follow', flow['stops'])
    tcomps = [c for c in target.get('target_components') or [] if isinstance(c, dict) and c.get('name')]
    add('parts in the target structure', len(tcomps)); add('layers in the target', len({c.get('layer') or c.get('name') or '?' for c in tcomps}))
    add('links the target allows', len([e for e in target.get('target_edges') or [] if isinstance(e, dict)]))
    progress = target_progress(target, cards, CLOSED)
    for component in tcomps:
        closed, total = progress.get(component['name'], (0, 0))
        for meaning in ('problems closed in this target part', 'problems closed here'): add(meaning, closed)
        for meaning in ('problems in this target part', 'problems in this part'): add(meaning, total)
        for meaning in ('files that belong to this target part', 'files in this target part'): add(meaning, component.get('files') or 0)
        add('share closed', percentage_text(closed_share(closed, total)))
    sm = m.get('system')
    if sm:
        counts = system_counts(sm)
        fields(counts, {'pages': 'pages', 'apis': 'APIs', 'handlers': 'server files that answer requests',
                       'answered': 'APIs with a server handler found', 'tables': 'tables', 'services': 'services and storage',
                       'untraced': 'pages whose component file was not found'})
        add('APIs in the table', counts['apis']); add('APIs whose handler is unknown', sm['unknown'])
        add('APIs matched by file name only', sm['guessed'])
        for count in (sm.get('capped') or {}).values(): add('items left out of the drawing', count)
        for value, meaning in zip(counts['columns'], ('pages and shared files drawn', 'APIs drawn', 'server files drawn', 'parts drawn', 'tables and services drawn')): add(meaning, value)
        for page in sm['pages']:
            add('APIs called from this page’s own files', page['counts']['calls'])
            add('shared files this page reaches', page['counts']['shared'])
        for caller in sm['callers']:
            add('pages that reach this file', caller['counts']['pages']); add('APIs this file calls', caller['counts']['calls'])
        for group in ('pages', 'callers', 'apis', 'handlers', 'modules', 'data'):
            for node in sm[group]:
                for value in node['counts']['groups'].values(): add('related items of this kind', value)
                for value in node['counts']['more'].values(): add('more items', value)
        # The API table hides all but a small sample of the source records.
        pages = {p['id']: p['route'] for p in sm['pages']}
        callers = {c['id']: c['path'] for c in sm['callers']}
        for api in sm['apis']:
            reached = {pages[p] for p in sm['related'].get(api['id'], []) if p in pages}
            add('more pages', remaining(reached, 5))
            add('more files', remaining(api['callers'], 3))
            add('more tables and services', remaining(api['tables'] + api['services'], 5)); add('more features', remaining(api['features'], 3))
    add('the date of the audit', str((m['dossier'].get('provenance') or {}).get('generated_at') or '')[:10])
    handover = m['progress'].get('handover') or {}
    work = handover.get('open_work') or {}
    add('the number of the open batch', work.get('number') if work.get('number') is not None else work.get('milestone'))
    for key, meaning in {'kept': 'cards kept in the open batch', 'not_kept': 'cards not kept in the open batch', 'left': 'cards left in the open batch'}.items(): add(meaning, len(work.get(key) or []))
    busy = handover.get('in_progress') or {}
    add('more files read', remaining([f for f in busy.get('files_read') or [] if isinstance(f, str)], 8))
    def when(at): return str(at or '').replace('T', ' ')[:16]
    add('when this card was started (UTC)', when(busy.get('since')))
    add('the time of the last step (UTC)', when(handover.get('last_activity')))
    for step in handover.get('last_steps') or []: add('the time of this step (UTC)', when(step.get('at')))
    for note in handover.get('notes') or []: add('the time of this note (UTC)', when(note.get('at')))
    p = handover.get('progress') or {}
    add('cards closed', p.get('closed', 0)); add('cards in the plan', p.get('total', 0))
    add('when this page was built (UTC)', when((m['progress'].get('eaos') or {}).get('built')))
    pipeline = (m.get('pipeline') or {}).get('en')
    if pipeline:
        counts = pipeline_counts(pipeline)
        for section in m['pipeline'].values(): add('pipeline verdict', section['verdict'])
        for gap in pipeline['views']['gap']: add('pipeline gap explanation', gap['detail'])
        add('pipeline confidence percent', counts['confidence'])
        for count in counts['stages'].values(): add('stages in this pipeline', count)
        product = [p for p in pipeline['pipelines'] if p['role'] == 'product'] or pipeline['pipelines']
        add('more pipeline stages in the Studio', pipeline_counts(pipeline, product)['more'])
        for key, count in pipeline.get('counts', {}).items(): add(f'pipeline {key}', count.get('value', '—'))
        for n in range(1, min(len(pipeline['views']['gap']), 60) + 1): add('pipeline gap order', n)
    return {meaning: sorted(candidates) for meaning, candidates in sorted(values.items())}


def chart_catalog(m):
    """Numeric labels inside the report's SVG groups, with their model-owned source identifiers."""
    out = {}
    def add(meaning, numbers, literals=()):
        item = out.setdefault(meaning, {'numbers': [], 'literals': []})
        item['numbers'] = sorted(set(item['numbers']) | {str(n) for n in numbers})
        item['literals'] = sorted(set(item['literals']) | {str(n) for n in literals if n})
    for area, row in m['score']['areas'].items():
        add(f'{row["total"]} problems in {area}', [row['total']])
        for severity, count in row['counts'].items(): add(f'{count} {severity} problems in {area}', [count])
    target = m['target']; counts = component_problems(m)
    for component in target.get('current_components') or target.get('components') or []:
        files, found = counts.get(component.get('id'), (0, 0))
        name = component.get('name') or component.get('id') or ''
        root = target.get('root') or ''
        short = name[len(root):] if root and name.startswith(root) and len(name) > len(root) else name
        add(f'{files} files and {found} problems in {name}', [files, found], [name, short])
    layers = {}
    for component in target.get('target_components') or []:
        layers.setdefault(component.get('layer') or component.get('name') or '?', []).append(component)
    for name, members in layers.items():
        row = layer_counts(members)
        add(f'{row["parts"]} target parts and {row["files"]} files in the {name} layer', [row['parts'], row['files']], [name])
    cmap = m.get('cmap')
    if cmap:
        names = {node['id']: node['short'] for node in cmap['nodes']}
        for node in cmap['nodes']:
            add(f'{node["files"]} files; it uses {node["uses"]} other parts; {node["used_by"]} parts use it',
                [node['files'], node['uses'], node['used_by']], [node['name'], node['short']])
        for edge in cmap['edges']:
            add(f'{edge["n"]} imports from one part to the other', [edge['n']], [names[edge['from']], names[edge['to']]])
    from ..arch_map import target_progress
    progress = target_progress(target, task_cards(m), CLOSED)
    for component in target.get('target_components') or []:
        name = component.get('name') or ''
        closed, total = progress.get(name, (0, 0))
        files = component.get('files') or 0
        add(f'{files} files; {closed} of the {total} problems in its files are closed', [files, closed, total],
            [name, component.get('responsibility'), *(component.get('sub') or [])])
    for edge in target.get('target_edges') or []:
        if isinstance(edge, dict):
            count = edge.get('imports') or 1
            add(f'{count} imports the target allows along this link', [count], [edge.get('from'), edge.get('to')])
    history = [p for p in (ledger_of(m) or {}).get('history') or [] if isinstance(p, dict) and p.get('at') and isinstance(p.get('percent'), (int, float))]
    if history:
        add('share of the gap closed', [f'{tick:g}%' for tick in history_ticks(history)])
        add('date of this event', [str(p['at'])[:10] for p in history])
        add('share of the gap closed now', [percentage_text(history[-1]['percent'])])
        add('share of the gap closed on this date', [percentage_text(p['percent']) for p in history], [str(p['at'])[:10] for p in history])
    return out


def pipeline_counts(section, pipelines=None, shown=60):
    """Scalar labels for the report's selected pipelines, from the Studio section."""
    pipelines = section.get('pipelines') or [] if pipelines is None else pipelines
    ids = {p['id'] for p in pipelines}
    confidence = section.get('confidence', {}).get('value')
    return {'stages': {p['id']: len(p['stages']) for p in pipelines},
            'drawn': {p['id']: sum(s['pipeline'] == p['id'] for s in section['stages']) for p in pipelines},
            'more': max(0, sum(s['pipeline'] in ids for s in section['stages']) - shown),
            'confidence': round(confidence * 100) if confidence is not None else '—'}
