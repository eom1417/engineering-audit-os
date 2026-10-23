"""The four reports a client reads first: where the project is, where it should be, the distance, and the plan.

  CURRENT-STATE.md      what the program is today: features, data, measured risk, the C4 view
  TARGET-STATE.md       the same features on the project's reference type: components, infrastructure, decisions
  GAP-AND-STRATEGY.md   the distance, component by component and item by item, and the order to close it
  EXECUTION-PLAN.md     milestones, sections and the first cards a team starts with

Each follows docs/MASTER-BLUEPRINT.md §6: a one-page summary (the decision asked for, the three numbers that
matter, the three largest risks), then evidence, inference, impact and recommendation, then what was not
examined, then links to the reference documents. Every number names where it comes from: a record, an item
id or a claim id. They repeat nothing the appendices hold; they link to them. Their record is reports.json:
the numbers each report states, with their sources.
"""
import json
import re
import textwrap
from pathlib import Path

from .labels import decided, who_decided

WIDTH = 80
NAMES = ('CURRENT-STATE.md', 'TARGET-STATE.md', 'GAP-AND-STRATEGY.md', 'EXECUTION-PLAN.md')


def _load(out, name, default=None):
    try: return json.loads((Path(out) / name).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


CODE_SPAN = re.compile(r'(`[^`]*`)')


def escape(text):
    """Text from the project (identifiers, paths, titles) is literal in Markdown: `_x_` and `*x*` are not
    emphasis, `<T>` is not HTML. Code spans stay as written; a span cut open by clip() is closed."""
    text = str(text)
    if text.count('`') % 2: text += '`'
    return ''.join(part if CODE_SPAN.fullmatch(part) else re.sub(r'([_*<>])', r'\\\1', part)
                   for part in CODE_SPAN.split(text))


LEADING_MARKER = re.compile(r'^(\s*)(#|[-+>]\s|\d+[.)]\s)')


def wrap(text, **indents):
    """Wrapped lines, none of which starts with a Markdown marker the text did not mean: a line that wraps onto
    `#`, `- ` or `3. ` would turn into a heading or a list."""
    lines = textwrap.wrap(escape(text), WIDTH, break_long_words=False, break_on_hyphens=False, **indents)
    first = len(indents.get('initial_indent', ''))
    return [line if index == 0 and first else LEADING_MARKER.sub(lambda m: m.group(1) + '\\' + m.group(2), line, count=1)
            for index, line in enumerate(lines)]


class Page:
    """Markdown with a blank line around every block, prose wrapped at 80 columns, every text escaped."""

    def __init__(self, title):
        self.lines = [f'# {title}']

    def heading(self, text, level=2):
        self.lines += ['', '#' * level + ' ' + escape(text)]

    def para(self, text):
        self.lines += [''] + wrap(text)

    def items(self, rows):
        if not rows: return
        self.lines.append('')
        for row in rows:
            self.lines += wrap(row, initial_indent='- ', subsequent_indent='  ') or ['-']

    def block(self, language, text):
        self.lines += ['', f'```{language}', *text.rstrip().splitlines(), '```']

    def text(self):
        return '\n'.join(self.lines) + '\n'


def _labels(ar):
    return (dict(summary='الخلاصة', decision='القرار المطلوب', numbers='أهم الأرقام', risks='أكبر المخاطر',
                 evidence='الدليل والاستنتاج', impact='الأثر', recommendation='التوصية', unexamined='ما لم يُفحص',
                 appendices='الملاحق', source='المصدر') if ar else
            dict(summary='Summary', decision='Decision asked for', numbers='The numbers that matter',
                 risks='The largest risks', evidence='Evidence and inference', impact='Impact',
                 recommendation='Recommendation', unexamined='Not examined', appendices='Appendices', source='source'))


def clip(text, n):
    """A text cut to n characters shows that it was cut."""
    text = ' '.join(str(text).split())
    return text if len(text) <= n else text[:n - 1].rstrip() + '…'


def _risks(register, n=3):
    return [f"{item['id']} ({item['severity']}, {item['category']}): {clip(item['title'], 110)}"
            for item in (register or {}).get('items', [])[:n]]


VERDICT_WORDS = {'keep': ('keep: already right, nothing changes', 'يبقى: صحيح كما هو، لا تغيير'),
                 'improve': ('improve', 'يتحسّن'), 'unmeasured': ('not measured in this check', 'لم يُقَس في هذا الفحص')}


def aspects(out):
    """Every aspect of the program with its verdict: the final target's (target-architecture.json, written by the
    reconcile stage), else the rules' verdict from the records (eaos/aspects.py)."""
    rows = (_load(out, 'target-architecture.json', {}) or {}).get('aspects')
    if rows: return rows
    from ..aspects import final
    return final(out)


def aspect_section(page, out, ar):
    """One line per aspect: its verdict, why, and for one to improve its plan and cards; who decided. The counts."""
    rows = aspects(out)
    page.heading('كل جانب من البرنامج: يبقى أو يتحسّن' if ar else 'Every aspect of the program: keep or improve')
    page.para('حكم مساعدك على كل جانب حيث حكم، وحكم القواعد في الباقي (target-architecture.json → aspects).' if ar else
              "Your assistant's verdict on each aspect it judged, the rules' on the rest (target-architecture.json → aspects).")
    page.items([_aspect_line(row, ar) for row in rows])
    return {verdict: sum(1 for row in rows if row['verdict'] == verdict) for verdict in ('keep', 'improve', 'unmeasured')}


def _aspect_line(row, ar):
    """An aspect, its verdict and why, its plan and cards when it is to improve, and who decided."""
    label = row['label'][1 if ar else 0] if isinstance(row.get('label'), (list, tuple)) else row.get('label') or row['aspect']
    words = VERDICT_WORDS.get(row['verdict'], (row['verdict'], row['verdict']))[1 if ar else 0]
    who = ('مساعدك' if ar else 'your assistant') if row.get('decided_by') == 'assistant' else ('القواعد' if ar else 'the rules')
    line = f"{label}: {words}. {clip(row.get('why'), 220)}"
    if row['verdict'] == 'improve' and row.get('plan'): line += (' الخطة: ' if ar else ' Plan: ') + clip(row['plan'], 220)
    if row.get('cards'): line += ' (' + ', '.join(row['cards'][:4]) + ')'
    return line + f" ({who})"


def _diagram(page, out, which, ar):
    """The C4 diagram of `which` (current or target) as a mermaid block, when it was drawn."""
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
            'accept this description as the baseline; no high item has enough witnesses, so start with the stabilize milestone.')


