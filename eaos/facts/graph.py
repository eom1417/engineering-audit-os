"""The dependency graph the other facts hang from, plus a declared attention ranking.

The ranking is a stated heuristic for deciding where to look first, with its factors exposed.
It is never a quality score and never an ordering of severity.
"""
from collections import defaultdict, deque
from . import digest, make
from ..architecture import cycles

NAME = 'graph'
VERSION = '1'
WEIGHTS = {'centrality': 0.3, 'change': 0.3, 'complexity': 0.2, 'entry_proximity': 0.2}
LIMITATIONS = [
    'The graph contains resolved source imports only; runtime wiring and dynamic dispatch are absent.',
    'A cycle is a signal to investigate, not a defect by itself.',
    'Attention weights are a declared convention, not a measured predictor of risk.',
    'Files unreachable from a detected entry point may still be reached through paths no detector covers.',
]


def normalise(values):
    top = max(values.values(), default=0)
    return {key: (value / top if top else 0.0) for key, value in values.items()}


def run(target, source, edges=None, entry_points=None, metrics=None, history=None, **options):
    from . import entrypoints as entry_module, history as history_module, metrics as metrics_module, resolve, syntax
    if edges is None:
        produced = syntax.run(target, source)['facts']
        edges = [f for f in resolve.run(target, source, imports=[f for f in produced if f['kind'] == 'import_edge'])['facts']]
        entry_points = entry_module.run(target, source, symbols=[f for f in produced if f['kind'] == 'symbol'])['facts']
        metrics = metrics_module.run(target, source, symbols=[f for f in produced if f['kind'] == 'symbol'])['facts']
        history = history_module.run(target, source)['facts']
    from .source import language_of
    participating = {edge['location']['path'] for edge in edges or []} | {edge['value'].get('to_path') for edge in edges or []}
    nodes = sorted({item['path'] for item in source.readable()
                    if language_of(item['path']) is not None or item['path'] in participating} - {None})
    adjacency = {path: set() for path in nodes}
    for edge in edges or []:
        if edge['resolution'] != 'RESOLVED': continue
        source_path, target_path = edge['location']['path'], edge['value']['to_path']
        if source_path in adjacency and target_path in adjacency: adjacency[source_path].add(target_path)
    fan_in = {path: 0 for path in nodes}
    for path, targets in adjacency.items():
        for other in targets: fan_in[other] += 1
    entry_files = sorted({fact['location']['path'] for fact in entry_points or []})
    distance = {path: 0 for path in entry_files if path in adjacency}
    queue = deque(distance)
    while queue:
        current = queue.popleft()
        for neighbour in sorted(adjacency[current]):
            if neighbour not in distance:
                distance[neighbour] = distance[current] + 1
                queue.append(neighbour)
    branches = defaultdict(int)
    for fact in metrics or []:
        if fact['kind'] == 'metric' and fact['value'].get('scope') == 'file':
            branches[fact['location']['path']] = fact['value']['branches']
    commits = defaultdict(int)
    for fact in history or []:
        if fact['kind'] == 'history_churn': commits[fact['location']['path']] = fact['value']['commits']
    factors = {
        'centrality': normalise({path: fan_in[path] for path in nodes}),
        'change': normalise({path: commits.get(path, 0) for path in nodes}),
        'complexity': normalise({path: branches.get(path, 0) for path in nodes}),
        'entry_proximity': {path: (1.0 / (1 + distance[path]) if path in distance else 0.0) for path in nodes},
    }
    scored = {path: round(sum(WEIGHTS[name] * factors[name][path] for name in WEIGHTS), 4) for path in nodes}
    ranking = sorted(nodes, key=lambda path: (-scored[path], path))
    position = {path: index + 1 for index, path in enumerate(ranking)}
    groups = cycles({path: set(targets) for path, targets in adjacency.items()})
    in_cycle = {path: index for index, group in enumerate(groups) for path in group}
    facts = []
    for path in nodes:
        facts.append(make('graph_node', NAME, VERSION, digest(path.encode('utf-8')), {'path': path},
                          {'fan_in': fan_in[path], 'fan_out': len(adjacency[path]),
                           'depends_on': sorted(adjacency[path]),
                           'entry_distance': distance.get(path), 'cycle_group': in_cycle.get(path),
                           'attention_score': scored[path], 'attention_rank': position[path],
                           'factors': {name: round(factors[name][path], 4) for name in WEIGHTS}},
                          limitations=LIMITATIONS))
    for index, group in enumerate(groups):
        facts.append(make('graph_cycle', NAME, VERSION, digest('|'.join(group).encode('utf-8')), {'path': group[0]},
                          {'group': index, 'members': group, 'size': len(group)}, limitations=LIMITATIONS))
    facts.sort(key=lambda f: (f['kind'], f['location']['path']))
    reachable = [path for path in nodes if path in distance]
    orphans = [path for path in nodes if not fan_in[path] and not adjacency[path]]
    summary = {'nodes': len(nodes), 'edges': sum(len(targets) for targets in adjacency.values()),
               'cycles': len(groups), 'cycle_members': sorted(in_cycle),
               'entry_files': entry_files,
               'reachable_from_entry': len(reachable),
               'unreachable_from_entry': len(nodes) - len(reachable),
               'weights': WEIGHTS,
               'attention_order': [{'path': path, 'score': scored[path], 'factors': {n: round(factors[n][path], 3) for n in WEIGHTS}} for path in ranking[:30]],
               'most_depended_on': [{'path': path, 'fan_in': fan_in[path]} for path in sorted(nodes, key=lambda p: (-fan_in[p], p))[:15]],
               'isolated_files': orphans[:50],
               'interpretation': 'Structure and attention order only. Nothing here judges design quality; a cycle or a high rank is an invitation to look, not a verdict.'}
    return {'facts': facts, 'summary': summary, 'available': True,
            'input_sha': digest('|'.join(nodes).encode('utf-8')), 'reason': None}
