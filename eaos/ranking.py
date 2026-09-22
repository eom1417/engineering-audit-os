"""Why one finding comes before another, stated as a formula with visible inputs.

Ordering by the length of a sentence, which is what the first version effectively did, is not a
priority model. This one multiplies what a change would reach by how well the claim is established,
divided by what it would cost to act, and shows every input it used.
"""
from .impact import dependents, entry_points_in, flows_through

CONFIDENCE_WEIGHT = {'CONFIRMED': 1.0, 'LIKELY': 0.7, 'HYPOTHESIS': 0.4, 'REFUTED': 0.0}
ORIGIN_WEIGHT = {'source': 1.0, 'test_and_source': 0.7, 'unknown': 0.6, 'test': 0.3}
COST_BUCKETS = [(120, 'small', 1.0), (600, 'medium', 2.0), (float('inf'), 'large', 3.0)]
WEIGHTS = {'reach': 'dependents + flows + entry-point exposure',
           'confidence': 'CONFIRMED 1.0 · LIKELY 0.7 · HYPOTHESIS 0.4',
           'origin': 'product code 1.0 · mixed 0.7 · test code 0.3',
           'cost': 'lines of the code the change would touch: small 1 · medium 2 · large 3',
           'formula': 'priority = (reach_normalised × confidence × origin) ÷ cost'}


def claim_paths(claim, fact_index):
    paths = []
    for fact_id in claim.get('fact_ids', []):
        value = fact_index.get(fact_id)
        if value: paths.append(value)
        paths += fact_index.get(fact_id + ':paths', [])
    return sorted({path for path in paths if path})


def cost_of(paths, sets):
    total = 0
    for fact in sets.get('metrics', {}).get('facts', []):
        if fact['kind'] == 'metric' and fact['value'].get('scope') == 'file' and fact['location']['path'] in paths:
            total += fact['value']['lines']
    for limit, label, points in COST_BUCKETS:
        if total <= limit: return {'lines': total, 'bucket': label, 'points': points}
    return {'lines': total, 'bucket': 'large', 'points': 3.0}


def reach_of(claim, paths, sets):
    """Reach is what the dependency graph, the traced flows, and the entry points say.

    A cluster with hundreds of paths but no graph node, no flow and no entry point has zero
    reach: a change to it does not touch the rest of the system. Treating cluster size as
    reach would let a test corpus outweigh a real entry point.
    """
    if not paths: return {'dependents': 0, 'flows': 0, 'entry_points': 0, 'total': 0,
                          'paths': 0, 'reach_source': 'no_paths'}
    distance, _ = dependents(sets, paths, depth=2)
    flows = flows_through(sets, paths)
    entries = entry_points_in(sets, paths)
    total = len(distance) + 2 * len(flows) + 3 * len(entries)
    has_graph_signal = bool(distance or flows or entries)
    return {'dependents': len(distance), 'flows': len(flows), 'entry_points': len(entries),
            'total': total, 'paths': len(paths),
            'reach_source': 'graph' if has_graph_signal else 'no_graph_node'}


def rank(claims, sets, fact_index):
    """Attach a priority and its inputs to every claim, then order by it."""
    measured = []
    for claim in claims:
        paths = claim_paths(claim, fact_index)
        measured.append((claim, paths, reach_of(claim, paths, sets), cost_of(paths, sets)))
    largest = max((reach['total'] for _, _, reach, _ in measured), default=0) or 1
    for claim, paths, reach, cost in measured:
        confidence = CONFIDENCE_WEIGHT.get(claim['confidence'], 0.4)
        origin = ORIGIN_WEIGHT.get(claim.get('origin', 'unknown'), 0.6)
        priority = round((reach['total'] / largest) * confidence * origin / cost['points'], 4)
        claim['priority'] = priority
        claim['priority_factors'] = {'reach': reach, 'reach_normalised': round(reach['total'] / largest, 3),
                                     'reach_source': reach['reach_source'],
                                     'confidence': confidence, 'origin': origin, 'cost': cost,
                                     'paths': paths, 'formula': WEIGHTS['formula']}
    return sorted(claims, key=lambda claim: (-claim['priority'], claim['id']))
