"""Kept and restorable (M14.4): the project's own backup run on the copy and restored into an empty database, compared
table by table; without one, the database's own dump, so the drill still says whether it comes back whole.

    commands(target)     [{argv, source}]: the backup the project declares (a `backup` or `dump` script of package.json,
                         a `backup` target of its Makefile, a scripts/*backup* file)
    drill(live, db)      {how, source?, file?, tables: [{table, rows, restored, same}], missing, differ, why?}
"""
import hashlib
import json
import re
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path

from .database import SEPARATOR, Postgres, Sqlite, ident
from ...core.system.local_db import binaries

NAMED = re.compile(r'backup|dump|export[-_:]?(db|data)', re.I)
RUNNERS = {'.sh': ['bash'], '.js': ['node'], '.mjs': ['node'], '.cjs': ['node'], '.ts': ['npx', 'tsx'], '.py': ['python3']}
OUTPUTS = ('*.sql', '*.dump', '*.backup', '*.json', '*.sql.gz', '*.db')


def _package_scripts(target):
    try: scripts = json.loads((Path(target) / 'package.json').read_text(encoding='utf-8')).get('scripts') or {}
    except (OSError, ValueError): return []
    return [{'argv': ['npm', 'run', name], 'source': f'package.json scripts.{name}', 'text': text}
            for name, text in scripts.items() if NAMED.search(name)]


def _files(target):
    root = Path(target)
    found = [p for folder in ('scripts', 'bin', 'tools', '.') for p in sorted((root / folder).glob('*'))
             if p.is_file() and p.suffix in RUNNERS and 'backup' in p.name.lower()]
    return [{'argv': [*RUNNERS[p.suffix], p.relative_to(root).as_posix()], 'source': p.relative_to(root).as_posix(),
             'text': p.read_text(encoding='utf-8', errors='replace')} for p in found]


def _make(target):
    try: text = (Path(target) / 'Makefile').read_text(encoding='utf-8')
    except OSError: return []
    return [{'argv': ['make', 'backup'], 'source': 'Makefile backup', 'text': text}] if re.search(r'^backup\s*:', text, re.M) else []


def commands(target):
    return _package_scripts(target) + _make(target) + _files(target)


def _newest(copy, since):
    """The file the backup wrote: the newest output-like file of the copy changed after `since`."""
    found = [p for pattern in OUTPUTS for p in Path(copy).rglob(pattern)
             if 'node_modules' not in p.parts and p.stat().st_mtime >= since]
    return max(found, key=lambda p: p.stat().st_mtime, default=None)


def _digest(db, table):
    if db.kind == 'postgres':
        return db.rows(f"select md5(coalesce(string_agg(md5(t::text), '' order by md5(t::text)), '')) from {ident(table)} t")[0][0]  # nosec B608
    rows = sorted(SEPARATOR.join(row) for row in db.rows(f'select * from {ident(table)}'))  # nosec B608
    return hashlib.sha256('\n'.join(rows).encode('utf-8')).hexdigest()


def compare(db, restored):
    """[{table, rows, restored, same}] of every table of `db` against the restored database."""
    there = set(restored.tables())
    rows = []
    for table in db.tables():
        count = db.count(table)
        back = restored.count(table) if table in there else None
        rows.append({'table': table, 'rows': count, 'restored': back,
                     'same': back == count and _digest(db, table) == _digest(restored, table)})
    return rows


def _restore_postgres(live, file):
    """A new empty database of the run with the file restored into it."""
    name = f'eaos_restored_{int(time.time())}'
    restored = Postgres(live._database.create(name), binaries())
    restored.name = name
    if file.suffix == '.sql': restored.rows(file.read_text(encoding='utf-8', errors='replace'), timeout=900)
    else:
        subprocess.run([restored.tool('pg_restore'), '--no-owner', '-d', restored.url, str(file)], capture_output=True, timeout=900)  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- the run's own pg_restore into a database the run made, no shell
    return restored


def _own_dump(db, folder):
    """The database's own dump: pg_dump's custom format, or SQLite's backup."""
    if db.kind == 'postgres':
        file = folder / 'own.dump'
        subprocess.run([db.tool('pg_dump'), '-Fc', '-f', str(file), db.url], capture_output=True, timeout=900, check=True)  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- the run's own pg_dump of a database the run made, no shell
        return file
    file = folder / 'own.db'
    with sqlite3.connect(db.path) as source, sqlite3.connect(file) as target: source.backup(target)
    return file


def _run_backup(live, command, db):
    """The file the project's own backup wrote in the copy, or None (why in the second value)."""
    since = time.time()
    env = {'DATABASE_URL': db.url} if db.kind == 'postgres' else {}
    code, out, err = live.run(command['argv'], timeout=600, env=env)
    file = _newest(live.sandbox.copy, since) if code == 0 else None
    return file, ('' if file else f"it ended with {code} and wrote no file: {(err or out)[-200:]}")


def _restored(live, db, file, folder):
    """The database the file restores into: a new one of the run's PostgreSQL, or an SQLite file in `folder`."""
    if db.kind == 'postgres': return _restore_postgres(live, file)
    if file.read_bytes()[:16].startswith(b'SQLite format 3'): return Sqlite(file)
    restored = Sqlite(folder / 'restored.db')
    with sqlite3.connect(restored.path) as target: target.executescript(file.read_text(encoding='utf-8', errors='replace'))
    return restored


def drill(live, db, target):
    """The restore drill on the copy's database: the project's backup when it declares one, else the database's own."""
    with tempfile.TemporaryDirectory(prefix='eaos-drill-') as scratch:
        return _drill(live, db, target, Path(scratch))


def _drill(live, db, target, folder):
    """The drill, its dump and restored SQLite file in `folder`."""
    command = next(iter(commands(target)), None)
    file, why = _run_backup(live, command, db) if command else (_own_dump(db, folder), '')
    if file is None: return {'how': 'project', 'source': command['source'], 'why': why, 'tables': []}
    restored = _restored(live, db, file, folder)
    rows = compare(db, restored)
    drop(db, restored)
    return {'how': 'project' if command else 'own', 'source': command and command['source'], 'file': file.name,
            'tables': rows, 'missing': [r['table'] for r in rows if r['restored'] is None],
            'differ': [r['table'] for r in rows if r['restored'] is not None and not r['same']]}


def drop(db, restored):
    """The restored database removed from the run's PostgreSQL (an SQLite one goes with the drill's folder)."""
    if getattr(restored, 'name', None): db.rows(f'drop database if exists {ident(restored.name)}')
