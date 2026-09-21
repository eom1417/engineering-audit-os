"""What a verification run actually established, bound to the candidate it ran against.

A passing check proves something about one tree at one moment. Recording that a case is closed
without binding it to the candidate, the checks and the scope turns a local pass into a general
claim. Every field here exists so that a later reader can tell which is which.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

VERSION = 1
RESOLVED, NEEDS_REVIEW, NOT_CLOSED = 'resolved', 'needs_human_review', 'not_closed'
# Why a finding can stop appearing without anything being repaired. Only the first is a fix.
DISAPPEARANCE = ('healed', 'unobserved', 'scope_changed', 'ambiguous_identity')
LIMITATIONS = [
    'An outcome describes the candidate it ran against, never the original target.',
    'Checks that passed prove the checks passed; they do not prove the cause was removed.',
    'A finding that stopped appearing is not closed until something says why it stopped.',
]


def candidate_digest(root, paths):
    """A fingerprint of exactly the files the repair claims to have changed."""
    digest = hashlib.sha256()
    for relative in sorted(paths):
        path = Path(root) / relative
        digest.update(relative.encode('utf-8'))
        digest.update(path.read_bytes() if path.is_file() else b'<absent>')
    return digest.hexdigest()


def record(case_id, decision, result, root=None, tools=None, scope=None, reviewed_by=None):
    """One typed outcome. Refuses to be built from a result that contradicts itself."""
    checks = list(result.get('baseline') or []) + list(result.get('post_checks') or [])
    failed = [check for check in checks if check.get('status') != 'pass']
    changed = sorted(result.get('changed_paths') or [])
    problems = []
    if result.get('patch') and not result.get('patch_complete', True):
        problems.append('the delivered patch does not represent every difference in the candidate')
    if result.get('original_target_unchanged') is False:
        problems.append('the original target changed during verification')
    if not checks:
        problems.append('no check was executed, so nothing was verified')
    required_review = (decision or {}).get('requires_human_review', False)
    if required_review and not reviewed_by:
        problems.append('a human review was required and none is recorded')
    outcome = {
        'contract_version': VERSION,
        'case_id': case_id,
        'decision_kind': (decision or {}).get('kind'),
        'recorded_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'candidate': {'root': str(result.get('project') or root or ''),
                      'changed_paths': changed,
                      'digest': candidate_digest(result.get('project') or root or '.', changed)
                      if (result.get('project') or root) else None},
        'checks': [{'id': check.get('id'), 'phase': check.get('phase'), 'status': check.get('status')}
                   for check in checks],
        'failed_checks': [check.get('id') for check in failed],
        'tools': dict(sorted((tools or {}).items())),
        'scope': dict(sorted((scope or {}).items())),
        'reviewed_by': reviewed_by,
        'blockers': sorted(set(problems + [f'check {check.get("id")} did not pass' for check in failed])),
        'limitations': LIMITATIONS,
    }
    outcome['closure'] = closure(outcome, required_review)
    return outcome


def closure(outcome, required_review=False):
    if outcome['blockers']:
        return NOT_CLOSED
    if required_review and not outcome.get('reviewed_by'):
        return NEEDS_REVIEW
    return RESOLVED


def disappearance(previous_claim, current_claims, comparison_status, ambiguous_identities, outcome=None):
    """Why a claim stopped appearing. Absence is a question; only an outcome can answer it."""
    from .delta import key_of
    key = key_of(previous_claim)
    if '|'.join(key) in {'|'.join(pair) if isinstance(pair, tuple) else str(pair)
                         for pair in (ambiguous_identities or [])} or key in (ambiguous_identities or []):
        return 'ambiguous_identity'
    if comparison_status != 'comparable':
        return 'scope_changed'
    if outcome and outcome.get('closure') == RESOLVED and outcome.get('case_id') == previous_claim.get('uid'):
        return 'healed'
    return 'unobserved'


def write(out, outcome):
    path = Path(out) / 'outcomes.json'
    existing = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'schema_version': VERSION,
                                                                                    'outcomes': []}
    existing['outcomes'] = [row for row in existing['outcomes'] if row['case_id'] != outcome['case_id']]
    existing['outcomes'].append(outcome)
    existing['outcomes'].sort(key=lambda row: row['case_id'])
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return str(path)
