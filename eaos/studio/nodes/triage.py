"""The card triage: every open card confirmed, doubted or rejected before it reaches the person (docs/STUDIO.md D11).

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

from . import core
from .. import ideal

VERSION = '1'
LIMIT = {'facts': 4, 'rejudge_facts': 12, 'measurements': 4, 'excerpt': 6, 'line': 200, 'summary': 300}
SEVERITY = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'info': 4}
DETAIL = {'type': 'object', 'additionalProperties': False, 'required': ['falsifier'],
          'properties': {'falsifier': {'type': 'string'}}}
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
it neither shows nor contradicts it (a probe will settle it before the person sees the card); "reject" when it
contradicts it (a false alarm: the card is set aside and its rule is told). `why`: one or two plain sentences naming what
in the evidence decided it. `detail.falsifier`: the observation that would show your decision wrong. `evidence`: the
card id and the fact ids you relied on.

A GOOD ANSWER
Every card decided once. A confirm points at the fact (its message, measurement or how the engine knows) and the code
line that show the problem. A doubt says exactly what is missing or what in the code questions it (a name used
dynamically, a generic name, a number the facts do not give). A reject names the fact or line that contradicts the card.

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
    from ... import indicators
    out = {}
    for row in indicators.facts(report):
        if row.get('id') not in wanted: continue
        value = row.get('value') or {}
        found = [{'name': m.get('name'), 'value': m['value'], 'threshold': m.get('threshold') if _number(m.get('threshold')) else None}
                 for m in value.get('measurements') or [] if isinstance(m, dict) and _number(m.get('value'))]
        if row.get('kind') == 'metric' and _number(value.get('branches')):
            found.append({'name': 'branches', 'value': value['branches'], 'threshold': None})
        if found: out[row['id']] = found
    return out


def _weight(measured):
    """Sort key of a fact: a value over its threshold first (the largest ratio first), then a bare value, then none."""
    ratios = [m['value'] / m['threshold'] for m in measured if m['threshold']]
    if ratios: return (0, -max(ratios))
    return (1, -max(m['value'] for m in measured)) if measured else (2, 0)


def inputs(report, project=None, lang='en', cards=None, limit=None, rejudge=None, **_):
    """The open cards (or those of `cards`), most severe first, each with its facts and their code, those carrying the
    measurement first. `rejudge` ({card: why it was doubted}): only those cards, each with all its facts and its doubt."""
    report = Path(report)
    rows = [c for c in ideal._cards(report) if c.get('state', 'open') not in ('done', 'resolved')]
    if cards: rows = [c for c in rows if c['id'] in set(cards)]
    if rejudge: rows = [c for c in rows if c['id'] in rejudge]
    rows.sort(key=lambda c: (SEVERITY.get(c.get('severity'), 5), c['id']))
    facts = _facts(report)
    cited = {card['id']: [f for f in card.get('evidence') or [] if isinstance(f, str)] for card in rows}
    measured = _measurements(report, {f for ids in cited.values() for f in ids})
    out = []
    for card in rows[:limit] if limit else rows:
        evidence = []
        ordered = sorted(cited[card['id']], key=lambda f: _weight(measured.get(f) or []))
        for fact in ordered[:LIMIT['rejudge_facts' if rejudge else 'facts']]:
            known = facts.get(fact) or {}
            evidence.append({'id': fact, 'summary': known.get('summary'), 'path': known.get('path'), 'line': known.get('line'),
                             'measurements': (measured.get(fact) or [])[:LIMIT['measurements']],
                             'code': _excerpt(project, known.get('path'), known.get('line'))})
        out.append({'id': card['id'], 'title': core.short(card.get('title'), 200), 'kind': card.get('kind'), 'severity': card.get('severity'),
                    'confidence': card.get('confidence'), 'paths': (card.get('paths') or [])[:3], 'evidence': evidence,
                    **({'first_doubt': core.short(rejudge[card['id']], 400)} if rejudge else {})})
    if not out: return None
    return {'project': {'name': (project and Path(project).name) or report.name, 'language': 'Arabic' if lang == 'ar' else 'English'},
            'trust': {'code': core.UNTRUSTED, 'titles': core.UNTRUSTED}, 'cards': out, 'omitted': len(rows) - len(out), 'lang': lang,
            **({'rejudge': True} if rejudge else {})}


BATCH = 40


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
    """A verdict must stand on the card's own evidence: the card itself or one of its facts."""
    card = next(c for c in data['cards'] if c['id'] == decision['subject'])
    own = {card['id']} | {e['id'] for e in card['evidence']}
    return None if own & set(decision['evidence']) else "none of its evidence is this card's"


