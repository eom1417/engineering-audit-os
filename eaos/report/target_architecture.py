"""Target architecture: the picture of what the codebase should look like.

Three things every target component must carry:

  origin         the file in the current codebase this component descends from
  relation       retain / modify / introduce / retire, the kind of move needed
  contracts      what the component promises: inputs, outputs, invariants

The matrix is the gap between current and target: every current component has
an origin in the target, every target component has an origin in the current.
The matrix is a fact about plans, not a claim about the future.
"""
import re
from collections import defaultdict
from pathlib import Path
from ..facts.store import read_set


NAME = 'target-architecture'
VERSION = '1'
LIMITATIONS = [
    'A target component is a proposal, not a guarantee; the engine does not write code.',
    'The relation (retain/modify/introduce/retire) is the engine\'s best read of the gap; a human '
    'reviewer may move a component from modify to retire or vice versa.',
    'A target component\'s contracts are derived from the source it descends from; new components '
    'have empty contracts until the engagement writes them.',
]


def _gather(out):
    sets = {}
    for name in ['syntax', 'graph', 'domain', 'fingerprint']:
        path = Path(out) / 'facts' / f'{name}.json'
        if path.is_file(): sets[name] = read_set(Path(out), name)
    return sets


# An architectural component is a package, not a symbol (eaos/analysis/target_projection.py holds the rule).
from ..analysis.target_projection import package_of  # noqa: E402


def components(sets, contracts_by_path=None):
    """One target component per package, carrying the files and symbols inside it.

    `contracts_by_path` lets the engagement declare contracts for known files; a package with no
    declared contract carries an empty list the reviewer fills in.
    """
    contracts_by_path = contracts_by_path or {}
    nodes = {fact['location']['path']: fact['value']
             for fact in sets.get('graph', {}).get('facts', []) if fact['kind'] == 'graph_node'}
    evidence = {fact['location']['path']: fact['id']
                for fact in sets.get('graph', {}).get('facts', []) if fact['kind'] == 'graph_node'}
    symbols = {}
    for fact in sets.get('syntax', {}).get('facts', []):
        if fact['kind'] == 'symbol':
            symbols.setdefault(fact['location']['path'], []).append(fact)
    paths = sorted(set(nodes) | set(symbols))
    grouped = {}
    for path in paths:
        grouped.setdefault(package_of(path), []).append(path)
    return [_package_component(package, members, (nodes, evidence, symbols), contracts_by_path)
            for package, members in sorted(grouped.items())]


def _package_component(package, members, indexes, contracts_by_path):
    """The target component of one package: its files, symbols, links, contracts and evidence."""
    nodes, evidence, symbols = indexes
    node_values = [nodes[path] for path in members if path in nodes]
    depends = sorted({package_of(target)
                      for value in node_values for target in (value.get('depends_on') or [])
                      if package_of(target) != package})
    return {
        'id': 'T-' + (package.replace('/', '.') if package else 'root'),
        'name': package or '(root)',
        'kind': 'package',
        'origin': package or '.',
        'relation': 'unassessed',
        'reason': 'no rule has been applied to this component yet',
        'responsibility': '',
        'owner': '',
        'paths': members,
        'files': len(members),
        'symbols': sum(len(symbols.get(path, [])) for path in members),
        'fan_in': sum(value.get('fan_in', 0) for value in node_values),
        'fan_out': sum(value.get('fan_out', 0) for value in node_values),
        'contracts': sorted({contract for path in members
                             for contract in contracts_by_path.get(path, [])}),
        'depends_on': depends,
        'evidence_ids': sorted({evidence[path] for path in members if path in evidence}),
        'source_component_id': None,
    }


