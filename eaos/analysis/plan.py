"""Build reviewable task cards with separate investigation and repair decisions.

An observed pattern does not establish a violation. Repairs need sourced requirements,
review and independent acceptance; investigations may conclude no change. The cards as documents are drawn in
eaos/analysis/plan_documents.py, the plan's order in eaos/analysis/plan_order.py.
"""
from pathlib import Path
from .card_review import (RESOLUTION_FIELDS, acceptance_for, apply_verdicts, cards_record, decided, fix_checks,
                          invariants_of, resolve, verify_command_for, what_to_do)
from ..core.decisions import decide, ready
from .impact import assess, load
from .plan_documents import PLAN_DIR, publish, title_of  # noqa: F401  (title_of: the Studio's cards read it here)
from .plan_order import sequence  # noqa: F401  (the pipeline's order stage reads it here)
from .ranking import claim_paths
from .remediation_patterns import pattern_for
from ..core.workspace import read, write

ACTIONABLE = {'CONFIRMED', 'LIKELY', 'HYPOTHESIS'}


def effort_for(radius, cost_bucket):
    if cost_bucket == 'large' or radius > 20: return 'كبير', 'منخفضة: لم يُقَس عمل مشابه بعد'
    if cost_bucket == 'medium' or radius > 5: return 'متوسط', 'متوسطة: مبني على حجم الكود ونطاق الأثر'
    return 'صغير', 'متوسطة: تغيير محصور في ملفات قليلة'


def size_of(paths, dependents):
    from .roadmap import effort
    return effort(paths, dependents)


def schedule(out, target, tasks):
    """Milestones and sections for the cards: the build milestones follow the target projection."""
    from .roadmap import milestones, sections
    from .target_projection import project
    projection = project(out, target)
    placements = (projection or {}).get('placements') or {}
    rebuilt = {}
    for judged in ((projection or {}).get('current') or {}).values():
        if judged['relation'] == 'rebuild': rebuilt[judged['target_component']] = 'rebuild'
    return milestones(tasks, placements, rebuilt), sections(tasks)


def _radius(out, paths, sets):
    """What a change to the paths reaches; nothing when there are no paths or the impact cannot be assessed."""
    if paths:
        try: return assess(out, paths, sets=sets)
        except ValueError: pass
    return {'direct_dependents': [], 'transitive_dependents': [], 'flows': [], 'covering_tests': [],
            'coverage': {}, 'entry_points': [], 'blast_radius': 0, 'change_partners': []}


def _task(index, claim, decision, context):
    """The card of one actionable claim; `context`: (target, out, fact sets)."""
    target, out, sets = context
    paths = claim_paths(claim, {}) or (claim.get('priority_factors') or {}).get('paths', [])
    radius = _radius(out, paths, sets)
    pattern = pattern_for(claim)
    unproven = decision['kind'] == 'investigate'
    cost = (claim.get('priority_factors') or {}).get('cost', {})
    effort, effort_confidence = effort_for(radius['blast_radius'], cost.get('bucket', 'medium'))
    assessment = claim.get('assessment') or {}
    change, options, rollback = what_to_do(claim, pattern, unproven)
    return {
        'id': 'TASK-%03d' % index, 'claim_id': claim['id'], 'title': claim['statement'][:120],
        'render': claim.get('render'),
        'kind': 'investigate' if unproven else 'remediate',
        'contract_version': 1, 'decision': decision,
        'prerequisites': [], 'before': assessment.get('before'),
        'after': assessment.get('after'),
        'requirement_refs': list(assessment.get('requirement_refs') or []),
        'status': 'planned', 'priority': claim.get('priority', 0),
        'pattern': 'investigation' if claim['confidence'] == 'HYPOTHESIS' else pattern['name'], 'paths': paths,
        'origin': claim.get('origin', 'unknown'),
        'impact': (claim.get('impact') or {}).get('scenario', ''),
        'impact_render': claim.get('render'),
        'evidence': {'fact_ids': claim.get('fact_ids', []), 'evidence_ids': claim.get('evidence_ids', []),
                     'probe_ids': claim.get('probe_ids', []), 'falsifier': claim['falsifier']},
        'blast_radius': {'direct_dependents': radius['direct_dependents'],
                         'transitive_dependents': radius['transitive_dependents'][:10],
                         'flows': radius['flows'], 'entry_points': radius['entry_points'],
                         'covering_tests': radius['covering_tests'],
                         'coverage': radius['coverage'], 'change_partners': radius['change_partners'],
                         'total': radius['blast_radius']},
        'change': change,
        'options': options,
        'rollback': rollback,
        'acceptance': acceptance_for(claim, target, out),
        'verify_command': verify_command_for(claim, target, out),
        'effort': size_of(paths, radius['blast_radius'])[0], 'effort_basis': size_of(paths, radius['blast_radius'])[1],
        'effort_confidence': 'A rule on the files it touches and its dependents (eaos/analysis/roadmap.py), not a measured duration.',
        'invariants': invariants_of(claim),
        'harm': harm_of(claim, radius, effort, effort_confidence),
        'finding_ids': [claim['id']],
    }


