"""Two people editing one record (M14.4): through the running app's own API, as the session of the run, the record is
read twice, changed by the first reader in one field and by the second, from the copy it read before, in another. When
the first change is gone afterwards and the second write was taken without a conflict (409 or 412), an edit is lost
silently: a card, with the requests as its evidence.

    probe(base, routes, cookie)   [{route, record, lost, why?, steps}]
A route is a PUT or PATCH with a parameter (/api/orders/:id); its record is the first of its collection's GET. A
session kept in localStorage (a bearer token) is not sent: such an API is said as not tried.
"""
import json
import re
import urllib.error
import urllib.request

from ...core.system.web import opened
from ...core.system.files import read_json

PARAM = re.compile(r'(:\w+|\{\w+\}|\[\w+\]|<\w+(?::\w+)?>)$')
TRIED = 3
FIRST, SECOND = 'eaos-first-change', 'eaos-second-change'


def cookie_of(state):
    """The Cookie header of a Playwright storage state (the run's session), or ''."""
    cookies = ((read_json(state) if state else None) or {}).get('cookies') or []
    return '; '.join(f"{c['name']}={c['value']}" for c in cookies)


def _call(url, cookie, method='GET', body=None):
    """(status, parsed JSON or None) of one request to the app."""
    data = json.dumps(body).encode('utf-8') if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={'Cookie': cookie, 'Content-Type': 'application/json'})
    try:
        with opened(request, timeout=20) as answer: text, status = answer.read().decode('utf-8', 'replace'), answer.status
    except urllib.error.HTTPError as problem: return problem.code, None
    except (OSError, ValueError): return 0, None
    try: return status, json.loads(text)
    except ValueError: return status, None


def _first_record(base, collection, cookie):
    status, value = _call(base + collection, cookie)
    rows = value if isinstance(value, list) else next((v for v in (value or {}).values() if isinstance(v, list)), []) if isinstance(value, dict) else []
    return next((row for row in rows if isinstance(row, dict) and any(k in row for k in ('id', 'uuid', '_id'))), None)


def _fields(record):
    """Two text fields of the record that are not its keys, or one twice."""
    names = [k for k, v in record.items() if isinstance(v, str) and not re.search(r'(^|_)(id|uuid|owner|user|email|created|updated)', k, re.I)]
    return (names[0], names[1]) if len(names) > 1 else (names[0], names[0]) if names else None


def _try(base, method, route, cookie):
    collection = PARAM.sub('', route).rstrip('/')
    record = _first_record(base, collection, cookie)
    fields = record and _fields(record)
    if not fields: return {'route': route, 'lost': None, 'why': f'no record with a text field from GET {collection}'}
    key = next(k for k in ('id', 'uuid', '_id') if k in record)
    url = f"{base}{collection}/{record[key]}"
    stale = dict(record)
    one = _call(url, cookie, method, {**record, fields[0]: FIRST})
    two = _call(url, cookie, method, {**stale, fields[1]: SECOND})
    after = _call(url, cookie)[1] or _first_record(base, collection, cookie) or {}
    _call(url, cookie, method, record)                                       # the record as it was
    if not 200 <= one[0] < 300: return {'route': route, 'lost': None, 'why': f'the first change was refused ({one[0]})'}
    lost = two[0] not in (409, 412) and after.get(fields[0]) != FIRST and fields[0] != fields[1]
    return {'route': route, 'record': f'{collection}/{record[key]}', 'field': fields[0], 'lost': lost,
            'steps': [f'GET {collection}', f'{method} {fields[0]}={FIRST} -> {one[0]}', f'{method} (stale) {fields[1]}={SECOND} -> {two[0]}',
                      f"GET -> {fields[0]}={after.get(fields[0])!r}"]}


def probe(base, routes, cookie):
    """The lost-update trial on each PUT or PATCH route with a parameter, TRIED at most: routes as (method, path)."""
    return [_try(base.rstrip('/'), method, path, cookie) for method, path in routes[:TRIED]]