def assess(component, sets, claims=None, load_record=None):
    """Give a component a relation, and the evidence for it.

    Every rule reads facts that already exist. "unassessed" survives only for a component no
    extraction reached, and it carries the reason. A verdict with no evidence is refused by
    the tests, because a target architecture whose every entry is a guess is worse than none.
    """
    if not component['symbols'] and not component['files']:
        return 'unassessed', 'no extractor reached this component', []
    live, cycles, violations, blockers = _signals(component, sets, claims, load_record)
    found = [(cycles, '{} dependency cycle(s) pass through it', [fact['id'] for fact in cycles]),
             (violations, '{} declared policy violation(s)', [fact['id'] for fact in violations]),
             (blockers, '{} load blocker(s) on its entry points', [reference for row in blockers for reference in row['evidence']]),
             (live, '{} live claim(s) about it', [claim['id'] for claim in live])]
    reasons = [words.format(len(rows)) for rows, words, _ in found if rows]
    if reasons:
        return 'modify', '; '.join(reasons), sorted({ref for _, _, ids in found for ref in ids})
    return 'retain', ('no cycle, no policy violation, no load blocker and no live claim touches it; '
                      'the evidence for keeping it is the absence of each'), sorted(component['evidence_ids'])


def _signals(component, sets, claims, load_record):
    """(live claims, dependency cycles, policy violations, load blockers) that touch the component's files."""
    paths = set(component.get('paths') or [])
    cycles = [fact for fact in sets.get('graph', {}).get('facts', [])
              if fact['kind'] == 'graph_cycle' and paths & set(fact['value'].get('members') or [])]
    violations = [fact for fact in sets.get('policy', {}).get('facts', [])
                  if fact['kind'] == 'policy_violation' and fact['location']['path'] in paths]
    blockers = []
    if load_record:
        from ..analysis.load_model import blockers as load_blockers
        blockers = [row for row in load_blockers(load_record) if row.get('path') in paths]
    return _live_claims(claims or [], paths), cycles, violations, blockers


def _live_claims(claims, paths):
    """The confirmed or likely claims, not withdrawn, about any of these files."""
    return [claim for claim in claims
            if paths & set((claim.get('priority_factors') or {}).get('paths') or [])
            and claim.get('confidence') in ('CONFIRMED', 'LIKELY') and claim.get('status') != 'withdrawn']


def assessment_details(component, sets, claims=None, load_record=None):
    live, cycles, violations, blockers = _signals(component, sets, claims, load_record)
    return {'live_claims': len(live), 'policy_violations': len(violations),
            'dependency_cycles': len(cycles), 'load_blockers': len(blockers)}


