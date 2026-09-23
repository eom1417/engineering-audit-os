"""Render docs/CAPABILITY-PLAN.md from docs/capability-plan.json, and refuse a plan that cannot be executed.

The JSON is the only source. A task a model cannot execute — no acceptance command, no files, a
dependency that does not exist, an indicator nobody measures — is caught here rather than by the
model that tries to run it.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SOURCE = ROOT / 'docs/capability-plan.json'
TARGET = ROOT / 'docs/CAPABILITY-PLAN.md'
MARK = {'done': '✅', 'in_progress': '◐', 'todo': '⬜', 'blocked': '⛔'}
VAGUE = ('…', 'إلخ', 'etc.', 'ونحوه', 'TBD', 'يُفضَّل', 'ربما', 'maybe')


def tasks(plan):
    return [task for milestone in plan['milestones'] for task in milestone['tasks']]


def milestone_status(milestone):
    """A milestone's status is what its tasks say: done when all are done, blocked when only blocked ones remain."""
    states = {task['status'] for task in milestone['tasks']}
    if states <= {'done'}:
        return 'done'
    if states <= {'done', 'blocked'}:
        return 'blocked'
    return 'in_progress' if states & {'done', 'in_progress'} else 'todo'


def counted(plan):
    statuses = [task['status'] for task in tasks(plan)]
    return {'milestones': len(plan['milestones']), 'tasks': len(statuses),
            **{name: statuses.count(name) for name in ('done', 'todo', 'blocked')}}


def validate(plan):
    from eaos.capability import DOMAINS
    problems = []
    for milestone in plan['milestones']:
        if milestone['status'] != milestone_status(milestone):
            problems.append(f"{milestone['id']}: status {milestone['status']!r} but its tasks say "
                            f"{milestone_status(milestone)!r}")
    if plan.get('totals') != counted(plan):
        problems.append(f"totals {plan.get('totals')} disagree with the tasks {counted(plan)}")
    known = {task['id'] for task in tasks(plan)}
    milestones = {milestone['id'] for milestone in plan['milestones']}
    seen = set()
    for milestone in plan['milestones']:
        for reference in milestone.get('depends_on', []):
            if reference not in milestones:
                problems.append(f"{milestone['id']}: depends on unknown milestone {reference}")
        for task in milestone['tasks']:
            identifier = task['id']
            if identifier in seen:
                problems.append(f'{identifier}: declared twice')
            seen.add(identifier)
            if not task.get('acceptance', '').strip():
                problems.append(f'{identifier}: no acceptance command')
            if not task.get('files'):
                problems.append(f'{identifier}: names no files to touch')
            if not task.get('steps'):
                problems.append(f'{identifier}: has no steps')
            if not task.get('rollback', '').strip():
                problems.append(f'{identifier}: no rollback')
            for reference in task.get('depends_on', []):
                if reference not in known:
                    problems.append(f'{identifier}: depends on unknown task {reference}')
                if reference == identifier:
                    problems.append(f'{identifier}: depends on itself')
            indicator = (task.get('moves') or {}).get('indicator')
            if indicator and indicator not in ('n/a', 'overall'):
                domain = indicator.split('.', 1)[0]
                if domain not in DOMAINS:
                    problems.append(f'{identifier}: moves an indicator in unknown domain {domain}')
            for step in task['steps']:
                for word in VAGUE:
                    if word in step:
                        problems.append(f'{identifier}: a step contains the vague token {word!r}')
    order = [task['id'] for task in tasks(plan)]
    position = {identifier: index for index, identifier in enumerate(order)}
    for task in tasks(plan):
        for reference in task.get('depends_on', []):
            if reference in position and position[reference] > position[task['id']]:
                problems.append(f"{task['id']}: listed before its dependency {reference}")
    return sorted(set(problems))


def ready(plan):
    done = {task['id'] for task in tasks(plan) if task['status'] == 'done'}
    return [task for task in tasks(plan)
            if task['status'] == 'todo' and all(ref in done for ref in task.get('depends_on', []))]


