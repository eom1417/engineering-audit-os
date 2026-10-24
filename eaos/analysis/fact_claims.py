"""The claims deterministic facts earn (eaos/analysis/claims.py from_facts), one builder per kind of fact; the ledger
numbers them in the order of claims.BUILDERS, which also takes the builders of code written twice
(eaos/analysis/duplicate_claims.py) and of security weaknesses (eaos/analysis/weaknesses.py).

Each builder is `build(fact_sets, add, target)`: `add(statement, claim_type, confidence, method, falsifier, **extra)`
appends one claim to the ledger and returns it, so a builder can bind an acceptance check to it. `target` is the audited
root, or None in a fixture.
"""
# A claim statement is one decidable sentence, and the schema caps it at 600 characters. An
# eighty-module cycle listed every member and the whole dossier failed to assemble; the members
# live in the fact, so the sentence names enough of them to recognise and says how many more.
NAMED_IN_A_STATEMENT = 6


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


def facts_of(fact_sets, name, kind):
    """The facts of one kind in one fact set."""
    return [f for f in fact_sets.get(name, {}).get('facts', []) if f['kind'] == kind]


def graph_query(query, **specification):
    """A claim's probe: a question the resolved graph and the facts answer again on a changed copy."""
    return {'probe_type': 'graph_query', 'specification': {'query': query, **specification}}


def cycles(fact_sets, add, target):
    for fact in facts_of(fact_sets, 'graph', 'graph_cycle'):
        add('Import cycle between: ' + naming(fact['value']['members']), 'structure',
            'CONFIRMED', ['static_fact'], 'A resolved import graph in which these files no longer form a cycle.',
            fact_ids=[fact['id']],
            probe_spec=graph_query('cycle_present', members=fact['value']['members'],
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
    from ..facts.source import language_of
    history = fact_sets.get('history', {})
    if (history.get('summary', {}).get('commits_analysed') or 0) < 10: return
    linked = {fact['location']['path']: set(fact['value']['depends_on']) for fact in facts_of(fact_sets, 'graph', 'graph_node')}
    pairs = sorted([f for f in history.get('facts', []) if f['kind'] == 'history_cochange'],
                   key=lambda f: (-f['value']['support'] * f['value']['confidence'], f['location']['path']))
    for fact in (f for f in pairs[:15] if _hidden_pair(f, linked, language_of)):
        left, right = fact['location']['path'], fact['location']['paired_path']
        add(f'{left} and {right} change together in {fact["value"]["support"]} commits with no visible code dependency',
            'structure', 'CONFIRMED', ['history_fact'],
            'A longer history window, or a rename, showing the pairing is coincidental rather than a shared reason to change.',
            fact_ids=[fact['id']],
            render={'key': 'cochange', 'params': {'left': left, 'right': right, 'support': fact['value']['support']}},
            probe_spec=graph_query('no_code_dependency', left=left, right=right,
                                    expected='Neither file imports the other in the resolved graph.'),
            impact={'scenario': 'A change to one is likely to need a matching change to the other, with nothing in the code to signal it.'})


def hotspots(fact_sets, add, target):
    """Every production function or method past the complexity limit of the code laws (eaos/core/code_laws.py), each a
    claim; those of one file become one card (eaos/analysis/plan.py GROUPED). It held to 60 branches and the three worst before,
    so a project's check named 3 of its 105 functions past the limit and scored its structure as sound."""
    from ..core.code_laws import MAX_COMPLEXITY
    from .system_map import is_test
    nodes = {fact['location']['path']: fact['value'] for fact in facts_of(fact_sets, 'graph', 'graph_node')}
    for fact in sorted(facts_of(fact_sets, 'metrics', 'metric'), key=lambda fact: -(fact['value'].get('branches') or 0)):
        value, path = fact['value'], fact['location']['path']
        if value.get('scope') in ('function', 'method') and (value.get('branches') or 0) > MAX_COMPLEXITY and not is_test(path):
            _hotspot(fact, (nodes.get(path) or {}).get('attention_rank'), MAX_COMPLEXITY, add)


def _hotspot(fact, rank, limit, add):
    path, symbol = fact['location']['path'], fact['location'].get('symbol')
    add(f"{symbol} in {path} carries {fact['value']['branches']} branches over "
        f"{fact['value']['lines']} lines, in a file ranked {rank or '-'} for attention",
        'structure', 'CONFIRMED', ['static_fact'],
        'A measurement showing the branching is within the limit, or evidence that the '
        'complexity is inherent to the problem and isolated behind a tested contract.',
        fact_ids=[fact['id']],
        render={'key': 'hotspot', 'params': {'symbol': symbol, 'path': path,
                                             'branches': fact['value']['branches'],
                                             'lines': fact['value']['lines'],
                                             'rank': rank or '-'}},
        probe_spec=graph_query('metric_threshold', path=path, symbol=symbol, max_branches=limit,
                                expected='The symbol is still past the complexity limit.'),
        impact={'scenario': f'Every change to this path passes through one function of more than {limit} decisions: '
                            'hard to read, to test and to change without breaking it.'})


def large_modules(fact_sets, add, target):
    """A production module past the line limit of the code laws: it holds more than one responsibility, so a change to
    one of them reads and risks the others. The card splits it along its responsibilities, its outside kept."""
    from ..core.code_laws import MAX_LINES
    from .system_map import is_test
    nodes = {fact['location']['path']: fact['value'] for fact in facts_of(fact_sets, 'graph', 'graph_node')}
    for fact in sorted(facts_of(fact_sets, 'metrics', 'metric'), key=lambda f: -(f['value'].get('lines') or 0)):
        value, path = fact['value'], fact['location']['path']
        if value.get('scope') != 'file' or (value.get('lines') or 0) <= MAX_LINES or is_test(path): continue
        params = _module_params(path, value, nodes.get(path) or {}, MAX_LINES)
        add(f"{path} has {params['lines']} lines and {params['symbols']} definitions, past the limit of {MAX_LINES} lines "
            f"for one module; {params['fan_in']} modules import it and it imports {params['fan_out']}",
            'structure', 'CONFIRMED', ['static_fact'],
            'A measurement showing the module is within the line limit, or that its definitions serve one responsibility '
            'no split would make clearer.',
            fact_ids=[fact['id']], render={'key': 'large_module', 'params': params},
            probe_spec=graph_query('module_size', path=path, max_lines=MAX_LINES,
                                    expected='The module is still past the line limit.'),
            impact={'scenario': 'Every change to one of its responsibilities reads and risks the others; '
                                'it grows wherever a new feature lands.'})


def _module_params(path, value, node, limit):
    """A large module's numbers: its lines and definitions, the limit, and the imports in and out."""
    return {'path': path, 'lines': value['lines'], 'symbols': value.get('symbols') or 0, 'limit': limit,
            'fan_in': node.get('fan_in') or 0, 'fan_out': node.get('fan_out') or 0}


def mutable_globals(fact_sets, add, target):
    for fact in [f for f in facts_of(fact_sets, 'domain', 'mutable_global') if f['value'].get('mutation_scope') == 'function']:
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
            probe_spec=graph_query('mutable_global_present', path=fact['location']['path'], name=fact['value']['name'],
                                    expected='The module-level value is still mutated at runtime.'),
            impact={'scenario': 'Two callers can observe different values depending on order, and tests '
                                'can pass in isolation while failing together.'})


def access_gaps(fact_sets, add, target):
    # A Supabase table is served to the browser through its API; without row-level security, or with a
    # write policy that checks nothing, whoever holds the public key reads or writes every row.
    domain_facts = fact_sets.get('domain', {}).get('facts', [])
    gaps = [(f, 'no_rls') for f in filter(_exposed, domain_facts)] + [(f, 'open_write') for f in filter(_open_write, domain_facts)]
    for fact, gap in gaps: _access_gap(fact, gap, add)


def _exposed(fact):
    """A Supabase table, still there, with row-level security disabled."""
    return (fact['kind'] == 'data_table' and '/supabase/' in '/' + fact['location']['path']
            and fact['value'].get('rls_enabled') is False and not fact['value'].get('dropped'))


def _open_write(fact):
    """A policy that lets anyone write: its condition checks nothing."""
    return fact['kind'] == 'db_policy' and fact['value'].get('open') and fact['value'].get('command') in {'ALL', 'INSERT', 'UPDATE', 'DELETE'}


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
        probe_spec=graph_query('access_gap_present', table=table, gap=gap, policy=policy,
                                expected='The table is still exposed in the net migration state.'),
        impact={'scenario': 'Anyone holding the public API key can read or change rows of this '
                            'table that belong to other users.'})