def _adr(component, number):
    relation = component['relation']
    measured = component.get('assessment') or {}
    paths = component.get('paths') or [component.get('origin') or component['id']]
    moved = (component.get('projection') or {})
    destination = component.get('target_component')
    if relation == 'delete':
        alternatives = [f"Delete the {moved.get('files', len(paths))} unreachable file(s) of `{component['origin']}` in one commit.",
                        'Keep them with an owner and a reason in eaos.engagement.json.',
                        'Do nothing and keep maintaining code no user reaches.']
    elif relation == 'rebuild' and destination:
        alternatives = [f"Rebuild `{component['origin']}` as `{destination}`: move {moved.get('moved', 0)} file(s) into it, "
                        f"remove {moved.get('forbidden', 0)} forbidden import(s), behind the behaviour lock.",
                        'Refactor it in place, one file at a time, without moving it.',
                        'Do nothing and keep the measured complexity, placement and risk.']
    elif relation == 'modify' and destination and (moved.get('moved') or moved.get('forbidden')):
        alternatives = [f"Move {moved.get('moved', 0)} file(s) of `{component['origin']}` into `{destination}` and "
                        f"break {moved.get('forbidden', 0)} forbidden import(s); the rest stays where it is.",
                        'Keep the files in place and add an adapter at the layer boundary.',
                        'Do nothing and keep the layer rules broken.']
    elif relation == 'introduce':
        alternatives = ['Introduce the component behind its declared contracts.',
                        'Extend the closest existing owner instead of adding a component.',
                        'Do nothing and leave the capability without an owner.']
    elif relation == 'retire':
        alternatives = ['Move callers to the named successor, then retire the component.',
                        'Keep a compatibility adapter at the current boundary.',
                        'Do nothing and keep maintaining the component.']
    elif measured.get('dependency_cycles'):
        alternatives = ['Break the cycle by moving the shared responsibility to its owning component.',
                        'Invert one dependency behind an interface at the current boundary.',
                        'Do nothing and retain the dependency cycle.']
    elif measured.get('load_blockers'):
        alternatives = ['Bound the entry path with rate limiting and explicit result pagination.',
                        'Cache repeated reads at the component boundary with an explicit lifetime.',
                        'Do nothing and accept the measured load blockers.']
    elif measured.get('policy_violations'):
        alternatives = ['Move the violating files to the layer that owns their responsibility.',
                        'Amend the declared policy with a reviewed exception and rationale.',
                        'Do nothing and retain the policy violation.']
    else:
        alternatives = ['Resolve the live claims inside the existing component boundary.',
                        'Split the claimed responsibility into a separately owned component.',
                        'Do nothing and retain the live claims.']
    action = alternatives[0]
    evidence = sorted(set(component.get('evidence_ids') or []))
    shown_evidence = evidence[:5]
    if len(evidence) > 5: shown_evidence.append(f'+{len(evidence) - 5} more evidence IDs')
    counts = (f"{measured.get('live_claims', 0)} live claim(s), "
              f"{measured.get('policy_violations', 0)} policy violation(s), "
              f"{measured.get('dependency_cycles', 0)} cycle(s), and "
              f"{measured.get('load_blockers', 0)} load blocker(s)")
    decision = {
        'id': f'ADR-{number:03d}',
        'component_id': component['id'],
        'problem': component.get('reason') or f'The component is assessed as {relation}.',
        'evidence': shown_evidence,
        'options': alternatives,
        'chosen': action,
        'tradeoffs': (f"The component has {counts}. The chosen option changes {len(paths)} file(s); "
                      'it keeps ownership at this boundary but requires its existing contracts to remain compatible.'),
        'consequences': [f'The component remains traceable as {relation}.',
                         'The cited evidence must be rechecked after migration.'],
        'migration': [f"Record the contract and acceptance check for `{path}`." for path in paths[:3]] +
                     [action, 'Run the acceptance check and update the evidence ledger.'],
    }
    validate_decision(decision)
    return decision


def validate_decision(decision):
    required = ('id', 'problem', 'evidence', 'options', 'chosen', 'tradeoffs',
                'consequences', 'migration')
    missing = [name for name in required if not decision.get(name)]
    if missing:
        raise ValueError('ADR is missing: ' + ', '.join(missing))
    options = decision['options']
    if not isinstance(options, list) or len(options) < 2:
        raise ValueError('ADR needs at least two options')
    if not any('do nothing' in str(option).lower() for option in options):
        raise ValueError('ADR options must include doing nothing')
    if decision['chosen'] not in options:
        raise ValueError('ADR chosen option must be one of its options')
    return decision


def decisions(components_list):
    candidates = [component for component in components_list
                  if component.get('relation') in {'modify', 'rebuild', 'delete', 'introduce', 'retire'}]
    return [_adr(component, number) for number, component in enumerate(candidates, 1)]


def render_decisions(out, records):
    """Every decision as a MADR file under adr/ (eaos/report/adr.py); stale files are removed."""
    from .adr import write_all
    for decision in records: validate_decision(decision)
    return write_all(out, records)


def current_gap(current, target_ids, claims, tasks):
    """The gap row of one of today's components: covered when it is retained with no open claim on its files, partial
    when a card closes its open claims, missing otherwise."""
    paths = set(current.get('paths') or [])
    open_claims = [claim for claim in claims
                   if claim.get('confidence') in {'CONFIRMED', 'LIKELY', 'HYPOTHESIS'}
                   and claim.get('status') != 'withdrawn'
                   and paths & set((claim.get('priority_factors') or {}).get('paths') or [])]
    claim_ids = {claim['id'] for claim in open_claims}
    blocking = sorted(task['id'] for task in tasks if task.get('claim_id') in claim_ids)
    if current.get('relation') == 'retain' and not open_claims:
        gap = 'covered'
    elif open_claims and blocking:
        gap = 'partial'
    else:
        gap = 'missing'
    return {'component': current['id'],
            'current': {'relation': current.get('relation'), 'origin': current.get('origin'),
                        'reason': current.get('reason')},
            'target': target_ids or [f"{current.get('relation')} {current['id']}"],
            'gap': gap,
            'evidence': sorted(set(current.get('evidence_ids') or []) | claim_ids),
            'blocking_tasks': blocking,
            # Compatibility names used by older machine consumers.
            'current_id': current['id'], 'current_origin': current['origin'],
            'target_ids': target_ids}


