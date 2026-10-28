"""The run's own database read as rows (M14): the run's PostgreSQL (eaos/core/system/local_db.py) through psql, or an
SQLite file of the copy through sqlite3; never any other. Names come from the database's own catalog and are quoted
as identifiers (`ident`); no value of a row is ever written into SQL text.

    open_run(live)       a Postgres or Sqlite of the run, or None
    db.tables()          [table]                 db.columns(table)   [(column, type)]
    db.rows(sql)         [[cell, ...]]           db.count(table)     its rows
"""
import os
import sqlite3
import subprocess
from pathlib import Path

SEPARATOR = '\x1f'
DATA_FILES = ('*.db', '*.sqlite', '*.sqlite3')
SKIPPED = {'node_modules', '.git', '.venv', 'venv', '__pycache__', '.next', 'dist', 'build'}
TEXT = ('text', 'json', 'jsonb', 'character varying', 'varchar', 'bytea', 'blob', 'clob', '')


def ident(name):
    """A catalog name quoted as an SQL identifier."""
    return '"' + str(name).replace('"', '""') + '"'


class Postgres:
    """The run's own PostgreSQL database, through its psql."""
    kind = 'postgres'

    def __init__(self, url, bin_dir):
        self.url, self.bin = url, Path(bin_dir)

    def tool(self, name): return str(self.bin / name)

    def rows(self, sql, timeout=300):
        done = subprocess.run([self.tool('psql'), self.url, '-X', '-tA', '-F', SEPARATOR, '-v', 'ON_ERROR_STOP=1'], input=sql,  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- the run's own psql on the run's own database, names quoted from its catalog, no shell
                              capture_output=True, text=True, timeout=timeout, env={**os.environ, 'PGOPTIONS': '-c client_min_messages=warning'})
        if done.returncode: raise RuntimeError(done.stderr.strip()[-300:])
        return [line.split(SEPARATOR) for line in done.stdout.splitlines() if line]

    def tables(self):
        return [row[0] for row in self.rows("select table_name from information_schema.tables where table_schema = 'public' "
                                            "and table_type = 'BASE TABLE' order by 1")]

    def columns(self, table):
        return [(row[0], row[1]) for row in self.rows(
            "select column_name, data_type from information_schema.columns where table_schema = 'public' and table_name = "
            f"'{table.replace(chr(39), chr(39) * 2)}' order by ordinal_position")]  # nosec B608 -- a catalog name, quoted as a literal

    def count(self, table): return int(self.rows(f'select count(*) from {ident(table)}')[0][0])  # nosec B608


class Sqlite:
    """An SQLite file of the copy."""
    kind = 'sqlite'

    def __init__(self, path):
        self.path = Path(path)

    def rows(self, sql, timeout=300):
        with sqlite3.connect(self.path, timeout=timeout) as db:
            return [[('' if cell is None else str(cell)) for cell in row] for row in db.execute(sql).fetchall()]

    def tables(self):
        return [row[0] for row in self.rows("select name from sqlite_master where type = 'table' and name not like 'sqlite_%' order by 1")]

    def columns(self, table):
        return [(row[1], row[2].lower()) for row in self.rows(f'pragma table_info({ident(table)})')]

    def count(self, table): return int(self.rows(f'select count(*) from {ident(table)}')[0][0])  # nosec B608


def _sqlite_files(copy):
    """The SQLite files inside the copy, outside what it installed."""
    found = []
    for pattern in DATA_FILES:
        found += [p for p in Path(copy).rglob(pattern) if not SKIPPED & set(p.relative_to(copy).parts)]
    return [p for p in sorted(found) if p.is_file() and p.read_bytes()[:16].startswith(b'SQLite format 3')]


def open_run(live):
    """The run's own database: its PostgreSQL when the profile declares one, else the copy's SQLite file; None when it
    has neither (MySQL, MongoDB and hosted databases are not read)."""
    url = live.database_url()
    if url:
        from ...core.system.local_db import binaries
        return Postgres(url, binaries())
    files = _sqlite_files(live.sandbox.copy)
    return Sqlite(files[0]) if files else None
