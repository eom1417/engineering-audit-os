"""How the data is saved, travels and is kept (M14), sorted into findings: from the code (ast-grep's records of the
saves, eaos/rules/ast-grep/rules/saving.yml; the SQL of the migrations and seeds; the backup the project declares) and
from the running copy (<out>/live/keeping.json, eaos/pipeline/runners/keeping.py; Lighthouse's reports of the crawl).

Each finding: {kind, place, line, severity, evidence: {...}} in the kinds of KINDS. A finding read from the code is a
candidate the running copy confirms when it ran (a whole state saved, both seen); one seen on the copy is a fact of
that run. What the copy could not read (no database of the run's own, no page that saves on its own) is said in
`unmeasured`, never taken for clean.
"""
import json
import re
from pathlib import Path

from ...facts.engine_findings import engine_records
from ...live.keeping.restore import commands

KINDS = {   # kind: severity
    'whole_state_local': 'medium', 'whole_state_request': 'medium', 'growing_queue': 'medium', 'told_early': 'medium',
    'pictures_in_sql': 'medium', 'state_column': 'low', 'backup_skips': 'high', 'no_backup': 'low',   # a hosted database may be backed up by its provider: said, never graded high 'backup_local': 'low',
    'save_resends': 'medium', 'save_grows': 'medium', 'save_large': 'medium', 'save_many': 'low',
    'documents_in_column': 'medium', 'pictures_in_rows': 'medium', 'two_tables': 'low', 'restore_misses': 'high',
    'restore_failed': 'high', 'two_places': 'medium', 'data_in_files': 'low', 'lost_update': 'high', 'page_weight': 'low', 'uncompressed': 'low'}
CODE = {'save_whole_local': 'whole_state_local', 'save_whole_request': 'whole_state_request',
        'save_growing_queue': 'growing_queue', 'save_told_early': 'told_early'}
PICTURE = re.compile(r"data:image/[a-z+]+;base64,[A-Za-z0-9+/=]{40,}")
TABLE = re.compile(r'create\s+table\s+(?:if\s+not\s+exists\s+)?(?:"?\w+"?\.)?"?(\w+)"?', re.I)
STATE_COLUMN = re.compile(r'^\s*"?(data|state|document|doc|payload|snapshot|content|blob|app_state|store)"?\s+(jsonb?|text)\b', re.I | re.M)
DUMP_TABLES = re.compile(r'(?:-t|--table)[ =]+"?([\w.]+)"?')
DUMPS = re.compile(r'\b(pg_dump|pg_dumpall|mysqldump|mongodump|supabase\s+db\s+dump|sqlite3\b.*\.(?:backup|dump))', re.I)
OFF_HOST = re.compile(r'\b(s3|gs://|gsutil|rclone|scp|rsync|aws\s|az\s+storage|b2\s|upload|dropbox|r2)\b', re.I)
DOCUMENT_AVG, DOCUMENT_MAX = 10 * 1024, 100 * 1024
SKIPPED = {'node_modules', '.git', 'dist', 'build', 'vendor'}


def _finding(kind, place, line=None, **evidence):
    return {'kind': kind, 'place': place, 'line': line, 'severity': KINDS[kind], 'evidence': evidence}


def from_code(sets):
    """The saves ast-grep recorded: a whole store to localStorage or in one request, a queue that only grows, "saved"
    told before the answer."""
    return [_finding(kind, f['location']['path'], f['location'].get('line'), fact_id=f['id'],
                     what=(f['value'].get('captures') or {}).get('S') or (f['value'].get('captures') or {}).get('Q'))
            for record, kind in CODE.items() for f in engine_records(sets, record)]


def _sql_files(root):
    root = Path(root)
    return [p for p in sorted(root.rglob('*.sql')) if not SKIPPED & set(p.relative_to(root).parts)]


def from_sql(root):
    """Pictures written as text into the database by a migration or seed; a column named for a whole state."""
    out = []
    for path in _sql_files(root):
        text, rel = path.read_text(encoding='utf-8', errors='replace'), path.relative_to(root).as_posix()
        pictures = PICTURE.findall(text)
        if pictures: out.append(_finding('pictures_in_sql', rel, text[:text.find(pictures[0])].count('\n') + 1, count=len(pictures)))
        for match in STATE_COLUMN.finditer(text):
            out.append(_finding('state_column', rel, text[:match.start()].count('\n') + 1, column=match.group(1), type=match.group(2)))
    return out


def tables_of(root):
    """The tables the project's SQL creates."""
    return sorted({name.lower() for path in _sql_files(root) for name in TABLE.findall(path.read_text(encoding='utf-8', errors='replace'))})


