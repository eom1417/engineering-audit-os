"""The reports a client reads first: where the project is, and the plan.

  CURRENT-STATE.md      what the program is today: features, data, measured risk, the C4 view, every aspect's verdict
  EXECUTION-PLAN.md     milestones, sections and the first cards a team starts with

Each follows docs/MASTER-BLUEPRINT.md §6: a one-page summary (the decision asked for, the three numbers that
matter, the three largest risks), then evidence, inference, impact and recommendation, then what was not
examined, then links to the reference documents. Every number names where it comes from: a record, an item
id or a claim id. They repeat nothing the appendices hold; they link to them.
"""
from pathlib import Path

from .markdown import Page, clip
from ...core.system.files import read_json
from ...analysis.claims.ledger import withheld_said

NAMES = ('CURRENT-STATE.md', 'EXECUTION-PLAN.md')


def _read(out, name, key, empty):
    """The `key` of the report's record `name`; `empty` when the record or the key is missing."""
    return (read_json(Path(out) / name, {}) or {}).get(key) or empty


def _labels(ar):
    return (dict(summary='الخلاصة', decision='القرار المطلوب', numbers='أهم الأرقام', risks='أكبر المخاطر',
                 evidence='الدليل والاستنتاج', impact='الأثر', recommendation='التوصية', unexamined='ما لم يُفحص',
                 appendices='الملاحق', source='المصدر') if ar else
            dict(summary='Summary', decision='Decision asked for', numbers='The numbers that matter',
                 risks='The largest risks', evidence='Evidence and inference', impact='Impact',
                 recommendation='Recommendation', unexamined='Not examined', appendices='Appendices', source='source'))


def _risks(register, n=3):
    return [f"{item['id']} ({item['severity']}, {item['category']}): {clip(item['title'], 110)}"
            for item in (register or {}).get('items', [])[:n]]


VERDICT_WORDS = {'keep': ('keep: already right, nothing changes', 'يبقى: صحيح كما هو، لا تغيير'),
                 'improve': ('improve', 'يتحسّن'),
                 'unmeasured': ('not measured in this check', 'لم يُقَس في هذا الفحص')}


def aspect_section(page, out, ar):
    """One line per aspect: its verdict, why, and for one to improve its plan and cards; who decided."""
    from ...analysis.understanding.aspects import final
    rows = final(out)
    page.heading('كل جانب من البرنامج: يبقى أو يتحسّن' if ar else 'Every aspect of the program: keep or improve')
    page.para('حكم القواعد على كل جانب، من سجلات الفحص (eaos/analysis/understanding/aspects.py).' if ar else
              "The rules' verdict on each aspect, from the check's records (eaos/analysis/understanding/aspects.py).")
    page.items([_aspect_line(row, ar) for row in rows])


def _aspect_line(row, ar):
    """An aspect, its verdict and why, its plan and cards when it is to improve, and who decided."""
    label = row['label'][1 if ar else 0] if isinstance(row.get('label'),
                                                       (list, tuple)) else row.get('label') or row['aspect']
    words = VERDICT_WORDS.get(row['verdict'], (row['verdict'], row['verdict']))[1 if ar else 0]
    line = f"{label}: {words}. {clip(row.get('why'), 220)}"
    if row['verdict'] == 'improve' and row.get('plan'):
        line += (' الخطة: ' if ar else ' Plan: ') + clip(row['plan'], 220)
    if row.get('cards'): line += ' (' + ', '.join(row['cards'][:4]) + ')'
    return line + f" ({_who(row, ar)})"


def _who(row, ar):
    """Who judged an aspect: the person's assistant, or the rules."""
    return ('مساعدك' if ar else 'your assistant') if row.get('decided_by') == 'assistant' else ('القواعد' if ar
        else 'the rules')


def _diagram(page, out, which, ar):
    """The C4 diagram of `which` (current) as a mermaid block, when it was drawn."""
    diagram = Path(out) / f'architecture/{which}/diagram.mmd'
    if diagram.is_file():
        page.heading('C4' if not ar else 'خريطة C4', 3)
        page.block('mermaid', diagram.read_text(encoding='utf-8'))


