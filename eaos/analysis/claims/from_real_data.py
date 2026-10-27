"""The claims real data in the code earns (M12.3): one per table or record eaos/analysis/assessments/real_data.py sorted
as data, each saying what it holds, where it sits, where the data goes and the screens it feeds.

Personal values in the product are CONFIRMED and high (they ship in every copy of the code; in a migration, into every
database); records of a domain in the product are LIKELY and medium; real-looking personal values only in tests,
stories, documents, mocks or a seed are low (replaced by placeholders); a table of one domain word is a HYPOTHESIS the
card triage (the judge) reads. The card's probe asks Presidio and ast-grep again: gone from the file, it is closed.
"""
from ..assessments.real_data import importers_of, findings, tables

ENGINES = ('presidio', 'ast-grep')
NOUNS = {'PERSON': ('name', 'names', 'أسماء'), 'AR_NAME': ('name', 'names', 'أسماء'),
         'EMAIL_ADDRESS': ('e-mail address', 'e-mail addresses', 'عناوين بريد'), 'SA_PHONE': ('mobile number', 'mobile numbers', 'أرقام جوال'),
         'PHONE_NUMBER': ('phone number', 'phone numbers', 'أرقام هاتف'), 'SA_NATIONAL_ID': ('national id', 'national ids', 'أرقام هوية'),
         'IBAN_CODE': ('IBAN', 'IBANs', 'أرقام آيبان'), 'CREDIT_CARD': ('card number', 'card numbers', 'أرقام بطاقات')}
WHAT = {'data_table': ('a table of records', 'جدول سجلات'), 'dated_map': ('a table keyed by dates or months', 'جدول مرتب بالتواريخ أو الشهور'),
        'json': ('a JSON table the product imports', 'جدول JSON يستورده البرنامج'), 'record': ('a record of personal values', 'سجل بيانات شخصية')}
PLACES = {'test': ('tests', 'الاختبارات'), 'story': ('stories', 'القصص المصورة'), 'docs': ('documents and examples', 'الوثائق والأمثلة'),
          'mock': ('mocks and fixtures', 'البيانات الوهمية'), 'seed': ('a seed', 'ملف بذرة')}
SEVERITY = {('personal', 'product'): 'high', ('personal', 'migration'): 'high', ('domain', 'product'): 'medium',
            ('doubtful', 'product'): 'medium'}
CONFIDENCE = {'personal': 'CONFIRMED', 'domain': 'LIKELY', 'doubtful': 'HYPOTHESIS'}


def _held(entities, language):
    """'4 names, 2 IBANs' / 'أسماء (4)، أرقام آيبان (2)': the values a finding holds, by kind."""
    counts = {}
    for entity, count in entities.items():
        same = 'PERSON' if entity == 'AR_NAME' else entity                   # a name is a name, in either language
        counts[same] = counts.get(same, 0) + count
    if language == 'ar': return '، '.join(f'{NOUNS[e][2]} ({n})' for e, n in counts.items())
    return ', '.join(f'{n} {NOUNS[e][0] if n == 1 else NOUNS[e][1]}' for e, n in counts.items())


def _where(row):
    lines = f"{row['line']}-{row['end_line']}" if row.get('end_line') and row['end_line'] != row['line'] else str(row['line'])
    return f"{row['path']}:{lines}"


def sentences(row):
    """(English, Arabic) of the card's title."""
    what, place, held = WHAT[row['record']], _where(row), (_held(row['entities'], 'en'), _held(row['entities'], 'ar'))
    if row['kind'] == 'personal':
        en, ar = f"Real personal data written in the code: {what[0]} in {place}", f"بيانات شخصية حقيقية مكتوبة في الكود: {what[1]} في {place}"
        en, ar = f"{en} holds {held[0]}", f"{ar} فيه {held[1]}"
    elif row['kind'] == 'domain':
        en, ar = f"Data written in the code: {what[0]} in {place} holds the program's records", f"بيانات مكتوبة في الكود: {what[1]} في {place} فيه سجلات البرنامج"
    else:
        en, ar = f"Maybe data written in the code: {what[0]} in {place}", f"قد تكون بيانات مكتوبة في الكود: {what[1]} في {place}"
    if row['place'] in PLACES: en, ar = f"{en}, in {PLACES[row['place']][0]}", f"{ar}، في {PLACES[row['place']][1]}"
    if row['feeds']: en, ar = f"{en}; it feeds {', '.join(row['feeds'])}", f"{ar}؛ تقرأ منه {'، '.join(row['feeds'])}"
    return en, ar


