"""The code map of the architecture stage, from EAOS's own facts: the files most worth a look and the groups the imports draw.

    hotspots    each production file's complexity (1 + its branches, facts/metrics.json) times how often it changed
                (facts/history.json history_churn), its code lines breaking a tie
    clusters    the production files grouped by their imports (facts/graph.json depends_on, read both ways) with Louvain's
                method: a file moves to its neighbours' group while modularity rises, then each group becomes one node and
                it starts again; nodes are visited in path order, so two runs on one tree draw the same groups
    modularity  Newman's Q of those groups: the share of imports inside a group minus what chance would give

Only records the check already wrote are read; a missing one gives an empty part.
"""
from collections import defaultdict
from pathlib import Path

from ...core.system.files import read_json
from .system import is_test

HOTSPOTS, CLUSTERS, MEMBERS = 10, 8, 8


def _facts(out, name, kind):
    return [f for f in (read_json(Path(out) / 'facts' / f'{name}.json', {}) or {}).get('facts') or [] if f.get('kind') == kind]


def _path(fact): return (fact.get('location') or {}).get('path') or ''


def hotspots(out):
    """The production files ranked by complexity times changes, size breaking a tie."""
    changes = {_path(f): f['value'] for f in _facts(out, 'history', 'history_churn')}
    authors = {_path(f): f['value'].get('authors') for f in _facts(out, 'history', 'history_ownership')}
    rows = []
    for fact in _facts(out, 'metrics', 'metric'):
        path, value = _path(fact), fact['value']
        if value.get('scope') != 'file' or is_test(path) or not value.get('code_lines'): continue
        complexity, commits = 1 + (value.get('branches') or 0), (changes.get(path) or {}).get('commits') or 0
        rows.append({'path': path, 'complexity': complexity, 'commits': commits, 'rloc': value['code_lines'],
                     'authors': authors.get(path), 'score': complexity * max(1, commits)})
    rows.sort(key=lambda r: (-r['score'], -r['rloc'], r['path']))
    return rows[:HOTSPOTS]


def import_graph(out):
    """({file: {neighbour: imports between them}} of the production files, read both ways; {file: fan-in})."""
    graph, fan_in = defaultdict(lambda: defaultdict(int)), {}
    for fact in _facts(out, 'graph', 'graph_node'):
        path = _path(fact)
        if is_test(path): continue
        fan_in[path] = fact['value'].get('fan_in') or 0
        graph[path]
        for other in fact['value'].get('depends_on') or []:
            if other == path or is_test(other): continue
            graph[path][other] += 1
            graph[other][path] += 1
    return graph, fan_in


def _one_level(graph):
    """(moved, {node: its group}): Louvain's local moves over `graph` until no move raises modularity."""
    degree = {n: sum(graph[n].values()) for n in graph}
    twice = sum(degree.values()) or 1
    group, total, moved = {n: n for n in graph}, dict(degree), False
    for _ in range(50):
        changed = False
        for node in sorted(graph):
            total[group[node]] -= degree[node]
            best = _best_group(node, graph, group, total, degree[node] / twice)
            total[best] += degree[node]
            if best != group[node]: changed = moved = True
            group[node] = best
        if not changed: break
    return moved, group


def _best_group(node, graph, group, total, share):
    """The group `node`, taken out of its own, gains most by joining: the imports it has into a group minus what chance
    gives (the group's total degree times this node's share); its own group when none gains more."""
    links = defaultdict(int)
    for other, weight in graph[node].items():
        if other != node: links[group[other]] += weight
    best = group[node]
    gain = links.get(best, 0) - total[best] * share
    for candidate in sorted(links):
        if links[candidate] - total[candidate] * share > gain + 1e-12:
            best, gain = candidate, links[candidate] - total[candidate] * share
    return best


def _aggregate(graph, group):
    """One node per group, its edges the sum of its members' edges."""
    merged = defaultdict(lambda: defaultdict(int))
    for node, neighbours in graph.items():
        merged[group[node]]
        for other, weight in neighbours.items(): merged[group[node]][group[other]] += weight
    return merged


def louvain(graph):
    """{file: its group}: local moves, then the groups as nodes, until nothing moves."""
    member, level = {n: n for n in graph}, graph
    while True:
        moved, group = _one_level(level)
        if not moved: return member
        member = {n: group[g] for n, g in member.items()}
        level = _aggregate(level, group)


def modularity(graph, member):
    """Newman's Q of `member`'s groups over `graph`; None for a graph with no edge."""
    twice = sum(sum(n.values()) for n in graph.values())
    if not twice: return None
    inside, total = defaultdict(int), defaultdict(int)
    for node, neighbours in graph.items():
        total[member[node]] += sum(neighbours.values())
        inside[member[node]] += sum(w for other, w in neighbours.items() if member[other] == member[node])
    return round(sum(inside[g] / twice - (total[g] / twice) ** 2 for g in total), 3)


def clusters(graph, member, fan_in):
    """The largest groups, each with its most depended-on members first."""
    groups = defaultdict(list)
    for node, group in member.items(): groups[group].append(node)
    rows = []
    for members in groups.values():
        if len(members) < 2: continue
        members.sort(key=lambda path: (-fan_in.get(path, 0), path))
        rows.append({'files': len(members), 'members': members[:MEMBERS],
                     'most_depended_on': members[0] if fan_in.get(members[0]) else None})
    rows.sort(key=lambda r: (-r['files'], r['members'][0]))
    return [{'id': f'group-{n}', **row} for n, row in enumerate(rows[:CLUSTERS], 1)]


def digest(out):
    """{hotspots, clusters, modularity} of one check's facts."""
    graph, fan_in = import_graph(out)
    member = louvain(graph)
    return {'hotspots': hotspots(out), 'clusters': clusters(graph, member, fan_in), 'modularity': modularity(graph, member)}
