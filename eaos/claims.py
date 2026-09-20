"""One ledger for everything the system asserts, with its source, its confidence and its refutation.

A fact is produced by an extractor and is reproducible. A claim is an interpretation and must name
what would disprove it. A question is an admitted gap. Nothing rendered may exist outside this ledger.
"""
from datetime import datetime, timezone
import json
from .audit_records import schema_errors
from .workspace import DATA, read, write

CONFIDENCE = ['CONFIRMED', 'LIKELY', 'HYPOTHESIS', 'REFUTED']
PROVING_METHODS = {'runtime_probe', 'test_evidence', 'static_fact', 'history_fact'}
TYPES = ['structure', 'responsibility', 'contract', 'business_rule', 'flow_step', 'risk', 'cause', 'capability_gap', 'cost']


def schema(): return read(DATA / 'schemas/claim.schema.json')


def now(): return datetime.now(timezone.utc).isoformat()


def claim_id(index): return 'CLM-%03d' % index


def make(index, statement, claim_type, confidence, method, evidence_ids, falsifier, **extra):
    row = {'id': claim_id(index), 'statement': statement, 'claim_type': claim_type, 'confidence': confidence,
           'method': list(method), 'evidence_ids': list(evidence_ids), 'falsifier': falsifier,
           'status': extra.pop('status', 'open'), 'created_at': extra.pop('created_at', now())}
    row.update({k: v for k, v in extra.items() if v is not None})
    return row


def errors(claims, evidence_ids=(), fact_ids=()):
    """Structural and epistemic rules. A claim that cannot be wrong is not an engineering claim."""
    spec = schema()
    found = []
    seen = set()
    known_evidence, known_facts = set(evidence_ids), set(fact_ids)
    for claim in claims:
        identity = claim.get('id', '?')
        found += [identity + ': ' + message for message in schema_errors(claim, spec)]
        if identity in seen: found.append(identity + ': duplicate claim id')
        seen.add(identity)
        if not claim.get('falsifier', '').strip():
            found.append(identity + ': a claim must state what would disprove it')
        if claim.get('confidence') == 'CONFIRMED' and not (set(claim.get('method', [])) & PROVING_METHODS):
            found.append(identity + ': CONFIRMED requires a probe, a test or a deterministic fact, not model inference')
        if claim.get('confidence') != 'REFUTED' and not claim.get('evidence_ids') and not claim.get('fact_ids'):
            found.append(identity + ': no evidence and no fact backs this claim')
        if known_evidence:
            for reference in claim.get('evidence_ids', []):
                if reference not in known_evidence: found.append(identity + ': unknown evidence ' + reference)
        if known_facts:
            for reference in claim.get('fact_ids', []):
                if reference not in known_facts: found.append(identity + ': unknown fact ' + reference)
        if claim.get('claim_type') == 'risk' and claim.get('disposition', {}).get('kind') == 'accepted':
            disposition = claim['disposition']
            if not disposition.get('owner') or not disposition.get('reason'):
                found.append(identity + ': an accepted risk needs an owner and a reason')
    return sorted(set(found))


def load(path): return read(path)


def save(path, claims, evidence_ids=(), fact_ids=()):
    problems = errors(claims, evidence_ids, fact_ids)
    if problems: raise ValueError('Claim ledger rejected: ' + '; '.join(problems[:5]))
    write(path, claims)
    return claims


