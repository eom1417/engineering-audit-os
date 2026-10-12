"""Build reviewable task cards with separate investigation and repair decisions.

An observed pattern does not establish a violation. Repairs need sourced requirements,
review and independent acceptance; investigations may conclude no change.
"""
from pathlib import Path
from .compose import Document
from .compose.labels import falsifier_of, impact_of, statement_of
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
    # An investigation changes no code: it is done when its decision is recorded (eaos decision-review), which
    # `eaos decided` checks. The decision itself stays a person's; the command only shows it was made.
    import shlex, sys
    from .decisions import identity
    uid = claim.get('uid') or identity(claim)
    return [{'command': shlex.join([sys.executable, '-m', 'eaos', 'decided', str(Path(out).resolve()), uid]),
             'expect': claim['id'] + ': a recorded decision (repair with its check, retain with an owner and a reason, or '
                       'the claim refuted) after weighing: ' + claim['falsifier']}]


def verify_command_for(claim, target, out):
    from .decisions import decide
    decision = decide(claim)
    checks = decision['checks']
    return next((check['argv'] for check in checks if check.get('kind') == 'command' and check.get('argv')), [])


def effort_for(radius, cost_bucket):
    if cost_bucket == 'large' or radius > 20: return 'كبير', 'منخفضة: لم يُقَس عمل مشابه بعد'
    if cost_bucket == 'medium' or radius > 5: return 'متوسط', 'متوسطة: مبني على حجم الكود ونطاق الأثر'
    return 'صغير', 'متوسطة: تغيير محصور في ملفات قليلة'


def size_of(paths, dependents):
    from .roadmap import effort
    return effort(paths, dependents)


def schedule(out, target, tasks, language):
    """Milestones and sections for the cards, and ROADMAP.md: the build milestones follow the target projection."""
    from .roadmap import milestones, render, sections
    from .target_projection import project
    projection = project(out, target)
    placements = (projection or {}).get('placements') or {}
    rebuilt = {}
    for judged in ((projection or {}).get('current') or {}).values():
        if judged['relation'] == 'rebuild': rebuilt[judged['target_component']] = 'rebuild'
    plan_milestones = milestones(tasks, placements, rebuilt)
    (Path(out) / 'ROADMAP.md').write_text(render(plan_milestones, tasks, language).render(), encoding='utf-8')
    return plan_milestones, sections(tasks)


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
            'requirement_refs': list((claim.get('assessment') or {}).get('requirement_refs') or []),
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
            'change': ('أثبت هذا الادعاء أو انقضه قبل أي تغيير: ' + falsifier_of(claim, 'ar')) if unproven else (claim.get('assessment') or {}).get('proposed_change', pattern['change']),
            'options': ([{'option': 'تشغيل مجسّ يحسم الادعاء', 'cost': 'منخفضة', 'verdict': 'مختار: لا تغيير قبل الحسم'},
                         {'option': 'قبول الادعاء بلا إثبات', 'cost': 'صفر الآن', 'verdict': 'مرفوض: يخالف قاعدة الإسناد'},
                         *pattern['options']] if unproven else pattern['options']),
            'rollback': 'لا تغيير في الكود خلال التحقيق.' if unproven else pattern['rollback'],
            'acceptance': acceptance_for(claim, target, out),
            'verify_command': verify_command_for(claim, target, out),
            'effort': size_of(paths, radius['blast_radius'])[0], 'effort_basis': size_of(paths, radius['blast_radius'])[1],
            'effort_confidence': 'A rule on the files it touches and its dependents (eaos/roadmap.py), not a measured duration.',
            'invariants': invariants_of(claim),
            'harm': harm_of(claim, radius, effort, effort_confidence),
            'finding_ids': [claim['id']],
        })
    tasks = grouped(tasks)
    from .roadmap import section
    for task in tasks: task['section'] = section(task)
    by_claim = {claim_id: task['id'] for task in tasks for claim_id in task['claim_ids']}
    source_claims = {claim['id']: claim for claim in dossier['claims']}
    for task in tasks:
        for claim_id in task['claim_ids']:
            for dependency in (source_claims[claim_id].get('assessment') or {}).get('prerequisites', []):
                if dependency.get('claim_id') not in by_claim:
                    raise ValueError('Unknown or non-actionable prerequisite claim')
                if not dependency.get('reason'): raise ValueError('Prerequisite needs a reason')
                if by_claim[dependency['claim_id']] == task['id']: continue
                task['prerequisites'].append({'task_id': by_claim[dependency['claim_id']], 'reason': dependency['reason']})
    from .decisions import task_errors
    for task in tasks:
        errors = task_errors(task)
        if errors: raise ValueError('Invalid task: ' + '; '.join(errors))
    return tasks


