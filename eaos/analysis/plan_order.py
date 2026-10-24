"""The plan's order (eaos/analysis/plan.py builds the cards and their waves): the plan orderer's steps when it ran in this
check and they hold, else the rules' waves; plan.json `order` and PLAN/STEPS.md.
"""
from pathlib import Path

from ..core.workspace import read, write
from .plan_documents import PLAN_DIR


def _load(path, default):
    try: return read(path)
    except (OSError, ValueError): return default


def _ordered(out, plan):
    """The plan orderer's steps of this check when they hold, with the cards it did not see after them in the rules'
    waves: every card of the plan once, none before its prerequisites; else None."""
    body = _load(Path(out) / 'nodes/plan_orderer/order.json', {})
    if (body.get('method'), body.get('source'), body.get('decision')) != ('model', 'model', 'reorder'): return None
    tasks = {t['id']: t for t in plan['tasks']}
    steps = [dict(step) for step in body.get('steps') or []]
    left = _unplaced(plan, steps)
    if left: steps.append({'id': 'not-placed', 'title': 'Not placed by the order', 'tasks': left,
                           'why': "The order did not place these cards; they follow in the rules' waves."})
    return {**body, 'steps': steps} if _holds(steps, tasks) else None


def _unplaced(plan, steps):
    """The cards of the rules' waves no step places, in their order."""
    seen = {task for step in steps for task in step.get('tasks') or []}
    return [task for wave in plan.get('waves') or [] for task in wave.get('tasks') or [] if task not in seen]


def _holds(steps, tasks):
    """Whether `steps` place every card of `tasks` ({id: task}) once, none before its prerequisites."""
    place = {}
    for index, step in enumerate(steps):
        for task in step.get('tasks') or []:
            if task not in tasks or task in place: return False
            place[task] = index
    return set(place) == set(tasks) and not any(place.get(ref.get('task_id'), -1) > place[task]
                                                for task in tasks for ref in tasks[task].get('prerequisites') or [])


SOURCE_WORDS = {'assistant': ("The assistant's order: every prerequisite kept, each step says why.",
                              'ترتيب المساعد: كل متطلب مسبق محفوظ، وكل خطوة تقول ليش.'),
                'rules': ("The rules' order: the waves of PLAN/WAVES.md.", 'ترتيب القواعد: موجات PLAN/WAVES.md.')}


def sequence(out, language='ar', ordered=False):
    """The plan's order: the plan orderer's steps when it ran in this check and its steps hold, else the rules' waves.
    Writes plan.json `order` ({source, steps, why}) and PLAN/STEPS.md; returns the order."""
    out = Path(out)
    plan = read(out / 'plan.json')
    body = _ordered(out, plan) if ordered else None
    source = 'assistant' if body else 'rules'
    steps = [{k: step.get(k) for k in ('id', 'title', 'tasks', 'why')} for step in (body or {}).get('steps') or []]
    plan['order'] = {'source': source, 'steps': steps, 'why': (body or {}).get('why') or SOURCE_WORDS[source][0]}
    write(out / 'plan.json', plan)
    (out / PLAN_DIR).mkdir(parents=True, exist_ok=True)
    (out / PLAN_DIR / 'STEPS.md').write_text(_steps_text(steps, source, language == 'ar'), encoding='utf-8')
    return plan['order']


def _steps_text(steps, source, ar):
    """PLAN/STEPS.md: who ordered the plan, then each step with why and its cards."""
    lines = ['# ' + ('خطوات الخطة' if ar else 'Plan steps'), '', SOURCE_WORDS[source][1 if ar else 0], '']
    for number, step in enumerate(steps, 1):
        lines += [f"## {number}. {step['title']}", '', step['why'] or '', '', ', '.join(f'`{t}`' for t in step['tasks']), '']
    return '\n'.join(lines)
