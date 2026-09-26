"""Target architecture: the picture of what the codebase should look like.

Three things every target component must carry:

  origin         the file in the current codebase this component descends from
  relation       retain / modify / introduce / retire, the kind of move needed
  contracts      what the component promises: inputs, outputs, invariants

The matrix is the gap between current and target: every current component has
an origin in the target, every target component has an origin in the current.
The matrix is a fact about plans, not a claim about the future.
"""
from collections import defaultdict
from pathlib import Path
from .facts.store import read_set


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


# An architectural component is a package, not a symbol (eaos/target_projection.py holds the rule).
from .target_projection import PACKAGE_ROOT, package_of  # noqa: E402,F401


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
    out = []
    for package, members in sorted(grouped.items()):
        node_values = [nodes[path] for path in members if path in nodes]
        depends = sorted({package_of(target)
                          for value in node_values for target in (value.get('depends_on') or [])
                          if package_of(target) != package})
        out.append({
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
        })
    return out


def assess(component, sets, claims=None, load_record=None):
    """Give a component a relation, and the evidence for it.

    Every rule reads facts that already exist. "unassessed" survives only for a component no
    extraction reached, and it carries the reason. A verdict with no evidence is refused by
    the tests, because a target architecture whose every entry is a guess is worse than none.
    """
    claims = claims or []
    paths = set(component['paths'])
    touching = [claim for claim in claims
                if paths & set((claim.get('priority_factors') or {}).get('paths') or [])]
    live = [claim for claim in touching
            if claim.get('confidence') in ('CONFIRMED', 'LIKELY') and claim.get('status') != 'withdrawn']
    cycles = [fact for fact in sets.get('graph', {}).get('facts', [])
              if fact['kind'] == 'graph_cycle' and paths & set(fact['value'].get('members') or [])]
    violations = [fact for fact in sets.get('policy', {}).get('facts', [])
                  if fact['kind'] == 'policy_violation' and fact['location']['path'] in paths]
    blockers = []
    if load_record:
        from .load_model import blockers as load_blockers
        blockers = [row for row in load_blockers(load_record) if row.get('path') in paths]
    if not component['symbols'] and not component['files']:
        return 'unassessed', 'no extractor reached this component', []
    reasons, evidence = [], []
    if cycles:
        reasons.append(f'{len(cycles)} dependency cycle(s) pass through it')
        evidence += [fact['id'] for fact in cycles]
    if violations:
        reasons.append(f'{len(violations)} declared policy violation(s)')
        evidence += [fact['id'] for fact in violations]
    if blockers:
        reasons.append(f'{len(blockers)} load blocker(s) on its entry points')
        evidence += [reference for row in blockers for reference in row['evidence']]
    if live:
        reasons.append(f'{len(live)} live claim(s) about it')
        evidence += [claim['id'] for claim in live]
    if reasons:
        return 'modify', '; '.join(reasons), sorted(set(evidence))
    return 'retain', ('no cycle, no policy violation, no load blocker and no live claim touches it; '
                      'the evidence for keeping it is the absence of each'), sorted(component['evidence_ids'])


def assessment_details(component, sets, claims=None, load_record=None):
    claims = claims or []
    paths = set(component.get('paths') or [])
    live = [claim for claim in claims
            if paths & set((claim.get('priority_factors') or {}).get('paths') or [])
            and claim.get('confidence') in ('CONFIRMED', 'LIKELY') and claim.get('status') != 'withdrawn']
    cycles = [fact for fact in sets.get('graph', {}).get('facts', [])
              if fact['kind'] == 'graph_cycle' and paths & set(fact['value'].get('members') or [])]
    violations = [fact for fact in sets.get('policy', {}).get('facts', [])
                  if fact['kind'] == 'policy_violation' and fact['location']['path'] in paths]
    blockers = []
    if load_record:
        from .load_model import blockers as load_blockers
        blockers = [row for row in load_blockers(load_record) if row.get('path') in paths]
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
    """Every decision as a MADR file under adr/ (eaos/adr.py); stale files are removed."""
    from .adr import write_all
    for decision in records: validate_decision(decision)
    return write_all(out, records)


def gap_matrix(current_components, target_components, claims=None, tasks=None, stages=None):
    """Map every component to the evidence and executable work that closes its gap."""
    claims, tasks, stages = claims or [], tasks or [], stages or []
    by_source = defaultdict(list)
    for target in target_components:
        if target.get('source_component_id'):
            by_source[target['source_component_id']].append(target)
    rows = []
    for current in current_components:
        matches = by_source[current['id']]
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
        target_ids = [target['id'] for target in matches]
        rows.append({'component': current['id'],
                     'current': {'relation': current.get('relation'), 'origin': current.get('origin'),
                                 'reason': current.get('reason')},
                     'target': target_ids or [f"{current.get('relation')} {current['id']}"],
                     'gap': gap,
                     'evidence': sorted(set(current.get('evidence_ids') or []) | claim_ids),
                     'blocking_tasks': blocking,
                     # Compatibility names used by older machine consumers.
                     'current_id': current['id'], 'current_origin': current['origin'],
                     'target_ids': target_ids})
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


