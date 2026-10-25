"""The data layer's rules tried (M6.6): the project's migrations applied to a database of the run's own, then the
Supabase CLI's security advisors (MIT, pinned) and pgTAP tests EAOS writes per table, run as no one, as the row's owner and
as another user. A policy that lets another user read or change a row is a finding whose evidence is the failing test.

Nothing touches the person's database: the server is the run's (eaos/core/local_db.py), the database is made empty for
the trial and dropped after it, and every test runs inside a transaction rolled back. A migration that does not apply
here (an extension this server lacks) is said, and its tables are not tested, never taken for safe.
"""
import json
import os
import re
import tempfile
import uuid
from pathlib import Path

from ..core.local_db import LocalPostgres
from ..core.process import run_command
from ..core.toolchain import home

STUBS = Path(__file__).resolve().parents[1] / 'templates/layers/supabase-stubs.sql'
DATABASE = 'eaos_layers'
OWNER, OTHER = str(uuid.UUID(int=0xA)), str(uuid.UUID(int=0xB))
# the two people of every test: A owns a row of each table, B tries to reach it
USERS = ("insert into auth.users (id, email) values ('00000000-0000-0000-0000-00000000000a', 'a@eaos.test'), "
         "('00000000-0000-0000-0000-00000000000b', 'b@eaos.test');")
# The schemas the trial itself makes (the stand-ins and pgTAP): what the advisors say of them is not the project's.
STANDING = ('tap', 'auth', 'storage', 'extensions')
OWNER_NAMES = ('user_id', 'owner_id', 'owner', 'author_id', 'created_by', 'profile_id', 'account_id', 'uid')
# Two helpers the tests call: the rows a statement changed, a refusal counted as none; and a row made for a table with
# every required column given a value of its type.
HELPERS = r"""
create or replace function tap.eaos_rows(q text) returns int language plpgsql as $f$
declare n int; begin execute q; get diagnostics n = row_count; return n;
exception when insufficient_privilege or check_violation or with_check_option_violation then return 0; end $f$;
create or replace function tap.eaos_row(t regclass, owner_column text, owner uuid) returns boolean language plpgsql as $f$
declare cols text := ''; vals text := ''; c record;
begin
  for c in select a.attname, format_type(a.atttypid, a.atttypmod) as kind from pg_attribute a
           where a.attrelid = t and a.attnum > 0 and not a.attisdropped and a.attnotnull and not a.atthasdef and a.attidentity = ''
             and a.attgenerated = '' and a.attname <> coalesce(owner_column, '') loop
    cols := cols || quote_ident(c.attname) || ',';
    vals := vals || case when c.kind like '%int%' or c.kind like 'numeric%' or c.kind in ('real', 'double precision') then '1'
                         when c.kind = 'boolean' then 'false' when c.kind = 'uuid' then quote_literal(gen_random_uuid())
                         when c.kind like 'timestamp%' or c.kind = 'date' then 'now()' when c.kind like 'json%' then '''{}'''
                         else quote_literal('eaos') end || ',';
  end loop;
  if owner_column is not null then cols := cols || quote_ident(owner_column) || ','; vals := vals || quote_literal(owner) || ','; end if;
  if cols = '' then execute format('insert into %s default values', t);
  else execute format('insert into %s (%s) values (%s)', t, rtrim(cols, ','), rtrim(vals, ',')); end if;
  return true;
exception when others then return false; end $f$;
create or replace function tap.eaos_count(t regclass) returns int language plpgsql as $f$
declare n int; begin execute format('select count(*) from %s', t) into n; return n;
exception when insufficient_privilege then return 0; end $f$;
create or replace function tap.eaos_take(t regclass, owner_column text, taker uuid) returns int language sql as
  $f$ select tap.eaos_rows(format('update %s set %I = %L', t, owner_column, taker)) $f$;
create or replace function tap.eaos_wipe(t regclass) returns int language sql as
  $f$ select tap.eaos_rows(format('delete from %s', t)) $f$;
grant usage on schema tap to anon, authenticated;
grant execute on all functions in schema tap to anon, authenticated;
"""
TABLES = r"""
select c.oid::regclass::text, c.relrowsecurity,
  (select a.attname from pg_constraint k join pg_attribute a on a.attrelid = k.conrelid and a.attnum = k.conkey[1]
     where k.conrelid = c.oid and k.contype = 'f' and k.confrelid = 'auth.users'::regclass limit 1),
  (select string_agg(a.attname, ',') from pg_attribute a where a.attrelid = c.oid and a.attnum > 0 and not a.attisdropped
     and format_type(a.atttypid, a.atttypmod) in ('uuid', 'text')),
  exists (select 1 from pg_policies p where p.schemaname = 'public' and p.tablename = c.relname and p.cmd in ('SELECT', 'ALL')
          and p.qual = 'true')
from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'public' and c.relkind = 'r' order by 1
"""


class Database:
    """The trial's own database on the run's server, made empty, dropped by close()."""

    def __init__(self, runtime):
        self.server = LocalPostgres(runtime)
        admin = self.server.start()
        self.psql_bin = Path(json.loads(self.server.state.read_text())['bin']) / 'psql'
        self.run(f'drop database if exists {DATABASE} with (force)', admin)
        self.url = self.server.create(DATABASE)
        self.admin = admin

    def run(self, sql, url=None, tuples=False):
        """(exit code, output, errors) of SQL text, every statement tried (ON_ERROR_STOP off)."""
        with tempfile.NamedTemporaryFile('w', suffix='.sql', encoding='utf-8') as script:
            script.write(sql)
            script.flush()
            argv = [str(self.psql_bin), url or self.url, '-q', '-X', '-f', script.name] + (['-t', '-A', '-F', '\t'] if tuples else [])
            done = run_command(argv, 600, env={**os.environ, 'PGOPTIONS': '-c client_min_messages=warning'})
        return done.returncode, done.stdout, done.stderr

    def close(self):
        self.run(f'drop database if exists {DATABASE} with (force)', self.admin)
        self.server.stop()


