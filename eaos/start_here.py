"""START-HERE.md: the first page of every report, in plain words (eaos/plain.py).

Written by the reports stage of every check, and read by the guided commands. Counts come from plan.json;
nothing is scored or invented. Its own module, because both the pipeline and eaos/guided.py need it.
"""
import json
import subprocess
from pathlib import Path

from . import plain
from .compose.labels import who_decided
from .decisions import ready as is_ready


def _read_json(path, empty):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else empty


def summary_counts(report):
    plan = _read_json(Path(report) / 'plan.json', {'tasks': []})
    tasks = plan.get('tasks') or []
    ready = [t for t in tasks if is_ready(t)]
    # A tool that broke, said with the counts: the check goes on from it (audit again_from=engines engines=[...]).
    engines = _read_json(Path(report) / 'run-manifest.json', {}).get('stages', {}).get('engines') or {}
    return {'problems': len(tasks), 'ready': len(ready), 'decide': len(tasks) - len(ready),
            'failed_tools': sorted((engines.get('detail') or {}).get('tools_failed') or {})}


def _say(ar, arabic, english): return arabic if ar else english


def _grouped(tasks):
    groups = {}
    for task in tasks:
        groups.setdefault(plain.kind(task), []).append(task)
    rank = lambda p: (plain.ORDER.index(p) if p in plain.ORDER else len(plain.ORDER), -len(groups[p]))
    return groups, sorted(groups, key=rank)


def _summary_lines(counts, ar):
    return ['## ' + _say(ar, 'الخلاصة', 'In short'), '',
            _say(ar, f"- وجدت **{counts['problems']}** مشكلة.", f"- I found **{counts['problems']}** problems."),
            _say(ar, f"- **{counts['ready']}** منها يستطيع EAOS إصلاحها آليًا، ويتحقق بعد كل إصلاح أن برنامجك لم ينكسر.",
                 f"- **{counts['ready']}** of them EAOS can fix automatically, checking after each fix that your app still works."),
            _say(ar, f"- **{counts['decide']}** تحتاج قرارك أو نظرة شخص قبل أي تغيير.",
                 f"- **{counts['decide']}** need your decision, or a person's look, before any change."), '',
            '## ' + _say(ar, 'أهم المشاكل', 'The main problems'), '']


def _pattern_lines(index, pattern, rows, lang, ar):
    title, why = plain.problem(pattern, lang)
    ready = sum(map(is_ready, rows))
    example = next((p for t in rows for p in t.get('paths') or []), '')
    shown = f" · {_say(ar, 'مثال', 'example')}: `{example}`" if example else ''
    return [f"{index}. **{title}** ({len(rows)})", f"   {why}",
            f"   {_say(ar, 'يمكن إصلاحه آليًا', 'Can be fixed automatically')}: {ready} {_say(ar, 'من', 'of')} {len(rows)}" + shown, '']


def _problem_lines(report, tasks, counts, lang, ar):
    groups, ordered = _grouped(tasks)
    lines = _summary_lines(counts, ar)
    for index, pattern in enumerate(ordered[:5], 1):
        lines += _pattern_lines(index, pattern, groups[pattern], lang, ar)
    rest = [f"{plain.problem(p, lang)[0]} ({len(groups[p])})" for p in ordered[5:]]
    if rest:
        lines += [_say(ar, 'وأنواع أخرى: ', 'And other kinds: ') + _say(ar, '، ', ', ').join(rest), '']
    target = _read_json(report / 'target-architecture.json', {})
    lines += ['## ' + _say(ar, 'من قرر', 'Who decided'), '', who_decided(target, lang), '']
    lines += ['## ' + _say(ar, 'ما أنصح به', 'What I recommend'), '',
              _say(ar, 'ابدأ بالإصلاحات الآلية: هي الأكثر أمانًا، وكل واحدة تُجرَّب في نسخة منفصلة من مشروعك قبل أن تراها.',
                   'Start with the automatic fixes: they are the safest, and each is tried on a separate copy of your project before you see it.'), '']
    return lines


def _incomplete_lines(report, lang, ar):
    stages = _read_json(report / 'run-manifest.json', {}).get('stages') or {}
    missing = [name for name, row in stages.items() if row.get('status') in ('failed', 'not_reached')]
    if not missing: return []
    return ['## ' + _say(ar, 'ما لم يكتمل', 'What did not complete'), '',
            _say(ar, 'هذه الأجزاء من الفحص لم تكتمل، فما وجدته فيها قد يكون ناقصًا: ',
                 'These parts of the check did not complete, so what they would have found may be missing: ')
            + _say(ar, '، ', ', ').join(plain.stage(name, lang) for name in missing), '']


def _one_page_lines(report, ar):
    if not (report / 'human' / 'index.html').is_file(): return []
    return ['## ' + _say(ar, 'التقرير في صفحة واحدة', 'The report on one page'), '',
            _say(ar, 'افتح `human/index.html` في المتصفح: الملخص، والفجوات والمخاطر، وخريطة البنية، والخطة، بالعربية والإنجليزية.',
                 'Open `human/index.html` in a browser: the summary, gaps and risks, structure map and plan, in Arabic and English.'), '']


def _closing_lines(ar):
    return ['## ' + _say(ar, 'الخطوة التالية', 'Next step'), '', '```', 'eaos next', '```', '',
            '## ' + _say(ar, 'للتفاصيل التقنية', 'Technical detail'), '',
            _say(ar, 'للمطوّر أو لمساعدك الذكي: ', 'For a developer or your AI assistant: ')
            + '`CURRENT-STATE.md` · `TARGET-STATE.md` · `GAP-AND-STRATEGY.md` · `EXECUTION-PLAN.md` · `plan.json`', '']


def project_name(folder):
    """The project's name: its folder's, or the project's for EAOS's own copy of a branch (eaos/guided.py source)."""
    folder = Path(folder)
    if not folder.name.startswith('checkout'): return folder.name
    origin = subprocess.run(['git', '-C', str(folder), 'config', '--get', 'remote.origin.url'], capture_output=True, text=True).stdout.strip()
    return Path(origin).name if origin else folder.name


def start_here(report, lang, name):
    """START-HERE.md: one page in plain words. Counts come from plan.json; nothing is scored or invented."""
    report = Path(report)
    tasks = _read_json(report / 'plan.json', {'tasks': []}).get('tasks') or []
    ar = lang == 'ar'
    lines = [f"# {_say(ar, 'ابدأ هنا', 'Start here')}: {name}", '']
    if not tasks:
        lines += [_say(ar, 'لم أجد مشاكل تحتاج إصلاحًا.', 'I found no problems that need fixing.'), '']
    else:
        lines += _problem_lines(report, tasks, summary_counts(report), lang, ar)
    lines += _incomplete_lines(report, lang, ar)
    lines += _one_page_lines(report, ar)
    lines += _closing_lines(ar)
    page = report / 'START-HERE.md'
    page.write_text('\n'.join(lines), encoding='utf-8')
    return page
