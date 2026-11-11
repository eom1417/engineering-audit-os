"""studio/cards.json: every card of the check with its area, severity, place, evidence, state and why it matters, in the
check's language (the cards the fix verbs, the problems filter and the AI nodes select from)."""
from ....plan.analysis.cards import title_of
from .....kernel.contracts.card_areas import classify
from .....kernel.language.words import impact_of
from .evidence import rel

LANGUAGES_SHOWN = ('ar', 'en')     # a card's `why` is written in both languages
SEVERITY_OF_CONFIDENCE = {'CONFIRMED': 1.0, 'LIKELY': 0.7, 'HYPOTHESIS': 0.4}


def cards(m, claims, lang, task_cards):
    """The body of cards.json: one row per card of `task_cards` (model.task_cards), with its plan task and claim."""
    rows = {r['id']: r for r in m['rows']}
    plan = {t.get('id'): t for t in m['plan'].get('tasks') or [] if isinstance(t, dict)}
    tasks = [(card, plan.get(card['id']) or {}) for card in task_cards]
    return [_card(card, rows.get(card['id']) or {}, task, claims.get(task.get('claim_id')) or {}, lang) for card,
            task in tasks]


def _needs_decision(task, card):
    """The person's to decide (or, in a plan whose cards are not resolved, an investigation), or a card a batch could
    not fix."""
    owner = task['resolution']['resolution'] == 'owner' if task.get('resolution') else task.get('kind') == 'investigate'
    return owner or card['state'] == 'skipped'


def _card(card, row, task, claim, lang):
    params = _params(claim, task)
    place = rel(params.get('place'))
    evidence = _fact_ids(task, claim)
    # in the check's language when the catalogue has words for it
    title = title_of(task, lang) if task.get('render') else card['title']
    return {'id': card['id'], 'key': card['key'], 'title': title, 'kind': card['pattern'],
            'category': row.get('area') or classify({'pattern': card['pattern']})[0], 'severity': card['severity'],
            'fixable': bool(row.get('auto')),
            'needs_decision': _needs_decision(task, card),
            **({'resolution': resolution_of(task['resolution'])} if task.get('resolution') else {}),
            'scope': 'group' if str(params.get('place') or '').startswith('group:') else 'place',
            'place': place, 'paths': [p for p in map(rel, card['paths']) if p], 'evidence': evidence,
            'state': card['state'], 'milestone': card.get('milestone'),
            'confidence': SEVERITY_OF_CONFIDENCE.get(row.get('confidence')), **why_of(task)}


def _params(claim, task):
    """The render parameters of a card's words: its claim's, else its task's."""
    return (claim.get('render') or task.get('render') or {}).get('params') or {}


def _fact_ids(task, claim):
    """The facts a card cites: its task's evidence, else its claim's."""
    return list((task.get('evidence') or {}).get('fact_ids') or claim.get('fact_ids') or [])


def resolution_of(row):
    """What the assistant decided for a card (eaos/features/plan/analysis/cards.py resolve): {kind: fix | owner, by, words,
    and the change of a fix or the question, options and recommendation of the person's choice; capped when it was the
    person's but turned into the assistant's recommendation}."""
    out = {'kind': row.get('resolution'), 'by': row.get('by') or 'assistant', 'words': row.get('words') or '',
           'why': row.get('why') or ''}
    if out['kind'] == 'fix': out.update(change=row.get('change') or '', capped=bool(row.get('capped')))
    if out['kind'] == 'owner': out.update(question=row.get('question') or '', options=list(row.get('options') or []),
                                          recommendation=row.get('recommendation') or '')
    return out


def why_of(task):
    """{'why': {ar, en}}: why the card matters, in both languages (the report's impact sentence, translated by its
    render key where the catalogue has it); nothing when the plan gives no impact."""
    if not task.get('impact') and not task.get('impact_render'): return {}
    claim = {'impact': {'scenario': task.get('impact') or ''}, 'render': task.get('impact_render')}
    words = {lang: impact_of(claim, lang) for lang in LANGUAGES_SHOWN}
    return {'why': words} if all(w and w != '—' for w in words.values()) else {}
