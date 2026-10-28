"""The ideal, planned with a model on top of the rules.

Two layers, both kept and shown. The rules (eaos/report/target_architecture/picture.py, eaos/analysis/target_state/projection.py and the maps built
from them) give the baseline target of every view and its evidence. The person's own assistant, run headless by the
command centre's launcher (eaos/ai/assistant/headless.py `ask`), then plans the ideal on top of it:

    bundle(report)    a compact, grounded picture: the rules' target of every view with the rules it applied, the cards,
                      the facts that matter, the decisions, and the project's own documents as untrusted data
    pass 'plan'       the ideal of every view in a strict JSON schema, every element citing fact, claim, card or rule ids,
                      asked in parts side by side (eaos/ai/ideal/passes.py)
    pass 'critique'   the same assistant reviews the draft (what was missed, risks, order) and returns its changes,
                      applied to the draft
    check(...)        deterministic: a citation resolves only to an id of this report; an element with no resolving
                      citation is dropped and listed, never shown
    <report>/ideal/plan.json   the checked ideal with its inputs, both answers and the dropped elements

What the Studio reads of it (eaos/ai/ideal/studio.py, its names re-exported here): `section(report)` is the body of
studio/ideal.json: every view with its provenance (rules or planned, the assistant and model, when, the confidence, the
departures from the rules and why, the open questions). Without an assistant, on a failure, a stuck assistant or a
stop, or when the plan was made for an earlier check, the rules' target stays and the section says so plainly.
`provenance_of(body)` stamps every section that draws a target; `decisions(report)` brings the open questions to the
Decisions inbox.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from ...analysis.understanding.aspects import ASPECTS, VERDICTS
from ...live.access.roles import unseen
from ...core.system.process import Stuck
from ...analysis.repair.review import triage_verdicts
from . import bundle as read
from .base import EVIDENCE, LIMIT, OPERATIONS, VIEWS, _slug
from .rules import proposal as _proposal, views as _rules_views
from .studio import SECTION_VIEWS, _words, current, decisions, disagreements, provenance_of, scan_key, section  # noqa: F401  (the names others read here)
from ..nodes.framework import digest, launcher_of, short as _short
from ...core.system.files import read_json
from ...core.system.clock import now


def _verdicts(report):
    """{card: decision} of the assistant's triage of this report ({} when the rules decided alone)."""
    return {card: v['decision'] for card, v in triage_verdicts(report).items()}


def _cards(report):
    cards = (read_json(Path(report) / 'studio/cards.json', {}) or {}).get('cards')
    if isinstance(cards, list): return _with_id(cards)
    return _with_id((read_json(Path(report) / 'plan.json', {}) or {}).get('tasks') or [])


def _with_id(rows):
    """The rows that are objects with an id."""
    return [row for row in rows if isinstance(row, dict) and row.get('id')]


# ---------------------------------------------------------------- the rules: their ids and their target per view

def rules(report):
    """{RULE id: what it says}: the disposition rules, the reference's layers, the infrastructure baseline, the plan's
    ordering rule and the pipeline rules, as the baseline applied them to this report."""
    target = _proposal(report)
    return {**_disposition_rules(), **_layer_rules(target), **_infra_rules(target),
            'RULE-plan-order': ('The fix plan runs in milestones; a task waits for the tasks it names as prerequisites and '
                                'for the last earlier task touching the same file (eaos/analysis/planning/cards.py waves).'),
            **_pipeline_rules()}


def _disposition_rules():
    """The disposition rules (eaos/analysis/target_state/projection.py RULES), in their order."""
    from ...analysis.target_state.projection import RULES as DISPOSITION
    disposition = read_json(DISPOSITION, {}) or {}
    return {f'RULE-disposition-{name}': _short((disposition.get(name) or {}).get('why'), 300) for name in disposition.get('order') or []}