def fixes(row):
    """(English, Arabic): where the data goes."""
    if row['place'] == 'migration':
        return ('Take these records out of the migration: a migration runs on every database. Load real records into the '
                'production database directly, never from the repository.',
                'أخرج هذه السجلات من ملف الترحيل: الترحيل يشتغل على كل قاعدة بيانات. البيانات الحقيقية تُدخل في قاعدة الإنتاج مباشرة، مو من الريبو.')
    if row['place'] != 'product':
        return ('Replace the real values with placeholders (John Doe, someone@example.com, 0500000000): real people\'s data '
                'does not belong in tests, stories, documents or seeds.',
                'بدّل القيم الحقيقية بقيم تجريبية (John Doe و someone@example.com و 0500000000): بيانات الناس الحقيقية ما مكانها الاختبارات ولا الوثائق ولا ملفات البذرة.')
    if row['in_database']:
        stored = ', '.join(row['in_database'])
        return (f'The database already holds these values ({stored}): read them from there through the data layer and '
                'delete this copy from the code.',
                f'قاعدة البيانات فيها نفس القيم ({stored}): اقرأها منها عن طريق طبقة البيانات واحذف النسخة اللي في الكود.')
    return ('Move these records into the database (a table, filled once by a seed kept outside the product), read them '
            'through the app\'s data layer and delete them from the code: an empty database then shows empty screens, '
            'never these records.',
            'انقل هذه السجلات إلى قاعدة البيانات (جدول يُعبّأ مرة واحدة من ملف بذرة خارج البرنامج)، واقرأها عن طريق طبقة بيانات '
            'التطبيق، واحذفها من الكود: فإذا كانت القاعدة فاضية تطلع الشاشات فاضية، مو بهذه السجلات.')


def real_data(fact_sets, add, target):
    """One claim per table or record of real data (eaos/analysis/claims/ledger.py BUILDERS)."""
    for row in findings(fact_sets, target):
        if not row['fact_ids']: continue
        (en, ar), (fix_en, fix_ar) = sentences(row), fixes(row)
        severity, confidence = SEVERITY.get((row['kind'], row['place']), 'low'), CONFIDENCE[row['kind']]
        add(en, 'risk', confidence, ['static_fact'],
            f"Presidio and ast-grep no longer finding {WHAT[row['record']][0]} of real data in {row['path']}.",
            fact_ids=row['fact_ids'], confidence_ceiling=confidence,
            render={'key': 'real_data', 'params': {'kind': row['kind'], 'place': row['path'], 'reached': row['place'], 'severity': severity,
                                                   'category': 'security' if row['kind'] == 'personal' else 'data',
                                                   'en': en, 'ar': ar, 'fix_en': fix_en, 'fix_ar': fix_ar, 'path': row['path'],
                                                   'line': row['line'], 'entities': row['entities'], 'feeds': row['feeds'],
                                                   'in_database': row['in_database']}},
            probe_spec={'probe_type': 'graph_query',
                        'specification': {'query': 'real_data_present', 'path': row['path'], 'kind': row['kind'], 'record': row['record'],
                                          'engines': list(ENGINES), 'expected': 'The file still holds this data.'}},
            impact={'scenario': fix_en})


def present(specification, sets):
    """The probe of a real-data card: CONFIRMED while the file still holds what the card found. Personal values are
    sorted again; a table of the domain is still there while ast-grep still records a table in its file (its keys were
    read when the card was made); a JSON table while the product still imports it."""
    if not any(f['kind'] == 'symbol_metric_external' for f in (sets.get('external') or {}).get('facts', [])):
        return 'INCONCLUSIVE', 'Presidio and ast-grep recorded nothing to read'
    path, kind = specification['path'], specification['kind']
    if kind == 'personal': still = any(r['path'] == path and r['kind'] == kind for r in findings(sets))
    elif specification.get('record') == 'json': still = path in importers_of(sets)
    else: still = any(t['path'] == path for t in tables(sets))
    if still: return 'CONFIRMED', f"{path} still holds {kind} data"
    return 'REFUTED', f"{path} no longer holds {kind} data"
