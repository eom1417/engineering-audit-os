"""What the person selected, as cards, and what running it would do (docs/studio-actions.json `selection`, `preview`).

The cards come from the Studio data of the latest check (`studio/cards.json`, and `gaps.json` and `operations.json` for
those groups): the same data the page showed, so the preview names what the person saw. Only open cards run.
"""
import json
from pathlib import Path

BATCH = 10                                  # fix_start's default batch size
OPEN = ('open',)
GROUPS = {'area': 'category', 'severity': 'severity'}


class SelectionError(ValueError):
    pass


def _load(folder, name):
    try: return json.loads((Path(folder) / f'{name}.json').read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError): return None


def studio_folder(project):
    """The Studio data of the project's latest check, or None before the first check."""
    from ... import guided
    state = guided.load(Path(project).resolve())
    if not state: return None
    try: folder = guided.report_of(state) / 'studio'
    except Exception: return None
    return folder if folder.is_dir() else None


def resolve(selection, folder):
    """(cards to run, cards left out with why): every card the selection names, in the order of cards.json."""
    if not isinstance(selection, dict) or selection.get('kind') not in ('card', 'cards', 'group', 'step'):
        raise SelectionError('the selection must say its kind: card, cards, group or step')
    data = _load(folder, 'cards') if folder else None
    if not data: raise SelectionError('this project has no check yet: run the check first (audit)')
    cards = data.get('cards') or []
    by_id = {card['id']: card for card in cards}
    kind = selection['kind']
    if kind in ('card', 'cards'):
        ids = [str(i) for i in selection.get('cards') or []]
        if kind == 'card': ids = ids[:1]
        if len(ids) > 500: raise SelectionError('at most 500 cards at once')
        unknown = [i for i in ids if i not in by_id]
        if unknown: raise SelectionError(f"no card named {', '.join(unknown[:5])} in the latest check")
        wanted = set(ids)
    elif kind == 'step':
        step = str(selection.get('step') or '')
        wanted = {card['id'] for card in cards if str(card.get('milestone') or '') == step}
    else:
        group = selection.get('group') or {}
        by, value = group.get('by'), str(group.get('value') or '')
        if by in GROUPS:
            wanted = {card['id'] for card in cards if str(card.get(GROUPS[by]) or '') == value}
        elif by in ('component', 'gap'):
            gaps = (_load(folder, 'gaps') or {}).get('gaps')
            if gaps is None: raise SelectionError('this check did not write the gap register (gaps.json) yet')
            wanted = {c for gap in gaps if str(gap.get('component' if by == 'component' else 'id')) == value for c in gap.get('cards') or []}
        elif by == 'operation':
            operations = (_load(folder, 'operations') or {}).get('operations')
            if operations is None: raise SelectionError('this check did not write the operations (operations.json) yet')
            wanted = {c for op in operations if str(op.get('id')) == value for c in op.get('cards') or []}
        else:
            raise SelectionError('a group is by area, severity, component, gap or operation')
    chosen = [card for card in cards if card['id'] in wanted]
    if not chosen: raise SelectionError('the selection names no card')
    run = [card for card in chosen if card.get('state', 'open') in OPEN]
    left = [{'id': card['id'], 'why': f"already {card.get('state')}"} for card in chosen if card not in run]
    if not run: raise SelectionError('every selected card is already handled: ' + ', '.join(f"{c['id']} ({c['why']})" for c in left[:5]))
    return run, left


def _paths(card):
    return [str(p) for p in card.get('paths') or [] if p] or ([str(card['place'])] if card.get('place') else [])