def from_legacy(findings, model, flows, coverage, revision=None):
    """Bridge existing audit records into the ledger without losing or inventing anything."""
    claims, index = [], 0
    confidence_of = {'confirmed': 'LIKELY', 'probable': 'HYPOTHESIS', 'requires_verification': 'HYPOTHESIS',
                     'refuted': 'REFUTED', 'false_positive': 'REFUTED'}
    for finding in sorted(findings, key=lambda f: f['id']):
        index += 1
        status = finding.get('claim_status', 'probable')
        claims.append(make(index, finding['current_behavior'][:600], 'cause',
                           'REFUTED' if finding.get('status') in {'false_positive'} else confidence_of.get(status, 'HYPOTHESIS'),
                           ['model_inference'], finding.get('evidence_ids', []),
                           'Source or test evidence showing the described behaviour does not occur, or that the stated root cause is not the actual one.',
                           legacy_id=finding['id'],
                           impact={'scenario': finding.get('why_this_matters', '')[:400],
                                   'affected_nodes': finding.get('affected_components', [])},
                           disposition={'kind': 'task'} if finding.get('status') == 'open' else {'kind': 'none_yet'},
                           revision=revision))
    for node in sorted(model.get('nodes', []), key=lambda n: n['id']):
        index += 1
        claims.append(make(index, f"{node['name']} owns: {node['responsibility']}"[:600], 'responsibility', 'HYPOTHESIS',
                           ['model_inference'], node.get('evidence_ids', []),
                           'A source range showing this responsibility lives elsewhere, or that this component owns a different rule.',
                           legacy_id=node['id'], revision=revision))
    for contract in sorted(model.get('contracts', []), key=lambda c: c['id']):
        index += 1
        claims.append(make(index, contract['invariant'][:600], 'contract', 'HYPOTHESIS', ['model_inference'],
                           contract.get('evidence_ids', []),
                           'A caller or test that violates the stated invariant without failing.',
                           legacy_id=contract['id'], revision=revision))
    for rule in sorted(model.get('business_rules', []), key=lambda r: r['id']):
        index += 1
        claims.append(make(index, rule['invariant'][:600], 'business_rule', 'HYPOTHESIS', ['model_inference'],
                           rule.get('evidence_ids', []),
                           'A second implementation of this rule with different behaviour, or a path that bypasses it.',
                           legacy_id=rule['id'], revision=revision))
    for flow in sorted(flows or [], key=lambda f: f['id']):
        index += 1
        claims.append(make(index, f"{flow['name']}: " + ' → '.join(flow.get('steps', []))[:500], 'flow_step', 'HYPOTHESIS',
                           ['model_inference'], flow.get('evidence_ids', []),
                           'An execution trace or test showing the flow takes a different path.',
                           legacy_id=flow['id'], revision=revision))
    return claims


def from_facts(fact_sets):
    """Deterministic facts promoted to claims keep CONFIRMED status and name their own refutation."""
    claims, index = [], 0
    graph = fact_sets.get('graph', {})
    for fact in [f for f in graph.get('facts', []) if f['kind'] == 'graph_cycle']:
        index += 1
        claims.append(make(index, 'Import cycle between: ' + ', '.join(fact['value']['members']), 'structure',
                           'CONFIRMED', ['static_fact'], [], 'A resolved import graph in which these files no longer form a cycle.',
                           fact_ids=[fact['id']],
                           probe_spec={'probe_type': 'graph_query', 'specification': {'query': 'cycle_present', 'members': fact['value']['members'],
                                                                                      'expected': 'The same files still form a cycle in the resolved import graph.'}},
                           impact={'scenario': 'Changing any member can require changing the others together; the group cannot be tested or replaced independently.'}))
    history = fact_sets.get('history', {})
    shallow = (history.get('summary', {}).get('commits_analysed') or 0) < 10
    linked = {fact['location']['path']: set(fact['value']['depends_on']) for fact in graph.get('facts', []) if fact['kind'] == 'graph_node'}
    from .facts.source import language_of
    pairs = [] if shallow else sorted([f for f in history.get('facts', []) if f['kind'] == 'history_cochange'],
                                       key=lambda f: (-f['value']['support'] * f['value']['confidence'], f['location']['path']))
    for fact in pairs[:15]:
        left, right = fact['location']['path'], fact['location']['paired_path']
        if right in linked.get(left, set()) or left in linked.get(right, set()): continue
        if fact['value']['confidence'] < 0.6: continue
        # Structural coupling needs code on both sides; a document moving with code is editorial.
        if language_of(left) is None or language_of(right) is None: continue
        index += 1
        claims.append(make(index, f'{left} and {right} change together in {fact["value"]["support"]} commits with no visible code dependency',
                           'structure', 'CONFIRMED', ['history_fact'], [],
                           'A longer history window, or a rename, showing the pairing is coincidental rather than a shared reason to change.',
                           fact_ids=[fact['id']],
                           probe_spec={'probe_type': 'graph_query', 'specification': {'query': 'no_code_dependency', 'left': left, 'right': right,
                                                                                      'expected': 'Neither file imports the other in the resolved graph.'}},
                           impact={'scenario': 'A change to one is likely to need a matching change to the other, with nothing in the code to signal it.'}))
    domain = fact_sets.get('domain', {})
    for fact in [f for f in domain.get('facts', []) if f['kind'] == 'domain_constant' and f['value']['duplicated']]:
        index += 1
        places = ', '.join(f"{d['path']}:{d['line']}" for d in fact['value']['definitions'])
        differs = fact['value']['distinct_values'] > 1
        claims.append(make(index, f"{fact['value']['name']} is defined in {len(fact['value']['definitions'])} places ({places})"
                           + (' with different values' if differs else ' with the same value'),
                           'business_rule', 'CONFIRMED', ['static_fact'], [],
                           'A single definition with the other sites importing it, or evidence that the repeated name encodes unrelated rules.',
                           fact_ids=[fact['id']],
                           probe_spec={'probe_type': 'absence_search', 'specification': {'patterns': [fact['value']['name']],
                                                                                         'search_scope': ['source', 'test'],
                                                                                         'expected': 'The name is defined in more than one file with no import linking them.'}},
                           impact={'scenario': 'Changing the rule in one place and not the others makes two paths disagree'
                                               + (' — and they already hold different values.' if differs else '.')}))
    flows = fact_sets.get('flows', {})
    for fact in [f for f in flows.get('facts', []) if f['value']['unresolved_steps'] > 2][:10]:
        index += 1
        entry = fact['value']['entry']
        claims.append(make(index, f"Flow {fact['value']['flow_id']} ({entry['surface']} {entry['route']}) stops at "
                                  f"{fact['value']['unresolved_steps']} unresolvable calls",
                           'capability_gap', 'CONFIRMED', ['static_fact'], [],
                           'A resolver or runtime trace that follows those calls to their targets.',
                           fact_ids=[fact['id']],
                           probe_spec={'probe_type': 'graph_query', 'specification': {'query': 'flow_has_unresolved_steps', 'flow_id': fact['value']['flow_id'],
                                                                                      'expected': 'The traced flow still stops at calls the resolver cannot follow.'}},
                           impact={'scenario': 'The end-to-end behaviour of this entry point is not fully visible from source alone.'}))
    return claims


