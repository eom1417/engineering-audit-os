"""The ideal planner as an AI node: node 1.

The planning itself is eaos/ai/ideal/planner.py `plan`, unchanged: the bundle, the plan and critique passes and the
evidence check of every element. As a node it gains the framework's guards: the time and cost recorded (never cut),
the cache (a current plan made from the same bundle is not asked again), the run log, and one decision in
the shared shape, subject "ideal": "accept" (every view planned on evidence and no question left: on to the plan
orderer), "ask" (its questions wait in the Decisions inbox) or "rules only" (not planned: the rules' target stands).
"""
import time
from contextlib import nullcontext
from pathlib import Path

from . import framework as core
from .runner import settings_of
from ..ideal import planner as ideal, prompts as ideal_prompts

SUBJECT = 'ideal'


def _evidence(planned):
    return list(dict.fromkeys(c for view in (planned.get('views') or {}).values() for e in view.get('elements') or []
                              for c in e.get('cites') or []))[:24]


def _decisions(node, report, plan_record, why=None):
    """The node's one decision from the ideal's plan record (None: not planned)."""
    kept = (plan_record or {}).get('ideal') or {}
    evidence = _evidence(kept)
    if not plan_record or not evidence: return [_rules_only(node, report, why)]
    return [_planned(node, plan_record, kept, evidence)]


def _rules_only(node, report, why):
    """Nothing planned on evidence: the rules' target stands, on the rules it applied."""
    rule_ids = sorted(ideal.rules(report))[:8] or ['RULE-plan-order']
    reason = why or "The ideal is not planned, so the rules' target stands."
    return {'subject': SUBJECT, 'decision': core.RULES_ONLY, 'options': core.choices(node), 'evidence': rule_ids, 'confidence': 0.5,
            'why': core.short(reason, 600), 'open_questions': [], 'source': 'rules', 'detail': {}}


def _questions(kept):
    return [{'id': core.short(q.get('id'), 60), 'question': core.short(q.get('question'), 400), 'options': list(q.get('options') or [])[:6],
             'recommendation': q.get('recommendation')} for q in kept.get('open_questions') or [] if q.get('question')]


def _planned(node, plan_record, kept, evidence):
    """The planned ideal: accepted, or asking the person its open questions."""
    questions = _questions(kept)
    views = [name for name, view in (kept.get('views') or {}).items() if view.get('elements')]
    confidence = kept.get('confidence')
    return {'subject': SUBJECT, 'decision': 'ask' if questions else 'accept', 'options': core.choices(node), 'evidence': evidence,
            'confidence': float(confidence) if isinstance(confidence, (int, float)) else 0.5,
            'why': _planned_why(plan_record, kept, views, questions), 'open_questions': questions, 'source': 'model',
            'detail': {'views': views, 'elements': plan_record.get('elements', 0), 'dropped': len(plan_record.get('dropped') or []),
                       'aspects': {row['aspect']: row['verdict'] for row in kept.get('aspects') or []}}}


def _planned_why(plan_record, kept, views, questions):
    return core.short(f"{plan_record.get('elements', 0)} elements planned on evidence over {len(views)} views, "
                      f"{len(kept.get('aspects') or [])} aspects judged, "
                      f"{len(kept.get('departures') or [])} departures from the rules, {len(questions)} questions for the person.", 600)


def _dropped(plan_record):
    return [{'subject': f"{row.get('view')}:{row.get('id')}", 'decision': None, 'evidence': list(row.get('cites') or [])[:8], 'why': row.get('why') or ''}
            for row in (plan_record or {}).get('dropped') or []]


def run(node, report, **options):
    """Plan the ideal (eaos/ai/ideal/planner.py) as a node; the settings come by name, as every node's (runner.RUN_OPTIONS)."""
    o = settings_of(options)
    project, lang, launcher = o['project'], o['lang'], o['launcher']
    report = Path(report)
    data = ideal.bundle(report, project, lang)
    prompt, at, began = ideal_prompts.prompt_plan(data), core.now(), time.monotonic()
    base = {'at': at, 'inputs': core.digest(data), 'passes': list(node.passes), 'summary': ''}
    asked = core.digest([prompt])
    schema = core.digest([ideal_prompts.IDEAL_SCHEMA, ideal_prompts.CRITIQUE_SCHEMA])
    current, state = ideal.current(report)
    if not o['fresh'] and state == 'planned' and current.get('inputs') == base['inputs']:
        return core.keep(report, node, core.record(node, {**base, 'state': 'decided', 'method': 'model', 'assistant': current.get('assistant'),
                                                          'model': current.get('model'), 'prompt': asked, 'schema': schema, 'cached': True,
                                                          'seconds': 0.0, 'cost_usd': None, 'why': None},
                                                   _decisions(node, report, current), _dropped(current)))
    stamp = at.replace(':', '').replace('+0000', 'Z')
    launcher = launcher or core.launcher_of(o['adapters'], report / 'ideal' / f'run-{stamp}', o['cancel'], o['started'])
    with o['assistants'] or nullcontext():
        result = ideal.plan(report, launcher=launcher, project=project, lang=lang, adapters={}, cancel=o['cancel'], say=o['say'])
    fields = {'assistant': getattr(launcher, 'assistant', None), 'model': getattr(launcher, 'model', None),
              'prompt': asked if launcher else None, 'schema': schema, 'cached': False, 'seconds': round(time.monotonic() - began, 1),
              'cost_usd': core.spent(launcher)}
    if result['state'] != 'planned':
        why, state = (core.WORDS['no_assistant'], 'rules_only') if launcher is None else core.fallback(str(result.get('why') or ''))
        return core.keep(report, node, core.record(node, {**base, **fields, 'state': state, 'method': 'rules', 'why': why},
                                                   _decisions(node, report, None, why), []))
    planned, _ = ideal.current(report)
    return core.keep(report, node, core.record(node, {**base, **fields, 'state': 'decided', 'method': 'model', 'why': None, 'calls': len(node.passes),
                                                      'summary': core.short(f"{result.get('elements', 0)} elements", 200)},
                                               _decisions(node, report, planned), _dropped(planned), critique=None))