# Kinds of card whose findings in one file are fixed by one change there: one card per (kind, file).
GROUPED = {'hotspot', 'dead_code', 'remove_dead', 'duplicated_rule'}


def grouped(tasks):
    """The cards with the findings of one kind in the same files (GROUPED) made one card: the most urgent one stands
    for them, every claim's id (`claim_ids`), facts and acceptance kept, the others named in `grouped`; then numbered
    again in order (TASK-001...)."""
    out, home = [], {}
    for task in tasks:
        task['claim_ids'] = [task['claim_id']]
        key = (task['pattern'], task['kind'], task.get('origin'), tuple(sorted(task['paths'])))
        first = home.get(key) if task['pattern'] in GROUPED and task['paths'] else None
        if first is None:
            home[key] = task
            out.append(task)
            continue
        first['claim_ids'].append(task['claim_id'])
        first['finding_ids'].append(task['claim_id'])
        first.setdefault('grouped', []).append({'claim_id': task['claim_id'], 'title': task['title'], 'render': task.get('render')})
        for name in ('fact_ids', 'evidence_ids', 'probe_ids'):
            first['evidence'][name] = list(dict.fromkeys(first['evidence'][name] + task['evidence'][name]))
        seen = {step['command'] for step in first['acceptance']}
        first['acceptance'] += [step for step in task['acceptance'] if step['command'] not in seen]
    for number, task in enumerate(out, 1): task['id'] = 'TASK-%03d' % number
    return out


UNKNOWN = 'unknown'


def invariants_of(claim):
    """What must still hold after the change. An empty list is a real answer, not a gap to fill."""
    assessment = claim.get('assessment') or {}
    stated = assessment.get('violated_invariant')
    rows = []
    if stated:
        rows.append({'invariant': stated, 'source': 'assessment', 'must_hold_after': True})
    rows.append({'invariant': claim['falsifier'], 'source': 'falsifier',
                 'must_hold_after': False,
                 'note': 'the observation that would show this claim is wrong; after a repair it should hold'})
    return rows


def harm_of(claim, radius, effort, effort_confidence):
    """Three different questions kept apart: what it costs the business, what it touches, what it costs us.

    Reach is measured and effort is estimated; business harm is neither unless someone evidenced it.
    Reporting a measured reach as if it were business harm is how a structural observation starts
    reading like an incident.
    """
    assessment = claim.get('assessment') or {}
    evidenced = assessment.get('business_harm') or (claim.get('impact') or {}).get('business_harm')
    return {
        'business': {'value': evidenced or UNKNOWN,
                     'basis': 'evidenced in the assessment' if evidenced else
                              'not established: no requirement or incident evidences a business cost'},
        'reach': {'value': radius['blast_radius'], 'basis': 'measured from the dependency graph',
                  'direct_dependents': len(radius['direct_dependents']), 'flows': len(radius['flows'])},
        'effort': {'value': effort, 'basis': effort_confidence},
    }


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
    marker = (' [كود اختبارات]' if language == 'ar' and task['origin'] == 'test' else
              ' [كود مؤرشف]' if language == 'ar' and task['origin'] == 'archive' else '')
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
                      f"falsifier: {falsifier_of({'falsifier': task['evidence']['falsifier'],
                                                  'render': task.get('render')}, language)}"])
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
    localized = falsifier_of({'falsifier': task['evidence']['falsifier'],
                              'render': task.get('render')}, language)
    document.text(('Establish or refute this observation before changing code: ' + localized)
                  if language == 'en' and task['kind'] == 'investigate'
                  else (('أثبت هذا الادعاء أو انقضه قبل أي تغيير: ' + localized)
                        if task['kind'] == 'investigate' else task['change']))
    document.section('معيار القبول' if language == 'ar' else 'Acceptance criterion')
    document.table(['الأمر' if language == 'ar' else 'Command', 'المتوقع' if language == 'ar' else 'Expected'],
                   [[step['command'], step['expect']] for step in task['acceptance']])
    document.section('التراجع' if language == 'ar' else 'Rollback')
    document.text('No code changes during investigation.' if language == 'en' and task['kind'] == 'investigate' else task['rollback'])
    document.section('التقدير' if language == 'ar' else 'Effort')
    document.text(f"{task['effort']} · ثقة التقدير: {task['effort_confidence']}" if language == 'ar'
                  else f"{task['effort']} · estimate confidence: {task['effort_confidence']}")
    return document


