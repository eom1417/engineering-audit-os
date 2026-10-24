"""Versioned decision contract: observed does not imply defective or executable."""
import hashlib
import json

VERSION = 1


def identity(claim):
    # Location and probe semantics distinguish similarly worded observations; what a probe expects and the finish line it
    # judges (eaos/analysis/finish_line.py, which shrinks as the code is fixed) do not: the card stays one card from check to check.
    probe = claim.get('probe_spec') or {}
    specification = {key: value for key, value in probe.get('specification', {}).items() if key not in ('expected', 'targets')}
    payload = {'claim_type': claim.get('claim_type'), 'probe_type': probe.get('probe_type'),
               'specification': specification, 'legacy_id': claim.get('legacy_id')}
    if not specification:
        payload['paths'] = sorted((claim.get('priority_factors') or {}).get('paths', []))
        payload['statement'] = ' '.join(claim.get('statement', '').split()).lower()
    return 'OBS-' + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:24]


def _argv_problem(argv):
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
        return 'argv must be a nonempty string array'
    if any(x in {'dossier', 'facts', 'tasks'} for x in argv[:3]):
        return 'report regeneration is not behavioral acceptance'
    return None


def _command_check_errors(check):
    problems = []
    argv_problem = _argv_problem(check.get('argv'))
    if argv_problem: problems.append(argv_problem)
    if type(check.get('expected_exit')) is not int: problems.append('expected_exit is required')
    if check.get('cwd', '.') != '.': problems.append('cwd must be the candidate root')
    return problems


def check_errors(check):
    if not isinstance(check, dict): return ['check must be an object']
    problems = ['missing ' + field for field in ('id', 'invariant', 'expected', 'source_revision')
                if not isinstance(check.get(field), str) or not check[field].strip()]
    if check.get('kind') not in {'command', 'human'}: problems.append('unsupported check kind')
    if check.get('kind') == 'command': problems += _command_check_errors(check)
    elif not check.get('rubric'): problems.append('human check needs a rubric')
    return problems


DOUBTED = 'The assistant doubted this card even on all its measurements: a person reviews it, it is never fixed automatically.'


KEPT = 'Decided by your assistant: not a problem worth changing. '
FIXED = 'Decided by your assistant: '


def _validated_inputs(claim):
    assessment = claim.get('assessment') or {}
    if not isinstance(assessment, dict): raise ValueError('assessment must be an object')
    checks = claim.get('checks') or []
    if not isinstance(checks, list): raise ValueError('checks must be an array')
    return assessment, checks


def _resolution(triage, checks):
    """The triage's resolution when it confirmed the card, and the checks a fix is judged by: the claim's, else the
    triage's (a fix with neither is no resolution)."""
    resolution = triage.get('resolution') if triage.get('decision') == 'confirm' else None
    if resolution != 'fix': return resolution, checks
    if not (checks or triage.get('checks')): return None, checks
    return resolution, checks or triage['checks']


def _retain_reason(claim, assessment, disposition):
    if claim.get('confidence') == 'REFUTED': return 'The claim was refuted; no repair is justified.'
    if disposition.get('kind') == 'accepted' and disposition.get('owner') and disposition.get('reason'):
        return disposition['reason']
    violated = assessment.get('violated_invariant')
    if claim.get('origin') == 'test' and not violated:
        return 'Test or fixture observation: no product violation established; retain for review.'
    if claim.get('origin') == 'archive' and not violated:
        return 'Archived code: not part of the running product; the owner keeps it for reference or removes it.'
    return None


def _triage_decision(resolution, triage):
    if resolution == 'keep': return 'retain', KEPT + (triage.get('why') or '')
    if resolution == 'fix': return 'repair', FIXED + (triage.get('note') or triage.get('change') or '')
    if resolution == 'owner': return 'investigate', 'Your assistant asks you: ' + (triage.get('question') or '')
    return None


