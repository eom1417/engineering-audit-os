"""Versioned decision contract: observed does not imply defective or executable."""
import hashlib
import json

VERSION = 1


def identity(claim):
    # Location and probe semantics distinguish similarly worded observations.
    probe = claim.get('probe_spec') or {}
    specification = {key: value for key, value in probe.get('specification', {}).items() if key != 'expected'}
    payload = {'claim_type': claim.get('claim_type'), 'probe_type': probe.get('probe_type'),
               'specification': specification, 'legacy_id': claim.get('legacy_id')}
    if not specification:
        payload['paths'] = sorted((claim.get('priority_factors') or {}).get('paths', []))
        payload['statement'] = ' '.join(claim.get('statement', '').split()).lower()
    return 'OBS-' + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:24]


def check_errors(check):
    problems = []
    if not isinstance(check, dict): return ['check must be an object']
    for field in ('id', 'invariant', 'expected', 'source_revision'):
        if not isinstance(check.get(field), str) or not check[field].strip(): problems.append('missing ' + field)
    if check.get('kind') not in {'command', 'human'}: problems.append('unsupported check kind')
    if check.get('kind') == 'command':
        argv = check.get('argv')
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
            problems.append('argv must be a nonempty string array')
        elif any(x in {'dossier', 'facts', 'tasks'} for x in argv[:3]):
            problems.append('report regeneration is not behavioral acceptance')
        if type(check.get('expected_exit')) is not int: problems.append('expected_exit is required')
        if check.get('cwd', '.') != '.': problems.append('cwd must be the candidate root')
    elif not check.get('rubric'): problems.append('human check needs a rubric')
    return problems


def decide(claim):
    disposition = claim.get('disposition') or {}
    assessment = claim.get('assessment') or {}
    if not isinstance(assessment, dict): raise ValueError('assessment must be an object')
    checks = claim.get('checks') or []
    if not isinstance(checks, list): raise ValueError('checks must be an array')
    reasons = []
    if claim.get('confidence') == 'REFUTED':
        kind, reason = 'retain', 'The claim was refuted; no repair is justified.'
    elif disposition.get('kind') == 'accepted' and disposition.get('owner') and disposition.get('reason'):
        kind, reason = 'retain', disposition['reason']
    elif claim.get('origin') == 'test' and not assessment.get('violated_invariant'):
        kind, reason = 'retain', 'Test or fixture observation: no product violation established; retain for review.'
    elif (claim.get('confidence') == 'CONFIRMED' and assessment.get('violated_invariant')
          and assessment.get('requirement_refs') and assessment.get('evidence_refs')):
        kind, reason = 'repair', 'A confirmed observation violates an explicitly evidenced requirement.'
    else:
        kind, reason = 'investigate', 'Establish the requirement and consequence before proposing a code change.'
    if kind == 'repair':
        if not checks: reasons.append('No acceptance check attached.')
        for check in checks: reasons.extend(check_errors(check))
        if not assessment.get('reviewed_by'): reasons.append('The engineering decision has not been reviewed.')
        if not assessment.get('before') or not assessment.get('after'): reasons.append('Before/after behavior is missing.')
    return {'contract_version': VERSION, 'observation_uid': claim.get('uid') or identity(claim),
            'kind': kind, 'reason': reason,
            'readiness': 'needs_review' if kind == 'investigate' else
                         'blocked' if reasons else 'ready' if kind == 'repair' else 'no_change',
            'blockers': sorted(set(reasons)), 'checks': checks if kind == 'repair' else [],
            'allowed_outcomes': ['repair', 'retain', 'blocked_missing_requirement'] if kind == 'investigate' else []}


def task_errors(task):
    if task.get('contract_version') != VERSION: return ['legacy task needs revalidation']
    decision = task.get('decision') or {}
    errors = []
    if decision.get('kind') not in {'repair', 'investigate', 'retain'}: errors.append('unknown decision kind')
    if task.get('kind') == 'remediate' and decision.get('kind') != 'repair': errors.append('repair without established violation')
    if decision.get('readiness') == 'ready':
        if decision.get('kind') != 'repair': errors.append('only repairs can be executable ready')
        if not decision.get('checks'): errors.append('ready without checks')
        for check in decision.get('checks', []): errors.extend(check_errors(check))
        if decision.get('blockers'): errors.append('ready with blockers')
    return errors