def _compact_waves(document, plan, by_id, language):
    """One row per wave: every task id kept, every title deferred to its card."""
    conditions = {(wave['entry_condition'], wave['exit_condition']) for wave in plan}
    document.header(['مهمتان تتشاركان ملفًا لا تقعان في موجة واحدة؛ التحقيق يسبق التغيير الذي يبني عليه.'
                     if language == 'ar' else
                     'Two tasks touching the same file never share a wave; an investigation precedes the change it informs.',
                     f"{len(plan)} موجات · التفاصيل في بطاقات PLAN/" if language == 'ar' else
                     f'{len(plan)} waves · the detail is in the PLAN/ cards'])
    if len(conditions) == 1:
        document.bullets(list(_condition_lines(*conditions.copy().pop(), language)))
    document.table(['#', 'المهام' if language == 'ar' else 'Tasks',
                    'النوع' if language == 'ar' else 'Kinds', 'الأولوية' if language == 'ar' else 'Top priority'],
                   [[str(wave['wave']), ' '.join(wave['tasks']),
                     ', '.join(sorted({by_id[identifier]['kind'] for identifier in wave['tasks']})),
                     str(max(by_id[identifier]['priority'] for identifier in wave['tasks']))]
                    for wave in plan])
    return document


def _condition_lines(entry, exit_condition, language):
    """One wording for a wave's entry and exit, wherever they are printed."""
    if language == 'ar':
        return [f'شرط الدخول: {entry}', f'شرط الخروج: {exit_condition}']
    return [f'entry: {entry}', f'exit: {exit_condition}']


WAVE_BUDGET = 140
# Chrome per wave in the sectioned form: heading, table header, separator, blank lines.
SECTION_OVERHEAD = 7


def waves_document(plan, tasks, language):
    document = Document('موجات التنفيذ' if language == 'ar' else 'Execution waves', language,
                        budget_lines=WAVE_BUDGET)
    by_id = {task['id']: task for task in tasks}
    # A section per wave costs a fixed overhead each. Past a few dozen waves that overhead alone
    # exceeds the budget and every table gets trimmed to one row, which hides the plan instead of
    # shortening it. One row per wave scales, and the titles live in the cards either way.
    if len(plan) * SECTION_OVERHEAD + len(tasks) > WAVE_BUDGET - 12:
        return _compact_waves(document, plan, by_id, language)
    conditions = {(wave['entry_condition'], wave['exit_condition']) for wave in plan}
    document.header(['مهمتان تتشاركان ملفًا لا تقعان في موجة واحدة؛ التحقيق يسبق التغيير الذي يبني عليه.'
                     if language == 'ar' else
                     'Two tasks touching the same file never share a wave; an investigation precedes the change it informs.'])
    # Conditions identical for every wave are stated once, not repeated into the line budget.
    if len(conditions) == 1:
        document.bullets(list(_condition_lines(*conditions.copy().pop(), language)))
    for wave in plan:
        document.section(f"الموجة {wave['wave']}" if language == 'ar' else f"Wave {wave['wave']}")
        document.table(['#', 'المهمة' if language == 'ar' else 'Task', 'النوع' if language == 'ar' else 'Kind',
                        'الأولوية' if language == 'ar' else 'Priority'],
                       [[identifier, title_of(by_id[identifier], language)[:90], by_id[identifier]['kind'],
                         by_id[identifier]['priority']] for identifier in wave['tasks']])
        if len(conditions) > 1:
            document.bullets(list(_condition_lines(wave['entry_condition'], wave['exit_condition'], language)))
    return document


def publish(directory, tasks, plan, language):
    """Render every card and the wave document before touching disk: a render failure leaves no half-written plan."""
    documents = {task['id'] + '.md': card(task, language).render() for task in tasks}
    documents['WAVES.md'] = waves_document(plan, tasks, language).render()
    directory.mkdir(parents=True, exist_ok=True)
    for stale in directory.glob('TASK-*.md'): stale.unlink()
    for name, text in documents.items():
        (directory / name).write_text(text, encoding='utf-8')