def _of_backup(command, tables):
    """The findings of one declared backup: the tables it leaves out, and whether it stays on this machine."""
    source, named = command['source'].split(' ')[0], {t.rsplit('.', 1)[-1].lower() for t in DUMP_TABLES.findall(command['text'])}
    skipped = sorted(set(tables) - named) if named else []
    out = [_finding('backup_skips', source, tables=skipped, kept=sorted(named))] if skipped else []
    return out + ([] if OFF_HOST.search(command['text']) else [_finding('backup_local', source)])


def from_backup(root):
    """The backup the project declares: none, one that names only some of the tables, one that stays on this machine."""
    tables, found = tables_of(root), [c for c in commands(root) if DUMPS.search(c['text'])]
    if not tables: return []
    if not found: return [_finding('no_backup', 'package.json' if (Path(root) / 'package.json').is_file() else '.', tables=len(tables))]
    return [row for command in found for row in _of_backup(command, tables)]


def _writes(record):
    kinds = {'resends': 'save_resends', 'grows': 'save_grows', 'large': 'save_large', 'many': 'save_many'}
    return [_finding(kinds[row['kind']], row['page'], None, **{k: v for k, v in row.items() if k not in ('kind',)})
            for row in record.get('writes') or []]


def _stored(record):
    stored = record.get('stored') if isinstance(record.get('stored'), dict) else {}
    columns = stored.get('columns') or []
    out = [_finding('documents_in_column', f"{c['table']}.{c['column']}", None, **c) for c in columns
           if c['average'] > DOCUMENT_AVG or c['largest'] > DOCUMENT_MAX]
    out += [_finding('pictures_in_rows', f"{c['table']}.{c['column']}", None, **c) for c in columns if c['images']]
    return out + [_finding('two_tables', '.'.join(s['one']), None, **s) for s in stored.get('shared') or []]


def _restore(record):
    drill = record.get('restore') if isinstance(record.get('restore'), dict) else {}
    if drill.get('error') or drill.get('why'):
        return [_finding('restore_failed', drill.get('source') or 'database', None, why=drill.get('error') or drill.get('why'))]
    if drill.get('missing') or drill.get('differ'):
        return [_finding('restore_misses', drill.get('source') or 'database', None, how=drill.get('how'),
                         missing=drill.get('missing'), differ=drill.get('differ'))]
    return []


def _places(record):
    written = record.get('files') if isinstance(record.get('files'), list) else []
    if not written: return []
    database = (record.get('database') or {}).get('kind')
    return [_finding('two_places' if database else 'data_in_files', written[0]['path'], None, files=written, database=database)]


def _lost(record):
    rows = record.get('lost_update') if isinstance(record.get('lost_update'), list) else []
    return [_finding('lost_update', row['route'], None, **row) for row in rows if row.get('lost')]


def from_copy(out):
    """What the running copy showed (live/keeping.json)."""
    try: record = json.loads((Path(out) / 'live/keeping.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): return [], None
    return _writes(record) + _stored(record) + _restore(record) + _places(record) + _lost(record), record


def _audits(path):
    """(the page's address, its Lighthouse audits) of one report, or None."""
    try: report = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError): return None
    return (report.get('finalUrl') or path.parent.name, report.get('audits') or {}) if isinstance(report, dict) else None


def _failed(audit, bar):
    return audit.get('score') is not None and audit['score'] < bar


def from_lighthouse(out):
    """Lighthouse's own audits of the crawl's pages: the page's total weight and text sent uncompressed."""
    found = []
    for url, audits in filter(None, map(_audits, sorted((Path(out) / 'live/crawl').rglob('*.json')))):
        weight, compression = audits.get('total-byte-weight') or {}, audits.get('uses-text-compression') or {}
        if _failed(weight, 0.5): found.append(_finding('page_weight', url, None, bytes=int(weight.get('numericValue') or 0)))
        if _failed(compression, 0.9):
            found.append(_finding('uncompressed', url, None, saving=(compression.get('details') or {}).get('overallSavingsBytes')))
    return found


def unmeasured(record):
    """What the copy could not read, in words: none of it is taken for clean."""
    if record is None: return ['the app did not run, so no save was measured and no database was read']
    out = []
    if (record.get('database') or {}).get('why'): out.append(record['database']['why'])
    if not (record.get('writes_before') or {}).get('pages'): out.append('no page was opened to measure its saves')
    return out


def findings(out, sets, root):
    """Every finding of M14, the code's and the copy's, and what was not measured."""
    copied, record = from_copy(out)
    found = from_code(sets) + (from_sql(root) + from_backup(root) if root else []) + copied + from_lighthouse(out)
    return found, unmeasured(record)
