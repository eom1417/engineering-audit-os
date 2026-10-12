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


DOUBTED = 'The assistant doubted this card even on all its measurements: a person reviews it, it is never fixed automatically.'


KEPT = 'Decided by your assistant: not a problem worth changing. '
FIXED = 'Decided by your assistant: '


def decide(claim):
    """The claim's decision. The assistant's triage (claim `triage`, eaos/plan.py apply_verdicts), when it confirmed the
    card, settles it: `keep` retains it with its reason, `fix` makes it a repair checked by the claim's own checks or the
    triage's (`triage.checks`), `owner` leaves it an investigation for the person."""
    disposition = claim.get('disposition') or {}
    assessment = claim.get('assessment') or {}
    if not isinstance(assessment, dict): raise ValueError('assessment must be an object')
    checks = claim.get('checks') or []
    if not isinstance(checks, list): raise ValueError('checks must be an array')
    reasons = []
    triage = claim.get('triage') or {}
    resolution = triage.get('resolution') if triage.get('decision') == 'confirm' else None
    if resolution == 'fix' and not (checks or triage.get('checks')): resolution = None
    if resolution == 'fix': checks = checks or triage['checks']
    if claim.get('confidence') == 'REFUTED':
        kind, reason = 'retain', 'The claim was refuted; no repair is justified.'
    elif disposition.get('kind') == 'accepted' and disposition.get('owner') and disposition.get('reason'):
        kind, reason = 'retain', disposition['reason']
    elif claim.get('origin') == 'test' and not assessment.get('violated_invariant'):
        kind, reason = 'retain', 'Test or fixture observation: no product violation established; retain for review.'
    elif claim.get('origin') == 'archive' and not assessment.get('violated_invariant'):
        kind, reason = 'retain', 'Archived code: not part of the running product; the owner keeps it for reference or removes it.'
    elif resolution == 'keep':
        kind, reason = 'retain', KEPT + (triage.get('why') or '')
    elif resolution == 'fix':
        kind, reason = 'repair', FIXED + (triage.get('note') or triage.get('change') or '')
    elif resolution == 'owner':
        kind, reason = 'investigate', 'Your assistant asks you: ' + (triage.get('question') or '')
    elif (claim.get('confidence') == 'CONFIRMED' and assessment.get('violated_invariant')
          and assessment.get('requirement_refs') and assessment.get('evidence_refs')):
        kind, reason = 'repair', 'A confirmed observation violates an explicitly evidenced requirement.'
    else:
        kind, reason = 'investigate', 'Establish the requirement and consequence before proposing a code change.'
    doubted = kind != 'retain' and (claim.get('triage') or {}).get('decision') == 'doubt'
    if doubted: reasons.append(DOUBTED)
    if kind == 'repair':
        if not checks: reasons.append('No acceptance check attached.')
        for check in checks: reasons.extend(check_errors(check))
        # The assistant's triage is the review of a change it decided, and its change is the "after".
        if resolution != 'fix' and not assessment.get('reviewed_by'): reasons.append('The engineering decision has not been reviewed.')
        if resolution != 'fix' and (not assessment.get('before') or not assessment.get('after')):
            reasons.append('Before/after behavior is missing.')
    return {'contract_version': VERSION, 'observation_uid': claim.get('uid') or identity(claim),
            'kind': kind, 'reason': reason,
            'readiness': 'needs_review' if kind == 'investigate' or doubted else
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
