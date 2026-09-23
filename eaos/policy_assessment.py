"""Build an acceptance assessment for a declared-policy violation."""
import hashlib
import sys
from pathlib import Path

from .acceptance import fingerprint
from .policy import FILENAME as POLICY_FILENAME
from .remediation_patterns import PATTERNS


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
    code = (
        "import subprocess, sys, tempfile\n"
        "tmp = tempfile.mkdtemp(prefix='eaos-policy-')\n"
        "r1 = subprocess.run([sys.executable, '-m', 'eaos', 'facts', '.', '--out', tmp])\n"
        "if r1.returncode != 0:\n"
        "    sys.exit(r1.returncode)\n"
        "sys.exit(subprocess.call([sys.executable, '-m', 'eaos', 'policy', 'check', '.', '--out', tmp]))\n"
    )
    return [sys.executable, '-B', '-c', code]


def build_assessment(claim, fact_sets, target):
    """Return ``{'assessment': ..., 'checks': [...]}`` for a policy claim, or ``None``."""
    if not isinstance(claim, dict):
        return None
    if target is None:
        return None
    if (claim.get('render') or {}).get('key') != 'policy':
        return None
    own = set(claim.get('fact_ids') or [])
    facts = [fact for fact in (fact_sets.get('policy') or {}).get('facts', [])
             if fact.get('kind') == 'policy_violation' and fact.get('id') in own]
    if not facts:
        return None
    fact = facts[0]
    edge_fact_id = (fact.get('value') or {}).get('edge_fact_id')
    if not edge_fact_id:
        return None
    digest, location = _policy_signature(target)
    if not digest:
        return None
    resolve_ids = {row.get('id') for row in (fact_sets.get('resolve') or {}).get('facts', [])}
    if edge_fact_id not in resolve_ids:
        return None
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
