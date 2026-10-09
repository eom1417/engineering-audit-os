"""studio/history.json: the project over time (contract v2, docs/STUDIO.md D7), read from the ledger (eaos/ledger.py) and
the check in hand; nothing is estimated.

- scans: every check the ledger recorded (its `baseline` and `recheck` points), oldest first, with the cards open and
  closed at that moment; the last one is this report, so it also carries the score and the open cards by severity.
  An older check carries them only when the ledger recorded them (`scores` on its point, NS31.T1); until then they are
  null, never guessed. Without a ledger (a check run outside a guided session) there is one scan: this one.
- progress: every point of the ledger (checks, and fixes taken in), with closed ÷ total: the line of "are we getting
  better" that exists even before a second check.
- events: the checks, the fixes taken in and the batches with a date, in time order.
- cards: the ledger's cards that closed or that a later check found new, with when, so two scans can be compared.
"""
from . import model as M

SEVERITIES = ('critical', 'high', 'medium', 'low', 'info')
SCAN_EVENTS = {'baseline', 'recheck'}


def _open_by_severity(card_rows):
    out = {s: 0 for s in SEVERITIES}
    for card in card_rows:
        if card.get('state') not in M.CLOSED and card.get('severity') in out: out[card['severity']] += 1
    return out


def _recorded(point):
    """(score 0..1 or None, open by severity or None) a ledger point recorded for its check, when it did (NS31.T1)."""
    scores = point.get('scores') if isinstance(point.get('scores'), dict) else {}
    score = scores.get('score')
    if isinstance(score, (int, float)) and not isinstance(score, bool):
        score = score / 100 if score > 1 else score
        score = round(score, 4) if 0 <= score <= 1 else None
    else: score = None
    found = scores.get('open') if isinstance(scores.get('open'), dict) else None
    opened = {s: found.get(s) if isinstance(found.get(s), int) and found.get(s) >= 0 else None for s in SEVERITIES} if found else None
    return score, opened


def history(scan, score, card_rows, ledger=None, waves=()):
    """The history section's body. scan: {commit, branch, at} of this check; score: its score 0..100 or None;
    card_rows: this check's cards; ledger: eaos.ledger.for_report's record, or None."""
    now_open = _open_by_severity(card_rows)
    now_score = None if score is None else round(score / 100, 4)
    points = [p for p in (ledger or {}).get('history') or [] if isinstance(p, dict) and p.get('at')]
    cards = [c for c in (ledger or {}).get('cards') or [] if isinstance(c, dict)]
    checks = [p for p in points if p.get('event') in SCAN_EVENTS]
    scans, seen = [], set()
    for i, point in enumerate(checks):
        last = i == len(checks) - 1
        recorded_score, recorded_open = _recorded(point)
        before = checks[i - 1]['at'] if i else None
        resolved = (sum(1 for c in cards if c.get('state') == 'resolved' and c.get('at') and before < c['at'] <= point['at'])
                    if before else None)
        total, closed = point.get('total'), point.get('closed')
        commit = point.get('commit') or (scan.get('commit') if last else None)
        ident = (commit or '')[:12] or f'scan-{i + 1}'
        if ident in seen: ident = f'{ident}-{i + 1}'        # a check again at the same commit
        seen.add(ident)
        scans.append({'id': ident,
                      'commit': commit, 'branch': scan.get('branch') if last else None, 'at': point['at'],
                      'event': point.get('event'), 'score': now_score if last else recorded_score,
                      'open': now_open if last else recorded_open or {s: None for s in SEVERITIES},
                      'open_total': total - closed if isinstance(total, int) and isinstance(closed, int) else None,
                      'closed': closed if isinstance(closed, int) else None, 'total': total if isinstance(total, int) else None,
                      # the ledger marks a card a later check found as new, not which check found it: known for a second check only
                      'added': sum(1 for c in cards if c.get('new')) if i == 1 and last else None,
                      'resolved': resolved, 'open_keys': []})
    if not scans:                                    # no ledger: this check alone
        scans.append({'id': (scan.get('commit') or 'current')[:12], 'commit': scan.get('commit'), 'branch': scan.get('branch'),
                      'at': scan.get('at') or '', 'event': 'scan', 'score': now_score, 'open': now_open,
                      'open_total': sum(1 for c in card_rows if c.get('state') not in M.CLOSED),
                      'closed': sum(1 for c in card_rows if c.get('state') in M.CLOSED), 'total': len(card_rows),
                      'added': None, 'resolved': None, 'open_keys': []})
    progress = [{'at': p['at'], 'event': p.get('event') or '', 'closed': p.get('closed'), 'total': p.get('total'),
                 'percent': round(p['closed'] / p['total'], 4) if isinstance(p.get('closed'), int) and p.get('total') else None,
                 'commit': p.get('commit')}
                for p in points if isinstance(p.get('closed'), int) and isinstance(p.get('total'), int)]
    events = []
    for point in points:
        event = point.get('event')
        if event in SCAN_EVENTS:
            events.append({'at': point['at'], 'kind': 'scan', 'title': event, 'ref': point.get('commit'), 'count': point.get('total')})
        elif event == 'merged':
            events.append({'at': point['at'], 'kind': 'merge', 'title': event, 'ref': point.get('commit'), 'count': point.get('closed')})
    for wave in waves or ():
        if isinstance(wave, dict) and wave.get('merged_at'):
            events.append({'at': wave['merged_at'], 'kind': 'batch', 'title': f"batch {wave.get('number')}", 'ref': wave.get('branch'),
                           'count': len(wave.get('kept') or [])})
    events.sort(key=lambda e: e['at'])
    changed = [{'key': c.get('key') or '', 'id': c.get('id'), 'title': str(c.get('title') or '')[:300], 'state': c.get('state'),
                'at': c.get('at'), 'new': bool(c.get('new')), 'batch': c.get('batch') if isinstance(c.get('batch'), int) else None}
               for c in cards if c.get('state') in M.CLOSED or c.get('new')]
    unscored = sum(1 for s in scans if s['score'] is None)
    missing = [{'id': 'scores', 'state': 'not_measured', 'step': 'NS31.T1', 'count': {'value': unscored, 'src': 'history.json#scans[score=null]'},
                'detail': {'ar': f'{unscored} فحص سابق بلا درجة مسجلة: السجل لا يحفظ درجة كل فحص بعد',
                           'en': f'{unscored} earlier checks with no recorded score: the ledger does not keep each check\'s score yet'}}] if unscored else []
    return {'scans': scans, 'progress': progress, 'events': events, 'cards': changed[:2000], 'missing': missing,
            'src': {'scans': 'ledger.json#history[event in baseline, recheck]; the last: this check',
                    'score': 'model.score of this check; older checks: ledger.json#history[].scores (NS31.T1)',
                    'progress': 'ledger.json#history[].closed / total', 'cards': 'ledger.json#cards[state in done, resolved, or new]'}}
