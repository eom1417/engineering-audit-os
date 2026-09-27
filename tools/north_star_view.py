"""What a reader follows: docs/NORTH-STAR.md and the two generated blocks of each README.

The view is a flow of twenty-five steps. For each: what it does, with which tools, into which output, its
weight in points, how much of it is done, the quality of its output, and the gate that must hold before the
next step starts. The same numbers feed every page, so no page can say something another does not.
"""
from north_star_steps import OPEN_CAP, SIZE_POINTS, criteria, gate_text, overall, step, task_completion

BLOCKS = ('pipeline', 'progress')
MARK = {'todo': '⬜', 'done': '✅', 'blocked': '⛔'}
STATE = {'ar': {'done': '✅ مكتملة', 'current': '🟡 قيد العمل', 'next': '⬜ التالية', 'owner': '🔴 تحتاج مدخلًا منك'},
         'en': {'done': '✅ done', 'current': '🟡 in progress', 'next': '⬜ next', 'owner': '🔴 needs owner input'}}
WAITS_ON = {'ar': {'sandbox': 'بيئة معزولة وتفويض بتشغيل كود المشروع', 'model_provider': 'مزوّد نموذج (مفتاح API)',
                   'human': 'مراجع بشري من خارج المشروع'},
            'en': {'sandbox': 'a sandbox and authorization to run the project', 'model_provider': 'a model provider (API key)',
                   'human': 'a human reviewer from outside the project'}}
NEEDS = {'none': 'نموذج أو مطوّر', 'model_provider': 'يحتاج مزوّد نموذج', 'human': 'يحتاج إنسانًا من خارج المشروع',
         'sandbox': 'يحتاج بيئة معزولة وتفويضًا لتشغيل كود المشروع'}
DIRTY = {'ar': '`+`: قيس على تغييرات فوق هذا الالتزام، حُفظت في الالتزام التالي.',
         'en': '`+`: measured on changes over this commit, saved in the next one.'}
STYLE = ['    classDef done fill:#dcfce7,stroke:#15803d,color:#14532d,stroke-width:2px',
         '    classDef current fill:#fef9c3,stroke:#ca8a04,color:#713f12,stroke-width:3px',
         '    classDef next fill:#f1f5f9,stroke:#64748b,color:#1e293b',
         '    classDef owner fill:#fee2e2,stroke:#b91c1c,color:#7f1d1d,stroke-dasharray:5 3']


def order(record):
    return [name for phase in record.get('roadmap', []) for name in phase['milestones']] or [m['id'] for m in record['milestones']]


def progress(record):
    """[(sequence, milestone, state)] in execution order. A step is done when every task is; the first one not
    done is current; after it, one whose open tasks need a sandbox, a model or an outside person waits on the
    owner, and the rest are next."""
    by_id = {milestone['id']: milestone for milestone in record['milestones']}
    rows, current = [], False
    for sequence, name in enumerate(order(record), 1):
        milestone = by_id[name]
        if all(task['status'] == 'done' for task in milestone['tasks']): state = 'done'
        elif not current: state, current = 'current', True
        elif any(task['needs'] != 'none' for task in milestone['tasks'] if task['status'] != 'done'): state = 'owner'
        else: state = 'next'
        rows.append((sequence, milestone, state))
    return rows


def completion(record):
    rows = progress(record)
    all_tasks = [task for milestone in record['milestones'] for task in milestone['tasks']]
    done = sum(state == 'done' for _, _, state in rows)
    return {'rows': rows, 'steps': {m['id']: step(m, record) for m in record['milestones']},
            'points': overall(record), 'milestones_done': done, 'milestones': len(rows),
            'tasks_done': sum(task['status'] == 'done' for task in all_tasks), 'tasks': len(all_tasks),
            'current': next(((sequence, milestone) for sequence, milestone, state in rows if state == 'current'), None),
            'owner': [(sequence, milestone) for sequence, milestone, state in rows if state == 'owner']}