def _prerequisite(task, dependency, by_claim):
    """A prerequisite the claim's assessment names, on the card that carries that claim (none on the card itself)."""
    if dependency.get('claim_id') not in by_claim:
        raise ValueError('Unknown or non-actionable prerequisite claim')
    if not dependency.get('reason'): raise ValueError('Prerequisite needs a reason')
    if by_claim[dependency['claim_id']] != task['id']:
        task['prerequisites'].append({'task_id': by_claim[dependency['claim_id']], 'reason': dependency['reason']})


def _link_prerequisites(tasks, dossier):
    by_claim = {claim_id: task['id'] for task in tasks for claim_id in task['claim_ids']}
    source_claims = {claim['id']: claim for claim in dossier['claims']}
    for task in tasks:
        for dependency in (d for claim_id in task['claim_ids'] for d in (source_claims[claim_id].get('assessment') or {}).get('prerequisites', [])):
            _prerequisite(task, dependency, by_claim)


def build_tasks(target, out, dossier, sets, patterns=None):
    """The cards of every actionable claim; `patterns`: only the cards of those patterns (a check of some paths)."""
    tasks = []
    for claim in sorted(dossier['claims'], key=lambda row: (-row.get('priority', 0), row['id'])):
        if claim['confidence'] not in ACTIONABLE: continue
        decision = decide(claim)
        if decision['kind'] != 'retain': tasks.append(_task(len(tasks) + 1, claim, decision, (target, out, sets)))
    tasks = grouped([task for task in tasks if patterns is None or task['pattern'] in patterns])
    from .roadmap import section
    for task in tasks: task['section'] = section(task)
    _link_prerequisites(tasks, dossier)
    _split_last(tasks)
    from ..core.decisions import task_errors
    for task in tasks:
        errors = task_errors(task)
        if errors: raise ValueError('Invalid task: ' + '; '.join(errors))
    return tasks


def _split_last(tasks):
    """A module is split after its complex functions are simplified: split first, those functions move to new files
    and their cards no longer find them (EAOS, 2026-10-14: four files over 1000 lines with complexity cards). Only a card a
    batch can take is waited for: one awaiting the person's decision would hold the split forever."""
    for split in (t for t in tasks if t.get('pattern') == 'split_module'):
        for task in tasks:
            if task.get('pattern') == 'hotspot' and ready(task) and set(task['paths']) & set(split['paths']):
                split['prerequisites'].append({'task_id': task['id'],
                                               'reason': 'its complex functions are simplified before the module is split'})


# Kinds of card whose findings in one file are fixed by one change there: one card per (kind, file).
GROUPED = {'hotspot', 'split_module', 'dead_code', 'remove_dead', 'duplicated_rule', 'canonicalize'}


def grouped(tasks):
    """The cards with the findings of one kind in the same files (GROUPED) made one card: the most urgent one stands
    for them, every claim's id (`claim_ids`), facts and acceptance kept, the others named in `grouped`; then numbered
    again in order (TASK-001...)."""
    out, home = [], {}
    for task in tasks:
        task['claim_ids'] = [task['claim_id']]
        key = (task['pattern'], task['kind'], task.get('origin'), tuple(sorted(task['paths'])))
        first = home.get(key) if task['pattern'] in GROUPED and task['paths'] else None
        if first is None:
            home[key] = task
            out.append(task)
            continue
        first['claim_ids'].append(task['claim_id'])
        first['finding_ids'].append(task['claim_id'])
        first.setdefault('grouped', []).append({'claim_id': task['claim_id'], 'title': task['title'], 'render': task.get('render')})
        for name in ('fact_ids', 'evidence_ids', 'probe_ids'):
            first['evidence'][name] = list(dict.fromkeys(first['evidence'][name] + task['evidence'][name]))
        seen = {step['command'] for step in first['acceptance']}
        first['acceptance'] += [step for step in task['acceptance'] if step['command'] not in seen]
    for number, task in enumerate(out, 1): task['id'] = 'TASK-%03d' % number
    return out


UNKNOWN = 'unknown'


