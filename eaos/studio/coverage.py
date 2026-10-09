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
from .model import LANGUAGES

FUNCTION_SCOPES = ('function', 'method')
# Each section the Studio reads, in the order the rows are written, with the field its count reads.
PLANNED = {'meta': 'languages', 'head': None, 'health': 'domains', 'cards': 'cards', 'evidence': 'facts', 'story': 'gap',
           'docs': 'docs', 'plans': 'plans', 'decisions': 'decisions', 'media': 'images',
           'functions': 'functions', 'screens': 'screens', 'gaps': 'gaps', 'operations': 'operations', 'history': 'scans',
           'quality': 'detectors', 'maps': None, 'paths': 'paths', 'journeys': 'screens', 'hidden': 'items',
           'data_paths': 'stores', 'infra': None, 'pipeline': 'stages', 'ideal': None}
V1_STEP = 'NS36.T2'


def _text(lang, ar, en):
    return ar if lang == 'ar' else en


def _count(value, src):
    return {'value': value if isinstance(value, int) and value >= 0 else None, 'src': src, 'unit': 'count'}


def _languages_with_functions(report):
    """{language: functions} from the function and method metrics the engines wrote."""
    out = {}
    for row in indicators.facts(report, 'metric'):
        if (row.get('value') or {}).get('scope') not in FUNCTION_SCOPES: continue
        name = LANGUAGES.get(Path(str((row.get('location') or {}).get('path') or '')).suffix.lower())
        if name: out[name] = out.get(name, 0) + 1
    return out


def _languages(report):
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
    if section == 'paths':
        return ('not_built', _text(lang, 'مسارات الكود لم تُصدَّر في هذا الفحص.', 'The code paths are not exported in this check.'),
                'NS46.T6', 'audit', _count(None, 'paths.json#paths'), [])
    if section in ('journeys', 'hidden'):
        return ('not_built', _text(lang, 'خريطة الرحلات والظاهر والخفي لم تُصدَّر في هذا الفحص.',
                                   'The journeys and the visible and hidden maps are not exported in this check.'),
                'NS46.T6', 'audit', _count(None, f'{section}.json'), [])
    if section in ('data_paths', 'infra'):
        return ('not_built', _text(lang, 'خريطة البيانات أو البنية التحتية لم تُصدَّر في هذا الفحص.',
                                   'The data or infrastructure map is not exported in this check.'),
                'NS46.T6', 'audit', _count(None, f'{section}.json'), [])
    if section == 'pipeline':
        return ('not_built', _text(lang, 'هذا الفحص لم يكتب حقائق خط المعالجة (facts/pipeline.json): أعد الفحص بإصدار أحدث من EAOS.',
                                   'This check wrote no pipeline facts (facts/pipeline.json): check again with a newer EAOS.'),
                'NS46.T12', 'audit', _count(None, 'pipeline.json#stages'), [])
    if section == 'ideal':
        return ('not_built', _text(lang, 'المثالي لم يُصدَّر في هذا الفحص.', 'The ideal is not exported in this check.'),
                'NS46.T14', 'replan_ideal', _count(None, 'ideal.json#views'), [])
    if section == 'maps':
        return ('not_built', _text(lang, 'خرائط النظام لم تُصدَّر في هذا الفحص.', 'The system maps are not exported in this check.'),
                'NS46.T6', 'audit', _count(None, 'maps.json'), [])
    return ('not_built', _text(lang, 'هذا القسم لم يُبنَ بعد.', 'This section is not built yet.'),
            V1_STEP, 'audit', _count(None, f'{section}.json'), [])