def rebuild(out, dossier, language='ar', target=None):
    """Regenerate the plan from a ledger that changed, without re-reading the target twice."""
    out = Path(out)
    sets = load(out)
    source = Path(target) if target else Path(dossier['provenance']['target'])
    tasks = build_tasks(source, out, dossier, sets)
    plan = waves(tasks)
    directory = out / PLAN_DIR
    publish(directory, tasks, plan, language)
    dossier['tasks'], dossier['waves'], dossier['plan_contract_version'] = tasks, plan, 1
    write(out / 'dossier.json', dossier)
    from .codemods import attach
    attach(tasks, out, source)
    plan_milestones, plan_sections = schedule(out, source, tasks, language)
    write(out / 'plan.json', {'contract_version': 1, 'tasks': tasks, 'waves': plan, 'milestones': plan_milestones,
                              'sections': plan_sections, 'decisions': dossier.get('decisions', [])})
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
    publish(directory, tasks, plan, language)
    dossier['plan_contract_version'] = 1
    dossier['tasks'] = tasks
    dossier['waves'] = plan
    write(dossier_path, dossier)
    from .decisions import decide
    from .codemods import attach
    attach(tasks, out, target)
    plan_milestones, plan_sections = schedule(out, target, tasks, language)
    write(out / 'plan.json', {'contract_version': 1, 'tasks': tasks, 'waves': plan, 'milestones': plan_milestones,
                             'sections': plan_sections, 'decisions': [decide(claim) for claim in dossier['claims']]})
    from .dossier import refresh_views
    refresh_views(out, language)
    return {'target': str(target), 'out': str(out), 'tasks': len(tasks), 'waves': len(plan),
            'cards': [str(directory / (task['id'] + '.md')) for task in tasks],
            'limits': 'Repairs require evidenced violations and independent checks. Investigations may conclude no change. '
                      'Effort is an estimate with declared confidence, not a commitment.'}


def _load(path, default):
    try: return read(path)
    except (OSError, ValueError): return default


def _verdicts(out):
    """{card: verdict} of this check's triage when the assistant made it; {} when the rules decided alone."""
    body = _load(Path(out) / 'nodes/card_triage/verdicts.json', {})
    if body.get('method') != 'model': return {}
    return {v['card']: v for v in body.get('verdicts') or [] if isinstance(v, dict) and v.get('source') == 'model'}


# A design finding's share of the top code card's priority, by its severity, times the weight of an unconfirmed
# claim (eaos/ranking.py): on the code claims' scale, never above the most urgent of them.
SEVERITY_SHARE = {'high': 1.0, 'medium': 0.5, 'low': 0.25}
SEVERITY_ORDER = ('high', 'medium', 'low')


def page_of(page):
    """One name per page: `http://host/`, `/`, `/#/` and `#/` are the home page; `/#/branches` is `/branches`."""
    from urllib.parse import urlsplit
    text = str(page or '')
    if '://' in text:
        parts = urlsplit(text)
        text = parts.path + ('#' + parts.fragment if parts.fragment else '')
    return '/' + '/'.join(part for part in text.split('?')[0].replace('#', '/').split('/') if part)


def template_of(page):
    """The page as a kind of page: a part of its path that names one record (a digit, an escape or a sign in it, as in
    `/tasks/TASK-001` or `/system/f/eaos%2Fplan.py`) is `*`, so the findings of every task page are the task page's."""
    import re
    return '/' + '/'.join('*' if re.search(r'[^a-z-]', part) else part for part in page_of(page).split('/') if part)


def design_cards(findings, tasks):
    """The visual reviewer's findings as design cards: one per (kind of page, kind of problem), the most severe finding
    standing for them and every picture of them its evidence (`design.findings`); each priority on the code cards'
    scale (SEVERITY_SHARE)."""
    from .ranking import CONFIDENCE_WEIGHT
    top = max((t.get('priority') or 0 for t in tasks if t.get('origin') != 'visual_review'), default=0) or 1.0
    kept = {}
    for finding in sorted(findings, key=lambda f: SEVERITY_ORDER.index(f['severity']) if f.get('severity') in SEVERITY_ORDER else 3):
        kept.setdefault((finding.get('template') or template_of(finding.get('page')), finding.get('kind') or ' '.join(str(finding.get('title') or '').lower().split())),
                        []).append(finding)
    cards = []
    for number, group in enumerate(kept.values(), 1):
        finding = group[0]
        card = design_card(number, finding)
        card['priority'] = round(top * SEVERITY_SHARE.get(finding.get('severity'), 0.25) * CONFIDENCE_WEIGHT['HYPOTHESIS'], 4)
        card['design']['page'] = finding.get('template') or template_of(finding.get('page'))
        card['design']['findings'] = [{k: f.get(k) for k in ('image', 'file', 'page', 'viewport', 'theme', 'title', 'severity', 'region', 'why',
                                                             'pictures')}
                                      for f in group]
        # A finding of the page reviewer (eaos/studio/nodes/visual_reviewer.py) lists every picture it shows on.
        shown = [show for f in group for show in f.get('pictures') or [f]]
        images = list(dict.fromkeys(show['image'] for show in shown))
        if len(images) > 1:
            card['design']['also_in'] = images[1:]
            card['finding_ids'] = images
            card['evidence']['evidence_ids'] = images
            card['evidence']['images'] = list(dict.fromkeys(show['file'] for show in shown))
            titles = list(dict.fromkeys(f['title'] for f in group[1:] if f['title'] != finding['title']))
            if titles: card['change'] += ' Also on this page: ' + '; '.join(titles[:6]) + (f' (+{len(titles) - 6})' if len(titles) > 6 else '') + '.'
        if finding.get('resolution') in RESOLUTIONS:
            card['design']['resolution'] = {k: finding.get(k) for k in ('resolution', 'question', 'options', 'recommendation')}
        cards.append(card)
    return cards


