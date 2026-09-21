"""Four engines describing one place, read as one problem — and their disagreements kept visible.

Nothing here decides that a finding is true. It decides how many independent engines said it, how
many looked and did not, and therefore what a claim built on it may honestly assert.
"""
from hashlib import sha1

CORROBORATED, SINGLE, CONTESTED = 'corroborated', 'single_engine', 'contested'
GRANULARITY_GAP = 'different_resolution'
OBSERVED, PARTIAL = 'observed', 'partial'
# Silence only contradicts where the property is structural: a graph either has that cycle or it
# does not. For threshold rules — complexity, coupling, duplication — a silent engine set its
# threshold elsewhere and has contradicted nothing. Calling that "contested" would make the word
# meaningless: it labelled 184 of 279 verdicts before this line existed.
DENIABLE = ('cycle',)


def _findings(sets):
    external = sets.get('external') or {}
    return [fact for fact in external.get('facts', []) if fact['kind'] == 'engine_finding']


def _evaluated(sets):
    return ((sets.get('external') or {}).get('summary') or {}).get('evaluated_kinds', {})


def _places(fact):
    """Every place this finding touches; a five-file duplicate belongs to five places.

    A finding about a package rather than a file — a dependency cycle, say — still has a place:
    its subject. Dropping those was how the one contested finding in this repository disappeared.
    """
    sites = [site['path'] for site in fact['value'].get('sites', []) if site.get('path')]
    if sites:
        return sorted(set(sites))
    location = fact['location']
    return [location.get('path') or location.get('symbol')] if (location.get('path') or location.get('symbol')) else []


def _resolution(evaluated, engine, kind):
    detail = (evaluated.get(engine) or {}).get(kind)
    return (detail or {}).get('granularity') if isinstance(detail, dict) else None


def _status(evaluated, engine, kind):
    detail = (evaluated.get(engine) or {}).get(kind)
    return detail.get('status') if isinstance(detail, dict) else detail


def verdict(kind, asserted_by, evaluated):
    """How much weight a kind of finding at one place has earned, and from whom.

    A silent engine only contradicts when it answered the same question at the same resolution.
    enola sees a cycle over package nodes that CodeGraph does not see over files — and both are
    right, because eaos/facts imports eaos.workspace while no single file closes the loop.
    """
    silent = {engine: state for engine in evaluated
              if (state := _status(evaluated, engine, kind)) and engine not in asserted_by}
    asserted_at = {_resolution(evaluated, engine, kind) for engine in asserted_by}
    same_resolution = sorted(engine for engine, state in silent.items()
                             if state == OBSERVED and _resolution(evaluated, engine, kind) in asserted_at)
    other_resolution = sorted(engine for engine, state in silent.items()
                              if state == OBSERVED and _resolution(evaluated, engine, kind) not in asserted_at)
    denied_fully = same_resolution if kind in DENIABLE else []
    if len(asserted_by) > 1:
        decision = CORROBORATED
    elif denied_fully:
        decision = CONTESTED
    elif kind in DENIABLE and other_resolution:
        decision = GRANULARITY_GAP
    else:
        decision = SINGLE
    return {'verdict': decision, 'asserted_by': sorted(asserted_by),
            'asserted_at': sorted(level for level in asserted_at if level),
            'evaluated_and_silent': dict(sorted(silent.items())), 'denied_by': denied_fully,
            'silent_at_another_resolution': other_resolution}


def clusters(sets):
    """One cluster per place, holding every engine's evidence about it."""
    evaluated = _evaluated(sets)
    by_place = {}
    for fact in _findings(sets):
        for place in _places(fact):
            by_place.setdefault(place, []).append(fact)
    built = []
    for place, facts in sorted(by_place.items()):
        kinds = {}
        for fact in facts:
            kinds.setdefault(fact['value']['kind'], set()).add(fact['value']['engine'])
        corroboration = {kind: verdict(kind, engines, evaluated) for kind, engines in sorted(kinds.items())}
        engines = sorted({fact['value']['engine'] for fact in facts})
        built.append({
            'id': 'CLU-' + sha1(place.encode('utf-8')).hexdigest()[:10],
            'place': place,
            'engines': engines,
            'kinds': sorted(kinds),
            'corroboration': corroboration,
            'fact_ids': sorted(fact['id'] for fact in facts),
            'findings': len(facts),
            # A place two engines agree on outranks a place one engine mentions four times.
            'weight': round(sum(2.0 if detail['verdict'] == CORROBORATED else
                                0.5 if detail['verdict'] in (CONTESTED, GRANULARITY_GAP) else 1.0
                                for detail in corroboration.values()), 2),
            'measurements': sorted({(m['name'], m.get('unit')) for fact in facts
                                    for m in fact['value'].get('measurements', []) if m.get('name')}),
        })
    built.sort(key=lambda cluster: (-cluster['weight'], -cluster['findings'], cluster['place']))
    return built


def summary(sets):
    built = clusters(sets)
    verdicts = {}
    for cluster in built:
        for kind, detail in cluster['corroboration'].items():
            verdicts.setdefault(detail['verdict'], set()).add((cluster['place'], kind))
    return {'clusters': len(built),
            'places_with_more_than_one_engine': sum(1 for c in built if len(c['engines']) > 1),
            'by_verdict': {name: len(items) for name, items in sorted(verdicts.items())},
            'engines_consulted': sorted(_evaluated(sets)),
            'limits': 'Corroboration counts engines, not correctness: four engines can share one blind spot, '
                      'and a contested finding is a question for a probe, not a settled refutation.'}
