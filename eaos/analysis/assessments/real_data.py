"""Real data written in the code (M12.2, M12.3): each table written as code and each record of personal values, sorted
on its evidence before anything is said.

From the engines' records (the `external` fact set): Presidio's personal values in string literals
(eaos/engines/security/presidio.py) and ast-grep's tables of records and maps keyed by dates (eaos/rules/ast-grep
data-tables.yml); and JSON a module of the product imports, read from the resolved graph. The words are
eaos/rules/personal-data.json. A table is:
    personal    a personal value that is no placeholder sits inside it
    domain      no such value, but its records carry two words of a domain (salary, price, date, ...) or it is keyed
                by dates or months
    doubtful    one such word: the judge (the card triage) reads it
    nothing     the program's own configuration (routes, options, labels), or placeholders only
Outside a table, a record of personal values (two kinds within LINE_WINDOW lines, or one national id, IBAN or card
number) is personal. Then where it is: the product, or only tests, stories, documents, mocks, a seed (outside the
product) or a migration (it runs on every database); a module of the product only tests or stories import is theirs.
Values of the code that a seed or migration also holds say the data is in the database already. A finding says the
screens and endpoints that reach it through the imports, so the card names what it feeds.
"""
import json
import re
from pathlib import Path, PurePosixPath

from ...core.contracts.vocabulary import classify
from ...facts.engine_findings import engine_records

RULES = json.loads((Path(__file__).resolve().parents[2] / 'rules/personal-data.json').read_text(encoding='utf-8'))
LINE_WINDOW = 3
ALONE = {'SA_NATIONAL_ID', 'IBAN_CODE', 'CREDIT_CARD'}      # never written in a program by right, even alone
KEY = re.compile(r'["\']?([A-Za-z_؀-ۿ][\w؀-ۿ]*)["\']?\s*:(?!:)')
TABLES = ('data_table', 'dated_map')
SCREENS = 6
GENERATED = 1000
DOMAIN = set(RULES['tables']['domain_keys'])
# A name the language model read, in a table of the program's own keys only (a menu, routes): never a person alone.
NAMES_ONLY = {'PERSON'}


def values(sets):
    """Presidio's personal values that are no placeholder: [{path, line, entity, digest, masked}]."""
    return [{'path': f['location']['path'], 'line': f['location'].get('line'), 'fact_id': f['id'], **f['value']}
            for f in engine_records(sets, 'personal_value') if not f['value'].get('placeholder')]


def tables(sets):
    """ast-grep's tables and dated maps: [{path, line, end_line, record}], an inner table inside an outer one dropped."""
    rows = sorted(({'path': f['location']['path'], 'line': f['location'].get('line'), 'end_line': f['value'].get('end_line'),
                    'record': f['value']['record'], 'fact_id': f['id']} for record in TABLES for f in engine_records(sets, record)),
                  key=lambda t: (t['path'], t['line'], -(t['end_line'] or 0)))
    kept = []
    for row in rows:
        if kept and kept[-1]['path'] == row['path'] and kept[-1]['line'] <= row['line'] <= (kept[-1]['end_line'] or 0): continue
        kept.append(row)
    return kept


def place(path):
    """Where a file sits: product, test, story, docs, mock, seed or migration."""
    parts, name = {p.lower() for p in PurePosixPath(path).parts[:-1]}, PurePosixPath(path).name.lower()
    if name.endswith('.sql'): return 'seed' if 'seed' in name or parts & set(RULES['outside_the_product']['seed']) else 'migration'
    if classify(path) == 'test': return 'test'
    if '.stories.' in name or '.story.' in name: return 'story'
    for where, folders in RULES['outside_the_product'].items():
        if parts & set(folders): return where
    return 'product'


def importers_of(sets):
    """{file: the files that import it}, from the resolved graph."""
    out = {}
    for fact in (sets.get('graph') or {}).get('facts', []):
        if fact['kind'] != 'graph_node': continue
        for target in fact['value'].get('depends_on') or []: out.setdefault(target, set()).add(fact['location']['path'])
    return out


def reach(path, importers):
    """Where a file is reached from: its own place; a product module only tests or stories import takes theirs."""
    own = place(path)
    if own != 'product': return own
    by = {place(p) for p in importers.get(path, ())}
    return 'test' if by and 'product' not in by else 'product'


def _entries(sets):
    """{file: ['page #/roster', 'http GET /api/staff']}: the screens and endpoints each file serves."""
    entries = {}
    for fact in (sets.get('entrypoints') or {}).get('facts', []):
        value = fact['value']
        if fact['kind'] == 'entry_point' and value.get('surface') in ('page', 'http') and value.get('route'):
            entries.setdefault(fact['location']['path'], []).append(' '.join(filter(None, (value['surface'], value.get('http_method'), value['route']))))
    return entries


def fed(path, sets, importers):
    """The screens and endpoints that reach the file through the imports, nearest first."""
    entries, seen, todo, out = _entries(sets), {path}, [path], []
    while todo and len(out) < SCREENS:
        current = todo.pop(0)
        out += [e for e in entries.get(current, []) if e not in out]
        fresh = sorted(set(importers.get(current, ())) - seen)
        seen |= set(fresh); todo += fresh
    return out[:SCREENS]


def _keys(lines, table):
    """The keys of a table's records; none for generated code (a line longer than GENERATED: a bundle, minified)."""
    span = lines[table['line'] - 1:table['end_line'] or table['line']]
    if any(len(line) > GENERATED for line in span): return set()
    return {key.lower() for key in KEY.findall('\n'.join(span))}


