"""The claims deterministic facts earn (eaos/claims.py from_facts), one builder per kind of fact, in ledger order.

Each builder is `build(fact_sets, add, target)`: `add(statement, claim_type, confidence, method, falsifier, **extra)`
appends one claim to the ledger and returns it, so a builder can bind an acceptance check to it. `target` is the audited
root, or None in a fixture. Also here: how a corroborated engine finding names the measurement it was earned by.
"""
import re

# A claim statement is one decidable sentence, and the schema caps it at 600 characters. An
# eighty-module cycle listed every member and the whole dossier failed to assemble; the members
# live in the fact, so the sentence names enough of them to recognise and says how many more.
NAMED_IN_A_STATEMENT = 6

# Maintenance hotspot: complexity that sits where change and dependency already concentrate.
BRANCH_THRESHOLD, ATTENTION_TOP, MAX_HOTSPOTS = 60, 10, 3
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

DEAD_REASONS = {'unreachable-module': ('لا تصله أي نقطة دخول إنتاجية', 'no production entry point reaches it'),
                'unused-symbol': ('لا يُذكر اسمه خارج تعريفه', 'its name appears nowhere outside its definition'),
                'unread-constant': ('لا يقرؤه شيء', 'nothing reads it')}
DEAD_VERDICT_REASONS = {'test_only': ('تذكره الاختبارات وحدها', 'only tests name it'),
                        'review': ('برنامج لا يشغّله شيء مسجّل، وقد يشغّله أحد بيده', 'a program nothing on record runs; someone may run it by hand')}
BROKEN_REASONS = {'undefined-name': ('اسم غير معرّف يرفع NameError عند تشغيل السطر', 'an undefined name that raises NameError when the line runs'),
                  'duplicate-key': ('مفتاح مكرر في قاموس واحد تضيع قيمته الأولى بصمت', 'a key written twice in one dictionary; the first value is silently lost'),
                  'missing-import': ('استيراد ملف غير موجود فتفشل الوحدة عند تحميلها', 'an import of a file that does not exist; the module fails to load'),
                  'stale-instruction': ('وثيقة تأمر بأمر لم يعد موجودًا', 'a document instructing a command that no longer exists')}


def naming(members, limit=NAMED_IN_A_STATEMENT):
    members = list(members)
    if len(members) <= limit:
        return ', '.join(members)
    return ', '.join(members[:limit]) + f' and {len(members) - limit} more'


def _facts(fact_sets, name, kind):
    return [f for f in fact_sets.get(name, {}).get('facts', []) if f['kind'] == kind]


def _graph_query(query, **specification):
    return {'probe_type': 'graph_query', 'specification': {'query': query, **specification}}


def cycles(fact_sets, add, target):
    for fact in _facts(fact_sets, 'graph', 'graph_cycle'):
        add('Import cycle between: ' + naming(fact['value']['members']), 'structure',
            'CONFIRMED', ['static_fact'], 'A resolved import graph in which these files no longer form a cycle.',
            fact_ids=[fact['id']],
            probe_spec=_graph_query('cycle_present', members=fact['value']['members'],
                                    expected='The same files still form a cycle in the resolved import graph.'),
            impact={'scenario': 'Changing any member can require changing the others together; the group cannot be tested or replaced independently.'})


def _hidden_pair(fact, linked, language_of):
    """Two code files that change together, strongly, with no import between them."""
    left, right = fact['location']['path'], fact['location']['paired_path']
    if right in linked.get(left, set()) or left in linked.get(right, set()): return False
    if fact['value']['confidence'] < 0.6: return False
    # Structural coupling needs code on both sides; a document moving with code is editorial.
    return language_of(left) is not None and language_of(right) is not None


