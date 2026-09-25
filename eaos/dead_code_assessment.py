"""An executable repair for dead code the detector confirms, under the engagement rule that asks for its removal.

Dead code is the one finding whose evidence is entirely mechanical: no production path reaches it and no text
names it. When the engagement rule `remove_dead_code` holds (a declared default the project can turn off in
eaos.engagement.json), the claim carries the assessment a ready card needs. Its reviewer of record is that rule
and its source, never an invented person. Its check re-runs the detector on the changed copy and passes only
when the candidate is gone.
"""
import sys

from .acceptance import fingerprint
from .engagement import rules_for
from .remediation_patterns import PATTERNS


def _check_argv(path, symbol, rule):
    """Re-collect facts into a private directory; exit 0 only when the candidate is no longer reported."""
    code = (
        "import json, subprocess, sys, tempfile\n"
        "tmp = tempfile.mkdtemp(prefix='eaos-deadcode-')\n"
        "r = subprocess.run([sys.executable, '-m', 'eaos', 'facts', '.', '--out', tmp])\n"
        "if r.returncode: sys.exit(r.returncode)\n"
        "facts = json.load(open(tmp + '/facts/deadcode.json'))['facts']\n"
        f"left = [f for f in facts if (f['location']['path'], f['location']['symbol'], f['value']['rule']) == ({path!r}, {symbol!r}, {rule!r})]\n"
        "sys.exit(1 if left else 0)\n")
    return [sys.executable, '-B', '-c', code]


def build_assessment(claim, fact_sets, target):
    """{'assessment': ..., 'checks': [...]} for a confirmed dead-code claim under the removal rule, else None."""
    if target is None or (claim.get('render') or {}).get('key') != 'dead_code' or claim.get('confidence') != 'CONFIRMED':
        return None
    rules, source = rules_for(target)
    rule = rules['remove_dead_code']
    if not rule['value']: return None
    own = set(claim.get('fact_ids') or [])
    facts = [fact for fact in (fact_sets.get('deadcode') or {}).get('facts', []) if fact.get('id') in own]
    if not facts: return None
    fact = facts[0]
    path, symbol, kind = fact['location']['path'], fact['location']['symbol'], fact['value']['rule']
    what = 'the module ' + path if kind == 'unreachable-module' else f'`{symbol}` in {path}'
    check = {'id': 'DEAD-' + fact['id'], 'kind': 'command',
             'invariant': 'Product code is reached from a production entry point, or named by something that is.',
             'expected': f'the next audit no longer reports {what} as dead code', 'expected_exit': 0, 'cwd': '.',
             'argv': _check_argv(path, symbol, kind), 'source_revision': fingerprint(target)}
    return {'assessment': {
                'violated_invariant': check['invariant'],
                'requirement_refs': ['engagement.rules.remove_dead_code'],
                'evidence_refs': [fact['id']],
                'reviewed_by': (f"engagement rule remove_dead_code ({rule['source']}): {rule['why']} "
                                'The evidence is mechanical; no human judgement is claimed.'),
                'before': fact['value']['message'],
                'after': f'{what} is deleted, the audit no longer reports it, and nothing that imported it remains.',
                'proposed_change': PATTERNS['remove_dead']['change']},
            'checks': [check]}
