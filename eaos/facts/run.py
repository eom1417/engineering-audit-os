"""Run deterministic extractors over one shared snapshot and persist their fact sets."""
import json
from pathlib import Path
from . import config, domain, entrypoints, external, fingerprint, flows, graph, history, leftovers, metrics, redundancy, resolve, runtime, secrets, sequences, structure, syntax
from .source import Source
from .store import facts_dir, write_index, write_set
from hashlib import sha256 as _sha256
def digest(data): return _sha256(data).hexdigest()

EXTRACTORS = {'history': history, 'syntax': syntax, 'structure': structure, 'resolve': resolve, 'entrypoints': entrypoints,
              'config': config, 'metrics': metrics, 'graph': graph, 'flows': flows, 'domain': domain,
              'fingerprint': fingerprint, 'sequences': sequences, 'redundancy': redundancy, 'runtime': runtime,
              'leftovers': leftovers,
              'secrets': secrets}
ORDER = ['syntax', 'resolve', 'structure', 'fingerprint', 'sequences', 'redundancy', 'runtime', 'entrypoints', 'config', 'metrics', 'domain', 'history', 'graph', 'flows', 'leftovers', 'secrets']


# Every fact set the tool can read, in one place. Three modules used to keep their own copy of
# this list, and a set added to one of them was invisible to the others — the duplication this
# product exists to find, in the product itself.
# 'external' is produced here too, but only when a caller asks for engines: it shells out to
# pinned binaries, so it never runs by default.
PRODUCED_ELSEWHERE = ['policy', 'verification', 'external']
ALL_SETS = ORDER + PRODUCED_ELSEWHERE
# The minimum a caller needs before it can ask what a change would reach.
GRAPH_PREREQUISITES = ['syntax', 'resolve', 'entrypoints', 'config', 'metrics', 'history', 'graph']


def read_available(out):
    """Load every fact set present in a report directory, whoever produced it."""
    from pathlib import Path as _Path
    from .store import read_set
    return {name: read_set(out, name) for name in ALL_SETS
            if (_Path(out) / 'facts' / (name + '.json')).is_file()}


def ordered(selected):
    names = [n for n in ORDER if n in (selected or EXTRACTORS)]
    unknown = sorted(set(selected or []) - set(EXTRACTORS))
    if unknown: raise ValueError('Unknown extractor: ' + ', '.join(unknown))
    return names


def collect_external(target, out, source, only=None):
    """Run the pinned external engines over the same snapshot and persist their fact set.

    A dead-code finding whose symbol is held in a distribution registry is filtered
    out before the facts are written, so the corpus measure and the ledger agree
    that those candidates are not dead. The filter runs after the engines report
    and before the fact set is persisted: the registry is part of the codebase
    itself and so lives in the snapshot. The reachability-based dead-code finder
    (NS5.T1) is run alongside the engines and its findings written to a separate
    ``reachability.json`` fact set, so downstream stages see the reachable modules
    and symbols without the registry-noise the engine output carries.
    """
    result = external.run(target, source, out=out, only=only)
    from ..correlate import filter_dead_code_references as _filter_dead_code_references
    facts, dropped = _filter_dead_code_references(result['facts'], source)
    if dropped:
        result['summary'] = dict(result.get('summary') or {})
        result['summary']['registry_referenced_dead_code_dropped'] = dropped
    external_entry = write_set(out, 'external', external.NAME, external.VERSION, facts, result['input_sha'],
                                external.LIMITATIONS, result['summary'], result['available'], result['reason'])
    reachability_entry = _run_reachability(target, out, source)
    return [external_entry, reachability_entry]


def _run_reachability(target, out, source):
    """Read the deterministic fact sets the static extractor produced and persist
    reachability's engine_finding-shaped output as a separate fact set.

    The run is computed from already-persisted facts so a cached or partial run
    still gets a reachability scan over whatever facts the previous run left.
    """
    from pathlib import Path
    from .store import facts_dir, write_set, read_set
    from ..reachability import NAME as _rname, VERSION as _rversion, LIMITATIONS as _rlimits, build as _rbuild
    fd = facts_dir(out)
    if not fd.is_dir():
        return {'set': 'reachability', 'facts': 0}
    gathered = []
    for child in sorted(fd.glob('*.json')):
        if child.name == 'index.json' or child.name == 'run.json': continue
        if child.name in {'external.json', 'reachability.json'}: continue
        try:
            data = read_set(out, child.stem)
            gathered.extend(data.get('facts') or [])
        except (OSError, ValueError):
            continue
    findings = [f for f in _rbuild(gathered) if f]
    return write_set(out, 'reachability', _rname, _rversion, findings,
                     digest(''.join(sorted(f.get('id', '') for f in findings)).encode('utf-8')) or ('0' * 64),
                     _rlimits, {'findings': len(findings),
                                'unreachable_modules': sum(1 for f in findings if f.get('value', {}).get('rule') == 'unreachable-module'),
                                'unreachable_symbols': sum(1 for f in findings if f.get('value', {}).get('rule') == 'unreachable-symbol')},
                     True, None)