def cochanges(fact_sets, add, target):
    from .facts.source import language_of
    history = fact_sets.get('history', {})
    if (history.get('summary', {}).get('commits_analysed') or 0) < 10: return
    linked = {fact['location']['path']: set(fact['value']['depends_on']) for fact in _facts(fact_sets, 'graph', 'graph_node')}
    pairs = sorted([f for f in history.get('facts', []) if f['kind'] == 'history_cochange'],
                   key=lambda f: (-f['value']['support'] * f['value']['confidence'], f['location']['path']))
    for fact in (f for f in pairs[:15] if _hidden_pair(f, linked, language_of)):
        left, right = fact['location']['path'], fact['location']['paired_path']
        add(f'{left} and {right} change together in {fact["value"]["support"]} commits with no visible code dependency',
            'structure', 'CONFIRMED', ['history_fact'],
            'A longer history window, or a rename, showing the pairing is coincidental rather than a shared reason to change.',
            fact_ids=[fact['id']],
            render={'key': 'cochange', 'params': {'left': left, 'right': right, 'support': fact['value']['support']}},
            probe_spec=_graph_query('no_code_dependency', left=left, right=right,
                                    expected='Neither file imports the other in the resolved graph.'),
            impact={'scenario': 'A change to one is likely to need a matching change to the other, with nothing in the code to signal it.'})


def duplicated_rules(fact_sets, add, target):
    for fact in [f for f in _facts(fact_sets, 'domain', 'domain_constant') if f['value']['duplicated']]:
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


def _hotspot_of(fact, graph_nodes, worst):
    """(graph node, central) of a function dense enough to be a hotspot where attention already is; None otherwise."""
    node = graph_nodes.get(fact['location']['path'])
    if not node: return None
    central = (node.get('attention_rank') or 999) <= ATTENTION_TOP
    if not central and fact['id'] not in worst: return None
    if (fact['value'].get('branches') or 0) < BRANCH_THRESHOLD: return None
    return node, central


def hotspots(fact_sets, add, target):
    # Rank alone is unstable: adding modules pushed the most complex function in the project out of
    # the top ten and silently dropped the finding. The worst offenders stay visible on their own merit.
    # A hotspot is one function: a class's metric sums the branches of all its methods, which no single change carries.
    ranked = sorted((fact for fact in _facts(fact_sets, 'metrics', 'metric') if fact['value'].get('scope') == 'function'),
                    key=lambda fact: -(fact['value'].get('branches') or 0))
    worst = {fact['id'] for fact in ranked[:MAX_HOTSPOTS]}
    graph_nodes = {fact['location']['path']: fact['value'] for fact in _facts(fact_sets, 'graph', 'graph_node')}
    found = [(fact, *made) for fact in ranked for made in [_hotspot_of(fact, graph_nodes, worst)] if made]
    for fact, node, central in found[:MAX_HOTSPOTS]: _hotspot(fact, node, central, add)


def _hotspot(fact, node, central, add):
    path, symbol = fact['location']['path'], fact['location'].get('symbol')
    add(f"{symbol} in {path} carries {fact['value']['branches']} branches over "
        f"{fact['value']['lines']} lines, in a file ranked {node['attention_rank']} for attention",
        'structure', 'CONFIRMED', ['static_fact'],
        'A measurement showing the branching is below the declared threshold, or evidence that the '
        'complexity is inherent to the problem and isolated behind a tested contract.',
        fact_ids=[fact['id']],
        render={'key': 'hotspot', 'params': {'symbol': symbol, 'path': path,
                                             'branches': fact['value']['branches'],
                                             'lines': fact['value']['lines'],
                                             'rank': node['attention_rank']}},
        probe_spec=_graph_query('metric_threshold', path=path, symbol=symbol, max_branches=BRANCH_THRESHOLD,
                                expected='The symbol still exceeds the declared branch threshold.'),
        impact={'scenario': 'Every change to this path passes through one dense function; '
                            'it is the most concentrated maintenance risk in the module.'
                            + ('' if central else ' It is among the most branching functions in the project.')})


