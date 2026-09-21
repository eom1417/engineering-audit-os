"""RUN.md: what this run did, what it could not do, and why — before any finding is read.

A reader who does not know which stages were absent cannot judge what an empty section means.
"""
from ..compose import Document

TITLE = {'ar': 'ما فعله هذا التشغيل', 'en': 'What this run did'}
WORDS = {
    'ar': {'stage': 'المرحلة', 'status': 'الحالة', 'seconds': 'الثواني', 'reason': 'السبب',
           'produced': 'ما أنتجته', 'header': 'المرحلة التي لم تُشغَّل لا تُثبت شيئًا. اقرأ صف الغياب قبل صف النتائج.',
           'examined': 'ما فُحص', 'absent': 'ما لم يُفحص، وسببه', 'total': 'الإجمالي'},
    'en': {'stage': 'Stage', 'status': 'Status', 'seconds': 'Seconds', 'reason': 'Reason',
           'produced': 'Produced', 'header': 'A stage that did not run proves nothing. Read the absences first.',
           'examined': 'Examined', 'absent': 'Not examined, and why', 'total': 'Total'},
}
STATE = {'ar': {'ok': 'تمّت', 'skipped': 'مُستبعدة', 'unavailable': 'غير متاحة', 'failed': 'فشلت',
                'not_reached': 'لم تُبلَغ'},
         'en': {'ok': 'ok', 'skipped': 'skipped', 'unavailable': 'unavailable', 'failed': 'failed',
                'not_reached': 'not reached'}}


def document(manifest, language='ar'):
    words = WORDS.get(language, WORDS['ar'])
    states = STATE.get(language, STATE['ar'])
    doc = Document(TITLE.get(language, TITLE['ar']), language, budget_lines=120)
    doc.header([words['header'],
                f"{words['total']}: {manifest['seconds']}s · {manifest['status']}"])
    ran = [(name, row) for name, row in manifest['stages'].items() if row['status'] == 'ok']
    absent = [(name, row) for name, row in manifest['stages'].items() if row['status'] != 'ok']
    doc.section(words['examined'])
    doc.table([words['stage'], words['seconds'], words['produced']],
              [[name, f"{row['seconds']:.2f}", ', '.join(row['artifacts']) or '—'] for name, row in ran])
    doc.section(words['absent'])
    doc.table([words['stage'], words['status'], words['reason']],
              [[name, states.get(row['status'], row['status']), row['reason']] for name, row in absent])
    return doc
