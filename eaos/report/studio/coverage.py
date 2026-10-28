"""studio/coverage.json: what EAOS measured for this report and what it has not measured yet (contract v2).

Every section the Studio reads gets one row: its state, the reason as a stable code the Studio words in either
language, the step of the plan that will produce it, and how to produce it. A page whose section is not measured
shows this row instead of "coming soon", and the share of rows still not measured is the plan's indicator F12, which
may only fall.

A row is never optimistic: a section counts as measured only when it was written and met its contract. A section
that is not exported yet says whether the facts it needs already exist in the report (so a Studio step will fill
it) or not (so an engine step must produce them first).
"""
from pathlib import Path

from ...facts.store import facts as facts_of
from ...analysis.presentation.model import language_counts
from ...analysis.presentation.counts import measured

FUNCTION_SCOPES = ('function', 'method')
# Each section the Studio reads, in the order the rows are written, with the field its count reads.
PLANNED = {'meta': 'languages', 'head': None, 'health': 'domains', 'cards': 'cards', 'evidence': 'facts', 'story': 'gap',
           'docs': 'docs', 'plans': 'plans', 'decisions': 'decisions', 'media': 'images',
           'functions': 'functions', 'screens': 'screens', 'gaps': 'gaps', 'operations': 'operations', 'history': 'scans',
           'maps': None, 'paths': 'paths', 'journeys': 'screens', 'hidden': 'items',
           'data_paths': 'stores', 'infra': None, 'pipeline': 'stages', 'ideal': None, 'nodes': 'nodes'}
V1_STEP = 'NS36.T2'


def _text(lang, ar, en):
    return ar if lang == 'ar' else en


def _languages_with_functions(report):
    """{language: functions} from the function and method metrics the engines wrote."""
    return language_counts(row for row in facts_of(report, 'metric') if (row.get('value') or {}).get('scope') in FUNCTION_SCOPES)


def _languages(report):
    return set(language_counts(facts_of(report, 'graph_node')))


def _functions_not_exported(section, report, built, lang):
    found = _languages_with_functions(report)
    parts = [{'id': name, 'state': 'measured' if name in found else 'not_measured',
              'detail': _text(lang, f'{found.get(name, 0)} دالة', f'{found.get(name, 0)} functions')}
             for name in sorted(_languages(report) | set(found))]
    if found:
        return ('facts_not_exported', _text(lang, f'قرأ EAOS {sum(found.values())} دالة، ومستكشف الدوال لم يُصدَّر بعد.',
                                            f'EAOS read {sum(found.values())} functions; the function explorer is not exported yet.'),
                'NS46.T5', 'audit', measured(sum(found.values()), 'facts/metrics.json#metric[scope in function, method]'), parts)
    return ('not_built', _text(lang, 'لا حقائق عن الدوال في هذا الفحص بعد.', 'This check has no function facts yet.'),
            'NS40.T3', 'audit', measured(None, 'facts/metrics.json#metric[scope in function, method]'), parts)


def _screens_not_exported(section, report, built, lang):
    shots = [image for image in built.get('media') or [] if image.get('kind') == 'screen']
    if shots:
        return ('facts_not_exported', _text(lang, f'{len(shots)} صورة شاشة موجودة، ومعرض الشاشات لم يُصدَّر بعد.',
                                            f'{len(shots)} screen shots exist; the screens gallery is not exported yet.'),
                'NS46.T5', 'audit', measured(len(shots), 'media.json#images[kind=screen]'), [])
    return ('needs_screens', _text(lang, 'تصوير الشاشات يحتاج تشغيل التطبيق بموافقتك.', 'Capturing the screens needs the app running, with your agreement.'),
            'NS41.T1', 'run_setup', measured(None, 'media.json#images[kind=screen]'), [])


def _gap_not_exported(section, report, built, lang):
    rows = (built.get('story') or {}).get('gap') or []
    if rows:
        return ('facts_not_exported', _text(lang, f'الفجوة محسوبة لـ{len(rows)} مكوّن، وصفحتها لم تُصدَّر بعد.',
                                            f'The gap is computed for {len(rows)} components; its page is not exported yet.'),
                'NS46.T3', 'plan', measured(len(rows), 'story.json#gap'), [])
    return ('not_built', _text(lang, 'لم تُحسب الصورة المثالية والفجوة في هذا الفحص.', 'This check computed no ideal picture or gap.'),
            'NS43.T1' if section == 'gaps' else 'NS44.T1', 'plan', measured(None, 'story.json#gap'), [])


def _history_not_exported(section, report, built, lang):
    scans = (built.get('health') or {}).get('history') or []
    return ('facts_not_exported', _text(lang, f'{len(scans)} فحص مسجل، وصفحة التاريخ لم تُصدَّر بعد.',
                                        f'{len(scans)} scans recorded; the history page is not exported yet.'),
            'NS46.T4', 'audit', measured(len(scans), 'health.json#history'), [])


# The sections whose facts can be counted before their page is exported.
NOT_EXPORTED = {'functions': _functions_not_exported, 'screens': _screens_not_exported, 'gaps': _gap_not_exported,
                'operations': _gap_not_exported, 'history': _history_not_exported}


