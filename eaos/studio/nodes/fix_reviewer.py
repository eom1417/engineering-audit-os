"""The fix reviewer: after a batch of fixes, the diff and the checks read, and each card accepted, retried or asked
(docs/STUDIO.md D11).

It reads one batch (eaos/waves.py `finish_batch`: `wave.json` with the cards kept and the ones that failed and why, and
the batch's patches, marked as untrusted data) and decides for each card: "accept" (the diff does what the card asks
and the checks hold), "retry" (the fix is wrong or incomplete) or "ask" (it needs the person). The gates stay the
judge: a card they failed cannot be accepted, whatever the answer says. "accept" is a recommendation only: the person
still takes the branch in (accept) or throws it away (undo). The review is written to nodes/fix_reviewer/review.json.
"""
import json
import sys
from pathlib import Path

from . import core
from .. import ideal

VERSION = '1'
LIMIT = {'diff': 60000, 'cards': 60}
DETAIL = {'type': 'object', 'additionalProperties': False, 'required': ['concerns'],
          'properties': {'concerns': {'type': 'array', 'items': {'type': 'string'}}}}
TASK = ('You are the fix reviewer of EAOS, an engineering audit. Below is one batch of fixes EAOS made in an isolated copy '
        'of this project: each card it tried, whether the project\'s checks and the card\'s own acceptance kept it or failed '
        'it (and why), and the diff of the kept changes. Decide for each card: "accept" when the diff does what the card asks '
        'and nothing else, "retry" when the fix is wrong, incomplete or changes more than the card asks, or "ask" when it '
        'needs a choice from the person. A card the checks failed is never "accept". Put what worries you in '
        '`detail.concerns`. Cite in `evidence` the card id and the fact ids you relied on.')


def _cards(report, ids):
    tasks = {t['id']: t for t in (core.load(Path(report) / 'plan.json', {}) or {}).get('tasks') or [] if isinstance(t, dict) and t.get('id')}
    cards = {c['id']: c for c in ideal._cards(report)}
    out = []
    for card in ids:
        task, row = tasks.get(card) or {}, cards.get(card) or {}
        facts = [f for f in ((task.get('evidence') or {}).get('fact_ids') if isinstance(task.get('evidence'), dict) else None)
                 or row.get('evidence') or [] if isinstance(f, str)][:6]
        out.append({'id': card, 'title': core.short(task.get('title') or row.get('title'), 200), 'kind': task.get('kind') or row.get('kind'),
                    'paths': (task.get('paths') or row.get('paths') or [])[:4], 'facts': facts})
    return out


def inputs(report, project=None, lang='en', wave=None, **_):
    """The batch of `wave` (its folder), or None when no batch is given."""
    if not wave: return None
    wave = Path(wave)
    summary = core.load(wave / 'wave.json')
    if not isinstance(summary, dict): return None
    kept, failed = list(summary.get('kept') or []), dict(summary.get('failed') or {})
    ids = (kept + [c for c in failed if c not in kept])[:LIMIT['cards']]
    if not ids: return None
    diff = ''.join(path.read_text(encoding='utf-8', errors='replace') for path in sorted(wave.glob('*.patch')))
    cards = _cards(report, ids)
    for card in cards:
        card['gates'] = 'kept' if card['id'] in kept else f"failed: {core.short(failed.get(card['id']), 300)}"
    return {'lang': lang, 'wave': summary.get('wave'), 'branch': summary.get('branch'), 'stat': summary.get('stat'), 'cards': cards,
            'diff': {'trust': core.UNTRUSTED, 'text': diff[:LIMIT['diff']], 'cut': max(0, len(diff) - LIMIT['diff'])}}


def subjects(data):
    return [c['id'] for c in data['cards']]


def known(report, data):
    return ideal.known_ids(report) | set(subjects(data))


def rules(data):
    return {c['id']: ([c['id'], *c['facts']], f"The gates {'kept' if c['gates'] == 'kept' else 'failed'} this fix.",
                      0.7 if c['gates'] == 'kept' else 0.5, {'concerns': [] if c['gates'] == 'kept' else [c['gates']]})
            for c in data['cards']}


def check(data, decision):
    card = next(c for c in data['cards'] if c['id'] == decision['subject'])
    if decision['decision'] == 'accept' and card['gates'] != 'kept': return 'the gates failed this fix, so it cannot be accepted'
    return None


def prompt(data):
    return core.prompt(TASK, data)


def finish(report, record, data):
    route = {s: r['decision'] for r in record['routes'] for s in r['subjects']}
    cards = {c['id']: c for c in data['cards']}
    rows = [{'card': d['subject'], 'decision': route[d['subject']], 'gates': cards[d['subject']]['gates'], 'why': d['why'],
             'concerns': (d.get('detail') or {}).get('concerns') or [], 'source': d['source']} for d in record['decisions']]
    folder = core.folder_of(report, record['node'])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'review.json').write_text(json.dumps({'schema_version': 1, 'at': record['at'], 'method': record['method'], 'wave': data['wave'],
                                                    'branch': data['branch'], 'cards': rows}, ensure_ascii=False, indent=1) + '\n',
                                        encoding='utf-8')


def run(node, report, **options):
    return core.run_node(node, sys.modules[__name__], report, **options)
