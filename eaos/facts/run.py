"""Run deterministic extractors over one shared snapshot and persist their fact sets."""
import json
from pathlib import Path
from . import config, domain, entrypoints, external, fingerprint, flows, graph, history, metrics, redundancy, resolve, runtime, sequences, structure, syntax
from .source import Source
from .store import facts_dir, write_index, write_set

EXTRACTORS = {'history': history, 'syntax': syntax, 'structure': structure, 'resolve': resolve, 'entrypoints': entrypoints,
              'config': config, 'metrics': metrics, 'graph': graph, 'flows': flows, 'domain': domain,
              'fingerprint': fingerprint, 'sequences': sequences, 'redundancy': redundancy, 'runtime': runtime}
ORDER = ['syntax', 'resolve', 'structure', 'fingerprint', 'sequences', 'redundancy', 'runtime', 'entrypoints', 'config', 'metrics', 'domain', 'history', 'graph', 'flows']


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

    One implementation, two callers: `collect(..., engines=...)` for the single-shot command, and
    the pipeline's own engines stage, so neither can drift from the other.
    """
    result = external.run(target, source, out=out, only=only)
    return write_set(out, 'external', external.NAME, external.VERSION, result['facts'], result['input_sha'],
                     external.LIMITATIONS, result['summary'], result['available'], result['reason'])


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
    exclude = sorted({*(exclude or ()), *declared_exclusions(target)})
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
        elif name == 'resolve': result = module.run(target, source, imports=[f for f in produced.get('syntax', []) if f['kind'] == 'import_edge'] or None)
        elif name in {'structure', 'fingerprint', 'sequences', 'redundancy', 'runtime'}: result = module.run(target, source, symbols=[f for f in produced.get('syntax', []) if f['kind'] == 'symbol'] or None)
        elif name in {'entrypoints', 'metrics'}: result = module.run(target, source, symbols=[f for f in produced.get('syntax', []) if f['kind'] == 'symbol'] or None)
        elif name == 'flows': result = module.run(target, source, symbols=[f for f in produced.get('syntax', []) if f['kind'] == 'symbol'],
                                                   calls=[f for f in produced.get('syntax', []) if f['kind'] == 'call_edge'],
                                                   edges=produced.get('resolve', []), entry_points=produced.get('entrypoints', []), env=produced.get('config', []),
                                                   imports=[f for f in produced.get('syntax', []) if f['kind'] == 'import_edge'])
        elif name == 'graph': result = module.run(target, source, edges=produced.get('resolve', []), entry_points=produced.get('entrypoints', []), metrics=produced.get('metrics', []), history=produced.get('history', []))
        elif name == 'syntax': result = module.run(target, source, cache=cache)
        else: result = module.run(target, source)
        produced[name] = result['facts']
        if result.get('reused_from_cache'): reuse[name] = result['reused_from_cache']
        entries.append(write_set(out, name, module.NAME, module.VERSION, result['facts'], result['input_sha'],
                                 module.LIMITATIONS, result['summary'], result['available'], result['reason']))
    if engines is not None:
        entries.append(collect_external(target, out, source, only=engines or None))
    cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding='utf-8')
    index = write_index(out, target, entries)
    return {'target': str(target), 'out': str(out), 'fingerprint': source.fingerprint, 'sets': index['sets'],
            'facts': sum(e['facts'] for e in entries), 'reused_from_cache': reuse,
            'excluded_paths': len(source.excluded_files), 'exclude_patterns': list(exclude or []),
            'limits': 'Deterministic extraction only. No model was consulted and no semantic conclusion is implied.'}
