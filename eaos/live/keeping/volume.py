"""Real volume in the copy (M14.1): the run's own database filled to a size a working app reaches, before the saves are
measured and the data is read, so a save that grows with the data, or a page that slows with it, can show.

Each table that holds rows (the seed's, the simulated users' or the app's own) is copied into itself until it holds
ROWS rows, or GROWTH times what it held, the smaller of the two: a column the database fills itself (an identity, a
default id) is left to it, a unique text column gets a suffix per copy, and a table whose unique column can be told
apart no other way is left as it is, with its reason. Pictures the app stores are not made: said as not covered.
"""
from .database import ident

ROWS, GROWTH = 2000, 50


def _postgres_plan(db, table):
    """(columns to copy, columns made unique by a suffix) of a Postgres table, or a reason it cannot be filled."""
    literal = table.replace("'", "''")
    defaults = {row[0] for row in db.rows("select column_name from information_schema.columns where table_schema = 'public' "
                                          f"and table_name = '{literal}' and (column_default is not null or is_identity = 'YES')")}  # nosec B608
    unique = {row[0] for row in db.rows("select a.attname from pg_index i join pg_attribute a on a.attrelid = i.indrelid and "
                                        f"a.attnum = any(i.indkey) where i.indrelid = '{ident(table).replace(chr(39), chr(39) * 2)}'::regclass "
                                        "and i.indisunique")}  # nosec B608
    return _plan(db.columns(table), defaults, unique)


def _sqlite_unique(db, table, info):
    """The columns of an SQLite table kept unique: its primary key (an index of its own, or the rowid) and its unique
    indexes."""
    unique = {row[1] for row in info if row[5] != '0'}
    for index in db.rows(f'pragma index_list({ident(table)})'):
        if index[2] == '1': unique |= {row[2] for row in db.rows(f'pragma index_info({ident(index[1])})')}
    return unique


def _sqlite_plan(db, table):
    info = db.rows(f'pragma table_info({ident(table)})')
    defaults = {row[1] for row in info if row[5] == '1' and row[2].lower() == 'integer'} | {row[1] for row in info if row[4]}
    return _plan([(row[1], row[2].lower()) for row in info], defaults, _sqlite_unique(db, table, info))


def _plan(columns, defaults, unique):
    """(columns to copy, the unique ones among them, made unique by a suffix), or why the table cannot be filled: a
    column the database fills itself and keeps unique is left to it."""
    filled_by_it = defaults & unique
    copied = [(name, kind) for name, kind in columns if name not in filled_by_it]
    kept = [(name, kind) for name, kind in copied if name in unique]
    blocked = next((name for name, kind in kept if not _textual(kind)), None)
    if blocked: return f"its unique column {blocked} has no default and is not text"
    return [name for name, _ in copied], [name for name, _ in kept]


def _textual(kind): return any(word in kind.lower() for word in ('char', 'text', 'clob'))


def _insert(db, table, plan, copies):
    names, suffixed = plan
    values = ', '.join(f"{ident(n)} || '-v' || g.n" if n in suffixed else ident(n) for n in names)
    columns = ', '.join(ident(n) for n in names)
    if db.kind == 'postgres':
        db.rows(f'insert into {ident(table)} ({columns}) select {values} from {ident(table)} cross join '  # nosec B608 -- catalog names, quoted
                f'generate_series(1, {int(copies)}) as g(n)', timeout=600)
    else:
        db.rows(f'with recursive g(n) as (select 1 union all select n + 1 from g where n < {int(copies)}) '  # nosec B608
                f'insert into {ident(table)} ({columns}) select {values} from {ident(table)}, g')


def fill(db):
    """{table: {before, after} or {before, why}} after filling every table that holds rows."""
    out = {}
    for table in db.tables():
        before = db.count(table)
        if not before: continue
        plan = (_postgres_plan if db.kind == 'postgres' else _sqlite_plan)(db, table)
        if isinstance(plan, str): out[table] = {'before': before, 'why': plan}; continue
        copies = max(0, min(ROWS, before * GROWTH) // before - 1)
        try: _insert(db, table, plan, copies)
        except Exception as problem: out[table] = {'before': before, 'why': str(problem)[:200]}; continue  # a constraint it breaks
        out[table] = {'before': before, 'after': db.count(table)}
    return out
