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
from .facts import digest
from .facts.store import read_set


NAME = 'sustainability'
VERSION = '1'
LIMITATIONS = [
    'Every indicator is a function of structural facts only; runtime behaviour is out of scope.',
    'Targets are taken from the engagement contract or the declared policy; no target is invented.',
    'A transformation is a proposal; its predicted delta is computed from the structural reduction, '
    'not from runtime measurements.',
    'A falsifier is a hint at the kind of evidence that would reject the move; it is not a guard.',
]

SHOWN_MOVES = 10
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
    from .facts.run import read_available
    return read_available(out)


def _indicator_single_source(sets):
    """P1: the smaller the duplicate-cluster count, the closer to one source of truth."""
    clusters = [f for f in sets.get('fingerprint', {}).get('facts', []) if f['kind'] == 'duplicate_cluster']
    duplicates = sum(len(c['value']['occurrences']) - 1 for c in clusters)
    symbols = max(1, sum(1 for f in sets.get('syntax', {}).get('facts', []) if f['kind'] == 'symbol'))
    return {'value': round(duplicates / symbols, 3), 'duplicates': duplicates, 'symbols': symbols}


def _indicator_minimal_path(sets):
    """P2: the lower the redundant-work count per flow, the closer to a minimal path."""
    redundant = sum(f['value']['kind'] in {'repeated_call', 'hoistable_call', 'n_plus_one', 'pass_through'}
                     for f in sets.get('redundancy', {}).get('facts', []))
    flows = max(1, sum(1 for f in sets.get('syntax', {}).get('facts', [])
                        if f['kind'] == 'symbol' and f['value'].get('kind') == 'function'))
    return {'value': round(redundant / flows, 3), 'redundant': redundant, 'functions': flows}


def _indicator_data_owners(sets):
    """P3: writers per mutable field; lower is better."""
    writers = defaultdict(set)
    for fact in sets.get('domain', {}).get('facts', []):
        if fact['kind'] == 'mutable_global':
            writers[fact['value']['name']].add(fact['location']['path'])
        if fact['kind'] == 'external_state_write':
            writers[(fact['value']['module'], fact['value']['attribute'])].add(fact['location']['path'])
    multi = {key: len(paths) for key, paths in writers.items() if len(paths) > 1}
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
    indicators = {
        'single_source': _indicator_single_source(sets),
        'minimal_path': _indicator_minimal_path(sets),
        'data_owners': _indicator_data_owners(sets),
        'honest_boundaries': _indicator_honest_boundaries(sets),
        'verifiable_paths': _indicator_verifiable_paths(sets),
        'understandable_units': _indicator_understandable_units(sets),
    }
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
    rows = dashboard['rows']
    by_indicator = {row['indicator']: row for row in rows}
    moves = []
    fingerprint_clusters = [f for f in sets.get('fingerprint', {}).get('facts', [])
                              if f['kind'] == 'duplicate_cluster']
    redundancy = sets.get('redundancy', {}).get('facts', [])
    if by_indicator['single_source']['gap'] > 0:
        for cluster in fingerprint_clusters:
            occs = cluster['value']['occurrences']
            if len(occs) < 2: continue
            moves.append({'move': 'canonicalize', 'indicator': 'single_source',
                          'rule': cluster['value']['shape_sha'],
                          'occurrences': [{'path': o['path'], 'line': o['start_line'], 'symbol': o['symbol']}
                                          for o in occs],
                          'canonical_home_candidates': occs,
                          'predicted': {'single_source': round(by_indicator['single_source']['gap']
                                                                  - 1.0 / max(1, by_indicator['single_source']['details'].get('symbols', 1)), 3)},
                          'falsifier': 'Demonstrate the two occurrences compute a different rule (different units, '
                                       'ranges, or business meanings).'})
    if by_indicator['minimal_path']['gap'] > 0:
        by_kind = defaultdict(list)
        for fact in redundancy:
            by_kind[fact['value']['kind']].append(fact)
        for kind, facts in by_kind.items():
            moves.append({'move': 'eliminate_redundancy', 'indicator': 'minimal_path',
                          'kind': kind,
                          'sites': [{'path': f['location']['path'], 'line': f['location']['start_line'],
                                       'symbol': f['location'].get('symbol'), 'callee': f['value'].get('callee')}
                                      for f in facts[:20]],
                          'predicted': {'minimal_path': round(by_indicator['minimal_path']['gap']
                                                                 - len(facts) / max(1, by_indicator['minimal_path']['details'].get('functions', 1)), 3)},
                          'falsifier': 'Show that the call depends on loop-local state and cannot be hoisted, or that '
                                       'the "redundant" call returns a different value across iterations.'})
    return moves


