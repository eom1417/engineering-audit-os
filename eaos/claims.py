"""One ledger for everything the system asserts, with its source, its confidence and its refutation.

A fact is produced by an extractor and is reproducible. A claim is an interpretation and must name
what would disprove it. A question is an admitted gap. Nothing rendered may exist outside this ledger.
"""
from datetime import datetime, timezone
import json
from .vocabulary import schema_errors
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


# A claim statement is one decidable sentence, and the schema caps it at 600 characters. An
# eighty-module cycle listed every member and the whole dossier failed to assemble; the members
# live in the fact, so the sentence names enough of them to recognise and says how many more.
NAMED_IN_A_STATEMENT = 6


def naming(members, limit=NAMED_IN_A_STATEMENT):
    members = list(members)
    if len(members) <= limit:
        return ', '.join(members)
    return ', '.join(members[:limit]) + f' and {len(members) - limit} more'


def from_facts(fact_sets):
    """Deterministic facts promoted to claims keep CONFIRMED status and name their own refutation."""
    claims, index = [], 0
    graph = fact_sets.get('graph', {})
    for fact in [f for f in graph.get('facts', []) if f['kind'] == 'graph_cycle']:
        index += 1
        claims.append(make(index, 'Import cycle between: ' + naming(fact['value']['members']), 'structure',
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
                           render={'key': 'cochange', 'params': {'left': left, 'right': right,
                                                                 'support': fact['value']['support']}},
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
                           render={'key': 'duplicated_rule', 'params': {'name': fact['value']['name'],
                                                                        'count': len(fact['value']['definitions']),
                                                                        'places': places,
                                                                        'differs': 'yes' if differs else 'no'}},
                           probe_spec={'probe_type': 'absence_search', 'specification': {'patterns': [fact['value']['name']],
                                                                                         'search_scope': ['source', 'test'],
                                                                                         'expected': 'The name is defined in more than one file with no import linking them.'}},
                           impact={'scenario': 'Changing the rule in one place and not the others makes two paths disagree'
                                               + (' — and they already hold different values.' if differs else '.')}))
    # Maintenance hotspot: complexity that sits where change and dependency already concentrate.
    BRANCH_THRESHOLD, ATTENTION_TOP, MAX_HOTSPOTS = 60, 10, 3
    hotspots = 0
    # Rank alone is unstable: adding modules pushed the most complex function in the project out of
    # the top ten and silently dropped the finding. The worst offenders stay visible on their own merit.
    ranked_symbols = sorted((fact for fact in fact_sets.get('metrics', {}).get('facts', [])
                             if fact['kind'] == 'metric' and fact['value'].get('scope') != 'file'),
                            key=lambda fact: -(fact['value'].get('branches') or 0))
    worst = {fact['id'] for fact in ranked_symbols[:MAX_HOTSPOTS]}
    graph_nodes = {fact['location']['path']: fact['value'] for fact in graph.get('facts', []) if fact['kind'] == 'graph_node'}
    for fact in sorted(fact_sets.get('metrics', {}).get('facts', []),
                       key=lambda f: -(f['value'].get('branches') or 0)):
        if fact['kind'] != 'metric' or fact['value'].get('scope') == 'file': continue
        path, symbol = fact['location']['path'], fact['location'].get('symbol')
        node = graph_nodes.get(path)
        if not node: continue
        central = (node.get('attention_rank') or 999) <= ATTENTION_TOP
        if not central and fact['id'] not in worst: continue
        if (fact['value'].get('branches') or 0) < BRANCH_THRESHOLD: continue
        if hotspots >= MAX_HOTSPOTS: break
        hotspots += 1
        index += 1
        claims.append(make(index, f"{symbol} in {path} carries {fact['value']['branches']} branches over "
                                  f"{fact['value']['lines']} lines, in a file ranked {node['attention_rank']} for attention",
                           'structure', 'CONFIRMED', ['static_fact'], [],
                           'A measurement showing the branching is below the declared threshold, or evidence that the '
                           'complexity is inherent to the problem and isolated behind a tested contract.',
                           fact_ids=[fact['id']],
                           render={'key': 'hotspot', 'params': {'symbol': symbol, 'path': path,
                                                                'branches': fact['value']['branches'],
                                                                'lines': fact['value']['lines'],
                                                                'rank': node['attention_rank']}},
                           probe_spec={'probe_type': 'graph_query',
                                       'specification': {'query': 'metric_threshold', 'path': path, 'symbol': symbol,
                                                         'max_branches': BRANCH_THRESHOLD,
                                                         'expected': 'The symbol still exceeds the declared branch threshold.'}},
                           impact={'scenario': 'Every change to this path passes through one dense function; '
                                               'it is the most concentrated maintenance risk in the module.'
                                               + ('' if central else ' It is among the most branching functions in the project.')}))
    domain_facts = fact_sets.get('domain', {}).get('facts', [])
    for fact in [f for f in domain_facts if f['kind'] == 'mutable_global' and f['value'].get('mutation_scope') == 'function']:
        index += 1
        claims.append(make(index, f"{fact['value']['name']} in {fact['location']['path']} is module-level state changed "
                                  f"at runtime ({fact['value']['mutated_by']}, line {fact['value']['mutated_at_line']})",
                           'risk', 'CONFIRMED', ['static_fact'], [],
                           'The value becoming immutable, or the mutation moving behind an owner that serialises access.',
                           fact_ids=[fact['id']],
                           render={'key': 'mutable_global', 'params': {'name': fact['value']['name'],
                                                                       'path': fact['location']['path'],
                                                                       'how': fact['value']['mutated_by'],
                                                                       'line': fact['value']['mutated_at_line']}},
                           probe_spec={'probe_type': 'graph_query',
                                       'specification': {'query': 'mutable_global_present', 'path': fact['location']['path'],
                                                         'name': fact['value']['name'],
                                                         'expected': 'The module-level value is still mutated at runtime.'}},
                           impact={'scenario': 'Two callers can observe different values depending on order, and tests '
                                               'can pass in isolation while failing together.'}))
    for fact in [f for f in domain_facts if f['kind'] == 'external_state_write']:
        index += 1
        claims.append(make(index, f"{fact['location']['path']} writes into {fact['value']['module']}."
                                  f"{fact['value']['attribute']}, state it does not own",
                           'structure', 'CONFIRMED', ['static_fact'], [],
                           'The write moving into the owning module behind a named operation.',
                           fact_ids=[fact['id']],
                           render={'key': 'external_write', 'params': {'path': fact['location']['path'],
                                                                       'module': fact['value']['module'],
                                                                       'attribute': fact['value']['attribute']}},
                           probe_spec={'probe_type': 'graph_query',
                                       'specification': {'query': 'external_write_present', 'path': fact['location']['path'],
                                                         'module': fact['value']['module'], 'attribute': fact['value']['attribute'],
                                                         'expected': 'The cross-module assignment is still present.'}},
                           impact={'scenario': 'The owning module cannot guarantee its own invariant, because another '
                                               'module assigns into it directly.'}))
    # Sustainability observations reach the same ledger as everything else: one record, one decision.
    DUPLICATE_MIN, REDUNDANCY_MAX = 2, 10
    for fact in fact_sets.get('fingerprint', {}).get('facts', []):
        if fact['kind'] != 'duplicate_cluster': continue
        places = fact['value']['occurrences']
        if len(places) < DUPLICATE_MIN: continue
        index += 1
        where = ', '.join(f"{row['path']}:{row['start_line']} {row['symbol']}" for row in places[:4])
        claims.append(make(index, f"{len(places)} symbols share the same structure up to identifier names ({where})",
                           'business_rule', 'CONFIRMED', ['static_fact'], [],
                           'Evidence that the occurrences encode different rules that evolve for different reasons, '
                           'which would make a single definition wrong rather than missing.',
                           fact_ids=[fact['id']],
                           render={'key': 'structural_duplicate',
                                   'params': {'count': len(places), 'where': where}},
                           probe_spec={'probe_type': 'graph_query',
                                       'specification': {'query': 'duplicate_cluster_present',
                                                         'shape_sha': fact['value']['shape_sha'],
                                                         'expected': 'The same structural cluster is still present.'}},
                           impact={'scenario': 'Changing the rule in one occurrence and not the others makes the paths '
                                               'disagree, and nothing in the code links them.'}))
    for fact in fact_sets.get('sequences', {}).get('facts', [])[:5]:
        if fact['kind'] != 'sequence_cluster': continue
        index += 1
        members = fact['value'].get('occurrences') or []
        where = ', '.join(f"{row['path']}:{row.get('start_line')}" for row in members[:4])
        claims.append(make(index, f"{len(members)} functions perform the same ordered sequence of calls ({where})",
                           'structure', 'CONFIRMED', ['static_fact'], [],
                           'Evidence that the shared order is coincidental rather than one orchestration copied.',
                           fact_ids=[fact['id']],
                           render={'key': 'sequence_duplicate', 'params': {'count': len(members), 'where': where}},
                           probe_spec={'probe_type': 'graph_query',
                                       'specification': {'query': 'sequence_cluster_present',
                                                         'sequence_sha': fact['value'].get('sequence_sha'),
                                                         'expected': 'The same call sequence is still repeated.'}},
                           impact={'scenario': 'The orchestration is maintained in several places at once.'}))
    redundant = [fact for fact in fact_sets.get('redundancy', {}).get('facts', []) if fact['kind'] == 'redundancy']
    for fact in redundant[:REDUNDANCY_MAX]:
        index += 1
        kind = fact['value']['kind']
        location = f"{fact['location']['path']}:{fact['location']['start_line']}"
        claims.append(make(index, f"{kind} at {location} in {fact['location'].get('symbol')}: {fact['value']['callee']}",
                           'risk' if kind == 'n_plus_one' else 'structure', 'CONFIRMED', ['static_fact'], [],
                           'Evidence that the repetition is required — a different result per call, or a dependency on '
                           'state that changes between the two.',
                           fact_ids=[fact['id']],
                           render={'key': 'redundant_work',
                                   'params': {'kind': kind, 'location': location,
                                              'symbol': fact['location'].get('symbol'),
                                              'callee': fact['value']['callee']}},
                           probe_spec={'probe_type': 'graph_query',
                                       'specification': {'query': 'redundancy_present', 'path': fact['location']['path'],
                                                         'line': fact['location']['start_line'], 'kind': kind,
                                                         'callee': fact['value']['callee'],
                                                         'expected': 'The redundant work is still present at that location.'}},
                           impact={'scenario': 'The path does more work than its result requires, on every execution.'}))
    for fact in fact_sets.get('policy', {}).get('facts', []):
        if fact['kind'] != 'policy_violation': continue
        index += 1
        claims.append(make(index, f"{fact['location']['path']} imports {fact['value']['to_path']}, which the declared "
                                  f"policy forbids ({fact['value']['from_layer']} → {fact['value']['to_layer']})",
                           'structure', 'CONFIRMED', ['static_fact'], [],
                           'The edge disappearing from the resolved graph, or the policy being changed deliberately with a reason.',
                           fact_ids=[fact['id']],
                           render={'key': 'policy', 'params': {'path': fact['location']['path'],
                                                               'to': fact['value']['to_path'],
                                                               'from_layer': fact['value']['from_layer'],
                                                               'to_layer': fact['value']['to_layer']}},
                           probe_spec={'probe_type': 'graph_query',
                                       'specification': {'query': 'policy_violation_present',
                                                         'path': fact['location']['path'],
                                                         'to_path': fact['value']['to_path'],
                                                         'expected': 'The forbidden edge is still present in the resolved graph.'}},
                           impact={'scenario': fact['value']['reason']}))
    flows = fact_sets.get('flows', {})
    for fact in [f for f in flows.get('facts', []) if f['value']['unresolved_steps'] > 2][:10]:
        index += 1
        entry = fact['value']['entry']
        claims.append(make(index, f"Flow {fact['value']['flow_id']} ({entry['surface']} {entry['route']}) stops at "
                                  f"{fact['value']['unresolved_steps']} unresolvable calls",
                           'capability_gap', 'CONFIRMED', ['static_fact'], [],
                           'A resolver or runtime trace that follows those calls to their targets.',
                           fact_ids=[fact['id']],
                           render={'key': 'trace_gap', 'params': {'flow': fact['value']['flow_id'],
                                                                  'surface': entry['surface'], 'route': str(entry['route']),
                                                                  'count': fact['value']['unresolved_steps']}},
                           probe_spec={'probe_type': 'graph_query', 'specification': {'query': 'flow_has_unresolved_steps', 'flow_id': fact['value']['flow_id'],
                                                                                      'expected': 'The traced flow still stops at calls the resolver cannot follow.'}},
                           impact={'scenario': 'The end-to-end behaviour of this entry point is not fully visible from source alone.'}))
    claims += from_engines(fact_sets, len(claims))
    return claims


