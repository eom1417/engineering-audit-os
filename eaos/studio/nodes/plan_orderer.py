"""The plan orderer: the order and grouping of the plan's steps, planned by the assistant (docs/STUDIO.md D11).

It reads the rules' plan (eaos/plan.py: milestones, waves and each card's prerequisites), what the card triage decided
(a rejected card is set aside, a doubtful one waits for its probe), the planned ideal's own order when there is one,
and the pipeline-gap planner's steps, then decides "reorder" (with its steps), "keep" or "ask". A planning node: a
critique pass reviews the draft. The check refuses an order that puts a card before one of its prerequisites, names a
card twice or names one the plan does not hold; a card the order leaves out is placed after it, in the rules' order.
The proposal is written to nodes/plan_orderer/order.json; the plan itself is never changed by it.
"""
import json
from pathlib import Path

from . import core
from .. import ideal

VERSION = '1'
LIMIT = {'tasks': 300}
_STEP = {'type': 'object', 'additionalProperties': False, 'required': ['id', 'title', 'tasks', 'why'],
         'properties': {'id': {'type': 'string'}, 'title': {'type': 'string'}, 'tasks': {'type': 'array', 'items': {'type': 'string'}},
                        'why': {'type': 'string'}}}
DETAIL = {'type': 'object', 'additionalProperties': False, 'required': ['steps'],
          'properties': {'steps': {'type': 'array', 'items': _STEP}}}
TASK = ('You are the plan orderer of EAOS, an engineering audit. Below is the rules\' plan of this project: its milestones, '
        'its waves and every open card with its prerequisites, what the card triage decided about each card, the planned '
        'ideal\'s order when there is one, and the steps that close the pipeline\'s gaps. Decide the order and grouping of the '
        'work for the subject "plan": "reorder" with `detail.steps` (each step a group of card ids done together, in the order '
        'to do them, with why), "keep" when the rules\' order is already right, or "ask" when the order depends on a choice '
        'for the person. Never put a card before one of its prerequisites; leave out the cards the triage rejected; put a '
        'card the triage doubted after its probe can settle it. Cite in `evidence` the card ids and rules you relied on.')


def _triage(report):
    body = core.load(Path(report) / 'nodes/card_triage/verdicts.json', {}) or {}
    return {v['card']: v['decision'] for v in body.get('verdicts') or [] if isinstance(v, dict) and v.get('card')}


def _gap_steps(report):
    body = core.load(Path(report) / 'nodes/pipeline_gap_planner/plan.json', {}) or {}
    return [s for s in body.get('steps') or [] if isinstance(s, dict) and s.get('decision') in ('plan', 'rules only')][:40]


def inputs(report, project=None, lang='en', **_):
    report = Path(report)
    plan = core.load(report / 'plan.json', {}) or {}
    done = {c['id'] for c in ideal._cards(report) if c.get('state') in ('done', 'resolved')}
    tasks = [t for t in plan.get('tasks') or [] if isinstance(t, dict) and t.get('id') and t['id'] not in done][:LIMIT['tasks']]
    if not tasks: return None
    wave = {task: i + 1 for i, row in enumerate(plan.get('waves') or []) for task in (row if isinstance(row, list) else [])}
    milestone = {task: m.get('id') for m in plan.get('milestones') or [] if isinstance(m, dict) for task in m.get('tasks') or []}
    triage = _triage(report)
    record, state = ideal.current(report)
    order = (((record or {}).get('ideal') or {}).get('views') or {}).get('plan_order') if state == 'planned' else None
    return {'lang': lang,
            'tasks': [{'id': t['id'], 'title': core.short(t.get('title'), 160), 'kind': t.get('kind'), 'paths': (t.get('paths') or [])[:2],
                       'prerequisites': [p for p in t.get('prerequisites') or [] if isinstance(p, str)], 'milestone': milestone.get(t['id']),
                       'wave': wave.get(t['id']), 'triage': triage.get(t['id'])} for t in tasks],
            'milestones': [{'id': m.get('id'), 'goal': core.short(m.get('goal'), 200), 'tasks': m.get('tasks') or []}
                           for m in plan.get('milestones') or [] if isinstance(m, dict)],
            'rules': {'RULE-plan-order': ideal.rules(report).get('RULE-plan-order')},
            'ideal_order': [{k: e.get(k) for k in ('id', 'title', 'detail', 'cites')} for e in (order or {}).get('elements') or []][:40],
            'pipeline_steps': _gap_steps(report)}