def _evidenced_violation(claim, assessment):
    return (claim.get('confidence') == 'CONFIRMED' and assessment.get('violated_invariant')
            and assessment.get('requirement_refs') and assessment.get('evidence_refs'))


def _kind_and_reason(claim, assessment, disposition, triage, resolution):
    retained = _retain_reason(claim, assessment, disposition)
    if retained: return 'retain', retained
    triaged = _triage_decision(resolution, triage)
    if triaged: return triaged
    if _evidenced_violation(claim, assessment):
        return 'repair', 'A confirmed observation violates an explicitly evidenced requirement.'
    return 'investigate', 'Establish the requirement and consequence before proposing a code change.'


def _repair_blockers(checks, resolution, assessment):
    reasons = [] if checks else ['No acceptance check attached.']
    for check in checks: reasons.extend(check_errors(check))
    # The assistant's triage is the review of a change it decided, and its change is the "after".
    if resolution == 'fix': return reasons
    if not assessment.get('reviewed_by'): reasons.append('The engineering decision has not been reviewed.')
    if not assessment.get('before') or not assessment.get('after'): reasons.append('Before/after behavior is missing.')
    return reasons


def _readiness(kind, doubted, reasons):
    if kind == 'investigate' or doubted: return 'needs_review'
    if reasons: return 'blocked'
    return 'ready' if kind == 'repair' else 'no_change'


def decide(claim):
    """The claim's decision. The assistant's triage (claim `triage`, eaos/analysis/card_review.py apply_verdicts), when it confirmed the
    card, settles it: `keep` retains it with its reason, `fix` makes it a repair checked by the claim's own checks or the
    triage's (`triage.checks`), `owner` leaves it an investigation for the person."""
    disposition = claim.get('disposition') or {}
    assessment, checks = _validated_inputs(claim)
    triage = claim.get('triage') or {}
    resolution, checks = _resolution(triage, checks)
    kind, reason = _kind_and_reason(claim, assessment, disposition, triage, resolution)
    doubted = kind != 'retain' and triage.get('decision') == 'doubt'
    reasons = [DOUBTED] if doubted else []
    if kind == 'repair': reasons += _repair_blockers(checks, resolution, assessment)
    return {'contract_version': VERSION, 'observation_uid': claim.get('uid') or identity(claim),
            'kind': kind, 'reason': reason,
            'readiness': _readiness(kind, doubted, reasons),
            'blockers': sorted(set(reasons)), 'checks': checks if kind == 'repair' else [],
            'allowed_outcomes': ['repair', 'retain', 'blocked_missing_requirement'] if kind == 'investigate' else []}


def ready(card):
    """Whether a batch may take the card without a person's decision: a fix, or a planned part to build (eaos/journeys/extend.py)."""
    return card.get('kind') in ('remediate', 'build') and (card.get('decision') or {}).get('readiness') == 'ready'


def waiting(card, done):
    """The cards `card` waits for: its prerequisites not in `done` yet. A module is split only once its complex functions
    are simplified (eaos/analysis/plan.py _split_last); taken before them, the split failed in batch after batch (EAOS, 2026-10-15)."""
    return [p['task_id'] for p in card.get('prerequisites') or [] if p.get('task_id') not in done]


def _ready_errors(decision):
    errors = []
    if decision.get('kind') != 'repair': errors.append('only repairs can be executable ready')
    if not decision.get('checks'): errors.append('ready without checks')
    for check in decision.get('checks', []): errors.extend(check_errors(check))
    if decision.get('blockers'): errors.append('ready with blockers')
    return errors


def task_errors(task):
    if task.get('contract_version') != VERSION: return ['legacy task needs revalidation']
    decision = task.get('decision') or {}
    errors = []
    if decision.get('kind') not in {'repair', 'investigate', 'retain'}: errors.append('unknown decision kind')
    if task.get('kind') == 'remediate' and decision.get('kind') != 'repair': errors.append('repair without established violation')
    if decision.get('readiness') == 'ready': errors += _ready_errors(decision)
    return errors
