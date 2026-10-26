"""The dependency graph the other facts hang from, plus a declared attention ranking.

The ranking is a stated heuristic for deciding where to look first, with its factors exposed.
It is never a quality score and never an ordering of severity.
"""
from collections import deque
from .. import digest, make
from .graph_queries import cycles

NAME = 'graph'
VERSION = '1'
WEIGHTS = {'centrality': 0.3, 'change': 0.3, 'complexity': 0.2, 'entry_proximity': 0.2}
LIMITATIONS = [
    'The graph contains resolved source imports only; runtime wiring and dynamic dispatch are absent.',
    'A cycle is a signal to investigate, not a defect by itself.',
    'Attention weights are a declared convention, not a measured predictor of risk.',
    'Files unreachable from a detected entry point may still be reached through paths no detector covers.',
    'Edges from external engines carry the engine name and resolution RESOLVED_BY_ENGINE; they are not the same evidence as edges resolved by our own resolver.',
]


def normalise(values):
    top = max(values.values(), default=0)
    return {key: (value / top if top else 0.0) for key, value in values.items()}


def _module_edge(value, location):
    target = value.get('to_path')
    return (location.get('path'), target) if target else None


def _import_edge(value, location):
    target = value.get('to_path')
    return (value.get('from_path') or location.get('path'), target) if target else None


def _call_edge(value, location):
    source = value.get('caller_path') or location.get('path')
    target = value.get('callee_path')
    return (source, target) if source and target else None


ENDPOINTS = {'module_edge': _module_edge, 'import_edge': _import_edge, 'call_edge': _call_edge}


def _edge_endpoints(edge):
    """Pull (source_path, target_path) from any of the edge kinds we accept.

    Returns None when the fact is not a graph edge we know how to orient, so the caller can skip it.
    """
    read = ENDPOINTS.get(edge.get('kind'))
    if read is None: return None
    return read(edge.get('value', {}), edge.get('location', {}) or {})


def _computed_inputs(target, source):
    from . import entrypoints as entry_module, history as history_module, metrics as metrics_module, resolve, syntax
    produced = syntax.run(target, source)['facts']
    edges = [f for f in resolve.run(target, source, imports=[f for f in produced if f['kind'] == 'import_edge'])['facts']]
    entry_points = entry_module.run(target, source, symbols=[f for f in produced if f['kind'] == 'symbol'])['facts']
    metrics = metrics_module.run(target, source, symbols=[f for f in produced if f['kind'] == 'symbol'])['facts']
    history = history_module.run(target, source)['facts']
    return edges, entry_points, metrics, history


def _nodes(source, edges):
    from ..source import language_of
    # Endpoints we see, regardless of resolution: used only to widen the node set.
    participating = set()
    for edge in edges: participating.update(_edge_endpoints(edge) or ())
    return sorted({item['path'] for item in source.readable()
                   if language_of(item['path']) is not None or item['path'] in participating} - {None})


def _record_edge(edge, adjacency, edge_source):
    endpoints = _edge_endpoints(edge)
    if not endpoints: return
    source_path, target_path = endpoints
    if source_path not in adjacency or target_path not in adjacency: return
    adjacency[source_path].add(target_path)
    if edge['resolution'] == 'RESOLVED_BY_ENGINE':
        engine = (edge.get('value') or {}).get('engine') or 'engine'
        edge_source[(source_path, target_path)] = 'engine:' + engine
    else:
        edge_source.setdefault((source_path, target_path), 'own')


def _adjacency(nodes, edges):
    adjacency = {path: set() for path in nodes}
    edge_source = {}  # (source_path, target_path) -> 'own' | 'engine:<name>'
    for edge in edges:
        if edge.get('resolution') in ('RESOLVED', 'RESOLVED_BY_ENGINE'): _record_edge(edge, adjacency, edge_source)
    return adjacency, edge_source


def _fan_in(nodes, adjacency):
    fan_in = {path: 0 for path in nodes}
    for targets in adjacency.values():
        for other in targets: fan_in[other] += 1
    return fan_in


def _distances(entry_files, adjacency):
    distance = {path: 0 for path in entry_files if path in adjacency}
    queue = deque(distance)
    while queue:
        current = queue.popleft()
        for neighbour in sorted(adjacency[current] - distance.keys()):
            distance[neighbour] = distance[current] + 1
            queue.append(neighbour)
    return distance


def _file_branches(metrics):
    return {fact['location']['path']: fact['value']['branches'] for fact in metrics
            if fact['kind'] == 'metric' and fact['value'].get('scope') == 'file'}


def _file_commits(history):
    return {fact['location']['path']: fact['value']['commits'] for fact in history if fact['kind'] == 'history_churn'}


def _factors(nodes, graph, branches, commits):
    distance = graph['distance']
    return {
        'centrality': normalise({path: graph['fan_in'][path] for path in nodes}),
        'change': normalise({path: commits.get(path, 0) for path in nodes}),
        'complexity': normalise({path: branches.get(path, 0) for path in nodes}),
        'entry_proximity': {path: (1.0 / (1 + distance[path]) if path in distance else 0.0) for path in nodes},
    }


