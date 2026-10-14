"""One ledger for everything the system asserts, with its source, its confidence and its refutation.

A fact is produced by an extractor and is reproducible. A claim is an interpretation and must name
what would disprove it. A question is an admitted gap. Nothing rendered may exist outside this ledger.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from .compose.labels import IMPACTS
from .fact_claims import BUILDERS, engine_measurement
from .vocabulary import schema_errors
from .weaknesses import SECURITY
from .workspace import DATA, read, write

CONFIDENCE = ['CONFIRMED', 'LIKELY', 'HYPOTHESIS', 'REFUTED']
PROVING_METHODS = {'runtime_probe', 'test_evidence', 'static_fact', 'history_fact'}
TYPES = ['structure', 'responsibility', 'contract', 'business_rule', 'flow_step', 'risk', 'cause', 'capability_gap', 'cost']


def schema(): return read(DATA / 'schemas/claim.schema.json')


def now(): return datetime.now(timezone.utc).isoformat()


def claim_id(index): return 'CLM-%03d' % index


STATEMENT_LIMIT = 600

# What the precision set (tools/precision.py) measured for each detector: shown or hidden. A detector whose
# measured precision or recall is under its declared bar is hidden, not shown with a caveat (NS38.T1).
VERDICTS = DATA / 'detector-verdicts.json'


def detector_of(claim):
    """The detector a claim comes from: its card key, an engine cluster's kind, or the import-cycle check."""
    render = claim.get('render') or {}
    key = render.get('key')
    if key == 'engine_cluster': return 'engine_cluster:' + str((render.get('params') or {}).get('kind'))
    if key: return key
    if str(claim.get('statement', '')).startswith('Import cycle between'): return 'import_cycle'
    return 'unattributed'


def verdicts_path():
    """The verdicts in force: $EAOS_DETECTOR_VERDICTS when it is set (empty: none, every detector shown), else the
    packaged file. The unit tests check each detector on its own fixture, so they run with none."""
    chosen = os.environ.get('EAOS_DETECTOR_VERDICTS')
    if chosen is None: return VERDICTS
    return Path(chosen) if chosen else None


def hidden_detectors():
    """{detector: why} for the detectors under their measured bar; empty when nothing was measured."""
    path = verdicts_path()
    if path is None: return {}
    try: return dict(read(path).get('hidden') or {})
    except (OSError, ValueError): return {}


def shown_kinds(kinds, detectors=None):
    """The fact kinds among `kinds` whose detector is shown; `detectors` maps a kind to its detector id."""
    hidden = hidden_detectors()
    return {kind for kind in kinds if (detectors or {}).get(kind, kind) not in hidden}


def withhold(claims):
    """(shown, withheld): a claim from a hidden detector is kept aside with the reason, never shown or planned."""
    hidden = hidden_detectors()
    shown, withheld = [], []
    for claim in claims:
        why = hidden.get(detector_of(claim))
        if why is None: shown.append(claim)
        else: withheld.append({**claim, 'withheld': {'detector': detector_of(claim), 'why': why}})
    return shown, withheld


def make(index, statement, claim_type, confidence, method, evidence_ids, falsifier, **extra):
    # The schema caps a statement at STATEMENT_LIMIT. Each builder names a bounded list (naming());
    # this is the last guard: one long sentence on a large project must not reject the whole ledger.
    if len(statement) > STATEMENT_LIMIT: statement = statement[:STATEMENT_LIMIT - 1].rstrip() + '…'
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
    known = (set(evidence_ids), set(fact_ids))
    for claim in claims:
        identity = claim.get('id', '?')
        found += [identity + ': ' + message for message in schema_errors(claim, spec)]
        if identity in seen: found.append(identity + ': duplicate claim id')
        seen.add(identity)
        found += [identity + ': ' + message for message in _claim_errors(claim, known)]
    return sorted(set(found))


def _unknown(references, known, what):
    """Each reference not among `known`; none when nothing is known to check against."""
    return [f'unknown {what} {reference}' for reference in references if reference not in known] if known else []


def _unowned_acceptance(claim):
    if claim.get('claim_type') != 'risk' or claim.get('disposition', {}).get('kind') != 'accepted': return False
    return not claim['disposition'].get('owner') or not claim['disposition'].get('reason')


def _claim_errors(claim, known):
    """The epistemic rules one claim breaks; `known`: (evidence ids, fact ids) to resolve against."""
    known_evidence, known_facts = known
    found = []
    if not claim.get('falsifier', '').strip():
        found.append('a claim must state what would disprove it')
    if claim.get('confidence') == 'CONFIRMED' and not (set(claim.get('method', [])) & PROVING_METHODS):
        found.append('CONFIRMED requires a probe, a test or a deterministic fact, not model inference')
    if claim.get('confidence') != 'REFUTED' and not claim.get('evidence_ids') and not claim.get('fact_ids'):
        found.append('no evidence and no fact backs this claim')
    found += _unknown(claim.get('evidence_ids', []), known_evidence, 'evidence')
    found += _unknown(claim.get('fact_ids', []), known_facts, 'fact')
    if _unowned_acceptance(claim): found.append('an accepted risk needs an owner and a reason')
    return found


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


def from_facts(fact_sets, target=None):
    """Deterministic facts promoted to claims keep CONFIRMED status and name their own refutation; one builder per
    kind of fact (eaos/fact_claims.py BUILDERS), numbered in that order.

    ``target`` is the audited root, used to bind a runnable acceptance check to
    a declared-policy violation. It is optional so test fixtures can build a
    claim ledger without a real directory.
    """
    claims = []

    def add(statement, claim_type, confidence, method, falsifier, **extra):
        claims.append(make(len(claims) + 1, statement, claim_type, confidence, method, [], falsifier, **extra))
        return claims[-1]

    for build in BUILDERS: build(fact_sets, add, target)
    return one_card_per_hotspot(claims + from_engines(fact_sets, len(claims)))


