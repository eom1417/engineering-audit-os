"""The cards of a feature being added (eaos/journeys/extend.py) a later check keeps: its plan is drawn again from the code,
so the cards not built yet come back into it."""
from pathlib import Path

from ..core.ledger import key, walk
from ..core.workspace import read, write


def _milestones(kept, ids):
    """The kept milestones that hold a carried card, each listing only its carried cards."""
    return [{**m, 'tasks': [t for t in m['tasks'] if t in ids]} for m in kept['milestones'] if ids & set(m['tasks'])]


def carry(target, out):
    """The extension cards a new check's plan lost and the project does not hold yet (no commit carries their key):
    back in plan.json, each in its milestone. The number of cards carried."""
    try: kept = read(Path(out).parent / 'extend' / 'cards.json')   # beside the report: eaos/journeys/extend.py folder
    except (OSError, ValueError): return 0
    if not kept: return 0
    plan = read(Path(out) / 'plan.json')
    built, have = walk(target, 'HEAD')[0], {t['id'] for t in plan['tasks']}
    cards = [c for c in kept['tasks'] if c['id'] not in have and key(c) not in built]
    if not cards: return 0
    plan['tasks'] += cards
    plan['milestones'] = (plan.get('milestones') or []) + _milestones(kept, {c['id'] for c in cards})
    write(Path(out) / 'plan.json', plan)
    return len(cards)
