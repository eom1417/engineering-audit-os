"""The one-page executive summary: state, biggest risks, investment, what-if-nothing.

Reads the dossier's claim ledger and task cards, the sustainability dashboard and the transform
plan; renders a single Markdown page that fits in a meeting. The page never invents metrics;
every number traces back to a fact or a declared target.

The risks are the ledger's own top-ranked live claims, in the ledger's own order. This page used
to build itself from the duplication moves alone, and on a project where duplication detection
finds nothing it told the sponsor "READY, no necessary moves" over a report holding 43 confirmed
claims and 254 task cards. A summary that can contradict the report beneath it is worse than no
summary.
"""
from pathlib import Path
import json
from .facts.store import read_set
from .compose.labels import falsifier_of, impact_of, statement_of
from .sustainability import compute as dashboard
from .transform_plan import build as plan

RANK = {'CONFIRMED': 0, 'LIKELY': 1, 'HYPOTHESIS': 2, 'REFUTED': 3}
# A claim type that carries a consequence a sponsor has to weigh.
DECIDABLE = {'risk', 'cause', 'structure'}


NAME = 'executive'
VERSION = '1'
LIMITATIONS = [
    'The executive page is a single screen; it cites the underlying artifacts, not their detail.',
    'Risks are the claim ledger\'s top-ranked live claims, in the ledger\'s own order; where the '
    'ledger is empty the page falls back to the largest duplication moves and says so.',
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
    dossier_path = out / 'dossier.json'
    dossier = {}
    if dossier_path.is_file():
        try: dossier = json.loads(dossier_path.read_text(encoding='utf-8'))
        except ValueError: dossier = {}
    live = [claim for claim in dossier.get('claims', [])
            if claim.get('status') != 'closed' and claim.get('confidence') != 'REFUTED']
    ranked_claims = sorted(live, key=lambda c: (-c.get('priority', 0),
                                                RANK.get(c['confidence'], 9), c['id']))
    decidable = [c for c in ranked_claims
                 if c.get('claim_type') in DECIDABLE or (c.get('impact') or {}).get('scenario')]
    cards = dossier.get('tasks') or []
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
    # READY has to mean the whole report found nothing to decide, not that one detector was quiet.
    outstanding = len(dash['moves']) + len(decidable) + len(cards)
    if not outstanding:
        status = 'READY · لا حركات ضرورية' if ar else 'READY · nothing outstanding'
    else:
        parts = []
        if decidable: parts.append(f"{len(decidable)} " + ('ادعاء حي' if ar else 'live claims'))
        if cards: parts.append(f"{len(cards)} " + ('بطاقة مهمة' if ar else 'task cards'))
        if dash['moves']: parts.append(f"{len(dash['moves'])} " + ('حركة مقترحة' if ar else 'proposed moves'))
        status = 'REVIEW_REQUIRED · ' + (' · '.join(parts))
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
    if decidable:
        for index, claim in enumerate(decidable[:3], start=1):
            # The ledger stores one statement; the reader asked for one language. `statement_of`
            # and `impact_of` are the same renderers the decision brief uses, so the two documents
            # cannot describe the same claim in different words.
            lines += [f"{index}. **{claim['id']}** ({claim['confidence']}) — "
                      + _shorten(statement_of(claim, language), 180)]
            impact = impact_of(claim, language)
            if impact:
                lines += ['   - ' + ('الأثر' if ar else 'impact') + ': ' + _shorten(impact, 160)]
            if claim.get('falsifier'):
                lines += ['   - ' + ('ما ينقضه' if ar else 'falsifier') + ': '
                          + _shorten(falsifier_of(claim, language), 160)]
            lines += ['   - ' + ('التفصيل' if ar else 'detail') + ': DECISION-BRIEF.md']
    elif sorted_moves:
        lines += [('لا ادعاء حي في السجل؛ أكبر ما وُجد هو تكرار بنيوي.' if ar else
                   'The ledger holds no live claim; the largest finding is structural duplication.')]
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
    else:
        lines += [('لا ادعاء حي ولا حركة مقترحة. هذا ليس شهادة سلامة: اقرأ RUN.md لتعرف ما لم يُفحص.'
                   if ar else
                   'No live claim and no proposed move. That is not a clean bill of health: read '
                   'RUN.md for what this run did not examine.')]
    lines += ['', '## ' + ('الاستثمار' if ar else 'Investment')]
    stages = plan_result['stages']
    canonicalize = sum(1 for s in stages if s['move'] == 'canonicalize')
    eliminate = sum(1 for s in stages if s['move'] == 'eliminate_redundancy')
    lines += [f"- {len(cards)} " + ('بطاقة مهمة في الخطة' if ar else 'task cards in the plan')
              + f" · {len(stages)} " + ('مرحلة تحويل' if ar else 'transform stages')]
    lines += [f"- {canonicalize} " + ('للتجميع' if ar else 'canonicalize') + ', '
               f"{eliminate} " + ('لإزالة التكرار' if ar else 'eliminate_redundancy')]
    lines += ['', '## ' + ('ماذا لو لم نفعل' if ar else 'What if we do nothing')]
    lines += [('تبقى كل الفجوات في المؤشرات الستة كما هي، و' if ar else 'Every indicator gap stays as-is, and ')
               + f"{len(decidable)} " + ('ادعاء حي و' if ar else 'live claims and ')
               + f"{len(sorted_moves)} "
               + ('حركة معلّقة تنتظر قرارًا. لا شيء يتغير تلقائيًا.'
                   if ar else 'pending moves wait for a decision. Nothing changes automatically.')]
    lines += ['', '## ' + ('الحدود' if ar else 'Limits')]
    for limit in LIMITATIONS: lines += [f"- {limit}"]
    Path(out, 'EXECUTIVE.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return {'artifact': str(Path(out, 'EXECUTIVE.md')),
            'indicators': {row['indicator']: row['value'] for row in dash['rows']},
            'moves': len(dash['moves']), 'stages': len(stages),
            'live_claims': len(decidable), 'cards': len(cards),
            'limits': ' '.join(LIMITATIONS)}


def _shorten(text, limit):
    """Cut on a word boundary; a decision page should not end a sentence mid-word."""
    text = ' '.join(str(text).split())
    if len(text) <= limit: return text
    cut = text[:limit]
    space = cut.rfind(' ')
    return (cut[:space] if space > limit * 0.6 else cut).rstrip(' ,،') + '…'
