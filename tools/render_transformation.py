"""Validate and render the execution plan; never execute stored shell commands."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
MARK = {'done': '✅', 'in_progress': '◐', 'todo': '⬜', 'blocked': '⛔'}


def tasks(plan):
    return [task for milestone in plan['milestones'] for task in milestone['tasks']]


def validate(plan, root=ROOT):
    rows = tasks(plan)
    index = {task['id']: task for task in rows}
    errors = []
    if len(index) != len(rows): errors.append('Duplicate task id')
    for task in rows:
        for field in ('steps', 'acceptance_cases', 'acceptance', 'references', 'deliverables', 'evidence_file'):
            if not task.get(field): errors.append(f"{task['id']}: missing {field}")
        if task.get('status') not in MARK: errors.append(f"{task['id']}: invalid status")
        for dep in task.get('depends_on', []):
            if dep not in index: errors.append(f"{task['id']}: unknown prerequisite {dep}")
        for reference in task.get('reference_details', []):
            if reference['availability'] == 'existing':
                if not (root / reference['path']).exists(): errors.append(f"{task['id']}: missing reference {reference['path']}")
            else:
                producer = reference.get('produced_by')
                if producer not in index or producer not in task.get('depends_on', []):
                    errors.append(f"{task['id']}: unbound future reference {reference['path']}")
                elif reference['path'] not in index[producer]['deliverables']:
                    errors.append(f"{task['id']}: prerequisite does not produce {reference['path']}")
    if errors: return errors
    placed = set()
    while len(placed) < len(rows):
        ready = [task['id'] for task in rows if task['id'] not in placed and set(task.get('depends_on', [])) <= placed]
        if not ready:
            errors.append('Dependency cycle: ' + ', '.join(sorted(set(index) - placed))); break
        placed.update(ready)
    return errors


def ready_tasks(plan):
    completed = {task['id'] for task in tasks(plan) if task['status'] == 'done'}
    ready = [task for task in tasks(plan) if task['status'] == 'todo' and set(task.get('depends_on', [])) <= completed]
    # Fix the evaluation protocol before tuning behavior to examples.
    return sorted(ready, key=lambda task: (task['id'] != 'M12.T1', [t['id'] for t in tasks(plan)].index(task['id'])))


def card(task):
    out = [f"# {task['id']} — {task['title']}", '', '> مولَّد من docs/transformation.json؛ الحالة هناك هي المرجع.', '',
           f"الحالة: {task['status']} · يعتمد على: {', '.join(task['depends_on']) or '—'}", '',
           '## اقرأ أولًا', '']
    for ref in task['reference_details']:
        suffix = 'موجود' if ref['availability'] == 'existing' else 'ينتجه ' + str(ref['produced_by'])
        out.append(f"- [{ref['path']}](../../{ref['path']}) — {suffix}")
    out += ['', '## خطوات التنفيذ', ''] + [f'{i}. {step}' for i, step in enumerate(task['steps'], 1)]
    out += ['', '## التسليم', ''] + ['- `' + path + '`' for path in task['deliverables']]
    out += ['', '## حالات القبول', ''] + ['- ' + case for case in task['acceptance_cases']]
    out += ['', '```bash', task['acceptance'], '```', '',
            '**تنبيه التنفيذ:** الاختبارات أو الأدوات الجديدة المذكورة تُكتب داخل المهمة؛ الأمر ليس دليلًا على أنها موجودة أو ناجحة الآن.', '',
            '**قبول مستقل مطلوب:** ' + ('نعم؛ عدم توفره يسجل blocked.' if task['human_required'] else 'لا؛ تبقى مراجعة صحة الدليل لازمة.'), '',
            '**سجل الدليل:** `' + task['evidence_file'] + '` وفق evidence_contract في المصدر.', '',
            '## الحدود والتراجع', '']
    out += ['- ' + limit for limit in task['out_of_scope']]
    out += ['', task.get('rollback', 'احتفظ بآخر نسخة مقبولة ولا تغيّر السجلات التاريخية.')]
    return '\n'.join(out) + '\n'


def render(plan):
    out = [f"# {plan['title']}", '', '> مولَّد من docs/transformation.json؛ لا تحرره يدويًا.', '',
           '**الحالة:** خطة تنفيذ؛ اكتمال الخطة ليس اكتمال المنتج. حالات done موروثة وليست اختبارًا أُعيد في إعداد هذه الوثيقة.', '',
           'ابدأ من [EXECUTION-START.md](EXECUTION-START.md). الاعتماديات الملزمة على مستوى المهمة؛ المرحلة حزمة تسليم وليست منعًا لبدء مهمة مستقلة.', '',
           '## قواعد التنفيذ', '']
    out += [f'{i}. {rule}' for i, rule in enumerate(plan['how_to_execute'], 1)]
    out += ['', '## المراحل والمهام', '', '| المرحلة | القيمة المطلوبة | المنجز / الإجمالي |', '| --- | --- | --- |']
    for milestone in plan['milestones']:
        done = sum(task['status'] == 'done' for task in milestone['tasks'])
        out.append(f"| {milestone['id']} — {milestone['title']} | {milestone['goal']} | {done} / {len(milestone['tasks'])} |")
    out += ['', '## بطاقات التنفيذ', '', '| المهمة | النتيجة | الاعتماديات | الحالة |', '| --- | --- | --- | --- |']
    for task in tasks(plan):
        out.append(f"| [{task['id']}](tasks/{task['id']}.md) | {task['title']} | {', '.join(task['depends_on']) or '—'} | {MARK[task['status']]} |")
    out += ['', '## بوابة التكامل', '', '```bash', plan['gate'], '```', '',
            'مشكلة البيئة أو غياب مزود/محرك ليست نجاحًا. دليل البشرية والنموذج الحي مطلوب في مهامه المحددة ولا تستبدله الاختبارات الآلية.', '',
            '## مصادر التصميم والتنفيذ', '']
    for category, refs in plan['references'].items():
        out += ['', '### ' + category, '']
        out += [f'- **{name}:** {value}' for name, value in refs.items()]
    out += ['', 'النسخ والإصدارات الخارجية مرجعها [upstreams/registry.yaml](../upstreams/registry.yaml) ونسخ المصدر المحلية. لم يُجرَ تحقق من أحدث إصدار عبر الشبكة في إعداد هذه الخطة.']
    return '\n'.join(out) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--next', action='store_true')
    args = parser.parse_args()
    plan = json.loads((ROOT / 'docs/transformation.json').read_text())
    errors = validate(plan)
    if errors:
        print('\n'.join(errors), file=sys.stderr); return 1
    if args.next:
        print(json.dumps([{'id': task['id'], 'title': task['title'], 'card': 'docs/tasks/' + task['id'] + '.md'}
                          for task in ready_tasks(plan)], ensure_ascii=False, indent=2))
        return 0
    documents = {ROOT / 'docs/TRANSFORMATION.md': render(plan)}
    documents.update({ROOT / 'docs/tasks' / (task['id'] + '.md'): card(task) for task in tasks(plan)})
    stale = []
    for path, content in documents.items():
        if args.check:
            if not path.is_file() or path.read_text() != content: stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
    if stale:
        print('Stale generated plan files: ' + ', '.join(stale), file=sys.stderr); return 1
    print(f"{'checked' if args.check else 'wrote'} {len(documents)} documents; {len(tasks(plan))} tasks; dependency graph and references valid")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
