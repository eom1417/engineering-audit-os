"""Render docs/NORTH-STAR.md from docs/north-star.json, and say how far the product is from its destination.

The JSON is the only source. An indicator with no value counts as zero: a capability is not partly
there because its machinery exists, only because its output on the corpus got better.

Usage:  python tools/north_star.py                       # write docs/NORTH-STAR.md
        python tools/north_star.py --check               # fail if the record is invalid or the document is stale
        python tools/north_star.py --score               # print the scores as JSON
        python tools/north_star.py fetch                 # clone the pinned corpus
        python tools/north_star.py measure               # audit the corpus, write every automated value
        python tools/north_star.py measure --only U2 --min 0.9   # check one indicator; writes nothing
        python tools/north_star.py --no-regression       # fail if an indicator fell below its best
        python tools/north_star.py --finished            # exit 0 only when every task is done and every indicator is at its target
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
SOURCE = ROOT / 'docs/north-star.json'
TARGET = ROOT / 'docs/NORTH-STAR.md'
READMES = {'ar': ROOT / 'README.md', 'en': ROOT / 'README.en.md'}
BLOCK = ('<!-- north-star:start -->', '<!-- north-star:end -->')
GENERATED = {'docs/north-star.json', 'docs/NORTH-STAR.md', 'docs/north-star-high-water.json', 'README.md', 'README.en.md'}
DIRTY_AR = ' (`+`: على تغييرات فوق هذا الالتزام تُحفظ في الالتزام التالي)'
DIRTY_EN = ' (`+`: on changes over this commit, saved in the next one)'
HIGH_WATER = ROOT / 'docs/north-star-high-water.json'
TOLERANCE = 0.02
MARK = {'todo': '⬜', 'done': '✅', 'blocked': '⛔'}
SIZES = ('S', 'M', 'L')
# The acceptance of a task still to do is owned by the planner: the measurement, or a check under
# tools/acceptance.py. A unit test the executor writes itself can be written to pass, so it never suffices.
OWNED_ACCEPTANCE = ('tools/north_star.py measure', 'tools/acceptance.py')
NEEDS = {'none': 'نموذج أو مطوّر', 'model_provider': 'يحتاج مزوّد نموذج', 'human': 'يحتاج إنسانًا من خارج المشروع',
         'sandbox': 'يحتاج بيئة معزولة وتفويضًا لتشغيل كود المشروع'}


def indicators(record):
    return [row for capability in record['capabilities'] for row in capability['indicators']]


def tasks(record):
    return [task for milestone in record['milestones'] for task in milestone['tasks']]


def validate(record):
    problems = []
    if sum(capability['weight'] for capability in record['capabilities']) != 100:
        problems.append('capability weights must sum to 100')
    known = set()
    for row in indicators(record):
        if row['id'] in known: problems.append(f"{row['id']}: declared twice")
        known.add(row['id'])
        for field in ('name', 'definition', 'evidence'):
            if not str(row.get(field) or '').strip(): problems.append(f"{row['id']}: no {field}")
        value = row.get('value')
        if value is not None and not 0 <= value <= 1: problems.append(f"{row['id']}: value {value} outside 0..1")
    order = [task['id'] for task in tasks(record)]
    for task in tasks(record):
        for field in ('acceptance', 'rollback'):
            if not str(task.get(field) or '').strip(): problems.append(f"{task['id']}: no {field}")
        if not task.get('files') or not task.get('steps'): problems.append(f"{task['id']}: names no files or steps")
        if task.get('needs') not in NEEDS: problems.append(f"{task['id']}: needs must be one of {sorted(NEEDS)}")
        if task.get('status') not in MARK: problems.append(f"{task['id']}: status must be one of {sorted(MARK)}")
        for moved in task.get('moves', []):
            if moved not in known: problems.append(f"{task['id']}: moves unknown indicator {moved}")
        for reference in task.get('depends_on', []):
            if reference not in order: problems.append(f"{task['id']}: depends on unknown task {reference}")
            elif order.index(reference) > order.index(task['id']): problems.append(f"{task['id']}: listed before {reference}")
    problems += card_problems(record, known)
    # The pipeline and the roadmap are the plan's two axes: every stage is served by a milestone, and every
    # milestone sits in exactly one phase, listed in phase order, so reading the record top-down is executing it.
    stages = [stage['id'] for stage in record.get('pipeline', [])]
    milestones = [milestone['id'] for milestone in record['milestones']]
    for item in record['milestones'] + record.get('roadmap', []):
        if not str(item.get('title_en') or '').strip(): problems.append(f"{item['id']}: no title_en (the READMEs are bilingual)")
    for milestone in record['milestones']:
        for stage in milestone.get('stages', []):
            if stage not in stages: problems.append(f"{milestone['id']}: unknown stage {stage}")
    for stage in stages:
        if not any(stage in milestone.get('stages', []) for milestone in record['milestones']):
            problems.append(f'{stage}: no milestone serves this stage')
    placed = [name for phase in record.get('roadmap', []) for name in phase['milestones']]
    if record.get('roadmap'):
        for name in milestones:
            if placed.count(name) != 1: problems.append(f'{name}: must appear in exactly one roadmap phase')
        if [name for name in placed if name in milestones] != milestones:
            problems.append('milestones must be listed in roadmap phase order')
    return problems


def card_problems(record, known):
    """A task still to do must be executable by any model: why, what it writes, when it is done, what trips it."""
    import sys as _sys
    _sys.path.insert(0, str(ROOT / 'tools'))
    from contracts import contracts
    names, problems = set(contracts()), []
    open_tasks = [task for task in tasks(record) if task['status'] != 'done']
    for task in open_tasks:
        where = task['id']
        if not str(task.get('why') or '').strip(): problems.append(f'{where}: no why')
        if task.get('size') not in SIZES: problems.append(f'{where}: size must be one of {SIZES}')
        if not task.get('done_when'): problems.append(f'{where}: no done_when checklist')
        if not isinstance(task.get('pitfalls'), list): problems.append(f'{where}: pitfalls must be a list')
        if not isinstance(task.get('writes'), list): problems.append(f'{where}: writes must be a list')
        for item in task.get('writes') or []:
            if item.startswith('contract:') and item[len('contract:'):] not in names:
                problems.append(f'{where}: writes unknown contract {item}')
        if not any(owned in task['acceptance'] for owned in OWNED_ACCEPTANCE):
            problems.append(f'{where}: acceptance must run the measurement or tools/acceptance.py, not only a test the executor writes')
        for name in re.findall(r'tools/acceptance\.py test (\w+)', task['acceptance']):
            if not (ROOT / f'acceptance/test_{name}.py').is_file(): problems.append(f'{where}: acceptance/test_{name}.py does not exist')
    # Every indicator short of its target must have a task that moves it, or the plan cannot end.
    moving = {moved for task in open_tasks for moved in task['moves']}
    for row in indicators(record):
        if (row.get('value') or 0) < row['target'] and row['id'] not in moving:
            problems.append(f"{row['id']}: below its target and no open task moves it")
    if (ROOT / 'acceptance').is_dir():
        from acceptance import digests, LOCK
        recorded = json.loads(LOCK.read_text(encoding='utf-8')) if LOCK.is_file() else {}
        if digests() != recorded: problems.append('acceptance/ differs from acceptance/LOCK.json: only the planner changes acceptance tests')
    return problems


def remaining(record):
    """What stands between the record and the destination: open tasks and indicators short of their target."""
    open_tasks = [f"{task['id']} {task['title']} ({task['status']}, {NEEDS[task['needs']]})" for task in tasks(record) if task['status'] != 'done']
    short = [f"{row['id']} {row['name']}: {percent(row.get('value'))} < {percent(row['target'])}"
             for row in indicators(record) if (row.get('value') or 0) < row['target']]
    return open_tasks, short


def score(record):
    """Capability = mean of its indicators, unmeasured as zero; overall = weighted mean, in percent."""
    capabilities = {}
    for capability in record['capabilities']:
        values = [row['value'] or 0 for row in capability['indicators']]
        capabilities[capability['id']] = round(sum(values) / len(values), 3)
    overall = sum(capability['weight'] * capabilities[capability['id']] for capability in record['capabilities'])
    return {'overall_percent': round(overall, 1), 'capabilities': capabilities}


def gaps(record, scores):
    """Where the remaining distance is, largest first: weight times what the capability still lacks."""
    rows = [(round(capability['weight'] * (1 - scores['capabilities'][capability['id']]), 1), capability)
            for capability in record['capabilities']]
    return sorted(rows, key=lambda pair: -pair[0])


def progress(record):
    """[(sequence, milestone, state)] in execution order (roadmap order). A milestone is done when every task is;
    the first one not done is current; after it, one whose tasks need a sandbox, a model or an outside person
    waits on the owner, and the rest are next."""
    order = [name for phase in record.get('roadmap', []) for name in phase['milestones']] or [m['id'] for m in record['milestones']]
    by_id = {milestone['id']: milestone for milestone in record['milestones']}
    rows, current = [], False
    for sequence, name in enumerate(order, 1):
        milestone = by_id[name]
        if all(task['status'] == 'done' for task in milestone['tasks']): state = 'done'
        elif not current: state, current = 'current', True
        elif any(task['needs'] != 'none' for task in milestone['tasks'] if task['status'] != 'done'): state = 'owner'
        else: state = 'next'
        rows.append((sequence, milestone, state))
    return rows


def completion(record):
    """The progress a reader follows: milestones closed, tasks done, the current one, and who each open one waits on.
    A milestone closes only when every task in it passed its acceptance command; nothing here is estimated."""
    rows = progress(record)
    all_tasks = tasks(record)
    done = sum(state == 'done' for _, _, state in rows)
    return {'rows': rows, 'milestones_done': done, 'milestones': len(rows),
            'milestones_percent': round(100 * done / len(rows), 1) if rows else 0.0,
            'tasks_done': sum(task['status'] == 'done' for task in all_tasks), 'tasks': len(all_tasks),
            'current': next(((sequence, milestone) for sequence, milestone, state in rows if state == 'current'), None),
            'owner': [(sequence, milestone) for sequence, milestone, state in rows if state == 'owner']}


def summary_line(record):
    done = completion(record)
    return (f"progress: {done['milestones_done']}/{done['milestones']} milestones ({done['milestones_percent']}%), "
            f"{done['tasks_done']}/{done['tasks']} tasks; measured output quality {score(record)['overall_percent']}%")


def bar(percent, width=25):
    filled = round(width * percent / 100)
    return '█' * filled + '░' * (width - filled)


STATE_AR = {'done': '✅ مكتمل', 'current': '🟡 قيد العمل', 'next': '⬜ التالي', 'owner': '🔴 يحتاج مدخلًا منك'}
STATE_EN = {'done': '✅ done', 'current': '🟡 in progress', 'next': '⬜ next', 'owner': '🔴 needs owner input'}
WAITS_ON = {'sandbox': 'بيئة معزولة وتفويض بتشغيل كود المشروع', 'model_provider': 'مزوّد نموذج (مفتاح API)',
            'human': 'مراجع بشري من خارج المشروع'}


def stage_state(record, stage_id, states):
    """A pipeline stage is built when every milestone serving it is done, and under way when some are."""
    serving = [states[m['id']] for m in record['milestones'] if stage_id in m.get('stages', [])]
    if serving and all(state == 'done' for state in serving): return 'done'
    return 'current' if any(state in ('done', 'current') for state in serving) else 'next'


def short_ar(title):
    return title.split(':')[0].split('،')[0].strip()


def label(*lines):
    return '"' + '<br/>'.join(line.replace('"', "'") for line in lines) + '"'


STYLE = ['    classDef done fill:#dcfce7,stroke:#15803d,color:#14532d,stroke-width:2px',
         '    classDef current fill:#fef9c3,stroke:#ca8a04,color:#713f12,stroke-width:3px',
         '    classDef next fill:#f1f5f9,stroke:#64748b,color:#1e293b',
         '    classDef owner fill:#fee2e2,stroke:#b91c1c,color:#7f1d1d,stroke-dasharray:5 3']
LEGEND = {'ar': {'done': '✅ مكتمل', 'current': '🟡 قيد العمل الآن (المرحلة في خط الإنتاج: مبنية جزئيًا)', 'next': '⬜ التالي، ينفّذه نموذج أو مطوّر',
                 'owner': '🔴 يحتاج مدخلًا من المالك (بيئة معزولة وتفويض، أو مزوّد نموذج، أو مراجع بشري)'},
          'en': {'done': '✅ done', 'current': '🟡 in progress now (a pipeline stage: partly built)', 'next': '⬜ next, doable by a model or a developer',
                 'owner': '🔴 needs owner input (a sandbox and authorization, a model provider, or a human reviewer)'}}


def pipeline_chart(record, states):
    """The fifteen stages, bilingual, grouped by contract: assessment reads only; execution runs in isolation."""
    groups = [('ASSESS', 'التقييم: قراءة فقط · Assessment: read-only', lambda s: s['id'] <= 'S07'),
              ('EXECUTE', 'التنفيذ: عزل وتفويض · Execution: isolated, authorized', lambda s: 'S08' <= s['id'] <= 'S14'),
              ('GOVERN', 'الحوكمة والتسليم · Governance and handover', lambda s: s['id'] == 'S15')]
    out = ['```mermaid', 'flowchart TB']
    for key, title, member in groups:
        stages = [stage for stage in record['pipeline'] if member(stage)]
        out += [f'    subgraph {key}[{label(title)}]', '        direction LR']
        for stage in stages:
            out.append(f"        {stage['id']}[{label(stage['id'] + ' · ' + stage['key'], stage['name'])}]:::{stage_state(record, stage['id'], states)}")
        out.append('        ' + ' --> '.join(stage['id'] for stage in stages) if len(stages) > 1 else '')
        out.append('    end')
    out += ['    ASSESS ==>|' + label('تفويض المالك · owner authorization')[1:-1].replace('<br/>', ' ') + '| EXECUTE',
            '    EXECUTE ==> GOVERN',
            # a back edge would pull GOVERN above ASSESS; the loop is said in the last box instead
            f"    LOOP[{label('↺ إعادة التدقيق بعد كل تغيير', 're-audit after every change')}]:::next", '    GOVERN -.-> LOOP'] + STYLE + ['```']
    return [line for line in out if line.strip()]


def roadmap_chart(record, rows):
    """The twenty-five milestones in execution order, one box per roadmap phase, coloured by state."""
    phase_of = {name: phase for phase in record['roadmap'] for name in phase['milestones']}
    out = ['```mermaid', 'flowchart TB']
    previous = None
    for phase in record['roadmap']:
        members = [(sequence, milestone, state) for sequence, milestone, state in rows if phase_of[milestone['id']] is phase]
        out += [f"    subgraph {phase['id']}[{label(phase['id'] + ' · ' + phase['title'], phase['title_en'])}]", '        direction LR']
        for sequence, milestone, state in members:
            out.append(f"        {milestone['id']}[{label(f'{sequence} · ' + milestone['id'], short_ar(milestone['title']), milestone['title_en'].split(':')[0])}]:::{state}")
        if len(members) > 1: out.append('        ' + ' --> '.join(milestone['id'] for _, milestone, _ in members))
        out.append('    end')
        if previous: out.append(f"    {previous} --> {phase['id']}")
        previous = phase['id']
    return out + STYLE + ['```']


def readme_block(record, language):
    """The status block both READMEs carry: generated, so it cannot drift from the record."""
    rows = progress(record)
    states = {milestone['id']: state for _, milestone, state in rows}
    done = sum(state == 'done' for _, _, state in rows)
    current = next(((sequence, milestone) for sequence, milestone, state in rows if state == 'current'), None)
    scores = score(record)
    owner = [f"{sequence} {milestone['id']}" for sequence, milestone, state in rows if state == 'owner']
    ar = language == 'ar'
    now = ('—' if current is None else
           f"{current[0]} · {current[1]['id']} — {current[1]['title'] if ar else current[1]['title_en']}")
    out = [BLOCK[0], '<!-- ' + ('مولَّد من docs/north-star.json بالأمر python tools/north_star.py؛ لا تحرّره يدويًا'
                                if ar else 'generated from docs/north-star.json by python tools/north_star.py; do not edit by hand') + ' -->', '']
    pct = round(100 * done / len(rows), 1) if rows else 0.0
    if ar:
        out += [f"### التقدم الفعلي: **{done} من {len(rows)} معلمًا ({pct}%)**", '', f"`{bar(pct)}` {pct}%", '',
                '| المعلم الحالي | جودة المخرج المقيسة (ليست نسبة إنجاز) | آخر قياس |', '|---|---|---|',
                f"| {now} | {scores['overall_percent']}% | {record['measured_at']} · `{record['measured_at_commit']}` |", '',
                '> **رقم التقدم هو عدد المعالم المكتملة.** المعلم لا يُحسب إلا حين تمر أوامر قبول كل مهامه، والمنتج مكتمل عند '
                f"{len(rows)} من {len(rows)}. أما «جودة المخرج» فتقيس جودة ما يسلّمه الجزء المبني حتى الآن على 3 مشاريع حقيقية "
                '(54 مؤشرًا على 10 قدرات)، وترتفع أسرع لأن أول المعالم بنت القدرات الأثقل وزنًا. '
                'التفصيل الكامل، معلمًا معلمًا ومهمة مهمة، في [docs/NORTH-STAR.md](docs/NORTH-STAR.md).']
    else:
        out += [f"### Actual progress: **{done} of {len(rows)} milestones ({pct}%)**", '', f"`{bar(pct)}` {pct}%", '',
                '| Current milestone | Measured output quality (not a completion rate) | Last measured |', '|---|---|---|',
                f"| {now} | {scores['overall_percent']}% | {record['measured_at']} · `{record['measured_at_commit']}` |", '',
                '> **Progress is the number of closed milestones.** A milestone counts only when every task in it passed its '
                f"acceptance command, and the product is complete at {len(rows)} of {len(rows)}. \"Output quality\" measures what "
                'the part built so far delivers on 3 real projects (54 indicators across 10 capabilities); it rises faster because the '
                'first milestones built the heaviest capabilities. Every milestone and task is detailed in '
                '[docs/NORTH-STAR.md](docs/NORTH-STAR.md) (Arabic).']
    if record['measured_at_commit'].endswith('+'): out += ['', (DIRTY_AR if ar else DIRTY_EN).strip()]
    if owner:
        out += ['', ('**تحتاج مدخلًا من المالك قبل أن تكتمل:** ' if ar else '**Need owner input before they can close:** ') + ', '.join(owner)]
    out += ['', '### ' + ('خط الإنتاج: المراحل الخمس عشرة' if ar else 'The pipeline: fifteen stages'), '',
            ('كل مرحلة تمر ببوابتها قبل التي تليها. المراحل S01 إلى S07 تقرأ المشروع فقط وتنتهي بالتقارير الأربعة؛ '
             'المراحل S08 إلى S14 تشغّل كود المشروع في بيئة معزولة، ولا تبدأ إلا بتفويض مالكه.' if ar else
             'Each stage passes its gate before the next begins. S01 to S07 only read the project and end with the four reports; '
             'S08 to S14 run the project\'s code in an isolated environment, and start only with its owner\'s authorization.'), '']
    out += pipeline_chart(record, states)
    out += ['', '### ' + ('خارطة الطريق: المعالم الخمسة والعشرون بترتيب التنفيذ' if ar else 'The roadmap: twenty-five milestones in execution order'), '']
    out += roadmap_chart(record, rows)
    out += ['', ' · '.join(LEGEND[language][state] for state in ('done', 'current', 'next', 'owner')), '', BLOCK[1]]
    return '\n'.join(out)


def with_block(text, block):
    start, end = text.find(BLOCK[0]), text.find(BLOCK[1])
    if start < 0 or end < 0: return None
    return text[:start] + block + text[end + len(BLOCK[1]):]


def percent(value):
    return '—' if value is None else f'{round(value * 100)}%'


def render(record):
    scores = score(record)
    done = completion(record)
    phase_of = {name: phase['id'] for phase in record.get('roadmap', []) for name in phase['milestones']}
    out = [f"# {record['title']}", '',
           '> مولَّد من `docs/north-star.json` — لا تحرّره يدويًا. أعد توليده بـ`python tools/north_star.py`. '
           f"آخر قياس: {record['measured_at']} على الالتزام `{record['measured_at_commit']}`"
           f"{DIRTY_AR if record['measured_at_commit'].endswith('+') else ''}.", '',
           f"## التقدم الفعلي: **{done['milestones_done']} من {done['milestones']} معلمًا ({done['milestones_percent']}%)**", '',
           f"`{bar(done['milestones_percent'])}` {done['milestones_percent']}%", '',
           'هذا هو رقم التقدم الذي يُتابَع. المعلم لا يُحسب مكتملًا إلا حين تمر أوامر قبول كل مهامه؛ لا تقدير ولا نسبة جزئية. '
           'المنتج مكتمل عند 25 من 25 مع بلوغ كل مؤشر هدفه (`python tools/north_star.py --finished`).', '',
           '| المقياس | القيمة | ماذا يعني |', '| --- | --- | --- |',
           f"| **المعالم المكتملة** | **{done['milestones_done']} / {done['milestones']}** ({done['milestones_percent']}%) | "
           'رقم التقدم الرسمي. كل معلم أُغلق بأوامر قبول مرّت. |',
           f"| المهام المنجزة | {done['tasks_done']} / {done['tasks']} ({round(100 * done['tasks_done'] / done['tasks'])}%) | "
           'المهام أحجامها مختلفة، فهذا الرقم للاستئناس لا للحكم. |',
           f"| المعلم الحالي | {'—' if done['current'] is None else str(done['current'][0]) + ' · ' + done['current'][1]['id'] + ' ' + done['current'][1]['title']} | "
           + ('' if done['current'] is None else
              f"{sum(t['status'] == 'done' for t in done['current'][1]['tasks'])} من {len(done['current'][1]['tasks'])} مهام أُغلقت فيه.") + ' |',
           f"| تنتظر مدخلًا منك | {len(done['owner'])} معالم | لا تكتمل مهما اكتمل الكود حتى يتوفر ما تحتاجه (العمود «ينفّذه أو يحتاج» أدناه). |",
           f"| جودة المخرج المقيسة | {scores['overall_percent']}% | **ليست نسبة إنجاز.** تقيس جودة ما يسلّمه الجزء المبني حتى الآن "
           'على 3 مشاريع حقيقية، بـ54 مؤشرًا موزونة على 10 قدرات (التفصيل أدناه). ترتفع أسرع من المعالم لأن أول المعالم بنت القدرات '
           'الأثقل وزنًا؛ ولا تصل إلى 100% إلا بإغلاق المعالم كلها. |', '',
           '## المعالم الخمسة والعشرون بترتيب التنفيذ', '',
           'يُنفَّذ المعلم بعد اكتمال الذي قبله. التفصيل الكامل لكل مهمة (الخطوات، والملفات، وأمر القبول، والتراجع، وما نُفّذ فعلًا) '
           'في قسم «خطة التحول» أسفل الملف.', '',
           '| # | المعلم | الحزمة | الحالة | المهام | المراحل | ينفّذه أو يحتاج |', '| --- | --- | --- | --- | --- | --- | --- |']
    for sequence, milestone, state in done['rows']:
        open_needs = sorted({t['needs'] for t in milestone['tasks'] if t['status'] != 'done'} - {'none'})
        who = '، '.join(WAITS_ON[need] for need in open_needs) or ('—' if state == 'done' else 'نموذج أو مطوّر')
        out.append(f"| {sequence} | **{milestone['id']}** {milestone['title']} | {phase_of.get(milestone['id'], '—')} | {STATE_AR[state]} | "
                   f"{sum(t['status'] == 'done' for t in milestone['tasks'])}/{len(milestone['tasks'])} | "
                   f"{', '.join(milestone.get('stages') or []) or '—'} | {who} |")
    out += ['', f"## جودة المخرج المقيسة: {scores['overall_percent']}% (ليست نسبة إنجاز)", '',
            'ما يسلّمه EAOS اليوم على عيّنة المشاريع الحقيقية، لكل قدرة درجة هي متوسط مؤشراتها، والمؤشر غير المقيس يُحسب صفرًا. '
            'القدرتان C9 وC10 لا ترتفعان إلا بالتنفيذ الفعلي والمراجع المستقل (المعالم 17 إلى 25).', '',
           record['scoring']['not_this'], '',
           '| # | القدرة | الوزن | الدرجة | المساهمة |', '| --- | --- | --- | --- | --- |']
    for capability in record['capabilities']:
        value = scores['capabilities'][capability['id']]
        out.append(f"| {capability['id']} | {capability['name']} | {capability['weight']} | {percent(value)} | "
                   f"{round(capability['weight'] * value, 1)} |")
    out += [f"| | **المجموع** | **100** | | **{scores['overall_percent']}** |", '',
            '## الرؤية', ''] + [f'- {line}' for line in record['vision']]
    out += ['', '## تعريف «وصلنا»: ما يجب أن يسلّمه EAOS لأي مشروع', '']
    out += [f'{index}. {line}' for index, line in enumerate(record['definition_of_done'], 1)]
    if record.get('pipeline'):
        out += ['', '## خط الإنتاج: المراحل بالتسلسل', '', 'لا تبدأ مرحلة قبل أن تمر بوابة سابقتها. '
                'التفصيل الكامل لكل مرحلة وأداة في `docs/MASTER-BLUEPRINT.md` و`docs/TOOLCHAIN.md`.', '',
                '| # | المرحلة | العقد | السؤال | المخرج | البوابة | المعالم |', '| --- | --- | --- | --- | --- | --- | --- |']
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
    out += ['', '## أين تنقص جودة المخرج', '', 'مرتبة بـ الوزن × (1 − الدرجة): أين يرفع العمل جودة المخرج أكثر.', '',
            '| القدرة | الفجوة المرجّحة |', '| --- | --- |']
    out += [f"| {capability['id']} {capability['name']} | {gap} |" for gap, capability in gaps(record, scores)]
    out += ['', '## القدرات ومؤشراتها', '', f"**طريقة الحساب:** {record['scoring']['indicator']} "
            f"{record['scoring']['capability']} {record['scoring']['overall']}"]
    for capability in record['capabilities']:
        out += ['', f"### {capability['id']} — {capability['name']} ({percent(scores['capabilities'][capability['id']])}، الوزن {capability['weight']})",
                '', f"**الصورة المثالية:** {capability['ideal']}", '',
                '| المؤشر | التعريف | الهدف | اليوم | الدليل |', '| --- | --- | --- | --- | --- |']
        for row in capability['indicators']:
            out.append(f"| {row['id']} {row['name']} | {row['definition']} | {percent(row['target'])} | "
                       f"{percent(row['value'])} | {row['evidence']} |")
    out += ['', '## عيّنة القياس', '', 'مشاريع حقيقية مثبّتة بالتزامها. حقيقتها الأرضية مكتوبة في السجل.', '',
            '| المشروع | النوع | الالتزام |', '| --- | --- | --- |']
    out += [f"| [{row['name']}]({row['repo']}) | {row['stack']} | `{row['commit'][:10]}` |" for row in record['corpus']]
    out += [f"| هذا المستودع (حقيقة ذاتية: {len(record['self_truth']['defects'])} عيبًا معروفًا) | Python | "
            f"`{record['self_truth']['commit'][:10]}` |"]
    if record.get('roadmap'):
        by_id = {milestone['id']: milestone for milestone in record['milestones']}
        out += ['', '## خارطة الطريق: المراحل التنفيذية حتى الوجهة', '',
                'تُنفَّذ بالترتيب. لا تبدأ مرحلة تنفيذية قبل أن يتحقق شرط خروج سابقتها.', '',
                '| المرحلة | العنوان | المعالم | المنجز | شرط الخروج |', '| --- | --- | --- | --- | --- |']
        for phase in record['roadmap']:
            owned = [task for name in phase['milestones'] for task in by_id[name]['tasks']]
            out.append(f"| {phase['id']} | {phase['title']} | {', '.join(phase['milestones'])} | "
                       f"{sum(t['status'] == 'done' for t in owned)}/{len(owned)} | {phase['exit']} |")
    out += ['', '## خطة التحول: كل معلم بمهامه', '', 'كل مهمة لها أمر قبول يفشل قبلها وينجح حين تكتمل. '
            'المهمة المنجزة تحمل في خطواتها ما نُفّذ فعلًا («كما نُفّذ»).']
    states = {milestone['id']: state for _, milestone, state in done['rows']}
    for milestone in record['milestones']:
        out += ['', f"### {milestone['id']} — {milestone['title']} {STATE_AR[states[milestone['id']]]}", '', f"**الهدف:** {milestone['goal']}"
                + (f" · **المراحل:** {', '.join(milestone['stages'])}" if milestone.get('stages') else '')]
        for task in milestone['tasks']:
            out += ['', f"#### {task['id']} — {task['title']} {MARK[task['status']]}", '']
            if task.get('why'): out += [f"**لماذا:** {task['why']}", '']
            out += [f"**يحرّك:** {', '.join(task['moves']) or '—'} · **ينفّذه:** {NEEDS[task['needs']]}"
                    + (f" · **يعتمد على:** {', '.join(task['depends_on'])}" if task['depends_on'] else '')
                    + (f" · **الحجم:** {task['size']}" if task.get('size') else ''), '',
                    '**الملفات:** ' + ' · '.join(f'`{name}`' for name in task['files'])]
            if task.get('writes'):
                out += ['', '**يكتب:** ' + ' · '.join(
                    f"`{item}` (العقد: `schemas/artifacts/{item[9:]}.schema.json`)" if item.startswith('contract:') else f'`{item}`'
                    for item in task['writes'])]
            out += ['', '**الخطوات:**', ''] + [f'{index}. {step}' for index, step in enumerate(task['steps'], 1)]
            if task.get('done_when'):
                out += ['', '**تنتهي حين:**', ''] + [f'- [ ] {item}' for item in task['done_when']]
            if task.get('pitfalls'):
                out += ['', '**فخاخ معروفة:**', ''] + [f'- {item}' for item in task['pitfalls']]
            out += ['', '**أمر القبول:**', '', '```bash', task['acceptance'], '```', '', f"**التراجع:** {task['rollback']}"]
    out += ['', '## قواعد التطوير نحو الوجهة', ''] + [f'{index}. {rule}' for index, rule in enumerate(record['rules'], 1)]
    return '\n'.join(out).rstrip() + '\n'


def measured(record, values):
    """Write each measured value and its evidence into the record; recorded-only indicators are left as they are."""
    import subprocess
    for row in indicators(record):
        if row['id'] in values and values[row['id']][0] is not None:
            row['value'], row['evidence'] = values[row['id']]
            row['measured'] = 'automated'
        else:
            row.setdefault('measured', 'recorded')
    import datetime
    record['measured_at'] = datetime.date.today().isoformat()
    record['measured_at_commit'] = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT,
                                                  capture_output=True, text=True).stdout.strip()
    # Measured on changes not yet committed: the commit alone would claim the numbers for code it does not hold.
    if [line for line in subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
            if line[3:].strip() not in GENERATED]:
        record['measured_at_commit'] += '+'
    return record


def raise_high_water(record):
    """Record the best value each indicator has reached. The file is only ever written upward."""
    best = json.loads(HIGH_WATER.read_text(encoding='utf-8')) if HIGH_WATER.is_file() else {'indicators': {}, 'reached_at': {}}
    for row in indicators(record):
        if row.get('value') is not None and row['value'] > best['indicators'].get(row['id'], -1):
            best['indicators'][row['id']] = row['value']
            best['reached_at'][row['id']] = record['measured_at_commit']
    HIGH_WATER.write_text(json.dumps(best, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def regressions(record):
    """Indicators now below the best they ever reached, by more than the tolerance."""
    if not HIGH_WATER.is_file(): return []
    best = json.loads(HIGH_WATER.read_text(encoding='utf-8'))['indicators']
    return [f"{row['id']}: {row.get('value')} < {best[row['id']]}" for row in indicators(record)
            if row['id'] in best and (row.get('value') or 0) < best[row['id']] - TOLERANCE]


def main(argv):
    record = json.loads(SOURCE.read_text(encoding='utf-8'))
    command = argv[0] if argv and not argv[0].startswith('--') else None
    options = argv[1:] if command else argv
    if command not in (None, 'fetch', 'measure') or any(o not in ('--check', '--score', '--only', '--min', '--no-regression', '--finished') and
                                                         not (i and options[i - 1] in ('--only', '--min'))
                                                         for i, o in enumerate(options)):
        print(f"unknown command: {' '.join(argv)}", file=sys.stderr)
        return 2
    problems = validate(record)
    if problems:
        for problem in problems: print(problem, file=sys.stderr)
        return 1
    if command == 'fetch':
        from north_star_measure import fetch
        fetch(record)
        return 0
    if command == 'measure':
        from north_star_measure import measure
        only = options[options.index('--only') + 1] if '--only' in options else None
        if only is not None and only not in {row['id'] for row in indicators(record)}:
            print(f'unknown indicator {only}', file=sys.stderr)
            return 2
        values = measure(record, only)
        if only is None:
            SOURCE.write_text(json.dumps(measured(record, values), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            TARGET.write_text(render(record), encoding='utf-8')
            fallen = regressions(record)
            if fallen:
                for line in fallen: print('REGRESSION ' + line, file=sys.stderr)
                return 1
            raise_high_water(record)
            for key in sorted(values): print(f'{key:3} {values[key][0]!s:6} {values[key][1]}')
            print(summary_line(record))
            return 0
        # An indicator recorded by hand (a human review, for instance) is read from the record, not re-measured.
        recorded = next((row['value'], row['evidence']) for row in indicators(record) if row['id'] == only)
        value, evidence = values.get(only) or recorded
        floor = float(options[options.index('--min') + 1]) if '--min' in options else None
        print(f'{only} {value} (min {floor}) · {evidence}')
        return 0 if value is not None and (floor is None or value >= floor) else 1
    if '--no-regression' in options:
        fallen = regressions(record)
        for line in fallen: print('REGRESSION ' + line, file=sys.stderr)
        if not fallen: print('no indicator fell below its high-water mark')
        return 1 if fallen else 0
    if '--finished' in options:
        open_tasks, short = remaining(record)
        for line in open_tasks: print('OPEN  ' + line)
        for line in short: print('SHORT ' + line)
        fallen = regressions(record)
        for line in fallen: print('REGRESSION ' + line)
        if open_tasks or short or fallen:
            print(f'not finished: {len(open_tasks)} open task(s), {len(short)} indicator(s) short of target; ' + summary_line(record))
            return 1
        print(f'FINISHED: every task done, every indicator at its target; ' + summary_line(record))
        return 0
    if '--score' in options:
        print(json.dumps(score(record), ensure_ascii=False, indent=2))
        return 0
    text = render(record)
    readmes = {path: (path.read_text(encoding='utf-8'), readme_block(record, language)) for language, path in READMES.items()}
    if '--check' in options:
        stale = [] if (TARGET.read_text(encoding='utf-8') if TARGET.is_file() else '') == text else [TARGET]
        stale += [path for path, (current, block) in readmes.items() if with_block(current, block) != current]
        for path in stale: print(f'{path.relative_to(ROOT)} is stale; run python tools/north_star.py', file=sys.stderr)
        if stale: return 1
        print(summary_line(record))
        return 0
    for path, (current, block) in readmes.items():
        updated = with_block(current, block)
        if updated is None:
            print(f'{path.relative_to(ROOT)} has no {BLOCK[0]} … {BLOCK[1]} block', file=sys.stderr)
            return 1
        path.write_text(updated, encoding='utf-8')
    TARGET.write_text(text, encoding='utf-8')
    print(f"wrote {TARGET.relative_to(ROOT)} and both READMEs; {summary_line(record)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