def summary_line(record):
    done = completion(record)
    return (f"progress: {done['points']}/100 points; {done['milestones_done']}/{done['milestones']} steps done, "
            f"{done['tasks_done']}/{done['tasks']} tasks")


def bar(percent, width=25):
    filled = round(width * percent / 100)
    return '█' * filled + '░' * (width - filled)


def pct(value):
    return '—' if value is None else f'{round(value * 100)}%'


def short_ar(title):
    return title.split(':')[0].split('،')[0].strip()


def short_en(title):
    return title.split(':')[0].strip()


def label(*lines):
    return '"' + '<br/>'.join(str(line).replace('"', "'") for line in lines if line) + '"'


def edge(text):
    return '|"' + text.replace('"', "'") + '"|'


def step_title(milestone, language):
    return milestone['title'] if language == 'ar' else milestone['title_en']


def stage_completion(record, stage_id, steps):
    """A pipeline stage is as built as the steps serving it, weighted by their points."""
    serving = [m for m in record['milestones'] if stage_id in m.get('stages', [])]
    total = sum(m['weight'] for m in serving)
    return sum(m['weight'] * steps[m['id']]['completion'] for m in serving) / total if total else 0.0


def stage_state(value):
    return 'done' if value >= 1 else 'current' if value > 0 else 'next'


ROW = 4
INIT = "%%{init: {'flowchart': {'wrappingWidth': 260, 'nodeSpacing': 40, 'rankSpacing': 60}}}%%"


def rows_chart(rows, joins):
    """Rows of at most ROW boxes, left to right, each arrow labelled with its gate. A row links to the next as
    a whole (subgraph to subgraph), which keeps each row horizontal instead of one tall column."""
    out = ['```mermaid', INIT, 'flowchart TB']
    for key, title, nodes, links in rows:
        out += [f'    subgraph {key}[{label(title)}]', '        direction LR']
        out += [f'        {node}[{text}]:::{state}' for node, text, state in nodes]
        out += [f'        {a} -->{edge(gate)} {b}' for a, b, gate in links]
        out.append('    end')
    out += [f'    {a} ==>{edge(gate)} {b}' for a, b, gate in joins]
    return out + STYLE + ['```']


def chunked(items, size=ROW):
    return [items[index:index + size] for index in range(0, len(items), size)]


def pipeline_chart(record, language):
    """The product's own fifteen stages: each box its output, each arrow the gate that must pass to go on."""
    ar = language == 'ar'
    steps = {m['id']: step(m, record) for m in record['milestones']}
    groups = [('التقييم: يقرأ المشروع فقط' if ar else 'Assessment: reads the project only', lambda s: s['id'] <= 'S07'),
              ('التنفيذ: بيئة معزولة بتفويض المالك' if ar else 'Execution: isolated, with the owner\'s authorization',
               lambda s: 'S08' <= s['id'] <= 'S14'),
              ('الحوكمة والتسليم' if ar else 'Governance and handover', lambda s: s['id'] == 'S15')]
    gate_of = {s['id']: (s['gate'] if ar else s['gate_en']) for s in record['pipeline']}
    rows, joins = [], []
    for title, member in groups:
        stages = [s for s in record['pipeline'] if member(s)]
        parts = chunked(stages)
        for index, part in enumerate(parts):
            nodes = []
            for stage in part:
                built = stage_completion(record, stage['id'], steps)
                outputs = ' · '.join(stage['outputs'][:2]) + (' …' if len(stage['outputs']) > 2 else '')
                nodes.append((stage['id'], label(f"<b>{stage['id']} · {stage['name'] if ar else stage['name_en']}</b>",
                                                 '📄 ' + outputs, f"▰ {pct(built)}"), stage_state(built)))
            links = [(x['id'], y['id'], '✔ ' + gate_of[x['id']]) for x, y in zip(part, part[1:])]
            key = f"P{len(rows) + 1}"
            if rows:
                previous = rows[-1][2][-1][0]
                gate = gate_of[previous] + ((' + تفويض المالك' if ar else ' + owner authorization') if previous == 'S07' else '')
                joins.append((rows[-1][0], key, '✔ ' + gate))
            rows.append((key, title + (f' ({index + 1}/{len(parts)})' if len(parts) > 1 else ''), nodes, links))
    loop = ('LOOP', label('↺ ' + ('إعادة التدقيق بعد كل تغيير: يعود إلى S01' if ar else 're-audit after every change: back to S01')), 'next')
    rows[-1] = (rows[-1][0], rows[-1][1], rows[-1][2] + [loop], rows[-1][3] + [('S15', 'LOOP', '✔ ' + gate_of['S15'])])
    return rows_chart(rows, joins)


