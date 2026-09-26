"""Ready repairs for confirmed observations whose evidence is mechanical, each checked by its own probe.

A structural duplicate, a hotspot over its threshold, a load blocker, broken code, a runtime-mutated
module global, a rule defined twice, an import cycle, redundant work in a flow: each is a fact the audit
decides by rule, and the same rule decides whether a changed copy still has it. Under the engagement rule
for its family (a declared default the owner turns off in eaos.engagement.json), such a confirmed claim
from product code carries the assessment a ready card needs. Its reviewer of record is that rule, never an
invented person; its check is `eaos recheck` with the claim's own probe, which passes only when the probe
refutes the observation on the candidate copy.
"""
import json
import sys
from pathlib import Path

from .acceptance import fingerprint
from .engagement import rules_for

# render key (or probe query) -> (engagement rule, invariant, what "after" looks like)
FAMILIES = {
    'structural_duplicate': ('consolidate_duplicates', 'One behaviour has one definition that every caller uses.',
                             'the shared shape lives in one function every former copy calls; the audit finds no such cluster.'),
    'duplicated_rule': ('consolidate_duplicates', 'A rule value is defined once and imported where it is used.',
                        'one module defines the value and every other place imports it.'),
    'hotspot': ('reduce_hotspots', 'No function carries more branches than its declared threshold.',
                'the function is split so that no part exceeds the threshold; its behaviour lock still passes.'),
    'load_blocker': ('bound_load_paths', 'Every user-facing entry point bounds its cost under load.',
                     'the entry point bounds the read, protects the call or caches it; the load model no longer flags it.'),
    'redundant_work': ('bound_load_paths', 'A flow does not repeat work its result does not need.',
                       'the repeated or loop-invariant call runs once; the audit finds no redundancy there.'),
    'broken_code': ('fix_broken_code', 'Every reference in the product resolves.',
                    'the reference resolves, or the dead code that held it is gone.'),
    'mutable_global': ('untangle_dependencies', 'Module-level state is not changed at runtime.',
                       'the state lives behind an owner that is passed in; no module-level value is reassigned at runtime.'),
    'cycle': ('untangle_dependencies', 'The resolved import graph has no cycle.',
              'the shared part lives in its own module both sides import; the cycle is gone.'),
}


def family(claim):
    key = (claim.get('render') or {}).get('key')
    if key in FAMILIES: return key
    query = ((claim.get('probe_spec') or {}).get('specification') or {}).get('query')
    return 'cycle' if query == 'cycle_present' else None


FAMILY_OF = {'.py': 'python', '.ts': 'js', '.tsx': 'js', '.js': 'js', '.jsx': 'js', '.mjs': 'js', '.go': 'go', '.java': 'java'}


def same_value(claim, fact_sets):
    """A rule defined twice with one value, in one language, has one home every copy can import. With different
    values, which is right is a person's decision; across languages no file can import another, so the home
    (a shared configuration, the API) is a design decision. Neither is a mechanical repair."""
    facts = [f for f in (fact_sets.get('domain') or {}).get('facts', []) if f.get('id') in set(claim.get('fact_ids') or [])]
    languages = {FAMILY_OF.get(Path(d.get('path', '')).suffix, Path(d.get('path', '')).suffix)
                 for f in facts for d in (f.get('value') or {}).get('definitions') or []}
    return bool(facts) and len(languages) == 1 and all((f.get('value') or {}).get('distinct_values') == 1 for f in facts)


def spec_for(claim, fact_sets):
    """The claim's probe, made independent of fact ids that change when a file changes."""
    spec = json.loads(json.dumps(claim['probe_spec']))
    specification = spec['specification']
    if specification.get('query') == 'load_blocker_present':
        entry = next((f for f in (fact_sets.get('entrypoints') or {}).get('facts', []) if f.get('id') == specification.get('entry_point')), None)
        if entry is None: return None
        specification['entry_path'] = entry['location'].get('path')
        specification['entry_route'] = (entry.get('value') or {}).get('route')
    return {'probe_type': spec['probe_type'], 'specification': specification}


def build_assessment(claim, fact_sets, target):
    """{'assessment', 'checks'} for a confirmed product claim of a mechanical family under its rule, else None."""
    name = family(claim)
    if (target is None or name is None or claim.get('confidence') != 'CONFIRMED' or claim.get('assessment')
            or claim.get('origin', 'source') == 'test' or not claim.get('probe_spec')):
        return None
    if name == 'duplicated_rule' and not same_value(claim, fact_sets): return None
    rule_name, invariant, after = FAMILIES[name]
    rules, _ = rules_for(target)
    rule = rules[rule_name]
    if not rule['value']: return None
    spec = spec_for(claim, fact_sets)
    if spec is None: return None
    from .remediation_patterns import pattern_for
    check = {'id': 'MECH-' + claim['id'], 'kind': 'command', 'invariant': invariant,
             'expected': 'the claim\'s own probe refutes it on the changed copy', 'expected_exit': 0, 'cwd': '.',
             'argv': [sys.executable, '-m', 'eaos', 'recheck', '--spec', json.dumps(spec, ensure_ascii=False), '.'],
             'source_revision': fingerprint(target)}
    return {'assessment': {
                'violated_invariant': invariant,
                'requirement_refs': [f'engagement.rules.{rule_name}'],
                'evidence_refs': list(claim.get('fact_ids') or []),
                'reviewed_by': (f"engagement rule {rule_name} ({rule['source']}): {rule['why']} "
                                'The evidence is decided by rule; no human judgement is claimed.'),
                'before': claim['statement'],
                'after': after,
                'proposed_change': pattern_for(claim)['change']},
            'checks': [check]}
