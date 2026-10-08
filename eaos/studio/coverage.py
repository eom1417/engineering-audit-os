"""studio/coverage.json: what EAOS measured for this report and what it has not measured yet (contract v2, docs/STUDIO.md D7).

Every section the Studio reads gets one row: its state, the reason as a stable code the Studio words in either
language, the step of the plan that will produce it, and how to produce it. A page whose section is not measured
shows this row instead of "coming soon", and the share of rows still not measured is the plan's indicator F12, which
may only fall.

A row is never optimistic: a section counts as measured only when it was written and met its contract. A section
that is not exported yet says whether the facts it needs already exist in the report (so a Studio step will fill
it) or not (so an engine step must produce them first).
"""
from pathlib import Path

from .. import indicators

FUNCTION_SCOPES = ('function', 'method')
# Each section the Studio reads, in the order the rows are written, with the field its count reads.
PLANNED = {'meta': 'languages', 'head': None, 'health': 'domains', 'cards': 'cards', 'evidence': 'facts', 'story': 'gap',
           'docs': 'docs', 'plans': 'plans', 'decisions': 'decisions', 'media': 'images',
           'functions': 'functions', 'screens': 'screens', 'gaps': 'gaps', 'operations': 'operations', 'history': 'scans',
           'quality': 'detectors', 'maps': None}
V1_STEP = 'NS36.T2'


def _text(lang, ar, en):
    return ar if lang == 'ar' else en


def _count(value, src):
    return {'value': value if isinstance(value, int) and value >= 0 else None, 'src': src, 'unit': 'count'}


def _languages_with_functions(report):
    """{language: functions} from the function and method metrics the engines wrote."""
    from .export import LANGUAGES
    out = {}
    for row in indicators.facts(report, 'metric'):
        if (row.get('value') or {}).get('scope') not in FUNCTION_SCOPES: continue
        name = LANGUAGES.get(Path(str((row.get('location') or {}).get('path') or '')).suffix.lower())
        if name: out[name] = out.get(name, 0) + 1
    return out


def _languages(report):
    from .export import LANGUAGES
    names = set()
    for row in indicators.facts(report, 'graph_node'):
        name = LANGUAGES.get(Path(str((row.get('location') or {}).get('path') or '')).suffix.lower())
        if name: names.add(name)
    return names


