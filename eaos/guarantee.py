"""Compare a recorded structural prediction with comparable observed snapshots."""
from collections import Counter
from pathlib import Path
import json
import math
from .snapshots import snapshot
from .sustainability import compute as dashboard

LIMITATIONS = [
    'Compares structural indicator deltas only, not runtime behaviour or repair acceptance.',
    'A matching prediction is not proof that a proposed change should be made.',
    'Absent predictions, changed scope or extractor versions cannot produce a guarantee.',
]


def predict(out, stage, destination):
    from .simulator import simulate
    result = simulate(out, stage)
    record = {'schema_version': 1, 'stage': stage, 'before_snapshot': snapshot(out),
              'prediction': result, 'method': 'structural_simulator_v1'}
    Path(destination).write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    return record


def compare(previous, current, tolerance=0.05, language='ar', prediction=None):
    previous, current = Path(previous), Path(current)
    if not math.isfinite(tolerance) or tolerance < 0: raise ValueError('Tolerance must be finite and nonnegative')
    rows, reasons = [], []
    record = json.loads(Path(prediction).read_text()) if prediction else None
    if record is None:
        reasons.append('No recorded prediction was supplied.')
    elif record.get('schema_version') != 1 or not record.get('stage'):
        reasons.append('Prediction contract or stage is missing.')
    else:
        before_snapshot, after_snapshot = snapshot(previous), snapshot(current)
        if record.get('before_snapshot') != before_snapshot:
            reasons.append('Prediction belongs to a different source snapshot.')
        if any(before_snapshot[key] != after_snapshot[key] for key in ('scope', 'exclude', 'extractors')):
            reasons.append('Scope or extractor configuration changed; snapshots are not comparable.')
        if not reasons:
            before = {row['indicator']: row for row in dashboard(previous)['rows']}
            after = {row['indicator']: row for row in dashboard(current)['rows']}
            deltas = record.get('prediction', {}).get('delta', {})
            if not deltas: reasons.append('Recorded prediction contains no indicator deltas.')
            for name, predicted in deltas.items():
                a, b = before.get(name, {}), after.get(name, {})
                if (not a.get('measured', True) or not b.get('measured', True)
                        or a.get('value') is None or b.get('value') is None
                        or type(predicted) not in (int, float) or not math.isfinite(predicted)):
                    reasons.append('Indicator cannot be compared: ' + name); continue
                observed = round(b['value'] - a['value'], 4)
                difference = round(predicted - observed, 4)
                verdict = 'HONEST' if abs(difference) <= tolerance else 'OVERSTATED' if predicted < observed else 'UNDERSTATED'
                rows.append({'indicator': name, 'predicted': predicted, 'observed': observed,
                             'difference': difference, 'verdict': verdict, 'tolerance': tolerance})
    status = 'UNAVAILABLE' if reasons else 'COMPARED'
    result = {'status': status, 'rows': rows, 'summary': dict(Counter(row['verdict'] for row in rows)),
              'reasons': reasons, 'prediction': str(prediction) if prediction else None,
              'artifact': str(current / 'GUARANTEE.md'), 'limits': ' '.join(LIMITATIONS)}
    title = 'مقارنة التوقع البنيوي' if language == 'ar' else 'Verification guarantee'
    lines = ['# ' + title, '', '> ' + status, '', *['- ' + reason for reason in reasons], '',
             '| Indicator | Predicted | Observed | Verdict |', '| --- | --- | --- | --- |']
    lines += [f"| {row['indicator']} | {row['predicted']} | {row['observed']} | {row['verdict']} |" for row in rows]
    lines += ['', result['limits']]
    current.mkdir(parents=True, exist_ok=True)
    (current / 'GUARANTEE.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (current / 'guarantee.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result
