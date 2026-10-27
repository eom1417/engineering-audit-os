"""One ledger for everything the system asserts, with its source, its confidence and its refutation.

A fact is produced by an extractor and is reproducible. A claim is an interpretation and must name
what would disprove it. A question is an admitted gap. Nothing rendered may exist outside this ledger.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from .duplicates import duplicated_rules, redundant_work, sequences, structural_duplicates
from .engine_measures import engine_measurement
from .from_experience import experience
from .from_layers import layer_findings
from .from_logic_flaws import logic_flaws
from .from_real_data import real_data
from .from_repository import repository_findings
from .from_facts import (broken_code, cochanges, cycles, dead_code, external_writes, hotspots, large_modules,
                         mutable_globals, policy_violations, trace_gaps, vulnerable_dependencies)
from ..assessments.weaknesses import SECURITY, claims as weaknesses
from ...core.contracts.vocabulary import schema_errors
from ...core.language.words import IMPACTS
from ...core.project.workspace import DATA, read, write

CONFIDENCE = ['CONFIRMED', 'LIKELY', 'HYPOTHESIS', 'REFUTED']
PROVING_METHODS = {'runtime_probe', 'test_evidence', 'static_fact', 'history_fact'}
# The builders of the claims facts earn (eaos/analysis/claims/from_facts.py), in ledger order: the claims are numbered in it.
BUILDERS = (cycles, cochanges, duplicated_rules, hotspots, large_modules, mutable_globals, external_writes,
            structural_duplicates, sequences, redundant_work, policy_violations, trace_gaps, dead_code, broken_code,
            vulnerable_dependencies, weaknesses, layer_findings, logic_flaws, repository_findings,
            experience, real_data)
TYPES = ['structure', 'responsibility', 'contract', 'business_rule', 'flow_step', 'risk', 'cause', 'capability_gap', 'cost']


def schema(): return read(DATA / 'schemas/claim.schema.json')


def now(): return datetime.now(timezone.utc).isoformat()


def claim_id(index): return 'CLM-%03d' % index


STATEMENT_LIMIT = 600

# What the precision set (tools/precision.py) measured for each detector: shown or hidden. A detector whose
# measured precision or recall is under its declared bar is hidden, not shown with a caveat (NS38.T1).
VERDICTS = DATA / 'detector-verdicts.json'


# The card keys whose detector is one of their params: (the detector's prefix, the param).
DETECTED_BY = {'engine_cluster': ('engine_cluster', 'kind'), 'layer_finding': ('layer', 'rule'),
               'repository_finding': ('repository', 'rule'), 'logic_flaw': ('logic', 'class'),
               'experience_difficulty': ('experience', 'kind'), 'real_data': ('real_data', 'kind'),
               'old_engine': ('old_engine', 'kind')}


def detector_of(claim):
    """The detector a claim comes from: its card key, an engine cluster's kind, or the import-cycle check."""
    render = claim.get('render') or {}
    key = render.get('key')
    if key in DETECTED_BY:
        prefix, param = DETECTED_BY[key]
        return prefix + ':' + str((render.get('params') or {}).get(param))
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


def withhold(claims):
    """(shown, withheld): a claim from a hidden detector is kept aside with the reason, never shown or planned."""
    hidden = hidden_detectors()
    shown, withheld = [], []
    for claim in claims:
        why = hidden.get(detector_of(claim))
        if why is None: shown.append(claim)
        else: withheld.append({**claim, 'withheld': {'detector': detector_of(claim), 'why': why}})
    return shown, withheld


def make(index, statement, claim_type, confidence, method, evidence_ids, falsifier, **extra):  # limits: parameters -- a claim's required fields (the claim-ledger schema)
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


def from_facts(fact_sets, target=None):
    """Deterministic facts promoted to claims keep CONFIRMED status and name their own refutation; one builder per
    kind of fact (BUILDERS), numbered in that order, then the claims the engines earn.

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


def _hotspot_of(claim, hotspots):
    """The hotspot whose file an engines' complexity claim is about, or None."""
    render = claim.get('render') or {}
    params = render.get('params') or {}
    if render.get('key') != 'engine_cluster' or params.get('kind') != 'complexity': return None
    return hotspots.get(params.get('place'))


