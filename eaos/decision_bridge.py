"""One decision contract for both planners, so the executor asks the same question of either.

The deterministic planner writes a typed decision onto every task. The older agent-led roadmap
writes a different record with none. Before this module the executor trusted whatever it was
handed, which meant a task could be executed without anyone having established that a change was
justified. It now adapts the older record into the same contract and refuses what the contract
refuses — an investigation, a blocked repair, or a record too old to interpret.
"""
from .decisions import VERSION, check_errors

NEEDS_REVALIDATION = 'needs_revalidation'


def from_roadmap(task, findings=None, gates=None):
    """Read a legacy roadmap task as a decision, deriving nothing it does not actually state."""
    findings = {row['id']: row for row in (findings or [])}
    gates = {row['id']: row for row in (gates or [])}
    blockers = []
    kind = {'remediate': 'repair', 'investigate': 'investigate'}.get(task.get('kind'))
    if kind is None:
        blockers.append(f"unknown legacy task kind {task.get('kind')!r}")
        kind = 'investigate'
    referenced = task.get('finding_ids') or []
    if kind == 'repair':
        if not referenced:
            blockers.append('a repair with no finding behind it')
        for identifier in referenced:
            finding = findings.get(identifier)
            if finding is None:
                blockers.append(f'finding {identifier} is referenced but absent')
            elif finding.get('claim_status') != 'CONFIRMED':
                blockers.append(f'finding {identifier} is {finding.get("claim_status")}, not CONFIRMED')
        if not task.get('evidence_ids'):
            blockers.append('no evidence reference on a repair')
        if not (task.get('required_gate_ids') or []):
            blockers.append('no acceptance gate declared')
        for identifier in task.get('required_gate_ids') or []:
            if gates and identifier not in gates:
                blockers.append(f'gate {identifier} is required but not declared')
    readiness = ('needs_review' if kind == 'investigate' else
                 'blocked' if blockers else 'ready')
    return {'contract_version': VERSION, 'observation_uid': task.get('id'), 'kind': kind,
            'reason': 'Adapted from the agent-led roadmap record; its own fields were not reinterpreted.',
            'readiness': readiness, 'blockers': sorted(set(blockers)),
            'checks': [], 'allowed_outcomes': ['repair', 'retain', 'blocked_missing_requirement']
            if kind == 'investigate' else [], 'source': 'roadmap'}


def decision_of(task, findings=None, gates=None):
    """The decision governing a task, whichever planner produced it."""
    if task.get('contract_version') == VERSION and task.get('decision'):
        return dict(task['decision'], source='plan')
    if task.get('decision'):
        return dict(task['decision'], source='plan', readiness=NEEDS_REVALIDATION,
                    blockers=sorted(set(list(task['decision'].get('blockers') or []) +
                                        ['the record predates the decision contract and needs revalidation'])))
    return from_roadmap(task, findings, gates)


def executable(task, findings=None, gates=None):
    """May this task be executed? Returns (allowed, reasons). Never raises on a malformed task."""
    decision = decision_of(task, findings, gates)
    reasons = []
    if decision['readiness'] == NEEDS_REVALIDATION:
        reasons.append('the record predates the decision contract and needs revalidation')
    if decision['kind'] == 'investigate':
        reasons.append('an investigation concludes with a decision, not with a code change')
    elif decision['kind'] == 'retain':
        reasons.append('the decision was to retain; there is nothing to execute')
    elif decision['kind'] != 'repair':
        reasons.append(f"unknown decision kind {decision['kind']!r}")
    if decision.get('blockers'):
        reasons += list(decision['blockers'])
    if decision['kind'] == 'repair' and decision['readiness'] != 'ready':
        reasons.append(f"readiness is {decision['readiness']}, not ready")
    for check in decision.get('checks') or []:
        reasons += check_errors(check)
    return (not reasons), {'decision': decision, 'refusals': sorted(set(reasons))}