def mutable_globals(fact_sets, add, target):
    for fact in [f for f in _facts(fact_sets, 'domain', 'mutable_global') if f['value'].get('mutation_scope') == 'function']:
        # State private to its module has an owner: its own functions. Whether it may stay per-process (a
        # shutdown flag) or must move out (an in-memory rate limit behind two instances) is a decision, not a
        # mechanical repair; exposed state other modules change directly is the defect.
        private = bool(fact['value'].get('encapsulated'))
        add(f"{fact['value']['name']} in {fact['location']['path']} is module-level state changed "
            f"at runtime ({fact['value']['mutated_by']}, line {fact['value']['mutated_at_line']})"
            + ('; private to its module, changed only through its own functions' if private else ''),
            'risk', 'LIKELY' if private else 'CONFIRMED', ['static_fact'],
            'The value becoming immutable, or the mutation moving behind an owner that serialises access.',
            fact_ids=[fact['id']],
            render={'key': 'mutable_global', 'params': {'name': fact['value']['name'],
                                                        'path': fact['location']['path'],
                                                        'how': fact['value']['mutated_by'],
                                                        'line': fact['value']['mutated_at_line'],
                                                        'encapsulated': private}},
            probe_spec=_graph_query('mutable_global_present', path=fact['location']['path'], name=fact['value']['name'],
                                    expected='The module-level value is still mutated at runtime.'),
            impact={'scenario': 'Two callers can observe different values depending on order, and tests '
                                'can pass in isolation while failing together.'})


def access_gaps(fact_sets, add, target):
    # A Supabase table is served to the browser through its API; without row-level security, or with a
    # write policy that checks nothing, whoever holds the public key reads or writes every row.
    domain_facts = fact_sets.get('domain', {}).get('facts', [])
    exposed = [f for f in domain_facts if f['kind'] == 'data_table' and '/supabase/' in '/' + f['location']['path']
               and f['value'].get('rls_enabled') is False and not f['value'].get('dropped')]
    open_writes = [f for f in domain_facts if f['kind'] == 'db_policy' and f['value'].get('open')
                   and f['value'].get('command') in {'ALL', 'INSERT', 'UPDATE', 'DELETE'}]
    for fact, gap in [(f, 'no_rls') for f in exposed] + [(f, 'open_write') for f in open_writes]: _access_gap(fact, gap, add)


def _access_gap(fact, gap, add):
    table = fact['value']['name'] if gap == 'no_rls' else fact['value']['table']
    policy = fact['value'].get('name') if gap == 'open_write' else None
    what = ('has row-level security disabled' if gap == 'no_rls'
            else f"has a {fact['value']['command']} policy \"{policy}\" that checks nothing (true)")
    add(f"Table {table} ({fact['location']['path']}:{fact['location']['start_line']}) {what}",
        'risk', 'CONFIRMED', ['static_fact'],
        'A later migration enabling row-level security on the table, or replacing the policy '
        'condition with one that ties each row to its owner.',
        fact_ids=[fact['id']],
        render={'key': 'access_gap_' + gap, 'params': {'table': table, 'path': fact['location']['path'],
                                                        'line': fact['location']['start_line'],
                                                        'gap': gap, 'policy': policy or '—'}},
        probe_spec=_graph_query('access_gap_present', table=table, gap=gap, policy=policy,
                                expected='The table is still exposed in the net migration state.'),
        impact={'scenario': 'Anyone holding the public API key can read or change rows of this '
                            'table that belong to other users.'})


def external_writes(fact_sets, add, target):
    for fact in _facts(fact_sets, 'domain', 'external_state_write'):
        add(f"{fact['location']['path']} writes into {fact['value']['module']}."
            f"{fact['value']['attribute']}, state it does not own",
            'structure', 'CONFIRMED', ['static_fact'],
            'The write moving into the owning module behind a named operation.',
            fact_ids=[fact['id']],
            render={'key': 'external_write', 'params': {'path': fact['location']['path'],
                                                        'module': fact['value']['module'],
                                                        'attribute': fact['value']['attribute']}},
            probe_spec=_graph_query('external_write_present', path=fact['location']['path'],
                                    module=fact['value']['module'], attribute=fact['value']['attribute'],
                                    expected='The cross-module assignment is still present.'),
            impact={'scenario': 'The owning module cannot guarantee its own invariant, because another '
                                'module assigns into it directly.'})


def worth_a_claim(places, shared_size):
    """A duplicate cluster large enough to be a rule; UI noise stays a fact: the cluster is recorded, the claim is not."""
    if len(places) < DUPLICATE_MIN: return False
    languages = {(p.get('path') or '').rsplit('.', 1)[-1] for p in places}
    in_ui = all(any(part in UI_PATH_PARTS for part in (p.get('path') or '').split('/')) for p in places)
    ui_noise = in_ui and languages <= UI_LANGUAGES
    return not (ui_noise and (shared_size < SHARED_SIZE_FOR_UI or len(places) < UI_MIN_OCCURRENCES))


