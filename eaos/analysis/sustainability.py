"""The six-indicator sustainability dashboard and the four transformations.

Indicators are computed from facts only, never from the model. Targets are
declared by the engagement contract; the engine writes current/goal/gap rows
for each indicator and the corresponding transformation stages.

A move (canonicalize / introduce / retire / no-op) is generated when an
indicator has a gap. Each move carries the evidence it would change, the
predicted indicator delta, and the falsifier a human would use to reject it.
"""
from collections import defaultdict
import json
from pathlib import Path

from ..core import progress


NAME = 'sustainability'
VERSION = '1'
LIMITATIONS = [
    'Every indicator is a function of structural facts only; runtime behaviour is out of scope.',
    'Targets are taken from the engagement contract or the declared policy; no target is invented.',
    'A transformation is a proposal; its predicted delta is computed from the structural reduction, '
    'not from runtime measurements.',
    'A falsifier is a hint at the kind of evidence that would reject the move; it is not a guard.',
]

INDICATORS = ['single_source', 'minimal_path', 'data_owners', 'honest_boundaries',
               'verifiable_paths', 'understandable_units']

DEFAULT_TARGETS = {
    'single_source': 0.0,
    'minimal_path': 0.0,
    'data_owners': 0,
    'honest_boundaries': 0,
    'verifiable_paths': 0.0,  # P5: fraction of flows that stop at the first boundary. Zero is best.
    'understandable_units': 0,
}


def _read_sets(out):
    """Every fact set present, from the one canonical list.

    This module kept its own copy and it omitted flows, policy and verification, so P4 reported
    "no policy declared" on a project that declares one and P5 never measured anything.
    """
    from ..facts.run import read_available
    return read_available(out)



# A detector that reached a small corner of the snapshot cannot speak for the whole of it. The
# floor is declared rather than tuned: below it the indicator reports what it did not cover
# instead of a number, because one Python file out of 1021 produced a clean 0.0 and a green tick
# over a Go repository the detector never read.
COVERAGE_FLOOR = 0.2


def _too_little_coverage(what, summary):
    """None when the detector saw enough of the snapshot to speak for it; an unmeasured row if not."""
    analysed = summary.get('files_observed')
    blocked = summary.get('files_blocked', 0)
    if analysed is None: return None
    total = analysed + blocked
    if not total: return None
    share = analysed / total
    if share >= COVERAGE_FLOOR: return None
    return {'value': None, 'measured': False, 'files_analysed': analysed, 'files_blocked': blocked,
            'reason': f'{what} analysed {analysed} of {total} file(s) ({share:.1%}), below the '
                      f'declared floor of {COVERAGE_FLOOR:.0%}; this is a statement about coverage, '
                      f'not a clean result'}


def _indicator_single_source(sets):
    """P1: the smaller the duplicate-cluster count, the closer to one source of truth.

    Guarded the same way as P2: a fingerprinter that analysed nothing has found nothing to report,
    not nothing to find.
    """
    summary = sets.get('fingerprint', {}).get('summary') or {}
    unmeasured = _too_little_coverage('fingerprinting', summary)
    if unmeasured: return unmeasured
    clusters = [f for f in sets.get('fingerprint', {}).get('facts', []) if f['kind'] == 'duplicate_cluster']
    duplicates = sum(len(c['value']['occurrences']) - 1 for c in clusters)
    symbols = max(1, sum(1 for f in sets.get('syntax', {}).get('facts', []) if f['kind'] == 'symbol'))
    return {'value': round(duplicates / symbols, 3), 'measured': True,
            'duplicates': duplicates, 'symbols': symbols}


