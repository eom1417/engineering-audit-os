"""The ideal, planned with a model on top of the rules (docs/STUDIO.md D10, docs/adoption/ns46-t14-ideal-planner.md).

Two layers, both kept and shown. The rules (eaos/target_architecture.py, eaos/target_projection.py and the maps built
from them) give the baseline target of every view and its evidence. The person's own assistant, run headless by the
command centre's launcher (eaos/studio/actions/adapters.py `ask`), then plans the ideal on top of it:

    bundle(report)    a compact, grounded picture: the rules' target of every view with the rules it applied, the cards,
                      the facts that matter, the decisions, and the project's own documents as untrusted data
    pass 'plan'       the ideal of every view in a strict JSON schema, every element citing fact, claim, card or rule ids
    pass 'critique'   the same assistant reviews the draft (what was missed, risks, order) and returns the revised ideal
    check(...)        deterministic: a citation resolves only to an id of this report; an element with no resolving
                      citation is dropped and listed, never shown
    <report>/ideal/plan.json   the checked ideal with its inputs, both answers and the dropped elements

`section(report)` is the body of studio/ideal.json: every view with its provenance (rules or planned, the assistant
and model, when, the confidence, the departures from the rules and why, the open questions). Without an assistant,
on a failure, a stuck assistant or a stop, or when the plan was made for an earlier check, the rules' target stays and
the section says so plainly. `provenance_of(body)` stamps every section that draws a target; `decisions(report)` brings the open
questions to the Decisions inbox.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from ..aspects import ASPECTS, VERDICTS
from ..assistants.command import Stuck
from ..card_review import triage_verdicts
from ..target_architecture import guard_words
from .ideal_base import EVIDENCE, LIMIT, OPERATIONS, VIEWS, _facts, _load, _slug
from .nodes.core import digest, launcher_of, lenient as _lenient, short as _short, UNTRUSTED

# The studio sections that draw a target, and the view whose provenance each carries (tools/make_contracts.py).
SECTION_VIEWS = {'system': 'system', 'story': 'system', 'gaps': 'change', 'operations': 'plan_order', 'plans': 'plan_order',
                 'paths': 'paths', 'journeys': 'journeys', 'data_paths': 'data_paths', 'infra': 'infra', 'pipeline': 'pipeline'}
DOCS = ('README.md', 'README', 'readme.md', 'ARCHITECTURE.md', 'CONTRIBUTING.md', 'docs/**/*.md', '*.md')
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


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _words(key, lang=None, **values):
    en, ar = WORDS[key]
    pick = lambda index: {k: WORDS[v][index] if isinstance(v, str) and v in WORDS else v for k, v in values.items()}
    words = {'en': en.format(**pick(0)), 'ar': ar.format(**pick(1))}
    return words if lang is None else words['ar' if lang == 'ar' else 'en']


def _proposal(report):
    """The rules' target as the rules proposed it (target-proposal.json), before the reconcile decided it; a report from
    before that stage has only target-architecture.json."""
    report = Path(report)
    return _load(report / 'target-proposal.json', None) or _load(report / 'target-architecture.json', {}) or {}


def _verdicts(report):
    """{card: decision} of the assistant's triage of this report ({} when the rules decided alone)."""
    return {card: v['decision'] for card, v in triage_verdicts(report).items()}


def _cards(report):
    cards = (_load(Path(report) / 'studio/cards.json', {}) or {}).get('cards')
    if isinstance(cards, list): return [c for c in cards if isinstance(c, dict) and c.get('id')]
    return [t for t in (_load(Path(report) / 'plan.json', {}) or {}).get('tasks') or [] if isinstance(t, dict) and t.get('id')]


# ---------------------------------------------------------------- the rules: their ids and their target per view