def gap_matrix(current_components, target_components, claims=None, tasks=None, stages=None):
    """Map every component to the evidence and executable work that closes its gap."""
    claims, tasks, stages = claims or [], tasks or [], stages or []
    by_source = defaultdict(list)
    for target in target_components:
        if target.get('source_component_id'):
            by_source[target['source_component_id']].append(target)
    rows = [current_gap(current, [target['id'] for target in by_source[current['id']]], claims, tasks)
            for current in current_components]
    for target in target_components:
        if target.get('relation') != 'introduce': continue
        paths = set(target.get('paths') or [])
        producing = [stage for stage in stages
                     if paths & ({site.get('path') for site in stage.get('sites', [])}
                                 | {stage.get('canonical_home')})]
        rows.append({'component': target['id'], 'current': None,
                     'target': [target['id']], 'gap': 'partial' if producing else 'missing',
                     'evidence': list(target.get('evidence_ids') or []),
                     'blocking_tasks': [f"TRANSFORM-{stage['stage']:03d}" for stage in producing],
                     'current_id': None, 'current_origin': None, 'target_ids': [target['id']]})
    return rows


def document(current, targets, decided, gaps, **more):
    """target-architecture.json, whichever journey drew it: a check, from today's code (build), or a build, from its plan
    (eaos/report/blueprint.py target). One shape for the reports, the Studio's maps and the assistant's `structure` tool: the
    target's parts are its layers, `target_edges` what each may use, `forbidden_edges` how many imports go against them.
    `more` starts with its `limits`, and may set the `status` (REVIEW_REQUIRED by default)."""
    return {'schema_version': 2, 'status': 'REVIEW_REQUIRED', 'current_components': current, 'components': targets or current,
            'target_components': targets, 'decisions': decided, 'gap_matrix': gaps, **more}


def _record(path, default):
    """A JSON record of the check, or `default` when it was not written."""
    import json
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else default


def _assess_all(current, sets, claims, load_record):
    # Every component gets a verdict from the evidence already collected, so the target is a
    # judgement about this codebase rather than a list of things nobody looked at.
    for component in current:
        relation, reason, evidence = assess(component, sets, claims, load_record)
        component['relation'] = relation
        component['reason'] = reason
        component['evidence_ids'] = sorted(set(component['evidence_ids']) | set(evidence))
        component['assessment'] = assessment_details(component, sets, claims, load_record)


def _apply_projection(current, projection):
    # The projection onto the project's reference type (eaos/analysis/target_projection.py) decides each component's
    # disposition and destination; the evidence-based reasons stay beside the numbers.
    for component in current:
        judged = projection['current'].get('' if component['origin'] == '.' else component['origin'])
        if not judged: continue
        earlier = component['reason'] if component['relation'] == 'modify' else ''
        component['relation'], component['target_component'] = judged['relation'], judged['target_component']
        component['reason'] = judged['reason'] + (f'; also: {earlier}' if earlier else '')
        component['projection'] = judged['stats']


def _proposed_targets(out, target_components, current):
    """The proposed target components (target-design.json when none is given), each checked against today's."""
    if target_components is None:
        data = _record(Path(out) / 'target-design.json', None)
        if data is not None and data.get('schema_version') != 1: raise ValueError('Unsupported target design')
        target_components = (data or {}).get('components')
    known, seen = {component['id'] for component in current}, set()
    for component in target_components or []: _check_target(component, known, seen)
    return target_components or []