def _indicator_minimal_path(sets):
    """P2: the lower the redundant-work count per flow, the closer to a minimal path.

    A detector that analysed no file cannot report a clean result. Dividing zero findings by every
    function in the snapshot produced 0.0 and a green tick on a project whose language the
    detector does not read, which is the most confident way to say nothing.
    """
    summary = sets.get('redundancy', {}).get('summary') or {}
    unmeasured = _too_little_coverage('redundancy detection', summary)
    if unmeasured: return unmeasured
    redundant = sum(f['value']['kind'] in {'repeated_call', 'hoistable_call', 'n_plus_one', 'pass_through'}
                     for f in sets.get('redundancy', {}).get('facts', []))
    flows = max(1, sum(1 for f in sets.get('syntax', {}).get('facts', [])
                        if f['kind'] == 'symbol' and f['value'].get('kind') == 'function'))
    return {'value': round(redundant / flows, 3), 'measured': True,
            'redundant': redundant, 'functions': flows,
            'files_analysed': summary.get('files_observed')}


def writers(sets):
    """{field: the files that write it} for every mutable field written from more than one file."""
    found = defaultdict(set)
    for fact in sets.get('domain', {}).get('facts', []):
        if fact['kind'] == 'mutable_global':
            found[fact['value']['name']].add(fact['location']['path'])
        if fact['kind'] == 'external_state_write':
            # A dotted name, not a tuple: the indicator is written as JSON, whose keys are strings.
            found[f"{fact['value']['module']}.{fact['value']['attribute']}"].add(fact['location']['path'])
    return {key: sorted(paths) for key, paths in found.items() if len(paths) > 1}


def _indicator_data_owners(sets):
    """P3: writers per mutable field; lower is better. Not measured while its detector is under its precision bar."""
    from .claims import hidden_detectors
    hidden = hidden_detectors().get('data_owners')
    if hidden: return {'value': None, 'measured': False, 'reason': 'hidden: ' + hidden}
    multi = {key: len(paths) for key, paths in writers(sets).items()}
    return {'value': len(multi), 'multi_writers': multi}


def _indicator_honest_boundaries(sets):
    """P4: import cycles plus violations of the policy the project declared."""
    graph = sets.get('graph', {}).get('summary') or {}
    if 'cycles' not in graph: return {'value': None, 'measured': False, 'reason': 'no dependency graph in this snapshot'}
    policy = sets.get('policy', {})
    declared = (policy.get('summary') or {}).get('declared')
    violations = (policy.get('summary') or {}).get('violations', 0) if declared else 0
    return {'value': graph['cycles'] + violations, 'measured': True, 'cycles': graph['cycles'],
            'policy_declared': bool(declared), 'policy_violations': violations,
            'note': None if declared else 'no policy declared, so only cycles are counted'}


def _indicator_verifiable_paths(sets):
    """P5: the share of traced flows that stop before reaching any other code.

    Every indicator points the same way: zero is the target, and a larger number is a larger gap.
    An earlier version divided resolved flows by total flows, so a perfect result read as the worst
    gap on the dashboard — and it read a summary key that does not exist, so it always returned 1.0.
    """
    summary = sets.get('flows', {}).get('summary') or {}
    total = summary.get('flows')
    if not total: return {'value': None, 'measured': False,
                          'reason': 'no traced flow in this snapshot; nothing to measure'}
    stopping = summary.get('flows_stopping_at_the_first_boundary', 0)
    return {'value': round(stopping / total, 3), 'measured': True,
            'stopping_at_first_boundary': stopping, 'flows': total}


def _indicator_understandable_units(sets):
    """P6: functions whose body exceeds a size threshold."""
    metrics = sets.get('metrics', {}).get('facts', [])
    big = [f for f in metrics if f['kind'] == 'metric' and f['value'].get('scope') in {'function', 'method'}
            and f['value']['lines'] > 80]
    return {'value': len(big), 'oversized': len(big)}