def _not_exported(section, report, built, lang):
    """(reason, detail, step, tool, count, parts) for a section the exporter does not write yet."""
    if section == 'functions':
        found = _languages_with_functions(report)
        parts = [{'id': name, 'state': 'measured' if name in found else 'not_measured',
                  'detail': _text(lang, f'{found.get(name, 0)} دالة', f'{found.get(name, 0)} functions')}
                 for name in sorted(_languages(report) | set(found))]
        if found:
            return ('facts_not_exported', _text(lang, f'قرأ EAOS {sum(found.values())} دالة، ومستكشف الدوال لم يُصدَّر بعد.',
                                                f'EAOS read {sum(found.values())} functions; the function explorer is not exported yet.'),
                    'NS46.T5', 'audit', _count(sum(found.values()), 'facts/metrics.json#metric[scope in function, method]'), parts)
        return ('not_built', _text(lang, 'لا حقائق عن الدوال في هذا الفحص بعد.', 'This check has no function facts yet.'),
                'NS40.T3', 'audit', _count(None, 'facts/metrics.json#metric[scope in function, method]'), parts)
    if section == 'screens':
        shots = [image for image in built.get('media') or [] if image.get('kind') == 'screen']
        if shots:
            return ('facts_not_exported', _text(lang, f'{len(shots)} صورة شاشة موجودة، ومعرض الشاشات لم يُصدَّر بعد.',
                                                f'{len(shots)} screen shots exist; the screens gallery is not exported yet.'),
                    'NS46.T5', 'audit', _count(len(shots), 'media.json#images[kind=screen]'), [])
        return ('needs_screens', _text(lang, 'تصوير الشاشات يحتاج تشغيل التطبيق بموافقتك.', 'Capturing the screens needs the app running, with your agreement.'),
                'NS41.T1', 'run_setup', _count(None, 'media.json#images[kind=screen]'), [])
    if section in ('gaps', 'operations'):
        rows = (built.get('story') or {}).get('gap') or []
        if rows:
            return ('facts_not_exported', _text(lang, f'الفجوة محسوبة لـ{len(rows)} مكوّن، وصفحتها لم تُصدَّر بعد.',
                                                f'The gap is computed for {len(rows)} components; its page is not exported yet.'),
                    'NS46.T3', 'plan', _count(len(rows), 'story.json#gap'), [])
        return ('not_built', _text(lang, 'لم تُحسب الصورة المثالية والفجوة في هذا الفحص.', 'This check computed no ideal picture or gap.'),
                'NS43.T1' if section == 'gaps' else 'NS44.T1', 'plan', _count(None, 'story.json#gap'), [])
    if section == 'history':
        scans = (built.get('health') or {}).get('history') or []
        return ('facts_not_exported', _text(lang, f'{len(scans)} فحص مسجل، وصفحة التاريخ لم تُصدَّر بعد.',
                                            f'{len(scans)} scans recorded; the history page is not exported yet.'),
                'NS46.T4', 'audit', _count(len(scans), 'health.json#history'), [])
    if section == 'quality':
        return ('not_built', _text(lang, 'دقة كاشفات EAOS تُقاس على حالاتها المعلَّمة، ولم تُصدَّر لكل مشروع بعد.',
                                   "EAOS's detector precision is measured on its labelled cases and not exported per project yet."),
                'NS46.T4', None, _count(None, 'docs/engine-precision.json'), [])
    if section == 'maps':
        return ('not_built', _text(lang, 'خرائط النظام لم تُصدَّر في هذا الفحص.', 'The system maps are not exported in this check.'),
                'NS46.T6', 'audit', _count(None, 'maps.json'), [])
    return ('not_built', _text(lang, 'هذا القسم لم يُبنَ بعد.', 'This section is not built yet.'),
            V1_STEP, 'audit', _count(None, f'{section}.json'), [])


def coverage(report, built, written, errors, lang='ar'):
    """The coverage section's body: one row per planned section, and every other written section, in that order.

    built: {section: body as the exporter built it}; written: the sections that met their contract and were written;
    errors: [{section, error}] of the sections that did not."""
    report, failed = Path(report), {row['section']: row['error'] for row in errors}
    rows = []
    for section in [*PLANNED, *[name for name in written if name not in PLANNED and name != 'coverage']]:
        items = PLANNED.get(section)
        if section in written:
            body = built.get(section)
            listed = body.get(items) if isinstance(body, dict) and items else body if isinstance(body, list) else None
            count = len(listed) if isinstance(listed, list) else None
            empty = count == 0
            rows.append({'section': section, 'state': 'empty' if empty else 'measured',
                         'reason': 'nothing_found' if empty else 'written',
                         'detail': (_text(lang, 'قيس ولم يُوجد شيء.', 'Measured; nothing was found.') if empty else
                                    _text(lang, 'مقيس في هذا الفحص.', 'Measured in this check.')),
                         'step': None, 'tool': None, 'count': _count(count, f'{section}.json' + (f'#{items}' if items else '')), 'parts': []})
        elif section in failed:
            rows.append({'section': section, 'state': 'failed', 'reason': 'section_error', 'detail': failed[section][:300],
                         'step': V1_STEP, 'tool': 'audit', 'count': _count(None, 'errors.json'), 'parts': []})
        else:
            reason, detail, step, tool, count, parts = _not_exported(section, report, built, lang)
            rows.append({'section': section, 'state': 'not_measured', 'reason': reason, 'detail': detail, 'step': step,
                         'tool': tool, 'count': count, 'parts': parts})
    missing = sum(row['state'] in ('not_measured', 'failed') for row in rows)
    return {'sections': rows, 'not_measured': _count(missing, 'coverage.json#sections[state in not_measured, failed]')}