def subjects(data):
    return ['plan']


def known(report, data):
    return ideal.known_ids(report) | {s['gap'] for s in data['pipeline_steps'] if s.get('gap')}


def rules_steps(data):
    """The rules' order: by milestone, then wave, as eaos/plan.py placed the cards."""
    order = {m['id']: i for i, m in enumerate(data['milestones'])}
    steps = {}
    for task in sorted(data['tasks'], key=lambda t: (order.get(t['milestone'], 99), t['wave'] or 99, t['id'])):
        if task['triage'] == 'reject': continue
        key = (task['milestone'], task['wave'])
        steps.setdefault(key, {'id': f"{task['milestone'] or 'M?'}-W{task['wave'] or '?'}", 'title': f"{task['milestone'] or 'M?'}, wave {task['wave'] or '?'}",
                               'tasks': [], 'why': "The rules' order: the milestone, then the wave."})['tasks'].append(task['id'])
    return list(steps.values())


def rules(data):
    ids = [t['id'] for t in data['tasks']][:20]
    return {'plan': (ids + ['RULE-plan-order'], "The rules' order: milestones, prerequisites and the files each card touches.", 0.6,
                     {'steps': rules_steps(data)})}


def check(data, decision):
    """An order keeps every prerequisite, names each card once and only cards of the plan."""
    if decision['decision'] != 'reorder': return None
    tasks = {t['id']: t for t in data['tasks']}
    place = {}
    for index, step in enumerate((decision.get('detail') or {}).get('steps') or []):
        for task in step.get('tasks') or []:
            if task not in tasks: return f'the order names {task}, which the plan does not hold'
            if task in place: return f'the order names {task} twice'
            place[task] = index
    if not place: return 'the order names no card'
    for task, index in place.items():
        for need in tasks[task]['prerequisites']:
            if need in place and place[need] > index: return f'the order puts {task} before its prerequisite {need}'
    return None


def prompt(data):
    return (TASK + '\n\n' + core.rules_of_the_answer(data['lang']) + '\n\nAnswer with the JSON object of the schema only.\n\n'
            'The bundle:\n' + json.dumps({k: v for k, v in data.items() if k != 'lang'}, ensure_ascii=False))


def finish(report, record, data):
    decision = next(d for d in record['decisions'] if d['subject'] == 'plan')
    steps = [dict(s) for s in ((decision.get('detail') or {}).get('steps') if decision['decision'] == 'reorder' else None)
             or rules_steps(data)]
    placed = {t for s in steps for t in s.get('tasks') or []}
    rejected = [t['id'] for t in data['tasks'] if t['triage'] == 'reject']
    left = [t for s in rules_steps(data) for t in s['tasks'] if t not in placed]
    if left: steps.append({'id': 'not-placed', 'title': 'Not placed by the order', 'tasks': left,
                           'why': "The order left these cards out; they follow in the rules' order."})
    folder = core.folder_of(report, record['node'])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'order.json').write_text(json.dumps({'schema_version': 1, 'at': record['at'], 'method': record['method'],
                                                   'decision': decision['decision'], 'source': decision['source'], 'steps': steps,
                                                   'set_aside': rejected, 'why': decision['why']}, ensure_ascii=False, indent=1) + '\n',
                                       encoding='utf-8')


def run(node, report, **options):
    import sys
    return core.run_node(node, sys.modules[__name__], report, **options)