def design_card(number, finding):
    """A card for one finding of the visual reviewer: an investigation, done when its decision is recorded, citing its
    picture and the region of it."""
    region = finding['region']
    where = f"{finding['file']} ({region['x']:.2f}, {region['y']:.2f}, {region['width']:.2f} x {region['height']:.2f})"
    return {'id': f'TASK-V{number:03d}', 'claim_id': None, 'title': finding['title'][:120], 'render': None, 'kind': 'investigate',
            'contract_version': 1,
            'decision': {'contract_version': 1, 'kind': 'investigate', 'readiness': 'needs_review', 'blockers': [], 'checks': [],
                         'reason': 'A design finding of the visual reviewer: confirm it on the screen before changing it.',
                         'allowed_outcomes': ['repair', 'retain', 'blocked_missing_requirement']},
            'prerequisites': [], 'before': None, 'after': None, 'requirement_refs': [], 'status': 'planned',
            'priority': SEVERITY_SHARE.get(finding['severity'], 0.25), 'pattern': 'design_review', 'paths': [], 'origin': 'visual_review',
            'impact': finding['why'], 'impact_render': None,
            'evidence': {'fact_ids': [], 'evidence_ids': [finding['image']], 'probe_ids': [], 'images': [finding['file']],
                         'region': region, 'falsifier': f"The picture {where} does not show it."},
            'blast_radius': {'direct_dependents': [], 'transitive_dependents': [], 'flows': [], 'entry_points': [],
                             'covering_tests': [], 'coverage': {}, 'change_partners': [], 'total': 0},
            'change': f"{finding['why']} ({finding['page']}, {finding['viewport']}, {finding['theme']}: {where})",
            'options': [], 'rollback': 'No code changes while the finding is confirmed.', 'acceptance': [{'command': 'human review',
            'expect': f'The screen no longer shows it: {where}'}], 'verify_command': [], 'effort': 'S', 'effort_basis': {'files': 0, 'dependents': 0},
            'effort_confidence': 'Not measured: a design change on one screen.', 'invariants': [], 'harm': {},
            'finding_ids': [finding['image']], 'section': 'frontend', 'design': {k: finding.get(k) for k in ('kind', 'severity', 'page', 'viewport', 'theme')}}


def _design_cards(out, tasks):
    """The visual reviewer's findings of this check, as design cards (design_cards)."""
    body = _load(Path(out) / 'nodes/visual_reviewer/findings.json', {})
    if body.get('method') != 'model': return []
    return design_cards(body.get('findings') or [], tasks)


RESOLUTIONS = ('fix', 'keep', 'owner')
OWNER_SHARE = 0.10          # at most this share of the cards asks the person (at least one)
RESOLUTION_FIELDS = ('resolution', 'change', 'question', 'options', 'recommendation', 'note', 'checks')
CARD_SEVERITY = {'critical': 5, 'high': 4, 'medium': 2, 'low': 1, 'info': 0.5}