def render(out, targets=None, language='ar'):
    """Render SUSTAINABILITY.md from the computed dashboard."""
    dashboard = compute(out, targets)
    moves = dashboard['moves']
    ar = language == 'ar'
    lines = []
    if ar:
        lines += ['# لوحة الاستدامة', '',
                  '> الخصائص الست قابلة للقياس. القيم من الحقائق الحتمية، والأهداف من عقد الارتباط. الفجوة هي '
                  'المسافة إلى الهدف؛ الحركة المقترحة تقلبها.', '']
    else:
        lines += ['# Sustainability dashboard', '',
                  '> Six measurable properties. Values come from deterministic facts; targets from the engagement '
                  'contract. The gap is the distance to the target; a proposed move closes it.', '']
    lines += ['## ' + ('المؤشرات' if ar else 'Indicators'), '']
    lines += ['| ' + ('المؤشر' if ar else 'Indicator') + ' | ' + ('القيمة' if ar else 'Current')
              + ' | ' + ('الهدف' if ar else 'Target') + ' | ' + ('الفجوة' if ar else 'Gap') + ' |']
    lines += ['| --- | --- | --- | --- |']
    name_ar = {'single_source': 'P1 تعريف واحد', 'minimal_path': 'P2 مسار أدنى',
                'data_owners': 'P3 مالك واحد للبيانات', 'honest_boundaries': 'P4 حدود صادقة',
                'verifiable_paths': 'P5 قابلية التحقق', 'understandable_units': 'P6 قابلية الفهم'}
    name_en = {'single_source': 'P1 Single source', 'minimal_path': 'P2 Minimal path',
                'data_owners': 'P3 Single owner per field', 'honest_boundaries': 'P4 Honest boundaries',
                'verifiable_paths': 'P5 Verifiable paths', 'understandable_units': 'P6 Understandable units'}
    for row in dashboard['rows']:
        label = (name_ar.get(row['indicator']) if ar else name_en.get(row['indicator']))
        shown = row['value'] if row['measured'] else ('لم يُقَس' if ar else 'not measured')
        gap = row['gap'] if row['measured'] else '—'
        lines += [f"| {label} | {shown} | {row['target']} | {gap} |"]
    lines += ['', '## ' + ('الحركات المقترحة' if ar else 'Proposed moves'), '']
    if not moves:
        lines += [('لا حركات مطلوبة؛ الفجوات صفر.' if ar else 'No moves required; every gap is zero.')]
    else:
        # The document shows the moves a reader can act on today; sustainability.json holds them all.
        # Printing 60 moves produced a 664-line document nobody reads and the contract never checked.
        for index, move in enumerate(moves[:SHOWN_MOVES], start=1):
            lines += [f"### Move {index}: {move['move']}",
                       f"- " + ('مؤشر' if ar else 'indicator') + f": {move['indicator']}"]
            if 'rule' in move:
                lines += [f"- cluster: {move['rule'][:16]}"]
                lines += ["- " + ('المواضع' if ar else 'sites') + ":"]
                for occ in move['occurrences']:
                    lines += [f"  - {occ['path']}:{occ['line']} {occ['symbol']}"]
            if 'kind' in move:
                lines += [f"- kind: {move['kind']}",
                           "- " + ('المواضع' if ar else 'sites') + ":"]
                for site in move['sites']:
                    lines += [f"  - {site['path']}:{site['line']} {site['symbol']} ({site['callee']})"]
            if 'predicted' in move:
                for k, v in move['predicted'].items():
                    lines += [f"- predicted {k}: {v}"]
            if 'falsifier' in move:
                lines += ["- " + ('ناقض' if ar else 'falsifier') + f": {move['falsifier']}"]
            lines += ['']
        if len(moves) > SHOWN_MOVES:
            lines += [(f'عُرضت {SHOWN_MOVES} حركة من {len(moves)}؛ البقية في `sustainability.json`.' if ar else
                       f'Showing {SHOWN_MOVES} of {len(moves)} moves; the rest are in `sustainability.json`.'), '']
    lines += ['## ' + ('التفاصيل' if ar else 'Details'), '']
    # The measured detail behind each indicator is a record, not prose: R8 forbids dumping it here.
    lines += [('قياس كل مؤشر بالكامل — المدخلات والعتبات والمواضع — في `sustainability.json`.' if ar else
               'The full measurement behind every indicator — inputs, thresholds and sites — is in '
               '`sustainability.json`.'), '']
    for row in dashboard['rows']:
        label = (name_ar.get(row['indicator']) if ar else name_en.get(row['indicator']))
        detail = row['details']
        summary = ', '.join(f'{key}={value}' for key, value in sorted(detail.items())
                            if isinstance(value, (int, float, str, bool)) and key != 'note')
        lines += [f"- **{label}** — {summary or ('لا تفاصيل' if ar else 'no detail')}"]
    lines += ['', '## ' + ('الحدود' if ar else 'Limits'), '']
    for line in LIMITATIONS: lines += [f"- {line}"]
    (Path(out) / 'SUSTAINABILITY.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    record = {'schema_version': 1, 'rows': dashboard['rows'], 'indicators': dashboard['indicators'],
              'targets': dashboard['targets'], 'moves': moves, 'shown_in_document': min(SHOWN_MOVES, len(moves)),
              'interpretation': dashboard['interpretation'], 'limitations': LIMITATIONS}
    (Path(out) / 'sustainability.json').write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'rows': dashboard['rows'], 'moves': moves,
            'artifact': str(Path(out) / 'SUSTAINABILITY.md'), 'record': str(Path(out) / 'sustainability.json')}