def _layer_rules(target):
    """The layers of the target's reference architecture: each one's responsibility and what it may depend on."""
    try:
        from ...analysis.target_state.references import by_id
        reference = by_id(target.get('reference')) if target.get('reference') else None
    except Exception:
        reference = None
    return {f"RULE-layer-{_slug(layer['name'])}": _short(f"{layer.get('responsibility', '')}; may depend on: "
                                                         f"{', '.join(layer.get('allowed_dependencies') or []) or 'nothing'}", 300)
            for layer in (reference or {}).get('layers') or []}


def _infra_rules(target):
    """The infrastructure baseline: the decision of each area."""
    return {f"RULE-infra-{_slug(item['area'])}": _short(item.get('decision'), 300)
            for item in target.get('infrastructure') or [] if isinstance(item, dict) and item.get('area')}


def _pipeline_rules():
    """The pipeline rules (eaos/data/pipeline-rules.json): each one's title."""
    pipeline = read_json(Path(__file__).resolve().parents[2] / 'data/pipeline-rules.json', []) or []
    return {f"RULE-pipeline-{_slug(rule['id'])}": _short(rule.get('title') or rule.get('text') or rule.get('rule'), 300)
            for rule in (pipeline.get('rules') or [] if isinstance(pipeline, dict) else pipeline) if isinstance(rule, dict) and rule.get('id')}


# ---------------------------------------------------------------- the bundle the assistant reads

def known_ids(report, project=None):
    """Every id a citation may resolve to: the report's facts (FACT-), claims (CLM-) and cards (TASK-), and the rules
    the baseline applied (RULE-)."""
    report = Path(report)
    known = set(rules(report)) | _fact_ids(report)
    known.update(c['id'] for c in (read_json(report / 'dossier.json', {}) or {}).get('claims') or [] if isinstance(c, dict) and c.get('id'))
    known.update(c['id'] for c in _cards(report))
    return {i for i in known if EVIDENCE.match(i)}


def _fact_ids(report):
    """The ids of the report's facts (facts/*.json, its caches and index aside)."""
    known = set()
    for path in sorted((report / 'facts').glob('*.json')):
        if path.name in ('syntax-cache.json', 'index.json', 'run.json'): continue
        data = read_json(path, {}) or {}
        known.update(f['id'] for f in data.get('facts') or [] if isinstance(f, dict) and isinstance(f.get('id'), str))
    return known


def _open_cards(report, triage):
    """The cards still open that the triage did not reject, most severe first."""
    severity = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'info': 4}
    return sorted((c for c in _cards(report) if c.get('state', 'open') not in ('done', 'resolved') and triage.get(c['id']) != 'reject'),
                  key=lambda c: (severity.get(c.get('severity'), 5), c['id']))


def bundle(report, project=None, lang='en'):
    """The compact, grounded picture the assistant plans from. Deterministic for the same records."""
    report = Path(report)
    target = _proposal(report)
    triage = _verdicts(report)
    cards = _open_cards(report, triage)
    return {
        'project': {'name': (project and Path(project).name) or report.name, 'reference': target.get('reference'),
                    'language': 'Arabic' if lang == 'ar' else 'English'},
        'rules': rules(report),
        'baseline': _baseline(_rules_views(report)),
        'target_edges': (target.get('target_edges') or [])[:80],
        'forbidden_edges': target.get('forbidden_edges'),
        'cards': [{'id': c['id'], 'title': _short(c.get('title'), 140), 'severity': c.get('severity'), 'kind': c.get('kind'),
                   'paths': (c.get('paths') or [])[:2], 'milestone': c.get('milestone'), 'triage': triage.get(c['id'])}
                  for c in cards[:LIMIT['cards']]],
        'cards_omitted': max(0, len(cards) - LIMIT['cards']),
        'semantic': read.semantic(report),
        'visual': _visual(report),
        'not_seen': unseen(read_json(report / 'live/screens.json', {}))[:40],
        'facts': read.facts_digest(report),
        'features': read.features(report),
        'decisions': {'structure': _structure_decisions(target)[:40], 'waiting_for_the_person': read.waiting(report, project),
                      'intake': read.intake(report)},
        'documents': read.docs(project),
        'aspects': _aspects(report),
    }