def structural_duplicates(fact_sets, add, target):
    for fact in _facts(fact_sets, 'fingerprint', 'duplicate_cluster'):
        places = fact['value']['occurrences']
        if not worth_a_claim(places, fact['value'].get('shared_size', 0)): continue
        where = ', '.join(f"{row['path']}:{row['start_line']} {row['symbol']}" for row in places[:4])
        add(f"{len(places)} symbols share the same structure up to identifier names ({where})",
            'business_rule', 'CONFIRMED', ['static_fact'],
            'Evidence that the occurrences encode different rules that evolve for different reasons, '
            'which would make a single definition wrong rather than missing.',
            fact_ids=[fact['id']],
            render={'key': 'structural_duplicate', 'params': {'count': len(places), 'where': where}},
            probe_spec=_graph_query('duplicate_cluster_present', shape_sha=fact['value']['shape_sha'],
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
            probe_spec=_graph_query('sequence_cluster_present', sequence_sha=fact['value'].get('sequence_sha'),
                                    expected='The same call sequence is still repeated.'),
            impact={'scenario': 'The orchestration is maintained in several places at once.'})


def redundant_work(fact_sets, add, target):
    for fact in _facts(fact_sets, 'redundancy', 'redundancy')[:REDUNDANCY_MAX]:
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
            probe_spec=_graph_query('redundancy_present', path=fact['location']['path'],
                                    line=fact['location']['start_line'], kind=kind, callee=fact['value']['callee'],
                                    expected='The redundant work is still present at that location.'),
            impact={'scenario': 'The path does more work than its result requires, on every execution.'})


def _assess(claim, built):
    """The acceptance check bound to a claim, when its assessment could be built."""
    if built: claim['assessment'], claim['checks'] = built['assessment'], built['checks']


def policy_violations(fact_sets, add, target):
    from .policy_assessment import build_assessment
    for fact in _facts(fact_sets, 'policy', 'policy_violation'):
        claim = add(f"{fact['location']['path']} imports {fact['value']['to_path']}, which the declared "
                    f"policy forbids ({fact['value']['from_layer']} → {fact['value']['to_layer']})",
                    'structure', 'CONFIRMED', ['static_fact'],
                    'The edge disappearing from the resolved graph, or the policy being changed deliberately with a reason.',
                    fact_ids=[fact['id']],
                    render={'key': 'policy', 'params': {'path': fact['location']['path'],
                                                        'to': fact['value']['to_path'],
                                                        'from_layer': fact['value']['from_layer'],
                                                        'to_layer': fact['value']['to_layer']}},
                    probe_spec=_graph_query('policy_violation_present', path=fact['location']['path'],
                                            to_path=fact['value']['to_path'],
                                            expected='The forbidden edge is still present in the resolved graph.'),
                    impact={'scenario': fact['value']['reason']})
        if target is not None: _assess(claim, build_assessment(claim, fact_sets, target))


def trace_gaps(fact_sets, add, target):
    for fact in [f for f in fact_sets.get('flows', {}).get('facts', []) if f['value']['unresolved_steps'] > 2][:10]:
        entry = fact['value']['entry']
        add(f"Flow {fact['value']['flow_id']} ({entry['surface']} {entry['route']}) stops at "
            f"{fact['value']['unresolved_steps']} unresolvable calls",
            'capability_gap', 'CONFIRMED', ['static_fact'],
            'A resolver or runtime trace that follows those calls to their targets.',
            fact_ids=[fact['id']],
            render={'key': 'trace_gap', 'params': {'flow': fact['value']['flow_id'],
                                                   'surface': entry['surface'], 'route': str(entry['route']),
                                                   'count': fact['value']['unresolved_steps']}},
            probe_spec=_graph_query('flow_has_unresolved_steps', flow_id=fact['value']['flow_id'],
                                    expected='The traced flow still stops at calls the resolver cannot follow.'),
            impact={'scenario': 'The end-to-end behaviour of this entry point is not fully visible from source alone.'})