def _current_numbers(coverage, features, items, severe, external):
    return {
        'files_parsed': (f"{coverage.get('files_parsed')}/{coverage.get('source_files')}", 'dossier.json → coverage'),
        'features': (len(features), 'features.json'),
        'critical_features': (sum(1 for f in features if f.get('critical')), 'features.json → critical'),
        'debt_items': (len(items), 'debt-register.json'),
        'high_or_critical': (len(severe), 'debt-register.json → severity'),
        'engines': (len(external.get('engines_observed') or []), 'facts/external.json → engines_observed'),
    }


def _baseline_decision(severe, ar):
    if severe:
        return (f"قبول هذا الوصف أساسًا للتحول، ومعالجة البنود العالية الخطورة ({len(severe)}) أولًا." if ar else
                f"accept this description as the baseline, and treat the {len(severe)} high or critical items first.")
    return ('قبول هذا الوصف أساسًا للتحول؛ لا بند عالي الخطورة بشاهد كافٍ، فالبداية بمعلم التثبيت.' if ar else
            'accept this description as the baseline; no high item has enough witnesses, so start with the '
            'stabilize milestone.')


def _feature_items(features, ar):
    return ([clip(f"{f['name']}: {f.get('description', '')}", 160) for f in features[:12]]






























            + ([f"… {len(features) - 12} " + ('أخرى في features.json' if ar else 'more in features.json')]
               if len(features) > 12 else []))


def _unexamined(page, out, coverage, external, ar):
    alike = [row['ar' if ar else 'en'] for row in _read(out, 'dossier.json', 'likenesses', [])[:10]]   # said, no card
    if alike:
        page.para('متشابهات في الشكل بس، ما صارت بطاقات (ما استوفت الشروط الثلاثة):' if ar
                  else 'Alike in shape only, not cards (they miss one of the three conditions):')
        page.items(alike)
    page.heading(_labels(ar)['unexamined'])
    page.items(list(coverage.get('not_examined') or [])[:8]
               + withheld_said(_read(out, 'dossier.json', 'withheld_claims', []), ar)






























               + [('محرك غير مثبت: ' if ar else 'engine not installed: ') + name
               for name in external.get('engines_unavailable') or []])


def _current_number_items(numbers, ar):
    """The summary's three numbers, each with the record it comes from."""
    return [f"{numbers['files_parsed'][0]} " + ('ملفًا محللًا' if ar else 'files analysed')
            + f" ({numbers['files_parsed'][1]})",
            f"{numbers['features'][0]} " + ('وظيفة، منها' if ar else 'features, of which')
            + f" {numbers['critical_features'][0]} "
            + ('حرجة' if ar else 'critical') + f" ({numbers['features'][1]})",
            f"{numbers['debt_items'][0]} " + ('بند دَين، منها' if ar else 'debt items, of which')
            + f" {numbers['high_or_critical'][0]} "
            + ('عالية أو حرجة' if ar else 'high or critical') + f" ({numbers['debt_items'][1]})"]


def _current_evidence(page, features, items, measured, ar):
    """What the program does today, its debt by category, and its most complex, most changed files."""
    page.para(('الوظائف التي يقدمها البرنامج اليوم، بأسطحها والبيانات التي تمسها:' if ar else
               'What the program does today, by its surfaces and the data each feature touches:'))
    page.items(_feature_items(features, ar))
    by_category = {}
    for item in items: by_category[item['category']] = by_category.get(item['category'], 0) + 1
    page.para(('الدَّين حسب الفئة (debt-register.json): ' if ar else 'Debt by category (debt-register.json): ')
              + ', '.join(f'{k} {v}' for k, v in sorted(by_category.items(), key=lambda kv: -kv[1])))
    hottest = sorted(measured, key=lambda r: (-(r.get('complexity_max') or 0), -(r.get('churn') or 0)))[:5]
    if hottest:
        page.para(('أعقد الملفات وأكثرها تغيّرًا (measurements.json):' if ar
                   else 'The most complex, most changed files (measurements.json):'))
        page.items([f"{r['path']}: complexity {r.get('complexity_max')}, "
                    f"commits {r.get('churn')}, fan-in {r.get('fan_in')}" for r in hottest])


