"""The target's architecture decisions (target-architecture.json decisions, the MADR files of adr/): one per component
that changes, with its problem, evidence, options (doing nothing among them), the chosen one, trade-offs, consequences
and migration (eaos/report/target_architecture.py draws the target they decide)."""

def _adr(component, number):
    relation = component['relation']
    measured = component.get('assessment') or {}
    paths = component.get('paths') or [component.get('origin') or component['id']]
    alternatives = _alternatives(component, measured, paths)
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


# The options of a decision that moves nothing: by the relation, else by what was measured, the live claims last.
OPTIONS = {
    'introduce': ['Introduce the component behind its declared contracts.',
                  'Extend the closest existing owner instead of adding a component.',
                  'Do nothing and leave the capability without an owner.'],
    'retire': ['Move callers to the named successor, then retire the component.',
               'Keep a compatibility adapter at the current boundary.',
               'Do nothing and keep maintaining the component.'],
    'dependency_cycles': ['Break the cycle by moving the shared responsibility to its owning component.',
                          'Invert one dependency behind an interface at the current boundary.',
                          'Do nothing and retain the dependency cycle.'],
    'load_blockers': ['Bound the entry path with rate limiting and explicit result pagination.',
                      'Cache repeated reads at the component boundary with an explicit lifetime.',
                      'Do nothing and accept the measured load blockers.'],
    'policy_violations': ['Move the violating files to the layer that owns their responsibility.',
                          'Amend the declared policy with a reviewed exception and rationale.',
                          'Do nothing and retain the policy violation.'],
    'live_claims': ['Resolve the live claims inside the existing component boundary.',
                    'Split the claimed responsibility into a separately owned component.',
                    'Do nothing and retain the live claims.'],
}


def _alternatives(component, measured, paths):
    """A decision's options, the chosen one first: those of a move when the component moves, else OPTIONS'."""
    moving = _move_options(component, paths)
    if moving: return moving
    if component['relation'] in ('introduce', 'retire'): return list(OPTIONS[component['relation']])
    return list(OPTIONS[next((key for key in ('dependency_cycles', 'load_blockers', 'policy_violations') if measured.get(key)), 'live_claims')])


def _move_options(component, paths):
    """The options of a component deleted, rebuilt into its target, or modified with files to move; None otherwise."""
    relation, moved, destination = component['relation'], component.get('projection') or {}, component.get('target_component')
    if relation == 'delete':
        return [f"Delete the {moved.get('files', len(paths))} unreachable file(s) of `{component['origin']}` in one commit.",
                'Keep them with an owner and a reason in eaos.engagement.json.',
                'Do nothing and keep maintaining code no user reaches.']
    if relation == 'rebuild' and destination:
        return [f"Rebuild `{component['origin']}` as `{destination}`: move {moved.get('moved', 0)} file(s) into it, "
                f"remove {moved.get('forbidden', 0)} forbidden import(s), behind the behaviour lock.",
                'Refactor it in place, one file at a time, without moving it.',
                'Do nothing and keep the measured complexity, placement and risk.']
    if relation == 'modify' and destination and (moved.get('moved') or moved.get('forbidden')):
        return [f"Move {moved.get('moved', 0)} file(s) of `{component['origin']}` into `{destination}` and "
                f"break {moved.get('forbidden', 0)} forbidden import(s); the rest stays where it is.",
                'Keep the files in place and add an adapter at the layer boundary.',
                'Do nothing and keep the layer rules broken.']
    return None


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