def apply_verdicts(out, tasks, verdicts, language='ar'):
    """The one place the assistant's triage reaches the ledger, before anything ranks, plans or reports: the claims of
    a card it rejected are refuted (confidence REFUTED, `refuted_by` the card, its why kept in `triage`), the claims of
    a card it doubted carry the doubt (eaos/decisions.py: needs_review, never fixed automatically), those of a card it
    confirmed carry its resolution (fix, keep or owner, eaos/decisions.py decide), and the ledger's ranking, decisions,
    brief and debt register are drawn again (dossier.refresh_views), so the risks, the reports and the plan all read the
    same verdicts. Returns {claim id: claim}."""
    from .dossier import refresh_views
    out = Path(out)
    dossier = read(out / 'dossier.json')
    claims = {c['id']: c for c in dossier['claims']}
    for task in tasks:
        verdict = verdicts.get(task['id'])
        if not verdict or verdict.get('decision') not in ('confirm', 'doubt', 'reject'): continue
        for claim in filter(None, (claims.get(c) for c in task.get('claim_ids') or [task.get('claim_id')])):
            claim['triage'] = {'decision': verdict['decision'], 'card': task['id'], 'why': verdict.get('why'),
                               'evidence': list(verdict.get('evidence') or []), 'rejudged': bool(verdict.get('rejudged')),
                               **{k: verdict[k] for k in RESOLUTION_FIELDS if verdict.get(k) is not None}}
            if verdict['decision'] == 'reject':
                claim['confidence'] = 'REFUTED'
                claim['refuted_by'] = sorted(set(claim.get('refuted_by') or []) | {'card_triage:' + task['id']})
    write(out / 'dossier.json', dossier)
    refresh_views(out, language)
    return {c['id']: c for c in read(out / 'dossier.json')['claims']}


def resolutions(tasks, verdicts, design):
    """{card: resolution} the assistant gave: the triage's for the code cards it confirmed (nodes/card_triage), the
    screen reviewer's for the design cards (a design card is the change it named, unless its finding asked the
    person or kept it)."""
    out = {}
    for task in tasks:
        verdict = verdicts.get(task['id']) or {}
        if verdict.get('decision') == 'confirm' and verdict.get('resolution') in RESOLUTIONS:
            out[task['id']] = {**{k: verdict.get(k) for k in RESOLUTION_FIELDS if verdict.get(k) is not None}, 'why': verdict.get('why'),
                               'severity': verdict.get('severity'), 'reach': (task.get('blast_radius') or {}).get('total') or 0}
    for card in design:
        asked = card['design'].get('resolution') or {}
        pictures = len(card['finding_ids']) or 1
        resolution = asked if asked.get('resolution') in ('keep', 'owner') and (asked['resolution'] == 'keep' or asked.get('question')) else {
            'resolution': 'fix', 'change': card['change'],
            'note': f'the screen reviewer saw it on {pictures} picture{"s" if pictures > 1 else ""} of this page and named the change'}
        out[card['id']] = {**{k: v for k, v in resolution.items() if v is not None}, 'why': card['impact'],
                           'severity': card['design'].get('severity'), 'reach': pictures}
    return out


def cap_owner(resolved, cards):
    """At most OWNER_SHARE of the `cards` ask the person: the questions that matter most (severity x reach) stay
    `owner`; the others become `fix` with the assistant's own recommendation, saying so. Changes `resolved`; returns
    the cards it turned."""
    asked = [card for card, r in resolved.items() if r['resolution'] == 'owner']
    room = max(1, int(cards * OWNER_SHARE))
    if len(asked) <= room: return []
    weight = lambda card: (-CARD_SEVERITY.get(resolved[card].get('severity'), 1) * (1 + (resolved[card].get('reach') or 0)), card)
    turned = sorted(asked, key=weight)[room:]
    for card in turned:
        row = resolved[card]
        row.update(resolution='fix', change=row['recommendation'], capped=True,
                   note=(f'it would have asked you about "{row["question"]}"; with more questions than one in ten cards, '
                         f'this one mattered less (severity x reach), so its own recommendation is taken'))
    return turned


def _fix_check(card, change, revision):
    """The check of a change the assistant decided: the project's own checks gate it (eaos/waves.py: a card with no
    command of its own is kept on the gates) and the next check tells whether it is gone."""
    return {'id': 'TRIAGE-' + card, 'kind': 'human', 'invariant': 'The problem this card names is gone and nothing else changed.',
            'expected': change, 'cwd': '.', 'source_revision': revision,
            'rubric': "The change your assistant decided is made, the project's own checks pass, and the next check no longer finds it."}


def resolve(task, resolution, claim, target, out, revision):
    """The card as the assistant resolved it: `fix` makes it remediate and ready with the change and its check, `owner`
    keeps it an investigation carrying the question, `keep` closes it (the caller sets it aside)."""
    from .decisions import decide
    words = 'decided by your assistant: ' + (resolution.get('note') or resolution.get('why') or '')
    task['resolution'] = {**{k: v for k, v in resolution.items() if k not in ('checks', 'severity', 'reach')}, 'by': 'assistant', 'words': words}
    if claim is not None:
        task['decision'] = decide(claim)
        task['acceptance'], task['verify_command'] = acceptance_for(claim, target, out), verify_command_for(claim, target, out)
        task['kind'] = 'remediate' if task['decision']['kind'] == 'repair' else 'investigate'
    if resolution['resolution'] != 'fix': return task
    task['change'] = resolution['change']
    if claim is not None:
        task['rollback'] = pattern_for(claim)['rollback']
    else:
        check = _fix_check(task['id'], resolution['change'], revision)
        task['decision'] = {**task['decision'], 'kind': 'repair', 'readiness': 'ready', 'blockers': [], 'checks': [check],
                            'reason': words, 'allowed_outcomes': []}
        task['acceptance'] = [{'command': 'human review', 'expect': check['rubric']}]
        task['rollback'] = 'One commit on the fix branch; reverting it restores the screen.'
        task['kind'] = 'remediate'
    return task


