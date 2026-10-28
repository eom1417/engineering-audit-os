"""The claims how the data is saved and kept earns (M14), one per finding of eaos/analysis/assessments/data_keeping.py,
made beside the runtime claims since half of them were seen on the running copy. A finding the copy showed is
CONFIRMED (something ran); one read from the code is LIKELY, and the judge (the card triage) reads it. A code finding has
a probe that reads the code again; a copy finding only a new run can close.
"""
from . import ledger
from ..assessments.data_keeping import findings

WORDS = {   # kind: (English, Arabic, fix in English, fix in Arabic); {place} {line} and the finding's evidence fill them
    'whole_state_local': ("{place}:{line} writes the whole of {what} to localStorage in one value on every save",
                          "{place}:{line} يكتب {what} كله في localStorage كقيمة وحدة مع كل حفظ",
                          'Save only what changed, keyed by record; keep the whole state on the server, and in the browser only what the screen needs offline.',
                          'احفظ اللي تغيّر بس، كل سجل بمفتاحه؛ والبيانات كلها مكانها الخادم، والمتصفح ما يحفظ إلا اللي تحتاجه الشاشة بدون اتصال.'),
    'whole_state_request': ("{place}:{line} sends the whole of {what} in one request to save it",
                            "{place}:{line} يرسل {what} كله في طلب واحد عشان يحفظه",
                            'Send the change only (the record that changed, by its id): the save stays small however much data the person has.',
                            'أرسل التغيير بس (السجل اللي تغيّر برقمه): يبقى الحفظ صغير مهما كبرت بيانات الشخص.'),
    'growing_queue': ("{place}:{line} keeps a queue in localStorage that is added to and never trimmed; it fails once the browser's quota is full",
                      "{place}:{line} يحفظ طابورًا في localStorage يزيد وما ينقص أبدًا؛ ويتوقف لما تمتلئ مساحة المتصفح",
                      'Remove an entry once the server took it, bound the queue, and catch the quota error so nothing is lost silently.',
                      'احذف العنصر أول ما يستلمه الخادم، وحط حد للطابور، والتقط خطأ امتلاء المساحة عشان ما يضيع شي بصمت.'),
    'told_early': ("{place}:{line} tells the person it saved without reading the server's answer",
                   "{place}:{line} يقول للشخص إنه حفظ بدون ما يقرأ رد الخادم",
                   "Say saved only after the answer is ok; show the failure and keep the change when it is not.",
                   'لا تقول "تم الحفظ" إلا بعد ما يكون الرد سليم؛ وإذا فشل اعرض الخطأ وخلّ التغيير.'),
    'pictures_in_sql': ("{place}:{line} writes {count} pictures into the database as base64 text",
                        "{place}:{line} يكتب {count} صورة داخل قاعدة البيانات كنص base64",
                        'Keep pictures as files (object storage) and only their address in the row.',
                        'خلّ الصور ملفات (في تخزين الملفات) وخلّ في السجل عنوانها بس.'),
    'state_column': ("{place}:{line} keeps a whole {column} in one {type} column: each save rewrites all of it",
                     "{place}:{line} يحفظ {column} كله في عمود {type} واحد: كل حفظ يعيد كتابته كله",
                     'Give the records their own table and columns; keep a JSON column for what truly has no fixed shape.',
                     'خلّ للسجلات جدولها وأعمدتها؛ وعمود JSON بس للي فعلًا ما له شكل ثابت.'),
    'backup_skips': ("The backup in {place} dumps only {kept}: the tables {tables} are not in it",
                     "النسخة الاحتياطية في {place} تأخذ {kept} بس: والجداول {tables} مو فيها",
                     'Dump the whole database (pg_dump without -t), then restore it into an empty database and compare, as EAOS did.',
                     'خذ نسخة من القاعدة كلها (pg_dump بدون -t)، وبعدها استرجعها في قاعدة فاضية وقارن، مثل ما سوّى EAOS.'),
    'no_backup': ("The project declares no backup of its database ({tables} tables); a hosted database's own backups, if any, are not seen from the code",
                  "المشروع ما فيه أي نسخة احتياطية لقاعدة بياناته ({tables} جدول)؛ ونسخ المزوّد الاحتياطية، إن وُجدت، ما تبين من الكود",
                  "Add a scheduled backup of the whole database to storage off this machine, and try restoring it once.",
                  'أضف نسخة احتياطية مجدولة للقاعدة كلها في مكان خارج هالجهاز، وجرّب تسترجعها مرة.'),
    'backup_local': ("The backup in {place} stays on the machine it was made on",
                     "النسخة الاحتياطية في {place} تبقى على نفس الجهاز اللي انسوت فيه",
                     'Copy each backup off the host (object storage, another region): a backup on the same disk goes with it.',
                     'انسخ كل نسخة احتياطية خارج الجهاز (تخزين ملفات، منطقة ثانية): النسخة اللي على نفس القرص تروح معه.'),
    'save_resends': ("{method} {path} is sent with every one of the {records} records the page read from {read}: the whole collection for one change (pages: {pages})",
                     "{method} {path} ينرسل ومعه كل السجلات ({records}) اللي قرأتها الصفحة من {read}: المجموعة كلها عشان تغيير واحد (الصفحات: {pages})",
                     'Send only the record that changed, by its id.', 'أرسل السجل اللي تغيّر بس، برقمه.'),
    'save_grows': ("The save {method} {path} of {place} grew from {before} to {bytes} bytes once the copy held more data: it carries the data, not the change",
                   "الحفظ {method} {path} في {place} كبر من {before} إلى {bytes} بايت لما زادت البيانات: يحمل البيانات كلها مو التغيير",
                   'Send the change only; the size of a save must not follow the size of the data.', 'أرسل التغيير بس؛ حجم الحفظ لازم ما يكبر مع حجم البيانات.'),
    'save_large': ("The page {place} sends {method} {path} of {bytes} bytes on its own",
                   "الصفحة {place} ترسل {method} {path} بحجم {bytes} بايت من نفسها",
                   'Send the change only, and compress what must stay large.', 'أرسل التغيير بس، واضغط اللي لازم يبقى كبير.'),
    'save_many': ("Opening {place} sends {count} writes ({bytes} bytes) without the person doing anything",
                  "فتح {place} يرسل {count} طلب كتابة ({bytes} بايت) بدون ما يسوي الشخص شي",
                  'Write when the person changes something, once per change.', 'اكتب لما يغيّر الشخص شي، مرة لكل تغيير.'),
    'documents_in_column': ("{place} holds whole documents: {average} bytes a row on average, {largest} at most",
                            "{place} فيه مستندات كاملة: {average} بايت للسجل بالمتوسط، وأكبرها {largest}",
                            'Split the document into its records; a save then writes one row, not all of it.', 'قسّم المستند إلى سجلاته؛ عشان الحفظ يكتب سجل واحد مو المستند كله.'),
    'pictures_in_rows': ("{place} keeps {images} pictures inside its rows as text",
                         "{place} يحفظ {images} صورة داخل سجلاته كنص",
                         'Move the pictures to file storage and keep their address in the row.', 'انقل الصور لتخزين الملفات وخلّ عنوانها في السجل.'),
    'two_tables': ("The same values are kept in two tables: {one} and {other} ({values} in common)",
                   "نفس القيم محفوظة في جدولين: {one} و{other} ({values} مشتركة)",
                   'Keep each value in one table and point to it from the other; two copies drift apart at the first edit.',
                   'خلّ كل قيمة في جدول واحد والثاني يشير لها؛ النسختين يختلفون من أول تعديل.'),
    'restore_misses': ("The backup ({how}) restored into an empty database lacks {missing} and differs in {differ}",
                       "النسخة الاحتياطية ({how}) لما انسترجعت في قاعدة فاضية ناقصها {missing} ومختلفة في {differ}",
                       'Back up every table; prove it the way EAOS did: restore into an empty database and compare table by table.',
                       'خذ نسخة من كل الجداول؛ وأثبتها مثل ما سوّى EAOS: استرجعها في قاعدة فاضية وقارن جدول جدول.'),
    'restore_failed': ("The backup could not be restored into an empty database: {why}",
                       "النسخة الاحتياطية ما قدرت تنسترجع في قاعدة فاضية: {why}",
                       'Make the backup restorable and try it: a backup nobody restored is not a backup.', 'خلّ النسخة الاحتياطية قابلة للاسترجاع وجرّبها: نسخة ما أحد استرجعها ما تعتبر نسخة.'),
    'two_places': ("While the app ran, its server wrote data into files ({place}, {count} files) besides its database ({database}): the data is kept in two places",
                   "وقت ما اشتغل التطبيق، خادمه كتب بيانات في ملفات ({place}، {count} ملف) غير قاعدة البيانات ({database}): البيانات محفوظة في مكانين",
                   'Keep each kind of data in one place, the database, and write files only for what is a file.',
                   'خلّ كل نوع بيانات في مكان واحد، قاعدة البيانات، والملفات بس للي هو فعلًا ملف.'),
    'data_in_files': ("While the app ran, its server kept its data in files ({place}, {count} files), with no database",
                      "وقت ما اشتغل التطبيق، خادمه حفظ بياناته في ملفات ({place}، {count} ملف) بدون قاعدة بيانات",
                      'Keep the data in a database: files written by a request are lost on the next deploy and break with two writers.',
                      'خلّ البيانات في قاعدة بيانات: الملفات اللي يكتبها الطلب تضيع مع أول نشر وتخرب لو كتب اثنين بنفس الوقت.'),
    'lost_update': ("Two people editing one record lose an edit: {route} took a change made from an old copy over the newer one, with no conflict",
                    "لما يعدّل شخصين نفس السجل يضيع تعديل: {route} قبِل تغيير من نسخة قديمة فوق الأحدث بدون أي تنبيه",
                    'Send the version read (updated_at or a version number) with each write and refuse a stale one (409).',
                    'أرسل نسخة السجل اللي انقرأت (updated_at أو رقم نسخة) مع كل كتابة وارفض القديمة (409).'),
    'page_weight': ("The page {place} weighs {bytes} bytes (Lighthouse's total weight)",
                    "الصفحة {place} حجمها {bytes} بايت (الحجم الكلي في Lighthouse)",
                    'Load only what the page shows; page the lists and send pictures at the size shown.', 'حمّل اللي تعرضه الصفحة بس؛ قسّم القوائم صفحات وأرسل الصور بالحجم المعروض.'),
    'uncompressed': ("The page {place} sends its text uncompressed (Lighthouse: {saving} bytes to save)",
                     "الصفحة {place} ترسل نصوصها بدون ضغط (Lighthouse: يوفر {saving} بايت)",
                     'Turn compression on in the server (gzip or brotli).', 'شغّل الضغط في الخادم (gzip أو brotli).'),
}
CODE = {'whole_state_local', 'whole_state_request', 'growing_queue', 'told_early', 'pictures_in_sql', 'state_column',
        'backup_skips', 'no_backup', 'backup_local'}


