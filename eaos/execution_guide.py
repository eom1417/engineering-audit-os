"""Render the task ledger as a compact, literal execution handoff."""
from pathlib import Path
import json


# Shared with the follow-up contract test: these tokens make an instruction
# non-executable because the implementer has to guess what was omitted.
FORBIDDEN_TOKENS = ('...', '…', 'TBD', 'TODO', 'as needed', 'and so on')


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _one_line(value):
    return ' '.join(str(value or '').split())


def _code(value):
    return f'`{_one_line(value).replace("`", "\\`")}`'


def _wave_order(plan):
    positions = {}
    for wave in plan.get('waves', []):
        number = wave.get('wave', 0)
        for position, task_id in enumerate(wave.get('tasks', [])):
            positions.setdefault(task_id, (number, position))
    return positions


def _transform_for(task, stages):
    paths = set(task.get('paths') or [])
    candidates = []
    for stage in stages:
        stage_paths = {site.get('path') for site in stage.get('sites', []) if site.get('path')}
        overlap = len(paths & stage_paths)
        if overlap:
            candidates.append((overlap, -int(stage.get('stage', 0)), stage))
    return max(candidates, default=(0, 0, None))[2]


def _load_for(task, entries):
    paths = set(task.get('paths') or [])
    matched = [entry for entry in entries if entry.get('path') in paths]
    if not matched:
        return 'none'
    parts = []
    for entry in sorted(matched, key=lambda row: row.get('path', '')):
        projection = entry.get('projection') or {}
        bottlenecks = ','.join(projection.get('bottlenecks') or []) or 'none'
        parts.append(f"{entry.get('path')}={bottlenecks}")
    return '; '.join(parts)


def _acceptance(task, transform):
    checks = task.get('acceptance') or []
    if checks:
        command = checks[0].get('command', '')
        expected = checks[0].get('expect', '')
        return command, expected
    check = (transform or {}).get('acceptance') or {}
    return check.get('command', ''), check.get('expected', '')


def _steps(task, transform):
    steps = [_one_line(task.get('change'))]
    steps.extend(_one_line(step) for step in (transform or {}).get('steps', []))
    return [step for step in steps if step]


def _localized_task(task, language):
    if language == 'ar':
        return task.get('impact') or task.get('title') or task.get('change'), task.get('change'), task.get('rollback')
    from .compose.labels import impact_of
    goal = impact_of({'impact': {'scenario': task.get('impact', '')},
                      'render': task.get('impact_render')}, 'en')
    if task.get('kind') == 'investigate':
        falsifier = (task.get('evidence') or {}).get('falsifier', '')
        return goal, f'Establish or refute this claim before any change: {falsifier}', 'No code changes during investigation.'
    values = [task.get('change'), task.get('rollback')]
    if any(any('\u0600' <= char <= '\u06ff' for char in str(value or '')) for value in values):
        reason = (task.get('decision') or {}).get('reason', '')
        return goal, reason, 'Revert the files listed for this task in one commit.'
    return goal, task.get('change'), task.get('rollback')


def _dependencies(task):
    rendered = []
    for dependency in task.get('prerequisites', []):
        if isinstance(dependency, dict):
            rendered.append(_code(dependency.get('task_id', '?')) + ': ' + _one_line(dependency.get('reason')))
        else:
            rendered.append(_code(dependency))
    return ', '.join(rendered) or 'none'


def document(plan, transform_plan, load_model, language='ar'):
    """Return one complete execution-guide Markdown document."""
    if language == 'ar':
        lines = [
            '# دليل التنفيذ', '', '## اقرأ هذا أولًا', '',
            'نفّذ البطاقات حسب الموجة ثم المعرّف. افتح الملفات الحرفية المسجلة، ونفّذ الخطوات '
            'بالترتيب، ثم شغّل أمر القبول كما هو. لا تغيّر الأمر أو النتيجة المتوقعة، ولا تتجاوز '
            'اعتمادًا غير منجز، ولا توسّع نطاق الملفات.', '',
            'توقّف واطلب قرارًا فقط إذا كان ملف أو أمر مسجل غير موجود، أو كانت اعتمادية غير منجزة، '
            'أو كان معيار القبول لا يحدد نتيجة قابلة للحسم. عند الفشل أعد الملفات المذكورة وفق نص '
            'التراجع وسجّل سبب الفشل بدل تخمين إصلاح جديد.', '',
            '## البطاقات بالترتيب', '',
        ]
    else:
        lines = [
            '# Execution guide', '', '## Read this first', '',
            'Execute cards by wave and then identifier. Open the literal files, perform the steps '
            'in order, and run the acceptance command exactly as recorded. Do not change the command '
            'or expected result, skip an unfinished dependency, or expand the file scope.', '',
            'Stop and request a decision only when a recorded file or command is absent, a dependency '
            'is unfinished, or acceptance has no decidable result. On failure, restore the listed files '
            'using the rollback instruction and record the failure instead of guessing a new repair.', '',
            '## Ordered cards', '',
        ]
    positions = _wave_order(plan)
    stages = transform_plan.get('stages', [])
    entries = load_model.get('entry_points', [])
    tasks = sorted(plan.get('tasks', []),
                   key=lambda task: (*positions.get(task.get('id'), (10**9, 10**9)), task.get('id', '')))
    for task in tasks:
        task_id = task.get('id', '?')
        wave = positions.get(task_id, ('unassigned', 0))[0]
        transform = _transform_for(task, stages)
        command, expected = _acceptance(task, transform)
        goal, change, rollback = _localized_task(task, language)
        if language == 'en' and command == 'human review / مراجعة هندسية':
            command = 'human review'
        files = ', '.join(_code(path) for path in task.get('paths', [])) or 'none'
        steps = [change, *(transform or {}).get('steps', [])]
        numbered = ' '.join(f'{index}. {_one_line(step)}' for index, step in enumerate(steps, 1) if step)
        rollback = rollback or (transform or {}).get('rollback') or 'none'
        lines.append(
            f"- **{task_id} / wave {wave}** — Goal: {_one_line(goal)}<br>"
            f"Files: {files}<br>Steps: {numbered}<br>"
            f"Acceptance: {_code(command)} → {_one_line(expected)}<br>"
            f"Rollback: {_one_line(rollback)}<br>Dependencies: {_dependencies(task)}<br>"
            f"Load constraint: {_one_line(_load_for(task, entries))}"
        )
    return '\n'.join(lines) + '\n'


def render(out, language='ar'):
    """Read the three pipeline records and write EXECUTION-GUIDE.md."""
    out = Path(out)
    body = document(_read(out / 'plan.json'), _read(out / 'transform-plan.json'),
                    _read(out / 'load-model.json'), language=language)
    (out / 'EXECUTION-GUIDE.md').write_text(body, encoding='utf-8')
    return {'tasks': body.count('\n- **'), 'lines': len(body.splitlines())}
