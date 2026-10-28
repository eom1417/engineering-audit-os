"""The claims one source per pattern earns (M15), one per finding of eaos/analysis/assessments/one_source.py: a cluster
of near copies, a way of working written by hand three times or more, an element tree repeated across the screens, and
the look written outside its tokens file. Each card names every place and its central home by the project's own
layout; its acceptance is the detector finding none (its probe reads the code again). Near copies and the look are
CONFIRMED (the code shows them); an idiom or a UI pattern is LIKELY, and the judge (the card triage) reads it.
"""
from . import ledger
from ..assessments.one_source import findings

FORMS = {   # an idiom's form: (English, Arabic)
    'json_read': ('reading a JSON file or stored value', 'قراءة ملف JSON أو قيمة محفوظة'),
    'date_format': ('formatting a date or the time now', 'تنسيق التاريخ أو الوقت الحالي'),
    'money_format': ('formatting an amount of money', 'تنسيق المبالغ'),
    'request_state': ('a request with its loading and error state', 'طلب مع حالة التحميل والخطأ'),
    'popup_close': ('closing a pop-up on Escape', 'إغلاق النافذة المنبثقة بزر Escape'),
    'drag_drop': ('drag and drop', 'السحب والإفلات'),
    'validation': ('checking a field', 'التحقق من حقل'),
    'pagination': ('paging a list', 'تقسيم القائمة صفحات'),
    'route_guard': ("checking the sign-in inside a route", 'التحقق من الدخول داخل كل مسار'),
}
WORDS = {   # kind: (English, Arabic, fix in English, fix in Arabic); the finding's evidence fills them
    'near_copy': ("{copies} near copies of {lines} lines ({kinds}), the fullest at {place}:{line}",
                  "{copies} نسخ متقاربة من {lines} سطر ({kinds})، أكملها في {place}:{line}",
                  'Keep the fullest copy as the one source ({home}), make what differs a parameter, and call it from every other place.',
                  'خلّ أكمل نسخة هي المصدر الواحد ({home})، واللي يختلف خلّه معامل، ونادِها من كل الأماكن الثانية.'),
    'idiom': ("{form_en} is written by hand in {count} places ({ways} ways), from {place}:{line}",
              "{form_ar} مكتوب يدويًا في {count} أماكن (بـ {ways} طرق)، أولها {place}:{line}",
              'Write it once as a helper, hook or middleware in {home} and call it from every place.',
              'اكتبها مرة وحدة كدالة مساعدة أو hook أو middleware في {home} ونادِها من كل مكان.'),
    'ui_pattern': ("The same <{tag}> structure of {elements} elements is written in {count} places ({similarity} alike), from {place}:{line}",
                   "نفس بنية <{tag}> من {elements} عناصر مكتوبة في {count} أماكن (متشابهة {similarity})، أولها {place}:{line}",
                   'Make it one component in {home} and use it in every place; what differs becomes its props.',
                   'سوّها مكوّن واحد في {home} واستخدمه في كل مكان؛ واللي يختلف يصير خصائص له.'),
    'look': ("{written} values of the look are written outside the tokens file ({by_kind}){seen_en}",
             "{written} قيمة للشكل مكتوبة خارج ملف الـ tokens ({by_kind}){seen_ar}",
             'Keep every colour, font size, spacing, radius, shadow and z-index in one tokens file ({home}) and use only its names.',
             'خلّ كل لون وحجم خط ومسافة وانحناء وظل وترتيب طبقات في ملف tokens واحد ({home})، واستخدم أسماءه بس.'),
}


def _seen(evidence, lang):
    """What the pictured pages showed, said where it drifts: '37 colours where 30 do'."""
    parts = []
    for kind in evidence.get('drifts') or []:
        row = evidence['seen'][kind]
        name = kind.replace('_', ' ')
        parts.append(f"{row['values']} {name} values where {row['would_do']} do" if lang == 'en' else
                     f"{row['values']} قيمة ({name}) وتكفي {row['would_do']}")
    if not parts: return ''
    return ('; the pages show ' if lang == 'en' else '؛ والصفحات تعرض ') + ', '.join(parts)