def external_writes(fact_sets, add, target):
    for fact in facts_of(fact_sets, 'domain', 'external_state_write'):
        add(f"{fact['location']['path']} writes into {fact['value']['module']}."
            f"{fact['value']['attribute']}, state it does not own",
            'structure', 'CONFIRMED', ['static_fact'],
            'The write moving into the owning module behind a named operation.',
            fact_ids=[fact['id']],
            render={'key': 'external_write', 'params': {'path': fact['location']['path'],
                                                        'module': fact['value']['module'],
                                                        'attribute': fact['value']['attribute']}},
            probe_spec=graph_query('external_write_present', path=fact['location']['path'],
                                    module=fact['value']['module'], attribute=fact['value']['attribute'],
                                    expected='The cross-module assignment is still present.'),
            impact={'scenario': 'The owning module cannot guarantee its own invariant, because another '
                                'module assigns into it directly.'})


def _assess(claim, built):
    """The acceptance check bound to a claim, when its assessment could be built."""
    if built: claim['assessment'], claim['checks'] = built['assessment'], built['checks']


def policy_violations(fact_sets, add, target):
    from .policy_assessment import build_assessment
    for fact in facts_of(fact_sets, 'policy', 'policy_violation'):
        claim = add(f"{fact['location']['path']} imports {fact['value']['to_path']}, which the declared "
                    f"policy forbids ({fact['value']['from_layer']} → {fact['value']['to_layer']})",
                    'structure', 'CONFIRMED', ['static_fact'],
                    'The edge disappearing from the resolved graph, or the policy being changed deliberately with a reason.',
                    fact_ids=[fact['id']],
                    render={'key': 'policy', 'params': {'path': fact['location']['path'],
                                                        'to': fact['value']['to_path'],
                                                        'from_layer': fact['value']['from_layer'],
                                                        'to_layer': fact['value']['to_layer']}},
                    probe_spec=graph_query('policy_violation_present', path=fact['location']['path'],
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
            probe_spec=graph_query('flow_has_unresolved_steps', flow_id=fact['value']['flow_id'],
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
                probe_spec=graph_query('dead_code_present', path=location['path'], symbol=location.get('symbol'), rule=value['rule'],
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
            probe_spec=graph_query('broken_code_present', path=location['path'], symbol=location.get('symbol'), rule=value['rule'],
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
               probe_spec=graph_query('vulnerable_dependency_present', package=fact['location'].get('symbol'), engines=[value['engine']],
                                       expected='The same package version is still reported vulnerable.'),
               impact={'scenario': 'Every user runs a version with a published vulnerability; the fix is published too.'})