def _feature_items(features, ar):
    return ([clip(f"{f['name']}: {f.get('description', '')}", 160) for f in features[:12]]
            + ([f"… {len(features) - 12} " + ('أخرى في features.json' if ar else 'more in features.json')] if len(features) > 12 else []))


def _unexamined(coverage, external, ar):
    return (list(coverage.get('not_examined') or [])[:8]
            + [('محرك غير مثبت: ' if ar else 'engine not installed: ') + name for name in external.get('engines_unavailable') or []])


def _current_number_items(numbers, ar):
    """The summary's three numbers, each with the record it comes from."""
    return [f"{numbers['files_parsed'][0]} " + ('ملفًا محللًا' if ar else 'files analysed') + f" ({numbers['files_parsed'][1]})",
            f"{numbers['features'][0]} " + ('وظيفة، منها' if ar else 'features, of which') + f" {numbers['critical_features'][0]} "
            + ('حرجة' if ar else 'critical') + f" ({numbers['features'][1]})",
            f"{numbers['debt_items'][0]} " + ('بند دَين، منها' if ar else 'debt items, of which') + f" {numbers['high_or_critical'][0]} "
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
        page.para(('أعقد الملفات وأكثرها تغيّرًا (measurements.json):' if ar else 'The most complex, most changed files (measurements.json):'))
        page.items([f"{r['path']}: complexity {r.get('complexity_max')}, commits {r.get('churn')}, fan-in {r.get('fan_in')}" for r in hottest])


def current_state(out, ar):
    L = _labels(ar)
    dossier = _load(out, 'dossier.json', {}) or {}
    coverage = dossier.get('coverage') or {}
    features = (_load(out, 'features.json', {}) or {}).get('features') or []
    register = _load(out, 'debt-register.json', {}) or {}
    items = register.get('items') or []
    severe = [i for i in items if i['severity'] in ('high', 'critical')]
    external = (_load(out, 'facts/external.json', {}) or {}).get('summary') or {}
    measured = (_load(out, 'measurements.json', {}) or {}).get('files') or []
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
    page.heading(L['impact'])
    page.para(('كل بند عالي الخطورة في السجل له شاهد حتمي أو أداتان؛ تركه يعني أن الخطر المعروف يبقى في كل إصدار.' if ar else
               'Every high item in the register has a deterministic witness or two tools; leaving one means a known risk ships in every release.'))
    page.heading(L['recommendation'])
    page.para(('ابدأ بمعلم التثبيت في EXECUTION-PLAN.md.' if ar else 'Start with the stabilize milestone in EXECUTION-PLAN.md.'))
    page.heading(L['unexamined'])
    page.items(_unexamined(coverage, external, ar))
    page.heading(L['appendices'])
    page.items(['`features.json`', '`measurements.json`', '`debt-register.json`', '`load-model.json`', '`facts/external.json`'])
    return page.text(), numbers


def target_state(out, ar):
    L = _labels(ar)
    target = _load(out, 'target-architecture.json', {}) or {}
    components = target.get('target_components') or []
    features = (_load(out, 'features.json', {}) or {}).get('features') or []
    infrastructure = target.get('infrastructure') or []
    absent = [i for i in infrastructure if not i['present']]
    numbers = _target_numbers(target, components, features, infrastructure, absent, ar)
    page = Page('الصورة المثالية' if ar else 'Target state')
    page.heading(L['summary'])
    page.para(f"{L['decision']}: " + (f"اعتماد النوع المرجعي `{numbers['reference'][0]}` كوحدة واحدة معيارية، بالوظائف نفسها." if ar else
                                       f"adopt `{numbers['reference'][0]}` as a modular monolith, with the same features."))
    page.heading(L['numbers'], 3)
    page.items([f"{numbers['components'][0]} " + ('مكوّنًا مستهدفًا' if ar else 'target components') + f" ({numbers['components'][1]})",
                f"{numbers['features_placed'][0]} " + ('وظيفة لها مكان' if ar else 'features placed') + f" ({numbers['features_placed'][1]})",
                f"{numbers['forbidden_imports'][0]} " + ('استيرادًا ممنوعًا يزول' if ar else 'forbidden imports removed') + f" ({numbers['forbidden_imports'][1]})",
                f"{numbers['decided'][0]} ({numbers['decided'][1]})"])
    page.heading(L['risks'], 3)
    page.items([clip(f"{i['area']}: {i['decision']}", 150) for i in absent[:3]] or ['—'])
    page.heading(L['evidence'])
    page.para(('المكوّنات الأكبر (الأسماء والمسؤوليات كاملة في TARGET-ARCHITECTURE.md):' if ar else
               'The largest components (names and responsibilities in TARGET-ARCHITECTURE.md):'))
    page.items([f"{c['name']} ({c['layer']}): {c.get('files', 0)} files, {c.get('moves_in', 0)} moving in"
                for c in sorted(components, key=lambda c: -c.get('files', 0))[:8]])
    _diagram(page, out, 'target', ar)
    page.heading(('البنية التحتية' if ar else 'Infrastructure'))
    page.items([clip(f"{'✅' if i['present'] else '⬜'} {i['area']}: {i.get('tool') or '—'}. {i['evidence']}", 170) for i in infrastructure])
    numbers['aspects'] = (aspect_section(page, out, ar), 'target-architecture.json → aspects')
    page.heading(L['recommendation'])
    page.para(('القرارات المعمارية بصيغة MADR في adr/، وكل قرار يذكر بدائله وكلفة ألا نفعل شيئًا.' if ar else
               'The decisions are MADR files in adr/, each with its options and the cost of doing nothing.'))
    page.heading(L['unexamined'])
    page.items([('لا يوجد نوع مرجعي معروف لهذا المشروع؛ لا إسقاط.' if ar else 'No known reference type fits this project; no projection.')]
               if not target.get('reference') else [('الخدمات المصغّرة غير مقترحة: لا سيناريو جودة يبررها.' if ar else
                                                     'No service split is proposed: no quality scenario justifies one.')])
    page.heading(L['appendices'])
    page.items(['[TARGET-ARCHITECTURE.md](TARGET-ARCHITECTURE.md)', '[adr/](adr/)', '[architecture/](architecture/)'])
    return page.text(), numbers


def _target_numbers(target, components, features, infrastructure, absent, ar):
    return {
        'reference': (target.get('reference') or '—', 'target-architecture.json → reference'),
        'components': (len(components), 'target-architecture.json → target_components'),
        'features_placed': (f"{len({f.get('name') for f in features} & {c.get('feature') for c in components})}/{len(features)}",
                            'target-architecture.json → target_components → feature'),
        'infrastructure_absent': (f"{len(absent)}/{len(infrastructure)}", 'target-architecture.json → infrastructure'),
        'forbidden_imports': (target.get('forbidden_edges', 0), 'target-architecture.json → forbidden_edges'),
        'decided': (who_decided(target, 'ar' if ar else 'en'), 'target-architecture.json → decided'),
    }


def _gap_numbers(current, milestones):
    """The numbers the gap page cites, each with the record it is read from."""
    counts = {}
    for component in current: counts[component.get('relation')] = counts.get(component.get('relation'), 0) + 1
    return {
        'dispositions': (counts, 'target-architecture.json → current_components[].relation'),
        'files_to_move': (sum((c.get('projection') or {}).get('moved', 0) for c in current),
                          'target-architecture.json → current_components[].projection.moved'),
        'milestones': (len(milestones), 'plan.json → milestones'),
    }


def _rebuilt_items(current):
    rebuilt = [c for c in current if c.get('relation') == 'rebuild']
    return [f"{c['origin']} → {c.get('target_component')}: {clip(c.get('reason'), 120)}" for c in rebuilt[:3]] or ['—']


def _disposition_items(current, ar):
    """Each component of today, its disposition and where it goes: the deleted first, then rebuilt, modified, kept."""
    order = {'delete': 0, 'rebuild': 1, 'modify': 2, 'retain': 3}
    return [f"{c['origin']}: {c.get('relation')} → {c.get('target_component') or '—'}"
            + (f" ({decided(c['decided_by']['label'], 'ar' if ar else 'en')})" if c.get('decided_by') else '')
            for c in sorted(current, key=lambda c: (order.get(c.get('relation'), 9), c['origin']))[:20]]


def gap_and_strategy(out, ar):
    L = _labels(ar)
    target = _load(out, 'target-architecture.json', {}) or {}
    current = target.get('current_components') or []
    plan = _load(out, 'plan.json', {}) or {}
    milestones = plan.get('milestones') or []
    numbers = _gap_numbers(current, milestones)
    counts, moved = numbers['dispositions'][0], numbers['files_to_move'][0]
    page = Page('الفجوة والاستراتيجية' if ar else 'Gap and strategy')
    page.heading(L['summary'])
    page.para(f"{L['decision']}: " + ('الموافقة على ترتيب المعالم: التثبيت، ثم شبكة الأمان، ثم الحدود، ثم البناء، ثم التصليب.' if ar else
                                       'approve the order: stabilize, safety net, boundaries, build, harden.'))
    page.heading(L['numbers'], 3)
    page.items([', '.join(f'{k} {v}' for k, v in sorted(counts.items())) + f" ({numbers['dispositions'][1]})",
                f"{moved} " + ('ملفًا ينتقل' if ar else 'files move') + f" ({numbers['files_to_move'][1]})",
                f"{len(milestones)} " + ('معالم' if ar else 'milestones') + f" ({numbers['milestones'][1]})"])
    page.heading(L['risks'], 3)
    page.items(_rebuilt_items(current))
    page.heading(L['evidence'])
    page.para(('كل مكوّن حالي وقراره وأرقامه (الترتيب: حذف، إعادة بناء، تعديل، إبقاء):' if ar else
               'Each current component, its disposition and its numbers (delete, rebuild, modify, retain):'))
    page.items(_disposition_items(current, ar))
    numbers['aspects'] = (aspect_section(page, out, ar), 'target-architecture.json → aspects')
    page.heading(L['impact'])
    page.para(('المكوّن الذي يُعاد بناؤه يُبنى بنمط Strangler Fig: المسار الجديد خلف علم، والقديم يُزال بعد تكافؤ السلوك فقط.' if ar else
               'A component that is rebuilt is done Strangler Fig: the new path behind a flag, the old removed only after behaviour parity.'))
    page.heading(L['recommendation'])
    page.items([f"{m['id']} {m['name']}: {m.get('goal_ar' if ar else 'goal', m['goal'])}" for m in milestones])
    page.heading(L['unexamined'])
    page.items([('الكلفة بالزمن غير مقيسة: الحجم S/M/L قاعدة على الملفات والتابعين.' if ar else
                 'Duration is not measured: S/M/L is a rule on files and dependents.')])
    page.heading(L['appendices'])
    page.items(['[TARGET-ARCHITECTURE.md](TARGET-ARCHITECTURE.md)', '[EXECUTION-PLAN.md](EXECUTION-PLAN.md)'])
    return page.text(), numbers


def execution_plan(out, ar):
    L = _labels(ar)
    plan = _load(out, 'plan.json', {}) or {}
    tasks = plan.get('tasks') or []
    numbers = _plan_numbers(plan, tasks, _load(out, 'cards.json', {}) or {})
    page = Page('خطة التنفيذ' if ar else 'Execution plan')
    page.heading(L['summary'])
    page.para(f"{L['decision']}: " + (f"تخصيص فريق للمعلم الأول ({(plan.get('milestones') or [{}])[0].get('name', '—')})." if ar else
                                       f"staff the first milestone ({(plan.get('milestones') or [{}])[0].get('name', '—')})."))
    _numbers_section(page, L, tasks, numbers, ar)
    _plan_sections(page, L, plan, tasks, ar)
    return page.text(), numbers


def _numbers_section(page, L, tasks, numbers, ar):
    """The plan's numbers: its cards, the ready ones, their sizes, the cards left out or added, and who ordered them."""
    ready, sizes = numbers['ready'][0], numbers['sizes'][0]
    page.heading(L['numbers'], 3)
    page.items([f"{len(tasks)} " + ('بطاقة' if ar else 'cards') + f" ({numbers['cards'][1]})",
                f"{ready} " + ('جاهزة بأمر قبول يقرر' if ar else 'ready, with an acceptance command that decides') + f" ({numbers['ready'][1]})",
                ', '.join(f'{k} {v}' for k, v in sorted((k or '?', v) for k, v in sizes.items())) + f" ({numbers['sizes'][1]})",
                (f"{numbers['set_aside'][0]} بطاقة رفضها مساعدك فخرجت من الخطة، و{numbers['design'][0]} بطاقة تصميم من صور الشاشات" if ar else
                 f"{numbers['set_aside'][0]} cards your assistant rejected left the plan; {numbers['design'][0]} design cards came from the screens")
                + f" ({numbers['set_aside'][1]}, {numbers['design'][1]})",
                _order_line(numbers['order'][0] == 'assistant', ar) + f" ({numbers['order'][1]}, PLAN/STEPS.md)"])


def _plan_sections(page, L, plan, tasks, ar):
    """The risks, the milestones and sections, the recommendation, what was not examined, and the appendices."""
    by_id = {t['id']: t for t in tasks}
    page.heading(L['risks'], 3)
    investigations = [t for t in tasks if t.get('kind') == 'investigate']
    page.items([(f"{len(investigations)} بطاقة تحقيق تنتظر قرارًا مسجلًا (eaos decision-review)." if ar else
                 f"{len(investigations)} investigation cards wait for a recorded decision (eaos decision-review).")])
    page.heading(('المعالم' if ar else 'Milestones'))
    for milestone in plan.get('milestones') or []: _milestone_section(page, milestone, by_id, ar)
    page.heading(('الأقسام' if ar else 'Sections'))
    page.items([_section_line(s, ar) for s in plan.get('sections') or []])
    page.heading(L['recommendation'])
    page.para(('نفّذ كل بطاقة في نسخة معزولة، وشغّل أمر قبولها، ثم أعد التدقيق؛ التراجع لكل بطاقة مكتوب فيها.' if ar else
               'Run each card in an isolated copy, run its acceptance command, then audit again; each card states its rollback.'))
    page.heading(L['unexamined'])
    page.items([('لم تُشغَّل أي بطاقة على كود المشروع بعد؛ التنفيذ يحتاج تفويض المالك (authorization.json).' if ar else
                 'No card has run against the project yet; execution needs the owner\'s authorization.json.')])
    page.heading(L['appendices'])
    page.items(['[PLAN/STEPS.md](PLAN/STEPS.md)', '[PLAN/WAVES.md](PLAN/WAVES.md)'])


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
        'ready': (sum(1 for t in tasks if (t.get('decision') or {}).get('readiness') == 'ready'), 'plan.json → tasks[].decision.readiness'),
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
    record = {'schema_version': 1, 'reports': {}}
    for name, builder in zip(NAMES, (current_state, target_state, gap_and_strategy, execution_plan)):
        text, numbers = builder(out, ar)
        (Path(out) / name).write_text(text, encoding='utf-8')
        record['reports'][name] = {key: {'value': value, 'source': source} for key, (value, source) in numbers.items()}
    (Path(out) / 'reports.json').write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return {'reports': len(NAMES)}