def _check_target(component, known, seen):
    """One proposed component: a unique id, a valid relation, a known source unless it is new, and its evidence."""
    if not isinstance(component, dict) or not component.get('id') or component['id'] in seen:
        raise ValueError('Each target component needs a unique id')
    seen.add(component['id'])
    relation = component.get('relation')
    if relation not in {'retain', 'modify', 'introduce', 'retire'}: raise ValueError('Invalid target relation')
    if relation != 'introduce' and component.get('source_component_id') not in known:
        raise ValueError('Target component refers to an unknown source component')
    if not component.get('evidence_ids'): raise ValueError('Target component needs evidence')


def _carry_moves(matrix, current):
    """Each row of a component the projection moves names where it goes, how many files move and the imports it breaks."""
    for row in matrix:
        source = next((c for c in current if c['id'] == row['component']), None)
        if source and source.get('target_component'):
            row['target_component'] = source['target_component']
            row['files_to_move'] = (source.get('projection') or {}).get('moved', 0)
            row['forbidden_imports'] = (source.get('projection') or {}).get('forbidden', 0)


def build(out, contracts_by_path=None, target_components=None, target=None):
    """A source inventory is not a target design. Only explicit proposals enter the matrix."""
    sets = _gather(out)
    current = components(sets, contracts_by_path)
    claims = _record(Path(out) / 'dossier.json', {}).get('claims', [])
    _assess_all(current, sets, claims, _record(Path(out) / 'load-model.json', None))
    from ..analysis.target_projection import project
    projection = project(out, target)
    if projection: _apply_projection(current, projection)
    target_components = _proposed_targets(out, target_components, current)
    matrix = gap_matrix(current, target_components, claims, _record(Path(out) / 'plan.json', {}).get('tasks', []), [])
    _carry_moves(matrix, current)
    result = document(current, target_components, decisions([*current, *target_components]), matrix, limits=' '.join(LIMITATIONS),
                      retained_structure='Source inventory is shown below. Missing target decisions remain explicit gaps.')
    if projection:
        result.update(reference=projection['reference'], root=projection.get('root', ''), target_components=projection['target_components'],
                      infrastructure=projection['infrastructure'], forbidden_edges=len(projection['forbidden_edges']),
                      target_edges=projection['target_edges'])
    return result


# The ideal planner's operations as the target's relations; "new" names no component of today's code.
RELATION_OF = {'retain': 'retain', 'refactor': 'modify', 'merge': 'modify', 'rebuild': 'rebuild', 'delete': 'delete'}


def _slug(text):
    return re.sub(r'[^A-Za-z0-9_.:-]+', '-', str(text)).strip('-') or 'root'


def protected_paths(out, policy_path=None):
    """The files the owner protects: those of the critical features (features.json, and the intake's answer) and those
    the project's architecture policy places in a layer. A decision may not delete them."""
    import json
    from fnmatch import fnmatch
    out = Path(out)
    def load(path):
        try: return json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError, ValueError): return {}
    named = {q.get('id'): q.get('answer') for q in load(out / 'intake.json').get('questions') or [] if isinstance(q, dict)}
    critical = set(named.get('critical_features') or []) if isinstance(named.get('critical_features'), list) else set()
    files = {f for feature in load(out / 'features.json').get('features') or [] if isinstance(feature, dict)
             and (feature.get('critical') or feature.get('name') in critical) for f in feature.get('files') or []}
    policy = load(policy_path) if policy_path else {}
    globs = [g for paths in (policy.get('layers') or {}).values() for g in paths or []]
    return lambda path: path in files or any(fnmatch(path, g) for g in globs)