def steps_chart(record, language):
    """The twenty-five steps in order: weight, completion, and on each arrow the gate the step must pass."""
    ar = language == 'ar'
    done = completion(record)
    phase_of = {name: phase for phase in record['roadmap'] for name in phase['milestones']}
    rows, joins = [], []
    for phase in record['roadmap']:
        members = [(sequence, milestone, state) for sequence, milestone, state in done['rows'] if phase_of[milestone['id']] is phase]
        parts = chunked(members)
        for index, part in enumerate(parts):
            nodes = []
            for sequence, milestone, state in part:
                measured = done['steps'][milestone['id']]
                nodes.append((milestone['id'], label(f"<b>{sequence} · {milestone['id']}</b>", short_ar(milestone['title']),
                                                     short_en(milestone['title_en']),
                                                     f"⚖ {milestone['weight']} · ▰ {pct(measured['completion'])}"), state))
            gate = lambda milestone: '✔ ' + gate_text(done['steps'][milestone['id']]['gate'], language, limit=3)
            links = [(x[1]['id'], y[1]['id'], gate(x[1])) for x, y in zip(part, part[1:])]
            key = f"{phase['id']}_{index + 1}"
            if rows: joins.append((rows[-1][0], key, gate(rows[-1][4])))
            title = phase['id'] + ' · ' + (phase['title'] if ar else phase['title_en'])
            rows.append((key, title + (f' ({index + 1}/{len(parts)})' if len(parts) > 1 else ''), nodes, links, part[-1][1]))
    return rows_chart([row[:4] for row in rows], joins)


SYMBOLS = {'ar': '⚖ الوزن بالنقاط (من 100) · ▰ نسبة الإنجاز · ✔ على السهم: بوابة الانتقال، أي المعايير التي يجب أن تتحقق قبل الخطوة التالية',
           'en': '⚖ weight in points (of 100) · ▰ completion · ✔ on an arrow: the transition gate, the criteria that must hold before the next step'}


def legend(language):
    return ' · '.join(STATE[language][state] for state in ('done', 'current', 'next', 'owner')) + '  \n' + SYMBOLS[language]


def gate_row(item, language):
    ar = language == 'ar'
    if item['kind'] == 'indicator':
        condition = f"{item['id']} {'=' if item['min'] >= 1 else '≥'} {item['min']:g}"
        return f"| {item['name']} | `{condition}` | {'—' if item['value'] is None else item['value']} | {'✅' if item['holds'] else '❌'} |"
    if item['kind'] == 'measured':
        return (f"| {item['name']} | `{item['id']}` {'مقيس' if ar else 'measured'} | {'—' if item['value'] is None else item['value']} | "
                f"{'✅' if item['holds'] else '❌'} |")
    return f"| {'اختبار قبول' if ar else 'acceptance test'} | `{item['id']}` | — | {'✅' if item['holds'] else '⬜'} |"


