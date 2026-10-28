"""The claims the person's own rules earn (M16.3, M16.5): one card per rule broken, with every place it is broken and
the cause, in their words; when it was said and how many times it came back. A rule guarded by a code pattern or a
test closes only when its guard, run again on the fixed copy, finds nothing (its probe, eaos/analysis/claims/recheck.py);
one guarded by EAOS's detectors names their cards, and closes when the next check finds none of them.

The rules stage (eaos/pipeline/runners/rules.py) ran each pattern and test; a detector's guard is read here, from what
the other detectors found in this same ledger. Each result goes into the rule's record (a break, a hold), once per check.
"""
from . import ledger
from .gather import _located

WORDS = {
    'en': ('Your rule {id} is broken in {count} places: "{words}"', 'You said this on {said_on}', '; it came back {returns} times',
           '; said {said} times', 'Fix every place at once, from its cause, until its guard ({guard}) finds none.'),
    'ar': ('قاعدتك {id} مكسورة في {count} أماكن: «{words}»', 'قلتها في {said_on}', '، ورجعت تنكسر {returns} مرات',
           '، وقلتها {said} مرات', 'أصلح كل الأماكن مرة وحدة من السبب، لين ما يلقى حارسها ({guard}) ولا مكان.'),
}


def _said(row, lang):
    title, said, back, times, fix = WORDS[lang]
    values = {**row, 'count': len(row['places'])}
    text = title.format(**values) + '. ' + said.format(**values)
    if row['returns']: text += back.format(**values)
    if row['said'] > 1: text += times.format(**values)
    return text, fix.format(**values)


def detected(claims, fact_index):
    """What the other detectors found, as a detector guard reads it: [{detector, places, said, card}]."""
    found = []
    for claim in claims:
        places = (claim.get('render') or {}).get('params', {}).get('places') or _located(claim, fact_index) or claim.get('evidence_ids') or []
        found.append({'detector': ledger.detector_of(claim), 'places': [str(p) for p in places], 'said': claim['statement'][:120],
                      'card': claim['id']})
    return found


def results(out, claims, fact_index):
    """Every rule of the check with its result: the stage's pattern and test results, a detector guard's read now."""
    from ..rules import guards
    from ..rules.held import read
    record = read(out)
    rows = record.get('rules') or []
    found = detected(claims, fact_index)
    for row in rows:
        if row['kind'] != 'detector': continue
        guard = _guard_of(record, row['id'])
        result = guards.run(guard, None, None, found)
        row.update(status=result['status'], places=result['places'], found=result['said'],
                   cards=sorted({f['card'] for f in found if any(guards._named(f['detector'], n) for n in guard['detectors'])}))
    return record, rows


def _guard_of(record, ident):
    from ...core.project import rules as registry
    return registry.find(registry.load(registry.Kept(record['workspace'])), ident).get('guard')


def rule_claims(out, claims, fact_index, offset):
    """One card per broken rule, numbered after `offset`; each result written into the rule's record."""
    record, rows = results(out, claims, fact_index)
    if not rows: return []
    from ..rules.held import record as keep
    from ...core.project import rules as registry
    keep(registry.Kept(record['workspace']), rows, f'check:{out.name}')
    made = []
    for row in rows:
        if row['status'] != 'broken': continue
        en, fix_en = _said(row, 'en')
        ar, fix_ar = _said(row, 'ar')
        params = {'kind': row['kind'], 'rule': row['id'], 'en': en, 'ar': ar, 'fix_en': fix_en, 'fix_ar': fix_ar,
                  'place': row['places'][0].split(':')[0] if row['places'] else None, 'places': row['places'],
                  'words': row['words'], 'said_on': row['said_on'], 'returns': row['returns'], 'cards': row.get('cards') or [],
                  'severity': 'high' if row['scope']['kind'] == 'pinned' or row['returns'] else 'medium', 'category': 'reliability'}
        probe = ({'probe_type': 'graph_query', 'specification': {'query': 'rule_broken', 'rule': row['id'], 'guard': _guard_of(record, row['id']),
                                                                 'found': {'status': row['status'], 'places': row['places']}, 'engines': []}} if row['kind'] in ('pattern', 'test') else None)
        made.append(ledger.make(offset + len(made) + 1, en, 'business_rule', 'CONFIRMED',
                                ['static_fact' if row['kind'] != 'test' else 'test_evidence'], ['rules.json'],
                                "The rule's guard, run again, finding nothing.", confidence_ceiling='CONFIRMED',
                                render={'key': 'person_rule', 'params': params}, probe_spec=probe, impact={'scenario': fix_en}))
    return made


def present(specification, sets):
    """A rule card's probe: CONFIRMED while its guard still finds the rule broken on the code read (`sets['rule']`, the
    guard run on the copy by recheck; in the check itself, what its rules stage found)."""
    result = sets.get('rule') or specification.get('found')
    if result is None or result['status'] not in ('broken', 'held'): return 'INCONCLUSIVE', 'the rule\'s guard did not run on this code'
    if result['status'] == 'broken': return 'CONFIRMED', f"the rule is still broken at {', '.join(result['places'][:4])}"
    return 'REFUTED', 'its guard finds the rule broken nowhere'


def said(out):
    """The rules the report says beside the cards: held, and not guarded with why (never pretended)."""
    from ..rules.held import read
    return [{'id': r['id'], 'words': r['words'], 'status': r['status'], 'guard': r['guard'], 'said_on': r['said_on']}
            for r in read(out).get('rules') or [] if r['status'] != 'broken']
