"""studio/history.json: the project over time (contract v2, docs/STUDIO.md D7), read from the ledger (eaos/core/ledger.py) and
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
from ...analysis import model as M

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
    found = scores.get('open') if isinstance(scores.get('open'), dict) else None
    opened = {s: _count(found.get(s)) for s in SEVERITIES} if found else None
    return _score(scores.get('score')), opened


def _score(score):
    """A recorded score as 0..1: a percentage is divided by 100; anything else is None."""
    if not isinstance(score, (int, float)) or isinstance(score, bool): return None
    score = score / 100 if score > 1 else score
    return round(score, 4) if 0 <= score <= 1 else None


def _count(value): return value if isinstance(value, int) and value >= 0 else None


def _whole(value): return value if isinstance(value, int) else None


def _resolved_between(cards, before, at):
    if not before: return None
    return sum(1 for c in cards if c.get('state') == 'resolved' and c.get('at') and before < c['at'] <= at)


def _scan_id(commit, i, seen):
    ident = (commit or '')[:12] or f'scan-{i + 1}'
    if ident in seen: ident = f'{ident}-{i + 1}'        # a check again at the same commit
    seen.add(ident)
    return ident


def _recorded_scan(i, point, checks, now):
    """One check the ledger recorded; the last of them is this check, with its score and open cards."""
    last = i == len(checks) - 1
    recorded_score, recorded_open = _recorded(point)
    total, closed = point.get('total'), point.get('closed')
    commit = point.get('commit') or (now['scan'].get('commit') if last else None)
    return {'id': _scan_id(commit, i, now['seen']),
            'commit': commit, 'branch': now['scan'].get('branch') if last else None, 'at': point['at'],
            'event': point.get('event'), 'score': now['score'] if last else recorded_score,
            'open': now['open'] if last else recorded_open or {s: None for s in SEVERITIES},
            'open_total': _open_total(total, closed), 'closed': _whole(closed), 'total': _whole(total), 'added': _added(i, last, now),
            'resolved': _resolved_between(now['cards'], checks[i - 1]['at'] if i else None, point['at']), 'open_keys': []}


def _open_total(total, closed):
    """The cards a recorded check left open; None when it did not record both counts."""
    return total - closed if isinstance(total, int) and isinstance(closed, int) else None


def _added(i, last, now):
    """The cards a check found new; None where that is not known."""
    # the ledger marks a card a later check found as new, not which check found it: known for a second check only
    return sum(1 for c in now['cards'] if c.get('new')) if i == 1 and last else None


def _this_scan(scan, card_rows, now_score, now_open):
    return {'id': (scan.get('commit') or 'current')[:12], 'commit': scan.get('commit'), 'branch': scan.get('branch'),
            'at': scan.get('at') or '', 'event': 'scan', 'score': now_score, 'open': now_open,
            'open_total': sum(1 for c in card_rows if c.get('state') not in M.CLOSED),
            'closed': sum(1 for c in card_rows if c.get('state') in M.CLOSED), 'total': len(card_rows),
            'added': None, 'resolved': None, 'open_keys': []}


def _progress(points):
    return [{'at': p['at'], 'event': p.get('event') or '', 'closed': p.get('closed'), 'total': p.get('total'),
             'percent': round(p['closed'] / p['total'], 4) if isinstance(p.get('closed'), int) and p.get('total') else None,
             'commit': p.get('commit')}
            for p in points if isinstance(p.get('closed'), int) and isinstance(p.get('total'), int)]


def _point_event(point):
    event = point.get('event')
    if event in SCAN_EVENTS:
        return {'at': point['at'], 'kind': 'scan', 'title': event, 'ref': point.get('commit'), 'count': point.get('total')}
    if event == 'merged':
        return {'at': point['at'], 'kind': 'merge', 'title': event, 'ref': point.get('commit'), 'count': point.get('closed')}
    return None


def _events(points, waves):
    """The checks, the fixes taken in and the batches with a date, in time order."""
    events = [event for event in (_point_event(point) for point in points) if event]
    events += [{'at': wave['merged_at'], 'kind': 'batch', 'title': f"batch {wave.get('number')}", 'ref': wave.get('branch'),
                'count': len(wave.get('kept') or [])} for wave in waves or () if isinstance(wave, dict) and wave.get('merged_at')]
    events.sort(key=lambda e: e['at'])
    return events


def _changed(cards):
    return [{'key': c.get('key') or '', 'id': c.get('id'), 'title': str(c.get('title') or '')[:300], 'state': c.get('state'),
             'at': c.get('at'), 'new': bool(c.get('new')), 'batch': c.get('batch') if isinstance(c.get('batch'), int) else None}
            for c in cards if c.get('state') in M.CLOSED or c.get('new')]


def _ledger_records(ledger):
    """(the ledger's dated history points, its cards); none of either without a ledger."""
    points = [p for p in (ledger or {}).get('history') or [] if isinstance(p, dict) and p.get('at')]
    return points, [c for c in (ledger or {}).get('cards') or [] if isinstance(c, dict)]


def history(scan, score, card_rows, ledger=None, waves=()):
    """The history section's body. scan: {commit, branch, at} of this check; score: its score 0..100 or None;
    card_rows: this check's cards; ledger: eaos.core.ledger.for_report's record, or None."""
    now_open = _open_by_severity(card_rows)
    now_score = None if score is None else round(score / 100, 4)
    points, cards = _ledger_records(ledger)
    checks = [p for p in points if p.get('event') in SCAN_EVENTS]
    now = {'scan': scan, 'cards': cards, 'score': now_score, 'open': now_open, 'seen': set()}
    scans = [_recorded_scan(i, point, checks, now) for i, point in enumerate(checks)]
    if not scans: scans.append(_this_scan(scan, card_rows, now_score, now_open))     # no ledger: this check alone
    progress = _progress(points)
    events = _events(points, waves)
    changed = _changed(cards)
    unscored = sum(1 for s in scans if s['score'] is None)
    missing = [{'id': 'scores', 'state': 'not_measured', 'step': 'NS31.T1', 'count': {'value': unscored, 'src': 'history.json#scans[score=null]'},
                'detail': {'ar': f'{unscored} فحص سابق بلا درجة مسجلة: السجل لا يحفظ درجة كل فحص بعد',
                           'en': f'{unscored} earlier checks with no recorded score: the ledger does not keep each check\'s score yet'}}] if unscored else []
    return {'scans': scans, 'progress': progress, 'events': events, 'cards': changed[:2000], 'missing': missing,
            'src': {'scans': 'ledger.json#history[event in baseline, recheck]; the last: this check',
                    'score': 'model.score of this check; older checks: ledger.json#history[].scores (NS31.T1)',
                    'progress': 'ledger.json#history[].closed / total', 'cards': 'ledger.json#cards[state done, or new]'}}
