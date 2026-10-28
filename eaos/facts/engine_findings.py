"""Findings from pinned external engines, normalised into facts.

This set is the one place where evidence we did not compute ourselves enters the system. It is
opt-in, it records which engines were absent as plainly as what the present ones found, and it
carries no timing or path from the run, so two runs of the same engine versions over the same
tree produce the same bytes.
"""
from . import digest, make
from .source import LANGUAGE_BY_SUFFIX
from ..engines.contract import ERROR, SCHEMA_MISMATCH
from pathlib import Path

NAME = 'external'
VERSION = '1'
PINNED_CODEGRAPH = 'v0.20.1'
LIMITATIONS = [
    'Every finding here comes from an engine whose rules we did not implement and cannot vouch for; '
    'it is heuristic evidence, and one engine agreeing with itself is not corroboration.',
    'An engine that is not installed produces no findings and no silence: its absence is recorded as '
    'reduced coverage, never as a clean result.',
    'Engine versions are pinned. A version that does not match its pin is still recorded, and marked.',
]


def source_formats():
    """The languages our own extraction understands, so an engine is asked the same question we ask."""
    return sorted(set(LANGUAGE_BY_SUFFIX.values()))


def _copy_artifacts(manifest, out):
    # What an engine produced for the report itself (Syft's SBOM) is copied in under its declared name.
    import shutil
    for report in manifest['engines'].values():
        for artifact, path in (report.get('artifacts') or {}).items():
            if Path(path).is_file(): shutil.copyfile(path, Path(out) / artifact)


def _edge_summary(edges, call_edges, module_edges, metrics):
    total = len(call_edges) + len(module_edges) + len(metrics)
    return {'status': 'merged' if total else 'empty',
            'reason': ('CodeGraph returned no call edge, module edge or symbol metric.'
                       if not total else
                       'CodeGraph output was normalized into the external fact set.'),
            'call_edges': len(call_edges), 'module_edges': len(module_edges),
            'symbol_metrics': len(metrics),
            'files_asked': edges['summary'].get('files_asked', 0),
            'tools': dict(edges['summary'].get('tools') or {})}


def _merge_codegraph(target, workdir, input_sha, facts):
    """CodeGraph edges are facts at a different layer than findings; they belong in our graph."""
    try:
        from ..engines.code import codegraph as codegraph_engine
        # The adapter already ran the tools during `analyze` and wrote what it found beside
        # its report. Reading that file keeps this to one pass over the files.
        edges = codegraph_engine.read_graph_facts(Path(workdir) / 'engines')
        call_edges = [f for f in edges['facts'] if f['kind'] == 'call_edge_external']
        module_edges = [f for f in edges['facts'] if f['kind'] == 'module_edge_external']
        metrics = [f for f in edges['facts'] if f['kind'] == 'symbol_metric_external']
        facts.extend(_from_external_call_edges(target, call_edges))
        facts.extend(_from_external_module_edges(target, module_edges))
        facts.extend(_as_symbol_metrics(input_sha, metrics))
        return _edge_summary(edges, call_edges, module_edges, metrics)
    except Exception as error:
        return {'status': 'failed',
                'reason': f'{type(error).__name__}: {error}'[:300],
                'call_edges': 0, 'module_edges': 0}


def metric_facts(manifest, input_sha):
    return [make('symbol_metric_external', NAME, VERSION, input_sha,
                 {'path': row['path'], 'line': row.get('line'), 'symbol': row.get('symbol')},
                 {'engine': name, 'engine_version': report.get('version'),
                  'granularity': row.get('granularity', 'file'), **row['measurements']},
                 limitations=LIMITATIONS[:1])
            for name, report in sorted(manifest['engines'].items()) for row in report.get('metrics') or []]


