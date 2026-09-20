"""Runnable checks that raise or drop a claim's confidence.

A claim only becomes CONFIRMED because something was actually executed or re-derived, and a probe
that fails turns its claim into REFUTED instead of quietly disappearing.
"""
from datetime import datetime, timezone
from pathlib import Path
import re
from .facts.source import Source
from .workspace import read, write

KINDS = ['absence_search', 'graph_query', 'execution', 'coverage', 'falsification']
DEFAULT_SCOPE = ['source', 'test']


def now(): return datetime.now(timezone.utc).isoformat()


def probe(index, claim_id, kind, specification, requires_execution=False):
    return {'id': 'PRB-%03d' % index, 'claim_id': claim_id, 'probe_type': kind,
            'specification': specification, 'requires_execution': requires_execution, 'status': 'not_run'}


def derive(claims, sets):
    """Attach a probe to every claim whose truth can be decided mechanically."""
    probes, index = [], 0
    facts = {fact['id']: fact for data in sets.values() for fact in data['facts']}
    for claim in claims:
        # A claim that declares how to re-decide itself stays testable on any later snapshot,
        # even after the underlying fact ids have changed.
        declared = claim.get('probe_spec')
        if declared:
            index += 1
            probes.append(probe(index, claim['id'], declared['probe_type'], declared['specification'],
                                declared.get('requires_execution', False)))
            continue
        for fact_id in claim.get('fact_ids', []):
            fact = facts.get(fact_id)
            if fact is None: continue
            index += 1
            if fact['kind'] == 'domain_constant':
                probes.append(probe(index, claim['id'], 'absence_search', {
                    'patterns': [r'\b%s\b' % re.escape(fact['value']['name'])],
                    'search_scope': DEFAULT_SCOPE,
                    'expected': 'The name appears as a definition in more than one file and no file imports it from another.'}))
            elif fact['kind'] == 'graph_cycle':
                probes.append(probe(index, claim['id'], 'graph_query', {
                    'query': 'cycle_present', 'members': fact['value']['members'],
                    'expected': 'The same files still form a cycle in the resolved import graph.'}))
            elif fact['kind'] == 'flow':
                probes.append(probe(index, claim['id'], 'graph_query', {
                    'query': 'flow_has_unresolved_steps', 'flow_id': fact['value']['flow_id'],
                    'expected': 'The traced flow still stops at calls the resolver cannot follow.'}))
            elif fact['kind'] == 'history_cochange':
                probes.append(probe(index, claim['id'], 'graph_query', {
                    'query': 'no_code_dependency', 'left': fact['location']['path'], 'right': fact['location']['paired_path'],
                    'expected': 'Neither file imports the other in the resolved graph.'}))
            else:
                index -= 1
    return probes


def search_definitions(name, source):
    pattern = re.compile(r'^\s*(?:export\s+)?(?:const|let|var)?\s*%s\s*[:=]' % re.escape(name), re.M)
    importing = re.compile(r'(?:import|from).*\b%s\b' % re.escape(name))
    definitions, importers = [], []
    for item in source.readable():
        text = source.text(item['path'])
        if text is None: continue
        if pattern.search(text): definitions.append(item['path'])
        elif importing.search(text): importers.append(item['path'])
    return sorted(definitions), sorted(importers)


def run_graph_query(specification, sets):
    query = specification['query']
    if query == 'cycle_present':
        groups = [fact['value']['members'] for fact in sets['graph']['facts'] if fact['kind'] == 'graph_cycle']
        return ('CONFIRMED', 'cycle still present') if specification['members'] in groups else ('REFUTED', 'no such cycle in the current graph')
    if query == 'flow_has_unresolved_steps':
        flow = next((fact['value'] for fact in sets['flows']['facts'] if fact['value']['flow_id'] == specification['flow_id']), None)
        if flow is None: return 'INCONCLUSIVE', 'flow not present in this snapshot'
        return ('CONFIRMED', f"{flow['unresolved_steps']} unresolved steps") if flow['unresolved_steps'] else ('REFUTED', 'all steps resolve now')
    if query == 'no_code_dependency':
        nodes = {fact['location']['path']: set(fact['value']['depends_on']) for fact in sets['graph']['facts'] if fact['kind'] == 'graph_node'}
        linked = specification['right'] in nodes.get(specification['left'], set()) or specification['left'] in nodes.get(specification['right'], set())
        return ('REFUTED', 'a resolved import links them') if linked else ('CONFIRMED', 'no resolved import between them')
    return 'INCONCLUSIVE', 'unknown query'


def run_absence_search(specification, source):
    hits = []
    for item in source.readable():
        text = source.text(item['path'])
        if text is None: continue
        for pattern in specification['patterns']:
            for match in re.finditer(pattern, text):
                hits.append(f"{item['path']}:{text.count(chr(10), 0, match.start()) + 1}")
                break
    return hits


def run_all(target, out, allow_execution=False):
    """Run every derived probe, update the ledger, and record what each probe decided."""
    out = Path(out)
    dossier = read(out / 'dossier.json')
    from .facts.store import read_set
    sets = {}
    for name in ['syntax', 'resolve', 'entrypoints', 'config', 'metrics', 'domain', 'history', 'graph', 'flows']:
        path = out / 'facts' / (name + '.json')
        if path.is_file(): sets[name] = read_set(out, name)
    source = Source(target)
    probes = derive(dossier['claims'], sets)
    by_claim = {claim['id']: claim for claim in dossier['claims']}
    counts = {'CONFIRMED': 0, 'REFUTED': 0, 'INCONCLUSIVE': 0, 'blocked': 0}
    for row in probes:
        if row['probe_type'] == 'graph_query':
            status, detail = run_graph_query(row['specification'], sets)
        elif row['probe_type'] == 'absence_search':
            name = re.sub(r'^\\b|\\b$', '', row['specification']['patterns'][0]).replace('\\', '')
            definitions, importers = search_definitions(name, source)
            if len(definitions) > 1 and not importers:
                status, detail = 'CONFIRMED', f"defined in {len(definitions)} files with no import between them"
            elif importers:
                status, detail = 'REFUTED', f"imported by {', '.join(importers[:3])}, so a single owner exists"
            else:
                status, detail = 'INCONCLUSIVE', 'fewer than two definitions found by search'
        elif row['probe_type'] in {'execution', 'coverage'} and not allow_execution:
            status, detail = 'blocked', 'execution probes are disabled; rerun with execution explicitly allowed'
        else:
            status, detail = 'INCONCLUSIVE', 'no runner for this probe type'
        row['status'], row['result'], row['ran_at'] = status, detail, now()
        counts[status] = counts.get(status, 0) + 1
        claim = by_claim.get(row['claim_id'])
        if claim is None: continue
        claim.setdefault('probe_ids', []).append(row['id'])
        if status == 'CONFIRMED':
            claim['confidence'] = 'CONFIRMED'
            claim['method'] = sorted(set(claim['method'] + ['runtime_probe' if row['probe_type'] == 'execution' else 'static_fact']))
        elif status == 'REFUTED':
            claim['confidence'] = 'REFUTED'
            claim['status'] = 'withdrawn'
            claim.setdefault('refuted_by', []).append(row['id'])
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
