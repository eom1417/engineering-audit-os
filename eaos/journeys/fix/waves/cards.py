"""The cards a batch takes: the plan with each card's key, the ready ones in the plan's order, the prerequisites
of the cards asked for, and why some cannot open a batch yet."""
import json
from pathlib import Path

from ....core.project import ledger
from ....core.contracts.decisions import ready, waiting
from ....core.project.ledger import keys

SIZE = 10


def plan(report):
    """plan.json, each card with its key (eaos/core/project/ledger.py), which its commit carries."""
    data = json.loads((Path(report) / 'plan.json').read_text(encoding='utf-8'))
    ids = keys(data.get('tasks') or [])
    for card in data.get('tasks') or []: card['key'] = ids[card['id']]
    return data


def ready_cards(report, state=None):
    """The ready cards in the plan's order: milestone by milestone, and inside one, as the plan lists them; without a card
    the ledger holds other than open, nor one tried before (the state's `tried`, by key: a new check numbers the cards
    again) unless the ledger opened it again (ledger._reopen_waited), nor one waiting for a card not done yet
    (decisions.waiting) unless that card is taken before it: the split goes in the same batch, after its simplifications
    (a full-stack app: ten splits left for "the next batch" while their simplifications were open)."""
    if not (Path(report) / 'plan.json').is_file(): return []
    book, tried = _book(state), set((state or {}).get('tried') or ())
    cards = [card for card in _in_order(plan(report)) if ready(card) and _free(card['key'], book, tried)]
    return _after_their_waits(cards, ledger.done(book))


def _after_their_waits(cards, done):
    """`cards` in the plan's order, each once the cards it waits for are `done` or taken before it; the others left."""
    taken, ids = [], set()
    # each time the first card in the plan's order whose waits are done or taken: a split comes right after the last of them
    while card := next((c for c in cards if c['id'] not in ids and set(waiting(c, done)) <= ids), None):
        taken.append(card)
        ids.add(card['id'])
    return taken


def _free(key, book, tried):
    """Whether a batch may take the card: open in the ledger, and not tried before unless the ledger opened it again."""
    entry = book.get(key) or {'state': 'open'}
    return entry['state'] == 'open' and (key not in tried or bool(entry.get('reopened')))


def _in_order(data):
    """The plan's cards milestone by milestone, then the rest as listed."""
    by_id = {card['id']: card for card in data.get('tasks') or [] if card.get('id')}
    order = [card_id for milestone in data.get('milestones') or [] for card_id in milestone['tasks']]
    return [by_id[i] for i in dict.fromkeys(order + list(by_id)) if i in by_id]


def _book(state):
    """The ledger's cards by key; none before the project has one."""
    return ((ledger.load(state) if (state or {}).get('project') else None) or {}).get('cards') or {}


def with_prerequisites(report, state, chosen):
    """The cards asked for, each after the ready cards it waits for, added when not asked (ready_cards' rule)."""
    known, done = {c['id']: c for c in plan(report)['tasks']}, ledger.done(_book(state))
    free, out = {c['id'] for c in ready_cards(report, state)}, []
    def put(card_id):
        for needed in waiting(known[card_id], done) if card_id in known else []:
            if needed in free and needed not in out: put(needed)
        if card_id not in out: out.append(card_id)
    for card_id in chosen: put(card_id)
    return out


def too_early(state, cards):
    """Why the cards asked for cannot open a batch yet: some wait for cards neither done (decisions.waiting) nor taken
    before them in the batch; else None."""
    done = set(ledger.done(_book(state)))
    early = {}
    for card in cards:
        if wait := waiting(card, done): early[card['id']] = wait
        done.add(card['id'])
    if not early: return None
    return {'error': '; '.join(f'{c} waits for {", ".join(w)}' for c, w in list(early.items())[:5]) + ': no batch was opened',
            'waits': early, 'what_now': 'A card goes in a batch once the cards it waits for are done (a module is split after '
                                        'its complex functions are simplified): call fix_start again without these cards.'}


def next_batch(report, state, size=SIZE):
    return [card['id'] for card in ready_cards(report, state)[:size]]
