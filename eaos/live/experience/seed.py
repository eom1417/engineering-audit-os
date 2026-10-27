"""The bulk history of the simulated users seeded into the copy's own database (M10.2), before any of them acts.

The rows are data.json's `seed` (eaos/analysis/experience/domain_data.py), already plain and bounded. They go only into
a database the run made: the run's own PostgreSQL (eaos/core/system/local_db.py) when the run profile declares one, or
an SQLite file inside the run's folder (the copy's). Any other database, the person's above all, is refused, and so is a
table or a column that database does not have. No value is ever written into the SQL text: PostgreSQL gets every name
and value as a psql variable (psql quotes them itself), SQLite gets its values bound and its names checked against the
table's own columns. A MySQL, MongoDB or hosted database is not covered: the run never makes one.

    seed(data, setup)   {seeded, database, tables: [{table, seeded, error?}]}, or {seeded: 0, why}

A database is seeded once: the run's folder keeps a mark of each database it seeded (SEEDED, by the database's name or
file), so running the simulation again on the same copy does not add the history twice.
"""
import json
import os
import re
import sqlite3
import tempfile
from pathlib import Path

from ...core.system.process import run_command

INSERTED = re.compile(r'^INSERT 0 (\d+)$', re.M)
SEEDED = 'experience-seeded.json'          # in the run's folder: {database: {seeded}}, each database seeded once


def _profile(runtime):
    try: return json.loads((Path(runtime) / 'run.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): return {}


def _text(value):
    return ('true' if value else 'false') if isinstance(value, bool) else str(value)


def _postgres_table(psql, url, item):
    """One table's rows through psql: every name and value a psql variable, :"name" an identifier, :'name' a literal."""
    schema, _, name = item['table'].rpartition('.')
    argv, lines = [str(psql), url, '-X', '-v', f'schema={schema or "public"}', '-v', f'table={name}'], []
    for r, row in enumerate(item['rows']):
        for c, (column, value) in enumerate(row.items()):
            argv += ['-v', f'c{r}_{c}={column}', '-v', f'v{r}_{c}={_text(value)}']
        names = ', '.join(f':"c{r}_{c}"' for c in range(len(row)))
        values = ', '.join(f":'v{r}_{c}'" for c in range(len(row)))
        # only psql variable references are written: psql quotes every name (:"x") and value (:'x') itself
        lines.append(f'insert into :"schema".:"table" ({names}) values ({values});')  # nosec B608
    with tempfile.NamedTemporaryFile('w', suffix='.sql', encoding='utf-8') as script:
        script.write('\n'.join(lines) + '\n')
        script.flush()
        done = run_command(argv + ['-f', script.name], 300, env={**os.environ, 'PGOPTIONS': '-c client_min_messages=warning'})
    seeded = sum(int(n) for n in INSERTED.findall(done.stdout))
    error = next((line for line in done.stderr.splitlines() if 'ERROR' in line), None)
    return {'table': item['table'], 'seeded': seeded, **({'error': error[:200]} if error else {})}


def _postgres(seed, runtime, name):
    from ...core.system.local_db import LocalPostgres
    server = LocalPostgres(runtime)
    state = server.running()
    if not state: return {'seeded': 0, 'why': "the run's own PostgreSQL is not running"}
    url, psql = server.url(state, name), Path(state['bin']) / 'psql'
    tables = [_postgres_table(psql, url, item) for item in seed]
    return {'seeded': sum(t['seeded'] for t in tables), 'database': 'postgres', 'tables': tables}


def _quoted(name):
    return '"' + name.replace('"', '""') + '"'


def _insert(db, table, row, own):
    """(rows inserted, error or None) of one row: its names the table's own columns, quoted, its values bound."""
    names = [name for name in row if name in own]
    if not names: return 0, None
    # the names are the table's own columns (pragma_table_info), quoted; the values are bound
    statement = f"insert into {_quoted(table)} ({', '.join(map(_quoted, names))}) values ({', '.join('?' * len(names))})"  # nosec B608
    try: return db.execute(statement, [row[name] for name in names]).rowcount, None  # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query -- sqlite3, not SQLAlchemy: the names are the table's own columns, quoted, the values bound
    except sqlite3.Error as problem: return 0, str(problem)[:200]


def _sqlite_table(db, item):
    """One table's rows, its names checked against the table's own columns."""
    own = {row[0] for row in db.execute('select name from pragma_table_info(?)', (item['table'],))}
    if not own: return {'table': item['table'], 'seeded': 0, 'error': 'the database has no such table'}
    done = [_insert(db, item['table'], row, own) for row in item['rows']]
    error = next((error for _, error in done if error), None)
    return {'table': item['table'], 'seeded': sum(n for n, _ in done), **({'error': error} if error else {})}


def _sqlite(seed, runtime, file):
    path = Path(file).resolve()
    if not path.is_relative_to(Path(runtime).resolve()): return {'seeded': 0, 'why': "the SQLite file is not inside the run's own folder"}
    if not path.is_file(): return {'seeded': 0, 'why': 'the SQLite file of the copy does not exist yet'}
    db = sqlite3.connect(path)
    try:
        with db: tables = [_sqlite_table(db, item) for item in seed]
    finally:
        db.close()
    return {'seeded': sum(t['seeded'] for t in tables), 'database': 'sqlite', 'tables': tables}


def _marks(runtime):
    try: return json.loads((Path(runtime) / SEEDED).read_text(encoding='utf-8'))
    except (OSError, ValueError): return {}


def _once(runtime, which, seeding):
    """`seeding()` done unless the run's folder marks database `which` seeded already; marked when it seeded rows."""
    marks = _marks(runtime)
    if which in marks: return {'seeded': 0, 'why': f'the history is already in this run\'s database ({which})', 'already': True}
    done = seeding()
    if done.get('seeded'):
        (Path(runtime) / SEEDED).write_text(json.dumps({**marks, which: {'seeded': done['seeded']}}, indent=1) + '\n', encoding='utf-8')
    return done


def _into(rows, runtime, setup):
    """The rows seeded into the database the run's profile declares, when it is the run's own: the run's PostgreSQL
    database named as the run named the copy's (its profile's name, then `apart`), or the copy's SQLite file."""
    database = _profile(runtime).get('database') or {}
    if database.get('kind') == 'postgres':
        name = '_'.join(filter(None, (database.get('name'), setup.get('apart'))))
        return _once(runtime, f'postgres:{name}', lambda: _postgres(rows, runtime, name))
    if database.get('kind') == 'sqlite' and setup.get('database'):
        return _once(runtime, f"sqlite:{Path(setup['database']).resolve()}", lambda: _sqlite(rows, runtime, setup['database']))
    return {'seeded': 0, 'why': "the app runs on no database of the run's own (only the run's PostgreSQL or an SQLite file "
                                'inside the run are seeded; MySQL, MongoDB and hosted databases are not covered)'}


def seed(data, setup):
    """The `seed` rows of data.json inserted into the run's own database. `setup`: {runtime: the run's folder (its
    run.json profile), database: the copy's SQLite file when the app keeps one, apart: the run's own suffix}."""
    rows = [item for item in data.get('seed') or [] if item.get('table') and item.get('rows')]
    if not rows: return {'seeded': 0, 'why': 'there is no history to seed'}
    if not setup.get('runtime'): return {'seeded': 0, 'why': 'no run of the app: only a database the run made is seeded'}
    return _into(rows, setup['runtime'], setup)
