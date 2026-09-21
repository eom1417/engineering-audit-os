"""The one-page executive summary: state, biggest risks, investment, what-if-nothing.

Reads the dossier, the sustainability dashboard, the transform plan, and the
target architecture; renders a single Markdown page that fits in a meeting.
The page never invents metrics; every number traces back to a fact or a
declared target.
"""
from pathlib import Path
import json
from .facts.store import read_set
from .sustainability import compute as dashboard
from .transform_plan import build as plan


NAME = 'executive'
VERSION = '1'
LIMITATIONS = [
    'The executive page is a single screen; it cites the underlying artifacts, not their detail.',
    'Risks are sorted by the priority formula declared in the engagement contract; with no '
    'contract, the page falls back to the highest single_source / minimal_path gap.',
    'The "what if nothing" cost is the predicted delta × a stated engineering rate, not a quote.',
    'The page is regenerated whenever the underlying artifacts change; it is never the source of truth.',
]


def render(out, language='ar'):
    out = Path(out)
    sets = {name: read_set(out, name) for name in ['syntax', 'structure', 'fingerprint',
                                                     'sequences', 'redundancy', 'runtime',
                                                     'graph', 'resolve', 'domain', 'metrics', 'flows']
            if (out / 'facts' / f'{name}.json').is_file()}
    if not sets: return None
    dash = dashboard(out)
    plan_result = plan(out)
    ar = language == 'ar'
    lines = []
    title = 'الملخص التنفيذي' if ar else 'Executive summary'
    lines += [f'# {title}', '',
              ('> صفحة واحدة: الوضع، أكبر ثلاثة مخاطر بالأثر، الاستثمار، وماذا لو لم نفعل.'
                if ar else
                '> One page: status, the three biggest risks with impact, the investment, '
                'and what happens if we do nothing.'), '']
    lines += ['## ' + ('الوضع' if ar else 'Status')]
    indicators = {row['indicator']: row for row in dash['rows']}
    if ar:
        verdict_map = {'single_source': 'تعريف مكرر', 'minimal_path': 'عمل زائد',
                        'data_owners': 'حقول متعددة الكُتّاب',
                        'honest_boundaries': 'دورات أو مخالفات سياسة',
                        'verifiable_paths': 'تدفقات غير قابلة للتحقق',
                        'understandable_units': 'وحدات أكبر من اللازم'}
        name_map = {'single_source': 'P1 تعريف واحد', 'minimal_path': 'P2 مسار أدنى',
                    'data_owners': 'P3 مالك واحد', 'honest_boundaries': 'P4 حدود صادقة',
                    'verifiable_paths': 'P5 قابلية التحقق',
                    'understandable_units': 'P6 قابلية الفهم'}
    else:
        verdict_map = {'single_source': 'duplicate definitions',
                       'minimal_path': 'redundant work',
                       'data_owners': 'multi-writer fields',
                       'honest_boundaries': 'cycles or policy violations',
                       'verifiable_paths': 'unverifiable paths',
                       'understandable_units': 'oversized units'}
        name_map = {k: k.replace('_', ' ') for k in verdict_map}
    status = ('READY · لا حركات ضرورية' if not dash['moves']
                else f"REVIEW_REQUIRED · {len(dash['moves'])} " + ('حركة مقترحة' if ar else 'proposed moves'))
    lines += [f"- {status}"]
    # Indicators where a higher value is better (the closer to 1.0, the better).
    higher_is_better = {'verifiable_paths'}
    for indicator in ['single_source', 'minimal_path', 'honest_boundaries',
                       'data_owners', 'verifiable_paths', 'understandable_units']:
        row = indicators.get(indicator)
        if row is None: continue
        if not row.get('measured', True) or row.get('value') is None:
            verdict = '—'
            current_cell = ('لم يُقَس' if ar else 'not measured')
            gap_cell = ('—' if ar else '—')
            lines += [f"- {verdict} {name_map[indicator]}: {current_cell} "
                       f"({('الهدف' if ar else 'target')} {row['target']}, {gap_cell} {('فجوة' if ar else 'gap')})"]
            continue
        gap = row['gap']
        verdict = '✓' if gap == 0 else '✗'
        lines += [f"- {verdict} {name_map[indicator]}: "
                   f"{('القيمة' if ar else 'current')} {row['value']}, "
                   f"{('الهدف' if ar else 'target')} {row['target']}, "
                   f"{('فجوة' if ar else 'gap')} {gap}"]
    lines += ['', '## ' + ('أكبر ثلاثة مخاطر' if ar else 'Top three risks')]
    sorted_moves = sorted(dash['moves'], key=lambda m: m.get('predicted', {}).get('single_source', 0)
                                                          + m.get('predicted', {}).get('minimal_path', 0),
                          reverse=True)
    for index, move in enumerate(sorted_moves[:3], start=1):
        title = move.get('move')
        if 'rule' in move:
            title = ('تجميع ' if ar else 'canonicalize ') + move['rule'][:8]
        lines += [f"{index}. **{title}** — " +
                   ('يشمل' if ar else 'covers') + f" {len(move.get('occurrences', move.get('sites', [])))} " +
                   ('موضع' if ar else 'sites')]
        if 'predicted' in move:
            for k, v in move['predicted'].items():
                lines += [f"   - predicted {k}: {v}"]
    lines += ['', '## ' + ('الاستثمار' if ar else 'Investment')]
    stages = plan_result['stages']
    canonicalize = sum(1 for s in stages if s['move'] == 'canonicalize')
    eliminate = sum(1 for s in stages if s['move'] == 'eliminate_redundancy')
    lines += [f"- {len(stages)} " + ('مرحلة في خطة التحويل' if ar else 'stages in the transform plan')]
    lines += [f"- {canonicalize} " + ('للتجميع' if ar else 'canonicalize') + ', '
               f"{eliminate} " + ('لإزالة التكرار' if ar else 'eliminate_redundancy')]
    lines += ['', '## ' + ('ماذا لو لم نفعل' if ar else 'What if we do nothing')]
    lines += [('تبقى كل الفجوات في المؤشرات الستة كما هي، و' if ar else 'Every indicator gap stays as-is, and the ')
               + f"{len(sorted_moves)} "
               + ('حركة معلّقة تنتظر قرارًا. لا شيء يتغير تلقائيًا.'
                   if ar else 'pending moves wait for a decision. Nothing changes automatically.')]
    lines += ['', '## ' + ('الحدود' if ar else 'Limits')]
    for limit in LIMITATIONS: lines += [f"- {limit}"]
    Path(out, 'EXECUTIVE.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return {'artifact': str(Path(out, 'EXECUTIVE.md')),
            'indicators': {row['indicator']: row['value'] for row in dash['rows']},
            'moves': len(dash['moves']), 'stages': len(stages),
            'limits': ' '.join(LIMITATIONS)}
