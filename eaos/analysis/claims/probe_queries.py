"""The graph queries a probe asks again (eaos/analysis/claims/probes.py decide_probe): each over the current snapshot's fact
sets, inconclusive when the facts it reads, or the engines it names, are not there.
"""
from . import from_experience as experience_claims, from_layers as layer_claims, from_logic_flaws as logic_claims, from_repository as repository_claims
from . import from_real_data as real_data_claims
from ..assessments import weaknesses


# Which fact set each query reads. A probe that cannot see its data has no verdict to give:
# refuting a claim because the evidence was not loaded is the worst failure this tool can make.
QUERY_REQUIRES = {
    'cycle_present': 'graph', 'flow_has_unresolved_steps': 'flows', 'no_code_dependency': 'graph',
    'metric_threshold': 'metrics', 'module_size': 'metrics', 'mutable_global_present': 'domain', 'external_write_present': 'domain',
    'policy_violation_present': 'graph', 'duplicate_cluster_present': 'fingerprint',
    'sequence_cluster_present': 'sequences', 'redundancy_present': 'redundancy',
    'engine_cluster_present': 'external', 'load_blocker_present': 'load_model',
    'dead_code_present': 'deadcode', 'broken_code_present': 'broken', 'vulnerable_dependency_present': 'external',
    'weakness_present': 'external', 'boundary_finding_present': 'boundaries',
    'repository_finding_present': 'repository', 'logic_flaw_present': 'logic_flaws',
    'experience_difficulty_present': 'experience', 'real_data_present': 'external',
}


def _verdict(holds, confirmed, refuted):
    return ('CONFIRMED', confirmed) if holds else ('REFUTED', refuted)


def _graph_nodes(sets):
    """{file: the files it imports} of the resolved graph."""
    return {fact['location']['path']: set(fact['value']['depends_on']) for fact in sets['graph']['facts'] if fact['kind'] == 'graph_node'}


def _cycle_present(specification, sets):
    groups = [fact['value']['members'] for fact in sets['graph']['facts'] if fact['kind'] == 'graph_cycle']
    return _verdict(specification['members'] in groups, 'cycle still present', 'no such cycle in the current graph')


def _flow_unresolved(specification, sets):
    flow = next((fact['value'] for fact in sets['flows']['facts'] if fact['value']['flow_id'] == specification['flow_id']), None)
    if flow is None: return 'INCONCLUSIVE', 'flow not present in this snapshot'
    return _verdict(flow['unresolved_steps'], f"{flow['unresolved_steps']} unresolved steps", 'all steps resolve now')


def _same_blocker(blocker, specification):
    # A recheck of a changed copy names the entry by its path and route: an entry fact's id changes with its file.
    if 'entry_path' in specification:
        same = (blocker['path'], blocker['route']) == (specification['entry_path'], specification.get('entry_route'))
    else:
        same = blocker['entry_point'] == specification['entry_point']
    return same and blocker['question'] == specification['question']


def _load_blocker(specification, sets):
    # Re-derive the blocker from the load model: the claim is about what the questions answer.
    from ..readiness.load_projection import blockers
    found = next((blocker for blocker in blockers(sets['load_model']) if _same_blocker(blocker, specification)), None)
    if found: return 'CONFIRMED', f"{found['question']} still answers {found['value']!r}"
    return 'REFUTED', 'the question no longer answers that way for this entry point'


def _vulnerable(specification, sets):
    for fact in sets['external']['facts']:
        if fact['kind'] == 'engine_finding' and fact['location'].get('symbol') == specification['package'] \
                and (fact['value'] or {}).get('kind') == 'vulnerability':
            return 'CONFIRMED', fact['value']['message']
    return 'REFUTED', 'the scan no longer reports this package version as vulnerable'


def _at_place(facts, specification):
    """The first fact at the specification's path and symbol with its rule; None when there is none."""
    wanted = (specification['path'], specification.get('symbol'), specification['rule'])
    return next((fact for fact in facts if (fact['location'].get('path'), fact['location'].get('symbol'), fact['value'].get('rule')) == wanted), None)


def _broken(specification, sets):
    fact = _at_place(sets['broken']['facts'], specification)
    return ('CONFIRMED', fact['value']['message']) if fact else ('REFUTED', 'the reference resolves in the current snapshot')


def _dead(specification, sets):
    # The detector is deterministic: running it again over this snapshot is the probe.
    fact = _at_place(sets['deadcode']['facts'], specification)
    return ('CONFIRMED', fact['value']['message']) if fact else ('REFUTED', 'the candidate is reached or referenced in the current snapshot')


def _finish_line(targets, sets):
    """A claim with a finish line (eaos/analysis/repair/finish_line.py): confirmed while one of its targets stands."""
    from ..repair.finish_line import left, said
    still = left(targets, sets)
    return ('CONFIRMED', 'still to clear: ' + '; '.join(map(said, still))) if still else ('REFUTED', 'every target is cleared')


def _engine_cluster(specification, sets):
    # Re-running the engines is the probe: the claim is about what they report, so it is settled
    # by asking them again, not by re-reading a graph we built ourselves. Only the claim's engines count, and of a
    # measured kind only a finding past its threshold (correlate._standing): any engine's finding anywhere in the file,
    # even one under its limit, refused every simplification of the functions the card names (EAOS, 2026-10-15). A claim
    # made since carries its finish line (eaos/analysis/repair/finish_line.py) and is judged by it alone.
    if specification.get('targets'): return _finish_line(specification['targets'], sets)
    from .correlate import clusters
    for cluster in (c for c in clusters(sets) if c['place'] == specification['place']):
        named = set(specification.get('engines') or ())
        still = [s for s in cluster.get('standing', {}).get(specification['kind'], []) if not named or s.split(':')[0] in named]
        if still: return 'CONFIRMED', 'still reported: ' + '; '.join(still[:12])
        return 'REFUTED', 'no engine of the claim reports this kind past its threshold here any more'
    return 'REFUTED', 'no engine reports anything at this place any more'