def _node_fact(path, graph):
    adjacency, edge_source = graph['adjacency'], graph['edge_source']
    depends = sorted(adjacency[path])
    return make('graph_node', NAME, VERSION, digest(path.encode('utf-8')), {'path': path},
                {'fan_in': graph['fan_in'][path], 'fan_out': len(adjacency[path]),
                 'depends_on': depends,
                 'depends_on_with_source': [{'path': target, 'source': edge_source.get((path, target), 'own')}
                                            for target in depends],
                 'entry_distance': graph['distance'].get(path), 'cycle_group': graph['in_cycle'].get(path),
                 'attention_score': graph['scored'][path], 'attention_rank': graph['position'][path],
                 'factors': {name: round(graph['factors'][name][path], 4) for name in WEIGHTS}},
                limitations=LIMITATIONS)


def _cycle_fact(index, group):
    return make('graph_cycle', NAME, VERSION, digest('|'.join(group).encode('utf-8')), {'path': group[0]},
                {'group': index, 'members': group, 'size': len(group)}, limitations=LIMITATIONS)


def _attention_order(ranking, scored, factors):
    """The files to look at first, each with its score and the factors that make it."""
    return [{'path': path, 'score': scored[path], 'factors': {n: round(factors[n][path], 3) for n in WEIGHTS}} for path in ranking]


def _summary(nodes, graph, groups, entry_files, ranking):
    adjacency, fan_in, distance = graph['adjacency'], graph['fan_in'], graph['distance']
    reachable = [path for path in nodes if path in distance]
    orphans = [path for path in nodes if not fan_in[path] and not adjacency[path]]
    # Per-edge source breakdown: how much of the graph is our own work, how much came from an engine.
    own = sum(1 for label in graph['edge_source'].values() if label == 'own')
    return {'nodes': len(nodes), 'edges': sum(len(targets) for targets in adjacency.values()),
            'own_edges': own, 'engine_edges': len(graph['edge_source']) - own,
            'cycles': len(groups), 'cycle_members': sorted(graph['in_cycle']),
            'entry_files': entry_files,
            'reachable_from_entry': len(reachable),
            'unreachable_from_entry': len(nodes) - len(reachable),
            'weights': WEIGHTS,
            'attention_order': _attention_order(ranking[:30], graph['scored'], graph['factors']),
            'most_depended_on': [{'path': path, 'fan_in': fan_in[path]} for path in sorted(nodes, key=lambda p: (-fan_in[p], p))[:15]],
            'isolated_files': orphans[:50],
            'interpretation': 'Structure and attention order only. Nothing here judges design quality; a cycle or a high rank is an invitation to look, not a verdict. Engine-resolved edges are listed separately so they cannot be mistaken for edges we resolved ourselves.'}


def _entry_files(entry_points):
    """The files an entry point is declared in (a navigation link aside), sorted."""
    return sorted({fact['location']['path'] for fact in entry_points if fact.get('kind') != 'navigation'})


def _rank(nodes, graph):
    """Each file's attention score (its weighted factors) and place in the order; returns the order."""
    graph['scored'] = {path: round(sum(WEIGHTS[name] * graph['factors'][name][path] for name in WEIGHTS), 4) for path in nodes}
    ranking = sorted(nodes, key=lambda path: (-graph['scored'][path], path))
    graph['position'] = {path: index + 1 for index, path in enumerate(ranking)}
    return ranking


def _cycle_groups(graph):
    """The import cycles, each file's group noted in the graph (in_cycle)."""
    groups = cycles({path: set(targets) for path, targets in graph['adjacency'].items()})
    graph['in_cycle'] = {path: index for index, group in enumerate(groups) for path in group}
    return groups


def run(target, source, edges=None, entry_points=None, metrics=None, history=None, **options):
    if edges is None: edges, entry_points, metrics, history = _computed_inputs(target, source)
    edges = edges or []
    nodes = _nodes(source, edges)
    adjacency, edge_source = _adjacency(nodes, edges)
    entry_files = _entry_files(entry_points or [])
    graph = {'adjacency': adjacency, 'edge_source': edge_source, 'fan_in': _fan_in(nodes, adjacency),
             'distance': _distances(entry_files, adjacency)}
    graph['factors'] = _factors(nodes, graph, _file_branches(metrics or []), _file_commits(history or []))
    ranking = _rank(nodes, graph)
    groups = _cycle_groups(graph)
    facts = [_node_fact(path, graph) for path in nodes]
    facts += [_cycle_fact(index, group) for index, group in enumerate(groups)]
    facts.sort(key=lambda f: (f['kind'], f['location']['path']))
    return {'facts': facts, 'summary': _summary(nodes, graph, groups, entry_files, ranking), 'available': True,
            'input_sha': digest('|'.join(nodes).encode('utf-8')), 'reason': None}
