"""Turn confirmed claims into work that can be handed over: task cards and ordered waves.

The acceptance criterion of a task is the probe that confirmed its claim, inverted: whatever proved
the problem is what proves it is gone. A task without a runnable criterion is not generated.
"""
from pathlib import Path
from .compose import Document
from .compose.labels import impact_of, statement_of
from .impact import assess, load
from .ranking import claim_paths
from .remediation_patterns import pattern_for
from .workspace import read, write

PLAN_DIR = 'PLAN'
ACTIONABLE = {'CONFIRMED', 'LIKELY', 'HYPOTHESIS'}


def acceptance_for(claim, target, out):
    if claim['confidence'] == 'HYPOTHESIS':
        return [{'command': f'eaos dossier {target} --out {out} && eaos probe {target} --out {out}',
                 'expect': f"the probe attached to {claim['id']} returns CONFIRMED or REFUTED instead of leaving it a hypothesis"},
                {'command': 'review the falsifier by hand if no probe can decide it',
                 'expect': f"a written decision recorded against {claim['id']}: {claim['falsifier'][:120]}"}]
    """Commands that decide the task, derived from how the claim was proven."""
    probe = (claim.get('probe_spec') or {}).get('probe_type')
    commands = [{'command': f'eaos facts {target} --out {out}',
                 'expect': 'the fact set is rebuilt from the changed source'}]
    if probe:
        commands.append({'command': f'eaos dossier {target} --out {out} && eaos probe {target} --out {out}',
                         'expect': f"the probe for {claim['id']} no longer reports CONFIRMED "
                                   f"(it was confirmed by: {(claim.get('probe_spec') or {}).get('specification', {}).get('expected', 'the recorded probe')})"})
    else:
        commands.append({'command': f'eaos dossier {target} --out {out}',
                         'expect': f"{claim['id']} is absent from dossier.json, or carries a documented acceptance"})
    commands.append({'command': 'python -m unittest discover -s tests',
                     'expect': 'no behavioural regression'})
    return commands


def verify_command_for(claim, target, out):
    return ['eaos', 'dossier', str(target), '--out', str(out)]


def effort_for(radius, cost_bucket):
    if cost_bucket == 'large' or radius > 20: return 'كبير', 'منخفضة: لم يُقَس عمل مشابه بعد'
    if cost_bucket == 'medium' or radius > 5: return 'متوسط', 'متوسطة: مبني على حجم الكود ونطاق الأثر'
    return 'صغير', 'متوسطة: تغيير محصور في ملفات قليلة'


def build_tasks(target, out, dossier, sets):
    tasks, index = [], 0
    for claim in sorted(dossier['claims'], key=lambda row: (-row.get('priority', 0), row['id'])):
        if claim['confidence'] not in ACTIONABLE: continue
        if (claim.get('disposition') or {}).get('kind') == 'accepted': continue
        index += 1
        paths = claim_paths(claim, {}) or (claim.get('priority_factors') or {}).get('paths', [])
        radius = {'direct_dependents': [], 'transitive_dependents': [], 'flows': [], 'covering_tests': [],
                  'coverage': {}, 'entry_points': [], 'blast_radius': 0, 'change_partners': []}
        if paths:
            try: radius = assess(out, paths, sets=sets)
            except ValueError: pass
        pattern = pattern_for(claim)
        unproven = claim['confidence'] == 'HYPOTHESIS'
        cost = (claim.get('priority_factors') or {}).get('cost', {})
        effort, effort_confidence = effort_for(radius['blast_radius'], cost.get('bucket', 'medium'))
        tasks.append({
            'id': 'TASK-%03d' % index, 'claim_id': claim['id'], 'title': claim['statement'][:120],
            'render': claim.get('render'),
            'kind': 'investigate' if unproven or pattern['name'] == 'hidden_coupling' else 'remediate',
            'status': 'planned', 'priority': claim.get('priority', 0),
            'pattern': 'investigation' if unproven else pattern['name'], 'paths': paths,
            'origin': claim.get('origin', 'unknown'),
            'impact': (claim.get('impact') or {}).get('scenario', ''),
            'impact_render': claim.get('render'),
            'evidence': {'fact_ids': claim.get('fact_ids', []), 'evidence_ids': claim.get('evidence_ids', []),
                         'probe_ids': claim.get('probe_ids', []), 'falsifier': claim['falsifier']},
            'blast_radius': {'direct_dependents': radius['direct_dependents'],
                             'transitive_dependents': radius['transitive_dependents'][:10],
                             'flows': radius['flows'], 'entry_points': radius['entry_points'],
                             'covering_tests': radius['covering_tests'],
                             'coverage': radius['coverage'], 'change_partners': radius['change_partners'],
                             'total': radius['blast_radius']},
            'change': ('أثبت هذا الادعاء أو انقضه قبل أي تغيير: ' + claim['falsifier']) if unproven else pattern['change'],
            'options': ([{'option': 'تشغيل مجسّ يحسم الادعاء', 'cost': 'منخفضة', 'verdict': 'مختار: لا تغيير قبل الحسم'},
                         {'option': 'قبول الادعاء بلا إثبات', 'cost': 'صفر الآن', 'verdict': 'مرفوض: يخالف قاعدة الإسناد'},
                         *pattern['options']] if unproven else pattern['options']),
            'rollback': 'لا تغيير في الكود خلال التحقيق.' if unproven else pattern['rollback'],
            'acceptance': acceptance_for(claim, target, out),
            'verify_command': verify_command_for(claim, target, out),
            'effort': effort, 'effort_confidence': effort_confidence,
            'finding_ids': [claim['id']],
        })
    return tasks


