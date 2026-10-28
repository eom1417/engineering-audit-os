"""Build an acceptance assessment for a declared-policy violation."""
import hashlib
from pathlib import Path

from ..repair.acceptance import fingerprint, recheck
from ..target_state.policy import FILENAME as POLICY_FILENAME
from ..repair.remediation import PATTERNS, cited


def _policy_signature(target):
    """Return ``(digest, location)`` for the project's policy file, or ``(None, None)`` if absent."""
    location = Path(target) / POLICY_FILENAME
    if not location.is_file():
        return None, None
    digest = hashlib.sha256(location.read_bytes()).hexdigest()
    return digest, str(location)


def _checks_command():
    """Build a self-contained ``argv`` that re-collects facts then re-runs policy check.

    The command is bound to ``cwd='.'`` (the candidate root) and exits with the
    policy check exit code: 0 when no forbidden edges remain, 2 otherwise. It
    collects its own facts into a private temp dir, so a runner does not have to
    stage the audit output to a known path.
    """
    return recheck('eaos-policy-', "sys.exit(subprocess.call([sys.executable, '-m', 'eaos', 'policy', 'check', '.', '--out', tmp]))\n")


def build_assessment(claim, fact_sets, target):
    """Return ``{'assessment': ..., 'checks': [...]}`` for a policy claim, or ``None``."""
    fact = _violation(claim, fact_sets, target)
    if fact is None:
        return None
    edge_fact_id = (fact.get('value') or {}).get('edge_fact_id')
    if not edge_fact_id:
        return None
    digest, location = _policy_signature(target)
    if not digest:
        return None
    resolve_ids = {row.get('id') for row in (fact_sets.get('resolve') or {}).get('facts', [])}
    if edge_fact_id not in resolve_ids:
        return None
    return _assessment(fact, edge_fact_id, digest, location, target)


def _violation(claim, fact_sets, target):
    """The policy_violation fact a policy claim stands on, or None."""
    if not isinstance(claim, dict) or target is None:
        return None
    if (claim.get('render') or {}).get('key') != 'policy':
        return None
    facts = [fact for fact in cited(claim, fact_sets, 'policy') if fact.get('kind') == 'policy_violation']
    return facts[0] if facts else None


def _assessment(fact, edge_fact_id, digest, location, target):
    reason = (fact.get('value') or {}).get('reason') or ''
    invariant = reason.strip() or 'A declared layering rule was contradicted by a resolved import.'
    before = (
        f"{fact['location']['path']} imports {fact['value']['to_path']} "
        f"({fact['value']['from_layer']} \u2192 {fact['value']['to_layer']}); the project's "
        "declared policy forbids this edge."
    )
    after = (
        f"{fact['location']['path']} no longer imports {fact['value']['to_path']} in the "
        "next audit, or the project's policy file documents why the edge is now "
        "permitted."
    )
    proposed_change = PATTERNS['policy_violation']['change']
    check = {
        'id': 'POLICY-' + fact['id'],
        'kind': 'command',
        'invariant': invariant,
        'expected': 'next audit reports zero policy_violation facts (policy check exits 0)',
        'expected_exit': 0,
        'cwd': '.',
        'argv': _checks_command(),
        'source_revision': fingerprint(target),
    }
    assessment = {
        'violated_invariant': invariant,
        'requirement_refs': [fact['id']],
        'evidence_refs': [edge_fact_id],
        'reviewed_by': (
            location + ' (sha256:' + digest[:16] + '); the project authored the rule, '
            'so its fingerprint is the reviewer of record \u2014 inventing a human name '
            'would be forgery.'
        ),
        'before': before,
        'after': after,
        'proposed_change': proposed_change,
    }
    return {'assessment': assessment, 'checks': [check]}
