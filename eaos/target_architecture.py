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
from .facts import digest


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


# An architectural component is a package, not a symbol. Building one per symbol produced 10,938
# "components" on a 1,031-file repository, which is a symbol listing rather than an architecture.
PACKAGE_ROOT = ''


def package_of(path):
    """The architectural unit a file belongs to: its directory, or the root for a top-level file."""
    parent = str(Path(path).parent)
    return PACKAGE_ROOT if parent in ('.', '') else parent


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
    if relation == 'introduce':
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
                  if component.get('relation') in {'modify', 'introduce', 'retire'}]
    return [_adr(component, number) for number, component in enumerate(candidates, 1)]


def render_decisions(out, records):
    directory = Path(out) / 'docs' / 'adr'
    directory.mkdir(parents=True, exist_ok=True)
    expected = set()
    for decision in records:
        validate_decision(decision)
        path = directory / f"{decision['id']}.md"
        expected.add(path.name)
        lines = [f"# {decision['id']}: {decision['problem']}", '',
                 f"Component: `{decision['component_id']}`", '', '## Evidence', '']
        lines += [f'- `{item}`' for item in decision['evidence']]
        lines += ['', '## Options', '']
        lines += [f'{index}. {option}' for index, option in enumerate(decision['options'], 1)]
        lines += ['', '## Chosen', '', decision['chosen'], '', '## Tradeoffs', '',
                  decision['tradeoffs'], '', '## Consequences', '']
        lines += [f'- {item}' for item in decision['consequences']]
        lines += ['', '## Migration', '']
        lines += [f'{index}. {step}' for index, step in enumerate(decision['migration'], 1)]
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    for path in directory.glob('ADR-*.md'):
        if path.name not in expected:
            path.unlink()


def gap_matrix(current_components, target_components):
    """For each current component, what target component descends from it, if any."""
    by_source = defaultdict(list)
    for target in target_components:
        if target.get('source_component_id'):
            by_source[target['source_component_id']].append(target)
    rows = []
    for current in current_components:
        matches = by_source[current['id']]
        complete = matches and all(t.get('contracts') and t.get('responsibility') and t.get('evidence_ids')
                                   and t.get('relation') in {'retain', 'modify', 'retire'} for t in matches)
        rows.append({'current_id': current['id'], 'current_origin': current['origin'],
                     'target_ids': [t['id'] for t in matches],
                     'gap': 'covered' if complete else 'incomplete_contract' if matches else 'unassessed'})
    return rows


def build(out, contracts_by_path=None, target_components=None):
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
    matrix = gap_matrix(current, target_components)
    architectural_decisions = decisions([*current, *target_components])
    return {'schema_version': 2, 'status': 'REVIEW_REQUIRED',
            'retained_structure': 'Source inventory is shown below. Missing target decisions remain explicit gaps.',
            'current_components': current, 'components': target_components or current,
            'target_components': target_components,
            'decisions': architectural_decisions, 'gap_matrix': matrix,
            'limits': ' '.join(LIMITATIONS)}


# The component inventory belongs in the record; the document names the shape of the target.
SHOWN_COMPONENTS = 12
SHOWN_DECISIONS = 12


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
    lines += ['## ' + ('البنية المحفوظة' if ar else 'Retained structure'), '']
    lines += [target['retained_structure']]
    lines += ['', '## ' + ('المكوّنات' if ar else 'Components')]
    by_relation = defaultdict(list)
    for component in target['components']:
        by_relation[component['relation']].append(component)
    for relation in ['unassessed', 'retain', 'modify', 'introduce', 'retire']:
        rows = by_relation.get(relation, [])
        if not rows: continue
        lines += ['', '### ' + relation.capitalize() + f' ({len(rows)})']
        for component in rows[:SHOWN_COMPONENTS]:
            lines += [f"- `{component['id']}` ← `{component['origin']}`: {component['name']}"]
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
