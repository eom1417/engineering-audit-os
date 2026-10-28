"""What the Studio reads of the planned ideal (eaos/ai/ideal/planner.py plans it): `section(report)`, the body of
studio/ideal.json, every view with the rules' target and, when it was made for this check, the plan on top of it, with
their provenance; `provenance_of(body)` stamps every section that draws a target; `decisions` and `disagreements` bring
the plan's open questions and the places the assistant and the rules differ to the Decisions inbox. The words the
person reads about a plan, and what a plan was made for (`scan_key`), are here too."""
import hashlib
from pathlib import Path
from typing import NamedTuple

from .base import VIEWS, _slug, guard_words
from .rules import views as _rules_views
from ..nodes.framework import short as _short
from ...core.system.files import read_json

# The studio sections that draw a target, and the view whose provenance each carries (tools/make_contracts.py).
SECTION_VIEWS = {'system': 'system', 'story': 'system', 'gaps': 'change', 'operations': 'plan_order', 'plans': 'plan_order',
                 'paths': 'paths', 'journeys': 'journeys', 'data_paths': 'data_paths', 'infra': 'infra', 'pipeline': 'pipeline'}
WORDS = {
    'not_planned': ("The ideal shown is the rules' target. It is not planned yet: re-plan it from the command centre "
                    "with your assistant (Claude Code or Codex).",
                    'المثالي المعروض هو هدف القواعد، وما خُطِّط بعد: أعد تخطيطه من مركز التحكم بمساعدك (Claude Code أو Codex).'),
    'no_assistant': ("No assistant is installed and logged in here, so the ideal stays the rules' target: not planned yet.",
                     'ما فيه مساعد مثبّت ومسجّل دخوله هنا، فيبقى المثالي هو هدف القواعد: ما خُطِّط بعد.'),
    'planned': ('Planned by {assistant} ({model}) on top of the rules, reviewed by a second pass; every element cites '
                'its evidence.', 'خطّطه {assistant} ({model}) فوق القواعد، وراجعه تمرير ثانٍ؛ كل عنصر يستشهد بدليله.'),
    'stale': ("The planned ideal was made for an earlier check; the rules' target of this check is shown until it is "
              "re-planned.", 'المثالي المخطَّط كان لفحص سابق؛ يظهر هدف القواعد لهذا الفحص حتى يُعاد التخطيط.'),
    'failed': ("The last planning run did not finish ({why}); the rules' target stays in place.",
               'آخر تخطيط ما اكتمل ({why})؛ ويبقى هدف القواعد مكانه.'),
    'stuck': ('the assistant gave no output at all for 20 minutes, so it was stuck and was ended',
              'ما أعطى المساعد أي ناتج طوال 20 دقيقة، فكان عالقًا وأُنهي'),
    'stopped': ('it was stopped', 'أُوقف'),
}


def _words(key, lang=None, **values):
    en, ar = WORDS[key]
    pick = lambda index: {k: WORDS[v][index] if isinstance(v, str) and v in WORDS else v for k, v in values.items()}
    words = {'en': en.format(**pick(0)), 'ar': ar.format(**pick(1))}
    return words if lang is None else words['ar' if lang == 'ar' else 'en']


def scan_key(report):
    """What a plan was made for: the rules' proposal and the confirmed cards it was planned from (the target and the plan
    of a report from before the reconcile stage). A check that changes them changes it; the final target and the
    plan's order are left out, since the check decides them from this plan."""
    h = hashlib.sha256()
    names = ('target-proposal.json', 'cards.json') if (Path(report) / 'target-proposal.json').is_file() else ('target-architecture.json', 'plan.json')
    for name in names:
        try: h.update(name.encode() + (Path(report) / name).read_bytes())
        except OSError: h.update(name.encode() + b'-')
    return h.hexdigest()[:16]


# ---------------------------------------------------------------- what the Studio reads

def current(report):
    """(plan record or None, state): the plan when it was made for this check, and the section's state."""
    report = Path(report)
    record = read_json(report / 'ideal/plan.json')
    runs = read_json(report / 'ideal/runs.json', []) or []
    last = runs[-1] if runs else None
    if isinstance(record, dict) and record.get('scan') == scan_key(report):
        return record, 'planned'
    if isinstance(record, dict): return None, 'stale'
    return None, 'failed' if last and last.get('state') == 'failed' else 'not_planned'


def _rules_provenance(state, message, lang):
    return {'method': 'rules', 'state': state, 'assistant': None, 'model': None, 'at': None, 'confidence': None,
            'message': message, 'departures': [], 'open_questions': []}