def rules(report):
    """{RULE id: what it says}: the disposition rules, the reference's layers, the infrastructure baseline, the plan's
    ordering rule and the pipeline rules, as the baseline applied them to this report."""
    from ..target_projection import RULES as DISPOSITION
    out = {}
    disposition = _load(DISPOSITION, {}) or {}
    for name in disposition.get('order') or []:
        out[f'RULE-disposition-{name}'] = _short((disposition.get(name) or {}).get('why'), 300)
    target = _proposal(report)
    try:
        from ..reference_architecture import by_id
        reference = by_id(target.get('reference')) if target.get('reference') else None
    except Exception:
        reference = None
    for layer in (reference or {}).get('layers') or []:
        out[f"RULE-layer-{_slug(layer['name'])}"] = _short(f"{layer.get('responsibility', '')}; may depend on: "
                                                           f"{', '.join(layer.get('allowed_dependencies') or []) or 'nothing'}", 300)
    for item in target.get('infrastructure') or []:
        if isinstance(item, dict) and item.get('area'):
            out[f"RULE-infra-{_slug(item['area'])}"] = _short(item.get('decision'), 300)
    out['RULE-plan-order'] = ('The fix plan runs in milestones; a task waits for the tasks it names as prerequisites and '
                              'for the last earlier task touching the same file (eaos/plan.py waves).')
    pipeline = _load(Path(__file__).resolve().parents[1] / 'data/pipeline-rules.json', []) or []
    for rule in pipeline.get('rules') or [] if isinstance(pipeline, dict) else pipeline:
        if isinstance(rule, dict) and rule.get('id'):
            out[f"RULE-pipeline-{_slug(rule['id'])}"] = _short(rule.get('title') or rule.get('text') or rule.get('rule'), 300)
    return out


def _rules_views(report):
    """{view: (summary, [elements])}: the rules' target of every view, from the records the rules wrote; each view's
    reader is in eaos/studio/ideal_rules.py."""
    from . import ideal_rules as read
    report = Path(report)
    studio, target = report / 'studio', _proposal(report)
    system = read.system(target, studio)
    return {'system': system, 'change': read.change(system), 'journeys': read.journeys(report, studio), 'paths': read.paths(studio),
            'data_paths': read.data_paths(report, studio), 'infra': read.infra(target), 'pipeline': read.pipeline(studio),
            'plan_order': read.plan_order(report)}


# ---------------------------------------------------------------- the bundle the assistant reads

def known_ids(report, project=None):
    """Every id a citation may resolve to: the report's facts (FACT-), claims (CLM-) and cards (TASK-), and the rules
    the baseline applied (RULE-)."""
    report = Path(report)
    known = set(rules(report))
    for path in sorted((report / 'facts').glob('*.json')):
        if path.name in ('syntax-cache.json', 'index.json', 'run.json'): continue
        data = _load(path, {}) or {}
        known.update(f['id'] for f in data.get('facts') or [] if isinstance(f, dict) and isinstance(f.get('id'), str))
    known.update(c['id'] for c in (_load(report / 'dossier.json', {}) or {}).get('claims') or [] if isinstance(c, dict) and c.get('id'))
    known.update(c['id'] for c in _cards(report))
    return {i for i in known if EVIDENCE.match(i)}


def _docs(project):
    """The project's own documents, cut to size, marked as untrusted data."""
    if not project or not Path(project).is_dir(): return []
    project, seen, out, total = Path(project), set(), [], 0
    for pattern in DOCS:
        for path in sorted(project.glob(pattern)):
            rel = path.relative_to(project).as_posix()
            if rel in seen or not path.is_file() or 'node_modules/' in rel or rel.startswith('.'): continue
            seen.add(rel)
            text = path.read_text(encoding='utf-8', errors='replace')[:LIMIT['doc_chars']]
            if total + len(text) > LIMIT['docs_chars']: return out
            total += len(text)
            out.append({'id': f'DOC:{rel}', 'path': rel, 'trust': UNTRUSTED, 'text': text})
    return out