def headline(record, language):
    """The progress figure and the table under it, the same on every page."""
    ar = language == 'ar'
    done = completion(record)
    points = done['points']
    now = '—' if done['current'] is None else f"{done['current'][0]} · {done['current'][1]['id']} {step_title(done['current'][1], language)}"
    remaining_owner = sum(milestone['weight'] for _, milestone in done['owner'])
    measured = f"{record['measured_at']} · `{record['measured_at_commit']}`"
    if ar:
        out = [f"### التقدم: **{points} من 100 نقطة**", '', f"`{bar(points)}` {points}%", '',
               '| الخطوات المكتملة | الخطوة الحالية | النقاط الباقية | منها تنتظر مدخلًا منك | آخر قياس |', '|---|---|---|---|---|',
               f"| {done['milestones_done']} من {done['milestones']} | {now} | {round(100 - points, 1)} | {remaining_owner} | {measured} |"]
    else:
        out = [f"### Progress: **{points} of 100 points**", '', f"`{bar(points)}` {points}%", '',
               '| Steps done | Current step | Points left | Of which wait on the owner | Last measured |', '|---|---|---|---|---|',
               f"| {done['milestones_done']} of {done['milestones']} | {now} | {round(100 - points, 1)} | {remaining_owner} | {measured} |"]
    if record['measured_at_commit'].endswith('+'): out += ['', DIRTY[language]]
    return out


def method(language):
    if language == 'ar':
        return ['**كيف يُحسب:**', '',
                '- لكل خطوة **وزن** بالنقاط، مجموعها 100، ومكتوب سبب كل وزن.',
                f"- **إنجاز الخطوة** = متوسط إنجاز مهامها موزونًا بحجمها (S = {SIZE_POINTS['S']}، M = {SIZE_POINTS['M']}، L = {SIZE_POINTS['L']}). "
                f"المهمة المغلقة 100%. المفتوحة = تقدم مؤشراتها نحو حد بوابتها (القيمة ÷ الحد)، بسقف {round(OPEN_CAP * 100)}% حتى يمر أمر قبولها وتُغلق.",
                '- **نقاط الخطوة** = الوزن × الإنجاز. **التقدم** = مجموع نقاط الخطوات من 100.',
                '- **جودة المخرج** = متوسط (القيمة ÷ الحد) لمعايير بوابة الخطوة كما تُقاس اليوم على 3 مشاريع حقيقية.',
                '- **بوابة الانتقال:** لا تبدأ الخطوة التالية قبل أن تتحقق كل معايير بوابة الخطوة الحالية. '
                'و`python tools/north_star.py --check` يفشل إن أُغلقت خطوة قبل سابقتها، أو سقط معيار من بوابة خطوة مغلقة.']
    return ['**How it is computed:**', '',
            '- Every step has a **weight** in points, summing to 100, each with its stated reason.',
            f"- **Step completion** = the mean of its tasks weighted by size (S = {SIZE_POINTS['S']}, M = {SIZE_POINTS['M']}, L = {SIZE_POINTS['L']}). "
            f"A closed task is 100%. An open one counts its indicators' progress toward their gate thresholds (value ÷ threshold), capped at {round(OPEN_CAP * 100)}% until its acceptance command passes and it is closed.",
            '- **Step points** = weight × completion. **Progress** = the sum over all steps, out of 100.',
            '- **Output quality** = the mean of value ÷ threshold over the step\'s gate criteria, as measured today on 3 real projects.',
            '- **Transition gate:** the next step does not start until every criterion of the current step\'s gate holds. '
            '`python tools/north_star.py --check` fails when a step closes before the one before it, or a closed step\'s gate stops holding.']


