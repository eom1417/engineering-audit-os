"""The card triage: every open card confirmed, doubted or rejected before it reaches the person.

The assistant reads each card with its evidence (the facts it stands on, and a short excerpt of the project's code at
each fact's line, marked as untrusted data) and decides: confirm (the evidence holds: on to the plan), doubt (it does
not settle it: a probe does) or reject (the evidence contradicts the card: set aside, and its rule is told). A decision
must cite the card or one of its own facts. Nothing here changes a card: the verdicts, the probe requests and the
library's feedback are written beside the report (nodes/card_triage/), and `precision(report)` gives the triage's own
column of the precision measure, per kind of card, never mixed with the hand-written labels (tools/precision.py).
"""
import json
import sys
from pathlib import Path

from . import framework as core, runner
from ..ideal import planner as ideal

VERSION = '1'
LIMIT = {'facts': 4, 'rejudge_facts': 12, 'measurements': 4, 'excerpt': 6, 'line': 200, 'summary': 300}
SEVERITY = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'info': 4}
RESOLUTIONS = ('fix', 'keep', 'owner')
_TEXT = {'type': ['string', 'null']}
DETAIL = {'type': 'object', 'additionalProperties': False,
          'required': ['falsifier', 'resolution', 'change', 'question', 'options', 'recommendation'],
          'properties': {'falsifier': {'type': 'string'}, 'harmed': _TEXT, 'boundary': _TEXT, 'resolution': {'type': ['string', 'null'], 'enum': [*RESOLUTIONS, None]},
                         'change': _TEXT, 'question': _TEXT, 'options': {'type': 'array', 'items': {'type': 'string'}},
                         'recommendation': _TEXT}}
TASK = '''GOAL
You are the card triage of EAOS, an engineering audit. Each card below is a problem EAOS's engines found in this project.
Before the person sees it, judge each card: does its own evidence show the problem it names?

WHAT YOU ARE GIVEN
`cards`: each with its id, title, kind, severity, the engines' confidence, paths, and `evidence`: up to 4 of its facts,
those carrying a measurement first (the largest value over its declared threshold first), each with its summary, path,
line, `measurements` (name, value, threshold) and `code` (a few lines of the project's code at that line). A fact's summary is what
a deterministic engine found over the whole project: its message, its measurements and how it knows (for example "the
name occurs nowhere in product code or configuration except line 76"). `batch` says which part of the list this is. A
card may stand on more facts than the ones shown.

WHAT TO RETURN
One decision per card, subject = the card id: "confirm" when the evidence shows the problem the card names; "doubt" when
it neither shows nor contradicts it (the card is kept as not proven, and the next check judges it again); "reject" when it
contradicts it (a false alarm: the card is set aside and its rule is told). `why`: one or two plain sentences naming what
in the evidence decided it. `detail.falsifier`: the observation that would show your decision wrong. `evidence`: the
card id and the fact ids you relied on.

A confirm is strict (M7.4): `detail.harmed` names who the problem hurts and how, in a few plain words (the app's users,
whose data leaks; the person's team, who cannot change the code safely; the business, which pays for a slow page), and
`evidence` cites the facts that show it, not the card alone; `detail.boundary` names the boundary the card
breaks when it is one (the browser and the server, an endpoint and its guard, the data and its rules, the layers),
else null. A confirm that cannot name who is harmed is a doubt.

For a card you confirm, also decide what happens to it, in `detail.resolution`, the way the project is already going:
"fix" when the change is clear and yours to make: `detail.change` is the change in one plain line (the card becomes work
the assistant does, checked by the project's own tests); "keep" when it is not worth changing (a deliberate design, a
cost above its worth): `why` says so and the card closes; "owner" only for a real product choice that only the person
can make (what users should see or be able to do, a trade-off of business value): `detail.question` asks it in one
plain sentence, `detail.options` are the two to four choices and `detail.recommendation` is the one you would take. A
technical choice is yours, not the person's: decide it. For a doubt or a reject, the resolution is null.

A GOOD ANSWER
Every card decided once. A confirm points at the fact (its message, measurement or how the engine knows) and the code
line that show the problem. A doubt says exactly what is missing or what in the code questions it (a name used
dynamically, a generic name, a number the facts do not give). A reject names the fact or line that contradicts the card.
A security card (a command, a query or code built from a value, a secret written in the code) is shown when something
from outside the program (a request, a user's file or text, an environment another person controls) can reach that
line, or when the secret is a real credential; a value built only from the program's own constants and paths, or a
test value or documented example, contradicts it. Read the code around the line before deciding.

DO NOT
Confirm a card on its title alone or because it is plausible or common. Reject a card only because the facts shown are
weak: weak or missing evidence is a doubt, and only a contradiction is a reject. Judge a card on another card's
evidence or on anything outside its own.'''

