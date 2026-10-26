"""Runnable checks that raise or drop a claim's confidence.

A claim only becomes CONFIRMED because something was actually executed or re-derived, and a probe
that fails turns its claim into REFUTED instead of quietly disappearing.
"""
from datetime import datetime, timezone
from pathlib import Path
import re
from .probe_queries import run_graph_query
from ...core.project.workspace import read, write

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
    acceptance recheck of a repaired copy (eaos/analysis/claims/recheck.py) decide with this same function."""
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
    from ...facts.run import read_available
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
