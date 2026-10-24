"""The gap matrix of the target (target-architecture.json gap_matrix, eaos/report/target_architecture.py): every
component of today and every one the target introduces, with the evidence and the cards or stages that close its gap."""
from collections import defaultdict

def current_gap(current, target_ids, claims, tasks):
    """The gap row of one of today's components: covered when it is retained with no open claim on its files, partial
    when a card closes its open claims, missing otherwise."""
    open_claims = _open_claims(claims, set(current.get('paths') or []))
    claim_ids = {claim['id'] for claim in open_claims}
    blocking = sorted(task['id'] for task in tasks if task.get('claim_id') in claim_ids)
    return {'component': current['id'],
            'current': {'relation': current.get('relation'), 'origin': current.get('origin'),
                        'reason': current.get('reason')},
            'target': target_ids or [f"{current.get('relation')} {current['id']}"],
            'gap': _gap(current, open_claims, blocking),
            'evidence': sorted(set(current.get('evidence_ids') or []) | claim_ids),
            'blocking_tasks': blocking,
            # Compatibility names used by older machine consumers.
            'current_id': current['id'], 'current_origin': current['origin'],
            'target_ids': target_ids}


def _open_claims(claims, paths):
    """The claims, not withdrawn, of any confidence a card may close, about any of these files."""
    return [claim for claim in claims
            if claim.get('confidence') in {'CONFIRMED', 'LIKELY', 'HYPOTHESIS'}
            and claim.get('status') != 'withdrawn'
            and paths & set((claim.get('priority_factors') or {}).get('paths') or [])]


def _gap(current, open_claims, blocking):
    """covered (retained, no open claim), partial (cards close its open claims) or missing."""
    if current.get('relation') == 'retain' and not open_claims: return 'covered'
    if open_claims and blocking: return 'partial'
    return 'missing'


def gap_matrix(current_components, target_components, claims=None, tasks=None, stages=None):
    """Map every component to the evidence and executable work that closes its gap."""
    claims, tasks, stages = claims or [], tasks or [], stages or []
    by_source = _by_source(target_components)
    rows = [current_gap(current, [target['id'] for target in by_source[current['id']]], claims, tasks)
            for current in current_components]
    rows += [_introduced_row(target, stages) for target in target_components if target.get('relation') == 'introduce']
    return rows


def _by_source(target_components):
    """{today's component id: the target components that descend from it}."""
    by_source = defaultdict(list)
    for target in target_components:
        if target.get('source_component_id'):
            by_source[target['source_component_id']].append(target)
    return by_source


def _introduced_row(target, stages):
    """The gap row of a component the target introduces: partial when a transform stage produces any of its files."""
    paths = set(target.get('paths') or [])
    producing = [stage for stage in stages
                 if paths & ({site.get('path') for site in stage.get('sites', [])}
                             | {stage.get('canonical_home')})]
    return {'component': target['id'], 'current': None,
            'target': [target['id']], 'gap': 'partial' if producing else 'missing',
            'evidence': list(target.get('evidence_ids') or []),
            'blocking_tasks': [f"TRANSFORM-{stage['stage']:03d}" for stage in producing],
            'current_id': None, 'current_origin': None, 'target_ids': [target['id']]}