def one_card_per_hotspot(claims):
    """A hotspot and the engines' complexity card on the same file are one problem: the engines' card leaves and its
    measurements join the hotspot's evidence."""
    hotspots = {c['render']['params']['path']: c for c in claims if (c.get('render') or {}).get('key') == 'hotspot'}
    kept = []
    for claim in claims:
        same = _hotspot_of(claim, hotspots)
        if same is not None:
            same['fact_ids'] = sorted(set(same.get('fact_ids') or []) | set(claim.get('fact_ids') or []))
            continue
        kept.append(claim)
    return kept


def _corroborated(kind, detail, cluster, fact_sets):
    engines, word = ', '.join(detail['asserted_by']), kind.replace('_', ' ')
    impact_key, measured = engine_measurement(kind, cluster, fact_sets)
    return {'statement': f"{len(detail['asserted_by'])} independent engines ({engines}) report {word} in {cluster['place']}",
            'confidence': 'LIKELY',
            'falsifier': ('Show the measurement each engine reports is below the threshold it declares, '
                          'or that the engines share one implementation and are therefore one witness.'),
            'impact': {'scenario': IMPACTS['en'][impact_key].format(**measured)}, 'impact_key': impact_key, 'measured': measured}


def _counted(kind, detail, cluster, fact_sets):
    """One engine counting exactly: too many parameters, nesting too deep, a function too long (finish_line.EXACT)."""
    engines, word = ', '.join(detail['asserted_by']), kind.replace('_', ' ')
    return {**_corroborated(kind, detail, cluster, fact_sets), 'statement': f"{engines} counts {word} in {cluster['place']}",
            'falsifier': 'Show that the count the engine states (parameters, nesting depth, lines) is within its threshold.'}


def _granularity_gap(kind, detail, cluster, fact_sets):
    engines, word = ', '.join(detail['asserted_by']), kind.replace('_', ' ')
    elsewhere = ', '.join(detail['silent_at_another_resolution'])
    level = ', '.join(detail['asserted_at']) or 'unknown'
    return {'statement': (f"{engines} reports {word} in {cluster['place']} at the {level} level, "
                          f"and {elsewhere} checked at another level and did not find it"),
            'confidence': 'LIKELY',
            'falsifier': ('Show that no import inside this package reaches back into it, so the loop '
                          'does not close at that resolution either.'),
            'impact': {'scenario': 'The property holds at one resolution and not at another; the decision follows the resolution the project cares about.'},
            'impact_key': None, 'measured': {}}


def _contested(kind, detail, cluster, fact_sets):
    engines, word = ', '.join(detail['asserted_by']), kind.replace('_', ' ')
    denied = ', '.join(detail['denied_by'])
    return {'statement': (f"{engines} reports {word} in {cluster['place']}, and {denied} checked the same property and did not find it"),
            'confidence': 'HYPOTHESIS',
            'falsifier': ('Resolve the contradiction: exhibit the edges that close the cycle in the source, '
                          'or show the asserting engine inferred an edge no import supports.'),
            'impact': {'scenario': 'Two engines contradict each other on a structural property; one is wrong, and neither can be built on until it is settled.'},
            'impact_key': None, 'measured': {}}


def _engine_claim(index, kind, cluster, said, finish=(None, None)):
    """The claim of one kind at one place, from what its verdict says. With a finish line (`finish`: the targets and the
    engines that state them, complexity) its probe judges exactly those targets, and only those engines are run again: a
    branch count is EAOS's own; with none left to clear (only sizes, or scores EAOS counts within the limit) it is a
    hypothesis for the person, never work a batch cannot finish."""
    detail = cluster['corroboration'][kind]
    (finish, judges), engines, impact_key = finish, ', '.join(detail['asserted_by']), said['impact_key']
    confidence = 'HYPOTHESIS' if finish == [] else said['confidence']
    return make(index, said['statement'][:600], 'structure' if kind in ('cycle', 'boundary') else 'risk',
                confidence, ['external_engine'], [],
                said['falsifier'], fact_ids=cluster['fact_ids_by_kind'][kind], confidence_ceiling=confidence,
                render={'key': 'engine_cluster',
                        'params': {'place': cluster['place'], 'kind': kind,
                                   'engines': engines, 'verdict': detail['verdict'],
                                   **said['measured'], **({'impact_key': impact_key} if impact_key else {})}},
                probe_spec={'probe_type': 'graph_query',
                            'specification': {'query': 'engine_cluster_present',
                                              'engines': detail['asserted_by'] if judges is None else judges,
                                              'place': cluster['place'], 'kind': kind,
                                              **({'targets': finish} if finish else {}),
                                              'expected': 'The same engines still report this kind at this place.'}},
                impact=said['impact'])


