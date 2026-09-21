"""Render docs/TRANSFORMATION.md from docs/transformation.json.

The JSON is the only source. Editing the markdown by hand is a duplicate definition of the plan,
which is the exact failure this product exists to find.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARK = {'done': '✅', 'in_progress': '◐', 'todo': '⬜', 'blocked': '⛔'}


def render(plan):
    out = [f"# {plan['title']}", '',
           f"> مولَّد من `docs/transformation.json` — لا تحرّره يدويًا. "
           f"الأساس: الالتزام `{plan['baseline_commit']}` بتاريخ {plan['recorded_at']}.", '',
           '## قواعد التنفيذ', '']
    out += [f'{index}. {rule}' for index, rule in enumerate(plan['rules'], 1)]
    out += ['', '## نقطة البداية المقيسة', '', '| القياس | القيمة |', '| --- | --- |']
    for key, value in plan['measured_starting_point'].items():
        out.append(f"| `{key}` | {', '.join(map(str, value)) if isinstance(value, list) else value} |")
    out += ['', '## المراحل', '', '| # | المرحلة | يعتمد على | الحالة |', '| --- | --- | --- | --- |']
    for stage in plan['stages']:
        depends = ', '.join(stage['depends_on']) or '—'
        out.append(f"| {stage['id']} | {stage['title']} | {depends} | {MARK.get(stage['status'], stage['status'])} |")
    for stage in plan['stages']:
        out += ['', f"### {stage['id']} — {stage['title']}", '',
                f"**لماذا:** {stage['why']}", '', '**التغييرات:**']
        out += [f'- {change}' for change in stage['changes']]
        out += ['', '**معيار القبول (أمر يُشغَّل، لا وصف):**', '', '```bash', stage['acceptance'], '```', '',
                f"**التراجع:** {stage['rollback']}"]
    return '\n'.join(out).rstrip() + '\n'


def main():
    plan = json.loads((ROOT / 'docs/transformation.json').read_text(encoding='utf-8'))
    text = render(plan)
    target = ROOT / 'docs/TRANSFORMATION.md'
    if '--check' in sys.argv:
        current = target.read_text(encoding='utf-8') if target.is_file() else ''
        if current != text:
            print('docs/TRANSFORMATION.md is stale; run tools/render_transformation.py', file=sys.stderr)
            return 1
        return 0
    target.write_text(text, encoding='utf-8')
    print(f"wrote {target.relative_to(ROOT)} ({text.count(chr(10))} lines, {len(plan['stages'])} stages)")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
