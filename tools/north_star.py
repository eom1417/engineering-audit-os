"""Render docs/NORTH-STAR.md from docs/north-star.json, and say how far the product is from its destination.

The JSON is the only source. An indicator with no value counts as zero: a capability is not partly
there because its machinery exists, only because its output on the corpus got better.

Usage:  python tools/north_star.py            # write docs/NORTH-STAR.md
        python tools/north_star.py --check    # fail if the record is invalid or the document is stale
        python tools/north_star.py --score    # print the scores as JSON
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'docs/north-star.json'
TARGET = ROOT / 'docs/NORTH-STAR.md'
NEEDS = {'none': 'نموذج أو مطوّر', 'model_provider': 'يحتاج مزوّد نموذج', 'human': 'يحتاج إنسانًا من خارج المشروع'}


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
        for moved in task.get('moves', []):
            if moved not in known: problems.append(f"{task['id']}: moves unknown indicator {moved}")
        for reference in task.get('depends_on', []):
            if reference not in order: problems.append(f"{task['id']}: depends on unknown task {reference}")
            elif order.index(reference) > order.index(task['id']): problems.append(f"{task['id']}: listed before {reference}")
    return problems


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


def percent(value):
    return '—' if value is None else f'{round(value * 100)}%'


def render(record):
    scores = score(record)
    out = [f"# {record['title']}", '',
           '> مولَّد من `docs/north-star.json` — لا تحرّره يدويًا. أعد توليده بـ`python tools/north_star.py`. '
           f"القياس: {record['measured_at']} على الالتزام `{record['measured_at_commit']}`.", '',
           f"## أين نحن: **{scores['overall_percent']}%** من الوجهة", '',
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
    out += ['', '## أين المسافة المتبقية', '', 'مرتبة بـ الوزن × (1 − الدرجة): أين يحرّك العمل النسبة أكثر.', '',
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
    out += ['', '## خطة التحول', '', 'كل مهمة لها أمر قبول يفشل اليوم وينجح حين تكتمل. '
            'أوامر `measure` يبنيها المعلم NS1 أولًا، ولذلك يسبق كل ما بعده.', '',
            '| المعلم | الهدف | المهام |', '| --- | --- | --- |']
    out += [f"| {milestone['id']} {milestone['title']} | {milestone['goal']} | {len(milestone['tasks'])} |"
            for milestone in record['milestones']]
    for milestone in record['milestones']:
        out += ['', f"### {milestone['id']} — {milestone['title']}", '', f"**الهدف:** {milestone['goal']}"]
        for task in milestone['tasks']:
            out += ['', f"#### {task['id']} — {task['title']}", '',
                    f"**يحرّك:** {', '.join(task['moves'])} · **ينفّذه:** {NEEDS[task['needs']]}"
                    + (f" · **يعتمد على:** {', '.join(task['depends_on'])}" if task['depends_on'] else ''), '',
                    '**الملفات:** ' + ' · '.join(f'`{name}`' for name in task['files']), '']
            out += [f'{index}. {step}' for index, step in enumerate(task['steps'], 1)]
            out += ['', '```bash', task['acceptance'], '```', '', f"**التراجع:** {task['rollback']}"]
    out += ['', '## قواعد التطوير نحو الوجهة', ''] + [f'{index}. {rule}' for index, rule in enumerate(record['rules'], 1)]
    return '\n'.join(out).rstrip() + '\n'


def main(argv):
    # An unknown command must fail: every acceptance command in the plan calls `measure`, and a
    # renderer that ignored it would pass them all before NS1.T2 builds it.
    unknown = [arg for arg in argv if arg not in ('--check', '--score')]
    if unknown:
        print(f"unknown command {' '.join(unknown)}; fetch and measure are built by milestone NS1", file=sys.stderr)
        return 2
    record = json.loads(SOURCE.read_text(encoding='utf-8'))
    problems = validate(record)
    if problems:
        for problem in problems: print(problem, file=sys.stderr)
        return 1
    if '--score' in argv:
        print(json.dumps(score(record), ensure_ascii=False, indent=2))
        return 0
    text = render(record)
    if '--check' in argv:
        if (TARGET.read_text(encoding='utf-8') if TARGET.is_file() else '') != text:
            print('docs/NORTH-STAR.md is stale; run python tools/north_star.py', file=sys.stderr)
            return 1
        print(f"north star: {score(record)['overall_percent']}%")
        return 0
    TARGET.write_text(text, encoding='utf-8')
    print(f"wrote {TARGET.relative_to(ROOT)}; north star: {score(record)['overall_percent']}%")
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