def _finding_fact(item, input_sha):
    """The fact of one finding; one the project justified on its line is an `engine_finding_justified`, with its
    reason: shown apart, never a card, and still held against a change by the gates (assessments/weaknesses.py new)."""
    subject = item['subject']
    return make('engine_finding_justified' if item.get('justified') else 'engine_finding', NAME, VERSION, input_sha,
                {'path': subject.get('path'), 'line': subject.get('line'), 'symbol': subject.get('key')},
                {'engine': item['engine'], 'engine_version': item['engine_version'], 'rule': item['rule'],
                 'kind': item['kind'], 'method': item['method'], 'message': item['message'],
                 'measurements': item['measurements'], 'engine_confidence': item['engine_confidence'],
                 'subject_kind': subject.get('kind'), 'cwe': item.get('cwe') or [],
                 'sites': [{'path': path, 'line': line} for path, line in item.get('sites', [])],
                 **({'justified': item['justified']} if item.get('justified') else {})},
                limitations=LIMITATIONS[:1])


def _evaluated_kinds(manifest, present):
    if not isinstance(manifest.get('coverage'), dict): return {}
    return {name: manifest['coverage'][name]['evaluated_kinds'] for name in present}


def _kind_counts(facts):
    kinds = sorted({f['value'].get('kind') for f in facts if f['value'].get('kind')})
    return {kind: len([f for f in facts if f['value'].get('kind') == kind]) for kind in kinds}


def _apart(facts):
    """(the facts, what the project justified on its line with its reason): the second reported apart, not hidden."""
    justified = [f for f in facts if f['kind'] == 'engine_finding_justified']
    return [f for f in facts if f['kind'] != 'engine_finding_justified'], [
        {'engine': f['value']['engine'], 'rule': f['value']['rule'], 'path': f['location']['path'],
         'line': f['location'].get('line'), 'why': f['value']['justified']} for f in justified][:100]


def _summary(manifest, facts, present, absent, edge_merge):
    from ..engines import not_applicable
    # A merged graph edge is an engine fact too, but it carries no finding `kind`: it is an edge,
    # not a judgement. Counting over `.get` keeps it in the engine tallies without inventing a
    # kind for it, and keeps one missing key from taking the whole stage down.
    facts, justified = _apart(facts)
    counts = {name: len([f for f in facts if f['value'].get('engine') == name]) for name in present}
    return {'engines_observed': present, 'engines_unavailable': absent,
            'justified': justified,
            'engines_failed': _failed(manifest),
            'engines_not_applicable': not_applicable(manifest),
            # Candidate boundaries of today's components (GitNexus communities), for the map and the target.
            'communities': _communities(manifest),
            # What each engine actually looked for, so silence can be told from absence.
            'evaluated_kinds': _evaluated_kinds(manifest, present),
            'findings': len(facts), 'target_unchanged': manifest['target_unchanged'],
            'by_engine': counts,
            'zero_findings': {name: 'engine completed but normalized zero facts'
                              for name, count in counts.items() if count == 0},
            'edge_merge': edge_merge,
            'by_kind': _kind_counts(facts),
            'graph_edges_without_a_finding_kind': len([f for f in facts if not f['value'].get('kind')]),
            'unmapped_rules': {name: manifest['engines'][name].get('unmapped_rules', {}) for name in present}}


def _failed(manifest):
    """{engine: why} of each engine that ran and broke: the check says so instead of reading its silence as clean."""
    return {name: detail.get('reason') or detail['status'] for name, detail in manifest['coverage'].items()
            if detail['status'] in (ERROR, SCHEMA_MISMATCH)}


def _communities(manifest):
    """GitNexus's communities: candidate boundaries of today's components."""
    return ((manifest['coverage'].get('gitnexus') or {}).get('detail') or {}).get('communities') or []


NO_CODEGRAPH = {'status': 'not_available', 'reason': 'codegraph was not observed in this run',
                'call_edges': 0, 'module_edges': 0}


def run(target, source, out=None, only=None, keep=False):
    from ..engines import analyze, missing, observed
    workdir = str(out) if out else None
    if workdir is None:
        return {'facts': [], 'input_sha': digest(b'external:no-workdir'), 'summary': {}, 'available': False,
                'reason': 'external engines need a report directory to write their raw artifacts into'}
    manifest = analyze(target, workdir + '/engines', exclude=source.exclude, only=only, formats=source_formats(), keep=keep)
    _copy_artifacts(manifest, out)
    versions = ''.join(f"{name}={detail.get('version')};" for name, detail in sorted(manifest['coverage'].items()))
    input_sha = digest((source.content_fingerprint + '|' + versions).encode('utf-8'))
    facts = []
    present, absent = observed(manifest), missing(manifest)
    edge_merge = _merge_codegraph(target, workdir, input_sha, facts) if 'codegraph' in present else dict(NO_CODEGRAPH)
    facts += metric_facts(manifest, input_sha)
    facts += [_finding_fact(item, input_sha) for item in manifest['findings'] + manifest.get('justified', [])]
    summary = _summary(manifest, facts, present, absent, edge_merge)
    _drop_scratch(Path(workdir) / 'engines')
    return {'facts': facts, 'input_sha': input_sha, 'summary': summary, 'available': bool(present),
            'reason': None if present else 'no external engine is installed'}