def finish(report, record, data):
    """The verdicts, the probe requests of the doubtful cards and the library's feedback of the rejected ones."""
    from ...probes import probe
    folder = core.folder_of(report, record['node'])
    folder.mkdir(parents=True, exist_ok=True)
    cards = {c['id']: c for c in data['cards']}
    claims = _claims(report)
    route = {s: r['decision'] for r in record['routes'] for s in r['subjects']}
    verdicts = [{'card': d['subject'], 'decision': route[d['subject']], 'kind': cards[d['subject']]['kind'],
                 'severity': cards[d['subject']]['severity'], 'confidence': d['confidence'], 'why': d['why'],
                 'evidence': d['evidence'], 'source': d['source'], 'rejudged': 'first_doubt' in (d.get('detail') or {})}
                for d in record['decisions']]
    doubted = [v for v in verdicts if v['decision'] == 'doubt']
    probes = [probe(i + 1, claims.get(v['card']) or v['card'], 'falsification',
                    {'card': v['card'], 'question': v['why'], 'falsifier': next((d['detail'].get('falsifier') for d in record['decisions']
                                                                               if d['subject'] == v['card']), None), 'from': 'card_triage'})
              for i, v in enumerate(doubted)]
    feedback = [{'card': v['card'], 'kind': v['kind'], 'why': v['why'], 'evidence': v['evidence']} for v in verdicts if v['decision'] == 'reject']
    body = {'schema_version': 1, 'at': record['at'], 'method': record['method'], 'assistant': record['assistant'], 'model': record['model'],
            'verdicts': verdicts, 'counts': {r['decision']: len(r['subjects']) for r in record['routes']}, 'by_kind': by_kind(verdicts),
            'omitted': data['omitted']}
    for name, value in (('verdicts.json', body), ('probes.json', {'schema_version': 1, 'at': record['at'], 'probes': probes}),
                        ('library-feedback.json', {'schema_version': 1, 'at': record['at'], 'rejected': feedback})):
        (folder / name).write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


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



def run(node, report, **options):
    """The triage, then a second look at the cards it doubted, each with every fact it stands on: the second verdict
    replaces the doubt (its detail keeps `first_doubt`), and a card doubted again stays doubted. Without a second answer
    the first verdicts stand."""
    spec = sys.modules[__name__]
    first = core.run_node(node, spec, report, **options)
    if not first or first['method'] != 'model': return first
    doubted = {d['subject']: d['why'] for d in first['decisions'] if d['source'] == 'model' and d['decision'] == 'doubt'}
    if not doubted: return first
    second = core.run_node(node, spec, report, **{**options, 'rejudge': doubted})
    again = {d['subject']: d for d in (second or {}).get('decisions') or []
             if (second or {}).get('method') == 'model' and d['source'] == 'model'}
    decisions = [{**again[d['subject']], 'detail': {**(again[d['subject']].get('detail') or {}), 'first_doubt': d['why']}}
                 if d['subject'] in again else d for d in first['decisions']]
    merged = {**first, 'decisions': decisions, 'routes': core.routes(node, decisions),
              'dropped': first['dropped'] + ((second or {}).get('dropped') or [] if again else []),
              'calls': (first.get('calls') or 0) + ((second or {}).get('calls') or 0)}
    row = core.keep(report, node, merged)
    finish(report, row, inputs(report, project=options.get('project'), lang=options.get('lang', 'en'), cards=options.get('cards'),
                               limit=options.get('limit')))
    return row