def confirm(target, out, language='ar', triaged=False, reviewed=False):
    """The confirmed cards: when the triage ran in this check, its verdicts are applied once (apply_verdicts), a card
    it rejected leaves the plan (and with it the gaps) and stays only in cards.json `set_aside` with why, a
    prerequisite on it is dropped with why, and every other card carries its verdict and its claim's decision and
    priority drawn again (a doubted card needs a person's review); when the visual reviewer ran, its findings join the
    plan as design cards. The assistant's resolution of each card it confirmed (resolutions) then settles it: `fix`
    makes it ready work, `keep` closes it with why (cards.json `closed`), `owner` asks the person, at most one card in
    ten (cap_owner). The waves, milestones and cards are then drawn again. Without either every card stands as the
    rules wrote it. Writes cards.json, the record of who decided each card, and returns it."""
    from .decisions import decide
    target, out = Path(target).resolve(), Path(out).resolve()
    plan = read(out / 'plan.json')
    verdicts = _verdicts(out) if triaged else {}
    tasks = plan['tasks']
    rejected = {t['id'] for t in tasks if (verdicts.get(t['id']) or {}).get('decision') == 'reject'}
    design = _design_cards(out, [t for t in tasks if t['id'] not in rejected]) if reviewed else []
    resolved = resolutions([t for t in tasks if t['id'] not in rejected], verdicts, design)
    closed = {card for card, r in resolved.items() if r['resolution'] == 'keep'}
    turned = cap_owner(resolved, len(tasks) - len(rejected) - len(closed) + len(design))
    revision = None
    if any(r['resolution'] == 'fix' for r in resolved.values()):
        from .acceptance import fingerprint
        revision = fingerprint(target)
        for card, row in resolved.items():
            if row['resolution'] == 'fix' and card in verdicts: row['checks'] = [_fix_check(card, row['change'], revision)]
    for card, row in resolved.items():
        if card in verdicts: verdicts[card] = {**verdicts[card], **{k: row[k] for k in RESOLUTION_FIELDS if k in row}}
    if verdicts:
        claims = apply_verdicts(out, tasks, verdicts, language)
        for task in tasks:
            claim = claims.get(task.get('claim_id'))
            if claim is not None and task['id'] not in rejected:
                task['decision'], task['priority'] = decide(claim), claim.get('priority', task['priority'])
        plan['decisions'] = read(out / 'dossier.json').get('decisions', plan.get('decisions', []))
    else:
        claims = {}
    gone = rejected | closed
    kept = [t for t in tasks if t['id'] not in gone] + [t for t in design if t['id'] not in closed]
    for task in kept:
        verdict = verdicts.get(task['id'])
        if verdict: task['triage'] = {k: verdict.get(k) for k in ('decision', 'why', 'evidence', 'confidence', 'rejudged')}
        if task['id'] in resolved: resolve(task, resolved[task['id']], claims.get(task.get('claim_id')), target, out, revision)
        dropped = [ref for ref in task['prerequisites'] if ref.get('task_id') in gone]
        if dropped:
            task['prerequisites'] = [ref for ref in task['prerequisites'] if ref not in dropped]
            task['dropped_prerequisites'] = [{**ref, 'why': 'the triage set this card aside' if ref['task_id'] in rejected else
                                              'your assistant closed this card: not worth changing'} for ref in dropped]
    if rejected or verdicts or design:
        _publish_plan(target, out, plan, kept, language)
    owner = [t for t in kept if (t.get('resolution') or {}).get('resolution') == 'owner']
    record = {'schema_version': 1, 'decided_by': 'assistant' if verdicts or design else 'rules', 'kept': [t['id'] for t in kept],
              'design': [t['id'] for t in design if t['id'] not in closed],
              'set_aside': [{'card': t['id'], 'claim_id': t.get('claim_id'), 'title': t.get('title'),
                             'why': verdicts[t['id']].get('why'), 'evidence': verdicts[t['id']].get('evidence') or []}
                            for t in tasks if t['id'] in rejected],
              'closed': [{'card': t['id'], 'claim_id': t.get('claim_id'), 'title': t.get('title'), 'why': resolved[t['id']].get('why')}
                         for t in tasks + design if t['id'] in closed],
              'doubted': [{'card': card, 'why': v.get('why')} for card, v in sorted(verdicts.items())
                          if v.get('decision') == 'doubt' and card not in rejected],
              'resolved': {'fix': sum((t.get('resolution') or {}).get('resolution') == 'fix' for t in kept), 'keep': len(closed),
                           'owner': len(owner), 'turned_to_fix': len(turned)},
              'owner': [t['id'] for t in owner],
              'ready': sum(t.get('kind') == 'remediate' and (t.get('decision') or {}).get('readiness') == 'ready' for t in kept),
              'why': ('The assistant triaged every card on its own evidence: the rejected ones left the plan, the ones it '
                      'resolved are fixed, closed or asked of you.' if verdicts else
                      'No triage by an assistant in this check: every card stands as the rules wrote it.')}
    write(out / 'cards.json', record)
    return record