def _paths_parts(body, lang):
    """The code paths' links measured, and each kind of gap they draw where the records stop: the gaps are counted here,
    not hidden."""
    counts = (body or {}).get('counts') or {}
    value = lambda key: (counts.get(key) or {}).get('value') or 0
    parts = [{'id': 'links', 'state': 'measured',
              'detail': _text(lang, f'{value("links")} رابطًا بدليله', f'{value("links")} links with their evidence')}]
    words = {'no_server_route': ('نداء بلا مسار خادم في الكود المقروء', 'calls with no server route in the code read'),
             'trace_stopped': ('مسار توقف تتبّعه عند نداء لم يُحلّ', 'paths whose trace stopped at a call it could not resolve'),
             'component_not_found': ('شاشة لم يُعرف ملف مكوّنها', 'screens whose component file is not known'),
             'handler_not_found': ('مدخل خادم بلا معالج يمكن تتبّعه', 'server entries with no traceable handler')}
    for key, (ar, en) in words.items():
        if value(key): parts.append({'id': key, 'state': 'not_measured', 'detail': _text(lang, f'{value(key)} {ar}', f'{value(key)} {en}')})
    return parts


def _pipeline_parts(body, lang):
    """What the pipeline map measured, and the steps it could not follow, counted rather than hidden."""
    counts = (body or {}).get('counts') or {}
    value = lambda key: (counts.get(key) or {}).get('value') or 0
    parts = [{'id': 'stages', 'state': 'measured', 'detail': _text(lang, f'{value("stages")} مرحلة و{value("edges")} رابطًا بدليلها',
                                                                  f'{value("stages")} stages and {value("edges")} edges with their evidence')}]
    if value('unresolved'):
        parts.append({'id': 'unresolved', 'state': 'not_measured',
                      'detail': _text(lang, f'{value("unresolved")} خطوة لم يستطع EAOS تتبّعها', f'{value("unresolved")} steps EAOS could not follow')})
    return parts


TIER_WORDS = {'field': ('حقل الإدخال', 'input field'), 'form': ('النموذج', 'form'), 'key': ('مفتاح الطلب', 'request key'),
              'caller': ('الوحدة المرسلة', 'calling module'), 'endpoint': ('نقطة الوصول', 'endpoint'),
              'handler': ('المعالج في الخادم', 'server handler'), 'column': ('العمود', 'column')}
LANE_WORDS = {'hosting': ('الاستضافة', 'hosting'), 'ci': ('البناء والنشر', 'CI/CD'), 'environments': ('البيئات', 'environments'),
              'databases': ('قواعد البيانات', 'databases'), 'queues': ('الطوابير', 'queues'),
              'services': ('الخدمات الخارجية', 'external services'), 'observability': ('المراقبة', 'observability')}


def _data_paths_parts(body, lang):
    """Each tier of the data paths: how many writes reach it with evidence, and why the others stop (the gaps the map
    draws are counted here)."""
    parts = []
    for tier in body.get('tiers') or []:
        ar, en = TIER_WORDS.get(tier['id'], (tier['id'], tier['id']))
        known, gaps = tier['known']['value'], sum(g['paths'] for g in tier.get('gaps') or [])
        detail = (_text(lang, f'{ar}: {known} معروف بدليله، {gaps} فجوة', f'{en}: {known} known with evidence, {gaps} gaps')
                  if known is not None else _text(lang, f'{ar}: لا كتابة في هذا المشروع', f'{en}: no write in this project'))
        parts.append({'id': tier['id'], 'state': tier['state'], 'detail': detail})
    return parts


def _infra_parts(body, lang):
    """Each lane of the infrastructure: found or measured empty today, and whether the target says anything about it."""
    target = {lane['id']: lane for lane in ((body.get('target') or {}).get('lanes') or [])}
    parts = []
    for lane in body.get('lanes') or []:
        ar, en = LANE_WORDS.get(lane['id'], (lane['id'], lane['id']))
        n = lane['count']['value']
        said = (target.get(lane['id']) or {}).get('state') == 'measured'
        parts.append({'id': lane['id'], 'state': lane['state'],
                      'detail': _text(lang, f'{ar}: {n} عنصر اليوم؛ ' + ('الهدف يحددها' if said else 'الهدف لم يقل عنها شيئًا بعد'),
                                      f'{en}: {n} today; ' + ('the target decides it' if said else 'the target says nothing about it yet'))})
    return parts