def _facts_digest(report):
    """The facts a plan needs, each with its id: entries, flows, tables, runtime, cycles, dead code, config names."""
    report = Path(report)
    take = lambda rows, make: [make(f) for f in rows[:LIMIT['facts']]]
    where = lambda f: (f.get('location') or {}).get('path')
    entry = [f for f in _facts(report, 'entrypoints') if f.get('kind') == 'entry_point']
    access = [f for f in _facts(report, 'entrypoints') if f.get('kind') == 'data_access']
    domain = [f for f in _facts(report, 'domain') if f.get('kind') != 'data_model' or (f.get('value') or {}).get('kind') in ('table', 'sql_table')]
    graph = [f for f in _facts(report, 'graph') if f.get('kind') == 'graph_node']
    graph.sort(key=lambda f: (f.get('value') or {}).get('attention_rank', 999))
    return {
        'entry_points': take(entry, lambda f: {'id': f['id'], 'surface': (f['value'] or {}).get('surface'),
                                               'route': (f['value'] or {}).get('route'), 'path': where(f)}),
        'data_access': take(access, lambda f: {'id': f['id'], 'path': where(f), **{k: (f['value'] or {}).get(k) for k in
                                                                                  ('operation', 'table', 'route', 'http_method', 'client') if (f['value'] or {}).get(k)}}),
        'flows': take(_facts(report, 'flows'), lambda f: {'id': f['id'], 'entry': ((f['value'] or {}).get('entry') or {}).get('route'),
                                                          'files': ((f['value'] or {}).get('touched_files') or [])[:6],
                                                          'unresolved': len((f['value'] or {}).get('unresolved') or [])}),
        'domain': take(domain, lambda f: {'id': f['id'], 'kind': f.get('kind'), 'name': (f['value'] or {}).get('name'), 'path': where(f)}),
        'runtime': take(_facts(report, 'runtime') + _facts(report, 'config'),
                        lambda f: {'id': f['id'], 'kind': f.get('kind'), 'path': where(f),
                                   'what': _short(json.dumps({k: v for k, v in (f.get('value') or {}).items() if k != 'snippet'}), 120)}),
        'hubs': take(graph, lambda f: {'id': f['id'], 'path': where(f), 'fan_in': (f['value'] or {}).get('fan_in'),
                                       'fan_out': (f['value'] or {}).get('fan_out')}),
        'cycles': take([f for f in _facts(report, 'graph') if f.get('kind') == 'graph_cycle'],
                       lambda f: {'id': f['id'], 'members': (f['value'] or {}).get('members')}),
        'dead_code': take(_facts(report, 'deadcode'), lambda f: {'id': f['id'], 'path': where(f), 'rule': (f['value'] or {}).get('rule')}),
    }


def bundle(report, project=None, lang='en'):
    """The compact, grounded picture the assistant plans from. Deterministic for the same records."""
    report = Path(report)
    target = _proposal(report)
    severity = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'info': 4}
    triage = _verdicts(report)
    cards = sorted((c for c in _cards(report) if c.get('state', 'open') not in ('done', 'resolved') and triage.get(c['id']) != 'reject'),
                   key=lambda c: (severity.get(c.get('severity'), 5), c['id']))
    semantic = _load(report / 'semantic.json', {}) or {}
    views = _rules_views(report)
    decisions = [{'id': d.get('id'), 'problem': _short(d.get('problem'), 200), 'chosen': _short(d.get('chosen'), 200),
                  'evidence': [e for e in d.get('evidence') or [] if isinstance(e, str) and EVIDENCE.match(e)][:4]}
                 for d in target.get('decisions') or [] if isinstance(d, dict)]
    waiting = [{'id': d.get('id'), 'question': _short(d.get('question'), 200), 'state': d.get('state')}
               for d in (_load(report / 'studio/decisions.json', {}) or {}).get('decisions') or [] if isinstance(d, dict)]
    if project:
        from ..places import workspace
        from .actions.store import _read_json, decision_scope
        responses = _read_json(workspace(Path(project).resolve()) / 'runs/decisions.json', {}) or {}
        for item, source in zip(waiting, (_load(report / 'studio/decisions.json', {}) or {}).get('decisions') or []):
            response = responses.get(decision_scope(report / 'studio', source))
            if response:
                item['owner_answer'] = response
                item['state'] = 'owner_answer_saved'
    intake = [{'question': _short(q.get('question'), 160), 'answer': _short(q.get('answer'), 160), 'status': q.get('status')}
              for q in (_load(report / 'intake.json', {}) or {}).get('questions') or [] if isinstance(q, dict)]
    features = [{'name': f.get('name'), 'surfaces': (f.get('surfaces') or [])[:6], 'tables': (f.get('tables') or [])[:6],
                 'evidence': [e for e in f.get('evidence') or [] if isinstance(e, str) and EVIDENCE.match(e)][:3]}
                for f in (_load(report / 'features.json', {}) or {}).get('features') or [] if isinstance(f, dict)]
    return {
        'project': {'name': (project and Path(project).name) or report.name, 'reference': target.get('reference'),
                    'language': 'Arabic' if lang == 'ar' else 'English'},
        'rules': rules(report),
        'baseline': {name: {'summary': summary, 'elements': [{k: v for k, v in e.items() if v not in (None, '', [])}
                                                             for e in elements[:LIMIT['elements']]],
                            'omitted': max(0, len(elements) - LIMIT['elements'])}
                     for name, (summary, elements) in views.items()},
        'target_edges': (target.get('target_edges') or [])[:80],
        'forbidden_edges': target.get('forbidden_edges'),
        'cards': [{'id': c['id'], 'title': _short(c.get('title'), 140), 'severity': c.get('severity'), 'kind': c.get('kind'),
                   'paths': (c.get('paths') or [])[:2], 'milestone': c.get('milestone'), 'triage': triage.get(c['id'])}
                  for c in cards[:LIMIT['cards']]],
        'cards_omitted': max(0, len(cards) - LIMIT['cards']),
        'semantic': {'hypotheses': [{'id': c.get('id'), 'statement': _short(c.get('statement'), 300), 'facts': (c.get('fact_ids') or [])[:4]}
                                    for c in semantic.get('claims') or [] if isinstance(c, dict)][:30],
                     'questions': [_short(q.get('question'), 200) for q in semantic.get('questions') or [] if isinstance(q, dict)][:20]},
        'visual': [{k: f.get(k) for k in ('page', 'viewport', 'theme', 'title', 'kind', 'severity')}
                   for f in (_load(report / 'nodes/visual_reviewer/findings.json', {}) or {}).get('findings') or []][:30],
        'facts': _facts_digest(report),
        'features': features[:40],
        'decisions': {'structure': decisions[:40], 'waiting_for_the_person': waiting, 'intake': intake[:30]},
        'documents': _docs(project),
        'aspects': _aspects(report),
    }