def _baseline(views):
    """The rules' target of every view, its elements bounded and their empty fields left out."""
    return {name: {'summary': summary, 'elements': [{k: v for k, v in e.items() if v not in (None, '', [])}
                                                    for e in elements[:LIMIT['elements']]],
                   'omitted': max(0, len(elements) - LIMIT['elements'])}
            for name, (summary, elements) in views.items()}


def _visual(report):
    """The visual reviewer's findings, the first 30, in short."""
    return [{k: f.get(k) for k in ('page', 'viewport', 'theme', 'title', 'kind', 'severity')}
            for f in (read_json(report / 'nodes/visual_reviewer/findings.json', {}) or {}).get('findings') or []][:30]


def _structure_decisions(target):
    """The target's structural decisions: the problem, the choice and their evidence."""
    return [{'id': d.get('id'), 'problem': _short(d.get('problem'), 200), 'chosen': _short(d.get('chosen'), 200), 'evidence': read.cited(d, 4)}
            for d in target.get('decisions') or [] if isinstance(d, dict)]


def _aspects(report):
    """Every aspect of the program with its compact evidence and the rules' verdict (eaos/analysis/understanding/aspects.py digest)."""
    from ...analysis.understanding.aspects import digest
    return {name: {**{k: v for k, v in row.items() if k != 'rules'}, 'rules_verdict': row['rules']['verdict'],
                   'rules_why': row['rules']['why']} for name, row in digest(report).items()}


# ---------------------------------------------------------------- what the assistant is asked: eaos/ai/ideal/prompts.py

# ---------------------------------------------------------------- the evidence check

def check(ideal, known, context=()):
    """(kept, dropped): every element keeps only its citations that resolve (`known`; `context` ids, such as the
    project's documents, are kept but are not evidence); an element with no resolving citation, an unknown operation
    or a repeated id is dropped and listed with why. Departures stay only on a kept element."""
    known, context = set(known), set(context)
    ideal = ideal or {}
    dropped, alive = [], set()
    refs = _Refs(known, context)
    views = {name: _check_view(name, (ideal.get('views') or {}).get(name) or {}, refs, dropped, alive) for name in VIEWS}
    kept = {'views': views, 'aspects': _check_aspects(ideal, known, context)}
    kept['departures'] = _departures(ideal, known, context, alive)
    kept['open_questions'] = [_question(i, q) for i, q in enumerate(ideal.get('open_questions') or [])
                              if isinstance(q, dict) and q.get('question')]
    kept['confidence'] = _confidence(ideal.get('confidence'))
    return kept, dropped


def _departures(ideal, known, context, alive):
    """The departures from the rules that say why, on a kept element (`alive`), with their resolving citations."""
    return [{'view': d.get('view'), 'element': d.get('element'), 'rule_says': _short(d.get('rule_says'), 400),
             'plan_chose': _short(d.get('plan_chose'), 400), 'because': _short(d.get('because'), 600),
             'cites': [c for c in d.get('cites') or [] if c in known or c in context]}
            for d in ideal.get('departures') or []
            if isinstance(d, dict) and (d.get('view'), str(d.get('element'))) in alive and d.get('because')]


def _confidence(value):
    """A confidence within 0..1, or None when the assistant gave no number."""
    return min(1.0, max(0.0, float(value))) if isinstance(value, (int, float)) else None


class _Refs(NamedTuple):
    """What a citation may name: `known` ids are evidence, `context` ids (such as the project's documents) are read but
    are not evidence."""
    known: set
    context: set


def _check_view(name, view, refs, dropped, alive):
    """One view's elements that stand on evidence; each one dropped is added to `dropped`, each one kept to `alive`."""
    seen, elements = set(), []
    for element in view.get('elements') or []:
        if not isinstance(element, dict): continue
        eid = str(element.get('id') or '')
        cites, evidence = _citations(element, refs.known)
        why = _drop_reason(eid, seen, element, evidence)
        if why:
            dropped.append({'view': name, 'id': eid or '?', 'title': _short(element.get('title'), 160), 'why': why, 'cites': cites[:8]})
            continue
        seen.add(eid)
        alive.add((name, eid))
        elements.append(_element_row(eid, element, cites, evidence, refs))
    return {'summary': _short(view.get('summary'), 600), 'confidence': _confidence(view.get('confidence')), 'elements': elements}


