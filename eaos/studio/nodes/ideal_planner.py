"""The ideal planner as an AI node: node 1 (docs/STUDIO.md D10 and D11).

The planning itself is eaos/studio/ideal.py `plan`, unchanged: the bundle, the plan and critique passes and the
evidence check of every element. As a node it gains the framework's guards: the launcher held to the node's time and
cost budget, the cache (a current plan made from the same bundle is not asked again), the run log, and one decision in
the shared shape, subject "ideal": "accept" (every view planned on evidence and no question left: on to the plan
orderer), "ask" (its questions wait in the Decisions inbox) or "rules only" (not planned: the rules' target stands).
"""
import threading
import time
from pathlib import Path

from . import core
from .. import ideal

SUBJECT = 'ideal'


def _evidence(planned):
    return list(dict.fromkeys(c for view in (planned.get('views') or {}).values() for e in view.get('elements') or []
                              for c in e.get('cites') or []))[:24]


def _decisions(node, report, plan_record, why=None):
    """The node's one decision from the ideal's plan record (None: not planned)."""
    kept = (plan_record or {}).get('ideal') or {}
    evidence = _evidence(kept)
    if not plan_record or not evidence:
        rule_ids = sorted(ideal.rules(report))[:8] or ['RULE-plan-order']
        reason = why or "The ideal is not planned, so the rules' target stands."
        return [{'subject': SUBJECT, 'decision': core.RULES_ONLY, 'options': core.choices(node), 'evidence': rule_ids, 'confidence': 0.5,
                 'why': core.short(reason, 600), 'open_questions': [], 'source': 'rules', 'detail': {}}]
    questions = [{'id': core.short(q.get('id'), 60), 'question': core.short(q.get('question'), 400), 'options': list(q.get('options') or [])[:6],
                  'recommendation': q.get('recommendation')} for q in kept.get('open_questions') or [] if q.get('question')]
    views = [name for name, view in (kept.get('views') or {}).items() if view.get('elements')]
    confidence = kept.get('confidence')
    return [{'subject': SUBJECT, 'decision': 'ask' if questions else 'accept', 'options': core.choices(node), 'evidence': evidence,
             'confidence': float(confidence) if isinstance(confidence, (int, float)) else 0.5,
             'why': core.short(f"{plan_record.get('elements', 0)} elements planned on evidence over {len(views)} views, "
                               f"{len(kept.get('departures') or [])} departures from the rules, {len(questions)} questions for the person.", 600),
             'open_questions': questions, 'source': 'model',
             'detail': {'views': views, 'elements': plan_record.get('elements', 0), 'dropped': len(plan_record.get('dropped') or [])}}]


def _dropped(plan_record):
    return [{'subject': f"{row.get('view')}:{row.get('id')}", 'decision': None, 'evidence': list(row.get('cites') or [])[:8], 'why': row.get('why') or ''}
            for row in (plan_record or {}).get('dropped') or []]


def run(node, report, launcher=None, adapters=None, project=None, lang='en', budget=None, fresh=False, say=None, cancel=None,
        started=None, **_):
    report = Path(report)
    budget = budget or node.budget
    data = ideal.bundle(report, project, lang)
    prompt, at, began = ideal.prompt_plan(data), core.now(), time.monotonic()
    base = {'at': at, 'inputs': core.digest(data), 'passes': list(node.passes), 'summary': '',
            'budget': {'seconds': float(budget.seconds), 'usd': budget.usd}}
    asked = core.digest([prompt])
    schema = core.digest([ideal.IDEAL_SCHEMA, ideal.CRITIQUE_SCHEMA])
    current, state = ideal.current(report)
    if not fresh and state == 'planned' and current.get('inputs') == base['inputs']:
        return core.keep(report, node, core.record(node, {**base, 'state': 'decided', 'method': 'model', 'assistant': current.get('assistant'),
                                                          'model': current.get('model'), 'prompt': asked, 'schema': schema, 'cached': True,
                                                          'seconds': 0.0, 'cost_usd': None, 'why': None},
                                                   _decisions(node, report, current), _dropped(current)))
    if launcher is None:
        adapter = core.pick(adapters)
        if adapter is not None:
            stamp = at.replace(':', '').replace('+0000', 'Z')
            launcher = core.AdapterLauncher(adapter, report / 'ideal' / f'run-{stamp}', timeout=budget.seconds, cancel=cancel,
                                            started=started, budget_usd=budget.usd)
    cancel = cancel or threading.Event()
    bounded = core.Bounded(launcher, budget.seconds, budget.usd, cancel) if launcher is not None else None
    result = ideal.plan(report, launcher=bounded, project=project, lang=lang, adapters={} if bounded is None else adapters, cancel=cancel,
                        say=say)
    seconds = round(time.monotonic() - began, 1)
    fields = {'assistant': result.get('assistant') or (bounded and bounded.assistant), 'model': result.get('model') or (bounded and bounded.model),
              'prompt': asked if bounded else None, 'schema': schema, 'cached': False, 'seconds': seconds,
              'cost_usd': bounded.cost_usd if bounded else None}
    if result['state'] != 'planned':
        why_raw = str(result.get('why') or '')
        if bounded is None: why, state = core.WORDS['no_assistant'], 'rules_only'
        elif why_raw == 'timeout': why, state = core.WORDS['time'].format(seconds=int(budget.seconds)), 'rules_only'
        elif why_raw.startswith('OverBudget'):
            why, state = core.WORDS['budget'].format(cost=f'{bounded.cost_usd or 0:.2f}', usd=f'{budget.usd:.2f}'), 'rules_only'
        elif why_raw == 'stopped': why, state = core.WORDS['stopped'], 'rules_only'
        else: why, state = core.WORDS['failed'].format(why=core.short(why_raw, 300)), 'failed'
        return core.keep(report, node, core.record(node, {**base, **fields, 'state': state, 'method': 'rules', 'why': why},
                                                   _decisions(node, report, None, why), [], over_budget=why_raw.startswith('OverBudget')))
    planned, _ = ideal.current(report)
    return core.keep(report, node, core.record(node, {**base, **fields, 'state': 'decided', 'method': 'model', 'why': None, 'calls': len(node.passes),
                                                      'summary': core.short(f"{result.get('elements', 0)} elements", 200)},
                                               _decisions(node, report, planned), _dropped(planned), critique=None))
