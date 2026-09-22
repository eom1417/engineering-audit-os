"""Findings from pinned external engines, normalised into facts.

This set is the one place where evidence we did not compute ourselves enters the system. It is
opt-in, it records which engines were absent as plainly as what the present ones found, and it
carries no timing or path from the run, so two runs of the same engine versions over the same
tree produce the same bytes.
"""
from . import digest, make
from .source import LANGUAGE_BY_SUFFIX
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


def run(target, source, out=None, only=None):
    from ..engines import analyze, missing, observed
    workdir = str(out) if out else None
    if workdir is None:
        return {'facts': [], 'input_sha': digest(b'external:no-workdir'), 'summary': {}, 'available': False,
                'reason': 'external engines need a report directory to write their raw artifacts into'}
    manifest = analyze(target, workdir + '/engines', exclude=source.exclude, only=only, formats=source_formats())
    versions = ''.join(f"{name}={detail.get('version')};" for name, detail in sorted(manifest['coverage'].items()))
    input_sha = digest((source.fingerprint + '|' + versions).encode('utf-8'))
    facts = []
    present, absent = observed(manifest), missing(manifest)
    edge_merge = {'status': 'not_available', 'reason': 'codegraph was not observed in this run',
                  'call_edges': 0, 'module_edges': 0}
    # CodeGraph edges are facts at a different layer than findings; they belong in our graph.
    if 'codegraph' in present:
        try:
            from ..engines import codegraph as codegraph_engine
            # The adapter already ran the tools during `analyze` and wrote what it found beside
            # its report. Reading that file keeps this to one pass over the files.
            edges = codegraph_engine.read_graph_facts(Path(workdir) / 'engines')
            call_edges = [f for f in edges['facts'] if f['kind'] == 'call_edge_external']
            module_edges = [f for f in edges['facts'] if f['kind'] == 'module_edge_external']
            metrics = [f for f in edges['facts'] if f['kind'] == 'symbol_metric_external']
            facts.extend(_from_external_call_edges(target, call_edges))
            facts.extend(_from_external_module_edges(target, module_edges))
            facts.extend(_from_external_symbol_metrics(input_sha, metrics))
            facts.extend(_as_symbol_metrics(input_sha, metrics))
            total = len(call_edges) + len(module_edges) + len(metrics)
            edge_merge = {'status': 'merged' if total else 'empty',
                          'reason': ('CodeGraph returned no call edge, module edge or symbol metric.'
                                     if not total else
                                     'CodeGraph output was normalized into the external fact set.'),
                          'call_edges': len(call_edges), 'module_edges': len(module_edges),
                          'symbol_metrics': len(metrics),
                          'files_asked': edges['summary'].get('files_asked', 0),
                          'tools': dict(edges['summary'].get('tools') or {})}
        except Exception as error:
            edge_merge = {'status': 'failed',
                          'reason': f'{type(error).__name__}: {error}'[:300],
                          'call_edges': 0, 'module_edges': 0}
    for item in manifest['findings']:
        subject = item['subject']
        facts.append(make('engine_finding', NAME, VERSION, input_sha,
                          {'path': subject.get('path'), 'line': subject.get('line'), 'symbol': subject.get('key')},
                          {'engine': item['engine'], 'engine_version': item['engine_version'], 'rule': item['rule'],
                           'kind': item['kind'], 'method': item['method'], 'message': item['message'],
                           'measurements': item['measurements'], 'engine_confidence': item['engine_confidence'],
                           'subject_kind': subject.get('kind'),
                           'sites': [{'path': path, 'line': line} for path, line in item.get('sites', [])]},
                          limitations=LIMITATIONS[:1]))
    # A merged graph edge is an engine fact too, but it carries no finding `kind`: it is an edge,
    # not a judgement. Counting over `.get` keeps it in the engine tallies without inventing a
    # kind for it, and keeps one missing key from taking the whole stage down.
    counts = {name: len([f for f in facts if f['value'].get('engine') == name]) for name in present}
    summary = {'engines_observed': present, 'engines_unavailable': absent,
               # What each engine actually looked for, so silence can be told from absence.
               'evaluated_kinds': {name: manifest['coverage'][name]['evaluated_kinds'] for name in present},
               'findings': len(facts), 'target_unchanged': manifest['target_unchanged'],
               'by_engine': counts,
               'zero_findings': {name: 'engine completed but normalized zero facts'
                                 for name, count in counts.items() if count == 0},
               'edge_merge': edge_merge,
               'by_kind': {kind: len([f for f in facts if f['value'].get('kind') == kind])
                           for kind in sorted({f['value'].get('kind') for f in facts if f['value'].get('kind')})},
               'graph_edges_without_a_finding_kind': len([f for f in facts if not f['value'].get('kind')]),
               'unmapped_rules': {name: manifest['engines'][name].get('unmapped_rules', {}) for name in present}}
    return {'facts': facts, 'input_sha': input_sha, 'summary': summary, 'available': bool(present),
            'reason': None if present else 'no external engine is installed'}