def _aspects(report):
    """Every aspect of the program with its compact evidence and the rules' verdict (eaos/aspects.py digest)."""
    from ..aspects import digest
    return {name: {**{k: v for k, v in row.items() if k != 'rules'}, 'rules_verdict': row['rules']['verdict'],
                   'rules_why': row['rules']['why']} for name, row in digest(report).items()}


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


# ---------------------------------------------------------------- what the assistant is asked: eaos/studio/ideal_prompts.py

# ---------------------------------------------------------------- the evidence check

def check(ideal, known, context=()):
    """(kept, dropped): every element keeps only its citations that resolve (`known`; `context` ids, such as the
    project's documents, are kept but are not evidence); an element with no resolving citation, an unknown operation
    or a repeated id is dropped and listed with why. Departures stay only on a kept element."""
    known, context = set(known), set(context)
    ideal = ideal or {}
    dropped, alive = [], set()
    views = {name: _check_view(name, (ideal.get('views') or {}).get(name) or {}, known, context, dropped, alive) for name in VIEWS}
    kept = {'views': views, 'aspects': _check_aspects(ideal, known, context)}
    kept['departures'] = [{'view': d.get('view'), 'element': d.get('element'), 'rule_says': _short(d.get('rule_says'), 400),
                           'plan_chose': _short(d.get('plan_chose'), 400), 'because': _short(d.get('because'), 600),
                           'cites': [c for c in d.get('cites') or [] if c in known or c in context]}
                          for d in ideal.get('departures') or []
                          if isinstance(d, dict) and (d.get('view'), str(d.get('element'))) in alive and d.get('because')]
    kept['open_questions'] = [_question(i, q) for i, q in enumerate(ideal.get('open_questions') or [])
                              if isinstance(q, dict) and q.get('question')]
    kept['confidence'] = _confidence(ideal.get('confidence'))
    return kept, dropped


def _confidence(value):
    """A confidence within 0..1, or None when the assistant gave no number."""
    return min(1.0, max(0.0, float(value))) if isinstance(value, (int, float)) else None


def _check_view(name, view, known, context, dropped, alive):
    """One view's elements that stand on evidence; each one dropped is added to `dropped`, each one kept to `alive`."""
    seen, elements = set(), []
    for element in view.get('elements') or []:
        if not isinstance(element, dict): continue
        eid = str(element.get('id') or '')
        cites = [c for c in element.get('cites') or [] if isinstance(c, str)]
        evidence = [c for c in cites if c in known]
        why = _drop_reason(eid, seen, element, evidence)
        if why:
            dropped.append({'view': name, 'id': eid or '?', 'title': _short(element.get('title'), 160), 'why': why, 'cites': cites[:8]})
            continue
        seen.add(eid)
        alive.add((name, eid))
        elements.append(_element_row(eid, element, cites, evidence, known, context))
    return {'summary': _short(view.get('summary'), 600), 'confidence': _confidence(view.get('confidence')), 'elements': elements}


def _drop_reason(eid, seen, element, evidence):
    """Why an element cannot stand, or None when it can."""
    return ('no id' if not eid else 'repeated id' if eid in seen else
            'unknown operation' if element.get('operation') not in OPERATIONS else
            'no citation resolves to a fact, claim, card or rule of this report' if not evidence else None)