def render(plan):
    out = [f"# {plan['title']}", '',
           f"> مولَّد من `docs/capability-plan.json` — لا تحرّره يدويًا. "
           f"الأساس: `{plan['baseline_commit']}` · {plan['recorded_at']}.", '',
           f"**الهدف:** {plan['goal']}", '',
           '## الأساس المقيس عند بدء الخطة', '',
           '> هذه أرقام نقطة البداية، لا اليوم. القياس الحالي في `docs/CAPABILITY-SCORE.md`.', '',
           '| المجال | الدرجة | الهدف |', '| --- | --- | --- |']
    base = plan['measured_baseline']
    for name, value in base.items():
        if name in ('overall', 'domains_at_target', 'domains_total'):
            continue
        out.append(f"| {name} | {value} | 0.80 |")
    out += ['', f"**الإجمالي {base['overall']}** — {base['domains_at_target']} من "
                f"{base['domains_total']} مجالات بلغت الهدف.", '',
            '## كيف ينفّذ أي نموذج هذه الخطة', '']
    out += plan['how_any_model_executes_this']
    out += ['', '**بوابة العبور بعد كل مهمة:**', '', '```bash', plan['gate'], '```', '',
            '## قواعد غير قابلة للتفاوض', '']
    out += [f'{index}. {rule}' for index, rule in enumerate(plan['rules'], 1)]
    out += ['', '## المراجع', '', '| ما هو | أين |', '| --- | --- |']
    out += [f'| {key} | `{value}` |' for key, value in plan['references'].items()]
    out += ['', '## المعالم', '', '| # | المعلم | يعتمد على | المهام | الحالة |', '| --- | --- | --- | --- | --- |']
    for milestone in plan['milestones']:
        done = sum(1 for task in milestone['tasks'] if task['status'] == 'done')
        out.append(f"| {milestone['id']} | {milestone['title']} | "
                   f"{', '.join(milestone.get('depends_on', [])) or '—'} | "
                   f"{done}/{len(milestone['tasks'])} | {MARK.get(milestone['status'], milestone['status'])} |")
    for milestone in plan['milestones']:
        out += ['', f"## {milestone['id']} — {milestone['title']}", '', f"**الهدف:** {milestone['goal']}"]
        if milestone.get('measured_problem'):
            out += ['', f"**المشكلة المقيسة:** {milestone['measured_problem']}"]
        if milestone.get('the_eight_questions'):
            out += ['', '**الأسئلة الثمانية:**', '']
            out += [f'- `{line}`' for line in milestone['the_eight_questions']]
        if milestone.get('human_required'):
            out += ['', '> هذا المعلم لا يستطيع نموذج إتمامه وحده.']
        for task in milestone['tasks']:
            moves = task.get('moves') or {}
            out += ['', f"### {task['id']} — {task['title']} {MARK.get(task['status'], '')}", '',
                    f"**لماذا:** {task['why']}"]
            if moves.get('indicator') and moves['indicator'] != 'n/a':
                out.append(f"**يحرّك:** `{moves['indicator']}` من `{moves.get('from')}` إلى `{moves.get('to')}`")
            if task.get('depends_on'):
                out.append(f"**يعتمد على:** {', '.join(task['depends_on'])}")
            out += ['', '**الملفات:**', ''] + [f'- `{name}`' for name in task['files']]
            out += ['', '**الخطوات:**', ''] + [f'{index}. {step}' for index, step in enumerate(task['steps'], 1)]
            if task.get('references'):
                out += ['', '**مراجع:** ' + ' · '.join(f'`{item}`' for item in task['references'])]
            out += ['', '**معيار القبول:**', '', '```bash', task['acceptance'], '```', '',
                    f"**التراجع:** {task['rollback']}"]
    return '\n'.join(out).rstrip() + '\n'


def main(argv):
    plan = json.loads(SOURCE.read_text(encoding='utf-8'))
    if '--check' not in argv:
        for milestone in plan['milestones']:
            milestone['status'] = milestone_status(milestone)
        plan['totals'] = counted(plan)
        SOURCE.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    problems = validate(plan)
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1
    text = render(plan)
    if '--check' in argv:
        current = TARGET.read_text(encoding='utf-8') if TARGET.is_file() else ''
        if current != text:
            print('docs/CAPABILITY-PLAN.md is stale; run tools/render_capability_plan.py', file=sys.stderr)
            return 1
        print(f"checked {len(tasks(plan))} tasks; next ready: "
              f"{', '.join(task['id'] for task in ready(plan)[:3]) or 'none'}")
        return 0
    TARGET.write_text(text, encoding='utf-8')
    print(f"wrote {TARGET.relative_to(ROOT)} ({text.count(chr(10))} lines, {len(tasks(plan))} tasks); "
          f"next ready: {', '.join(task['id'] for task in ready(plan)[:3]) or 'none'}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