def add_to_index(out, target, entry):
    """Fold a set produced outside the main sweep into the index, replacing any earlier copy."""
    from .store import facts_dir
    import json as _json
    path = facts_dir(out) / 'index.json'
    existing = _json.loads(path.read_text(encoding='utf-8'))['sets'] if path.is_file() else []
    keep = [row for row in existing if row['set'] != entry['set']]
    return write_index(out, target, keep + [entry])


def collect(target, out, selected=None, max_commits=2000, max_files=100000, max_bytes=2_000_000, source=None,
            exclude=(), engines=None):
    target = Path(target).resolve()
    if not target.is_dir(): raise ValueError('Target must be an existing directory')
    out = Path(out).resolve()
    if out == target or target in out.parents: raise ValueError('Write facts outside the target; the target stays read-only')
    # What the project declared out of scope applies to every caller, not only the ones that
    # remembered to ask. Two commands honoured it and three did not.
    from .scope import declared_exclusions
    from .scope import exclusion_reasons
    exclude = sorted({*(exclude or ()), *declared_exclusions(target)})
    exclusion_reason_map = exclusion_reasons(target)
    names = ordered(selected)
    source = source or Source(target, max_files=max_files, max_bytes=max_bytes, exclude=exclude)
    cache_path = facts_dir(out) / 'syntax-cache.json'
    cache = {}
    if cache_path.is_file():
        try: cache = json.loads(cache_path.read_text(encoding='utf-8'))
        except ValueError: cache = {}
    entries, produced, reuse = [], {}, {}
    for name in names:
        module = EXTRACTORS[name]
        if name == 'history': result = module.run(target, source, max_commits=max_commits)
        elif name == 'resolve':
            ext = []
            if 'external' in produced:
                ext = [f for f in produced['external'] if f.get('resolution') == 'RESOLVED_BY_ENGINE']
            result = module.run(target, source, imports=[f for f in produced.get('syntax', []) if f['kind'] == 'import_edge'] or None,
                                external_edges=ext or None)
        elif name in {'structure', 'fingerprint', 'sequences', 'redundancy', 'runtime'}: result = module.run(target, source, symbols=[f for f in produced.get('syntax', []) if f['kind'] == 'symbol'] or None)
        elif name in {'entrypoints', 'metrics'}: result = module.run(target, source, symbols=[f for f in produced.get('syntax', []) if f['kind'] == 'symbol'] or None)
        elif name == 'flows': result = module.run(target, source, symbols=[f for f in produced.get('syntax', []) if f['kind'] == 'symbol'],
                                                   calls=[f for f in produced.get('syntax', []) if f['kind'] == 'call_edge'],
                                                   edges=produced.get('resolve', []), entry_points=produced.get('entrypoints', []), env=produced.get('config', []),
                                                   imports=[f for f in produced.get('syntax', []) if f['kind'] == 'import_edge'])
        elif name == 'graph': result = module.run(target, source, edges=produced.get('resolve', []), entry_points=produced.get('entrypoints', []), metrics=produced.get('metrics', []), history=produced.get('history', []))
        elif name == 'syntax': result = module.run(target, source, cache=cache)
        elif name == 'leftovers': result = module.run(target, source, resolve_facts=produced.get('resolve', []))
        elif name == 'secrets': result = module.run(target, source)
        else: result = module.run(target, source)
        produced[name] = result['facts']
        if result.get('reused_from_cache'): reuse[name] = result['reused_from_cache']
        entries.append(write_set(out, name, module.NAME, module.VERSION, result['facts'], result['input_sha'],
                                 module.LIMITATIONS, result['summary'], result['available'], result['reason']))
    if engines is not None:
        for entry in collect_external(target, out, source, only=engines or None):
            entries.append(entry)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding='utf-8')
    index = write_index(out, target, entries)
    return {'target': str(target), 'out': str(out), 'fingerprint': source.fingerprint, 'sets': index['sets'],
            'facts': sum(e['facts'] for e in entries), 'reused_from_cache': reuse,
            'excluded_paths': len(source.excluded_files), 'exclude_patterns': list(exclude or []),
            'exclusion_reasons': exclusion_reason_map,
            'limits': 'Deterministic extraction only. No model was consulted and no semantic conclusion is implied.'}
