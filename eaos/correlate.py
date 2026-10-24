"""Four engines describing one place, read as one problem — and their disagreements kept visible.

Nothing here decides that a finding is true. It decides how many independent engines said it, how
many looked and did not, and therefore what a claim built on it may honestly assert.

The candidates a distribution registry of the project holds by name are tagged by eaos/facts/registry.py (NS4.T2): they
stay on disk, but clusters() skips them so no dead_code claim is raised for them.
"""
from hashlib import sha1

from .facts.registry import filter_in_sets

CORROBORATED, SINGLE, CONTESTED = 'corroborated', 'single_engine', 'contested'
GRANULARITY_GAP = 'different_resolution'
OBSERVED, PARTIAL = 'observed', 'partial'
# Silence only contradicts where the property is structural: a graph either has that cycle or it
# does not.
DENIABLE = ('cycle',)


def _findings(sets):
    """Engine findings from every engine, EAOS's own dead-code detector included, minus the dead-code
    candidates adjudication refuted or found to name no symbol (facts/deadcode.adjudicate)."""
    out = [fact for name in ('external', 'deadcode') for fact in (sets.get(name) or {}).get('facts', [])
           if fact.get('kind') == 'engine_finding']
    return [fact for fact in out
            if ((fact.get('value') or {}).get('adjudication') or {}).get('verdict') not in ('refuted', 'not_a_symbol')]


def _evaluated(sets):
    out = ((sets.get('external') or {}).get('summary') or {}).get('evaluated_kinds', {})
    out = dict(out)
    extra = ((sets.get('deadcode') or {}).get('summary') or {}).get('evaluated_kinds', {})
    out.update(extra)
    return out


def _places(fact):
    """Every place this finding touches; a five-file duplicate belongs to five places."""
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


# Kinds that are a measurement: agreeing engines corroborate only when one of them measured a value over the threshold
# it declares. Two engines reporting complexity 1 at a file are two measurements, not a problem.
MEASURED = ('complexity',)


def over_threshold(fact):
    """Whether one of the finding's measurements exceeds the threshold it declares."""
    return any(isinstance(m.get('value'), (int, float)) and isinstance(m.get('threshold'), (int, float))
               and m['value'] > m['threshold'] for m in (fact.get('value') or {}).get('measurements') or [])


def verdict(kind, asserted_by, evaluated, over=None):
    """How much weight a kind of finding at one place has earned. `over`: the engines whose value of a MEASURED kind
    exceeds their declared threshold here; with none, more engines are not corroboration."""
    silent = {engine: state for engine in evaluated
              if (state := _status(evaluated, engine, kind)) and engine not in asserted_by}
    asserted_at = {_resolution(evaluated, engine, kind) for engine in asserted_by}
    observed = [engine for engine, state in silent.items() if state == OBSERVED]
    same_resolution = sorted(engine for engine in observed if _resolution(evaluated, engine, kind) in asserted_at)
    other_resolution = sorted(engine for engine in observed if _resolution(evaluated, engine, kind) not in asserted_at)
    denied_fully = same_resolution if kind in DENIABLE else []
    decision = _decision(kind, asserted_by, over, denied_fully, other_resolution)
    return {'verdict': decision, 'asserted_by': sorted(asserted_by),
            'asserted_at': sorted(level for level in asserted_at if level),
            'evaluated_and_silent': dict(sorted(silent.items())), 'denied_by': denied_fully,
            'silent_at_another_resolution': other_resolution}


def _decision(kind, asserted_by, over, denied_fully, other_resolution):
    if len(asserted_by) > 1 and (kind not in MEASURED or over is None or over): return CORROBORATED
    if denied_fully: return CONTESTED
    if kind in DENIABLE and other_resolution: return GRANULARITY_GAP
    return SINGLE


def is_wide(fact):
    """A finding about a group spread over more than WIDE files is evidence about the group, not about each file in it:
    a word repeated across 17 files says nothing about the complexity of any one of them (NS30.T1)."""
    return fact['value'].get('subject_kind') == 'group' and len(_places(fact)) > WIDE


