"""RUN.md: what this run did, what it could not do, and why — before any finding is read.

A reader who does not know which stages were absent cannot judge what an empty section means.
"""
from ...core.contracts.document import Document

TITLE = {'ar': 'ما فعله هذا التشغيل', 'en': 'What this run did'}
WORDS = {
    'ar': {'stage': 'المرحلة', 'status': 'الحالة', 'seconds': 'الثواني', 'reason': 'السبب',
           'produced': 'ما أنتجته', 'header': 'المرحلة التي لم تُشغَّل لا تُثبت شيئًا. اقرأ صف الغياب قبل صف النتائج.',
           'examined': 'ما فُحص', 'absent': 'ما لم يُفحص، وسببه', 'total': 'الإجمالي',
           'without': 'بدأ الفحص بدون هذه الأدوات لأن تثبيتها فشل', 'loops': 'ما غطّته كل حلقة من الفحص',
           'loop': 'الحلقة', 'covered': 'ما غطّته', 'missed': 'ما لم تغطّه'},
    'en': {'stage': 'Stage', 'status': 'Status', 'seconds': 'Seconds', 'reason': 'Reason',
           'produced': 'Produced', 'header': 'A stage that did not run proves nothing. Read the absences first.',
           'examined': 'Examined', 'absent': 'Not examined, and why', 'total': 'Total',
           'without': 'The check started without these tools, whose install failed', 'loops': 'What each loop of the check covered',
           'loop': 'Loop', 'covered': 'Covered', 'missed': 'Not covered'},
}
STATE = {'ar': {'ok': 'تمّت', 'skipped': 'مُستبعدة', 'unavailable': 'غير متاحة', 'failed': 'فشلت',
                'not_reached': 'لم تُبلَغ'},
         'en': {'ok': 'ok', 'skipped': 'skipped', 'unavailable': 'unavailable', 'failed': 'failed',
                'not_reached': 'not reached'}}
LOOP_STATE = {'ar': {'met': 'اكتملت', 'explained': 'ناقصة بسبب معروف', 'not_met': 'لم تكتمل', 'running': 'تعمل'},
              'en': {'met': 'met', 'explained': 'short, for a stated reason', 'not_met': 'not met', 'running': 'running'}}
GAP = {'ar': ('فجوة كبيرة', 'لم يُغطَّ'), 'en': ('Big gap', 'not covered')}


def absences(manifest):
    """[{stage, status, reason: {ar, en}}] of every stage that did not end ok: the catalog's words for its reason_code
    (eaos/data/errors.json reasons), else EAOS's own sentence in both. The one list the report for people, RUN.md and
    the Studio's head read (a real check: ten stages stood still and nobody said why in the person's language)."""
    rows = []
    for name, row in (manifest.get('stages') or {}).items():
        if row.get('status') == 'ok': continue
        did = [r for r in manifest.get('remedies') or [] if r['stage'] == name]
        rows.append({'stage': name, 'status': row.get('status'), 'reason': _reason(row),
                     'did': did[-1]['outcome'] if did else None})
    return rows


def big_gaps(record, language='ar'):
    """The red lines at the top of a report: each loop of the check (its `coverage`, eaos/pipeline/coverage.py) whose goal
    was not reached for a reason the person did not choose, with the stages behind it and why."""
    lang = 'en' if language == 'en' else 'ar'
    gap, missing = GAP[lang]
    lines = []
    for entry in record.get('coverage') or []:
        if not entry.get('big'): continue
        rows = {row['stage']: row for row in entry['missed']}
        why = '; '.join(f"{_stage_title(name, lang)}: {_reason(rows.get(name) or {})[lang]}" for name in entry['behind'])
        lines.append(f"🔴 **{gap}: {entry['name'][lang]}** ({missing}). {why}")
    return lines


def _stage_title(name, lang):
    from ...core.language.words import catalog
    title = (catalog()['stages'].get(name) or {}).get('title')
    return title[0 if lang == 'ar' else 1] if title else name


def _loops(doc, manifest, language, words):
    """The coverage ledger's table: each loop, its state, how many of its stages covered, and those that were not."""
    states = LOOP_STATE.get(language, LOOP_STATE['ar'])
    doc.section(words['loops'])
    doc.table([words['loop'], words['status'], words['covered'], words['missed']],
              [[entry['name'].get(language, entry['loop']), states.get(entry['state'], entry['state']),
                f"{len(entry['covered'])}/{len(entry['covered']) + len(entry['missed'])}",
                ', '.join(row['stage'] for row in entry['missed']) or '—'] for entry in manifest.get('coverage') or []])


def _reason(row):
    """{ar, en} of why a stage did not end ok: the catalog's words for its reason_code, else EAOS's own sentence."""
    from ...core.progress.reasons import reasons
    said = reasons().get(str(row.get('reason_code') or '')) or {}
    return {lang: said.get(lang) or row.get('reason') or '' for lang in ('ar', 'en')}


def document(manifest, language='ar'):
    words = WORDS.get(language, WORDS['ar'])
    states = STATE.get(language, STATE['ar'])
    doc = Document(TITLE.get(language, TITLE['ar']), language, budget_lines=120)
    without = manifest.get('options', {}).get('without_tools')
    doc.header([words['header'],
                f"{words['total']}: {manifest['seconds']}s · {manifest['status']}",
                f"{words['without']}: {', '.join(without)}" if without else '', *big_gaps(manifest, language)])
    ran = [(name, row) for name, row in manifest['stages'].items() if row['status'] == 'ok']
    doc.section(words['examined'])
    doc.table([words['stage'], words['seconds'], words['produced']],
              [[name, f"{row['seconds']:.2f}", ', '.join(row['artifacts']) or '—'] for name, row in ran])
    _loops(doc, manifest, language, words)
    doc.section(words['absent'])
    doc.table([words['stage'], words['status'], words['reason']],
              [[row['stage'], states.get(row['status'], row['status']), row['reason'][language]] for row in absences(manifest)])
    return doc
