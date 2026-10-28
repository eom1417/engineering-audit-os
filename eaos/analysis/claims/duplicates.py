"""The claims of code written more than once (eaos/analysis/claims/ledger.py BUILDERS): a rule's value defined in several
places, and work a path repeats for nothing. Each builder is `build(fact_sets, add, target)`, as in
eaos/analysis/claims/from_facts.py. Code copied, near copies and every other repeated pattern are one source per
pattern's (M15, eaos/analysis/claims/from_one_source.py).
"""
from .from_facts import facts_of, graph_query, naming

# Sustainability observations reach the same ledger as everything else: one record, one decision.
REDUNDANCY_MAX = 10


def duplicated_rules(fact_sets, add, target):
    for fact in [f for f in facts_of(fact_sets, 'domain', 'domain_constant') if f['value']['duplicated']]:
        places = naming(f"{d['path']}:{d['line']}" for d in fact['value']['definitions'])
        differs = fact['value']['distinct_values'] > 1
        add(f"{fact['value']['name']} is defined in {len(fact['value']['definitions'])} places ({places})"
            + (' with different values' if differs else ' with the same value'),
            'business_rule', 'CONFIRMED', ['static_fact'],
            'A single definition with the other sites importing it, or evidence that the repeated name encodes unrelated rules.',
            fact_ids=[fact['id']],
            render={'key': 'duplicated_rule', 'params': {'name': fact['value']['name'],
                                                         'count': len(fact['value']['definitions']),
                                                         'places': places,
                                                         'differs': 'yes' if differs else 'no'}},
            probe_spec={'probe_type': 'absence_search', 'specification': {'patterns': [fact['value']['name']],
                                                                          'search_scope': ['source', 'test'],
                                                                          'expected': 'The name is defined in more than one file with no import linking them.'}},
            impact={'scenario': 'Changing the rule in one place and not the others makes two paths disagree'
                                + (' — and they already hold different values.' if differs else '.')})


def redundant_work(fact_sets, add, target):
    for fact in facts_of(fact_sets, 'redundancy', 'redundancy')[:REDUNDANCY_MAX]:
        kind = fact['value']['kind']
        location = f"{fact['location']['path']}:{fact['location']['start_line']}"
        add(f"{kind} at {location} in {fact['location'].get('symbol')}: {fact['value']['callee']}",
            'risk' if kind == 'n_plus_one' else 'structure', 'CONFIRMED', ['static_fact'],
            'Evidence that the repetition is required — a different result per call, or a dependency on '
            'state that changes between the two.',
            fact_ids=[fact['id']],
            render={'key': 'redundant_work',
                    'params': {'kind': kind, 'location': location,
                               'symbol': fact['location'].get('symbol'),
                               'callee': fact['value']['callee']}},
            probe_spec=graph_query('redundancy_present', path=fact['location']['path'],
                                    line=fact['location']['start_line'], kind=kind, callee=fact['value']['callee'],
                                    expected='The redundant work is still present at that location.'),
            impact={'scenario': 'The path does more work than its result requires, on every execution.'})
