"""The plan as documents (eaos/analysis/plan.py builds it): PLAN/TASK-*.md, one card per task with its problem, evidence,
blast radius, options, change, acceptance and rollback, and PLAN/WAVES.md, the waves it is done in.
"""
from functools import partial

from ..core.document import Document, say
from ..core.words import falsifier_of, impact_of, statement_of

PLAN_DIR = 'PLAN'


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
    document = Document(f"{task['id']}: {title_of(task, language)}", language, budget_lines=140)
    _card_head(document, task, language)
    if _card_radius(document, task, language):
        _card_options(document, task, language)
        _card_steps(document, task, language)
    return document


def _card_head(document, task, language):
    """The card's header and decision, the problem and its evidence."""
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
                      f"falsifier: {falsifier_of({'falsifier': task['evidence']['falsifier'], 'render': task.get('render')}, language)}"])


def _card_radius(document, task, language):
    """The blast radius; False when the claim names no file, so the card says so and ends there."""
    document.section('نطاق الأثر' if language == 'ar' else 'Blast radius')
    radius = task['blast_radius']
    if not task['paths']:
        document.text('هذا الادعاء يخص المنتج ككل ولا يشير إلى ملف بعينه، فلا نطاق أثر محسوبًا له؛ '
                      'حدّد الملفات المعنية أثناء التحقيق.' if language == 'ar' else
                      'This claim is about the product as a whole and names no file, so there is no computed blast radius; identify the affected files during the investigation.')
        return False
    document.bullets([
        f"الملفات المعنية: {capped(task['paths'])}" if language == 'ar' else f"files: {capped(task['paths'])}",
        f"مستوردون مباشرون ({len(radius['direct_dependents'])}): {capped(radius['direct_dependents'])}",
        f"غير مباشرين ({len(radius['transitive_dependents'])}): {capped(radius['transitive_dependents'])}",
        f"تدفقات مارّة: {capped([flow['flow_id'] + ' ' + str(flow['route']) for flow in radius['flows']])}",
        f"اختبارات مغطية: {capped(radius['covering_tests'])}",
        coverage_line(radius['coverage'], language),
        f"شركاء التغيير: {capped([partner['path'] for partner in radius['change_partners']], 5)}",
    ])
    return True


def _card_options(document, task, language):
    """The options and their verdicts, and the card's before and after."""
    tr = partial(say, language)
    document.section(tr('الخيارات', 'Options'))
    document.table([tr('الخيار', 'Option'), tr('الكلفة', 'Cost'), tr('الحكم', 'Verdict')],
                   ([['Investigate the requirement', 'unknown', 'Determine repair or retain'],
                     ['Keep current design', 'unknown', 'Valid outcome if no violation is established']]
                    if language == 'en' and task['kind'] == 'investigate' else
                    [[option.get('option'), option.get('cost'), option.get('verdict', '')] for option in task['options']]))
    if task.get('before') or task.get('after'):
        document.section(tr('قبل وبعد', 'Before and after'))
        document.bullets([str(task.get('before')), str(task.get('after'))])


def _card_steps(document, task, language):
    """The change proposed, how it is accepted, how it is rolled back, and its effort."""
    tr = partial(say, language)
    document.section(tr('التغيير المقترح', 'Proposed change'))
    localized = falsifier_of({'falsifier': task['evidence']['falsifier'], 'render': task.get('render')}, language)
    prefix = 'Establish or refute this observation before changing code: ' if language == 'en' else 'أثبت هذا الادعاء أو انقضه قبل أي تغيير: '
    document.text(prefix + localized if task['kind'] == 'investigate' else task['change'])
    document.section(tr('معيار القبول', 'Acceptance criterion'))
    document.table([tr('الأمر', 'Command'), tr('المتوقع', 'Expected')], [[step['command'], step['expect']] for step in task['acceptance']])
    document.section(tr('التراجع', 'Rollback'))
    document.text('No code changes during investigation.' if language == 'en' and task['kind'] == 'investigate' else task['rollback'])
    document.section(tr('التقدير', 'Effort'))
    document.text(tr(f"{task['effort']} · ثقة التقدير: {task['effort_confidence']}",
                     f"{task['effort']} · estimate confidence: {task['effort_confidence']}"))


def _compact_waves(document, plan, by_id, language):
    """One row per wave: every task id kept, every title deferred to its card."""
    tr = partial(say, language)
    conditions = {(wave['entry_condition'], wave['exit_condition']) for wave in plan}
    document.header([tr(*SHARED_FILE), tr(f"{len(plan)} موجات · التفاصيل في بطاقات PLAN/", f'{len(plan)} waves · the detail is in the PLAN/ cards')])
    if len(conditions) == 1:
        document.bullets(list(_condition_lines(*conditions.copy().pop(), language)))
    document.table(['#', tr('المهام', 'Tasks'), tr('النوع', 'Kinds'), tr('الأولوية', 'Top priority')],
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


# Said over every waves document.
SHARED_FILE = ('مهمتان تتشاركان ملفًا لا تقعان في موجة واحدة؛ التحقيق يسبق التغيير الذي يبني عليه.',
               'Two tasks touching the same file never share a wave; an investigation precedes the change it informs.')
WAVE_BUDGET = 140
# Chrome per wave in the sectioned form: heading, table header, separator, blank lines.
SECTION_OVERHEAD = 7


def waves_document(plan, tasks, language):
    tr = partial(say, language)
    document = Document(tr('موجات التنفيذ', 'Execution waves'), language, budget_lines=WAVE_BUDGET)
    by_id = {task['id']: task for task in tasks}
    # A section per wave costs a fixed overhead each. Past a few dozen waves that overhead alone
    # exceeds the budget and every table gets trimmed to one row, which hides the plan instead of
    # shortening it. One row per wave scales, and the titles live in the cards either way.
    if len(plan) * SECTION_OVERHEAD + len(tasks) > WAVE_BUDGET - 12:
        return _compact_waves(document, plan, by_id, language)
    conditions = {(wave['entry_condition'], wave['exit_condition']) for wave in plan}
    document.header([tr(*SHARED_FILE)])
    # Conditions identical for every wave are stated once, not repeated into the line budget.
    if len(conditions) == 1:
        document.bullets(list(_condition_lines(*conditions.copy().pop(), language)))
    for wave in plan:
        document.section(tr(f"الموجة {wave['wave']}", f"Wave {wave['wave']}"))
        document.table(['#', tr('المهمة', 'Task'), tr('النوع', 'Kind'), tr('الأولوية', 'Priority')],
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