WIDE = 3


def clusters(sets):
    """One cluster per place, holding every engine's evidence about it; a wide group finding is a cluster of its own."""
    evaluated = _evaluated(sets)
    filtered = filter_in_sets(_findings(sets), sets)
    built = [cluster for place, facts in sorted(_by_place(filtered).items())
             if (cluster := _cluster(place, facts, evaluated))]
    built.sort(key=lambda cluster: (-cluster['weight'], -cluster['findings'], cluster['place']))
    return built


def _by_place(facts):
    by_place = {}
    for fact in facts:
        for place in (['group:' + fact['id']] if is_wide(fact) else _places(fact)):
            by_place.setdefault(place, []).append(fact)
    return by_place


def _alive(fact):
    # A registry-referenced fact is by name still alive, so it does not contribute
    # to any finding-kind cluster: keep the fact on disk but skip the cluster slot.
    return not (fact.get('value') or {}).get('referenced_by_registry')


def _engines_by_kind(facts, keep):
    out = {}
    for fact in facts:
        if keep(fact): out.setdefault(fact['value']['kind'], set()).add(fact['value']['engine'])
    return out


def _weight(corroboration):
    return round(sum(2.0 if detail['verdict'] == CORROBORATED else
                     0.5 if detail['verdict'] in (CONTESTED, GRANULARITY_GAP) else 1.0
                     for detail in corroboration.values()), 2)


def _cluster(place, facts, evaluated):
    """Every engine's evidence about one place, with a verdict per kind of finding; None when none is alive."""
    kinds = _engines_by_kind(facts, _alive)
    over = _engines_by_kind(facts, lambda fact: fact['value']['kind'] in MEASURED and over_threshold(fact))
    corroboration = {kind: verdict(kind, engines, evaluated, over.get(kind, set()) if kind in MEASURED else None)
                     for kind, engines in sorted(kinds.items())}
    if not corroboration:
        return None
    alive = [fact for fact in facts if _alive(fact)]
    return {
        'id': 'CLU-' + sha1(place.encode('utf-8')).hexdigest()[:10],
        'place': place,
        'engines': sorted({fact['value']['engine'] for fact in alive}),
        'kinds': sorted(kinds),
        'corroboration': corroboration,
        'fact_ids': sorted(fact['id'] for fact in alive),
        # A claim about one kind cites only the evidence of that kind, so its files are where that evidence lies.
        'fact_ids_by_kind': {kind: sorted(fact['id'] for fact in alive if fact['value']['kind'] == kind)
                             for kind in sorted(kinds)},
        'standing': _standing(alive),
        'scope': 'group' if place.startswith('group:') else 'place',
        'findings': len(alive),
        'weight': _weight(corroboration),
        'measurements': sorted({(m['name'], m.get('unit')) for fact in facts
                                for m in fact['value'].get('measurements', []) if m.get('name')}),
    }


def _standing(facts):
    """Per kind, what still stands: `engine: symbol` of each finding, of a MEASURED kind only one past its own threshold
    (a card's probe judges by it, so a function brought under the limit no longer counts, 2026-10-15)."""
    out = {}
    for fact in facts:
        kind = fact['value']['kind']
        if kind not in MEASURED or over_threshold(fact):
            out.setdefault(kind, set()).add(f"{fact['value']['engine']}: {(fact.get('location') or {}).get('symbol') or '(file)'}")
    return {kind: sorted(found) for kind, found in out.items()}


def summary(sets):
    built = clusters(sets)
    verdicts = {}
    for cluster in built:
        for kind, detail in cluster['corroboration'].items():
            verdicts.setdefault(detail['verdict'], set()).add((cluster['place'], kind))
    return {'clusters': len(built),
            'places_with_more_than_one_engine': sum(1 for c in built if len(c['engines']) > 1),
            'by_verdict': {name: len(items) for name, items in sorted(verdicts.items())},
            'limits': 'A cluster is a verdict about one place, not the truth of the finding itself.'}
