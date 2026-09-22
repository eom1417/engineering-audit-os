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
            edges = codegraph_engine.run(target, Path(workdir) / 'codegraph', tools=None)
            call_edges = [f for f in edges['facts'] if f['kind'] == 'call_edge_external']
            module_edges = [f for f in edges['facts'] if f['kind'] == 'module_edge_external']
            facts.extend(_from_external_call_edges(target, call_edges))
            facts.extend(_from_external_module_edges(target, module_edges))
            total = len(call_edges) + len(module_edges)
            edge_merge = {'status': 'merged' if total else 'empty',
                          'reason': ('CodeGraph returned no call or module edges.' if not total else
                                     'CodeGraph edges were normalized into the external fact set.'),
                          'call_edges': len(call_edges), 'module_edges': len(module_edges)}
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
    counts = {name: len([f for f in facts if f['value']['engine'] == name]) for name in present}
    summary = {'engines_observed': present, 'engines_unavailable': absent,
               # What each engine actually looked for, so silence can be told from absence.
               'evaluated_kinds': {name: manifest['coverage'][name]['evaluated_kinds'] for name in present},
               'findings': len(facts), 'target_unchanged': manifest['target_unchanged'],
               'by_engine': counts,
               'zero_findings': {name: 'engine completed but normalized zero facts'
                                 for name, count in counts.items() if count == 0},
               'edge_merge': edge_merge,
               'by_kind': {kind: len([f for f in facts if f['value']['kind'] == kind])
                           for kind in sorted({f['value']['kind'] for f in facts})},
               'unmapped_rules': {name: manifest['engines'][name].get('unmapped_rules', {}) for name in present}}
    return {'facts': facts, 'input_sha': input_sha, 'summary': summary, 'available': bool(present),
            'reason': None if present else 'no external engine is installed'}

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