def readme_block(record, name, language):
    ar = language == 'ar'
    out = [f'<!-- north-star:{name}:start -->', '<!-- ' + ('مولَّد من docs/north-star.json بالأمر python tools/north_star.py؛ لا تحرّره يدويًا'
                                                          if ar else 'generated from docs/north-star.json by python tools/north_star.py; do not edit by hand') + ' -->', '']
    if name == 'pipeline':
        out += [('كل صندوق مرحلة ومخرجها، وكل سهم بوابة: لا ينتقل العمل إلى المرحلة التالية إلا إذا تحققت معاييرها. '
                 'المراحل S01 إلى S07 تقرأ المشروع فقط وتنتهي بالتقارير الأربعة؛ S08 إلى S14 تشغّله في بيئة معزولة بتفويض مالكه.'
                 if ar else 'Each box is a stage and its output; each arrow is a gate: work moves on only when its criteria hold. '
                 'S01 to S07 only read the project and end with the four reports; S08 to S14 run it in isolation, with its owner\'s authorization.'), '']
        out += pipeline_chart(record, language)
    else:
        out += headline(record, language) + [''] + method(language)
        out += ['', ('الخطوات الخمس والعشرون بترتيب التنفيذ. على كل سهم بوابة الخطوة التي قبله. التفصيل الكامل لكل خطوة '
                     '(ماذا تفعل، وأدواتها، ومخرجها، وقيم بوابتها اليوم) في [docs/NORTH-STAR.md](docs/NORTH-STAR.md).'
                     if ar else 'The twenty-five steps in execution order; each arrow carries the gate of the step before it. '
                     'Every step in full (what it does, its tools, its output, and its gate values today) is in '
                     '[docs/NORTH-STAR.md](docs/NORTH-STAR.md) (Arabic).'), '']
        out += steps_chart(record, language) + ['', legend(language)]
    return '\n'.join(out + ['', f'<!-- north-star:{name}:end -->'])


def with_block(text, name, block):
    start, end = f'<!-- north-star:{name}:start -->', f'<!-- north-star:{name}:end -->'
    a, b = text.find(start), text.find(end)
    if a < 0 or b < 0: return None
    return text[:a] + block + text[b + len(end):]