def from_engines(fact_sets, offset=0):
    """External evidence becomes a claim only when it has earned one.

    Two independent engines agreeing is worth a LIKELY claim that a probe can raise. One engine
    contradicted by another that fully evaluated the same property is worth a HYPOTHESIS that a
    probe must settle. One engine speaking alone is left as a fact: promoting it would flood the
    ledger with 586 findings and teach a reader to ignore it. Except a count it states exactly (M2.2): a function with
    eight parameters has eight whoever counts them, so that count alone is a claim, on those targets only.
    """
    from .correlate import clusters, CORROBORATED, CONTESTED, GRANULARITY_GAP, SINGLE
    if not fact_sets.get('external'):
        return []
    says = {CORROBORATED: _corroborated, GRANULARITY_GAP: _granularity_gap, CONTESTED: _contested}
    made, index = [], offset
    for cluster in clusters(fact_sets):
        for kind, detail in sorted(cluster['corroboration'].items()):
            counted = detail['verdict'] == SINGLE and kind == 'complexity'
            if not _earns_a_claim(kind, detail, detail['verdict'] in says or counted): continue
            finish = _finish(kind, cluster, fact_sets, exact=counted)
            if counted and not finish[0]: continue
            index += 1
            said = (_counted if counted else says[detail['verdict']])(kind, detail, cluster, fact_sets)
            made.append(_engine_claim(index, kind, cluster, said, finish))
    return made


def _earns_a_claim(kind, detail, said):
    """Whether a kind of finding at a place is a claim of the engines; `said`: its verdict is one a claim is made of."""
    # Security findings are cards of their own, alone or agreed (eaos/analysis/assessments/weaknesses.py), a vulnerable dependency too;
    # dead code EAOS's own detector also reports is its card (fact_claims.dead_code), not a second one.
    return not (kind in SECURITY or (kind == 'dead_code' and 'eaos' in detail['asserted_by']) or not said)


def _complexity_rows(cluster, fact_sets):
    """The engines' findings of a cluster's complexity."""
    facts = {f['id']: f for f in (fact_sets.get('external') or {}).get('facts') or []}
    return [facts[i] for i in cluster['fact_ids_by_kind']['complexity'] if i in facts]


def _finish(kind, cluster, fact_sets, exact=False):
    """(finish line, the engines that judge it) of a complexity claim (eaos/analysis/repair/finish_line.py), (None, None) for another kind.
    `exact`: only the counts an engine states exactly."""
    if kind != 'complexity': return None, None
    from ..repair.finish_line import EXACT, judges, targets
    rows = _complexity_rows(cluster, fact_sets)
    found = targets([f for f in rows if f['value'].get('rule') in EXACT] if exact else rows, fact_sets)
    return found, judges(found, rows) if found else None


ORDER = {level: index for index, level in enumerate(CONFIDENCE)}
# The same sentence recorded twice is one claim; the more specific type wins.
SPECIFICITY = {level: index for index, level in enumerate(
    ['business_rule', 'contract', 'cause', 'risk', 'flow_step', 'responsibility', 'structure', 'capability_gap', 'cost'])}


def _absorb(existing, claim):
    """A second record of the same claim joins the first: its sources added, the higher confidence and the more
    specific type kept."""
    existing['evidence_ids'] = sorted(set(existing.get('evidence_ids', []) + claim.get('evidence_ids', [])))
    existing['fact_ids'] = sorted(set(existing.get('fact_ids', []) + claim.get('fact_ids', [])))
    existing['method'] = sorted(set(existing['method'] + claim['method']))
    if ORDER[claim['confidence']] < ORDER[existing['confidence']]: existing['confidence'] = claim['confidence']
    if SPECIFICITY[claim['claim_type']] < SPECIFICITY[existing['claim_type']]: existing['claim_type'] = claim['claim_type']
    if claim.get('legacy_id'): existing['legacy_ids'] = sorted(set(existing.get('legacy_ids', []) + [claim['legacy_id']]))


def merge(claims):
    """Two records asserting the same thing are one claim with two sources, not two claims."""
    grouped = {}
    for claim in claims:
        key = (' '.join(claim['statement'].split()).lower(),
               json.dumps(claim.get('probe_spec') or {}, sort_keys=True))
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = dict(claim)
            if claim.get('legacy_id'): grouped[key]['legacy_ids'] = [claim['legacy_id']]
            continue
        _absorb(existing, claim)
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
        from ...core.contracts.decisions import identity
        row.setdefault('uid', identity(row))
        result.append(row)
    return result