def build(out, contracts_by_path=None, target_components=None, target=None):
    """A source inventory is not a target design. Only explicit proposals enter the matrix."""
    import json
    sets = _gather(out)
    current = components(sets, contracts_by_path)
    # Every component gets a verdict from the evidence already collected, so the target is a
    # judgement about this codebase rather than a list of things nobody looked at.
    dossier_path = Path(out) / 'dossier.json'
    claims = json.loads(dossier_path.read_text(encoding='utf-8')).get('claims', []) \
        if dossier_path.is_file() else []
    load_path = Path(out) / 'load-model.json'
    load_record = json.loads(load_path.read_text(encoding='utf-8')) if load_path.is_file() else None
    for component in current:
        relation, reason, evidence = assess(component, sets, claims, load_record)
        component['relation'] = relation
        component['reason'] = reason
        component['evidence_ids'] = sorted(set(component['evidence_ids']) | set(evidence))
        component['assessment'] = assessment_details(component, sets, claims, load_record)
    # The projection onto the project's reference type (eaos/target_projection.py) decides each component's
    # disposition and destination; the evidence-based reasons above stay beside the numbers.
    from .target_projection import project
    projection = project(out, target)
    if projection:
        for component in current:
            judged = projection['current'].get('' if component['origin'] == '.' else component['origin'])
            if not judged: continue
            earlier = component['reason'] if component['relation'] == 'modify' else ''
            component['relation'], component['target_component'] = judged['relation'], judged['target_component']
            component['reason'] = judged['reason'] + (f'; also: {earlier}' if earlier else '')
            component['projection'] = judged['stats']
    proposal = Path(out) / 'target-design.json'
    if target_components is None and proposal.is_file():
        data = json.loads(proposal.read_text())
        if data.get('schema_version') != 1: raise ValueError('Unsupported target design')
        target_components = data.get('components')
    target_components = target_components or []
    known = {component['id'] for component in current}
    seen = set()
    for component in target_components:
        if not isinstance(component, dict) or not component.get('id') or component['id'] in seen:
            raise ValueError('Each target component needs a unique id')
        seen.add(component['id'])
        relation = component.get('relation')
        if relation not in {'retain', 'modify', 'introduce', 'retire'}: raise ValueError('Invalid target relation')
        if relation != 'introduce' and component.get('source_component_id') not in known:
            raise ValueError('Target component refers to an unknown source component')
        if not component.get('evidence_ids'): raise ValueError('Target component needs evidence')
    plan_path = Path(out) / 'plan.json'
    plan_tasks = json.loads(plan_path.read_text(encoding='utf-8')).get('tasks', []) \
        if plan_path.is_file() else []
    transform_path = Path(out) / 'transform-plan.json'
    transform_stages = json.loads(transform_path.read_text(encoding='utf-8')).get('stages', []) \
        if transform_path.is_file() else []
    matrix = gap_matrix(current, target_components, claims, plan_tasks, transform_stages)
    for row in matrix:
        source = next((c for c in current if c['id'] == row['component']), None)
        if source and source.get('target_component'):
            row['target_component'] = source['target_component']
            row['files_to_move'] = (source.get('projection') or {}).get('moved', 0)
            row['forbidden_imports'] = (source.get('projection') or {}).get('forbidden', 0)
    architectural_decisions = decisions([*current, *target_components])
    result = {'schema_version': 2, 'status': 'REVIEW_REQUIRED',
              'retained_structure': 'Source inventory is shown below. Missing target decisions remain explicit gaps.',
              'current_components': current, 'components': target_components or current,
              'target_components': target_components,
              'decisions': architectural_decisions, 'gap_matrix': matrix,
              'limits': ' '.join(LIMITATIONS)}
    if projection:
        result.update(reference=projection['reference'], target_components=projection['target_components'],
                      infrastructure=projection['infrastructure'], forbidden_edges=len(projection['forbidden_edges']),
                      target_edges=projection['target_edges'])
        place_features(out, projection['features'])
    return result


def place_features(out, placement):
    """Write each feature's target component into features.json: the same features, in the target."""
    import json
    path = Path(out) / 'features.json'
    if not path.is_file(): return
    record = json.loads(path.read_text(encoding='utf-8'))
    for feature in record.get('features') or []:
        feature['target_component'] = placement.get(feature['name'])
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


# The component inventory belongs in the record; the document names the shape of the target.
SHOWN_COMPONENTS = 12
SHOWN_DECISIONS = 8