def _element_row(eid, element, cites, evidence, known, context):
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
        if not isinstance(row, dict) or row.get('aspect') not in ASPECTS or row.get('verdict') not in VERDICTS: continue
        if row['aspect'] in judged or not str(row.get('why') or '').strip(): continue
        judged.add(row['aspect'])
        out.append(_aspect_row(row, cards, known, context))
    return out


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
    rows = [e for v in ((ideal or {}).get('views') or {}).values() if isinstance(v, dict) for e in v.get('elements') or [] if isinstance(e, dict)]
    if not rows: return None
    return round(sum(any(c in known for c in e.get('cites') or [] if isinstance(c, str)) for e in rows) / len(rows), 4)


# ---------------------------------------------------------------- the run

def _record(folder, row):
    path = folder / 'runs.json'
    rows = (_load(path, []) or [])[-19:] + [row]
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def plan(report, launcher=None, project=None, lang='en', adapters=None, cancel=None, started=None, say=None):
    """Plan the ideal of every view on top of the rules: the planning pass, the critique pass and the evidence check.

    Returns {state, message{en, ar}, ...}. 'planned' writes <report>/ideal/plan.json; 'not_planned' (no assistant here)
    and 'failed' (an error, a stuck assistant, a stop, an answer outside the schema) leave the last plan and the rules'
    target as they are. `say(en, ar)` hears each step, for the command centre's run page."""
    from .. import artifact_contracts
    from .ideal_prompts import CRITIQUE_SCHEMA, IDEAL_SCHEMA, prompt_critique, prompt_plan
    report = Path(report)
    folder = report / 'ideal'
    folder.mkdir(parents=True, exist_ok=True)
    at, tell = _now(), (say or (lambda en, ar: None))
    launcher = launcher or launcher_of(adapters, folder / ('run-' + at.replace(':', '').replace('+0000', 'Z')), cancel, started)
    if launcher is None:
        message = _words('no_assistant')
        _record(folder, {'at': at, 'state': 'not_planned', 'assistant': None, 'model': None, 'seconds': None, 'passes': [],
                         'message': message['en']})
        return {'state': 'not_planned', 'message': message}
    tell('Reading the check and the rules\' target', 'يقرأ الفحص وهدف القواعد')
    data = bundle(report, project, lang)
    passes, began = [], datetime.now(timezone.utc)
    try:
        tell(f'{getattr(launcher, "assistant", "The assistant")} plans the ideal of every view', f'{getattr(launcher, "assistant", "المساعد")} يخطّط المثالي لكل عرض')
        draft = launcher('plan', prompt_plan(data), IDEAL_SCHEMA)
        passes.append('plan')
        problems = artifact_contracts.validate(draft, _lenient(IDEAL_SCHEMA))
        if problems: raise ValueError('the plan is not in the asked shape: ' + '; '.join(problems[:3]))
        tell('A second pass reviews the plan: what was missed, the risks, the order', 'تمرير ثانٍ يراجع الخطة: ما فات، والمخاطر، والترتيب')
        reviewed = launcher('critique', prompt_critique(data, draft), CRITIQUE_SCHEMA)
        passes.append('critique')
        problems = artifact_contracts.validate(reviewed, _lenient(CRITIQUE_SCHEMA))
        if problems: raise ValueError('the review is not in the asked shape: ' + '; '.join(problems[:3]))
    except Exception as problem:
        stopped = getattr(cancel, 'is_set', lambda: False)()
        why = 'stopped' if stopped else 'stuck' if isinstance(problem, Stuck) else _short(f'{type(problem).__name__}: {problem}', 300)
        message = _words('failed', why=why)
        _record(folder, {'at': at, 'state': 'failed', 'assistant': getattr(launcher, 'assistant', None), 'model': getattr(launcher, 'model', None),
                         'seconds': round((datetime.now(timezone.utc) - began).total_seconds(), 1), 'passes': passes, 'message': message['en'],
                         'why': why})
        return {'state': 'failed', 'message': message, 'why': why}
    tell('Checking that every element stands on evidence', 'يتحقق أن كل عنصر قائم على دليل')
    known = known_ids(report, project)
    context = {d['id'] for d in data['documents']}
    revised = reviewed['ideal']
    kept, dropped = check(revised, known, context)
    elements = sum(len(v['elements']) for v in kept['views'].values())
    record = {'schema_version': 1, 'at': at, 'scan': scan_key(report), 'inputs': digest(data), 'lang': lang,
              'assistant': getattr(launcher, 'assistant', None), 'model': getattr(launcher, 'model', None),
              'seconds': round((datetime.now(timezone.utc) - began).total_seconds(), 1), 'passes': passes,
              'ideal': kept, 'dropped': dropped, 'critique': reviewed.get('critique'), 'draft': draft,
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


# ---------------------------------------------------------------- what the Studio reads

def current(report):
    """(plan record or None, state): the plan when it was made for this check, and the section's state."""
    report = Path(report)
    record = _load(report / 'ideal/plan.json')
    runs = _load(report / 'ideal/runs.json', []) or []
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
                           for d in ideal.get('departures') or [] if view is None or d.get('view') == view],
            'open_questions': [{'id': q['id'], 'question': q['question'], 'recommendation': q.get('recommendation')}
                               for q in ideal.get('open_questions') or [] if view is None or q.get('view') == view]}