def conflicts(tasks):
    """Two tasks that touch the same file cannot be executed in the same wave."""
    graph = {task['id']: set() for task in tasks}
    for first in tasks:
        for second in tasks:
            if first['id'] == second['id']: continue
            if set(first['paths']) & set(second['paths']): graph[first['id']].add(second['id'])
    return graph


def waves(tasks):
    """Greedy sequencing: highest priority first, investigations before the changes they inform."""
    graph = conflicts(tasks)
    ordered = sorted(tasks, key=lambda task: (0 if task['kind'] == 'investigate' else 1, -task['priority'], task['id']))
    placed, result = {}, []
    for task in ordered:
        level = 0
        while any(placed.get(other) == level for other in graph[task['id']]): level += 1
        placed[task['id']] = level
        while len(result) <= level: result.append([])
        result[level].append(task['id'])
    return [{'wave': number + 1, 'tasks': members,
             'entry_condition': 'الموجة السابقة اجتازت معايير قبولها' if number else 'ابدأ هنا',
             'exit_condition': 'كل مهمة في الموجة اجتازت أمر قبولها وسجّلت نتيجته'}
            for number, members in enumerate(result)]


def capped(items, limit=8):
    """A card is a decision surface, not a dump: show the first few and count the rest."""
    items = list(items)
    if len(items) <= limit: return ', '.join(items) or '—'
    return ', '.join(items[:limit]) + f' … (+{len(items) - limit})'


def coverage_line(coverage, language):
    if not coverage: return 'تغطية منفّذة: —' if language == 'ar' else 'executed coverage: —'
    parts = ', '.join(f"{path} {value.get('percent')}%" for path, value in sorted(coverage.items()))
    return ('تغطية منفّذة: ' if language == 'ar' else 'executed coverage: ') + parts


def title_of(task, language):
    return statement_of({'statement': task['title'], 'render': task.get('render')}, language)[:120]


