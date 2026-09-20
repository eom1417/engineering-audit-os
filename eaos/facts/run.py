"""Run deterministic extractors over one shared snapshot and persist their fact sets."""
import json
from pathlib import Path
from . import config, domain, entrypoints, flows, graph, history, metrics, resolve, syntax
from .source import Source
from .store import facts_dir, write_index, write_set

EXTRACTORS = {'history': history, 'syntax': syntax, 'resolve': resolve, 'entrypoints': entrypoints,
              'config': config, 'metrics': metrics, 'graph': graph, 'flows': flows, 'domain': domain}
ORDER = ['syntax', 'resolve', 'entrypoints', 'config', 'metrics', 'domain', 'history', 'graph', 'flows']


def ordered(selected):
    names = [n for n in ORDER if n in (selected or EXTRACTORS)]
    unknown = sorted(set(selected or []) - set(EXTRACTORS))
    if unknown: raise ValueError('Unknown extractor: ' + ', '.join(unknown))
    return names


def collect(target, out, selected=None, max_commits=2000, max_files=100000, max_bytes=2_000_000, source=None, exclude=()):
    target = Path(target).resolve()
    if not target.is_dir(): raise ValueError('Target must be an existing directory')
    out = Path(out).resolve()
    if out == target or target in out.parents: raise ValueError('Write facts outside the target; the target stays read-only')
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
    cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding='utf-8')
    index = write_index(out, target, entries)
    return {'target': str(target), 'out': str(out), 'fingerprint': source.fingerprint, 'sets': index['sets'],
            'facts': sum(e['facts'] for e in entries), 'reused_from_cache': reuse,
            'excluded_paths': len(source.excluded_files), 'exclude_patterns': list(exclude or []),
            'limits': 'Deterministic extraction only. No model was consulted and no semantic conclusion is implied.'}