def render(out, target, language='ar'):
    """Render the target architecture as a Markdown document."""
    ar = language == 'ar'
    render_decisions(out, target['decisions'])
    lines = []
    if ar:
        lines += ['# البنية المستهدفة', '',
                  '> جرد المصدر منفصل عن التصميم المستهدف؛ ما لم يُحدد ويُراجع يبقى فجوة.', '']
    else:
        lines += ['# Target architecture', '',
                  '> Source inventory and reviewed target proposals are separate. Unspecified targets remain gaps.', '']
    if target.get('reference'):
        lines += ['## ' + ('النوع المرجعي والمكوّنات المستهدفة' if ar else 'Reference type and target components'), '',
                  (f"النوع: `{target['reference']}` (وحدة واحدة معيارية). {len(target['target_components'])} مكوّنًا مستهدفًا، "
                   f"و{target.get('forbidden_edges', 0)} استيرادًا ممنوعًا تزيله الخطة." if ar else
                   f"Type: `{target['reference']}` (a modular monolith). {len(target['target_components'])} target components; "
                   f"{target.get('forbidden_edges', 0)} forbidden imports the plan removes."), '',
                  '| ' + (' | '.join(['المكوّن', 'الطبقة', 'الملفات', 'تنتقل إليه', 'استيرادات ممنوعة']) if ar else
                         ' | '.join(['Component', 'Layer', 'Files', 'Moving in', 'Forbidden imports'])) + ' |',
                  '|---|---|---:|---:|---:|']
        shown = sorted(target['target_components'], key=lambda c: (-c.get('moves_in', 0), -c.get('files', 0), c['name']))[:15]
        for component in shown:
            lines.append(f"| `{component['name']}` | {component['layer']} | {component.get('files', 0)} | "
                         f"{component.get('moves_in', 0)} | {component.get('forbidden_edges_removed', 0)} |")
        if len(target['target_components']) > len(shown):
            lines += ['', (f"عُرض {len(shown)} من {len(target['target_components'])}؛ البقية في `target-architecture.json`." if ar else
                           f"Showing {len(shown)} of {len(target['target_components'])}; the rest are in `target-architecture.json`.")]
        lines += ['', '## ' + ('قرارات البنية التحتية' if ar else 'Infrastructure decisions'), '']
        for item in target.get('infrastructure') or []:
            mark = '✅' if item['present'] else '⬜'
            tool = item['tool'] or (('بلا أداة: ' if ar else 'no tool: ') + (item.get('tool_reason') or ''))
            lines.append(f"- {mark} **{item['area']}**: {item['decision']} ({tool}). "
                         + ('الدليل: ' if ar else 'Evidence: ') + item['evidence'])
        lines.append('')
    lines += ['## ' + ('البنية المحفوظة' if ar else 'Retained structure'), '']
    lines += [target['retained_structure']]
    lines += ['', '## ' + ('المكوّنات' if ar else 'Components')]
    by_relation = defaultdict(list)
    for component in target['components']:
        by_relation[component['relation']].append(component)
    for relation in ['unassessed', 'delete', 'rebuild', 'modify', 'retain', 'introduce', 'retire']:
        rows = by_relation.get(relation, [])
        if not rows: continue
        lines += ['', '### ' + relation.capitalize() + f' ({len(rows)})']
        for component in rows[:SHOWN_COMPONENTS]:
            where = f" → `{component['target_component']}`" if component.get('target_component') else ''
            lines += [f"- `{component['id']}` ← `{component['origin']}`{where}: {component['name']}"]
        if len(rows) > SHOWN_COMPONENTS:
            lines += [('- … البقية في `target-architecture.json`' if ar
                       else '- … the rest are in `target-architecture.json`')]
    lines += ['', '## ' + ('القرارات المعمارية' if ar else 'Architectural decisions')]
    for adr in target['decisions'][:SHOWN_DECISIONS]:
        lines += ['', f"### {adr['id']}: {adr.get('problem', '')}"]
        lines += ['- ' + ('المشكلة' if ar else 'problem') + f": {adr.get('problem', '')}"]
        lines += ['- ' + ('البدائل' if ar else 'options') + ":"]
        for option in adr.get('options', []): lines += [f"  - {option}"]
        lines += ['- ' + ('المختار' if ar else 'chosen') + f": {adr.get('chosen', '')}"]
        lines += ['- ' + ('المقايضة' if ar else 'tradeoffs') + f": {adr.get('tradeoffs', '')}"]
    if len(target['decisions']) > SHOWN_DECISIONS:
        lines += ['', (f"عُرض {SHOWN_DECISIONS} قرارًا من {len(target['decisions'])}؛ البقية في "
                       '`target-architecture.json`.' if ar else
                       f"Showing {SHOWN_DECISIONS} of {len(target['decisions'])} decisions; the rest are in "
                       '`target-architecture.json`.')]
    lines += ['', '## ' + ('مصفوفة الفجوة' if ar else 'Gap matrix')]
    covered = sum(1 for row in target['gap_matrix'] if row['gap'] == 'covered')
    lines += [f"- {'مغطى' if ar else 'covered'}: {covered} / {len(target['gap_matrix'])}"]
    Path(out, 'TARGET-ARCHITECTURE.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    Path(out, 'target-architecture.json').write_text(json_dumps(target), encoding='utf-8')
    return {'markdown': str(Path(out, 'TARGET-ARCHITECTURE.md')),
            'json': str(Path(out, 'target-architecture.json'))}


def json_dumps(obj):
    import json
    return json.dumps(obj, ensure_ascii=False, indent=2) + '\n'