def _citations(element, known):
    """(cites, evidence): an element's citations, and those of them that resolve."""
    cites = [c for c in element.get('cites') or [] if isinstance(c, str)]
    return cites, [c for c in cites if c in known]


def _drop_reason(eid, seen, element, evidence):
    """Why an element cannot stand, or None when it can."""
    return ('no id' if not eid else 'repeated id' if eid in seen else
            'unknown operation' if element.get('operation') not in OPERATIONS else
            'no citation resolves to a fact, claim, card or rule of this report' if not evidence else None)


def _element_row(eid, element, cites, evidence, refs):
    known, context = refs
    row = {'id': eid, 'kind': str(element.get('kind') or 'element'), 'title': _short(element.get('title'), 200),
           'operation': element['operation'], 'subject': element.get('subject') if isinstance(element.get('subject'), str) else None,
           'detail': _short(element.get('detail'), 600), 'cites': list(dict.fromkeys(evidence))}
    read = [c for c in cites if c in context]
    unresolved = [c for c in cites if c not in known and c not in context]
    if read: row['context'] = read[:8]
    if unresolved: row['unresolved'] = unresolved[:8]
    return row


def _check_aspects(ideal, known, context):
    """The assistant's verdict on each known aspect, once, when it says why; cards and citations kept when they resolve."""
    cards = {i for i in known if i.startswith('TASK-')}
    out, judged = [], set()
    for row in ideal.get('aspects') or []:
        if not _judges(row, judged): continue
        judged.add(row['aspect'])
        out.append(_aspect_row(row, cards, known, context))
    return out


def _judges(row, judged):
    """Whether a row gives a known verdict on a known aspect not judged yet, and says why."""
    return (isinstance(row, dict) and row.get('aspect') in ASPECTS and row.get('verdict') in VERDICTS
            and row['aspect'] not in judged and str(row.get('why') or '').strip())


def _aspect_row(row, cards, known, context):
    return {'aspect': row['aspect'], 'verdict': row['verdict'], 'why': _short(row.get('why'), 600),
            'plan': _short(row.get('plan'), 800) if row['verdict'] == 'improve' else '',
            'cards': [c for c in row.get('cards') or [] if c in cards][:12],
            'cites': [c for c in row.get('cites') or [] if c in known or c in context][:8]}


def _question(index, q):
    return {'id': str(q.get('id') or f'q{index + 1}'), 'view': q.get('view') if q.get('view') in VIEWS else 'system',
            'question': _short(q.get('question'), 400), 'options': [_short(o, 120) for o in q.get('options') or []][:6],
            'recommendation': _short(q.get('recommendation'), 200) or None, 'why': _short(q.get('why'), 400)}


def share(ideal, known):
    """Elements with at least one citation in `known` ÷ elements (None when there is no element)."""
    rows = _elements(ideal)
    if not rows: return None
    return round(sum(any(c in known for c in e.get('cites') or [] if isinstance(c, str)) for e in rows) / len(rows), 4)


def _elements(ideal):
    """Every element of every view of an ideal."""
    return [e for v in ((ideal or {}).get('views') or {}).values() if isinstance(v, dict) for e in v.get('elements') or [] if isinstance(e, dict)]


# ---------------------------------------------------------------- the run

def _record(folder, row):
    path = folder / 'runs.json'
    rows = (read_json(path, []) or [])[-19:] + [row]
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def _why(problem, cancel):
    """Why a planning run did not finish: it was stopped, the assistant was stuck, or the error's own words."""
    if getattr(cancel, 'is_set', lambda: False)(): return 'stopped'
    return 'stuck' if isinstance(problem, Stuck) else _short(f'{type(problem).__name__}: {problem}', 300)