def one_card_per_hotspot(claims):
    """A hotspot and the engines' complexity card on the same file are one problem: the engines' card leaves and its
    measurements join the hotspot's evidence."""
    hotspots = {c['render']['params']['path']: c for c in claims if (c.get('render') or {}).get('key') == 'hotspot'}
    kept = []
    for claim in claims:
        render = claim.get('render') or {}
        params = render.get('params') or {}
        same = hotspots.get(params.get('place')) if render.get('key') == 'engine_cluster' else None
        if same is not None and params.get('kind') == 'complexity':
            same['fact_ids'] = sorted(set(same.get('fact_ids') or []) | set(claim.get('fact_ids') or []))
            continue
        kept.append(claim)
    return kept


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


ENGINE_KIND_WORDS = {'complexity': 'تعقيد', 'coupling': 'ترابط', 'cycle': 'دورة اعتماد',
                     'duplication': 'تكرار بنيوي', 'literal_duplication': 'تكرار حرفي',
                     'dead_code': 'كود ميت', 'dataflow': 'تدفق بيانات', 'surface': 'سطح عام',
                     'boundary': 'خرق حد', 'naming': 'انحراف تسمية', 'test_quality': 'جودة اختبار',
                     'unused_dependency': 'اعتمادية غير مستخدمة'}


def _corroborated(kind, detail, cluster, fact_sets):
    engines, word = ', '.join(detail['asserted_by']), ENGINE_KIND_WORDS.get(kind, kind)
    impact_key, measured = engine_measurement(kind, cluster, fact_sets)
    return {'statement': f"{len(detail['asserted_by'])} محركات مستقلة ({engines}) تبلّغ عن {word} في {cluster['place']}",
            'confidence': 'LIKELY',
            'falsifier': ('Show the measurement each engine reports is below the threshold it declares, '
                          'or that the engines share one implementation and are therefore one witness.'),
            'impact': {'scenario': IMPACTS['ar'][impact_key].format(**measured)}, 'impact_key': impact_key, 'measured': measured}


def _granularity_gap(kind, detail, cluster, fact_sets):
    engines, word = ', '.join(detail['asserted_by']), ENGINE_KIND_WORDS.get(kind, kind)
    elsewhere = ', '.join(detail['silent_at_another_resolution'])
    level = ', '.join(detail['asserted_at']) or 'unknown'
    return {'statement': (f"{engines} يبلّغ عن {word} في {cluster['place']} على مستوى {level}، "
                          f"و{elsewhere} فحص على مستوى آخر ولم يجدها"),
            'confidence': 'LIKELY',
            'falsifier': ('Show that no import inside this package reaches back into it, so the loop '
                          'does not close at that resolution either.'),
            'impact': {'scenario': 'الخاصية قائمة عند دقة قياس ومنتفية عند أخرى؛ القرار يتبع الدقة التي تهمّ المشروع.'},
            'impact_key': None, 'measured': {}}


def _contested(kind, detail, cluster, fact_sets):
    engines, word = ', '.join(detail['asserted_by']), ENGINE_KIND_WORDS.get(kind, kind)
    denied = ', '.join(detail['denied_by'])
    return {'statement': (f"{engines} يبلّغ عن {word} في {cluster['place']}، و{denied} فحص الخاصية نفسها ولم يجدها"),
            'confidence': 'HYPOTHESIS',
            'falsifier': ('Resolve the contradiction: exhibit the edges that close the cycle in the source, '
                          'or show the asserting engine inferred an edge no import supports.'),
            'impact': {'scenario': 'محركان يتناقضان في خاصية بنيوية؛ أحدهما مخطئ ولا يصح البناء على أي منهما قبل الحسم.'},
            'impact_key': None, 'measured': {}}


def _engine_claim(index, kind, cluster, detail, said):
    """The claim of one kind at one place, from what its verdict says."""
    engines, impact_key = ', '.join(detail['asserted_by']), said['impact_key']
    return make(index, said['statement'][:600], 'structure' if kind in ('cycle', 'boundary') else 'risk',
                said['confidence'], ['external_engine'], [],
                said['falsifier'], fact_ids=cluster['fact_ids_by_kind'][kind], confidence_ceiling=said['confidence'],
                render={'key': 'engine_cluster',
                        'params': {'place': cluster['place'], 'kind': kind,
                                   'engines': engines, 'verdict': detail['verdict'],
                                   **said['measured'], **({'impact_key': impact_key} if impact_key else {})}},
                probe_spec={'probe_type': 'graph_query',
                            'specification': {'query': 'engine_cluster_present', 'engines': detail['asserted_by'],
                                              'place': cluster['place'], 'kind': kind,
                                              'expected': 'The same engines still report this kind at this place.'}},
                impact=said['impact'])


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
    says = {CORROBORATED: _corroborated, GRANULARITY_GAP: _granularity_gap, CONTESTED: _contested}
    made, index = [], offset
    for cluster in clusters(fact_sets):
        for kind, detail in sorted(cluster['corroboration'].items()):
            # Security findings are cards of their own, alone or agreed (eaos/weaknesses.py), a vulnerable dependency too.
            if kind in SECURITY or detail['verdict'] not in says:
                continue
            index += 1
            made.append(_engine_claim(index, kind, cluster, detail, says[detail['verdict']](kind, detail, cluster, fact_sets)))
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