def card(task, language):
    document = Document(f"{task['id']} — {title_of(task, language)}", language, budget_lines=140)
    marker = ' [كود اختبارات]' if language == 'ar' and task['origin'] == 'test' else ''
    document.header([f"الادعاء: {task['claim_id']} · النمط: {task['pattern']} · الأولوية: {task['priority']}{marker}"
                     if language == 'ar' else
                     f"claim: {task['claim_id']} · pattern: {task['pattern']} · priority: {task['priority']}"])
    document.section('المشكلة' if language == 'ar' else 'The problem')
    document.text(title_of(task, language))
    document.text(impact_of({'impact': {'scenario': task['impact']}, 'render': task.get('impact_render')}, language))
    document.section('الدليل' if language == 'ar' else 'Evidence')
    document.bullets([f"facts: {', '.join(task['evidence']['fact_ids']) or '—'}",
                      f"probes: {', '.join(task['evidence']['probe_ids']) or '—'}",
                      f"falsifier: {task['evidence']['falsifier']}"])
    document.section('نطاق الأثر' if language == 'ar' else 'Blast radius')
    radius = task['blast_radius']
    document.bullets([
        f"الملفات المعنية: {capped(task['paths'])}" if language == 'ar' else f"files: {capped(task['paths'])}",
        f"مستوردون مباشرون ({len(radius['direct_dependents'])}): {capped(radius['direct_dependents'])}",
        f"غير مباشرين ({len(radius['transitive_dependents'])}): {capped(radius['transitive_dependents'])}",
        f"تدفقات مارّة: {capped([flow['flow_id'] + ' ' + str(flow['route']) for flow in radius['flows']])}",
        f"اختبارات مغطية: {capped(radius['covering_tests'])}",
        coverage_line(radius['coverage'], language),
        f"شركاء التغيير: {capped([partner['path'] for partner in radius['change_partners']], 5)}",
    ])
    document.section('الخيارات' if language == 'ar' else 'Options')
    document.table(['الخيار' if language == 'ar' else 'Option', 'الكلفة' if language == 'ar' else 'Cost',
                    'الحكم' if language == 'ar' else 'Verdict'],
                   [[option.get('option'), option.get('cost'), option.get('verdict', '')] for option in task['options']])
    document.section('التغيير المقترح' if language == 'ar' else 'Proposed change')
    document.text(task['change'])
    document.section('معيار القبول' if language == 'ar' else 'Acceptance criterion')
    document.table(['الأمر' if language == 'ar' else 'Command', 'المتوقع' if language == 'ar' else 'Expected'],
                   [[step['command'], step['expect']] for step in task['acceptance']])
    document.section('التراجع' if language == 'ar' else 'Rollback')
    document.text(task['rollback'])
    document.section('التقدير' if language == 'ar' else 'Effort')
    document.text(f"{task['effort']} · ثقة التقدير: {task['effort_confidence']}" if language == 'ar'
                  else f"{task['effort']} · estimate confidence: {task['effort_confidence']}")
    return document


def waves_document(plan, tasks, language):
    document = Document('موجات التنفيذ' if language == 'ar' else 'Execution waves', language, budget_lines=140)
    by_id = {task['id']: task for task in tasks}
    document.header(['مهمتان تتشاركان ملفًا لا تقعان في موجة واحدة؛ التحقيق يسبق التغيير الذي يبني عليه.'
                     if language == 'ar' else
                     'Two tasks touching the same file never share a wave; an investigation precedes the change it informs.'])
    for wave in plan:
        document.section(f"الموجة {wave['wave']}" if language == 'ar' else f"Wave {wave['wave']}")
        document.table(['#', 'المهمة' if language == 'ar' else 'Task', 'النوع' if language == 'ar' else 'Kind',
                        'الأولوية' if language == 'ar' else 'Priority'],
                       [[identifier, title_of(by_id[identifier], language)[:90], by_id[identifier]['kind'],
                         by_id[identifier]['priority']] for identifier in wave['tasks']])
        document.bullets([f"شرط الدخول: {wave['entry_condition']}" if language == 'ar' else f"entry: {wave['entry_condition']}",
                          f"شرط الخروج: {wave['exit_condition']}" if language == 'ar' else f"exit: {wave['exit_condition']}"])
    return document


def build(target, out, language='ar'):
    target, out = Path(target).resolve(), Path(out).resolve()
    dossier_path = out / 'dossier.json'
    if not dossier_path.is_file(): raise ValueError('Build a dossier before planning: eaos dossier')
    dossier = read(dossier_path)
    sets = load(out)
    tasks = build_tasks(target, out, dossier, sets)
    plan = waves(tasks)
    directory = out / PLAN_DIR
    directory.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        (directory / (task['id'] + '.md')).write_text(card(task, language).render(), encoding='utf-8')
    (directory / 'WAVES.md').write_text(waves_document(plan, tasks, language).render(), encoding='utf-8')
    dossier['tasks'] = tasks
    dossier['waves'] = plan
    write(dossier_path, dossier)
    write(out / 'plan.json', {'tasks': tasks, 'waves': plan})
    from .dossier import refresh_views
    refresh_views(out, language)
    return {'target': str(target), 'out': str(out), 'tasks': len(tasks), 'waves': len(plan),
            'cards': [str(directory / (task['id'] + '.md')) for task in tasks],
            'limits': 'Each task states one runnable acceptance criterion derived from the probe that confirmed its claim. '
                      'Effort is an estimate with declared confidence, not a commitment.'}