def _publish_plan(target, out, plan, tasks, language):
    """plan.json, the dossier's cards and PLAN/ drawn again for `tasks`."""
    order = waves(tasks)
    publish(out / PLAN_DIR, tasks, order, language)
    dossier = read(out / 'dossier.json')
    dossier['tasks'], dossier['waves'] = tasks, order
    write(out / 'dossier.json', dossier)
    milestones, sections = schedule(out, target, tasks, language)
    write(out / 'plan.json', {**plan, 'tasks': tasks, 'waves': order, 'milestones': milestones, 'sections': sections})


def _ordered(out, plan):
    """The plan orderer's steps of this check when they hold, with the cards it did not see after them in the rules'
    waves: every card of the plan once, none before its prerequisites; else None."""
    body = _load(Path(out) / 'nodes/plan_orderer/order.json', {})
    if body.get('method') != 'model' or body.get('source') != 'model' or body.get('decision') != 'reorder': return None
    tasks = {t['id']: t for t in plan['tasks']}
    steps = [dict(step) for step in body.get('steps') or []]
    seen = {task for step in steps for task in step.get('tasks') or []}
    left = [task for wave in plan.get('waves') or [] for task in wave.get('tasks') or [] if task not in seen]
    if left: steps.append({'id': 'not-placed', 'title': 'Not placed by the order', 'tasks': left,
                           'why': "The order did not place these cards; they follow in the rules' waves."})
    place = {}
    for index, step in enumerate(steps):
        for task in step.get('tasks') or []:
            if task not in tasks or task in place: return None
            place[task] = index
    if set(place) != set(tasks): return None
    if any(place.get(ref.get('task_id'), -1) > place[task] for task in tasks for ref in tasks[task].get('prerequisites') or []):
        return None
    return {**body, 'steps': steps}


SOURCE_WORDS = {'assistant': ("The assistant's order: every prerequisite kept, each step says why.",
                              'ترتيب المساعد: كل متطلب مسبق محفوظ، وكل خطوة تقول ليش.'),
                'rules': ("The rules' order: the waves of PLAN/WAVES.md.", 'ترتيب القواعد: موجات PLAN/WAVES.md.')}


def sequence(out, language='ar', ordered=False):
    """The plan's order: the plan orderer's steps when it ran in this check and its steps hold, else the rules' waves.
    Writes plan.json `order` ({source, steps, why}) and PLAN/STEPS.md; returns the order."""
    out = Path(out)
    plan = read(out / 'plan.json')
    body = _ordered(out, plan) if ordered else None
    source = 'assistant' if body else 'rules'
    steps = [{k: step.get(k) for k in ('id', 'title', 'tasks', 'why')} for step in (body or {}).get('steps') or []]
    plan['order'] = {'source': source, 'steps': steps, 'why': (body or {}).get('why') or SOURCE_WORDS[source][0]}
    write(out / 'plan.json', plan)
    ar = language == 'ar'
    lines = ['# ' + ('خطوات الخطة' if ar else 'Plan steps'), '', SOURCE_WORDS[source][1 if ar else 0], '']
    for number, step in enumerate(steps, 1):
        lines += [f"## {number}. {step['title']}", '', step['why'] or '', '', ', '.join(f'`{t}`' for t in step['tasks']), '']
    (out / PLAN_DIR).mkdir(parents=True, exist_ok=True)
    (out / PLAN_DIR / 'STEPS.md').write_text('\n'.join(lines), encoding='utf-8')
    return plan['order']
