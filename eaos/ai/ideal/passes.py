"""The ideal's two passes (eaos/ai/ideal/planner.py plan): the plan pass asked in parts side by side (ideal_prompts.PARTS) and
joined into one draft, then the critique, whose changes are applied to the draft here, deterministically."""
import copy
from concurrent.futures import ThreadPoolExecutor

from .prompts import CRITIQUE_SCHEMA, IDEAL_SCHEMA, PARTS, part_schema, prompt_critique, prompt_plan
from ..nodes.framework import check_shape


def passes(launcher, data, done, tell):
    """(draft, reviewed ideal, critique): each answer held to its schema; each pass done is added to `done`."""
    name = getattr(launcher, 'assistant', None)
    tell(f'{name or "The assistant"} plans the ideal of every view, {len(PARTS)} parts side by side',
         f'{name or "المساعد"} يخطّط المثالي لكل عرض، {len(PARTS)} أجزاء معًا')
    draft = join(_parts(launcher, data))
    done.append('plan')
    check_shape(draft, IDEAL_SCHEMA, 'plan')
    tell('A second pass reviews the plan: what was missed, the risks, the order', 'تمرير ثانٍ يراجع الخطة: ما فات، والمخاطر، والترتيب')
    reviewed = launcher('critique', prompt_critique(data, draft), CRITIQUE_SCHEMA)
    done.append('critique')
    check_shape(reviewed, CRITIQUE_SCHEMA, 'review')
    return draft, apply(draft, reviewed['changes']), reviewed['critique']


def _parts(launcher, data):
    """Every part's answer, asked at once; the first error goes on once all have ended."""
    def ask(views):
        answer = launcher('plan-' + views[0], prompt_plan(data, views), part_schema(views))
        check_shape(answer, part_schema(views), 'plan')
        return answer
    with ThreadPoolExecutor(max_workers=len(PARTS), thread_name_prefix='eaos-ideal') as pool:
        return list(pool.map(ask, PARTS))


def join(parts):
    """One draft of the parts' answers: their views, the last part's aspects, every departure and question, and the
    parts' mean confidence."""
    confidences = [part['confidence'] for part in parts if isinstance(part.get('confidence'), (int, float))]
    return {'views': {name: view for part in parts for name, view in part['views'].items()},
            **{key: _every(parts, key) for key in ('aspects', 'departures', 'open_questions')},
            'confidence': round(sum(confidences) / len(confidences), 2) if confidences else 0.5}


def _every(parts, key):
    return [row for part in parts for row in part.get(key) or []]


def apply(draft, changes):
    """The draft with the critique's changes: elements put (replaced by id, or added) and removed, summaries and aspects
    replaced, departures and questions added, questions dropped, the confidence when it gives one."""
    ideal = copy.deepcopy(draft)
    _elements(ideal['views'], changes)
    judged = {row['aspect'] for row in changes['aspects']}
    ideal['aspects'] = [row for row in ideal['aspects'] if row['aspect'] not in judged] + changes['aspects']
    ideal['departures'] += changes['departures']
    dropped = set(changes['drop_questions'])
    ideal['open_questions'] = [q for q in ideal['open_questions'] if q.get('id') not in dropped] + changes['open_questions']
    if isinstance(changes.get('confidence'), (int, float)): ideal['confidence'] = changes['confidence']
    return ideal


def _elements(views, changes):
    """The views' elements removed and put, and their summaries replaced, as the critique says (a view not in the
    draft left out)."""
    for row in changes['remove']:
        if row['view'] in views: views[row['view']]['elements'] = [e for e in views[row['view']]['elements'] if e.get('id') != row['id']]
    for row in changes['put']:
        if row['view'] in views: _put(views[row['view']]['elements'], row['element'])
    for row in changes['summaries']:
        if row['view'] in views: views[row['view']]['summary'] = row['summary']


def _put(elements, element):
    """`element` in place of the one of its id, else added."""
    at = next((i for i, e in enumerate(elements) if e.get('id') == element['id']), None)
    if at is None: elements.append(element)
    else: elements[at] = element
