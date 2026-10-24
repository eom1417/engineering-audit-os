"""RUN.md: what this run did, what it could not do, and why — before any finding is read.

A reader who does not know which stages were absent cannot judge what an empty section means.
"""
from ..core.document import Document

TITLE = {'ar': 'ما فعله هذا التشغيل', 'en': 'What this run did'}
WORDS = {
    'ar': {'stage': 'المرحلة', 'status': 'الحالة', 'seconds': 'الثواني', 'reason': 'السبب',
           'produced': 'ما أنتجته', 'header': 'المرحلة التي لم تُشغَّل لا تُثبت شيئًا. اقرأ صف الغياب قبل صف النتائج.',
           'examined': 'ما فُحص', 'absent': 'ما لم يُفحص، وسببه', 'total': 'الإجمالي',
           'without': 'بدأ الفحص بدون هذه الأدوات لأن تثبيتها فشل'},
    'en': {'stage': 'Stage', 'status': 'Status', 'seconds': 'Seconds', 'reason': 'Reason',
           'produced': 'Produced', 'header': 'A stage that did not run proves nothing. Read the absences first.',
           'examined': 'Examined', 'absent': 'Not examined, and why', 'total': 'Total',
           'without': 'The check started without these tools, whose install failed'},
}
STATE = {'ar': {'ok': 'تمّت', 'skipped': 'مُستبعدة', 'unavailable': 'غير متاحة', 'failed': 'فشلت',
                'not_reached': 'لم تُبلَغ'},
         'en': {'ok': 'ok', 'skipped': 'skipped', 'unavailable': 'unavailable', 'failed': 'failed',
                'not_reached': 'not reached'}}


def absences(manifest):
    """[{stage, status, reason: {ar, en}}] of every stage that did not end ok: the catalog's words for its reason_code
    (eaos/data/errors.json reasons), else EAOS's own sentence in both. The one list the report for people, RUN.md and
    the Studio's head read (a real check: ten stages stood still and nobody said why in the person's language)."""
    from ..core.progress.reasons import reasons
    rows = []
    for name, row in (manifest.get('stages') or {}).items():
        if row.get('status') == 'ok': continue
        said = reasons().get(str(row.get('reason_code') or '')) or {}
        did = [r for r in manifest.get('remedies') or [] if r['stage'] == name]
        rows.append({'stage': name, 'status': row.get('status'), 'reason': {lang: said.get(lang) or row.get('reason') or '' for lang in ('ar', 'en')},
                     'did': did[-1]['outcome'] if did else None})
    return rows


def document(manifest, language='ar'):
    words = WORDS.get(language, WORDS['ar'])
    states = STATE.get(language, STATE['ar'])
    doc = Document(TITLE.get(language, TITLE['ar']), language, budget_lines=120)
    without = manifest.get('options', {}).get('without_tools')
    doc.header([words['header'],
                f"{words['total']}: {manifest['seconds']}s · {manifest['status']}",
                f"{words['without']}: {', '.join(without)}" if without else ''])
    ran = [(name, row) for name, row in manifest['stages'].items() if row['status'] == 'ok']
    doc.section(words['examined'])
    doc.table([words['stage'], words['seconds'], words['produced']],
              [[name, f"{row['seconds']:.2f}", ', '.join(row['artifacts']) or '—'] for name, row in ran])
    doc.section(words['absent'])
    doc.table([words['stage'], words['status'], words['reason']],
              [[row['stage'], states.get(row['status'], row['status']), row['reason'][language]] for row in absences(manifest)])
    return doc
