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
import textwrap
from pathlib import Path

WIDTH = 80
NAMES = ('CURRENT-STATE.md', 'TARGET-STATE.md', 'GAP-AND-STRATEGY.md', 'EXECUTION-PLAN.md')


def _load(out, name, default=None):
    try: return json.loads((Path(out) / name).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


class Page:
    """Markdown with a blank line around every block, prose wrapped at 80 columns."""

    def __init__(self, title):
        self.lines = [f'# {title}']

    def heading(self, text, level=2):
        self.lines += ['', '#' * level + ' ' + text]

    def para(self, text):
        self.lines += [''] + textwrap.wrap(str(text), WIDTH, break_long_words=False, break_on_hyphens=False)

    def items(self, rows):
        if not rows: return
        self.lines.append('')
        for row in rows:
            self.lines += textwrap.wrap(str(row), WIDTH, initial_indent='- ', subsequent_indent='  ',
                                        break_long_words=False, break_on_hyphens=False) or ['-']

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
    numbers = {
        'files_parsed': (f"{coverage.get('files_parsed')}/{coverage.get('source_files')}", 'dossier.json → coverage'),
        'features': (len(features), 'features.json'),
        'critical_features': (sum(1 for f in features if f.get('critical')), 'features.json → critical'),
        'debt_items': (len(items), 'debt-register.json'),
        'high_or_critical': (len(severe), 'debt-register.json → severity'),
        'engines': (len(external.get('engines_observed') or []), 'facts/external.json → engines_observed'),
    }
    page = Page('الوضع الراهن' if ar else 'Current state')
    page.heading(L['summary'])
    if severe:
        decision = (f"قبول هذا الوصف أساسًا للتحول، ومعالجة البنود العالية الخطورة ({len(severe)}) أولًا." if ar else
                    f"accept this description as the baseline, and treat the {len(severe)} high or critical items first.")
    else:
        decision = ('قبول هذا الوصف أساسًا للتحول؛ لا بند عالي الخطورة بشاهد كافٍ، فالبداية بمعلم التثبيت.' if ar else
                    'accept this description as the baseline; no high item has enough witnesses, so start with the stabilize milestone.')
    page.para(f"{L['decision']}: " + decision)
    page.heading(L['numbers'], 3)
    page.items([f"{numbers['files_parsed'][0]} " + ('ملفًا محللًا' if ar else 'files analysed') + f" ({numbers['files_parsed'][1]})",
                f"{numbers['features'][0]} " + ('وظيفة، منها' if ar else 'features, of which') + f" {numbers['critical_features'][0]} "
                + ('حرجة' if ar else 'critical') + f" ({numbers['features'][1]})",
                f"{numbers['debt_items'][0]} " + ('بند دَين، منها' if ar else 'debt items, of which') + f" {numbers['high_or_critical'][0]} "
                + ('عالية أو حرجة' if ar else 'high or critical') + f" ({numbers['debt_items'][1]})"])
    page.heading(L['risks'], 3)
    page.items(_risks(register) or ['—'])
    page.heading(L['evidence'])
    page.para(('الوظائف التي يقدمها البرنامج اليوم، بأسطحها والبيانات التي تمسها:' if ar else
               'What the program does today, by its surfaces and the data each feature touches:'))
    page.items([clip(f"{f['name']}: {f.get('description', '')}", 160) for f in features[:12]]
               + ([f"… {len(features) - 12} " + ('أخرى في FEATURES.md' if ar else 'more in FEATURES.md')] if len(features) > 12 else []))
    by_category = {}
    for item in items: by_category[item['category']] = by_category.get(item['category'], 0) + 1
    page.para(('الدَّين حسب الفئة (debt-register.json): ' if ar else 'Debt by category (debt-register.json): ')
              + ', '.join(f'{k} {v}' for k, v in sorted(by_category.items(), key=lambda kv: -kv[1])))
    hottest = sorted(measured, key=lambda r: (-(r.get('complexity_max') or 0), -(r.get('churn') or 0)))[:5]
    if hottest:
        page.para(('أعقد الملفات وأكثرها تغيّرًا (measurements.json):' if ar else 'The most complex, most changed files (measurements.json):'))
        page.items([f"{r['path']}: complexity {r.get('complexity_max')}, commits {r.get('churn')}, fan-in {r.get('fan_in')}" for r in hottest])
    diagram = Path(out) / 'architecture/current/diagram.mmd'
    if diagram.is_file():
        page.heading('C4' if not ar else 'خريطة C4', 3)
        page.block('mermaid', diagram.read_text(encoding='utf-8'))
    page.heading(L['impact'])
    page.para(('كل بند عالي الخطورة في السجل له شاهد حتمي أو أداتان؛ تركه يعني أن الخطر المعروف يبقى في كل إصدار.' if ar else
               'Every high item in the register has a deterministic witness or two tools; leaving one means a known risk ships in every release.'))
    page.heading(L['recommendation'])
    page.para(('ابدأ بمعلم التثبيت في EXECUTION-PLAN.md.' if ar else 'Start with the stabilize milestone in EXECUTION-PLAN.md.'))
    page.heading(L['unexamined'])
    page.items(list(coverage.get('not_examined') or [])[:8]
               + [('محرك غير مثبت: ' if ar else 'engine not installed: ') + name for name in external.get('engines_unavailable') or []])
    page.heading(L['appendices'])
    page.items(['[FEATURES.md](FEATURES.md)', '[MEASUREMENTS.md](MEASUREMENTS.md)', '[RISK-REGISTER.md](RISK-REGISTER.md)',
                '[SECURITY-SURFACE.md](SECURITY-SURFACE.md)', '[LOAD-MODEL.md](LOAD-MODEL.md)', '[ENGINES.md](ENGINES.md)'])
    return page.text(), numbers


def target_state(out, ar):
    L = _labels(ar)
    target = _load(out, 'target-architecture.json', {}) or {}
    components = target.get('target_components') or []
    features = (_load(out, 'features.json', {}) or {}).get('features') or []
    infrastructure = target.get('infrastructure') or []
    absent = [i for i in infrastructure if not i['present']]
    numbers = {
        'reference': (target.get('reference') or '—', 'target-architecture.json → reference'),
        'components': (len(components), 'target-architecture.json → target_components'),
        'features_placed': (f"{sum(1 for f in features if f.get('target_component'))}/{len(features)}", 'features.json → target_component'),
        'infrastructure_absent': (f"{len(absent)}/{len(infrastructure)}", 'target-architecture.json → infrastructure'),
        'forbidden_imports': (target.get('forbidden_edges', 0), 'target-architecture.json → forbidden_edges'),
    }
    page = Page('الصورة المثالية' if ar else 'Target state')
    page.heading(L['summary'])
    page.para(f"{L['decision']}: " + (f"اعتماد النوع المرجعي `{numbers['reference'][0]}` كوحدة واحدة معيارية، بالوظائف نفسها." if ar else
                                       f"adopt `{numbers['reference'][0]}` as a modular monolith, with the same features."))
    page.heading(L['numbers'], 3)
    page.items([f"{numbers['components'][0]} " + ('مكوّنًا مستهدفًا' if ar else 'target components') + f" ({numbers['components'][1]})",
                f"{numbers['features_placed'][0]} " + ('وظيفة لها مكان' if ar else 'features placed') + f" ({numbers['features_placed'][1]})",
                f"{numbers['forbidden_imports'][0]} " + ('استيرادًا ممنوعًا يزول' if ar else 'forbidden imports removed') + f" ({numbers['forbidden_imports'][1]})"])
    page.heading(L['risks'], 3)
    page.items([clip(f"{i['area']}: {i['decision']}", 150) for i in absent[:3]] or ['—'])
    page.heading(L['evidence'])
    page.para(('المكوّنات الأكبر (الأسماء والمسؤوليات كاملة في TARGET-ARCHITECTURE.md):' if ar else
               'The largest components (names and responsibilities in TARGET-ARCHITECTURE.md):'))
    page.items([f"{c['name']} ({c['layer']}): {c.get('files', 0)} files, {c.get('moves_in', 0)} moving in"
                for c in sorted(components, key=lambda c: -c.get('files', 0))[:8]])
    diagram = Path(out) / 'architecture/target/diagram.mmd'
    if diagram.is_file():
        page.heading('C4' if not ar else 'خريطة C4', 3)
        page.block('mermaid', diagram.read_text(encoding='utf-8'))
    page.heading(('البنية التحتية' if ar else 'Infrastructure'))
    page.items([clip(f"{'✅' if i['present'] else '⬜'} {i['area']}: {i.get('tool') or '—'}. {i['evidence']}", 170) for i in infrastructure])
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


def gap_and_strategy(out, ar):
    L = _labels(ar)
    target = _load(out, 'target-architecture.json', {}) or {}
    current = target.get('current_components') or []
    plan = _load(out, 'plan.json', {}) or {}
    milestones = plan.get('milestones') or []
    counts = {}
    for component in current: counts[component.get('relation')] = counts.get(component.get('relation'), 0) + 1
    moved = sum((c.get('projection') or {}).get('moved', 0) for c in current)
    numbers = {
        'dispositions': (counts, 'target-architecture.json → current_components[].relation'),
        'files_to_move': (moved, 'target-architecture.json → current_components[].projection.moved'),
        'milestones': (len(milestones), 'plan.json → milestones'),
    }
    page = Page('الفجوة والاستراتيجية' if ar else 'Gap and strategy')
    page.heading(L['summary'])
    page.para(f"{L['decision']}: " + ('الموافقة على ترتيب المعالم: التثبيت، ثم شبكة الأمان، ثم الحدود، ثم البناء، ثم التصليب.' if ar else
                                       'approve the order: stabilize, safety net, boundaries, build, harden.'))
    page.heading(L['numbers'], 3)
    page.items([', '.join(f'{k} {v}' for k, v in sorted(counts.items())) + f" ({numbers['dispositions'][1]})",
                f"{moved} " + ('ملفًا ينتقل' if ar else 'files move') + f" ({numbers['files_to_move'][1]})",
                f"{len(milestones)} " + ('معالم' if ar else 'milestones') + f" ({numbers['milestones'][1]})"])
    page.heading(L['risks'], 3)
    rebuilt = [c for c in current if c.get('relation') == 'rebuild']
    page.items([f"{c['origin']} → {c.get('target_component')}: {clip(c.get('reason'), 120)}" for c in rebuilt[:3]] or ['—'])
    page.heading(L['evidence'])
    page.para(('كل مكوّن حالي وقراره وأرقامه (الترتيب: حذف، إعادة بناء، تعديل، إبقاء):' if ar else
               'Each current component, its disposition and its numbers (delete, rebuild, modify, retain):'))
    order = {'delete': 0, 'rebuild': 1, 'modify': 2, 'retain': 3}
    page.items([f"{c['origin']}: {c.get('relation')} → {c.get('target_component') or '—'}"
                for c in sorted(current, key=lambda c: (order.get(c.get('relation'), 9), c['origin']))[:20]])
    page.heading(L['impact'])
    page.para(('المكوّن الذي يُعاد بناؤه يُبنى بنمط Strangler Fig: المسار الجديد خلف علم، والقديم يُزال بعد تكافؤ السلوك فقط.' if ar else
               'A component that is rebuilt is done Strangler Fig: the new path behind a flag, the old removed only after behaviour parity.'))
    page.heading(L['recommendation'])
    page.items([f"{m['id']} {m['name']}: {m.get('goal_ar' if ar else 'goal', m['goal'])}" for m in milestones])
    page.heading(L['unexamined'])
    page.items([('الكلفة بالزمن غير مقيسة: الحجم S/M/L قاعدة على الملفات والتابعين.' if ar else
                 'Duration is not measured: S/M/L is a rule on files and dependents.')])
    page.heading(L['appendices'])
    page.items(['[TARGET-ARCHITECTURE.md](TARGET-ARCHITECTURE.md)', '[ROADMAP.md](ROADMAP.md)', '[SUSTAINABILITY.md](SUSTAINABILITY.md)'])
    return page.text(), numbers


def execution_plan(out, ar):
    L = _labels(ar)
    plan = _load(out, 'plan.json', {}) or {}
    tasks = plan.get('tasks') or []
    by_id = {t['id']: t for t in tasks}
    ready = sum(1 for t in tasks if (t.get('decision') or {}).get('readiness') == 'ready')
    sizes = {}
    for t in tasks: sizes[t.get('effort')] = sizes.get(t.get('effort'), 0) + 1
    numbers = {
        'cards': (len(tasks), 'plan.json → tasks'),
        'ready': (ready, 'plan.json → tasks[].decision.readiness'),
        'sizes': (sizes, 'plan.json → tasks[].effort'),
    }
    page = Page('خطة التنفيذ' if ar else 'Execution plan')
    page.heading(L['summary'])
    page.para(f"{L['decision']}: " + (f"تخصيص فريق للمعلم الأول ({(plan.get('milestones') or [{}])[0].get('name', '—')})." if ar else
                                       f"staff the first milestone ({(plan.get('milestones') or [{}])[0].get('name', '—')})."))
    page.heading(L['numbers'], 3)
    page.items([f"{len(tasks)} " + ('بطاقة' if ar else 'cards') + f" ({numbers['cards'][1]})",
                f"{ready} " + ('جاهزة بأمر قبول يقرر' if ar else 'ready, with an acceptance command that decides') + f" ({numbers['ready'][1]})",
                ', '.join(f'{k} {v}' for k, v in sorted((k or '?', v) for k, v in sizes.items())) + f" ({numbers['sizes'][1]})"])
    page.heading(L['risks'], 3)
    investigations = [t for t in tasks if t.get('kind') == 'investigate']
    page.items([(f"{len(investigations)} بطاقة تحقيق تنتظر قرارًا مسجلًا (eaos decision-review)." if ar else
                 f"{len(investigations)} investigation cards wait for a recorded decision (eaos decision-review).")])
    page.heading(('المعالم' if ar else 'Milestones'))
    for milestone in plan.get('milestones') or []:
        page.heading(f"{milestone['id']} · {milestone['name']}", 3)
        page.para(f"{milestone.get('goal_ar' if ar else 'goal', milestone['goal'])} " + ('الخروج: ' if ar else 'Exit: ')
                  + milestone.get('exit_ar' if ar else 'exit', milestone['exit']))
        page.items([f"{tid} [{by_id[tid].get('effort')}/{by_id[tid].get('section')}] {clip(by_id[tid].get('title'), 90)}"
                    for tid in milestone['tasks'][:4]]
                   + ([f"… +{len(milestone['tasks']) - 4}"] if len(milestone['tasks']) > 4 else []))
    page.heading(('الأقسام' if ar else 'Sections'))
    page.items([f"{s['section']}: {len(s['tasks'])} " + ('بطاقة' if ar else 'cards')
                + (f", {'تنتظر' if ar else 'waits for'} {', '.join(s['depends_on'])}" if s['depends_on'] else '')
                for s in plan.get('sections') or []])
    page.heading(L['recommendation'])
    page.para(('نفّذ كل بطاقة في نسخة معزولة، وشغّل أمر قبولها، ثم أعد التدقيق؛ التراجع لكل بطاقة مكتوب فيها.' if ar else
               'Run each card in an isolated copy, run its acceptance command, then audit again; each card states its rollback.'))
    page.heading(L['unexamined'])
    page.items([('لم تُشغَّل أي بطاقة على كود المشروع بعد؛ التنفيذ يحتاج تفويض المالك (authorization.json).' if ar else
                 'No card has run against the project yet; execution needs the owner\'s authorization.json.')])
    page.heading(L['appendices'])
    page.items(['[ROADMAP.md](ROADMAP.md)', '[PLAN/WAVES.md](PLAN/WAVES.md)', '[EXECUTION-GUIDE.md](EXECUTION-GUIDE.md)'])
    return page.text(), numbers


def write(out, language='ar'):
    ar = language == 'ar'
    record = {'schema_version': 1, 'reports': {}}
    for name, builder in zip(NAMES, (current_state, target_state, gap_and_strategy, execution_plan)):
        text, numbers = builder(out, ar)
        (Path(out) / name).write_text(text, encoding='utf-8')
        record['reports'][name] = {key: {'value': value, 'source': source} for key, (value, source) in numbers.items()}
    (Path(out) / 'reports.json').write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return {'reports': len(NAMES)}