def current_state(out, ar):
    L = _labels(ar)
    coverage, features = _read(out, 'dossier.json', 'coverage', {}), _read(out, 'features.json', 'features', [])
    register = read_json(Path(out) / 'debt-register.json', {}) or {}
    items = register.get('items') or []
    severe = [i for i in items if i['severity'] in ('high', 'critical')]
    external, measured = _read(out, 'facts/external.json', 'summary', {}), _read(out, 'measurements.json', 'files', [])
    numbers = _current_numbers(coverage, features, items, severe, external)
    page = Page('الوضع الراهن' if ar else 'Current state')
    page.heading(L['summary'])
    page.para(f"{L['decision']}: " + _baseline_decision(severe, ar))
    page.heading(L['numbers'], 3)
    page.items(_current_number_items(numbers, ar))
    page.heading(L['risks'], 3)
    page.items(_risks(register) or ['—'])
    page.heading(L['evidence'])
    _current_evidence(page, features, items, measured, ar)
    _diagram(page, out, 'current', ar)
    aspect_section(page, out, ar)
    page.heading(L['impact'])
    page.para(('كل بند عالي الخطورة في السجل له شاهد حتمي أو أداتان؛ تركه يعني أن الخطر المعروف يبقى في كل إصدار.' if ar
               else
               'Every high item in the register has a deterministic witness or two tools; leaving one means a known '
               'risk ships in every release.'))
    page.heading(L['recommendation'])
    page.para(('ابدأ بمعلم التثبيت في EXECUTION-PLAN.md.' if ar
               else 'Start with the stabilize milestone in EXECUTION-PLAN.md.'))
    _unexamined(page, out, coverage, external, ar)
    page.heading(L['appendices'])
    page.items(['`features.json`', '`measurements.json`', '`debt-register.json`', '`load-model.json`',
                '`facts/external.json`'])
    return page.text()


def execution_plan(out, ar):
    L = _labels(ar)
    plan = read_json(Path(out) / 'plan.json', {}) or {}
    tasks = plan.get('tasks') or []
    numbers = _plan_numbers(plan, tasks, read_json(Path(out) / 'cards.json', {}) or {})
    page = Page('خطة التنفيذ' if ar else 'Execution plan')
    page.heading(L['summary'])
    page.para(f"{L['decision']}: "
              + (f"تخصيص فريق للمعلم الأول ({(plan.get('milestones') or [{}])[0].get('name', '—')})." if ar else
                 f"staff the first milestone ({(plan.get('milestones') or [{}])[0].get('name', '—')})."))
    _numbers_section(page, L, tasks, numbers, ar)
    _plan_sections(page, L, plan, tasks, ar)
    return page.text()


def _numbers_section(page, L, tasks, numbers, ar):
    """The plan's numbers: its cards, the ready ones, their sizes, the cards left out or added, and who ordered them."""
    ready, sizes = numbers['ready'][0], numbers['sizes'][0]
    page.heading(L['numbers'], 3)
    page.items([f"{len(tasks)} " + ('بطاقة' if ar else 'cards') + f" ({numbers['cards'][1]})",
                f"{ready} " + ('جاهزة بأمر قبول يقرر' if ar else 'ready, with an acceptance command that decides')
                + f" ({numbers['ready'][1]})",
                ', '.join(f'{k} {v}' for k, v in sorted((k or '?', v) for k, v in sizes.items()))
                + f" ({numbers['sizes'][1]})",
                (f"{numbers['set_aside'][0]} بطاقة رفضها مساعدك فخرجت من الخطة، و{numbers['design'][0]} بطاقة تصميم "
                 f"من صور الشاشات" if ar else
                 f"{numbers['set_aside'][0]} cards your assistant rejected left the plan; "
                 f"{numbers['design'][0]} design cards came from the screens")
                + f" ({numbers['set_aside'][1]}, {numbers['design'][1]})",
                _order_line(numbers['order'][0] == 'assistant', ar) + f" ({numbers['order'][1]}, PLAN/STEPS.md)"])