PARTS = {'paths': _paths_parts, 'data_paths': _data_paths_parts, 'infra': _infra_parts, 'pipeline': _pipeline_parts}
def _ideal_row(body, lang):
    """The ideal is measured when the person's assistant planned it for this check; the rules' target alone is partial,
    with each view's part saying how it was made (docs/STUDIO.md D10)."""
    views = (body or {}).get('views') or {}
    planned = [name for name, view in views.items() if (view.get('provenance') or {}).get('method') == 'planned']
    parts = [{'id': name, 'state': 'measured' if name in planned else 'partial',
              'detail': _text(lang, 'مخطَّط بنموذج' if name in planned else 'هدف القواعد فقط',
                              'planned with a model' if name in planned else "the rules' target only")} for name in views]
    count = _count(sum(len((v.get('planned') or {}).get('elements') or []) for v in views.values()) if planned else None,
                   'ideal.json#views[].planned.elements')
    if (body or {}).get('state') == 'planned':
        return {'count': count, 'parts': parts}
    return {'state': 'partial', 'reason': 'some_parts_missing', 'detail': ((body or {}).get('message') or {}).get(lang if lang == 'ar' else 'en')
            or _text(lang, 'المثالي هو هدف القواعد، وما خُطِّط بعد.', "The ideal is the rules' target; it is not planned yet."),
            'step': 'NS46.T14', 'tool': 'replan_ideal', 'count': count, 'parts': parts}


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
            # A written section may name the parts of its data the engine does not produce yet (`missing`): it is partial.
            gaps = [g for g in (body.get('missing') if isinstance(body, dict) and not empty else None) or []
                    if isinstance(g, dict) and g.get('state') in ('not_measured', 'partial', 'failed')]
            parts = PARTS[section](body, lang) if section in PARTS else \
                [{'id': g['id'], 'state': g['state'], 'detail': (g.get('detail') or {}).get(lang) or g['id']} for g in gaps]
            # A map whose own tiers stop short (no form extractor yet, a payload sent as a variable) is partial, not measured.
            tiers = section == 'data_paths' and any(part['state'] in ('partial', 'not_measured') for part in parts)
            rows.append({'section': section, 'state': 'empty' if empty else 'partial' if gaps or tiers else 'measured',
                         'reason': 'nothing_found' if empty else 'some_parts_missing' if gaps or tiers else 'written',
                         'detail': (_text(lang, 'قيس ولم يُوجد شيء.', 'Measured; nothing was found.') if empty else
                                    _text(lang, 'مقيس، وأجزاء منه لم تُقس بعد: ', 'Measured; parts are not measured yet: ')
                                    + _text(lang, '؛ ', '; ').join(p['detail'].rstrip('.') for p in parts) + '.' if gaps else
                                    _text(lang, 'قيس جزء من المسار؛ الفجوات معدودة في أجزائه.', 'Part of each path is measured; the gaps are counted in its parts.') if tiers else
                                    _text(lang, 'مقيس في هذا الفحص.', 'Measured in this check.')),
                         'step': gaps[0]['step'] if gaps else 'NS40.T2' if tiers else None, 'tool': 'audit' if tiers and not gaps else None,
                         'count': _count(count, f'{section}.json' + (f'#{items}' if items else '')), 'parts': parts})
            if section == 'ideal': rows[-1].update(_ideal_row(body, lang))
        elif section in failed:
            rows.append({'section': section, 'state': 'failed', 'reason': 'section_error', 'detail': failed[section][:300],
                         'step': V1_STEP, 'tool': 'audit', 'count': _count(None, 'errors.json'), 'parts': []})
        else:
            reason, detail, step, tool, count, parts = _not_exported(section, report, built, lang)
            rows.append({'section': section, 'state': 'not_measured', 'reason': reason, 'detail': detail, 'step': step,
                         'tool': tool, 'count': count, 'parts': parts})
    missing = sum(row['state'] in ('not_measured', 'failed') for row in rows)
    return {'sections': rows, 'not_measured': _count(missing, 'coverage.json#sections[state in not_measured, failed]')}
