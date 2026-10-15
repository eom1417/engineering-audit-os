"""Runnable checks that raise or drop a claim's confidence.

A claim only becomes CONFIRMED because something was actually executed or re-derived, and a probe
that fails turns its claim into REFUTED instead of quietly disappearing.
"""
from datetime import datetime, timezone
from pathlib import Path
import re
from . import weaknesses
from .workspace import read, write

KINDS = ['absence_search', 'graph_query', 'execution', 'coverage', 'falsification']
# What each kind of probe is able to settle. A static check can show that a structure exists;
# it cannot show why it exists, so a claim about cause or responsibility cannot be confirmed by one.
DECIDABLE = {
    'graph_query': {'structure', 'business_rule', 'capability_gap', 'contract', 'risk'},
    'absence_search': {'structure', 'business_rule', 'contract'},
    'coverage': {'risk', 'capability_gap', 'structure'},
    'execution': {'structure', 'business_rule', 'contract', 'cause', 'risk', 'capability_gap', 'responsibility'},
    'falsification': {'structure', 'business_rule', 'contract', 'cause', 'risk', 'capability_gap', 'responsibility'},
}
DEFAULT_SCOPE = ['source', 'test']
CONFIDENCE = ['CONFIRMED', 'LIKELY', 'HYPOTHESIS', 'REFUTED']


def now(): return datetime.now(timezone.utc).isoformat()


def probe(index, claim_id, kind, specification, requires_execution=False):
    return {'id': 'PRB-%03d' % index, 'claim_id': claim_id, 'probe_type': kind,
            'specification': specification, 'requires_execution': requires_execution, 'status': 'not_run'}


def _apply_ceiling(claim, row):
    """A claim may declare a confidence it must never exceed, however well its probe runs.

    An external engine asked the same question twice gives the same answer twice; that is
    repetition, not corroboration, and it must not read as proof.
    """
    ceiling = claim.get('confidence_ceiling')
    if not ceiling or CONFIDENCE.index(claim['confidence']) >= CONFIDENCE.index(ceiling):
        return
    claim['confidence'] = ceiling
    row['status'] = 'PARTIAL'
    row['result'] += f"; this claim is capped at {ceiling} by its source and cannot rise above it"


def _fact_probe(fact):
    """(kind, specification) of the probe that re-decides a fact; None for a fact no probe decides."""
    if fact['kind'] == 'domain_constant':
        return 'absence_search', {
            'patterns': [r'\b%s\b' % re.escape(fact['value']['name'])],
            'search_scope': DEFAULT_SCOPE,
            'expected': 'The name appears as a definition in more than one file and no file imports it from another.'}
    if fact['kind'] == 'graph_cycle':
        return 'graph_query', {
            'query': 'cycle_present', 'members': fact['value']['members'],
            'expected': 'The same files still form a cycle in the resolved import graph.'}
    if fact['kind'] == 'flow':
        return 'graph_query', {
            'query': 'flow_has_unresolved_steps', 'flow_id': fact['value']['flow_id'],
            'expected': 'The traced flow still stops at calls the resolver cannot follow.'}
    if fact['kind'] == 'history_cochange':
        return 'graph_query', {
            'query': 'no_code_dependency', 'left': fact['location']['path'], 'right': fact['location']['paired_path'],
            'expected': 'Neither file imports the other in the resolved graph.'}
    return None


def derive(claims, sets):
    """Attach a probe to every claim whose truth can be decided mechanically."""
    probes = []
    facts = {fact['id']: fact for data in sets.values() for fact in data['facts']}
    for claim in claims:
        # A claim that declares how to re-decide itself stays testable on any later snapshot,
        # even after the underlying fact ids have changed.
        declared = claim.get('probe_spec')
        if declared:
            probes.append(probe(len(probes) + 1, claim['id'], declared['probe_type'], declared['specification'],
                                declared.get('requires_execution', False)))
            continue
        for fact in (facts.get(fact_id) for fact_id in claim.get('fact_ids', [])):
            found = _fact_probe(fact) if fact is not None else None
            if found: probes.append(probe(len(probes) + 1, claim['id'], *found))
    return probes


def constant_sites(name, sets):
    """Definition sites come from the parsed domain facts, not from a text search over the repository.

    A text search cannot tell a definition from the same words inside a string literal in a test,
    and acting on that difference is how a true finding gets wrongly withdrawn.
    """
    for fact in sets.get('domain', {}).get('facts', []):
        if fact['kind'] == 'domain_constant' and fact['value']['name'] == name:
            return [definition['path'] for definition in fact['value']['definitions']]
    return []