ENGINE_KIND_WORDS = {'complexity': 'تعقيد', 'coupling': 'ترابط', 'cycle': 'دورة اعتماد',
                     'duplication': 'تكرار بنيوي', 'literal_duplication': 'تكرار حرفي',
                     'dead_code': 'كود ميت', 'dataflow': 'تدفق بيانات', 'surface': 'سطح عام',
                     'boundary': 'خرق حد', 'naming': 'انحراف تسمية', 'test_quality': 'جودة اختبار'}


def from_engines(fact_sets, offset=0):
    """External evidence becomes a claim only when it has earned one.

    Two independent engines agreeing is worth a LIKELY claim that a probe can raise. One engine
    contradicted by another that fully evaluated the same property is worth a HYPOTHESIS that a
    probe must settle. One engine speaking alone is left as a fact: promoting it would flood the
    ledger with 586 findings and teach a reader to ignore it.
    """
    from .correlate import clusters, CORROBORATED, CONTESTED, GRANULARITY_GAP
    if not fact_sets.get('external'):
        return []
    made, index = [], offset
    for cluster in clusters(fact_sets):
        for kind, detail in sorted(cluster['corroboration'].items()):
            if detail['verdict'] not in (CORROBORATED, CONTESTED, GRANULARITY_GAP):
                continue
            index += 1
            engines = ', '.join(detail['asserted_by'])
            word = ENGINE_KIND_WORDS.get(kind, kind)
            if detail['verdict'] == CORROBORATED:
                statement = f"{len(detail['asserted_by'])} محركات مستقلة ({engines}) تبلّغ عن {word} في {cluster['place']}"
                confidence = ceiling = 'LIKELY'
                falsifier = ('Show the measurement each engine reports is below the threshold it declares, '
                             'or that the engines share one implementation and are therefore one witness.')
                impact = {'scenario': 'أدلة متعددة المصدر على موضع واحد؛ مرشّح أول للمراجعة، لا حكم بوجود عيب.'}
            elif detail['verdict'] == GRANULARITY_GAP:
                elsewhere = ', '.join(detail['silent_at_another_resolution'])
                level = ', '.join(detail['asserted_at']) or 'unknown'
                statement = (f"{engines} يبلّغ عن {word} في {cluster['place']} على مستوى {level}، "
                             f"و{elsewhere} فحص على مستوى آخر ولم يجدها")
                confidence = ceiling = 'LIKELY'
                falsifier = ('Show that no import inside this package reaches back into it, so the loop '
                             'does not close at that resolution either.')
                impact = {'scenario': 'الخاصية قائمة عند دقة قياس ومنتفية عند أخرى؛ القرار يتبع الدقة التي تهمّ المشروع.'}
            else:
                denied = ', '.join(detail['denied_by'])
                statement = (f"{engines} يبلّغ عن {word} في {cluster['place']}، و{denied} فحص الخاصية نفسها ولم يجدها")
                confidence = ceiling = 'HYPOTHESIS'
                falsifier = ('Resolve the contradiction: exhibit the edges that close the cycle in the source, '
                             'or show the asserting engine inferred an edge no import supports.')
                impact = {'scenario': 'محركان يتناقضان في خاصية بنيوية؛ أحدهما مخطئ ولا يصح البناء على أي منهما قبل الحسم.'}
            made.append(make(index, statement[:600], 'structure' if kind in ('cycle', 'boundary') else 'risk',
                             confidence, ['external_engine'], [],
                             falsifier, fact_ids=cluster['fact_ids'], confidence_ceiling=ceiling,
                             render={'key': 'engine_cluster',
                                     'params': {'place': cluster['place'], 'kind': kind,
                                                'engines': engines, 'verdict': detail['verdict']}},
                             probe_spec={'probe_type': 'graph_query',
                                         'specification': {'query': 'engine_cluster_present',
                                                           'place': cluster['place'], 'kind': kind,
                                                           'expected': 'The same engines still report this kind at this place.'}},
                             impact=impact))
    return made


def merge(claims):
    """Two records asserting the same thing are one claim with two sources, not two claims."""
    order = {level: index for index, level in enumerate(CONFIDENCE)}
    # The same sentence recorded twice is one claim; the more specific type wins.
    specificity = {level: index for index, level in enumerate(
        ['business_rule', 'contract', 'cause', 'risk', 'flow_step', 'responsibility', 'structure', 'capability_gap', 'cost'])}
    grouped = {}
    for claim in claims:
        key = (' '.join(claim['statement'].split()).lower(),
               json.dumps(claim.get('probe_spec') or {}, sort_keys=True))
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
        from .decisions import identity
        row.setdefault('uid', identity(row))
        result.append(row)
    return result