def harm_of(claim, radius, effort, effort_confidence):
    """Three different questions kept apart: what it costs the business, what it touches, what it costs us.

    Reach is measured and effort is estimated; business harm is neither unless someone evidenced it.
    Reporting a measured reach as if it were business harm is how a structural observation starts
    reading like an incident.
    """
    assessment = claim.get('assessment') or {}
    evidenced = assessment.get('business_harm') or (claim.get('impact') or {}).get('business_harm')
    return {
        'business': {'value': evidenced or UNKNOWN,
                     'basis': 'evidenced in the assessment' if evidenced else
                              'not established: no requirement or incident evidences a business cost'},
        'reach': {'value': radius['blast_radius'], 'basis': 'measured from the dependency graph',
                  'direct_dependents': len(radius['direct_dependents']), 'flows': len(radius['flows'])},
        'effort': {'value': effort, 'basis': effort_confidence},
    }


def conflicts(tasks):
    """Two tasks that touch the same file cannot be executed in the same wave."""
    graph = {task['id']: set() for task in tasks}
    for first in tasks:
        for second in tasks:
            if first['id'] == second['id']: continue
            if set(first['paths']) & set(second['paths']): graph[first['id']].add(second['id'])
    return graph


def _dependencies(tasks, by_id):
    """{task: the tasks it needs first}, every prerequisite checked to name a known task and a reason."""
    dependencies = {}
    for task in tasks:
        dependencies[task['id']] = set()
        for ref in task.get('prerequisites', []):
            if not isinstance(ref, dict) or not ref.get('reason'): raise ValueError('Prerequisite needs a reason')
            if ref.get('task_id') not in by_id: raise ValueError('Unknown prerequisite')
            dependencies[task['id']].add(ref['task_id'])
    return dependencies


def _wave_members(available, graph):
    """The available tasks, in order, that share no file with one taken before them."""
    members = []
    for task in available:
        if not graph[task['id']] & set(members): members.append(task['id'])
    return members


def waves(tasks):
    """Causal prerequisites and file conflicts are distinct constraints."""
    graph = conflicts(tasks)
    by_id = {task['id']: task for task in tasks}
    if len(by_id) != len(tasks): raise ValueError('Duplicate task id')
    dependencies = _dependencies(tasks, by_id)
    placed, result = {}, []
    while len(placed) < len(tasks):
        available = [task for task in tasks if task['id'] not in placed
                     and dependencies[task['id']] <= set(placed)]
        if not available: raise ValueError('Causal dependency cycle')
        available.sort(key=lambda task: (task['kind'] != 'investigate', -task['priority'], task['id']))
        members = _wave_members(available, graph)
        for identifier in members: placed[identifier] = len(result)
        result.append({'wave': len(result) + 1, 'tasks': members,
                       'entry_condition': 'Required predecessor decisions accepted; file conflicts serialized.',
                       'exit_condition': 'Record check outcomes or an evidenced investigation decision.'})
    return result


def rebuild(out, dossier, language='ar', target=None):
    """Regenerate the plan from a ledger that changed, without re-reading the target twice."""
    out = Path(out)
    sets = load(out)
    source = Path(target) if target else Path(dossier['provenance']['target'])
    tasks = build_tasks(source, out, dossier, sets)
    _write_plan((source, out), dossier, tasks, dossier.get('decisions', []), language)
    return len(tasks)


def _write_plan(where, dossier, tasks, decisions, language):
    """The cards and their waves into PLAN/, the dossier and plan.json, each mechanical card's codemod tried; the
    waves. `where`: (target, out)."""
    target, out = where
    plan = waves(tasks)
    publish(out / PLAN_DIR, tasks, plan, language)
    dossier['tasks'], dossier['waves'], dossier['plan_contract_version'] = tasks, plan, 1
    write(out / 'dossier.json', dossier)
    from .codemods import attach
    attach(tasks, out, target)
    plan_milestones, plan_sections = schedule(out, target, tasks)
    write(out / 'plan.json', {'contract_version': 1, 'tasks': tasks, 'waves': plan, 'milestones': plan_milestones, 'sections': plan_sections, 'decisions': decisions})
    return plan


def build(target, out, language='ar', patterns=None):
    target, out = Path(target).resolve(), Path(out).resolve()
    dossier_path = out / 'dossier.json'
    if not dossier_path.is_file(): raise ValueError('Build a dossier before planning: eaos dossier')
    dossier = read(dossier_path)
    sets = load(out)
    tasks = build_tasks(target, out, dossier, sets, patterns)
    plan = _write_plan((target, out), dossier, tasks, [decide(claim) for claim in dossier['claims']], language)
    directory = out / PLAN_DIR
    from .dossier import refresh_views
    refresh_views(out, language)
    return {'target': str(target), 'out': str(out), 'tasks': len(tasks), 'waves': len(plan),
            'cards': [str(directory / (task['id'] + '.md')) for task in tasks],
            'limits': 'Repairs require evidenced violations and independent checks. Investigations may conclude no change. Effort is an estimate with declared confidence, not a commitment.'}


