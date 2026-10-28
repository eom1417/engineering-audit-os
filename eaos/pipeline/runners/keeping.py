"""How the data is saved, travels and is kept (M14), on the shared app after every other page stage: the saves the pages
send, the copy's database filled to a real size and the saves read again, how that database stores its data, the
restore drill, the files the server wrote, and two edits of one record. Each part is its own: one that fails says why
in live/keeping.json and the others still run."""

from .live_app import _keep, _live, sessions
from ...facts.store import facts
from ...live.keeping import database, files, lost_update, restore, stored, synthetic, volume, writes
from ...core.system.files import read_json
from ...analysis.assessments.data_keeping import unmeasured

PAGES = 5
EDITS = ('PUT', 'PATCH')


def _pages(context):
    """The pages to read the saves of: the crawl's, one per template, PAGES at most; else the entry."""
    pages = (read_json(context.out / 'live/crawl.json') or {}).get('pages') or []
    return pages[:PAGES] or ['/']


def edit_routes(out):
    """(method, route) of every PUT or PATCH endpoint with a parameter the code declares."""
    rows = {(f['value'].get('http_method'), f['value'].get('route')) for f in facts(out, 'entry_point')
            if f['value'].get('surface') == 'http' and f['value'].get('http_method') in EDITS and f['value'].get('route')}
    return sorted(row for row in rows if lost_update.PARAM.search(row[1]))


def _part(record, name, work):
    """record[name] = work(), or why it could not be done."""
    try: record[name] = work()
    except Exception as problem: record[name] = {'error': f'{type(problem).__name__}: {problem}'[:300]}  # one part never stops the others


def _database_parts(record, live, db, context, saves):
    record['database'] = {'kind': db.kind, 'tables': {t: db.count(t) for t in db.tables()}}
    _part(record, 'volume', lambda: {**volume.fill(db), **synthetic.fill_empty(db)})   # grown, then a year where it was empty
    _part(record, 'writes_at_volume', lambda: saves())
    _part(record, 'stored', lambda: {'columns': stored.columns(db), 'shared': stored.shared(db)})
    _part(record, 'restore', lambda: restore.drill(live, db, context.target))


def keeping(context):
    _live(context)
    live, base, made = sessions(context)
    state = made[0][1] if made else None

    def saves(): return writes.capture(base, _pages(context), state)
    record = {'schema_version': 1}
    _part(record, 'writes_before', saves)
    try: db = database.open_run(live)
    except Exception as problem: db, record['database'] = None, {'why': f'its database could not be opened: {problem}'[:300]}  # noqa: BLE001

    if db: _database_parts(record, live, db, context, saves)
    else: record.setdefault('database', {'why': "the app runs on no database of the run's own (its PostgreSQL or an SQLite file)"})
    record['writes'] = writes.sorted_out(record.get('writes_before') or {}, record.get('writes_at_volume'))
    _part(record, 'files', lambda: files.written(live.sandbox.copy, live.started_at, getattr(db, 'path', None)))
    _part(record, 'lost_update', lambda: lost_update.probe(base, edit_routes(context.out), lost_update.cookie_of(state)))
    for heavy in ('writes_before', 'writes_at_volume'):
        if isinstance(record.get(heavy), dict): record[heavy] = {'pages': len(record[heavy].get('pages') or []), 'error': record[heavy].get('error')}
    _keep(context, 'keeping.json', record)
    return {'saves': len(record['writes']), 'database': record['database'].get('kind'), 'files': len(record.get('files') or []),
            'unmeasured': unmeasured(record)}       # what the copy could not read: a gap of the coverage ledger, in red (M15.0)
