"""Progress over time: compare two snapshots and report the indicator deltas.

The progress view consumes two dossiers (previous, current) and reports, for
each of the six sustainability indicators, how the gap closed. A positive
direction reduces the indicator value when the target is 0; the report
labels the direction correctly per indicator.
"""
from pathlib import Path
from .facts.store import read_set
from .sustainability import compute as dashboard


NAME = 'progress'
VERSION = '1'
LIMITATIONS = [
    'A progress report compares the persisted fact sets; it cannot reason about facts the earlier '
    'snapshot did not record.',
    'A negative direction means the gap grew; the report labels it WORSENED, never hides it.',
    'The progress view never invents metrics the engagement did not state; it shows the six '
    'sustainability indicators only.',
]


# Indicators where lower is better. Everything that contributes to a gap.
_LOWER_IS_BETTER = {'single_source', 'minimal_path', 'honest_boundaries',
                    'understandable_units', 'data_owners', 'verifiable_paths'}


def render(previous, current, language='ar'):
    previous = Path(previous); current = Path(current)
    if not (previous / 'facts' / 'fingerprint.json').is_file():
        return None
    before = dashboard(previous); after = dashboard(current)
    ar = language == 'ar'
    rows = []
    for row_before, row_after in zip(before['rows'], after['rows']):
        before_value = row_before.get('value'); after_value = row_after.get('value')
        measured = row_after.get('measured', True)
        if not measured or before_value is None or after_value is None:
            rows.append({'indicator': row_after['indicator'],
                          'before': before_value, 'after': after_value,
                          'delta': None,
                          'direction': ('لم يُقَس' if ar else 'not measured'),
                          'measured': False})
            continue
        delta = round(after_value - before_value, 4)
        if delta == 0:
            direction = ('لم يتغير' if ar else 'unchanged')
        elif row_after['indicator'] in _LOWER_IS_BETTER:
            direction = ('تحسن' if delta < 0 else 'تراجع') if ar else ('improved' if delta < 0 else 'worsened')
        else:
            direction = ('تحسن' if delta > 0 else 'تراجع') if ar else ('improved' if delta > 0 else 'worsened')
        rows.append({'indicator': row_after['indicator'],
                      'before': before_value, 'after': after_value,
                      'delta': delta, 'direction': direction, 'measured': True})
    lines = []
    title = ('التقدم عبر الزمن' if ar else 'Progress over time')
    lines += [f'# {title}', '',
              ('> مقارنة بين جرعتين: ما كان وما صار. الأرقام من الحقائق الحتمية، الاتجاه من القاعدة المعلنة.'
                if ar else
                '> Two snapshots compared: what was and what is. Numbers come from the facts; direction comes from the declared rule.'), '']
    lines += ['| ' + ('مؤشر' if ar else 'Indicator') + ' | '
               + ('قبل' if ar else 'Before') + ' | '
               + ('بعد' if ar else 'After') + ' | '
               + ('الفرق' if ar else 'Delta') + ' | '
               + ('الاتجاه' if ar else 'Direction') + ' |']
    lines += ['| --- | --- | --- | --- | --- |']
    for row in rows:
        before_cell = row['before'] if row.get('measured', True) else ('—' if ar else '—')
        after_cell = row['after'] if row.get('measured', True) else ('—' if ar else '—')
        delta_cell = row['delta'] if row.get('measured', True) else ('—' if ar else '—')
        lines += [f"| {row['indicator']} | {before_cell} | {after_cell} | {delta_cell} | {row['direction']} |"]
    (current / 'PROGRESS.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return {'artifact': str(current / 'PROGRESS.md'), 'rows': rows,
            'limits': ' '.join(LIMITATIONS)}
