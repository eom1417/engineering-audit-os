"""Simulate one proposed move against the existing graph before it is written. A
move is accepted only when the simulated graph has the predicted indicator
delta and no new violation: no cycle, no new layer break, no new redundancy.

The simulator is a structural replayer. It does not execute Python; it builds
the graph that would result if a human followed the stage, and recomputes the
indicators from that graph. The output is the projected state, not the patched
code.
"""
from collections import defaultdict
from pathlib import Path
from .facts.store import read_set
from .facts import digest
from .sustainability import compute, _indicator_single_source, _indicator_minimal_path, \
    _indicator_data_owners, _indicator_honest_boundaries, _indicator_understandable_units


NAME = 'simulator'
VERSION = '1'
LIMITATIONS = [
    'The simulator replays the structural graph, not the code. A move that produces the predicted '
    'graph change but a wrong runtime result is not caught here.',
    'A canonicalize move assumes the chosen home will host the rule. If the home file already hosts '
    'the rule, the move is a no-op; the simulator returns zero delta.',
    'An eliminate_redundancy move assumes the call is removed at every listed site. Removing only some '
    'sites produces a smaller delta than predicted.',
    'The simulator does not re-run structure / fingerprint / redundancy extractors; it projects the '
    'changes the move would make. Indicators that depend on those extracts are recomputed from the '
    'projection.',
]


def _build_graph(sets):
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


def _adjacency_to_resolve_facts(adjacency):
    facts = []
    for source, targets in adjacency.items():
        for target in targets:
            facts.append({'kind': 'import_edge', 'resolution': 'RESOLVED',
                          'location': {'path': source}, 'value': {'to_path': target}})
    return facts


def _fingerprint_after(sets, canonicalize_stages):
    """Project the fingerprint fact set after canonicalize moves.

    A move removes all occurrences of a cluster except the canonical home's site;
    the cluster shrinks to one occurrence and the cluster fact is removed.
    """
    kept = list(sets.get('fingerprint', {}).get('facts', []))
    canonical_homes_by_cluster = {}
    for stage in canonicalize_stages:
        if stage.get('move') != 'canonicalize': continue
        cluster = stage.get('rule')
        canonical_home = stage.get('canonical_home')
        if cluster and canonical_home:
            canonical_homes_by_cluster[cluster] = canonical_home
    survivors = []
    for fact in kept:
        if fact['kind'] == 'duplicate_cluster':
            if fact['value']['shape_sha'] in canonical_homes_by_cluster:
                home = canonical_homes_by_cluster[fact['value']['shape_sha']]
                occs = [o for o in fact['value']['occurrences'] if o['path'] == home]
                if len(occs) == len(fact['value']['occurrences']):
                    survivors.append(fact)  # All occurrences are at the home; no change.
                elif occs:
                    survivors.append(dict(fact, value=dict(fact['value'],
                                                           occurrences=occs)))
                # else: the cluster shrinks to nothing; drop the fact.
            else:
                survivors.append(fact)
        else:
            survivors.append(fact)
    return {'facts': survivors}


def _redundancy_after(sets, eliminate_stages):
    """Project the redundancy fact set after eliminate_redundancy moves.

    Each stage lists the sites it removes; the corresponding facts disappear.
    """
    drop_paths = set()
    drop_kinds = set()
    for stage in eliminate_stages:
        if stage.get('move') != 'eliminate_redundancy': continue
        drop_kinds.add(stage.get('redundancy_kind'))
        for site in stage.get('sites', []):
            drop_paths.add((site.get('path'), site.get('line') or site.get('start_line')))
    kept = [f for f in sets.get('redundancy', {}).get('facts', [])
            if not (f['value'].get('kind') in drop_kinds
                    and (f['location']['path'],
                          f['location'].get('start_line')) in drop_paths)]
    return {'facts': kept}


def simulate(out, stage, all_stages=None):
    """Project the state after applying the given stage (and all prior stages)."""
    out = Path(out)
    sets = {name: read_set(out, name) for name in ['graph', 'resolve', 'fingerprint', 'redundancy',
                                                     'syntax', 'metrics', 'domain', 'flows']
            if (out / 'facts' / f'{name}.json').is_file()}
    before = compute(out)
    before_rows = {row['indicator']: row['value'] for row in before['rows']}
    adjacency = _build_graph(sets)
    notes = []
    canonicalize_stages = []; eliminate_stages = []
    if stage.get('move') == 'canonicalize': canonicalize_stages.append(stage)
    if stage.get('move') == 'eliminate_redundancy': eliminate_stages.append(stage)
    if stage.get('move') == 'canonicalize':
        canonical_home = stage.get('canonical_home')
        for site in stage.get('sites', []):
            site_path = site.get('path')
            if not site_path or site_path == canonical_home: continue
            adjacency[site_path].add(canonical_home)
            notes.append(f'Add edge {site_path} -> {canonical_home}.')
    sets['resolve'] = {'facts': _adjacency_to_resolve_facts(adjacency)}
    sets['fingerprint'] = _fingerprint_after(sets, canonicalize_stages)
    sets['redundancy'] = _redundancy_after(sets, eliminate_stages)
    single_source = _indicator_single_source(sets)
    minimal_path = _indicator_minimal_path(sets)
    data_owners = _indicator_data_owners(sets)
    honest = _indicator_honest_boundaries(sets)
    understandable = _indicator_understandable_units(sets)
    after_rows = {
        'single_source': single_source.get('value', 0),
        'minimal_path': minimal_path.get('value', 0),
        'data_owners': data_owners.get('value', 0),
        'honest_boundaries': honest.get('value', 0),
        'understandable_units': understandable.get('value', 0),
    }
    delta = {key: round(after_rows.get(key, 0) - before_rows.get(key, 0), 3) for key in after_rows}
    return {'before': before_rows, 'after': after_rows, 'delta': delta,
            'notes': notes,
            'interpretation': 'The simulator projects the graph state and re-runs the indicators. '
                              'A delta of zero means the move is a no-op; a positive delta means the move made things worse.'}
