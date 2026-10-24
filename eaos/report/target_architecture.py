"""Target architecture: the picture of what the codebase should look like.

Three things every target component must carry:

  origin         the file in the current codebase this component descends from
  relation       retain / modify / introduce / retire, the kind of move needed
  contracts      what the component promises: inputs, outputs, invariants

The matrix is the gap between current and target: every current component has
an origin in the target, every target component has an origin in the current.
The matrix is a fact about plans, not a claim about the future.

The matrix's rows are eaos/report/target_gaps.py's; the decisions about each component that changes
eaos/report/target_decisions.py's; the final target, as the rules and the person's assistant decided it,
eaos/report/target_reconcile.py's.
"""
from pathlib import Path
from ..facts.store import read_set
from .target_gaps import gap_matrix
from .target_decisions import decisions, render_decisions, validate_decision  # noqa: F401  (the tests and the pipeline read them here)
from .target_reconcile import _decide_current, reconcile  # noqa: F401  (the same)


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
        **_package_counts(members, node_values, symbols),
        'contracts': sorted({contract for path in members
                             for contract in contracts_by_path.get(path, [])}),
        'depends_on': _depends(node_values, package),
        'evidence_ids': sorted({evidence[path] for path in members if path in evidence}),
        'source_component_id': None,
    }


def _depends(node_values, package):
    """The other packages a package's files import."""
    return sorted({package_of(target)
                   for value in node_values for target in (value.get('depends_on') or [])
                   if package_of(target) != package})


def _package_counts(members, node_values, symbols):
    """A package's symbols, and the imports coming into and going out of its files."""
    return {'symbols': sum(len(symbols.get(path, [])) for path in members),
            'fan_in': sum(value.get('fan_in', 0) for value in node_values),
            'fan_out': sum(value.get('fan_out', 0) for value in node_values)}


def assess(component, sets, claims=None, load_record=None):
    """Give a component a relation, and the evidence for it.

    Every rule reads facts that already exist. "unassessed" survives only for a component no
    extraction reached, and it carries the reason. A verdict with no evidence is refused by
    the tests, because a target architecture whose every entry is a guess is worse than none.
    """
    if not component['symbols'] and not component['files']:
        return 'unassessed', 'no extractor reached this component', []
    found = _found(*_signals(component, sets, claims, load_record))
    reasons = [words.format(len(rows)) for rows, words, _ in found if rows]
    if reasons:
        return 'modify', '; '.join(reasons), sorted({ref for _, _, ids in found for ref in ids})
    return 'retain', ('no cycle, no policy violation, no load blocker and no live claim touches it; '
                      'the evidence for keeping it is the absence of each'), sorted(component['evidence_ids'])


def _found(live, cycles, violations, blockers):
    """[(rows, words, evidence ids)] of each kind of signal: cycles, policy violations, load blockers, live claims."""
    return [(cycles, '{} dependency cycle(s) pass through it', [fact['id'] for fact in cycles]),
            (violations, '{} declared policy violation(s)', [fact['id'] for fact in violations]),
            (blockers, '{} load blocker(s) on its entry points', [reference for row in blockers for reference in row['evidence']]),
            (live, '{} live claim(s) about it', [claim['id'] for claim in live])]


def _signals(component, sets, claims, load_record):
    """(live claims, dependency cycles, policy violations, load blockers) that touch the component's files."""
    paths = set(component.get('paths') or [])
    cycles = _cycles_through(sets, paths)
    violations = [fact for fact in sets.get('policy', {}).get('facts', [])
                  if fact['kind'] == 'policy_violation' and fact['location']['path'] in paths]
    blockers = []
    if load_record:
        from ..analysis.load_model import blockers as load_blockers
        blockers = [row for row in load_blockers(load_record) if row.get('path') in paths]
    return _live_claims(claims or [], paths), cycles, violations, blockers


def _cycles_through(sets, paths):
    """The dependency cycles that pass through any of these files."""
    return [fact for fact in sets.get('graph', {}).get('facts', [])
            if fact['kind'] == 'graph_cycle' and paths & set(fact['value'].get('members') or [])]


def _live_claims(claims, paths):
    """The confirmed or likely claims, not withdrawn, about any of these files."""
    return [claim for claim in claims
            if paths & set((claim.get('priority_factors') or {}).get('paths') or [])
            and claim.get('confidence') in ('CONFIRMED', 'LIKELY') and claim.get('status') != 'withdrawn']


def assessment_details(component, sets, claims=None, load_record=None):
    live, cycles, violations, blockers = _signals(component, sets, claims, load_record)
    return {'live_claims': len(live), 'policy_violations': len(violations),
            'dependency_cycles': len(cycles), 'load_blockers': len(blockers)}


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