_LEFT_TO_RULES = {
    'en': "The plan left this view as the rules' target: nothing it planned here stood on evidence, or there was nothing to plan.",
    'ar': 'ترك التخطيط هذا العرض على هدف القواعد: ما خطّطه هنا بلا دليل، أو ما فيه شيء يُخطَّط.'}


def _message(state, record, runs):
    if state == 'planned':
        return _words('planned', assistant=record.get('assistant') or '?', model=record.get('model') or '?')
    if state == 'failed':
        return _words('failed', why=(runs[-1].get('why') if runs else None) or '?')
    return _words(state)


def _planned_provenance(record, ideal, message, view=None):
    """The provenance of what the assistant planned: of one view, or of the whole plan when view is None."""
    confidence = (((ideal.get('views') or {}).get(view) or {}) if view else {}).get('confidence')
    return {'method': 'planned', 'state': 'planned', 'assistant': record.get('assistant'), 'model': record.get('model'),
            'at': record.get('at'), 'confidence': confidence if confidence is not None else ideal.get('confidence'),
            'message': message, 'inputs': record.get('inputs'),
            'departures': [{k: d[k] for k in ('rule_says', 'plan_chose', 'because', 'element', 'cites')}
                           for d in _of_view(ideal.get('departures'), view)],
            'open_questions': [{'id': q['id'], 'question': q['question'], 'recommendation': q.get('recommendation')}
                               for q in _of_view(ideal.get('open_questions'), view)]}


def _of_view(rows, view):
    """The rows about one view, or all of them when view is None."""
    return [row for row in rows or [] if view is None or row.get('view') == view]


def _differences(planned, rules_elements):
    rules_ids = {e['id']: e for e in rules_elements}
    rows = []
    for element in (planned or {}).get('elements') or []:
        base = rules_ids.get(element.get('subject'))
        kind = 'added' if base is None else 'same' if base['operation'] == element['operation'] else 'changed'
        rows.append({'element': element['id'], 'kind': kind, 'subject': element.get('subject'),
                     'rules': base['operation'] if base else None, 'planned': element['operation']})
    return rows


class _Plan(NamedTuple):
    """The latest plan as every view reads it: its record (None when there is none for this check), the ideal it holds,
    its state and the words that say it."""
    record: dict
    ideal: dict
    state: str
    message: str


def _view(name, rules_view, plan, lang):
    summary, rules_elements = rules_view
    record, ideal, state, message = plan
    planned = (ideal.get('views') or {}).get(name) if record else None
    planned = planned if planned and planned.get('elements') else None
    if planned:
        provenance = _planned_provenance(record, ideal, message, name)
    elif state == 'planned':
        provenance = _rules_provenance('not_planned', _LEFT_TO_RULES, lang)
    else:
        provenance = _rules_provenance(state, message, lang)
    return {'provenance': provenance,
            'rules': {'summary': summary, 'elements': rules_elements[:400],
                      'count': {'value': len(rules_elements), 'src': f'ideal: the rules\' {name} view', 'unit': 'count'}},
            'planned': None if not planned else {
                'summary': planned.get('summary') or '', 'confidence': planned.get('confidence'), 'elements': planned['elements'],
                'count': {'value': len(planned['elements']), 'src': 'ideal/plan.json#ideal.views.' + name, 'unit': 'count'}},
            'differences': _differences(planned, rules_elements)}


def _evidence(record, views):
    elements = sum(len(v['planned']['elements']) for v in views.values() if v['planned'])
    kept = record or {}
    return {'share': {'value': kept.get('share'),
                      'src': 'ideal/plan.json#share: planned elements with a resolving citation / planned elements'},
            'raw_share': {'value': kept.get('raw_share'), 'src': 'ideal/plan.json#raw_share: the same before the evidence check'},
            'elements': {'value': elements if record else None, 'src': 'ideal/plan.json#elements', 'unit': 'count'},
            'dropped': [{k: row[k] for k in ('view', 'id', 'title', 'why')} for row in kept.get('dropped') or []]}


def _critique(record):
    critique = (record or {}).get('critique')
    return {k: list(critique.get(k) or [])[:30] for k in ('missed', 'risks', 'order')} if isinstance(critique, dict) else None


def _questions(ideal):
    return [{'id': q['id'], 'view': q['view'], 'question': q['question'], 'options': q.get('options') or [],
             'recommendation': q.get('recommendation'), 'why': q.get('why') or ''} for q in ideal.get('open_questions') or []]


def _run(r):
    return {'at': r.get('at') or '', 'state': r.get('state') if r.get('state') in ('planned', 'not_planned', 'failed', 'stale') else 'failed',
            'assistant': r.get('assistant'), 'model': r.get('model'), 'seconds': r.get('seconds'),
            'passes': list(r.get('passes') or []), 'message': r.get('message') or ''}