def pgtap():
    """pgTAP's install script for this PostgreSQL, made once from its pinned source (PostgreSQL licence)."""
    folder = home() / 'pgtap'
    made = folder / 'pgtap.sql'
    if made.is_file(): return made
    source = next(folder.rglob('pgtap.sql.in'), None)
    if source is None: return None
    text = source.read_text(encoding='utf-8')
    made.write_text(text.replace('MODULE_PATHNAME', 'pgtap').replace('__OS__', 'linux').replace('__VERSION__', '1.3'), encoding='utf-8')
    return made


def apply(db, migrations, root):
    """(applied, [(migration, its first error)]): the stand-ins, then every migration in order."""
    db.run(STUBS.read_text(encoding='utf-8'))
    applied, failed = [], []
    for path in migrations:
        _, _, error = db.run((Path(root) / path).read_text(encoding='utf-8', errors='replace'))
        problem = next((line for line in error.splitlines() if 'ERROR' in line), None)
        (failed.append((path, problem[:200])) if problem else applied.append(path))
    return applied, failed


def advisors(db):
    """The Supabase CLI's security advisors on the trial's database: [{name, level, detail}], or None without the CLI."""
    binary = home() / 'bin' / 'supabase'
    if not binary.is_file(): return None
    done = run_command([str(binary), 'db', 'advisors', '--db-url', db.url + '?sslmode=disable', '--type', 'security',
                        '--output-format', 'json'], 300)
    try: rows = json.loads(done.stdout).get('results') or []
    except ValueError: return None
    return [{'name': row.get('name'), 'level': row.get('level'), 'detail': row.get('detail'),
             'object': (row.get('metadata') or {}).get('name')} for row in rows
            if (row.get('metadata') or {}).get('schema') not in STANDING]


def tables(db):
    """[{table, rls, owner, public_read}] of the public schema, the owner column by its key to auth.users or its name."""
    _, out, _ = db.run(TABLES, tuples=True)
    found = []
    for line in out.splitlines():
        name, rls, keyed, columns, public = (line.split('\t') + [''] * 5)[:5]
        named = next((c for c in OWNER_NAMES if c in (columns or '').split(',')), None)
        found.append({'table': name, 'rls': rls == 't', 'owner': keyed or named, 'public_read': public == 't'})
    return found


def _quoted(text):
    return "'" + str(text).replace("'", "''") + "'"


def _tests(row):
    """The pgTAP tests of one table: (description, the call that must give 0, the role, the user), as no one and as
    another user; the statements themselves are the database's own functions (HELPERS), given the table's name."""
    table, owner = _quoted(row['table']), row['owner']
    said = row['table'].replace("'", '')
    reads = [] if row['public_read'] else [(f'no one signed in reads {said}', f'tap.eaos_count({table})', 'anon', None)]
    if not owner: return reads
    reads += [] if row['public_read'] else [(f'another user reads none of the rows of {said}', f'tap.eaos_count({table})', 'authenticated', OTHER)]
    return reads + [(f'another user changes none of the rows of {said}', f'tap.eaos_take({table}, {_quoted(owner)}, {_quoted(OTHER)})', 'authenticated', OTHER),
                    (f'another user deletes none of the rows of {said}', f'tap.eaos_wipe({table})', 'authenticated', OTHER)]


def script(rows):
    """The whole pgTAP script: users A and B, one row per table owned by A, then each test as its role, rolled back."""
    tests = [(row, test) for row in rows for test in _tests(row)]
    lines = ['set search_path = public, tap;', 'begin;', f'select plan({len(tests)});', USERS]
    lines += [f"select tap.eaos_row({_quoted(row['table'])}, {_literal(row['owner'])}, '{OWNER}');" for row in rows]
    for _, (said, call, role, user) in tests:
        lines += [f'set local role {role};', f"set local request.jwt.claim.sub = '{user or ''}';",
                  f"set local request.jwt.claim.role = '{role}';", f'select is({call}, 0, {_quoted(said)});', 'reset role;']
    return '\n'.join(lines + ['select * from finish();', 'rollback;']) + '\n', tests


def _literal(value):
    return _quoted(value) if value else 'null'


def run_tests(db, rows):
    """[{test, table, passed, said}] from pgTAP's TAP output."""
    text, tests = script(rows)
    _, out, _ = db.run(text, tuples=True)
    verdicts = {int(m.group(2)): (m.group(1) is None, m.group(3)) for m in re.finditer(r'^(not )?ok (\d+) - (.*)$', out, re.M)}
    return [{'test': said, 'table': row['table'], 'passed': verdicts.get(n, (None, ''))[0], 'role': role}
            for n, (row, (said, _, role, _)) in enumerate(tests, start=1)]


def trial(runtime, root, migrations):
    """{'applied', 'failed', 'advisors', 'tables', 'tests'} of the migrations tried, or {'gap': why}."""
    if not migrations: return {'gap': 'the project has no SQL migration to try'}
    tap = pgtap()
    if tap is None: return {'gap': 'pgTAP is not installed: eaos tools install --only pgtap'}
    db = Database(runtime)
    try:
        db.run('create schema if not exists tap;\nset search_path = tap, public;\n' + tap.read_text(encoding='utf-8'))
        applied, failed = apply(db, migrations, root)
        db.run(HELPERS)
        rows = tables(db)
        return {'applied': applied, 'failed': failed, 'advisors': advisors(db), 'tables': rows, 'tests': run_tests(db, rows)}
    finally:
        db.close()