def _not_exported(section, report, built, lang):
    """(reason, detail, step, tool, count, parts) for a section the exporter does not write yet."""
    if section in NOT_EXPORTED: return NOT_EXPORTED[section](section, report, built, lang)
    if section == 'paths':
        return ('not_built', _text(lang, 'مسارات الكود لم تُصدَّر في هذا الفحص.', 'The code paths are not exported in this check.'),
                'NS46.T6', 'audit', measured(None, 'paths.json#paths'), [])
    if section in ('journeys', 'hidden'):
        return ('not_built', _text(lang, 'خريطة الرحلات والظاهر والخفي لم تُصدَّر في هذا الفحص.',
                                   'The journeys and the visible and hidden maps are not exported in this check.'),
                'NS46.T6', 'audit', measured(None, f'{section}.json'), [])
    if section in ('data_paths', 'infra'):
        return ('not_built', _text(lang, 'خريطة البيانات أو البنية التحتية لم تُصدَّر في هذا الفحص.',
                                   'The data or infrastructure map is not exported in this check.'),
                'NS46.T6', 'audit', measured(None, f'{section}.json'), [])
    if section == 'pipeline':
        return ('not_built', _text(lang, 'هذا الفحص لم يكتب حقائق خط المعالجة (facts/pipeline.json): أعد الفحص بإصدار أحدث من EAOS.',
                                   'This check wrote no pipeline facts (facts/pipeline.json): check again with a newer EAOS.'),
                'NS46.T12', 'audit', measured(None, 'pipeline.json#stages'), [])
    if section == 'ideal':
        return ('not_built', _text(lang, 'المثالي لم يُصدَّر في هذا الفحص.', 'The ideal is not exported in this check.'),
                'NS46.T14', 'replan_ideal', measured(None, 'ideal.json#views'), [])
    if section == 'nodes':
        return ('not_built', _text(lang, 'عُقد الذكاء لم تُصدَّر في هذا الفحص.', 'The AI nodes are not exported in this check.'),
                'NS46.T15', 'run_nodes', measured(None, 'nodes.json#nodes'), [])
    if section == 'maps':
        return ('not_built', _text(lang, 'خرائط النظام لم تُصدَّر في هذا الفحص.', 'The system maps are not exported in this check.'),
                'NS46.T6', 'audit', measured(None, 'maps.json'), [])
    return ('not_built', _text(lang, 'هذا القسم لم يُبنَ بعد.', 'This section is not built yet.'),
            V1_STEP, 'audit', measured(None, f'{section}.json'), [])


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


def _functions_parts(body, lang):
    """Each language of the project: its functions measured with their calls, measured without calls (Lizard only), or not
    measured, so a language with no function facts is named here rather than left out of an empty list."""
    words = {'measured': ('دالة بعلاقات استدعائها', 'functions with their calls'), 'partial': ('دالة بلا تتبع للاستدعاءات', 'functions, calls not traced'),
             'not_measured': ('لا حقائق دوال بعد', 'no function facts yet')}
    parts = []
    for row in body.get('languages') or []:
        ar, en = words[row['state']] if row['state'] in words else (row['state'], row['state'])
        n = row['functions']['value']
        parts.append({'id': row['id'], 'state': row['state'],
                      'detail': _text(lang, f"{row['id']}: " + (f'{n} {ar}' if n is not None else ar), f"{row['id']}: " + (f'{n} {en}' if n is not None else en))})
    return parts


PARTS = {'functions': _functions_parts, 'paths': _paths_parts, 'data_paths': _data_paths_parts, 'infra': _infra_parts, 'pipeline': _pipeline_parts}


def _nodes_row(body, lang):
    """The AI nodes are measured when at least one ran for this check; each node's part says how it was decided:
    by the person's assistant, by the rules alone, or not yet."""
    nodes = (body or {}).get('nodes') or []
    words = {'model': ('قرّره المساعد', "decided by the person's assistant"), 'rules': ('قُرِّر بالقواعد فقط', 'decided by the rules only'),
             None: ('لم يعمل بعد', 'not run yet')}
    parts = [{'id': n['id'], 'state': 'measured' if n['method'] == 'model' else 'partial' if n['method'] == 'rules' else 'not_measured',
              'detail': _text(lang, *words.get(n['method'], words[None]))} for n in nodes]
    if any(n['state'] != 'not_run' for n in nodes): return {'parts': parts}
    return {'state': 'partial', 'reason': 'some_parts_missing', 'parts': parts, 'step': 'NS46.T15', 'tool': 'run_nodes',
            'detail': _text(lang, 'عُقد الذكاء لم تعمل على هذا الفحص بعد: شغّلها من مركز التحكم.',
                            'The AI nodes have not run on this check yet: run them from the command centre.')}


