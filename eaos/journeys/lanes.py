"""A batch fixed by several assistants at once: the speed mode of a fix.

Most of a card's time is its assistant's thinking (a minute and a half a card, against seconds for EAOS to check the
change), so a batch's cards are dealt into lanes (deal), each fixed by its own assistant at the same time, in the batch's
one copy and on its one branch. The cards that share a file, or that one waits for, go in one lane: no two assistants
change one file. Lane 0 is the assistant that opened the batch; the Studio starts one beside it for each other lane
(eaos/interfaces/studio/helpers.py). EAOS checks their changes one at a time (eaos/journeys/agent_tools.py _start), so each change
is checked, kept or taken back alone, as it is with one assistant.

A lane holds the files its cards name, and every file it changes. A change to a file another lane holds is not tried:
its card waits for the end (`later`), when the first assistant fixes it, every other lane done. A lane is done when
each of its cards was kept, left out or left for the end, or once its assistant stopped for good (release): what it
had not tried goes to the end too. fix_finish hands the batch over once every lane is done (waiting).

    wave['lanes']    [[card, ...], ...]   lane 0 first      wave['claims']   {path: lane}
    wave['helpers']  {run: lane}                            wave['later']    [card, ...]
    wave['released'] [lane, ...]
"""
import fcntl
import os
import time
from contextlib import contextmanager
from pathlib import PurePosixPath

from . import guided
from ..core.places import workspace
from ..core import project_state

WAIT = 50                     # seconds fix_finish waits for the other lanes before it answers that they still work


def deal(cards, most):
    """The ids of `cards` (plan tasks, in the batch's order) in at most `most` lanes, the largest first: the cards that
    name a file in common, or that one waits for, together; each lane in the batch's order."""
    group = {card['id']: card['id'] for card in cards}

    def root(card):
        while group[card] != card: card = group[card]
        return card
    holder = {}
    for card in cards:
        linked = [holder.setdefault(path, card['id']) for path in card.get('paths') or []]
        linked += [ref.get('task_id') for ref in card.get('prerequisites') or [] if ref.get('task_id') in group]
        for other in linked: group[root(other)] = root(card['id'])
    together = {}
    for card in cards: together.setdefault(root(card['id']), []).append(card['id'])
    lanes = [[] for _ in range(max(1, min(int(most), len(together))))]
    for members in sorted(together.values(), key=len, reverse=True): min(lanes, key=len).extend(members)
    order = [card['id'] for card in cards]
    return [sorted(lane, key=order.index) for lane in lanes if lane]


def open_lanes(wave, cards, assistants):
    """Deal the cards of `wave` left to an assistant (`cards`: {id: plan task}) into lanes when more than one assistant
    fixes it (`assistants`, as the Studio's speed mode asks: one anywhere else, where nobody starts the others); the
    lanes past the first, which the Studio gives to the assistants it starts."""
    most = int(assistants or 1) if os.environ.get('EAOS_STUDIO_RUN') else 1
    lanes = deal([cards[card] for card in untried(wave, wave['cards'])], most) if most > 1 else []
    if len(lanes) < 2: return []
    wave.update(lanes=lanes, claims={path: lane for lane, ids in enumerate(lanes) for card in ids for path in cards[card].get('paths') or []},
                helpers={}, later=[], released=[])
    return lanes[1:]


def told(helpers):
    """What fix_start adds to its answer when other assistants fix lanes of the batch beside the first one."""
    if not helpers: return {}
    return {'helpers': helpers,
            'what_now': f'{len(helpers)} more assistants fix the other cards of this batch at the same time, each its own '
                        'files: fix only the cards in to_do (finding, fix_read, then fix_edit), then call fix_finish, which waits '
                        'for them and gives you any card left for the end. Keep every feature, route and behaviour.'}


def mine(wave, cards):
    """Of `cards`, those of the assistant asking: its lane's (the first assistant's: lane 0's and those left for the end)."""
    lane = helper(wave)
    return [card for card in cards if lane_of(wave, card) == (lane or 0)]


def lane_of(wave, card):
    """The lane fixing `card`: 0 for the first assistant, a card left for the end, or a batch of one lane."""
    if card in (wave.get('later') or []): return 0
    return next((lane for lane, ids in enumerate(wave.get('lanes') or []) if card in ids), 0)