def _values(finding):
    evidence = finding['evidence']
    home = evidence.get('home')
    values = {'place': finding['place'], 'line': finding['line'] or 1, **evidence,
              'home': ', '.join(home) if isinstance(home, list) else home or 'tokens.json',
              'kinds': ', '.join(evidence.get('kinds') or []), 'seen_en': _seen(evidence, 'en'), 'seen_ar': _seen(evidence, 'ar'),
              'by_kind': ', '.join(f'{k} {v}' for k, v in (evidence.get('by_kind') or {}).items())}
    if finding['kind'] == 'idiom': values['form_en'], values['form_ar'] = FORMS.get(evidence['form'], (evidence['form'],) * 2)
    if isinstance(values.get('similarity'), float): values['similarity'] = f"{round(values['similarity'] * 100)}%"
    return values


def params(finding):
    values = _values(finding)
    en, ar, fix_en, fix_ar = (text.format(**values) for text in WORDS[finding['kind']])
    return {'kind': finding['kind'] if finding['kind'] != 'idiom' else f"idiom:{finding['evidence']['form']}", 'severity': finding['severity'],
            'en': en, 'ar': ar, 'fix_en': fix_en, 'fix_ar': fix_ar, 'place': finding['place'], 'line': finding['line'],
            'home': values['home'], 'places': [f"{p['path']}:{p.get('line') or 1}" for p in finding['evidence'].get('places') or []][:40],
            'category': 'maintainability'}


def _probe(finding):
    """The probe that reads the code again: CONFIRMED while the detector still finds this pattern."""
    engines = {'near_copy': ['jscpd'], 'idiom': ['ast-grep']}.get(finding['kind'], [])
    key = finding['evidence'].get('form') or finding['evidence'].get('tag') or ''
    return {'probe_type': 'graph_query', 'specification': {'query': 'one_source_present', 'kind': finding['kind'], 'key': key,
                                                           'places': sorted({p['path'] for p in finding['evidence'].get('places') or []})[:40],
                                                           'engines': engines, 'expected': 'The detector still finds this pattern.'}}


def one_source_claims(out, sets, target, offset):
    """Every claim of M15, numbered after `offset`."""
    found, _ = findings(out, sets, target)
    rows = []
    for finding in found:
        confidence = 'CONFIRMED' if finding['kind'] in ('near_copy', 'look') else 'LIKELY'
        rendered = params(finding)
        facts = finding['evidence'].get('fact_ids') or ([finding['evidence']['fact_id']] if finding['evidence'].get('fact_id') else None)
        rows.append(ledger.make(offset + len(rows) + 1, rendered['en'], 'structure', confidence, ['static_fact'],
                                [] if facts else [finding['place']], 'The detector of this pattern finding none in the code.',
                                fact_ids=facts, confidence_ceiling=confidence, render={'key': 'one_source', 'params': rendered},
                                probe_spec=_probe(finding), impact={'scenario': rendered['fix_en']}))
    return rows


def _same(finding, specification):
    """Whether a finding is the card's pattern: its kind, its form or tag, and one of its places."""
    places = set(specification.get('places') or [])
    key = finding['evidence'].get('form') or finding['evidence'].get('tag') or ''
    return (finding['kind'] == specification['kind'] and key == specification.get('key')
            and (not places or bool(places & {p['path'] for p in finding['evidence'].get('places') or []})))


def present(specification, sets):
    """The probe of a card: CONFIRMED while a finding of its kind (and form or tag) still touches one of its places."""
    found, _ = findings(None, sets)
    if any(_same(finding, specification) for finding in found):
        return 'CONFIRMED', f"the {specification['kind'].replace('_', ' ')} is still there"
    return 'REFUTED', f"no {specification['kind'].replace('_', ' ')} left at its places"
