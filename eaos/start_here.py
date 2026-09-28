"""START-HERE.md: the first page of every report, in plain words (eaos/plain.py).

Written by the compose stage for every audit, and read by the guided commands. Counts come from plan.json;
nothing is scored or invented. Its own module, because both the pipeline and eaos/guided.py need it.
"""
import json
from pathlib import Path

from . import plain


def summary_counts(report):
    plan = json.loads((Path(report) / 'plan.json').read_text(encoding='utf-8')) if (Path(report) / 'plan.json').is_file() else {'tasks': []}
    tasks = plan.get('tasks') or []
    ready = [t for t in tasks if t.get('kind') == 'remediate' and (t.get('decision') or {}).get('readiness') == 'ready']
    return {'problems': len(tasks), 'ready': len(ready), 'decide': len(tasks) - len(ready)}


def start_here(report, lang, name):
    """START-HERE.md: one page in plain words. Counts come from plan.json; nothing is scored or invented."""
    report = Path(report)
    plan = json.loads((report / 'plan.json').read_text(encoding='utf-8')) if (report / 'plan.json').is_file() else {'tasks': []}
    tasks = plan.get('tasks') or []
    counts = summary_counts(report)
    groups = {}
    for task in tasks:
        groups.setdefault(task.get('pattern') or 'generic', []).append(task)
    ordered = sorted(groups, key=lambda p: (plain.ORDER.index(p) if p in plain.ORDER else len(plain.ORDER), -len(groups[p])))
    ar = lang == 'ar'
    lines = [f"# {'ابدأ هنا' if ar else 'Start here'}: {name}", '']
    if not tasks:
        lines += ['لم أجد مشاكل تحتاج إصلاحًا.' if ar else 'I found no problems that need fixing.', '']
    else:
        lines += ['## ' + ('الخلاصة' if ar else 'In short'), '',
                  (f"- وجدت **{counts['problems']}** مشكلة." if ar else f"- I found **{counts['problems']}** problems."),
                  (f"- **{counts['ready']}** منها يستطيع EAOS إصلاحها آليًا، ويتحقق بعد كل إصلاح أن برنامجك لم ينكسر." if ar else
                   f"- **{counts['ready']}** of them EAOS can fix automatically, checking after each fix that your app still works."),
                  (f"- **{counts['decide']}** تحتاج قرارك أو نظرة شخص قبل أي تغيير." if ar else
                   f"- **{counts['decide']}** need your decision, or a person's look, before any change."), '',
                  '## ' + ('أهم المشاكل' if ar else 'The main problems'), '']
        for index, pattern in enumerate(ordered[:5], 1):
            title, why = plain.problem(pattern, lang)
            rows = groups[pattern]
            ready = sum((t.get('decision') or {}).get('readiness') == 'ready' and t.get('kind') == 'remediate' for t in rows)
            example = next((p for t in rows for p in t.get('paths') or []), '')
            lines += [f"{index}. **{title}** ({len(rows)})", f"   {why}",
                      f"   {'يمكن إصلاحه آليًا' if ar else 'Can be fixed automatically'}: {ready} {'من' if ar else 'of'} {len(rows)}"
                      + (f" · {'مثال' if ar else 'example'}: `{example}`" if example else ''), '']
        rest = [f"{plain.problem(p, lang)[0]} ({len(groups[p])})" for p in ordered[5:]]
        if rest:
            lines += [('وأنواع أخرى: ' if ar else 'And other kinds: ') + ('، ' if ar else ', ').join(rest), '']
        lines += ['## ' + ('ما أنصح به' if ar else 'What I recommend'), '',
                  ('ابدأ بالإصلاحات الآلية: هي الأكثر أمانًا، وكل واحدة تُجرَّب في نسخة منفصلة من مشروعك قبل أن تراها.' if ar else
                   'Start with the automatic fixes: they are the safest, and each is tried on a separate copy of your project before you see it.'), '']
    manifest = report / 'run-manifest.json'
    if manifest.is_file():
        stages = json.loads(manifest.read_text(encoding='utf-8')).get('stages') or {}
        missing = [name for name, row in stages.items() if row.get('status') in ('failed', 'not_reached')]
        if missing:
            lines += ['## ' + ('ما لم يكتمل' if ar else 'What did not complete'), '',
                      ('هذه الأجزاء من الفحص لم تكتمل، فما وجدته فيها قد يكون ناقصًا: ' if ar else
                       'These parts of the check did not complete, so what they would have found may be missing: ')
                      + ('، ' if ar else ', ').join(plain.stage(name, lang) for name in missing), '']
    if (report / 'human' / 'index.html').is_file():
        lines += ['## ' + ('التقرير في صفحة واحدة' if ar else 'The report on one page'), '',
                  ('افتح `human/index.html` في المتصفح: الملخص، والفجوات والمخاطر، وخريطة البنية، والخطة، بالعربية والإنجليزية.' if ar else
                   'Open `human/index.html` in a browser: the summary, gaps and risks, structure map and plan, in Arabic and English.'), '']
    lines += ['## ' + ('الخطوة التالية' if ar else 'Next step'), '', '```', 'eaos next', '```', '',
              '## ' + ('للتفاصيل التقنية' if ar else 'Technical detail'), '',
              ('للمطوّر أو لمساعدك الذكي: ' if ar else 'For a developer or your AI assistant: ')
              + '`CURRENT-STATE.md` · `TARGET-STATE.md` · `GAP-AND-STRATEGY.md` · `EXECUTION-PLAN.md` · `plan.json`', '']
    page = report / 'START-HERE.md'
    page.write_text('\n'.join(lines), encoding='utf-8')
    return page