def _view(out):
    """The system view of this check's planned ideal, with the departures that say why: ([elements], {id: why})."""
    import json
    try: record = json.loads((Path(out) / 'ideal/plan.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): return [], {}
    ideal = record.get('ideal') or {}
    because = {str(d.get('element')): d.get('because') for d in ideal.get('departures') or []
               if isinstance(d, dict) and d.get('view') == 'system'}
    return [e for e in ((ideal.get('views') or {}).get('system') or {}).get('elements') or [] if isinstance(e, dict)], because


def _decide_current(component, element, why, protected, aside=frozenset()):
    """(label, why) of one of today's components: the rule stands when the assistant said nothing or when its decision
    breaks a guard (it stands only on cards or claims the triage set aside: two of the assistant's steps would
    contradict each other); otherwise the assistant's relation is the target's and the rule's is kept beside it."""
    rule = component['relation']
    if element is None: return 'rule_only', ''
    relation = RELATION_OF.get(element.get('operation'))
    if relation is None:
        return 'disagreement', f"\"{element.get('operation')}\" is not an operation on a component that exists today"
    cites = set(element.get('cites') or [])
    if relation != rule and cites and cites <= aside:
        return 'disagreement', 'it stands only on cards the triage set aside as false alarms'

    if relation == rule: return 'agreed', why       # the same answer is never a disagreement, whatever it is
    if relation == 'delete' and any(protected(path) for path in component.get('paths') or []):
        return 'disagreement', 'it would delete files the owner protects (a critical feature or the architecture policy)'
    component.update(relation=relation, reason=why or element.get('detail') or component.get('reason'),
                     evidence_ids=sorted(set(component.get('evidence_ids') or []) | set(element.get('cites') or [])))
    return 'ai_modified', why


def _decide_targets(targets, on, because, moving_to, disagreements):
    """The reference's target components the assistant kept, rejected or did not judge: a rejected one leaves the
    target unless today's components still move into it, then it stays as a disagreement."""
    kept = []
    for key, target in targets.items():
        element = on.get(key)
        rejected = element is not None and element.get('operation') == 'delete'
        label = _target_label(element, rejected, target.get('name') in moving_to)
        why = because.get(str((element or {}).get('id'))) or (element or {}).get('detail') or ''
        if label == 'disagreement': why = "today's components still move into it, so it stays: " + why
        target['decided_by'] = {'label': label, 'rule': 'new', 'assistant': (element or {}).get('operation'), 'why': why,
                                'cites': list((element or {}).get('cites') or [])}
        if rejected:
            disagreements.append({'element': key, 'rule': 'new', 'assistant': 'delete', 'label': label, 'why': why,
                                  'final': 'new' if label == 'disagreement' else 'delete', 'cites': target['decided_by']['cites']})
        if label != 'ai_modified': kept.append(target)
    return kept


def _target_label(element, rejected, moved_into):
    """rule_only when the assistant said nothing, agreed when it kept it; a rejected target leaves (ai_modified) unless
    today's components still move into it (disagreement)."""
    if element is None: return 'rule_only'
    if not rejected: return 'agreed'
    return 'disagreement' if moved_into else 'ai_modified'


def _added(elements, known, because):
    """The target components the assistant added: operation "new" on nothing that exists, each with its evidence."""
    out, seen = [], set()
    for element in elements:
        if element.get('operation') != 'new' or element.get('id') in known | seen or element.get('subject') in known: continue
        seen.add(element.get('id'))
        out.append({'name': element.get('title') or element['id'], 'layer': None, 'responsibility': element.get('detail', ''),
                    'paths': [], 'evidence_ids': list(element.get('cites') or []),
                    'decided_by': {'label': 'ai_added', 'rule': None, 'assistant': 'new', 'cites': list(element.get('cites') or []),
                                   'why': because.get(element['id']) or element.get('detail', '')}})
    return out


def _redraw_gaps(out, record, current):
    """The gap rows of today's components drawn again from their final relation, the confirmed cards and the claims
    the triage did not set aside; the rows of introduced components stay as proposed."""
    import json
    out = Path(out)
    def load(name, default):
        try: return json.loads((out / name).read_text(encoding='utf-8'))
        except (OSError, ValueError): return default
    aside = {row.get('claim_id') for row in load('cards.json', {}).get('set_aside') or []}
    claims = [c for c in load('dossier.json', {}).get('claims', []) if c.get('id') not in aside]
    tasks = load('plan.json', {}).get('tasks', [])
    by_id = {c['id']: c for c in current}
    rows = []
    for row in record.get('gap_matrix') or []:
        component = by_id.get(row.get('current_id'))
        if component is not None:
            row = {**row, **current_gap(component, row.get('target_ids') or [], claims, tasks),
                   'decided_by': component['decided_by']['label']}
        rows.append(row)
    return rows


def _elements_on(elements, known):
    """{component or target id: the assistant's first element about it} (by its own id, else by its subject)."""
    on = {}
    for element in elements:
        on.setdefault(element.get('id') if element.get('id') in known else element.get('subject'), element)
    return on


def _set_aside(out):
    """The cards and claims the triage set aside (cards.json)."""
    import json
    try: set_aside = json.loads((Path(out) / 'cards.json').read_text(encoding='utf-8')).get('set_aside') or []
    except (OSError, ValueError): set_aside = []
    return {row.get(key) for row in set_aside for key in ('card', 'claim_id') if row.get(key)}


def _decide_currents(current, on, because, guards):
    """Each of today's components decided (its `decided_by`); the disagreements between the rule and the assistant.
    `guards`: (protected path test, the set-aside cards and claims)."""
    protected, aside = guards
    disagreements = []
    for component in current:
        element = on.get(component['id'])
        rule, why = component['relation'], because.get(str((element or {}).get('id'))) or (element or {}).get('detail') or ''
        label, said = _decide_current(component, element, why, protected, aside)
        component['decided_by'] = {'label': label, 'rule': rule, 'why': said, 'cites': list((element or {}).get('cites') or []),
                                   'assistant': RELATION_OF.get((element or {}).get('operation'), (element or {}).get('operation'))}
        if label in ('ai_modified', 'disagreement'):
            disagreements.append({'element': component['id'], 'rule': rule, 'assistant': component['decided_by']['assistant'],
                                  'final': component['relation'], 'label': label, 'why': said, 'cites': component['decided_by']['cites']})
    return disagreements


def _label_counts(rows):
    counts = {}
    for row in rows: counts[row['decided_by']['label']] = counts.get(row['decided_by']['label'], 0) + 1
    return counts


def reconcile(out, planned=False, policy_path=None):
    """The final target from the rules' proposal (target-proposal.json) and, when the ideal was planned in this check,
    the assistant's decision on each of its components; the gap matrix is drawn again from it, without the claims of
    the cards the triage set aside (cards.json). Returns the record (render writes it) with `decided`, the count per
    label: agreed, ai_modified, rule_only, disagreement, ai_added, and `disagreements`, the rule's view beside the
    assistant's wherever they differ, and `aspects`: every aspect of the program with its verdict, keep or improve, and
    who gave it (eaos/analysis/aspects.py final)."""
    import json
    out = Path(out)
    source = out / 'target-proposal.json'
    record = json.loads((source if source.is_file() else out / 'target-architecture.json').read_text(encoding='utf-8'))
    elements, because = _view(out) if planned else ([], {})
    current = record['current_components']
    ids = {c['id'] for c in current}
    targets = {f"TC-{_slug(t.get('name') or t.get('id'))}": t for t in record.get('target_components') or [] if isinstance(t, dict)}
    on = _elements_on(elements, ids | set(targets))
    disagreements = _decide_currents(current, on, because, (protected_paths(out, policy_path), _set_aside(out)))
    final = _decide_targets(targets, on, because, {c.get('target_component') for c in current}, disagreements)
    added = _added(elements, ids | set(targets), because)
    final += added
    explicit = [c for c in record.get('components') or [] if c.get('id') not in ids]
    # Every proposal is counted, the target components the assistant rejected (no longer in the target) too.
    counts = _label_counts([*current, *targets.values(), *added])
    from ..analysis.aspects import final as aspects
    from ..ai.ideal import current as planned_ideal
    plan, state = planned_ideal(out) if planned else (None, 'not_planned')
    record.update(target_components=final, components=explicit or current, gap_matrix=_redraw_gaps(out, record, current),
                  decisions=decisions([*current, *explicit]), decided={'by': 'assistant' if elements else 'rules', **counts},
                  disagreements=disagreements, aspects=aspects(out, plan if state == 'planned' else None))
    return record