def dead_code(fact_sets, add, target):
    for fact in (fact_sets.get('deadcode') or {}).get('facts', []):
        verdict = (fact['value'].get('adjudication') or {}).get('verdict')
        if verdict in ('confirmed', 'test_only', 'review'): _dead(fact, verdict, add, (fact_sets, target))


def _dead(fact, verdict, add, context):
    value, location = fact['value'], fact['location']
    # test_only and review are candidates to ask about, not defects to remove: they render as dead_code_review.
    test_only = verdict in ('test_only', 'review')
    reason = DEAD_REASONS[value['rule']]
    ar, en = DEAD_VERDICT_REASONS.get(verdict, reason)
    subject = value['message'].split('`')[1]
    claim = add(value['message'], 'structure', 'LIKELY' if test_only else 'CONFIRMED', ['static_fact'],
                ('A test that pins it as a contract the product relies on, or a production path the text search missed.' if test_only else
                 'A production path that reaches it: an import, a call, or a registry entry naming it that the text search missed.'),
                fact_ids=[fact['id']],
                render={'key': 'dead_code', 'params': {'subject': subject, 'reason_ar': ar, 'reason_en': en}},
                probe_spec=_graph_query('dead_code_present', path=location['path'], symbol=location.get('symbol'), rule=value['rule'],
                                        expected='The candidate is still unreached and unreferenced in the current snapshot.'),
                impact={'scenario': 'Code nobody runs is still read, maintained and reviewed, and can be switched back on without anyone noticing.'})
    fact_sets, target = context
    if test_only: claim['render']['key'] = 'dead_code_review'
    elif target is not None:
        from .dead_code_assessment import build_assessment as dead_code_assessment
        _assess(claim, dead_code_assessment(claim, fact_sets, target))


def broken_code(fact_sets, add, target):
    for fact in (fact_sets.get('broken') or {}).get('facts', []):
        value, location = fact['value'], fact['location']
        ar, en = BROKEN_REASONS[value['rule']]
        add(value['message'], 'risk' if value['severity'] == 'high' else 'structure', 'CONFIRMED', ['static_fact'],
            'The name, key, file or command existing after all: a definition, a file or a subcommand the text reading missed.',
            fact_ids=[fact['id']],
            render={'key': 'broken_code', 'params': {'path': location['path'], 'line': location.get('start_line'),
                                                     'subject': str(location.get('symbol')), 'reason_ar': ar, 'reason_en': en}},
            probe_spec=_graph_query('broken_code_present', path=location['path'], symbol=location.get('symbol'), rule=value['rule'],
                                    expected='The same broken reference is still in the current snapshot.'),
            impact={'scenario': en[0].upper() + en[1:] + '.'})


def _advisory(fact):
    """An osv-scanner finding of a vulnerable locked version."""
    value = fact.get('value') or {}
    return fact.get('kind') == 'engine_finding' and value.get('kind') == 'vulnerability' and value.get('engine') == 'osv-scanner'


def vulnerable_dependencies(fact_sets, add, target):
    # A locked version the advisory database lists as affected is a deterministic finding: one engine suffices.
    for fact in filter(_advisory, (fact_sets.get('external') or {}).get('facts', [])):
        claim = _vulnerable(fact, add)
        if target is not None:
            from .dependency_assessment import build_assessment as dependency_assessment
            _assess(claim, dependency_assessment(claim, fact_sets, target))


def _vulnerable(fact, add):
    value = fact.get('value') or {}
    numbers = {m['name']: m['value'] for m in value.get('measurements') or []}
    ecosystem, _, rest = str(fact['location'].get('symbol')).partition(':')
    package, _, installed = rest.rpartition('@')
    ids = numbers.get('advisory_ids') or []
    return add(value['message'], 'risk', 'CONFIRMED', ['static_fact'],
               'The locked version being another, or the OSV database withdrawing the advisory.',
               fact_ids=[fact['id']],
               render={'key': 'vulnerable_dependency',
                       'params': {'package': package, 'installed': installed, 'count': len(ids),
                                  'ids': ', '.join(ids[:3]) + (' …' if len(ids) > 3 else ''),
                                  'severity': numbers.get('severity'), 'fixed': numbers.get('fixed_in') or '—'}},
               probe_spec=_graph_query('vulnerable_dependency_present', package=fact['location'].get('symbol'),
                                       expected='The same package version is still reported vulnerable.'),
               impact={'scenario': 'Every user runs a version with a published vulnerability; the fix is published too.'})