def compute(out, targets=None):
    sets = _read_sets(out)
    targets = dict(DEFAULT_TARGETS, **(targets or {}))
    measures = (('single_source', _indicator_single_source), ('minimal_path', _indicator_minimal_path),
                ('data_owners', _indicator_data_owners), ('honest_boundaries', _indicator_honest_boundaries),
                ('verifiable_paths', _indicator_verifiable_paths), ('understandable_units', _indicator_understandable_units))
    indicators = {}
    for done, (name, measure) in enumerate(measures):
        progress.count('indicators', done, len(measures))
        indicators[name] = measure(sets)
    progress.count('indicators', len(measures), len(measures))
    rows = []
    for name, indicator in indicators.items():
        target = targets.get(name, DEFAULT_TARGETS[name])
        value = indicator.get('value')
        measured = indicator.get('measured', value is not None)
        rows.append({'indicator': name, 'value': value if measured else None,
                     'target': target, 'measured': bool(measured),
                     'gap': round(value - target, 4) if measured and value is not None else None,
                     'details': {k: v for k, v in indicator.items() if k != 'value'}})
    moves = _transformations(out, {'rows': rows})
    return {'indicators': indicators, 'rows': rows, 'targets': targets, 'moves': moves,
            'interpretation': 'Indicators are pure functions of structural facts. The target is declared; the gap is the '
                              'distance to the declared target; the proposal is a function of the same facts.'}


def _transformations(out, dashboard):
    """For each indicator with a non-zero gap, propose concrete moves.

    A move is identified by: which indicator it would reduce, the evidence
    ids it would touch, and the falsifier a human reviewer can use to reject it.
    """
    sets = _read_sets(out)
    by_indicator = {row['indicator']: row for row in dashboard['rows']}
    moves = []
    if (by_indicator['single_source']['gap'] or 0) > 0:
        clusters = [f for f in sets.get('fingerprint', {}).get('facts', []) if f['kind'] == 'duplicate_cluster']
        moves += _canonicalize_moves(clusters, by_indicator['single_source'])
    if (by_indicator['minimal_path']['gap'] or 0) > 0:
        moves += _redundancy_moves(sets.get('redundancy', {}).get('facts', []), by_indicator['minimal_path'])
    return moves


def _canonicalize_moves(clusters, row):
    """One move per duplicate cluster of two occurrences or more: give the rule one home."""
    return [{'move': 'canonicalize', 'indicator': 'single_source',
             'rule': cluster['value']['shape_sha'],
             'occurrences': [{'path': o['path'], 'line': o['start_line'], 'symbol': o['symbol']}
                             for o in cluster['value']['occurrences']],
             'canonical_home_candidates': cluster['value']['occurrences'],
             'predicted': {'single_source': round(row['gap'] - 1.0 / max(1, row['details'].get('symbols', 1)), 3)},
             'falsifier': 'Demonstrate the two occurrences compute a different rule (different units, '
                          'ranges, or business meanings).'}
            for cluster in clusters if len(cluster['value']['occurrences']) >= 2]


def _redundancy_moves(redundancy, row):
    """One move per kind of redundant work: hoist or drop the repeated call."""
    by_kind = defaultdict(list)
    for fact in redundancy:
        by_kind[fact['value']['kind']].append(fact)
    return [{'move': 'eliminate_redundancy', 'indicator': 'minimal_path',
             'kind': kind,
             'sites': [{'path': f['location']['path'], 'line': f['location']['start_line'],
                        'symbol': f['location'].get('symbol'), 'callee': f['value'].get('callee')}
                       for f in facts[:20]],
             'predicted': {'minimal_path': round(row['gap'] - len(facts) / max(1, row['details'].get('functions', 1)), 3)},
             'falsifier': 'Show that the call depends on loop-local state and cannot be hoisted, or that '
                          'the "redundant" call returns a different value across iterations.'}
            for kind, facts in by_kind.items()]


def write(out, targets=None):
    """Write sustainability.json from the computed dashboard."""
    dashboard = compute(out, targets)
    record = {'schema_version': 1, 'rows': dashboard['rows'], 'indicators': dashboard['indicators'],
              'targets': dashboard['targets'], 'moves': dashboard['moves'],
              'interpretation': dashboard['interpretation'], 'limitations': LIMITATIONS}
    (Path(out) / 'sustainability.json').write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'rows': dashboard['rows'], 'moves': dashboard['moves'], 'record': str(Path(out) / 'sustainability.json')}