def render(record, indicators_by_capability):
    done = completion(record)
    phase_of = {name: phase['id'] for phase in record.get('roadmap', []) for name in phase['milestones']}
    out = [f"# {record['title']}", '',
           '> مولَّد من `docs/north-star.json` — لا تحرّره يدويًا. أعد توليده بـ`python tools/north_star.py`.', '',
           '## أين نحن', ''] + headline(record, 'ar') + [''] + method('ar')
    out += ['', '## الخريطة: الخطوات الخمس والعشرون ومعايير الانتقال', '',
            'كل صندوق خطوة: وزنها بالنقاط ونسبة إنجازها. على كل سهم بوابة الخطوة التي قبله: المعايير التي يجب أن تتحقق قبل الانتقال.', '']
    out += steps_chart(record, 'ar') + ['', legend('ar')]
    out += ['', '## جدول الخطوات', '',
            '| # | الخطوة | الحزمة | الوزن | الإنجاز | النقاط | جودة المخرج | الحالة | بوابة الانتقال |',
            '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for sequence, milestone, state in done['rows']:
        measured = done['steps'][milestone['id']]
        out.append(f"| {sequence} | [**{milestone['id']}** {milestone['title']}](#step-{sequence}) | {phase_of.get(milestone['id'], '—')} | "
                   f"{milestone['weight']} | {pct(measured['completion'])} | {measured['points']:g} | {pct(measured['quality'])} | "
                   f"{STATE['ar'][state]} | {gate_text(measured['gate'], 'ar')} |")
    out.append(f"| | **المجموع** | | **100** | | **{done['points']}** | | | |")
    out += ['', '## الخطوات بالتفصيل']
    for sequence, milestone, state in done['rows']:
        measured = done['steps'][milestone['id']]
        open_needs = sorted({t['needs'] for t in milestone['tasks'] if t['status'] != 'done'} - {'none'})
        who = '، '.join(WAITS_ON['ar'][need] for need in open_needs)
        out += ['', f'<a id="step-{sequence}"></a>', '', f"### الخطوة {sequence} · {milestone['id']} — {milestone['title']} {STATE['ar'][state]}", '',
                '| الوزن | الإنجاز | النقاط | جودة المخرج | الحزمة | مراحل خط الإنتاج |', '| --- | --- | --- | --- | --- | --- |',
                f"| {milestone['weight']} | {pct(measured['completion'])} | {measured['points']:g} من {milestone['weight']} | {pct(measured['quality'])} | "
                f"{phase_of.get(milestone['id'], '—')} | {', '.join(milestone.get('stages') or []) or '—'} |", '',
                f"**الهدف:** {milestone['goal']}", '', f"**لماذا هذا الوزن:** {milestone['weight_why']}", '',
                '**ماذا تفعل:**', ''] + [f'{index}. {line}' for index, line in enumerate(milestone['does'], 1)]
        out += ['', '**الأدوات:** ' + ' · '.join(milestone['tools']), '',
                '**المخرج:** ' + ' · '.join(f'`{name}`' for name in milestone['outputs'])]
        if who: out += ['', f"**تحتاج منك قبل أن تكتمل:** {who}"]
        out += ['', '**بوابة الانتقال إلى الخطوة التالية** (تتحقق كلها، وإلا لا انتقال):', '',
                '| المعيار | الشرط | اليوم | الحال |', '| --- | --- | --- | --- |']
        out += [gate_row(item, 'ar') for item in measured['gate']]
        out += ['', '**المهام:**', '', '| المهمة | الحجم | الحالة | الإنجاز | أمر القبول |', '| --- | --- | --- | --- | --- |']
        for task in milestone['tasks']:
            out.append(f"| [{task['id']}](#{task['id'].lower().replace('.', '')}) {task['title']} | {task.get('size') or 'M'} | "
                       f"{MARK[task['status']]} | {pct(task_completion(task, record))} | `{task['acceptance'].replace('|', '¦')}` |")
    if record.get('pipeline'):
        out += ['', '## خط الإنتاج: المراحل الخمس عشرة التي يمر بها أي مشروع', '',
                'هذا خط المنتج نفسه، لا خطوات بنائه: ما يفعله EAOS بمشروعك. كل مرحلة «مبنية» بقدر الخطوات التي تخدمها.', '']
        out += pipeline_chart(record, 'ar')
        out += ['', '| # | المرحلة | العقد | السؤال | المخرج | البوابة | الخطوات التي تبنيها |', '| --- | --- | --- | --- | --- | --- | --- |']
        for stage in record['pipeline']:
            served = [m['id'] for m in record['milestones'] if stage['id'] in m.get('stages', [])]
            out.append(f"| {stage['id']} | **{stage['key']}** {stage['name']} | {stage['contract']} | {stage['question']} | "
                       f"{' · '.join(f'`{name}`' for name in stage['outputs'])} | {stage['gate']} | {', '.join(served)} |")
        out += ['', '### الأدوات في كل مرحلة', '', '**تقرأ:** يشغّلها EAOS ويقرأ مخرجها. **يولّد لها:** يكتب EAOS ملف إدخالها '
                'بصيغتها الأصلية وتقبله الأداة نفسها. **تُشغَّل:** في بيئة معزولة بتفويض. **يوصي:** تدخل الصورة المثالية للمشروع.', '',
                '| # | تقرأ | يولّد لها | تُشغَّل | يوصي |', '| --- | --- | --- | --- | --- |']
        for stage in record['pipeline']:
            tools = stage['tools']
            out.append(f"| {stage['id']} {stage['key']} | " + ' | '.join(', '.join(tools.get(role, [])) or '—'
                                                                   for role in ('read', 'emit', 'run', 'recommend')) + ' |')
    out += ['', '## ملحق أ: المؤشرات التي تقيس البوابات', '',
            'كل معيار في بوابة أي خطوة مؤشر من هذه المؤشرات، يُحسب بأمر من تقارير عيّنة المشاريع الحقيقية؛ والمؤشر غير المقيس لا يحقق أي شرط. '
            'المؤشرات مجمّعة في قدرات (C1 إلى C10) للقراءة فقط؛ التقدم يُحسب من الخطوات أعلاه، لا من القدرات.', '',
            f"**تعريف القيمة:** {record['scoring']['indicator']}"]
    for capability, rows in indicators_by_capability:
        out += ['', f"### {capability['id']} — {capability['name']}", '', f"**الصورة المثالية:** {capability['ideal']}", '',
                '| المؤشر | التعريف | الهدف | اليوم | الدليل |', '| --- | --- | --- | --- | --- |']
        out += [f"| {row['id']} {row['name']} | {row['definition']} | {pct(row['target'])} | {pct(row['value'])} | {row['evidence']} |" for row in rows]
    out += ['', '## ملحق ب: الرؤية', ''] + [f'- {line}' for line in record['vision']]
    out += ['', '## ملحق ج: تعريف «وصلنا»: ما يجب أن يسلّمه EAOS لأي مشروع', '']
    out += [f'{index}. {line}' for index, line in enumerate(record['definition_of_done'], 1)]
    out += ['', '## ملحق د: عيّنة القياس', '', 'مشاريع حقيقية مثبّتة بالتزامها. حقيقتها الأرضية مكتوبة في السجل.', '',
            '| المشروع | النوع | الالتزام |', '| --- | --- | --- |']
    out += [f"| [{row['name']}]({row['repo']}) | {row['stack']} | `{row['commit'][:10]}` |" for row in record['corpus']]
    out += [f"| هذا المستودع (حقيقة ذاتية: {len(record['self_truth']['defects'])} عيبًا معروفًا) | Python | "
            f"`{record['self_truth']['commit'][:10]}` |"]
    if record.get('live_corpus'):
        out += ['', '### المشاريع التي تُشغَّل (الخطوات 17 إلى 24)', '',
                'العيّنة أعلاه عامة: تُدقَّق ولا تُشغَّل، لأن أصحابها لم يفوّضوا تشغيلها. مؤشرات التشغيل (E1، E2، E5 إلى E11) '
                'تُحسب من هذه المشاريع وحدها، وكلها بتفويض مالكها، وفي البيئة المعزولة فقط.', '',
                '| المشروع | النوع | الالتزام | المالك | أساس التفويض |', '| --- | --- | --- | --- | --- |']
        out += [f"| {row['name']} | {row['stack']} | `{row['commit'][:10]}` | {row['owner']} | {row['authorization']} |"
                for row in record['live_corpus']]
    out += ['', '## ملحق هـ: كل مهمة بتفاصيلها', '', 'كل مهمة لها أمر قبول يفشل قبلها وينجح حين تكتمل. '
            'المهمة المنجزة تحمل في خطواتها ما نُفّذ فعلًا («كما نُفّذ»).']
    for sequence, milestone, state in done['rows']:
        out += ['', f"### الخطوة {sequence} · {milestone['id']} — {milestone['title']} {STATE['ar'][state]}"]
        for task in milestone['tasks']:
            out += ['', f'<a id="{task['id'].lower().replace('.', '')}"></a>', '', f"#### {task['id']} — {task['title']} {MARK[task['status']]}", '']
            if task.get('why'): out += [f"**لماذا:** {task['why']}", '']
            out += [f"**يحرّك:** {', '.join(task['moves']) or '—'} · **ينفّذه:** {NEEDS[task['needs']]}"
                    + (f" · **يعتمد على:** {', '.join(task['depends_on'])}" if task['depends_on'] else '')
                    + (f" · **الحجم:** {task['size']}" if task.get('size') else ''), '',
                    '**الملفات:** ' + ' · '.join(f'`{name}`' for name in task['files'])]
            if task.get('writes'):
                out += ['', '**يكتب:** ' + ' · '.join(
                    f"`{item}` (العقد: `schemas/artifacts/{item[9:]}.schema.json`)" if item.startswith('contract:') else f'`{item}`'
                    for item in task['writes'])]
            out += ['', '**الخطوات:**', ''] + [f'{index}. {line}' for index, line in enumerate(task['steps'], 1)]
            if task.get('done_when'):
                out += ['', '**تنتهي حين:**', ''] + [f'- [ ] {item}' for item in task['done_when']]
            if task.get('pitfalls'):
                out += ['', '**فخاخ معروفة:**', ''] + [f'- {item}' for item in task['pitfalls']]
            out += ['', '**أمر القبول:**', '', '```bash', task['acceptance'], '```', '', f"**التراجع:** {task['rollback']}"]
    out += ['', '## قواعد التطوير نحو الوجهة', ''] + [f'{index}. {rule}' for index, rule in enumerate(record['rules'], 1)]
    return '\n'.join(out).rstrip() + '\n'