# The builders in ledger order: the claims are numbered in this order.
BUILDERS = (cycles, cochanges, duplicated_rules, hotspots, mutable_globals, access_gaps, external_writes,
            structural_duplicates, sequences, redundant_work, policy_violations, trace_gaps, dead_code, broken_code,
            vulnerable_dependencies)


# ---------------------------------------------------------------- what a corroborated engine finding measured

def _extract_measurement(fact, name):
    for m in fact.get('value', {}).get('measurements', []) or []:
        if m.get('name') == name:
            return m
    return None


def _number(value):
    return int(value) if isinstance(value, float) and value.is_integer() else value


def _complexity(facts):
    # reforge names it function.complexity and declares a threshold; codegraph names it complexity
    # without one. A measurement that carries its threshold is preferred over one that does not.
    found = [m for fact in facts for name in ('function.complexity', 'cyclomatic_complexity', 'cognitive_complexity', 'complexity')
             for m in [_extract_measurement(fact, name)] if m is not None and m.get('value') is not None]
    found.sort(key=lambda m: m.get('threshold') is None)
    if not found: return None
    if found[0].get('threshold') is not None:
        return 'engine_cluster_complexity', {'value': _number(found[0]['value']), 'threshold': _number(found[0]['threshold'])}
    return 'engine_cluster_complexity_value', {'value': _number(found[0]['value'])}


def _literal_duplication(facts):
    # reforge reports the occurrence count as group.size; its sites list also carries file-level
    # entries, so counting sites overstates it. jscpd reports one site per copy.
    sizes = [m['value'] for fact in facts for m in [_extract_measurement(fact, 'group.size')]
             if m is not None and m.get('value') is not None]
    counts = sizes or [len((fact.get('value') or {}).get('sites') or []) for fact in facts]
    return ('engine_cluster_literal_duplication', {'sites': _number(max(counts))}) if any(counts) else None


def _coupling_parts(message):
    return [label + ' ' + found.group(1) for label in ('fan-in', 'fan-out')
            for found in [re.search(label + r'\s+(\d+)', message)] if found]


def _coupling(facts):
    for parts in (_coupling_parts((fact.get('value') or {}).get('message') or '') for fact in facts):
        if parts: return 'engine_cluster_coupling', {'measure': ', '.join(parts)}
    return None


def _dead_symbol(fact):
    """The dead symbol a finding names: its location's symbol, the one its message names, else its first site's path."""
    location = fact.get('location') or {}
    symbol = location.get('symbol')
    if symbol and symbol != location.get('path'): return symbol
    found = re.search(r'(?:function|method|class)\s+([\w./]+)', (fact.get('value') or {}).get('message') or '')
    if found: return found.group(1)
    sites = (fact.get('value') or {}).get('sites') or []
    return sites[0]['path'] if sites and sites[0].get('path') else None


def _dead_code_measure(facts):
    for symbol in map(_dead_symbol, facts):
        if symbol: return 'engine_cluster_dead_code', {'symbol': symbol}
    return None


MEASURES = {'complexity': _complexity, 'literal_duplication': _literal_duplication, 'coupling': _coupling,
            'dead_code': _dead_code_measure}


def engine_measurement(kind, cluster, fact_sets):
    """Return ``(impact_key, params)`` naming the measurement a corroborated finding was earned by.

    The key selects a template in ``compose.labels.IMPACTS`` for every language, so the report reads
    the same measurement the claim carries. With no measurement the key says so rather than guessing.
    """
    by_id = {fact['id']: fact for fact in (fact_sets.get('external') or {}).get('facts', [])}
    facts = [by_id.get(fid) for fid in cluster.get('fact_ids', [])]
    facts = [fact for fact in facts if fact and (fact.get('value') or {}).get('kind') == kind]
    measure = MEASURES.get(kind)
    return (measure(facts) if measure else None) or ('engine_cluster_unmeasured', {})
