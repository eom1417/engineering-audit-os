"""A year of records for the tables the copy left empty (M14.1): the run seeded nothing into them (no assistant, no
seed), so EAOS writes ROWS rows of its own, by each column's type, parents before children: a foreign key points at a
row of its table, a date walks back a day per row over a year, a unique text is numbered. A column the database fills
itself is left to it. A table it cannot fill this way (a custom type, a check it breaks, a cycle of keys) is left
empty, with its reason.
"""
from .database import ident

ROWS = 365


def _postgres_keys(db):
    """{(table, column): (parent table, its column)} of the foreign keys of the public schema."""
    rows = db.rows("select k.table_name, k.column_name, c.table_name, c.column_name from information_schema.table_constraints t "
                   "join information_schema.key_column_usage k on k.constraint_name = t.constraint_name "
                   "join information_schema.constraint_column_usage c on c.constraint_name = t.constraint_name "
                   "where t.constraint_type = 'FOREIGN KEY' and t.table_schema = 'public'")
    return {(table, column): (parent, key) for table, column, parent, key in rows}


def _sqlite_keys(db):
    return {(table, row[3]): (row[2], row[4] or 'rowid') for table in db.tables() for row in db.rows(f'pragma foreign_key_list({ident(table)})')}


def _filled_by_it(db, table):
    """The columns the database fills itself: an identity or a default, SQLite's rowid key."""
    if db.kind == 'postgres':
        literal = table.replace("'", "''")
        return {row[0] for row in db.rows("select column_name from information_schema.columns where table_schema = 'public' "
                                          f"and table_name = '{literal}' and (column_default is not null or is_identity = 'YES')")}  # nosec B608
    info = db.rows(f'pragma table_info({ident(table)})')
    return {row[1] for row in info if (row[5] == '1' and row[2].lower() == 'integer') or row[4]}


def _parent(parent):
    """The SQL of a foreign key's value for row g: the parent's rows by number, every parent in turn."""
    table, key = parent
    key = 'rowid' if key == 'rowid' else ident(key)
    return (f'(select p.k from (select {key} as k, row_number() over (order by {key}) as r from {ident(table)}) p '  # nosec B608 -- catalog names, quoted
            f'where p.r = 1 + (g.n % (select count(*) from {ident(table)})))')


# A column's type: the words that name it, and its value for row g in PostgreSQL and in SQLite.
BY_TYPE = (
    (('int', 'numeric', 'decimal', 'real', 'double', 'float'), 'g.n', 'g.n'),
    (('bool',), '(g.n % 2 = 0)', '(g.n % 2)'),
    (('date', 'time'), "now() - (g.n || ' days')::interval", "datetime('now', '-' || g.n || ' days')"),
    (('uuid',), 'gen_random_uuid()', None),
    (('json',), "'{}'", "'{}'"),
)


def _value(db, column, kind, parent):
    """The SQL of a column's value for row g, or None when its type is not one EAOS can make."""
    if parent: return _parent(parent)
    kind = kind.lower()
    for words, postgres, sqlite in BY_TYPE:
        if any(word in kind for word in words): return postgres if db.kind == 'postgres' else sqlite
    if any(word in kind for word in ('char', 'text', 'clob')) or kind == '': return f"'{column.replace(chr(39), chr(39) * 2)} ' || g.n"
    return None


def _parents(table, keys, left):
    """The tables still to fill that `table` points at (itself aside)."""
    return {parent for (child, _), (parent, _key) in keys.items() if child == table and parent != table and parent in left}


def _order(tables, keys):
    """The tables with their parents before them; a table in a cycle of keys is left out."""
    done, left = [], list(tables)
    while left:
        ready = [t for t in left if not _parents(t, keys, left)]
        if not ready: break
        done += ready
        left = [t for t in left if t not in ready]
    return done


def _fill(db, table, keys):
    columns = [(c, k) for c, k in db.columns(table) if c not in _filled_by_it(db, table)]
    values = [(c, _value(db, c, k, keys.get((table, c)))) for c, k in columns]
    unknown = [c for c, v in values if v is None]
    if unknown: return f'no value EAOS can make for its column {unknown[0]}'
    names, made = ', '.join(ident(c) for c, _ in values), ', '.join(v for _, v in values)
    if db.kind == 'postgres':
        db.rows(f'insert into {ident(table)} ({names}) select {made} from generate_series(1, {ROWS}) as g(n)')  # nosec B608 -- catalog names, quoted
    else:
        db.rows(f'with recursive g(n) as (select 1 union all select n + 1 from g where n < {ROWS}) '  # nosec B608 -- catalog names, quoted
                f'insert into {ident(table)} ({names}) select {made} from g')
    return None


def fill_empty(db):
    """{table: {before: 0, after} or {before: 0, why}} for every table the copy left empty."""
    keys = _postgres_keys(db) if db.kind == 'postgres' else _sqlite_keys(db)
    empty = [t for t in db.tables() if not db.count(t)]
    ordered, out = _order(empty, keys), {}
    for table in ordered + [t for t in empty if t not in ordered]:
        try: why = _fill(db, table, keys)
        except Exception as problem: why = str(problem)[:200]             # a check or a type it breaks
        out[table] = {'before': 0, 'why': why} if why else {'before': 0, 'after': db.count(table)}
    return out