def kind_of(table, inside, keys):
    """personal, domain, doubtful or None for one table, from the personal values inside it and its records' keys."""
    if inside: return 'personal'
    if table['record'] == 'dated_map': return 'domain'
    domain = keys & DOMAIN
    return 'domain' if len(domain) >= 2 else 'doubtful' if domain else None


def _read(root, path):
    try: return (Path(root) / path).read_text(encoding='utf-8', errors='replace').split('\n')
    except (OSError, TypeError): return []


def _inside(table, hits):
    """The values on the lines of a table."""
    last = table['end_line'] or table['line']
    return [h for h in hits if h['path'] == table['path'] and table['line'] <= h['line'] <= last]


def _from_tables(sets, root, hits):
    """(findings, the values they hold): one per table that is data."""
    out, used = [], set()
    for table in tables(sets):
        inside, keys = _inside(table, hits), _keys(_read(root, table['path']), table)
        used |= {id(h) for h in inside}
        if not keys & DOMAIN: inside = [h for h in inside if h['entity'] not in NAMES_ONLY]    # a menu's 'Button Groups'
        kind = kind_of(table, inside, keys)
        if kind: out.append({**table, 'kind': kind, 'values': inside})
    return _one_per_file(out), used


def _one_per_file(rows):
    """Tables of one kind in one file are one finding (one card, one judgement), from the first to the last."""
    kept = {}
    for row in rows:
        same = kept.get((row['path'], row['kind'], row['record']))
        if same is None: kept[(row['path'], row['kind'], row['record'])] = dict(row, fact_ids=[row['fact_id']]); continue
        same['end_line'] = max(same['end_line'] or same['line'], row['end_line'] or row['line'])
        same['values'] = same['values'] + row['values']; same['fact_ids'].append(row['fact_id'])
    return list(kept.values())


def _grouped(hits):
    """Values grouped into records: each within LINE_WINDOW lines of the one before it, in one file."""
    groups = []
    for hit in sorted(hits, key=lambda h: (h['path'], h['line'])):
        last = groups[-1] if groups else None
        if last and last['path'] == hit['path'] and hit['line'] - last['end_line'] <= LINE_WINDOW:
            last['values'].append(hit); last['end_line'] = hit['line']
        else: groups.append({'path': hit['path'], 'line': hit['line'], 'end_line': hit['line'], 'record': 'record', 'values': [hit]})
    return groups


def _records_alone(hits, used):
    """The records of personal values outside every table: two kinds of value, or one never written by right."""
    groups = _grouped([h for h in hits if id(h) not in used])
    return [dict(g, kind='personal') for g in groups
            if len({v['entity'] for v in g['values']}) >= 2 or {v['entity'] for v in g['values']} & ALONE]


def _json_imports(sets):
    """{JSON file: the ids of the product modules' graph nodes that import it}."""
    out = {}
    for fact in (sets.get('graph') or {}).get('facts', []):
        if fact['kind'] != 'graph_node' or place(fact['location']['path']) != 'product': continue
        for target in fact['value'].get('depends_on') or []:
            if target.endswith('.json'): out.setdefault(target, []).append(fact['id'])
    return out


def _json_rows(root, path):
    """The records of a JSON file that is an array of objects, else none."""
    try: data = json.loads((Path(root) / path).read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError): return []
    return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []


def _json_tables(sets, root):
    """JSON files a module of the product imports that hold a table of records of the domain."""
    out = []
    for path, fact_ids in sorted(_json_imports(sets).items()):
        rows = _json_rows(root, path)
        if len(rows) < RULES['tables']['min_records']: continue
        kind = kind_of({'record': 'data_table'}, [], {key.lower() for row in rows for key in row})
        if kind: out.append({'path': path, 'line': 1, 'end_line': None, 'record': 'json', 'kind': kind, 'values': [], 'fact_id': fact_ids[0]})
    return out


def _stored(hits):
    """{digest of a value: the seeds and migrations that hold it}."""
    stored = {}
    for hit in hits:
        if place(hit['path']) in ('seed', 'migration'): stored.setdefault(hit['digest'], set()).add(hit['path'])
    return stored


def _finding(row, where, stored, feeds):
    entities = {}
    for value in row['values']: entities[value['entity']] = entities.get(value['entity'], 0) + 1
    return {**{k: row[k] for k in ('path', 'line', 'end_line', 'record', 'kind')}, 'place': where,
            'entities': dict(sorted(entities.items())),
            'fact_ids': sorted(filter(None, [*row.get('fact_ids', [row.get('fact_id')]), *(v['fact_id'] for v in row['values'])])),
            'in_database': sorted({p for v in row['values'] for p in stored.get(v['digest'], ()) if p != row['path']}),
            'feeds': feeds}


def findings(sets, root=None):
    """Every table or record of real data, sorted on its evidence: kind, place, the values (by kind), the seeds or
    migrations that hold the same values, the screens it feeds."""
    hits, importers = values(sets), importers_of(sets)
    found, used = _from_tables(sets, root, hits)
    found += _records_alone(hits, used) + (_json_tables(sets, root) if root else [])
    stored, out = _stored(hits), []
    for row in found:
        where = reach(row['path'], importers)
        if row['kind'] != 'personal' and where != 'product': continue       # records of a domain in tests are fixtures
        out.append(_finding(row, where, stored, fed(row['path'], sets, importers) if where == 'product' else []))
    return out
