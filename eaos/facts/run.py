"""Run deterministic extractors over one shared snapshot and persist their fact sets."""
import json
import time as _time
from pathlib import Path
from . import (broken, config, deadcode, domain, entrypoints, external, fingerprint, flows, graph, history, leftovers,
               metrics, pipeline, redundancy, resolve, runtime, secrets, sequences, structure, syntax)
from .source import Source
from ..core import progress
from .store import write_index, write_set
from hashlib import sha256 as _sha256
def digest(data): return _sha256(data).hexdigest()

EXTRACTORS = {'history': history, 'syntax': syntax, 'structure': structure, 'resolve': resolve, 'entrypoints': entrypoints,
              'config': config, 'metrics': metrics, 'graph': graph, 'flows': flows, 'domain': domain,
              'fingerprint': fingerprint, 'sequences': sequences, 'redundancy': redundancy, 'runtime': runtime,
              'leftovers': leftovers, 'deadcode': deadcode, 'broken': broken,
              'secrets': secrets, 'pipeline': pipeline}
ORDER = ['syntax', 'resolve', 'structure', 'fingerprint', 'sequences', 'runtime', 'entrypoints', 'redundancy', 'config', 'metrics', 'domain', 'history', 'graph', 'flows', 'leftovers', 'deadcode', 'broken', 'secrets', 'pipeline']


# Every fact set the tool can read, in one place. Three modules used to keep their own copy of
# this list, and a set added to one of them was invisible to the others — the duplication this
# product exists to find, in the product itself.
# 'external' is produced here too, but only when a caller asks for engines: it shells out to
# pinned binaries, so it never runs by default. 'boundaries' is the layers' (eaos/analysis/layers/).
PRODUCED_ELSEWHERE = ['policy', 'verification', 'external', 'boundaries']
ALL_SETS = ORDER + PRODUCED_ELSEWHERE
# The minimum a caller needs before it can ask what a change would reach.
GRAPH_PREREQUISITES = ['syntax', 'resolve', 'entrypoints', 'config', 'metrics', 'history', 'graph']


def read_available(out):
    """Every fact set present in a report directory, whoever produced it, each read when first asked for."""
    from .store import Sets
    return Sets(out, ALL_SETS)


def ordered(selected):
    names = [n for n in ORDER if n in (selected or EXTRACTORS)]
    unknown = sorted(set(selected or []) - set(EXTRACTORS))
    if unknown: raise ValueError('Unknown extractor: ' + ', '.join(unknown))
    return names


def collect_external(target, out, source, only=None, keep=False):
    """Run the pinned external engines over the same snapshot and persist their fact set.

    Registry-referenced dead-code candidates are tagged ``value.referenced_by_registry``, then every
    dead-code candidate is adjudicated against EAOS's own detector (facts/deadcode): the engine's fields
    stay as written, and value.adjudication says whether EAOS asserts it.
    """
    result = external.run(target, source, out=out, only=only, keep=keep)
    from .registry import filter_dead_code_references as _filter_dead_code_references
    facts, _dropped = _filter_dead_code_references(result['facts'], source)
    # One verdict per dead-code candidate, whichever engine raised it: EAOS's own detector and the same
    # textual reference test decide what the report asserts (see facts/deadcode.adjudicate).
    from .store import read_set
    try: own = read_set(out, 'deadcode').get('facts') or []
    except (OSError, ValueError): own = []
    facts = deadcode.adjudicate(facts, source, own)
    referenced = sum(1 for f in facts
                     if (f.get('value') or {}).get('referenced_by_registry'))
    if referenced:
        result['summary'] = dict(result.get('summary') or {})
        result['summary']['registry_referenced_dead_code_marked'] = referenced
    external_entry = write_set(out, 'external', external.NAME, external.VERSION, facts, result['input_sha'],
                                external.LIMITATIONS, result['summary'], result['available'], result['reason'])
    return [external_entry]


def add_to_index(out, target, entry):
    """Fold a set produced outside the main sweep into the index, replacing any earlier copy."""
    from .store import facts_dir
    import json as _json
    path = facts_dir(out) / 'index.json'
    existing = _json.loads(path.read_text(encoding='utf-8'))['sets'] if path.is_file() else []
    keep = [row for row in existing if row['set'] != entry['set']]
    return write_index(out, target, keep + [entry])


def _syntax_of(produced, kind):
    return [f for f in produced.get('syntax', []) if f['kind'] == kind]


def _symbols_or_none(produced, context):
    return {'symbols': _syntax_of(produced, 'symbol') or None}


def _resolve_args(produced, context):
    ext = [f for f in produced.get('external', []) if f.get('resolution') == 'RESOLVED_BY_ENGINE']
    return {'imports': _syntax_of(produced, 'import_edge') or None, 'external_edges': ext or None}


def _redundancy_args(produced, context):
    return {'symbols': _syntax_of(produced, 'symbol') or None, 'structure': produced.get('structure'),
            'entrypoints': produced.get('entrypoints')}