def _plan_sections(page, L, plan, tasks, ar):
    """The risks, the milestones and sections, the recommendation, what was not examined, and the appendices."""
    by_id = {t['id']: t for t in tasks}
    page.heading(L['risks'], 3)
    page.items([_investigations(tasks, ar)])
    page.heading(('المعالم' if ar else 'Milestones'))
    for milestone in plan.get('milestones') or []: _milestone_section(page, milestone, by_id, ar)
    page.heading(('الأقسام' if ar else 'Sections'))
    page.items([_section_line(s, ar) for s in plan.get('sections') or []])
    page.heading(L['recommendation'])
    page.para(('نفّذ كل بطاقة في نسخة معزولة، وشغّل أمر قبولها، ثم أعد التدقيق؛ التراجع لكل بطاقة مكتوب فيها.' if ar
               else
               'Run each card in an isolated copy, run its acceptance command, then audit again; each card states '
               'its rollback.'))
    page.heading(L['unexamined'])
    page.items([('لم تُشغَّل أي بطاقة على كود المشروع بعد؛ التنفيذ يحتاج تفويض المالك (authorization.json).' if ar else
                 'No card has run against the project yet; execution needs the owner\'s authorization.json.')])
    page.heading(L['appendices'])
    page.items(['[PLAN/STEPS.md](PLAN/STEPS.md)', '[PLAN/WAVES.md](PLAN/WAVES.md)'])


def _investigations(tasks, ar):
    """How many investigation cards wait for a recorded decision."""
    investigations = [t for t in tasks if t.get('kind') == 'investigate']
    return (f"{len(investigations)} بطاقة تحقيق تنتظر قرارًا مسجلًا (eaos decision-review)." if ar else
            f"{len(investigations)} investigation cards wait for a recorded decision (eaos decision-review).")


def _section_line(s, ar):
    """One section of the plan: its cards, and the sections it waits for."""
    waits = f", {'تنتظر' if ar else 'waits for'} {', '.join(s['depends_on'])}" if s['depends_on'] else ''
    return f"{s['section']}: {len(s['tasks'])} " + ('بطاقة' if ar else 'cards') + waits


def _plan_numbers(plan, tasks, cards):
    sizes = {}
    for t in tasks: sizes[t.get('effort')] = sizes.get(t.get('effort'), 0) + 1
    return {
        'cards': (len(tasks), 'plan.json → tasks'),
        'set_aside': (len(cards.get('set_aside') or []), 'cards.json → set_aside'),
        'design': (len(cards.get('design') or []), 'cards.json → design'),
        'order': ((plan.get('order') or {}).get('source') or 'rules', 'plan.json → order.source'),
        'ready': (sum(1 for t in tasks if (t.get('decision') or {}).get('readiness') == 'ready'),
                  'plan.json → tasks[].decision.readiness'),
        'sizes': (sizes, 'plan.json → tasks[].effort'),
    }


def _order_line(by_assistant, ar):
    if ar: return 'الترتيب: خطوات مساعدك، وكل متطلب مسبق محفوظ' if by_assistant else 'الترتيب: دفعات القواعد'
    return "Order: your assistant's steps, every prerequisite kept" if by_assistant else "Order: the rules' waves"


def _milestone_section(page, milestone, by_id, ar):
    """A milestone: its goal and exit, and its first four cards."""
    page.heading(f"{milestone['id']} · {milestone['name']}", 3)
    page.para(f"{milestone.get('goal_ar' if ar else 'goal', milestone['goal'])} " + ('الخروج: ' if ar else 'Exit: ')
              + milestone.get('exit_ar' if ar else 'exit', milestone['exit']))
    page.items([f"{tid} [{by_id[tid].get('effort')}/{by_id[tid].get('section')}] {clip(by_id[tid].get('title'), 90)}"
                for tid in milestone['tasks'][:4]]
               + ([f"… +{len(milestone['tasks']) - 4}"] if len(milestone['tasks']) > 4 else []))


def write(out, language='ar'):
    ar = language == 'ar'
    for name, builder in zip(NAMES, (current_state, execution_plan)):
        (Path(out) / name).write_text(builder(out, ar), encoding='utf-8')
    return {'reports': len(NAMES)}