def estimate(verb, count, past):
    """(low, high, basis) in minutes. From the person's own past runs of this verb when there are three or more; else a
    rough rule, said as such."""
    rates = sorted(minutes / max(cards, 1) for minutes, cards in past if minutes and cards)
    if len(rates) >= 3:
        middle = rates[len(rates) // 2]
        low, high = max(1, round(middle * count * 0.7)), max(2, round(middle * count * 1.5 + 1))
        return low, high, {'en': f'from your last {len(rates)} runs of this kind', 'ar': f'من آخر {len(rates)} تشغيلات من هذا النوع'}
    if verb == 'fix':
        low, high = 5 + 3 * count, 15 + 8 * count
        return low, high, {'en': 'a rough rule: about 3 to 8 minutes a card, plus preparing the safe copy; it improves with your runs',
                           'ar': 'تقدير تقريبي: من 3 إلى 8 دقائق للبطاقة، مع تجهيز النسخة الآمنة؛ يتحسن مع تشغيلاتك'}
    low, high = 1, max(2, 1 + count)
    return low, high, {'en': 'a rough rule: under a minute or two a card; nothing in the project changes',
                       'ar': 'تقدير تقريبي: دقيقة أو دقيقتان للبطاقة؛ لا يتغير شيء في المشروع'}


def risk(verb, cards, files):
    if verb != 'fix':
        return {'level': 'low', 'why': {'en': 'It only reads: nothing in the project changes.', 'ar': 'قراءة فقط: لا يتغير شيء في المشروع.'}}
    hard = [card for card in cards if not card.get('fixable', True) or card.get('needs_decision')]
    severe = [card for card in cards if card.get('severity') in ('critical', 'high')]
    if hard or len(files) > 20:
        return {'level': 'high', 'why': {'en': f'{len(hard)} card(s) need judgement or a decision, and {len(files)} file(s) are touched; '
                                               'each change is still checked, and your branch is not touched.',
                                         'ar': f'{len(hard)} بطاقة تحتاج حكمًا أو قرارًا، و{len(files)} ملفًا ستُمس؛ كل تغيير يُفحص، وفرعك لا يُلمس.'}}
    if severe or len(files) > 5:
        return {'level': 'medium', 'why': {'en': f'{len(severe)} important card(s), {len(files)} file(s); every change is checked in a copy first.',
                                           'ar': f'{len(severe)} بطاقة مهمة و{len(files)} ملفًا؛ كل تغيير يُفحص في نسخة أولًا.'}}
    return {'level': 'low', 'why': {'en': 'Few files, and every change is checked in a copy first.', 'ar': 'ملفات قليلة، وكل تغيير يُفحص في نسخة أولًا.'}}


ON_FAILURE = {
    'fix': {'en': 'A change that fails its checks is taken back with the reason. Nothing reaches your branch; at the end you choose to take '
                  'the new branch or throw it away.',
            'ar': 'التغيير الذي يفشل في الفحص يُرجَع مع السبب. لا يصل شيء إلى فرعك؛ وفي النهاية أنت تختار تعتمد الفرع الجديد أو ترميه.'},
    'read': {'en': 'Nothing changes. If the assistant stops, the run says why and you can try again.',
             'ar': 'لا يتغير شيء. إن توقف المساعد يقول التشغيل السبب وتقدر تعيد.'},
}


def preview_of(verb, cards, left, past):
    files = sorted({path for card in cards for path in _paths(card)})
    low, high, basis = estimate(verb, len(cards), past)
    batches = [{'number': index + 1, 'cards': [card['id'] for card in cards[at:at + BATCH]]}
               for index, at in enumerate(range(0, len(cards), BATCH))] if verb == 'fix' else []
    return {'cards': [{'id': card['id'], 'title': card.get('title'), 'severity': card.get('severity'), 'paths': _paths(card)} for card in cards],
            'left_out': left, 'files': files, 'batches': batches,
            'estimate': {'minutes_low': low, 'minutes_high': high, 'basis': basis},
            'risk': risk(verb, cards, files), 'on_failure': ON_FAILURE['fix' if verb == 'fix' else 'read']}


def decision_scope(folder, question):
    from .store import decision_scope as scope
    return scope(folder, question)