def confirm(target, out, language='ar', triaged=False, reviewed=False):
    """The confirmed cards: when the triage ran in this check, its verdicts are applied once (apply_verdicts), a card
    it rejected leaves the plan (and with it the gaps) and stays only in cards.json `set_aside` with why, a
    prerequisite on it is dropped with why, and every other card carries its verdict and its claim's decision and
    priority drawn again (a doubted card needs a person's review); when the visual reviewer ran, its findings join the
    plan as design cards. The assistant's resolution of each card it confirmed (resolutions) then settles it: `fix`
    makes it ready work, `keep` closes it with why (cards.json `closed`), `owner` asks the person, at most one card in
    ten (cap_owner). The waves, milestones and cards are then drawn again. Without either every card stands as the
    rules wrote it. Writes cards.json, the record of who decided each card, and returns it."""
    target, out = Path(target).resolve(), Path(out).resolve()
    plan = read(out / 'plan.json')
    tasks = plan['tasks']
    verdicts, rejected, design, resolved = decided(out, tasks, triaged, reviewed)
    closed = {card for card, r in resolved.items() if r['resolution'] == 'keep'}
    from ..core.owner_share import cap_owner
    turned = cap_owner(resolved, len(tasks) - len(rejected) - len(closed) + len(design))
    revision = fix_checks((target, out), tasks, resolved, verdicts)
    _carry_resolutions(verdicts, resolved)
    claims = _apply_triage(out, plan, verdicts, (rejected, language))
    gone = rejected | closed
    kept = _standing(tasks, design, gone, closed)
    for task in kept: _settle(task, verdicts, (resolved, claims), (target, out, revision, gone, rejected))
    if rejected or verdicts or design:
        _publish_plan(target, out, plan, kept, language)
    record = cards_record((tasks, design, kept), verdicts, resolved, (rejected, closed, turned))
    write(out / 'cards.json', record)
    return record


def _carry_resolutions(verdicts, resolved):
    """Each triaged card's verdict carries the resolution the assistant gave it."""
    for card, row in resolved.items():
        if card in verdicts: verdicts[card] = {**verdicts[card], **{k: row[k] for k in RESOLUTION_FIELDS if k in row}}


def _standing(tasks, design, gone, closed):
    """The cards that stay: the plan's not gone, then the design cards not closed."""
    return [t for t in tasks if t['id'] not in gone] + [t for t in design if t['id'] not in closed]


def _apply_triage(out, plan, verdicts, how):
    """The triage's verdicts on the ledger, and each standing card's decision and priority drawn again from its claim;
    `how`: (the rejected cards, the language). {claim id: claim}, {} without verdicts."""
    if not verdicts: return {}
    rejected, language = how
    claims = apply_verdicts(out, plan['tasks'], verdicts, language)
    for task in plan['tasks']:
        claim = claims.get(task.get('claim_id'))
        if claim is not None and task['id'] not in rejected:
            task['decision'], task['priority'] = decide(claim), claim.get('priority', task['priority'])
    plan['decisions'] = read(out / 'dossier.json').get('decisions', plan.get('decisions', []))
    return claims


def _settle(task, verdicts, decided, context):
    """A card that stays: its verdict, its resolution, and its prerequisites on cards that left dropped with why.
    `decided`: (resolutions, claims); `context`: (target, out, revision, the cards gone, the cards rejected)."""
    resolved, claims = decided
    target, out, revision, gone, rejected = context
    verdict = verdicts.get(task['id'])
    if verdict: task['triage'] = {k: verdict.get(k) for k in ('decision', 'why', 'evidence', 'confidence', 'rejudged')}
    if task['id'] in resolved: resolve(task, resolved[task['id']], claims.get(task.get('claim_id')), target, out, revision)
    _drop_prerequisites(task, gone, rejected)


def _drop_prerequisites(task, gone, rejected):
    """The prerequisites on cards that left are dropped, each with why."""
    dropped = [ref for ref in task['prerequisites'] if ref.get('task_id') in gone]
    if not dropped: return
    task['prerequisites'] = [ref for ref in task['prerequisites'] if ref not in dropped]
    task['dropped_prerequisites'] = [{**ref, 'why': 'the triage set this card aside' if ref['task_id'] in rejected else
                                      'your assistant closed this card: not worth changing'} for ref in dropped]


def _publish_plan(target, out, plan, tasks, language):
    """plan.json, the dossier's cards and PLAN/ drawn again for `tasks`."""
    order = waves(tasks)
    publish(out / PLAN_DIR, tasks, order, language)
    dossier = read(out / 'dossier.json')
    dossier['tasks'], dossier['waves'] = tasks, order
    write(out / 'dossier.json', dossier)
    milestones, sections = schedule(out, target, tasks)
    write(out / 'plan.json', {**plan, 'tasks': tasks, 'waves': order, 'milestones': milestones, 'sections': sections})