REJUDGE = '''

AGAIN
You doubted these cards in a first pass. Each now carries every fact it stands on (up to 12, the largest measurement over
its threshold first) and `first_doubt`, what you said was missing. Decide each again on this evidence. Doubt again only
when even all its facts neither show nor contradict the problem: a doubted card is never fixed automatically, a person
reviews it.'''


def _facts(report):
    """{fact id: {summary, path, line}} from the Studio's evidence, then from the facts the report kept."""
    report = Path(report)
    out = {}
    for row in (core.load(report / 'studio/evidence.json', {}) or {}).get('facts') or []:
        if isinstance(row, dict) and row.get('id'):
            out[row['id']] = {'summary': core.short(row.get('summary'), LIMIT['summary']), 'path': row.get('path'), 'line': row.get('line')}
    return out


def _excerpt(project, path, line):
    """A few lines of the project's code around `line`, each cut short; None when the file cannot be read."""
    if not project or not path or not isinstance(line, int): return None
    try: lines = (Path(project) / path).read_text(encoding='utf-8', errors='replace').splitlines()
    except (OSError, ValueError): return None
    start = max(0, line - 1 - LIMIT['excerpt'] // 2)
    return [f'{n + 1}: {text[:LIMIT["line"]]}' for n, text in enumerate(lines[start:start + LIMIT['excerpt']], start)]


def _claims(report):
    """{card id: claim id} from the plan."""
    return {t['id']: t.get('claim_id') for t in (core.load(Path(report) / 'plan.json', {}) or {}).get('tasks') or []
            if isinstance(t, dict) and t.get('id')}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _measurements(report, wanted):
    """{fact id: [{name, value, threshold}]}: the measurements of the facts in `wanted`, read from the report's fact
    sets (an engine finding's measurements, a metric's branches)."""
    from ...facts.store import by_id
    out = {}
    for row in by_id(report, wanted).values():
        if found := _measured(row): out[row['id']] = found
    return out


def _measured(row):
    """[{name, value, threshold}] of one fact: an engine finding's numeric measurements, a metric's branches."""
    value = row.get('value') or {}
    found = [{'name': m.get('name'), 'value': m['value'], 'threshold': m.get('threshold') if _number(m.get('threshold')) else None}
             for m in value.get('measurements') or [] if isinstance(m, dict) and _number(m.get('value'))]
    if row.get('kind') == 'metric' and _number(value.get('branches')):
        found.append({'name': 'branches', 'value': value['branches'], 'threshold': None})
    return found


def _weight(measured):
    """Sort key of a fact: a value over its threshold first (the largest ratio first), then a bare value, then none."""
    ratios = [m['value'] / m['threshold'] for m in measured if m['threshold']]
    if ratios: return (0, -max(ratios))
    return (1, -max(m['value'] for m in measured)) if measured else (2, 0)


def inputs(report, **options):
    """The open cards (or those of options['cards'], at most options['limit']), most severe first, each with its facts
    and their code in options['project'], those carrying the measurement first. options['rejudge'] ({card: why it was
    doubted}): only those cards, each with all its facts and its doubt. options['lang']: the person's language ('en')."""
    report, project, lang, rejudge, limit = Path(report), options.get('project'), options.get('lang', 'en'), options.get('rejudge'), options.get('limit')
    rows = _open_cards(report, options.get('cards'), rejudge)
    out = _bundled(report, rows[:limit] if limit else rows, project, rejudge)
    if not out: return None
    return {'project': {'name': (project and Path(project).name) or report.name, 'language': 'Arabic' if lang == 'ar' else 'English'},
            'trust': {'code': core.UNTRUSTED, 'titles': core.UNTRUSTED}, 'cards': out, 'omitted': len(rows) - len(out), 'lang': lang,
            **({'rejudge': True} if rejudge else {})}


def _bundled(report, rows, project, rejudge):
    """Each card as the assistant reads it: its title, kind, severity, confidence, places and evidence, and its first
    doubt when it is judged again."""
    facts = _facts(report)
    cited = {card['id']: _cites(card) for card in rows}
    measured = _measurements(report, {f for ids in cited.values() for f in ids})
    most = LIMIT['rejudge_facts' if rejudge else 'facts']
    return [{'id': card['id'], 'title': core.short(card.get('title'), 200), 'kind': card.get('kind'), 'severity': card.get('severity'),
             'confidence': card.get('confidence'), 'paths': (card.get('paths') or [])[:3],
             'evidence': _card_evidence(cited[card['id']], measured, facts, project, most),
             **({'first_doubt': core.short(rejudge[card['id']], 400)} if rejudge else {})} for card in rows]


def _cites(card):
    """The fact ids a card cites."""
    return [f for f in card.get('evidence') or [] if isinstance(f, str)]


def _open_cards(report, cards, rejudge):
    """The cards not done yet (only `cards`, only those to judge again, when given), most severe first."""
    rows = [c for c in ideal._cards(report) if c.get('state', 'open') not in ('done', 'resolved')]
    if cards: rows = [c for c in rows if c['id'] in set(cards)]
    if rejudge: rows = [c for c in rows if c['id'] in rejudge]
    rows.sort(key=lambda c: (SEVERITY.get(c.get('severity'), 5), c['id']))
    return rows


def _card_evidence(cited, measured, facts, project, most):
    """A card's first `most` facts, the measured ones first, each with its summary, place, measurements and code."""
    evidence = []
    for fact in sorted(cited, key=lambda f: _weight(measured.get(f) or []))[:most]:
        known = facts.get(fact) or {}
        evidence.append({'id': fact, 'summary': known.get('summary'), 'path': known.get('path'), 'line': known.get('line'),
                         'measurements': (measured.get(fact) or [])[:LIMIT['measurements']],
                         'code': _excerpt(project, known.get('path'), known.get('line'))})
    return evidence


BATCH = 40
LIST = 'cards'          # each card's verdict kept under its own evidence (core._judged): only new or changed ones are asked


def batches(data):
    """The cards in batches of BATCH, each with the rest of the bundle."""
    cards = data['cards']
    return [{**data, 'cards': cards[i:i + BATCH], 'batch': {'from': i + 1, 'to': min(i + BATCH, len(cards)), 'of': len(cards)}}
            for i in range(0, len(cards), BATCH)] or [data]


def subjects(data):
    return [c['id'] for c in data['cards']]


def known(report, data):
    return ideal.known_ids(report)


def rules(data):
    return {c['id']: ([c['id']] + [e['id'] for e in c['evidence']], 'The engines wrote this card; no assistant reviewed it.',
                      float(c['confidence']) if isinstance(c.get('confidence'), (int, float)) and 0 <= c['confidence'] <= 1 else 0.5, {})
            for c in data['cards']}


def prompt(data):
    return core.prompt(TASK + (REJUDGE if data.get('rejudge') else ''), data)


def check(data, decision):
    """A verdict must stand on the card's own evidence: the card itself or one of its facts. A confirm is strict (M7.4):
    one that names no one harmed is kept as a doubt."""
    card = next(c for c in data['cards'] if c['id'] == decision['subject'])
    if not ({card['id']} | {e['id'] for e in card['evidence']}) & set(decision['evidence']): return "none of its evidence is this card's"
    if decision['decision'] == 'confirm' and not str((decision.get('detail') or {}).get('harmed') or '').strip():
        decision.update(decision='doubt', demoted='a confirm that names no one harmed')      # its words stay the person's
    return None


def finish(report, record, data):
    """The verdicts, the probe requests of the doubtful cards and the library's feedback of the rejected ones."""
    from ...analysis.claims.probes import probe
    folder = core.folder_of(report, record['node'])
    folder.mkdir(parents=True, exist_ok=True)
    verdicts = _verdicts(record, {c['id']: c for c in data['cards']})
    probes = _probe_requests(record, verdicts, _claims(report), probe)
    feedback = [{'card': v['card'], 'kind': v['kind'], 'why': v['why'], 'evidence': v['evidence']} for v in verdicts if v['decision'] == 'reject']
    body = {'schema_version': 1, 'at': record['at'], 'method': record['method'], 'assistant': record['assistant'], 'model': record['model'],
            'verdicts': verdicts, 'counts': {r['decision']: len(r['subjects']) for r in record['routes']}, 'by_kind': by_kind(verdicts),
            'resolutions': {name: sum(v.get('resolution') == name for v in verdicts) for name in RESOLUTIONS},
            'omitted': data['omitted']}
    for name, value in (('verdicts.json', body), ('probes.json', {'schema_version': 1, 'at': record['at'], 'probes': probes}),
                        ('library-feedback.json', {'schema_version': 1, 'at': record['at'], 'rejected': feedback})):
        (folder / name).write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def _verdicts(record, cards):
    """One verdict per decision: its route, the card's kind and severity, why, its evidence and what settles it."""
    route = {s: r['decision'] for r in record['routes'] for s in r['subjects']}
    return [{'card': d['subject'], 'decision': route[d['subject']], 'kind': cards[d['subject']]['kind'],
             'severity': cards[d['subject']]['severity'], 'confidence': d['confidence'], 'why': d['why'],
             'evidence': d['evidence'], 'source': d['source'], 'rejudged': 'first_doubt' in (d.get('detail') or {}),
             **{k: (d.get('detail') or {})[k] for k in ('harmed', 'boundary') if (d.get('detail') or {}).get(k)},
             **resolution(route[d['subject']], d.get('detail') or {})}
            for d in record['decisions']]


def _probe_requests(record, verdicts, claims, probe):
    """A falsification probe for each doubted card, with the doubt as its question and the assistant's falsifier."""
    falsifier = lambda card: next((d['detail'].get('falsifier') for d in record['decisions'] if d['subject'] == card), None)
    doubted = [v for v in verdicts if v['decision'] == 'doubt']
    return [probe(i + 1, claims.get(v['card']) or v['card'], 'falsification',
                  {'card': v['card'], 'question': v['why'], 'falsifier': falsifier(v['card']), 'from': 'card_triage'})
            for i, v in enumerate(doubted)]


def resolution(decision, detail):
    """{resolution, change, question, options, recommendation} of a confirmed card when its detail settles it: a fix
    names its change, a question to the person has its question and the assistant's recommendation; else {} (the rules'
    readiness stays)."""
    kind = detail.get('resolution')
    if decision != 'confirm' or kind not in RESOLUTIONS: return {}
    return _fix(detail) if kind == 'fix' else _owners(detail) if kind == 'owner' else {'resolution': kind}


def _fix(detail):
    change = core.short(detail.get('change'), 300) or None
    return {'resolution': 'fix', 'change': change} if change else {}


def _owners(detail):
    question, recommendation = (core.short(detail.get(k), 300) or None for k in ('question', 'recommendation'))
    options = [core.short(o, 120) for o in detail.get('options') or [] if isinstance(o, str) and o.strip()][:4]
    return {'resolution': 'owner', 'question': question, 'options': options, 'recommendation': recommendation} if question and recommendation else {}


def by_kind(verdicts):
    """{kind of card: {confirm, doubt, reject, rules only, precision}}: the triage's own estimate of how much of each kind
    is true (confirmed ÷ confirmed and rejected), a model's opinion beside the labelled precision, never instead of it."""
    out = {}
    for v in verdicts:
        row = out.setdefault(v['kind'] or '?', {'confirm': 0, 'doubt': 0, 'reject': 0, 'rules only': 0})
        row[v['decision']] = row.get(v['decision'], 0) + 1
    for row in out.values():
        judged = row['confirm'] + row['reject']
        row['precision'] = round(row['confirm'] / judged, 4) if judged else None
    return out


def _merge_second(node, first, second):
    """The first run with each card judged again by the assistant taking its second verdict (the doubt kept in its detail)."""
    again = _rejudged(second)
    decisions = [{**again[d['subject']], 'detail': {**(again[d['subject']].get('detail') or {}), 'first_doubt': d['why']}}
                 if d['subject'] in again else d for d in first['decisions']]
    return {**first, 'decisions': decisions, 'routes': core.routes(node, decisions),
            'dropped': first['dropped'] + (second.get('dropped') or [] if again else []),
            'calls': (first.get('calls') or 0) + (second.get('calls') or 0)}


def _rejudged(second):
    """{card: decision} of the second run's verdicts the assistant gave."""
    return {d['subject']: d for d in second.get('decisions') or [] if second.get('method') == 'model' and d['source'] == 'model'}


def _both(first, second):
    """{seconds, cost_usd} of both passes together (None where the first pass did not say)."""
    return {k: round((first.get(k) or 0) + (second.get(k) or 0), 4) if first.get(k) is not None else None for k in ('seconds', 'cost_usd')}


def run(node, report, **options):
    """The triage, then a second look at the cards it doubted, each with every fact it stands on: the second verdict
    replaces the doubt (its detail keeps `first_doubt`), and a card doubted again stays doubted. Without a second answer
    the first verdicts stand."""
    spec = sys.modules[__name__]
    first = runner.run_node(node, spec, report, **options, logged=False)
    if not first: return first
    doubted = {d['subject']: d['why'] for d in first['decisions'] if d['source'] == 'model' and d['decision'] == 'doubt'}
    if first['method'] != 'model' or not doubted:
        core.log_run(report, node, first)
        return first
    second = runner.run_node(node, spec, report, **{**options, 'rejudge': doubted, 'logged': False}) or {}
    row = core.keep(report, node, _merge_second(node, first, second), logged=False)
    # one line for the run, both passes' time and cost: the first pass's alone counted it twice beside the merged one
    core.log_run(report, node, {**row, **_both(first, second)})
    finish(report, row, inputs(report, project=options.get('project'), lang=options.get('lang', 'en'), cards=options.get('cards'),
                               limit=options.get('limit')))
    return row
