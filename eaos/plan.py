"""Build reviewable task cards with separate investigation and repair decisions.

An observed pattern does not establish a violation. Repairs need sourced requirements,
review and independent acceptance; investigations may conclude no change.
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
    from .decisions import decide
    decision = decide(claim)
    if decision['kind'] == 'repair' and decision['checks']:
        import shlex
        return [{'command': shlex.join(check['argv']) if check.get('kind') == 'command' else 'human review',
                 'expect': check.get('expected', '')} for check in decision['checks']]
    return [{'command': 'human review / مراجعة هندسية',
             'expect': claim['id'] + ': CONFIRMED or REFUTED concerns the observation only; '
                       'record requirement evidence and decide repair, retain, or blocked_missing_requirement. ' + claim['falsifier']}]


def verify_command_for(claim, target, out):
    from .decisions import decide
    decision = decide(claim)
    checks = decision['checks']
    return next((check['argv'] for check in checks if check.get('kind') == 'command' and check.get('argv')), [])


def effort_for(radius, cost_bucket):
    if cost_bucket == 'large' or radius > 20: return 'كبير', 'منخفضة: لم يُقَس عمل مشابه بعد'
    if cost_bucket == 'medium' or radius > 5: return 'متوسط', 'متوسطة: مبني على حجم الكود ونطاق الأثر'
    return 'صغير', 'متوسطة: تغيير محصور في ملفات قليلة'


def build_tasks(target, out, dossier, sets):
    tasks, index = [], 0
    for claim in sorted(dossier['claims'], key=lambda row: (-row.get('priority', 0), row['id'])):
        if claim['confidence'] not in ACTIONABLE: continue
        from .decisions import decide
        decision = decide(claim)
        if decision['kind'] == 'retain': continue
        index += 1
        paths = claim_paths(claim, {}) or (claim.get('priority_factors') or {}).get('paths', [])
        radius = {'direct_dependents': [], 'transitive_dependents': [], 'flows': [], 'covering_tests': [],
                  'coverage': {}, 'entry_points': [], 'blast_radius': 0, 'change_partners': []}
        if paths:
            try: radius = assess(out, paths, sets=sets)
            except ValueError: pass
        pattern = pattern_for(claim)
        unproven = decision['kind'] == 'investigate'
        cost = (claim.get('priority_factors') or {}).get('cost', {})
        effort, effort_confidence = effort_for(radius['blast_radius'], cost.get('bucket', 'medium'))
        tasks.append({
            'id': 'TASK-%03d' % index, 'claim_id': claim['id'], 'title': claim['statement'][:120],
            'render': claim.get('render'),
            'kind': 'investigate' if unproven else 'remediate',
            'contract_version': 1, 'decision': decision,
            'prerequisites': [], 'before': (claim.get('assessment') or {}).get('before'),
            'after': (claim.get('assessment') or {}).get('after'),
            'status': 'planned', 'priority': claim.get('priority', 0),
            'pattern': 'investigation' if claim['confidence'] == 'HYPOTHESIS' else pattern['name'], 'paths': paths,
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
            'change': ('أثبت هذا الادعاء أو انقضه قبل أي تغيير: ' + claim['falsifier']) if unproven else (claim.get('assessment') or {}).get('proposed_change', pattern['change']),
            'options': ([{'option': 'تشغيل مجسّ يحسم الادعاء', 'cost': 'منخفضة', 'verdict': 'مختار: لا تغيير قبل الحسم'},
                         {'option': 'قبول الادعاء بلا إثبات', 'cost': 'صفر الآن', 'verdict': 'مرفوض: يخالف قاعدة الإسناد'},
                         *pattern['options']] if unproven else pattern['options']),
            'rollback': 'لا تغيير في الكود خلال التحقيق.' if unproven else pattern['rollback'],
            'acceptance': acceptance_for(claim, target, out),
            'verify_command': verify_command_for(claim, target, out),
            'effort': 'unknown', 'effort_confidence': 'Not measured / لم يُقَس',
            'finding_ids': [claim['id']],
        })
    by_claim = {task['claim_id']: task['id'] for task in tasks}
    source_claims = {claim['id']: claim for claim in dossier['claims']}
    for task in tasks:
        dependencies = (source_claims[task['claim_id']].get('assessment') or {}).get('prerequisites', [])
        for dependency in dependencies:
            if dependency.get('claim_id') not in by_claim:
                raise ValueError('Unknown or non-actionable prerequisite claim')
            if not dependency.get('reason'): raise ValueError('Prerequisite needs a reason')
            task['prerequisites'].append({'task_id': by_claim[dependency['claim_id']], 'reason': dependency['reason']})
    from .decisions import task_errors
    for task in tasks:
        errors = task_errors(task)
        if errors: raise ValueError('Invalid task: ' + '; '.join(errors))
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
    """Causal prerequisites and file conflicts are distinct constraints."""
    graph = conflicts(tasks)
    by_id = {task['id']: task for task in tasks}
    if len(by_id) != len(tasks): raise ValueError('Duplicate task id')
    dependencies = {}
    for task in tasks:
        refs = task.get('prerequisites', [])
        dependencies[task['id']] = set()
        for ref in refs:
            if not isinstance(ref, dict) or not ref.get('reason'): raise ValueError('Prerequisite needs a reason')
            if ref.get('task_id') not in by_id: raise ValueError('Unknown prerequisite')
            dependencies[task['id']].add(ref['task_id'])
    placed, result = {}, []
    while len(placed) < len(tasks):
        available = [task for task in tasks if task['id'] not in placed
                     and dependencies[task['id']] <= set(placed)]
        if not available: raise ValueError('Causal dependency cycle')
        available.sort(key=lambda task: (task['kind'] != 'investigate', -task['priority'], task['id']))
        members = []
        for task in available:
            if not graph[task['id']] & set(members): members.append(task['id'])
        for identifier in members: placed[identifier] = len(result)
        result.append({'wave': len(result) + 1, 'tasks': members,
                       'entry_condition': 'Required predecessor decisions accepted; file conflicts serialized.',
                       'exit_condition': 'Record check outcomes or an evidenced investigation decision.'})
    return result


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
    decision = task.get('decision', {})
    document.header([f"{decision.get('kind', 'legacy')} · {decision.get('readiness', 'needs_revalidation')}"])
    document.bullets(decision.get('blockers', []))
    document.section('المشكلة' if language == 'ar' else 'The problem')
    document.text(title_of(task, language))
    document.text(impact_of({'impact': {'scenario': task['impact']}, 'render': task.get('impact_render')}, language))
    document.section('الدليل' if language == 'ar' else 'Evidence')
    document.bullets([f"facts: {', '.join(task['evidence']['fact_ids']) or '—'}",
                      f"probes: {', '.join(task['evidence']['probe_ids']) or '—'}",
                      f"falsifier: {task['evidence']['falsifier']}"])
    document.section('نطاق الأثر' if language == 'ar' else 'Blast radius')
    radius = task['blast_radius']
    if not task['paths']:
        document.text('هذا الادعاء يخص المنتج ككل ولا يشير إلى ملف بعينه، فلا نطاق أثر محسوبًا له؛ '
                      'حدّد الملفات المعنية أثناء التحقيق.' if language == 'ar' else
                      'This claim is about the product as a whole and names no file, so there is no computed '
                      'blast radius; identify the affected files during the investigation.')
        return document
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
                   ([['Investigate the requirement', 'unknown', 'Determine repair or retain'],
                     ['Keep current design', 'unknown', 'Valid outcome if no violation is established']]
                    if language == 'en' and task['kind'] == 'investigate' else
                    [[option.get('option'), option.get('cost'), option.get('verdict', '')] for option in task['options']]))
    if task.get('before') or task.get('after'):
        document.section('قبل وبعد' if language == 'ar' else 'Before and after')
        document.bullets([str(task.get('before')), str(task.get('after'))])
    document.section('التغيير المقترح' if language == 'ar' else 'Proposed change')
    document.text(('Establish or refute this observation before changing code: ' + task['evidence']['falsifier'])
                  if language == 'en' and task['kind'] == 'investigate' else task['change'])
    document.section('معيار القبول' if language == 'ar' else 'Acceptance criterion')
    document.table(['الأمر' if language == 'ar' else 'Command', 'المتوقع' if language == 'ar' else 'Expected'],
                   [[step['command'], step['expect']] for step in task['acceptance']])
    document.section('التراجع' if language == 'ar' else 'Rollback')
    document.text('No code changes during investigation.' if language == 'en' and task['kind'] == 'investigate' else task['rollback'])
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


def rebuild(out, dossier, language='ar', target=None):
    """Regenerate the plan from a ledger that changed, without re-reading the target twice."""
    out = Path(out)
    sets = load(out)
    source = Path(target) if target else Path(dossier['provenance']['target'])
    tasks = build_tasks(source, out, dossier, sets)
    plan = waves(tasks)
    directory = out / PLAN_DIR
    directory.mkdir(parents=True, exist_ok=True)
    for stale in directory.glob('TASK-*.md'): stale.unlink()
    for task in tasks:
        (directory / (task['id'] + '.md')).write_text(card(task, language).render(), encoding='utf-8')
    (directory / 'WAVES.md').write_text(waves_document(plan, tasks, language).render(), encoding='utf-8')
    dossier['tasks'], dossier['waves'], dossier['plan_contract_version'] = tasks, plan, 1
    write(out / 'dossier.json', dossier)
    write(out / 'plan.json', {'contract_version': 1, 'tasks': tasks, 'waves': plan,
                              'decisions': dossier.get('decisions', [])})
    return len(tasks)


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
    for stale in directory.glob('TASK-*.md'): stale.unlink()
    for task in tasks:
        (directory / (task['id'] + '.md')).write_text(card(task, language).render(), encoding='utf-8')
    (directory / 'WAVES.md').write_text(waves_document(plan, tasks, language).render(), encoding='utf-8')
    dossier['plan_contract_version'] = 1
    dossier['tasks'] = tasks
    dossier['waves'] = plan
    write(dossier_path, dossier)
    from .decisions import decide
    write(out / 'plan.json', {'contract_version': 1, 'tasks': tasks, 'waves': plan,
                             'decisions': [decide(claim) for claim in dossier['claims']]})
    from .dossier import refresh_views
    refresh_views(out, language)
    return {'target': str(target), 'out': str(out), 'tasks': len(tasks), 'waves': len(plan),
            'cards': [str(directory / (task['id'] + '.md')) for task in tasks],
            'limits': 'Repairs require evidenced violations and independent checks. Investigations may conclude no change. '
                      'Effort is an estimate with declared confidence, not a commitment.'}
