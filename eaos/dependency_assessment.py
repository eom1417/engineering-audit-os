"""An executable repair for a dependency version with a known, fixed vulnerability.

OSV-Scanner's lookup is deterministic: this locked version is listed as affected, and the advisory names
the version that fixes it. When the engagement rule `upgrade_vulnerable_dependencies` holds (a declared
default the project can turn off in eaos.engagement.json), the claim carries the assessment a ready card
needs. Its reviewer of record is that rule, never an invented person. Its check re-runs Syft and
OSV-Scanner on the changed copy and passes only when none of the original advisories remain for the package.
"""
import sys

from .acceptance import fingerprint
from .engagement import rules_for
from .remediation_patterns import PATTERNS


def _check_argv(ecosystem, name, advisories):
    """Re-scan into a private directory; exit 0 only when the package carries none of these advisories."""
    code = (
        "import json, subprocess, sys, tempfile\n"
        "tmp = tempfile.mkdtemp(prefix='eaos-deps-')\n"
        "r = subprocess.run([sys.executable, '-m', 'eaos', 'facts', '.', '--out', tmp, '--engines', 'syft', 'osv-scanner'])\n"
        "if r.returncode: sys.exit(r.returncode)\n"
        "data = json.load(open(tmp + '/facts/external.json'))\n"
        "if 'osv-scanner' not in (data.get('summary') or {}).get('engines_observed', []): sys.exit(2)\n"
        f"prefix, wanted = {f'{ecosystem}:{name}@'!r}, set({sorted(advisories)!r})\n"
        "left = [f for f in data['facts'] if f['kind'] == 'engine_finding' and f['value'].get('kind') == 'vulnerability'\n"
        "        and str(f['location'].get('symbol', '')).startswith(prefix)\n"
        "        and wanted & set(next((m['value'] for m in f['value']['measurements'] if m['name'] == 'advisory_ids'), []))]\n"
        "sys.exit(1 if left else 0)\n")
    return [sys.executable, '-B', '-c', code]


def measured(fact, name):
    return next((m['value'] for m in (fact.get('value') or {}).get('measurements') or [] if m['name'] == name), None)


def build_assessment(claim, fact_sets, target):
    """{'assessment': ..., 'checks': [...]} for a fixable vulnerable dependency under the upgrade rule, else None."""
    if target is None or (claim.get('render') or {}).get('key') != 'vulnerable_dependency':
        return None
    rules, _ = rules_for(target)
    rule = rules['upgrade_vulnerable_dependencies']
    if not rule['value']: return None
    own = set(claim.get('fact_ids') or [])
    fact = next((f for f in (fact_sets.get('external') or {}).get('facts', []) if f.get('id') in own), None)
    if fact is None or not measured(fact, 'fixed_in'): return None
    ecosystem, _, rest = str(fact['location'].get('symbol')).partition(':')
    name, _, installed = rest.rpartition('@')
    fixed, advisories = measured(fact, 'fixed_in'), measured(fact, 'advisory_ids') or []
    check = {'id': 'DEP-' + fact['id'], 'kind': 'command',
             'invariant': 'No locked dependency is a version with a published, fixed vulnerability.',
             'expected': f'the next scan reports none of {", ".join(advisories)} for {name}', 'expected_exit': 0, 'cwd': '.',
             'argv': _check_argv(ecosystem, name, advisories), 'source_revision': fingerprint(target)}
    return {'assessment': {
                'violated_invariant': check['invariant'],
                'requirement_refs': ['engagement.rules.upgrade_vulnerable_dependencies'],
                'evidence_refs': [fact['id']],
                'reviewed_by': (f"engagement rule upgrade_vulnerable_dependencies ({rule['source']}): {rule['why']} "
                                'The evidence is a database lookup of the locked version; no human judgement is claimed.'),
                'before': fact['value']['message'],
                'after': f'{name} is at {fixed} or later in every lockfile, and the scan reports none of its advisories.',
                'proposed_change': PATTERNS['upgrade_dependency']['change'].format(name=name, installed=installed, fixed=fixed)},
            'checks': [check]}
