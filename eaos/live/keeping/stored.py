"""How the data is stored in the run's own database (M14.3): the columns that hold whole documents or pictures, and
the values kept in two tables.

    columns(db)   [{table, column, type, rows, average, largest, images}]: every text-like column's sizes, and how many
                  of its cells are a picture written as text (data:image..., or a long base64 run)
    shared(db)    [{one: (table, column), other: (table, column), values}]: two columns of two tables holding the same
                  values (a copy kept in two places), keys and ids left out
"""
import hashlib
import re

from .database import TEXT, ident

BASE64 = re.compile(r'^[A-Za-z0-9+/=\s]{2000,}$')
SAMPLE = 500                 # distinct values read of a column to compare it with another
SHARED_MIN = 5               # values two columns must have in common
KEYLIKE = re.compile(r'(^|_)(id|uuid|key|slug|code|status|type|kind|role|state|created|updated)(_|$)|_at$|_id$', re.I)


def _text_columns(db):
    return [(table, column, kind) for table in db.tables() for column, kind in db.columns(table) if kind.lower() in TEXT]


def _picture(cell): return cell.startswith('data:image') or bool(BASE64.match(cell[:4000]))


def _postgres_sizes(db, table, column):
    name, of = ident(column), ident(table)
    row = db.rows(f"select count({name}), coalesce(avg(octet_length({name}::text)), 0)::bigint, coalesce(max(octet_length({name}::text)), 0), "  # nosec B608 -- catalog names, quoted
                  f"count(*) filter (where {name}::text like 'data:image%' or (octet_length({name}::text) > 2000 and {name}::text ~ '^[A-Za-z0-9+/=]+$')) from {of}")[0]
    return [int(value) for value in row]


def _sqlite_sizes(db, table, column):
    cells = [row[0] for row in db.rows(f'select {ident(column)} from {ident(table)} where {ident(column)} is not null')]  # nosec B608
    sizes = [len(cell.encode('utf-8')) for cell in cells]
    return [len(cells), sum(sizes) // len(sizes) if sizes else 0, max(sizes, default=0), sum(_picture(cell) for cell in cells)]


def columns(db):
    out = []
    for table, column, kind in _text_columns(db):
        rows, average, largest, images = (_postgres_sizes if db.kind == 'postgres' else _sqlite_sizes)(db, table, column)
        if rows: out.append({'table': table, 'column': column, 'type': kind, 'rows': rows, 'average': average,
                             'largest': largest, 'images': images})
    return out


def _values(db, table, column):
    """The digests of up to SAMPLE distinct values of a column."""
    cells = db.rows(f'select distinct {ident(column)} from {ident(table)} where {ident(column)} is not null limit {SAMPLE}')  # nosec B608
    return {hashlib.sha256(row[0].encode('utf-8')).hexdigest()[:16] for row in cells if row[0].strip()}


def shared(db):
    """Two columns of two tables holding the same values, the larger part of the smaller one."""
    found = {(t, c): _values(db, t, c) for t, c, _ in _text_columns(db) if not KEYLIKE.search(c)}
    found = {key: values for key, values in found.items() if len(values) >= SHARED_MIN}
    out, keys = [], sorted(found)
    for index, one in enumerate(keys):
        for other in keys[index + 1:]:
            same = found[one] & found[other]
            if one[0] != other[0] and len(same) >= SHARED_MIN and len(same) * 2 >= min(len(found[one]), len(found[other])):
                out.append({'one': list(one), 'other': list(other), 'values': len(same)})
    return out