def section(report, lang='ar'):
    """The body of studio/ideal.json (contract studio-ideal)."""
    report = Path(report)
    record, state = current(report)
    runs = read_json(report / 'ideal/runs.json', []) or []
    message = _message(state, record, runs)
    ideal = (record or {}).get('ideal') or {}
    rules_views, plan = _rules_views(report), _Plan(record, ideal, state, message)
    views = {name: _view(name, rules_views[name], plan, lang) for name in VIEWS}
    return {'state': state, 'message': message,
            'provenance': _planned_provenance(record, ideal, message) if record else _rules_provenance(state, message, lang),
            'views': views, 'evidence': _evidence(record, views), 'critique': _critique(record),
            'questions': _questions(ideal) if record else [], 'runs': [_run(r) for r in runs[-10:]]}


def provenance_of(body):
    """{studio section: provenance}: the provenance every section that draws a target carries."""
    views = (body or {}).get('views') or {}
    return {name: views[view]['provenance'] for name, view in SECTION_VIEWS.items() if view in views}


def decisions(report, lang='ar'):
    """The open questions of the current plan, as rows of studio/decisions.json (the Decisions inbox)."""
    record, state = current(report)
    if state != 'planned': return []
    rows = []
    for q in ((record.get('ideal') or {}).get('open_questions') or []):
        options = q.get('options') or []
        rows.append({'id': f"ideal-{_slug(q['id'])}", 'question': q['question'],
                     'recommendation': q.get('recommendation') or ('' if lang != 'ar' else ''),
                     'options': [{'id': f'o{i + 1}', 'label': str(o)} for i, o in enumerate(options)],
                     'blocks': [], 'state': 'waiting', 'answer': None, 'plan': None, 'asked': record.get('at') or '',
                     'tool': 'replan_ideal'})
    return rows


def disagreements(report, lang='ar'):
    """Rows of studio/decisions.json for every place the assistant and the rules differ (eaos/report/target_architecture/picture.py
    reconcile, eaos/analysis/planning/cards.py confirm): both views, and the one the check kept as the answer: the assistant's where it
    cited evidence and passed the guards, the rule's where a guard kept it."""
    ar = lang == 'ar'
    target = read_json(Path(report) / 'target-architecture.json', {}) or {}
    cards = read_json(Path(report) / 'cards.json', {}) or {}
    return ([_disagreement(row, ar) for row in target.get('disagreements') or []]
            + [_set_aside(row, ar) for row in cards.get('set_aside') or []])


def _disagreement(row, ar):
    """The inbox row of one element the assistant and the rules decided differently, answered by the check."""
    kept = 'assistant' if row['label'] == 'ai_modified' else 'rule'
    question = (f"{row['element']}: القواعد تقول «{row['rule']}» ومساعدك قال «{row['assistant']}». {guard_words(row['why'], ar)}" if ar else
                f"{row['element']}: the rules say \"{row['rule']}\" and your assistant said \"{row['assistant']}\". {row['why']}")
    return {'id': f"disagree-{_slug(row['element'])}", 'question': _short(question, 600),
            'recommendation': ('رأي مساعدك، لأن له دليلًا ومرّ الضوابط' if kept == 'assistant' else 'رأي القواعد، لأن ضابطًا منع رأي مساعدك')
            if ar else ("your assistant's view: it cites evidence and passed the guards" if kept == 'assistant'
                        else "the rules' view: a guard kept it"),
            'options': [{'id': 'assistant', 'label': f"{'مساعدك' if ar else 'your assistant'}: {row['assistant']}"},
                        {'id': 'rule', 'label': f"{'القواعد' if ar else 'the rules'}: {row['rule']}"}],
            'blocks': [], 'state': 'answered', 'answer': kept, 'plan': None, 'asked': '', 'tool': None}


def _set_aside(row, ar):
    """The inbox row of one card the rules wrote and the assistant rejected: out of the plan."""
    question = (f"{row['card']}: القواعد كتبت البطاقة «{_short(row.get('title'), 160)}» ومساعدك رفضها. {row.get('why') or ''}" if ar else
                f"{row['card']}: the rules wrote the card \"{_short(row.get('title'), 160)}\" and your assistant rejected it. {row.get('why') or ''}")
    return {'id': f"disagree-{_slug(row['card'])}", 'question': _short(question, 600),
            'recommendation': 'رأي مساعدك: البطاقة خارج الخطة' if ar else "your assistant's view: the card is out of the plan",
            'options': [{'id': 'assistant', 'label': 'خارج الخطة' if ar else 'out of the plan'},
                        {'id': 'rule', 'label': 'في الخطة' if ar else 'in the plan'}],
            'blocks': [], 'state': 'answered', 'answer': 'assistant', 'plan': None, 'asked': '', 'tool': None}
