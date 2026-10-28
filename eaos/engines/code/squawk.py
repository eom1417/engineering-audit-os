"""Squawk: risky PostgreSQL migrations (M14.3): a NOT NULL column added without a default, no lock timeout, a type
changed in place, an index built while writes wait. It reads the project's migrations (a `migrations` folder, or
Supabase's), never its other SQL; each violation is a finding of the shared kind `sql_quality`, its rule named.
Squawk sees a migration's risk, not a design (a whole document kept in one column): the run's own database is read
for that (eaos/live/keeping/database.py).
"""
import json
from pathlib import Path

from .. import tool
from ..contract import OBSERVED, Capability, Report, finding, measurement, subject
from ..process import run, which

NAME = BINARY = 'squawk'
PINNED = tool.pinned(NAME)
SKIPPED = ('node_modules', '.git', 'dist', 'build', 'vendor')
# The rules that risk the data or hold the table: a finding each, medium when the data can be lost. The rest (prefer
# bigint, identity, text fields, IF NOT EXISTS, a lock timeout on every statement) are counted, never findings.
LOSS = {'ban-drop-column', 'ban-drop-table', 'ban-drop-database', 'changing-column-type', 'renaming-column', 'renaming-table',
        'ban-truncate-cascade', 'adding-required-field', 'adding-not-nullable-field'}
HOLDS = {'require-concurrent-index-creation', 'require-concurrent-index-deletion', 'constraint-missing-not-valid',
         'adding-foreign-key-constraint', 'disallowed-unique-constraint', 'adding-serial-primary-key-field',
         'adding-field-with-default', 'ban-alter-domain-with-add-constraint'}


def capabilities(): return [Capability('sql_quality', '*')]


def migrations(target, exclude=()):
    """The project's migration files: .sql files under a folder named migrations (or migrate)."""
    root = Path(target)
    return sorted(str(p.relative_to(root)) for p in root.rglob('*.sql')
                  if {'migrations', 'migrate'} & set(p.relative_to(root).parts[:-1])
                  and not set(p.relative_to(root).parts) & set(SKIPPED + tuple(exclude)))


def findings(rows, found):
    """The findings of Squawk's JSON report: one per risky violation, at its file and line (Squawk counts from 0)."""
    out = []
    for row in rows:
        rule = row.get('rule_name') or 'squawk'
        if rule not in LOSS | HOLDS: continue
        path, line = tool.relative(row.get('file') or ''), (row.get('line') or 0) + 1
        message = ' '.join(filter(None, [f'{rule}:', row.get('message'), row.get('help')]))
        out.append(finding(NAME, found, rule, 'sql_quality', subject('file', f'{path}:{line}:{rule}', path, line), message,
                           measurements=[measurement('severity', 'medium' if rule in LOSS else 'low')], raw_ref=f'{NAME}/squawk.json'))
    return out


@tool.engine(NAME, BINARY)
def analyze(target, workdir, exclude, formats, found):
    files = migrations(target, exclude)
    if not files:
        return Report(NAME, found, PINNED, OBSERVED, coverage={'status': 'observed', 'files': 0, 'note': 'no migration folder'},
                      evaluated={'sql_quality': {'status': 'observed', 'granularity': 'file'}})
    output = workdir / 'squawk.json'
    code, out, error, seconds = run([which(BINARY), '--reporter', 'json', *files], cwd=target)
    try: rows = json.loads(out or '[]')
    except ValueError: return tool.failed(NAME, found, seconds, code, error or out)
    output.write_text(out or '[]', encoding='utf-8')
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, findings=findings(rows, found), raw=str(output),
                  coverage={'status': 'observed', 'files': len(files), 'violations': len(rows),
                            'by_rule': dict(sorted({r.get('rule_name'): sum(x.get('rule_name') == r.get('rule_name') for x in rows) for r in rows}.items()))},
                  evaluated={'sql_quality': {'status': 'observed', 'granularity': 'file'}})