def helper(wave):
    """The lane of the assistant asking when the Studio started it beside the first one, else None."""
    return (wave.get('helpers') or {}).get(os.environ.get('EAOS_STUDIO_RUN') or '')


def held(wave, card, files):
    """The files of `files` another lane holds while it still has cards to try, for a change to `card`: the card is then
    left for the end. Else none, and the lane of `card` holds them from now on."""
    lane, claims = lane_of(wave, card), wave.get('claims')
    if claims is None: return []
    busy = {other for other, ids in enumerate(wave['lanes']) if other != lane and (other == 0 or untried(wave, ids))} - set(wave['released'])
    taken = sorted(path for path in files if claims.get(path) in busy)
    if taken: wave['later'] = list(dict.fromkeys(wave['later'] + [card]))
    else: claims.update(dict.fromkeys(files, lane))
    return taken


def take(project, card, edits):
    """None when the change `edits` to `card` may be tried, its files held by its lane from now on; else the answer that
    the card waits for the end, another lane holding one of its files."""
    if not ((project_state.load(project) or {}).get('open_wave') or {}).get('lanes'): return None
    with changing(project) as state:
        taken = held(state['open_wave'], card, [PurePosixPath(str(edit.get('path'))).as_posix() for edit in edits if isinstance(edit, dict)])
    return {'card': card, 'kept': False, 'later': True, 'why': f"another assistant of this batch is changing {', '.join(taken)}",
            'what_now': 'Nothing changed. Leave this card for now and go on with the next one: it is fixed at the end, once the '
                        'other assistants are done (fix_finish gives it to the first assistant).'} if taken else None


def not_yours(state):
    """Why an assistant the Studio started for a lane may not hand the batch over or close it; None for the first one."""
    if helper((state or {}).get('open_wave') or {}) is None: return None
    return {'status': 'not_yours', 'what_now': 'The first assistant of this batch hands it over. Once each of your cards is '
                                               'kept, skipped or left for the end, tell the person what you fixed and end your turn.'}


def next_step(wave, left):
    """What an assistant does once a card of its own is kept: the next one, else hand the batch over, or end its turn
    when it fixes a lane beside the first assistant."""
    if left: return 'Next card with fix_edit.'
    if helper(wave) is not None: return 'Every card of yours is done: tell the person what you fixed and end your turn.'
    return 'Every card is done: call fix_finish.'


def release(wave, lane):
    """A lane whose assistant stopped for good: the cards it had not tried go to the end, its files are free."""
    if lane in (wave.get('released') or []) or not wave.get('lanes'): return
    wave['released'] = (wave.get('released') or []) + [lane]
    wave['later'] = list(dict.fromkeys((wave.get('later') or []) + untried(wave, wave['lanes'][lane])))


def waiting(wave):
    """The cards the other lanes still have to try: the batch is handed over once there are none."""
    released = set(wave.get('released') or [])
    return [card for lane, ids in enumerate(wave.get('lanes') or []) if lane and lane not in released for card in untried(wave, ids)]


def untried(wave, cards):
    """Of `cards`, those neither kept nor left out, nor left for the end."""
    tried = {**(wave.get('kept') or {}), **(wave.get('failed') or {})}
    return [card for card in cards if card not in tried and card not in (wave.get('later') or [])]


def finish_wait(project):
    """None when no other lane has a card left; else, once they are done or after WAIT seconds (an assistant's call of
    a tool has a time limit), what the first assistant does now."""
    until = time.monotonic() + WAIT
    if not (left := waiting((project_state.load(project) or {}).get('open_wave') or {})): return None
    while left and time.monotonic() < until:
        time.sleep(2)
        left = waiting((project_state.load(project) or {}).get('open_wave') or {})
    if not left: return {'status': 'others_done', 'what_now': 'The other assistants of this batch are done: call fix_finish again now.'}
    return {'status': 'others_fixing', 'cards': left,
            'what_now': 'The other assistants of this batch are still fixing these cards: call fix_finish again, it waits for them.'}


@contextmanager
def changing(project):
    """The project's state, loaded under its lock and saved when the block ends: what the lanes write, at once, never
    loses what another wrote."""
    with open(workspace(project) / 'state.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = project_state.load(project)
        yield state
        guided.save(state)