def _ideal_row(body, lang):
    """The ideal is measured when the person's assistant planned it for this check; the rules' target alone is partial,
    with each view's part saying how it was made."""
    views = (body or {}).get('views') or {}
    planned = [name for name, view in views.items() if (view.get('provenance') or {}).get('method') == 'planned']
    parts = _view_parts(views, planned, lang)
    count = measured(_planned_elements(views) if planned else None, 'ideal.json#views[].planned.elements')
    if (body or {}).get('state') == 'planned':
        return {'count': count, 'parts': parts}
    return _rules_ideal(body, lang, count, parts)


def _planned_elements(views):
    """How many elements the person's assistant planned over every view of the ideal."""
    return sum(len((v.get('planned') or {}).get('elements') or []) for v in views.values())


def _view_parts(views, planned, lang):
    """Each view of the ideal: planned with a model, or the rules' target only."""
    return [{'id': name, 'state': 'measured' if name in planned else 'partial',
              'detail': _text(lang, 'مخطَّط بنموذج' if name in planned else 'هدف القواعد فقط',
                              'planned with a model' if name in planned else "the rules' target only")} for name in views]


def _rules_ideal(body, lang, count, parts):
    """The row of an ideal that is the rules' target only: partial, and how to plan it."""
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
        if section in written: rows.append(_written_row(section, built.get(section), lang))
        elif section in failed: rows.append(_failed_row(section, failed[section]))
        else: rows.append(_not_measured_row(section, report, built, lang))
    missing = sum(row['state'] in ('not_measured', 'failed') for row in rows)
    return {'sections': rows, 'not_measured': measured(missing, 'coverage.json#sections[state in not_measured, failed]')}


def _gaps(body, empty):
    """The parts a written section names as not produced yet (`missing`): such a section is partial."""
    return [g for g in (body.get('missing') if isinstance(body, dict) and not empty else None) or []
            if isinstance(g, dict) and g.get('state') in ('not_measured', 'partial', 'failed')]


def _listed_count(body, items):
    """How many items the section lists (its body, or its `items` field); None when it lists none."""
    listed = body.get(items) if isinstance(body, dict) and items else body if isinstance(body, list) else None
    return len(listed) if isinstance(listed, list) else None


def _parts_of(section, body, gaps, lang):
    if section in PARTS: return PARTS[section](body, lang)
    return [{'id': g['id'], 'state': g['state'], 'detail': (g.get('detail') or {}).get(lang) or g['id']} for g in gaps]


def _standing(empty, gaps, tiers):
    """{state, reason, step, tool} of a written section: empty, partial (and the step that would complete it), or measured."""
    if empty: return {'state': 'empty', 'reason': 'nothing_found', 'step': gaps[0]['step'] if gaps else 'NS40.T2' if tiers else None,
                      'tool': 'audit' if tiers and not gaps else None}
    if gaps: return {'state': 'partial', 'reason': 'some_parts_missing', 'step': gaps[0]['step'], 'tool': None}
    if tiers: return {'state': 'partial', 'reason': 'some_parts_missing', 'step': 'NS40.T2', 'tool': 'audit'}
    return {'state': 'measured', 'reason': 'written', 'step': None, 'tool': None}


def _written_row(section, body, lang):
    """A section that met its contract: measured, empty, or partial when parts of it are not measured yet."""
    items = PLANNED.get(section)
    count = _listed_count(body, items)
    empty = count == 0
    gaps = _gaps(body, empty)
    parts = _parts_of(section, body, gaps, lang)
    # A map whose own tiers stop short (no form extractor yet, a payload sent as a variable) is partial, not measured.
    tiers = section == 'data_paths' and any(part['state'] in ('partial', 'not_measured') for part in parts)
    row = {'section': section, **_standing(empty, gaps, tiers), 'detail': _written_detail(lang, empty, gaps, tiers, parts),
           'count': measured(count, f'{section}.json' + (f'#{items}' if items else '')), 'parts': parts}
    if section == 'ideal': row.update(_ideal_row(body, lang))
    if section == 'nodes': row.update(_nodes_row(body, lang))
    return row


def _failed_row(section, error):
    return {'section': section, 'state': 'failed', 'reason': 'section_error', 'detail': error[:300],
            'step': V1_STEP, 'tool': 'audit', 'count': measured(None, 'errors.json'), 'parts': []}


def _not_measured_row(section, report, built, lang):
    reason, detail, step, tool, count, parts = _not_exported(section, report, built, lang)
    return {'section': section, 'state': 'not_measured', 'reason': reason, 'detail': detail, 'step': step,
            'tool': tool, 'count': count, 'parts': parts}


def _written_detail(lang, empty, gaps, tiers, parts):
    return (_text(lang, 'قيس ولم يُوجد شيء.', 'Measured; nothing was found.') if empty else
            _text(lang, 'مقيس، وأجزاء منه لم تُقس بعد: ', 'Measured; parts are not measured yet: ')
            + _text(lang, '؛ ', '; ').join(p['detail'].rstrip('.') for p in parts) + '.' if gaps else
            _text(lang, 'قيس جزء من المسار؛ الفجوات معدودة في أجزائه.', 'Part of each path is measured; the gaps are counted in its parts.') if tiers else
            _text(lang, 'مقيس في هذا الفحص.', 'Measured in this check.'))
