"""The claims of code written more than once (eaos/analysis/claims/ledger.py BUILDERS): a rule's value defined in several
places, a function copied whole or a structure shared, one ordered sequence of calls repeated, and work a path repeats
for nothing. Each builder is `build(fact_sets, add, target)`, as in eaos/analysis/claims/from_facts.py.
"""
from .from_facts import facts_of, graph_query, naming

# Sustainability observations reach the same ledger as everything else: one record, one decision.
DUPLICATE_MIN, REDUNDANCY_MAX = 6, 10  # structural duplicates below 6 are common noise in shared-method code
# UI components share boilerplate by construction: an arrow function that calls setState
# and renders a button is not a duplicated business rule, it is a duplicated idiom.
# The detector runs on every duplicate cluster; only large clusters of code that is not
# pure JSX reach the ledger as a business-rule claim. JSX files whose shared shape is
# small stay as facts but do not produce a CONFIRMED rule-duplication claim.
UI_LANGUAGES = {'typescript', 'tsx', 'javascript', 'jsx'}
UI_PATH_PARTS = {'components', 'pages', 'views', 'screens'}
SHARED_SIZE_FOR_UI = 30  # tokens of shared shape, not occurrence count
UI_MIN_OCCURRENCES = 4
# A shared shape this large is a function copied whole, not an idiom: precise enough to be its own detector
# (structural_duplicate, all sizes together, falls under the precision bar; eaos/data/detector-verdicts.json).
COPIED_SIZE = 50


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


def worth_a_claim(places, shared_size):
    """A duplicate cluster large enough to be a rule; UI noise stays a fact: the cluster is recorded, the claim is not."""
    if len(places) < DUPLICATE_MIN: return False
    languages = {(p.get('path') or '').rsplit('.', 1)[-1] for p in places}
    in_ui = all(any(part in UI_PATH_PARTS for part in (p.get('path') or '').split('/')) for p in places)
    ui_noise = in_ui and languages <= UI_LANGUAGES
    return not (ui_noise and (shared_size < SHARED_SIZE_FOR_UI or len(places) < UI_MIN_OCCURRENCES))


def structural_duplicates(fact_sets, add, target):
    from ..maps.system import is_test
    for fact in facts_of(fact_sets, 'fingerprint', 'duplicate_cluster'):
        places, size = fact['value']['occurrences'], fact['value'].get('shared_size', 0)
        copied = size >= COPIED_SIZE and not all(is_test(row['path']) for row in places)
        if not (copied or worth_a_claim(places, size)): continue
        where = ', '.join(f"{row['path']}:{row['start_line']} {row['symbol']}" for row in places[:4])
        add(f"{len(places)} functions are one function copied whole, up to identifier names ({where})" if copied else
            f"{len(places)} symbols share the same structure up to identifier names ({where})",
            'business_rule', 'CONFIRMED', ['static_fact'],
            'Evidence that the occurrences encode different rules that evolve for different reasons, '
            'which would make a single definition wrong rather than missing.',
            fact_ids=[fact['id']],
            render={'key': 'copied_function' if copied else 'structural_duplicate', 'params': {'count': len(places), 'where': where}},
            probe_spec=graph_query('duplicate_cluster_present', shape_sha=fact['value']['shape_sha'],
                                    expected='The same structural cluster is still present.'),
            impact={'scenario': 'Changing the rule in one occurrence and not the others makes the paths '
                                'disagree, and nothing in the code links them.'})


def sequences(fact_sets, add, target):
    for fact in [f for f in fact_sets.get('sequences', {}).get('facts', [])[:5] if f['kind'] == 'sequence_cluster']:
        members = fact['value'].get('occurrences') or []
        where = ', '.join(f"{row['path']}:{row.get('start_line')}" for row in members[:4])
        add(f"{len(members)} functions perform the same ordered sequence of calls ({where})",
            'structure', 'CONFIRMED', ['static_fact'],
            'Evidence that the shared order is coincidental rather than one orchestration copied.',
            fact_ids=[fact['id']],
            render={'key': 'sequence_duplicate', 'params': {'count': len(members), 'where': where}},
            probe_spec=graph_query('sequence_cluster_present', sequence_sha=fact['value'].get('sequence_sha'),
                                    expected='The same call sequence is still repeated.'),
            impact={'scenario': 'The orchestration is maintained in several places at once.'})


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