def _flows_args(produced, context):
    return {'symbols': _syntax_of(produced, 'symbol'), 'calls': _syntax_of(produced, 'call_edge'),
            'edges': produced.get('resolve', []), 'entry_points': produced.get('entrypoints', []), 'env': produced.get('config', []),
            'imports': _syntax_of(produced, 'import_edge')}


def _graph_args(produced, context):
    return {'edges': produced.get('resolve', []), 'entry_points': produced.get('entrypoints', []),
            'metrics': produced.get('metrics', []), 'history': produced.get('history', [])}


def _deadcode_args(produced, context):
    return {'symbols': _syntax_of(produced, 'symbol'), 'resolved': produced.get('resolve', []),
            'entry_points': produced.get('entrypoints', [])}


# What each extractor reads from the sets produced before it; an extractor absent here reads only the snapshot.
EXTRACTOR_ARGS = {
    'history': lambda produced, context: {'max_commits': context['max_commits']},
    'resolve': _resolve_args,
    'redundancy': _redundancy_args,
    'structure': _symbols_or_none, 'fingerprint': _symbols_or_none, 'sequences': _symbols_or_none,
    'runtime': _symbols_or_none, 'entrypoints': _symbols_or_none, 'metrics': _symbols_or_none,
    'flows': _flows_args,
    'graph': _graph_args,
    'syntax': lambda produced, context: {'cache': context['cache']},
    'leftovers': lambda produced, context: {'resolve_facts': produced.get('resolve', [])},
    'broken': lambda produced, context: {'resolved': produced.get('resolve', [])},
    'deadcode': _deadcode_args,
}


def _checked_paths(target, out):
    target = Path(target).resolve()
    if not target.is_dir(): raise ValueError('Target must be an existing directory')
    out = Path(out).resolve()
    if out == target or target in out.parents: raise ValueError('Write facts outside the target; the target stays read-only')
    return target, out


def _load_cache(cache_path):
    if not cache_path.is_file(): return {}
    try: return json.loads(cache_path.read_text(encoding='utf-8'))
    except ValueError: return {}


def _run_extractor(name, target, source, produced, context, step, done, total):
    module = EXTRACTORS[name]
    step(name, done, total, 'running')
    began = _time.monotonic()
    arguments = EXTRACTOR_ARGS.get(name, lambda produced, context: {})(produced, context)
    result = module.run(target, source, **arguments)
    available = result['available']
    step(name, done + 1, total, 'ok' if available else 'unavailable', _time.monotonic() - began,
         reason='' if available else result.get('reason') or '',
         reason_code='' if available else 'extractor_unavailable')
    return module, result


def _extract(names, target, out, source, context):
    """Each named extractor run in order over the one snapshot, its set written: (index entries, sets reused from the
    cache)."""
    entries, produced, reuse = [], {}, {}
    step = progress.step
    for name in names: step(name, 0, len(names), 'waiting')
    for done, name in enumerate(names):
        module, result = _run_extractor(name, target, source, produced, context, step, done, len(names))
        produced[name] = result['facts']
        if result.get('reused_from_cache'): reuse[name] = result['reused_from_cache']
        entries.append(write_set(out, name, module.NAME, module.VERSION, result['facts'], result['input_sha'],
                                 module.LIMITATIONS, result['summary'], result['available'], result['reason']))
    return entries, reuse


def collect(target, out, selected=None, max_commits=2000, max_files=100000, max_bytes=2_000_000, source=None,
            exclude=(), engines=None, cache=None):
    """Each extractor's start and end is reported as a step of the running stage (eaos/core/progress/context.py): the live
    map shows where the facts stage is inside. It does not change what runs. `cache`: the file the parsed files are kept in between checks (in the check's runtime,
    never in the report: 63 MB of it sat among EAOS's facts); without one they are kept for this call only."""
    target, out = _checked_paths(target, out)
    # What the project declared out of scope applies to every caller, not only the ones that
    # remembered to ask. Two commands honoured it and three did not.
    from .scope import declared_exclusions
    from .scope import exclusion_reasons
    exclude = sorted({*(exclude or ()), *declared_exclusions(target)})
    exclusion_reason_map = exclusion_reasons(target)
    names = ordered(selected)
    source = source or Source(target, max_files=max_files, max_bytes=max_bytes, exclude=exclude)
    context = {'cache': _load_cache(Path(cache)) if cache else {}, 'max_commits': max_commits}
    entries, reuse = _extract(names, target, out, source, context)
    if engines is not None:
        entries += collect_external(target, out, source, only=engines or None)
    if cache:
        Path(cache).parent.mkdir(parents=True, exist_ok=True)       # the facts come before the runtime's other parts
        Path(cache).write_text(json.dumps(context['cache'], ensure_ascii=False), encoding='utf-8')
    index = write_index(out, target, entries)
    return {'target': str(target), 'out': str(out), 'fingerprint': source.fingerprint, 'sets': index['sets'],
            'facts': sum(e['facts'] for e in entries), 'reused_from_cache': reuse,
            'excluded_paths': len(source.excluded_files), 'exclude_patterns': list(exclude or []),
            'exclusion_reasons': exclusion_reason_map,
            'limits': 'Deterministic extraction only. No model was consulted and no semantic conclusion is implied.'}
