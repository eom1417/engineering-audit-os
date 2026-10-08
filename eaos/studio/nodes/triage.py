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
LIMIT = {'cards': 400, 'facts': 4, 'excerpt': 6, 'line': 200, 'summary': 300}
SEVERITY = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'info': 4}
DETAIL = {'type': 'object', 'additionalProperties': False, 'required': ['falsifier'],
          'properties': {'falsifier': {'type': 'string'}}}
TASK = ('You are the card triage of EAOS, an engineering audit. Each card below is a problem EAOS\'s engines found in this '
        'project, with the facts it stands on and the code at each fact. Before the person sees a card, decide for each: '
        '"confirm" when its evidence really shows the problem it names; "doubt" when the evidence does not settle it (a '
        'probe will, before the person sees it); "reject" when the evidence contradicts it (a false alarm: the card is set '
        'aside and its rule is told). Judge only from the evidence given; a card whose evidence you cannot see is a doubt, '
        'not a confirm. In `detail.falsifier`, write what would show your decision wrong. Cite in `evidence` the card id '
        'and the fact ids you relied on.')


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


def inputs(report, project=None, lang='en', cards=None, limit=None, **_):
    """The open cards (or those of `cards`), most severe first, each with its facts and their code."""
    report = Path(report)
    rows = [c for c in ideal._cards(report) if c.get('state', 'open') not in ('done', 'resolved')]
    if cards: rows = [c for c in rows if c['id'] in set(cards)]
    rows.sort(key=lambda c: (SEVERITY.get(c.get('severity'), 5), c['id']))
    cap = limit or LIMIT['cards']
    facts = _facts(report)
    out = []
    for card in rows[:cap]:
        evidence = []
        for fact in [f for f in card.get('evidence') or [] if isinstance(f, str)][:LIMIT['facts']]:
            known = facts.get(fact) or {}
            evidence.append({'id': fact, 'summary': known.get('summary'), 'path': known.get('path'), 'line': known.get('line'),
                             'code': _excerpt(project, known.get('path'), known.get('line'))})
        out.append({'id': card['id'], 'title': core.short(card.get('title'), 200), 'kind': card.get('kind'), 'severity': card.get('severity'),
                    'confidence': card.get('confidence'), 'paths': (card.get('paths') or [])[:3], 'evidence': evidence})
    if not out: return None
    return {'project': {'name': (project and Path(project).name) or report.name, 'language': 'Arabic' if lang == 'ar' else 'English'},
            'trust': {'code': core.UNTRUSTED, 'titles': core.UNTRUSTED}, 'cards': out, 'omitted': max(0, len(rows) - cap), 'lang': lang}


def subjects(data):
    return [c['id'] for c in data['cards']]


def known(report, data):
    return ideal.known_ids(report)


def rules(data):
    return {c['id']: ([c['id']] + [e['id'] for e in c['evidence']], 'The engines wrote this card; no assistant reviewed it.',
                      float(c['confidence']) if isinstance(c.get('confidence'), (int, float)) and 0 <= c['confidence'] <= 1 else 0.5, {})
            for c in data['cards']}


def prompt(data):
    return (TASK + '\n\n' + core.rules_of_the_answer(data['lang']) + '\n\nAnswer with the JSON object of the schema only.\n\n'
            'The bundle:\n' + json.dumps({k: v for k, v in data.items() if k != 'lang'}, ensure_ascii=False))


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
                 'evidence': d['evidence'], 'source': d['source']} for d in record['decisions']]
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


def precision(report):
    """by_kind of the last triage of `report`, or {} when it was not triaged by a model."""
    body = core.load(Path(report) / 'nodes/card_triage/verdicts.json', {}) or {}
    return body.get('by_kind') or {} if body.get('method') == 'model' else {}


def run(node, report, **options):
    return core.run_node(node, sys.modules[__name__], report, **options)