def plan(report, launcher=None, project=None, lang='en', adapters=None, cancel=None, started=None, say=None):  # limits: parameters -- the planning's settings by name, a node's (eaos/ai/nodes/runner.py RUN_OPTIONS)
    """Plan the ideal of every view on top of the rules: the planning pass, the critique pass and the evidence check.

    Returns {state, message{en, ar}, ...}. 'planned' writes <report>/ideal/plan.json; 'not_planned' (no assistant here)
    and 'failed' (an error, a stuck assistant, a stop, an answer outside the schema) leave the last plan and the rules'
    target as they are. `say(en, ar)` hears each step, for the command centre's run page."""
    report = Path(report)
    folder = report / 'ideal'
    folder.mkdir(parents=True, exist_ok=True)
    at, tell = now(), (say or (lambda en, ar: None))
    launcher = launcher or launcher_of(adapters, folder / ('run-' + at.replace(':', '').replace('+0000', 'Z')), cancel, started)
    if launcher is None:
        message = _words('no_assistant')
        _record(folder, {'at': at, 'state': 'not_planned', 'assistant': None, 'model': None, 'seconds': None, 'passes': [],
                         'message': message['en']})
        return {'state': 'not_planned', 'message': message}
    tell('Reading the check and the rules\' target', 'يقرأ الفحص وهدف القواعد')
    data = bundle(report, project, lang)
    passes, began = [], datetime.now(timezone.utc)
    from .passes import passes as asked          # it reads the prompts, which read the nodes, which read this module
    try: draft, revised, critique = asked(launcher, data, passes, tell)
    except Exception as problem:
        why = _why(problem, cancel)
        message = _words('failed', why=why)
        _record(folder, {'at': at, 'state': 'failed', 'assistant': getattr(launcher, 'assistant', None), 'model': getattr(launcher, 'model', None),
                         'seconds': round((datetime.now(timezone.utc) - began).total_seconds(), 1), 'passes': passes, 'message': message['en'],
                         'why': why})
        return {'state': 'failed', 'message': message, 'why': why}
    tell('Checking that every element stands on evidence', 'يتحقق أن كل عنصر قائم على دليل')
    known = known_ids(report, project)
    context = {d['id'] for d in data['documents']}
    kept, dropped = check(revised, known, context)
    elements = sum(len(v['elements']) for v in kept['views'].values())
    record = {'schema_version': 1, 'at': at, 'scan': scan_key(report), 'inputs': digest(data), 'lang': lang,
              'assistant': getattr(launcher, 'assistant', None), 'model': getattr(launcher, 'model', None),
              'seconds': round((datetime.now(timezone.utc) - began).total_seconds(), 1), 'passes': passes,
              'ideal': kept, 'dropped': dropped, 'critique': critique, 'draft': draft,
              'elements': elements, 'raw_share': share(revised, known), 'share': share(kept, known) if elements else None,
              'draft_share': share(draft, known), 'bundle_bytes': len(json.dumps(data, ensure_ascii=False).encode('utf-8'))}
    (folder / 'plan.json').write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    _record(folder, {'at': at, 'state': 'planned', 'assistant': record['assistant'], 'model': record['model'],
                     'seconds': record['seconds'], 'passes': passes, 'message': f"{elements} elements, {len(dropped)} dropped"})
    tell(f'Planned: {elements} elements with their evidence, {len(dropped)} dropped without it',
         f'تم التخطيط: {elements} عنصرًا بدليله، وحُذف {len(dropped)} بلا دليل')
    return {'state': 'planned', 'message': _words('planned', assistant=record['assistant'], model=record['model'] or '?'),
            'elements': elements, 'dropped': dropped, 'share': record['share'], 'raw_share': record['raw_share'],
            'departures': kept['departures'], 'open_questions': kept['open_questions'], 'assistant': record['assistant'],
            'model': record['model'], 'at': at, 'passes': passes, 'seconds': record['seconds']}