def _differences(planned, rules_elements):
    rules_ids = {e['id']: e for e in rules_elements}
    rows = []
    for element in (planned or {}).get('elements') or []:
        base = rules_ids.get(element.get('subject'))
        kind = 'added' if base is None else 'same' if base['operation'] == element['operation'] else 'changed'
        rows.append({'element': element['id'], 'kind': kind, 'subject': element.get('subject'),
                     'rules': base['operation'] if base else None, 'planned': element['operation']})
    return rows


def _view(name, rules_view, record, ideal, state, message, lang):
    summary, rules_elements = rules_view
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
    runs = _load(report / 'ideal/runs.json', []) or []
    message = _message(state, record, runs)
    ideal = (record or {}).get('ideal') or {}
    rules_views = _rules_views(report)
    views = {name: _view(name, rules_views[name], record, ideal, state, message, lang) for name in VIEWS}
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
    """Rows of studio/decisions.json for every place the assistant and the rules differ (eaos/target_architecture.py
    reconcile, eaos/plan.py confirm): both views, and the one the check kept as the answer: the assistant's where it
    cited evidence and passed the guards, the rule's where a guard kept it."""
    ar = lang == 'ar'
    target = _load(Path(report) / 'target-architecture.json', {}) or {}
    rows = []
    for row in target.get('disagreements') or []:
        kept = 'assistant' if row['label'] == 'ai_modified' else 'rule'
        question = (f"{row['element']}: القواعد تقول «{row['rule']}» ومساعدك قال «{row['assistant']}». {guard_words(row['why'], ar)}" if ar else
                    f"{row['element']}: the rules say \"{row['rule']}\" and your assistant said \"{row['assistant']}\". {row['why']}")
        rows.append({'id': f"disagree-{_slug(row['element'])}", 'question': _short(question, 600),
                     'recommendation': ('رأي مساعدك، لأن له دليلًا ومرّ الضوابط' if kept == 'assistant' else 'رأي القواعد، لأن ضابطًا منع رأي مساعدك')
                     if ar else ("your assistant's view: it cites evidence and passed the guards" if kept == 'assistant'
                                 else "the rules' view: a guard kept it"),
                     'options': [{'id': 'assistant', 'label': f"{'مساعدك' if ar else 'your assistant'}: {row['assistant']}"},
                                 {'id': 'rule', 'label': f"{'القواعد' if ar else 'the rules'}: {row['rule']}"}],
                     'blocks': [], 'state': 'answered', 'answer': kept, 'plan': None, 'asked': '', 'tool': None})
    cards = _load(Path(report) / 'cards.json', {}) or {}
    for row in cards.get('set_aside') or []:
        question = (f"{row['card']}: القواعد كتبت البطاقة «{_short(row.get('title'), 160)}» ومساعدك رفضها. {row.get('why') or ''}" if ar else
                    f"{row['card']}: the rules wrote the card \"{_short(row.get('title'), 160)}\" and your assistant rejected it. {row.get('why') or ''}")
        rows.append({'id': f"disagree-{_slug(row['card'])}", 'question': _short(question, 600),
                     'recommendation': 'رأي مساعدك: البطاقة خارج الخطة' if ar else "your assistant's view: the card is out of the plan",
                     'options': [{'id': 'assistant', 'label': 'خارج الخطة' if ar else 'out of the plan'},
                                 {'id': 'rule', 'label': 'في الخطة' if ar else 'in the plan'}],
                     'blocks': [], 'state': 'answered', 'answer': 'assistant', 'plan': None, 'asked': '', 'tool': None})
    return rows