def linking_import(name, sites, sets):
    """A real import edge between two definition sites, taken from resolved facts."""
    by_id = {fact['id']: fact for fact in sets.get('syntax', {}).get('facts', []) if fact['kind'] == 'import_edge'}
    for edge in sets.get('resolve', {}).get('facts', []):
        if edge['resolution'] != 'RESOLVED': continue
        origin, destination = edge['location']['path'], edge['value'].get('to_path')
        if origin not in sites or destination not in sites: continue
        imported = by_id.get(edge['value'].get('import_fact_id'), {}).get('value', {}).get('names') or []
        if name in imported:
            return f'{origin} imports {name} from {destination}'
        if not imported:
            # An edge with no recorded names cannot show who owns the value; it is not grounds to withdraw a finding.
            return 'UNKNOWN: ' + f'{origin} imports from {destination}, but the imported names were not captured'
    return None


# Which fact set each query reads. A probe that cannot see its data has no verdict to give:
# refuting a claim because the evidence was not loaded is the worst failure this tool can make.
QUERY_REQUIRES = {
    'cycle_present': 'graph', 'flow_has_unresolved_steps': 'flows', 'no_code_dependency': 'graph',
    'metric_threshold': 'metrics', 'module_size': 'metrics', 'mutable_global_present': 'domain', 'external_write_present': 'domain',
    'policy_violation_present': 'graph', 'duplicate_cluster_present': 'fingerprint',
    'sequence_cluster_present': 'sequences', 'redundancy_present': 'redundancy',
    'engine_cluster_present': 'external', 'load_blocker_present': 'load_model', 'access_gap_present': 'domain',
    'dead_code_present': 'deadcode', 'broken_code_present': 'broken', 'vulnerable_dependency_present': 'external',
    'weakness_present': 'external',
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
    from .load_model import blockers
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


def _engine_cluster(specification, sets):
    # Re-running the engines is the probe: the claim is about what they report, so it is settled
    # by asking them again, not by re-reading a graph we built ourselves. Only the claim's engines count, and of a
    # measured kind only a finding past its threshold (correlate._standing): any engine's finding anywhere in the file,
    # even one under its limit, refused every simplification of the functions the card names (EAOS, 2026-10-15). A claim
    # made since carries its finish line (eaos/finish_line.py) and is judged by it alone.
    if specification.get('targets'):
        from .finish_line import left, said
        still = left(specification['targets'], sets)
        return ('CONFIRMED', 'still to clear: ' + '; '.join(map(said, still))) if still else ('REFUTED', 'every target is cleared')
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
    branches = rows[0]['value']['branches']
    return _verdict(branches > specification['max_branches'], f"{branches} branches, limit {specification['max_branches']}",
                    f"{branches} branches, now within the limit of {specification['max_branches']}")


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


def _exposed(fact, specification):
    """A table still without row-level security, or a policy still open, as the specification names it."""
    value = fact['value']
    if specification['gap'] == 'no_rls':
        return fact['kind'] == 'data_table' and value.get('name') == specification['table'] and value.get('rls_enabled') is False \
            and not value.get('dropped')
    return fact['kind'] == 'db_policy' and value.get('table') == specification['table'] and value.get('name') == specification['policy'] \
        and value.get('open')


def _access_gap(specification, sets):
    still = [f for f in sets.get('domain', {}).get('facts', []) if _exposed(f, specification)]
    return _verdict(still, 'still exposed after every migration', 'no longer exposed')


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
    'access_gap_present': _access_gap, 'external_write_present': _external_write, 'policy_violation_present': _policy,
    'duplicate_cluster_present': _duplicate, 'sequence_cluster_present': _sequence, 'redundancy_present': _redundancy,
    'no_code_dependency': _no_dependency,
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


def _searched_name(row):
    return re.sub(r'^\\b|\\b$', '', row['specification']['patterns'][0]).replace('\\', '')


def _absence(row, sets):
    """Whether a rule is still defined in several files with no import linking them."""
    name = _searched_name(row)
    sites = constant_sites(name, sets)
    link = linking_import(name, sites, sets) if len(sites) > 1 else None
    if len(sites) > 1 and not link:
        return 'CONFIRMED', f"parsed as a definition in {len(sites)} files with no import linking them: " + ', '.join(sites)
    if link and link.startswith('UNKNOWN: '):
        return 'INCONCLUSIVE', link[len('UNKNOWN: '):] + '; a claim is not withdrawn on weaker evidence than confirmed it'
    if link: return 'REFUTED', f'a single owner exists: {link}'
    # One definition left is the repair; none at all may be a file the parser could not read, so it decides nothing.
    if len(sites) == 1: return 'REFUTED', f'the name is defined in one file now: {sites[0]}'
    return 'INCONCLUSIVE', 'the current snapshot no longer parses more than one definition of this name'


def decide_probe(row, sets, allow_execution=False):
    """(status, detail) of one probe over one snapshot's fact sets: the audit's probe stage and the
    acceptance recheck of a repaired copy (eaos/recheck.py) decide with this same function."""
    if row['probe_type'] == 'graph_query':
        return run_graph_query(row['specification'], sets)
    if row['probe_type'] == 'absence_search':
        return _absence(row, sets)
    if row['probe_type'] in {'execution', 'coverage'} and not allow_execution:
        return 'blocked', 'execution probes are disabled; rerun with execution explicitly allowed'
    return 'INCONCLUSIVE', 'no runner for this probe type'


def _confirm(claim, row):
    """A probe that confirmed its claim: CONFIRMED when the probe can establish the claim's type, else LIKELY at most."""
    if claim.get('claim_type') in DECIDABLE.get(row['probe_type'], set()):
        claim['confidence'] = 'CONFIRMED'
    else:
        # The probe supports the claim without establishing it: consistent evidence, not proof.
        claim['confidence'] = 'LIKELY' if claim['confidence'] == 'HYPOTHESIS' else claim['confidence']
        row['result'] += (f"; this probe cannot establish a {claim.get('claim_type')} claim, "
                          f"so the claim rises to LIKELY at most")
        row['status'] = 'PARTIAL'
    claim['method'] = sorted(set(claim['method'] + ['runtime_probe' if row['probe_type'] == 'execution' else 'static_fact']))
    _apply_ceiling(claim, row)


def _settle(claim, row, status):
    """A probe's verdict on its claim: confirmed, or refuted and withdrawn."""
    claim.setdefault('probe_ids', []).append(row['id'])
    if status == 'CONFIRMED':
        _confirm(claim, row)
    elif status == 'REFUTED':
        claim['confidence'] = 'REFUTED'
        claim['status'] = 'withdrawn'
        claim.setdefault('refuted_by', []).append(row['id'])


def run_all(target, out, allow_execution=False):
    """Run every derived probe, update the ledger, and record what each probe decided."""
    out = Path(out)
    dossier = read(out / 'dossier.json')
    from .facts.run import read_available
    sets = read_available(out)
    probes = derive(dossier['claims'], sets)
    by_claim = {claim['id']: claim for claim in dossier['claims']}
    counts = {'CONFIRMED': 0, 'REFUTED': 0, 'PARTIAL': 0, 'INCONCLUSIVE': 0, 'blocked': 0}
    for row in probes:
        status, detail = decide_probe(row, sets, allow_execution)
        row['status'], row['result'], row['ran_at'] = status, detail, now()
        row['searched'] = sorted(constant_sites(_searched_name(row), sets)) if row['probe_type'] == 'absence_search' else None
        claim = by_claim.get(row['claim_id'])
        if claim is None:
            counts[status] = counts.get(status, 0) + 1
            continue
        _settle(claim, row, status)
        counts[row['status']] = counts.get(row['status'], 0) + 1
    write(out / 'probes.json', probes)
    confirmed = sum(1 for claim in dossier['claims'] if claim['confidence'] == 'CONFIRMED')
    dossier['coverage']['probe_confirmed_claims'] = confirmed
    dossier['coverage']['probes_run'] = len(probes)
    dossier['claim_counts'] = {}
    for claim in dossier['claims']:
        dossier['claim_counts'][claim['confidence']] = dossier['claim_counts'].get(claim['confidence'], 0) + 1
    write(out / 'dossier.json', dossier)
    return {'target': str(Path(target).resolve()), 'out': str(out), 'probes': len(probes), 'by_status': counts,
            'confirmed_claims': confirmed, 'claims': len(dossier['claims']),
            'limits': 'A probe decides only what it checks. Execution probes stay disabled unless explicitly allowed, and an isolated copy is not an OS sandbox.'}
