"""The claims the engines' findings earn (eaos/analysis/correlate.py clusters them by place): two engines agreeing, an
engine contradicted, a property seen at one resolution and not another, or a count one engine states exactly; each
with the finish line a complexity card must clear (eaos/analysis/finish_line.py). Part of the claim ledger
(eaos/analysis/claims.py from_facts).
"""
from ..core.words import ENGINE_KIND_WORDS, IMPACTS
from .claims import make
from .fact_claims import engine_measurement
from .weaknesses import SECURITY


def _corroborated(kind, detail, cluster, fact_sets):
    engines, word = ', '.join(detail['asserted_by']), ENGINE_KIND_WORDS.get(kind, kind)
    impact_key, measured = engine_measurement(kind, cluster, fact_sets)
    return {'statement': f"{len(detail['asserted_by'])} محركات مستقلة ({engines}) تبلّغ عن {word} في {cluster['place']}",
            'confidence': 'LIKELY',
            'falsifier': ('Show the measurement each engine reports is below the threshold it declares, '
                          'or that the engines share one implementation and are therefore one witness.'),
            'impact': {'scenario': IMPACTS['ar'][impact_key].format(**measured)}, 'impact_key': impact_key, 'measured': measured}


def _counted(kind, detail, cluster, fact_sets):
    """One engine counting exactly: too many parameters, nesting too deep, a function too long (finish_line.EXACT)."""
    engines, word = ', '.join(detail['asserted_by']), ENGINE_KIND_WORDS.get(kind, kind)
    return {**_corroborated(kind, detail, cluster, fact_sets), 'statement': f"{engines} يعدّ {word} في {cluster['place']}",
            'falsifier': 'Show that the count the engine states (parameters, nesting depth, lines) is within its threshold.'}


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


def _engine_claim(index, kind, cluster, detail, said, finish=(None, None)):
    """The claim of one kind at one place, from what its verdict says. With a finish line (`finish`: the targets and the
    engines that state them, complexity) its probe judges exactly those targets, and only those engines are run again: a
    branch count is EAOS's own; with none left to clear (only sizes, or scores EAOS counts within the limit) it is a
    hypothesis for the person, never work a batch cannot finish."""
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
            made.append(_engine_claim(index, kind, cluster, detail, said, finish))
    return made


def _earns_a_claim(kind, detail, said):
    """Whether a kind of finding at a place is a claim of the engines; `said`: its verdict is one a claim is made of."""
    # Security findings are cards of their own, alone or agreed (eaos/analysis/weaknesses.py), a vulnerable dependency too;
    # dead code EAOS's own detector also reports is its card (fact_claims.dead_code), not a second one.
    return not (kind in SECURITY or (kind == 'dead_code' and 'eaos' in detail['asserted_by']) or not said)


def _complexity_rows(cluster, fact_sets):
    """The engines' findings of a cluster's complexity."""
    facts = {f['id']: f for f in (fact_sets.get('external') or {}).get('facts') or []}
    return [facts[i] for i in cluster['fact_ids_by_kind']['complexity'] if i in facts]


def _finish(kind, cluster, fact_sets, exact=False):
    """(finish line, the engines that judge it) of a complexity claim (eaos/analysis/finish_line.py), (None, None) for another kind.
    `exact`: only the counts an engine states exactly."""
    if kind != 'complexity': return None, None
    from .finish_line import EXACT, judges, targets
    rows = _complexity_rows(cluster, fact_sets)
    found = targets([f for f in rows if f['value'].get('rule') in EXACT] if exact else rows, fact_sets)
    return found, judges(found, rows) if found else None
