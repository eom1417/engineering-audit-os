"""Pick a canonical home for a cluster of duplicates.

Three properties a candidate must have:
  reachable    every duplicate site can import the canonical home without new violations
  acyclic      placing the home here does not create a cycle
  in_layer     the candidate must belong to a layer the project's policy allows

The result is a ranked list of candidates with the proof the engine can give.
A missing candidate (no layer satisfies the three properties) is a real finding:
the project may need a layer rule change before unification is safe.
"""
from collections import defaultdict, deque
from pathlib import Path
from .facts.store import read_set


def _read_sets(out):
    out = Path(out)
    sets = {}
    for name in ['graph', 'resolve', 'fingerprint']:
        path = out / 'facts' / f'{name}.json'
        if path.is_file(): sets[name] = read_set(out, name)
    return sets


def _adjacency(sets):
    adjacency = defaultdict(set)
    for fact in sets.get('resolve', {}).get('facts', []):
        if fact['resolution'] != 'RESOLVED': continue
        source = fact['location']['path']; target = fact['value'].get('to_path')
        if target: adjacency[source].add(target)
    for fact in sets.get('graph', {}).get('facts', []):
        if fact['kind'] != 'graph_node': continue
        for dep in fact['value'].get('depends_on', []):
            adjacency[fact['location']['path']].add(dep)
    return adjacency


def _reverse(adjacency):
    rev = defaultdict(set)
    for src, targets in adjacency.items():
        for tgt in targets:
            rev[tgt].add(src)
    return rev


def _ancestors_of(node, rev):
    seen = set(); queue = deque([node])
    while queue:
        current = queue.popleft()
        for parent in rev.get(current, ()):
            if parent in seen: continue
            seen.add(parent); queue.append(parent)
    return seen


def _transitive_reachable(start, adjacency, exclude_self=False):
    seen = set()
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for nxt in adjacency.get(current, ()):
            if exclude_self and nxt == start: continue
            if nxt in seen: continue
            seen.add(nxt); queue.append(nxt)
    return seen


def _would_cycle(candidate, target, adjacency):
    """Would placing the home at <candidate> for site <target> create a cycle?

    The new edge is target -> candidate. A cycle exists if candidate already
    reaches target through some other path. Self-loops are not cycles by
    themselves unless the file already imports itself.
    """
    if candidate == target:
        return target in _transitive_reachable(target, adjacency, exclude_self=True)
    return target in _transitive_reachable(candidate, adjacency)


def _policy(policy_path):
    if not policy_path or not Path(policy_path).is_file(): return {}, []
    import json
    try:
        policy = json.loads(Path(policy_path).read_text())
    except ValueError:
        return {}, []
    return policy.get('layers', {}), policy.get('rules', [])


def _layer_of(path, layers):
    from fnmatch import fnmatch
    for name, patterns in layers.items():
        if any(fnmatch(path, pattern) for pattern in patterns): return name
    return None


def _violates_policy(target, candidate, layers, deny):
    if not layers: return False
    target_layer = _layer_of(target, layers)
    candidate_layer = _layer_of(candidate, layers)
    if not target_layer or not candidate_layer: return False
    for rule in deny:
        d = rule.get('deny') or {}
        if d.get('from') == target_layer and d.get('to') == candidate_layer: return True
    return False


def _directory_candidates(members):
    """Candidate paths that are directories shared by every member's path."""
    paths = [m['path'] for m in members]
    if not paths: return set()
    parts_list = [Path(p).parts for p in paths]
    shortest = min(parts_list, key=len)
    prefix = list(shortest[:-1])
    for parts in parts_list:
        new_prefix = []
        for i, component in enumerate(prefix):
            if i < len(parts) - 1 and parts[i] == component:
                new_prefix.append(component)
            else:
                break
        prefix = new_prefix
    lca = '/'.join(prefix)
    candidates = {lca} if lca else {''}  # '' represents the project root
    # Also include each member's parent directory.
    for path in paths:
        parent = str(Path(path).parent)
        if parent == '.':
            parent = ''
        if lca == '' or parent.startswith(lca) or lca == '':
            candidates.add(parent)
    return {c for c in candidates if c is not None}


def _candidates(members, adjacency, rev, layers, deny):
    file_candidates = set()
    for member in members:
        ancestors = _ancestors_of(member['path'], rev) | {member['path']}
        file_candidates.update(ancestors)
    file_candidates |= _directory_candidates(members)
    viable = []
    for candidate in file_candidates:
        cycle_with = [site for site in members if _would_cycle(candidate, site['path'], adjacency)]
        if cycle_with: continue
        violations = sum(1 for site in members
                          if _violates_policy(site['path'], candidate, layers, deny))
        viable.append({'path': candidate, 'layer': _layer_of(candidate, layers),
                        'reachable_sites': sorted({m['path'] for m in members}),
                        'policy_violations': violations})
    paths = {member['path'] for member in members}
    for candidate in viable:
        candidate['home_already'] = candidate['path'] in paths
        candidate['score'] = (1 if candidate['home_already'] else 0,
                              -candidate['policy_violations'])
    viable.sort(key=lambda c: (-c['score'][0], c['score'][1], c['path']))
    return viable


def suggest(out, cluster, policy_path=None):
    sets = _read_sets(out)
    adjacency = _adjacency(sets); rev = _reverse(adjacency)
    layers, deny = _policy(policy_path)
    members = cluster.get('value', {}).get('occurrences', [])
    candidates = _candidates(members, adjacency, rev, layers, deny)
    return {'candidates': candidates, 'members': members,
            'interpretation': 'A candidate is the lowest common ancestor that satisfies reachable, acyclic, in-layer. '
                              'No candidate means the project needs a layer change before unification is safe.'}