def _from_external_symbol_metrics(input_sha, metric_facts):
    """Per-symbol complexity becomes a performance finding, because that is how it is read.

    `load_model` answers `complexity_class` from findings whose rule is `performance`. A metric
    recorded under any other rule is a measurement nobody reads, so the engine's complexity grade
    enters under the name its only consumer looks for, carrying the file it was measured in.
    """
    out = []
    for fact in metric_facts:
        value = fact.get('value', {})
        out.append(make('engine_finding', NAME, VERSION, input_sha,
                        {'path': fact['location']['path'], 'line': fact['location'].get('line'),
                         'symbol': value.get('name')},
                        {'engine': 'codegraph', 'engine_version': PINNED_CODEGRAPH, 'rule': 'performance',
                         'kind': 'complexity', 'method': 'measured',
                         'message': (f"{value.get('name', 'symbol')}: cyclomatic complexity "
                                     f"{value.get('complexity')} (grade {value.get('grade') or 'n/a'})"),
                         'measurements': [{'name': 'complexity', 'value': value.get('complexity')},
                                          {'name': 'lines_of_code', 'value': value.get('lines')},
                                          {'name': 'branches', 'value': value.get('branches')},
                                          {'name': 'loops', 'value': value.get('loops')},
                                          {'name': 'nesting', 'value': value.get('nesting')}],
                         'engine_confidence': None, 'subject_kind': 'symbol',
                         'complexity': value.get('complexity'), 'grade': value.get('grade'),
                         'sites': []},
                        limitations=LIMITATIONS[:1]))
    return out


def _as_symbol_metrics(input_sha, metric_facts):
    """Keep the measurement in the vocabulary the engine contract declares for it.

    `symbol_metric_external` is one of the kinds an engine is allowed to produce, and it carries a
    granularity and a set of measurements that a `performance` finding flattens into prose. Both
    are stored: the finding is what `load_model` reads, and this is what a reader auditing the
    engine layer's own vocabulary finds when they look for it.
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
    import json
    from . import digest, make
    out = []
    inventory_sha = digest(target.read_bytes() if target.is_file() else b'')
    for fact in codegraph_facts:
        value = fact.get('value', {})
        location = {'path': fact['location']['path']}
        caller_path = value.get('caller_path') or location['path']
        callee_path = value.get('callee_path') or ''
        new = make('call_edge', 'external', VERSION, inventory_sha, location,
                   {'caller': value.get('caller', ''),
                    'callee': value.get('callee', ''),
                    'caller_path': caller_path,
                    'callee_path': callee_path,
                    'line': value.get('line', 0),
                    'source': 'codegraph'},
                   resolution='RESOLVED_BY_ENGINE', limitations=LIMITATIONS[:1])
        new['value']['engine'] = value.get('tool', 'codegraph')
        out.append(new)
    return out


def _from_external_module_edges(target, codegraph_facts):
    """Convert codegraph's module_edge_external facts into our import_edge facts."""
    import json
    from . import digest, make
    out = []
    inventory_sha = digest(target.read_bytes() if target.is_file() else b'')
    for fact in codegraph_facts:
        value = fact.get('value', {})
        location = {'path': value.get('from', fact['location']['path'])}
        new = make('import_edge', 'external', VERSION, inventory_sha, location,
                   {'module': value.get('to', ''),
                    'from_path': value.get('from', ''),
                    'to_path': value.get('to', ''),
                    'names': [], 'level': 0, 'style': 'codegraph',
                    'source': 'codegraph'},
                   resolution='RESOLVED_BY_ENGINE', limitations=LIMITATIONS[:1])
        new['value']['engine'] = value.get('tool', 'codegraph')
        out.append(new)
    return out