# The engines' working folders: their indexes, caches, copies of the project and raw outputs. Once their findings are
# normalised above (engines.json keeps them, once, for an engine run again within the check) nothing reads them: the
# code index alone is 130 MB on a five-file project, and reforge's and semgrep's raw reports were 10 MB on EAOS.
SCRATCH = ('*/',)


def _drop_scratch(engines):
    import shutil
    for folder in Path(engines).glob('*/'):
        shutil.rmtree(folder, ignore_errors=True)


def _as_symbol_metrics(input_sha, metric_facts):
    """Keep the measurement in the vocabulary the engine contract declares for it.

    `symbol_metric_external` is one of the kinds an engine is allowed to produce, and it carries a
    granularity and a set of measurements. It is never a finding: with no threshold a metric of
    complexity 1 would be a problem. `load_model` reads its `complexity` from here.
    """
    out = []
    for fact in metric_facts:
        value = dict(fact.get('value') or {})
        value['engine'] = 'codegraph'
        value['engine_version'] = PINNED_CODEGRAPH
        out.append(make('symbol_metric_external', NAME, VERSION, input_sha,
                        {'path': fact['location']['path'], 'line': fact['location'].get('line'),
                         'symbol': value.get('name')},
                        value, limitations=LIMITATIONS[:1]))
    return out

def _from_external_call_edges(target, codegraph_facts):
    """Convert codegraph's call_edge_external facts into our call_edge facts.

    Each input fact carries the caller's path and the callee's path (from the engine).
    The resolution is RESOLVED_BY_ENGINE: our resolver could not produce this edge on its own.
    """
    def edge(fact, value):
        caller_path = value.get('caller_path') or fact['location']['path']
        return {'path': fact['location']['path']}, {
            'caller': value.get('caller', ''), 'callee': value.get('callee', ''), 'caller_path': caller_path,
            'callee_path': value.get('callee_path') or '', 'line': value.get('line', 0), 'source': 'codegraph'}
    return _engine_edges(target, codegraph_facts, 'call_edge', edge)


def _from_external_module_edges(target, codegraph_facts):
    """Convert codegraph's module_edge_external facts into our import_edge facts."""
    def edge(fact, value):
        return {'path': value.get('from', fact['location']['path'])}, {
            'module': value.get('to', ''), 'from_path': value.get('from', ''), 'to_path': value.get('to', ''),
            'names': [], 'level': 0, 'style': 'codegraph', 'source': 'codegraph'}
    return _engine_edges(target, codegraph_facts, 'import_edge', edge)


def _engine_edges(target, codegraph_facts, kind, edge):
    """One `kind` fact per codegraph edge, located and valued by `edge(fact, value)`, resolved by the engine."""
    from . import digest, make
    out = []
    inventory_sha = digest(target.read_bytes() if target.is_file() else b'')
    for fact in codegraph_facts:
        value = fact.get('value', {})
        location, fields = edge(fact, value)
        new = make(kind, 'external', VERSION, inventory_sha, location, fields,
                   resolution='RESOLVED_BY_ENGINE', limitations=LIMITATIONS[:1])
        new['value']['engine'] = value.get('tool', 'codegraph')
        out.append(new)
    return out


def engine_records(sets, record):
    """The engines' records of one kind (`record` in a symbol_metric_external fact: Presidio's personal values,
    ast-grep's tables and switches) among the read fact sets."""
    return [f for f in (sets.get('external') or {}).get('facts', [])
            if f['kind'] == 'symbol_metric_external' and f['value'].get('record') == record]