def _metric(specification, sets):
    rows = [fact for fact in sets.get('metrics', {}).get('facts', [])
            if fact['location'].get('symbol') == specification['symbol']
            and fact['location']['path'] == specification['path']]
    if not rows: return 'INCONCLUSIVE', 'the symbol is no longer present under that name'
    value = rows[0]['value']          # the code laws' count (eaos/facts/code/metrics.py); its branches in older facts
    measured = value.get('complexity') or value['branches']
    return _verdict(measured > specification['max_branches'], f"complexity {measured}, limit {specification['max_branches']}",
                    f"complexity {measured}, now within the limit of {specification['max_branches']}")


def _module_size(specification, sets):
    rows = [fact for fact in sets.get('metrics', {}).get('facts', [])
            if fact['location']['path'] == specification['path'] and fact['value'].get('scope') == 'file']
    if not rows: return 'INCONCLUSIVE', 'the module is no longer present under that name'
    lines = rows[0]['value']['lines']
    return _verdict(lines > specification['max_lines'], f"{lines} lines, limit {specification['max_lines']}",
                    f"{lines} lines, now within the limit of {specification['max_lines']}")


def _matching(sets, name, kind, specification, *keys):
    """The facts of `kind` in the fact set `name`, at the specification's path, that agree with it on every key."""
    return [fact for fact in sets.get(name, {}).get('facts', [])
            if fact['kind'] == kind and fact['location']['path'] == specification['path']
            and all(fact['value'][key] == specification[key] for key in keys)]


def _mutable(specification, sets):
    rows = [fact for fact in _matching(sets, 'domain', 'mutable_global', specification, 'name')
            if fact['value'].get('mutation_scope') == 'function']
    return _verdict(rows, 'still mutated at runtime', 'no runtime mutation of this value remains')


def _external_write(specification, sets):
    return _verdict(_matching(sets, 'domain', 'external_state_write', specification, 'module', 'attribute'),
                    'the cross-module assignment is still there', 'the assignment is gone')


def _policy(specification, sets):
    present = specification['to_path'] in _graph_nodes(sets).get(specification['path'], set())
    return _verdict(present, 'the forbidden edge is still in the graph', 'the edge is gone')


def _duplicate(specification, sets):
    shapes = {fact['value'].get('shape_sha') for fact in sets.get('fingerprint', {}).get('facts', [])
              if fact['kind'] == 'duplicate_cluster'}
    return _verdict(specification['shape_sha'] in shapes, 'the structural cluster is still present', 'the occurrences no longer share a structure')


def _sequence(specification, sets):
    shapes = {fact['value'].get('sequence_sha') for fact in sets.get('sequences', {}).get('facts', [])}
    return _verdict(specification.get('sequence_sha') in shapes, 'the repeated sequence is still present', 'the sequence is no longer repeated')


def _redundancy(specification, sets):
    return _verdict(_matching(sets, 'redundancy', 'redundancy', specification, 'kind', 'callee'),
                    'the redundant work is still there', 'the redundancy is gone')


def _no_dependency(specification, sets):
    nodes = _graph_nodes(sets)
    forward = specification['right'] in nodes.get(specification['left'], set())
    backward = specification['left'] in nodes.get(specification['right'], set())
    # A claim about one direction must not be refuted by an edge running the other way.
    if specification.get('direction') == 'one_way':
        return ('REFUTED', f"{specification['left']} imports {specification['right']}") if forward \
            else ('CONFIRMED', f"no resolved import from {specification['left']} to {specification['right']}"
                               + (" (the reverse edge exists and is allowed)" if backward else ''))
    linked = forward or backward
    return ('REFUTED', 'a resolved import links them') if linked else ('CONFIRMED', 'no resolved import between them')


# How each query decides, over the current snapshot's fact sets.
QUERIES = {
    'cycle_present': _cycle_present, 'flow_has_unresolved_steps': _flow_unresolved, 'load_blocker_present': _load_blocker,
    'vulnerable_dependency_present': _vulnerable, 'broken_code_present': _broken, 'dead_code_present': _dead,
    'engine_cluster_present': _engine_cluster, 'weakness_present': weaknesses.present, 'metric_threshold': _metric, 'module_size': _module_size, 'mutable_global_present': _mutable,
    'external_write_present': _external_write, 'policy_violation_present': _policy,
    'duplicate_cluster_present': _duplicate, 'sequence_cluster_present': _sequence, 'redundancy_present': _redundancy,
    'no_code_dependency': _no_dependency, 'boundary_finding_present': layer_claims.present,
    'repository_finding_present': repository_claims.present, 'logic_flaw_present': logic_claims.present,
    'experience_difficulty_present': experience_claims.present, 'real_data_present': real_data_claims.present,
}


def run_graph_query(specification, sets):
    query = specification['query']
    required = QUERY_REQUIRES.get(query)
    if required and required not in sets:
        return 'INCONCLUSIVE', f'the {required} facts are not present in this run, so this probe cannot decide'
    # Silence from an engine that never looked proves nothing: a probe naming its engines needs every one to have run.
    missing = set(specification.get('engines') or []) - weaknesses.observed(sets)
    if missing: return 'INCONCLUSIVE', f"{', '.join(sorted(missing))} did not run here, so this probe cannot decide"
    decide = QUERIES.get(query)
    return decide(specification, sets) if decide else ('INCONCLUSIVE', 'unknown query')