def _filled(text, finding):
    values = {'place': finding['place'], 'line': finding['line'], **finding['evidence']}
    values = {k: (', '.join(map(str, v)) if isinstance(v, list) and not (v and isinstance(v[0], dict)) else v) for k, v in values.items()}
    values.setdefault('count', len(finding['evidence'].get('files') or []))
    try: return text.format(**values)
    except (KeyError, IndexError): return text.split('{')[0].strip()


def params(finding):
    en, ar, fix_en, fix_ar = (_filled(text, finding) for text in WORDS[finding['kind']])
    return {'kind': finding['kind'], 'severity': finding['severity'], 'en': en, 'ar': ar, 'fix_en': fix_en, 'fix_ar': fix_ar,
            'place': finding['place'].split('.')[0] if finding['kind'] in ('documents_in_column', 'pictures_in_rows') else finding['place'],
            'line': finding['line'], 'category': 'data'}


def keeping_claims(out, sets, target, offset):
    """Every claim of M14, numbered after `offset`: one per finding with its fact (a code finding) or its run's record."""
    found, _ = findings(out, sets, target)
    rows = []
    for finding in found:
        from_code = finding['kind'] in CODE
        confidence = 'LIKELY' if from_code else 'CONFIRMED'
        rendered = params(finding)
        fact = finding['evidence'].get('fact_id')
        rows.append(ledger.make(offset + len(rows) + 1, rendered['en'], 'risk', confidence,
                                ['static_fact' if from_code else 'runtime_probe'], [] if fact else [finding['place'] if from_code else 'live/keeping.json'],
                                'The code, or a new run of the copy, no longer showing it.', fact_ids=[fact] if fact else None,
                                confidence_ceiling=confidence, render={'key': 'data_keeping', 'params': rendered},
                                probe_spec={'probe_type': 'graph_query', 'specification': {'query': 'data_keeping_present', 'kind': finding['kind'],
                                                                                           'place': finding['place'], 'engines': ['ast-grep']}}
                                if finding['kind'] in ('whole_state_local', 'whole_state_request', 'growing_queue', 'told_early') else None,
                                impact={'scenario': rendered['fix_en']}))
    return rows


def present(specification, sets):
    """The probe of a code card: CONFIRMED while ast-grep still records it at its place."""
    from ..assessments.data_keeping import from_code
    if any(f['kind'] == specification['kind'] and f['place'] == specification['place'] for f in from_code(sets)):
        return 'CONFIRMED', f"{specification['place']} still saves this way"
    return 'REFUTED', f"{specification['place']} no longer saves this way"