def merge(claims):
    """Two records asserting the same thing are one claim with two sources, not two claims."""
    order = {level: index for index, level in enumerate(CONFIDENCE)}
    # The same sentence recorded twice is one claim; the more specific type wins.
    specificity = {level: index for index, level in enumerate(
        ['business_rule', 'contract', 'cause', 'risk', 'flow_step', 'responsibility', 'structure', 'capability_gap', 'cost'])}
    grouped = {}
    for claim in claims:
        key = ' '.join(claim['statement'].split()).lower()
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = dict(claim)
            if claim.get('legacy_id'): grouped[key]['legacy_ids'] = [claim['legacy_id']]
            continue
        existing['evidence_ids'] = sorted(set(existing.get('evidence_ids', []) + claim.get('evidence_ids', [])))
        existing['fact_ids'] = sorted(set(existing.get('fact_ids', []) + claim.get('fact_ids', [])))
        existing['method'] = sorted(set(existing['method'] + claim['method']))
        if order[claim['confidence']] < order[existing['confidence']]: existing['confidence'] = claim['confidence']
        if specificity[claim['claim_type']] < specificity[existing['claim_type']]: existing['claim_type'] = claim['claim_type']
        if claim.get('legacy_id'): existing['legacy_ids'] = sorted(set(existing.get('legacy_ids', []) + [claim['legacy_id']]))
    merged = []
    for claim in grouped.values():
        if not claim.get('fact_ids'): claim.pop('fact_ids', None)
        if len(claim.get('legacy_ids', [])) > 1: claim['legacy_id'] = ', '.join(claim['legacy_ids'])
        claim.pop('legacy_ids', None)
        merged.append(claim)
    return merged


def renumber(claims):
    """Stable ids after merging sources, keeping the original id visible for traceability."""
    result = []
    for index, claim in enumerate(sorted(claims, key=lambda c: (c['claim_type'], c.get('legacy_id') or '', c['statement'])), start=1):
        row = dict(claim)
        if row['id'] != claim_id(index): row['supersedes'] = sorted(set(row.get('supersedes', []) + [row['id']]))
        row['id'] = claim_id(index)
        result.append(row)
    return result
