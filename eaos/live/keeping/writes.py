"""The saves measured (M14.2): what the app's pages send on their own (eaos/templates/screens/writes.mjs), read before
and after the copy was filled to a real size, and what of it is a whole state sent for a small change.

    capture(base, pages, storage_state)   {pages: [{path, writes, reads}]} or {error}
    sorted_out(before, after)              [{path, method, page, kind, bytes, ...}]: the saves worth a card:
        resends     it sends back every record the page read (three or more): the whole of a collection for one change
        grows       the same save sends GROW times more once the data grew: it carries the data, not the change
        large       one save of more than LARGE bytes
        many        one page load sends more than MANY writes
"""
from pathlib import Path

from ..screens.audit import _node, missing, toolchain

LARGE, GROW, GROW_FLOOR, MANY = 128 * 1024, 3, 16 * 1024, 5


def capture(base, pages, storage_state=None):
    absent = missing('playwright')
    if absent: return {'error': absent}
    config = {'base': base, 'pages': list(pages), 'modules': {'playwright': str(toolchain.home() / 'node/node_modules')}}
    if storage_state and Path(storage_state).is_file(): config['storage_state'] = str(storage_state)   # no one signed in: none
    result, error = _node('writes.mjs', config, 900)
    return result or {'error': error}


def _resends(page, write):
    """The read of the same page whose every record the write sends back, or None."""
    sent = set(write.get('ids') or ())
    return next((read for read in page.get('reads') or [] if len(read['ids']) >= 3 and set(read['ids']) <= sent), None)


def _row(page, write, kind, **more):
    return {'page': page['path'], 'path': write['path'], 'method': write['method'], 'bytes': write['bytes'], 'kind': kind,
            'compressed': bool(write.get('encoding')), 'ms': write.get('ms'), **more}


def _of(page):
    """The saves of one page load worth a card."""
    out = []
    for write in page.get('writes') or []:
        read = _resends(page, write)
        if read: out.append(_row(page, write, 'resends', read=read['path'], records=len(read['ids'])))
        elif write['bytes'] > LARGE: out.append(_row(page, write, 'large'))
    if len(page.get('writes') or []) > MANY:
        out.append({'page': page['path'], 'path': page['writes'][0]['path'], 'method': page['writes'][0]['method'], 'kind': 'many',
                    'count': len(page['writes']), 'bytes': sum(w['bytes'] for w in page['writes'])})
    return out


def _sizes(record):
    """{(page, method, address): bytes} of the saves of a capture."""
    return {(p['path'], w['method'], w['path']): w['bytes'] for p in record.get('pages') or [] for w in p.get('writes') or []}


def _grown(before, after):
    """Saves the same page sends again once the data grew, GROW times bigger."""
    first = _sizes(before)
    return [_row(page, write, 'grows', before=first[key]) for page in after.get('pages') or [] for write in page.get('writes') or []
            if (key := (page['path'], write['method'], write['path'])) in first and write['bytes'] >= max(GROW_FLOOR, GROW * first[key])]


def sorted_out(before, after=None):
    """One row per save and kind of what is wrong with it, with every page that sends it (`pages`)."""
    rows = [row for page in (after or before).get('pages') or [] for row in _of(page)]
    rows += _grown(before, after) if after else []
    kept = {}
    for row in rows:
        same = kept.setdefault((row['method'], row['path'], row['kind']), dict(row, pages=[]))
        same['pages'].append(row['page'])
    return list(kept.values())
