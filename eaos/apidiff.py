"""The public surface, and what changing it would break for a consumer.

A caller does not care that a file changed; it cares that a name it calls disappeared or now takes
different arguments. That is the only difference this reports as breaking.
"""
from pathlib import Path
from .compose import Document
from .discovery import classify
from .facts.store import read_set
from .workspace import write

LIMITS = [
    'The surface is what the snapshot exports; a consumer may also rely on names this misses.',
    'Parameter names are compared, not types or defaults, so a compatible rename reads as breaking.',
    'Removing a name that no consumer used is reported as breaking all the same.',
]


def surface(sets, include_tests=False):
    """Exported symbols outside test code, keyed by module and name."""
    rows = {}
    for fact in sets.get('syntax', {}).get('facts', []):
        if fact['kind'] != 'symbol': continue
        path = fact['location']['path']
        if not include_tests and classify(path) == 'test': continue
        value = fact['value']
        if not value.get('exported'): continue
        if value.get('parent'): continue
        key = f"{path}::{value['name']}"
        rows[key] = {'path': path, 'name': value['name'], 'kind': value['kind'],
                     'signature': (value.get('signature') or {}).get('parameters'),
                     'required': (value.get('signature') or {}).get('required'),
                     'line': fact['location']['start_line']}
    return rows


def compare(before, after):
    removed = [before[key] for key in sorted(set(before) - set(after))]
    added = [after[key] for key in sorted(set(after) - set(before))]
    changed = []
    for key in sorted(set(before) & set(after)):
        old, new = before[key], after[key]
        if old['signature'] is None or new['signature'] is None: continue
        if old['signature'] == new['signature']: continue
        lost = [name for name in old['signature'] if name not in new['signature']]
        gained = [name for name in new['signature'] if name not in old['signature']]
        breaking = bool(lost) or (new.get('required') or 0) > (old.get('required') or 0)
        changed.append({**new, 'from_signature': old['signature'], 'to_signature': new['signature'],
                        'removed_parameters': lost, 'added_parameters': gained, 'breaking': breaking})
    breaking = removed + [row for row in changed if row['breaking']]
    return {'removed': removed, 'changed': changed, 'added': added,
            'breaking': breaking, 'counts': {'removed': len(removed), 'changed': len(changed),
                                             'added': len(added), 'breaking': len(breaking)}}


def document(result, language):
    doc = Document('سطح الكسر بين لقطتين' if language == 'ar' else 'Breaking-change surface', language, budget_lines=160)
    counts = result['counts']
    doc.header([f"breaking {counts['breaking']} · removed {counts['removed']} · "
                f"signature changes {counts['changed']} · added {counts['added']}",
                'الإضافة ليست كسرًا؛ الحذف وتغيير المعاملات هما الكسر.' if language == 'ar'
                else 'An addition is not a break; a removal or a parameter change is.'])
    doc.section('كاسر' if language == 'ar' else 'Breaking')
    doc.table(['الاسم' if language == 'ar' else 'name', 'الموضع' if language == 'ar' else 'location',
               'ماذا حدث' if language == 'ar' else 'what changed'],
              [[row['name'], f"{row['path']}:{row['line']}",
                'removed' if 'from_signature' not in row else
                f"parameters {row['from_signature']} → {row['to_signature']}"]
               for row in result['breaking']], limit=30)
    doc.section('غير كاسر' if language == 'ar' else 'Non-breaking')
    doc.table(['الاسم' if language == 'ar' else 'name', 'الموضع' if language == 'ar' else 'location',
               'النوع' if language == 'ar' else 'kind'],
              [[row['name'], f"{row['path']}:{row['line']}", 'added'] for row in result['added']], limit=20)
    return doc


def run(before_out, after_out, language='ar'):
    before = read_set(Path(before_out), 'syntax')
    after = read_set(Path(after_out), 'syntax')
    result = compare(surface({'syntax': before}), surface({'syntax': after}))
    write(Path(after_out) / 'api-diff.json', result)
    (Path(after_out) / 'API-DIFF.md').write_text(document(result, language).render(), encoding='utf-8')
    return {'before': str(before_out), 'after': str(after_out), 'counts': result['counts'],
            'breaking': [f"{row['path']}::{row['name']}" for row in result['breaking']][:20],
            'status': 'BREAKING' if result['breaking'] else 'COMPATIBLE', 'limits': LIMITS}
