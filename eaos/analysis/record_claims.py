"""The claims of the records beside the facts (eaos/analysis/dossier_claims.py gathers them with the facts' claims): every
load blocker the load model answered, and the findings, components, contracts, rules and flows of a legacy audit run.
"""
from .claims import make


def from_load_model(fact_sets, offset=0):
    """Every load blocker becomes a claim, so a scaling risk reaches a task card like any other.

    A blocker comes only from an answered question. An unanswered one is never a claim: we do not
    know, and a risk we invented is worse than a risk we missed.
    """
    record = fact_sets.get('load_model')
    if not record:
        return []
    from .load_model import blockers
    made, index = [], offset
    for blocker in blockers(record):
        index += 1
        where = blocker['route'] or blocker['path'] or blocker['entry_point']
        made.append(make(index, f"{where}: {blocker['statement']}"[:600], 'risk', 'CONFIRMED',
                         ['static_fact'], [], blocker['falsifier'],
                         fact_ids=blocker['evidence'],
                         render={'key': 'load_blocker',
                                 'params': {'where': str(where), 'kind': blocker['kind'],
                                            'statement': blocker['statement']},
                                 'params_en': {'where': str(where), 'kind': blocker['kind'],
                                               'statement': blocker['statement_en']}},
                         probe_spec={'probe_type': 'graph_query',
                                     'specification': {'query': 'load_blocker_present',
                                                       'entry_point': blocker['entry_point'],
                                                       'question': blocker['question'],
                                                       'expected': 'The same question still answers the '
                                                                   'same way for this entry point.'}},
                         impact={'scenario': blocker['scenario']}))
    return made


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
