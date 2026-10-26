"""START-HERE.md: the first page of every report, in plain words (eaos/core/language/plain.py).

Written by the reports stage of every check, and read by the guided commands. Counts come from plan.json;
nothing is scored or invented. Its own module, because both the pipeline and eaos/journeys/guided/ need it.
"""
import json
import subprocess
from pathlib import Path

from . import layers
from ...core.language import plain
from ...core.language.words import who_decided
from ...core.contracts.decisions import ready as is_ready
from ...analysis.target_state.repair_or_rebuild import decide
from .run import big_gaps


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
    lines += _decision_lines(decide(report), ar)
    lines += ['## ' + _say(ar, 'ما أنصح به', 'What I recommend'), '',
              _say(ar, 'ابدأ بالإصلاحات الآلية: هي الأكثر أمانًا، وكل واحدة تُجرَّب في نسخة منفصلة من مشروعك قبل أن تراها.',
                   'Start with the automatic fixes: they are the safest, and each is tried on a separate copy of your project before you see it.'), '']
    return lines


def _span(minutes, ar):
    """'3–8 minutes', or in hours from two hours up."""
    if minutes[1] < 120: return f"{minutes[0]}–{minutes[1]} " + _say(ar, 'دقيقة', 'minutes')
    return f"{minutes[0] / 60:.0f}–{minutes[1] / 60:.0f} " + _say(ar, 'ساعة', 'hours')


def _decision_lines(found, ar):
    """Repair or rebuild (eaos/analysis/target_state/repair_or_rebuild.py): the recommendation and each option's effort and time."""
    if not found: return []
    repair, rebuild, lang = found['options']['repair'], found['options']['rebuild'], 'ar' if ar else 'en'
    chosen = _say(ar, 'الإصلاح', 'repair') if found['recommend'] == 'repair' else _say(ar, 'إعادة البناء', 'rebuild')
    small, medium, large = (repair['sizes'][size] for size in 'SML')
    return ['## ' + _say(ar, 'أصلح أو أعيد البناء؟', 'Repair or rebuild?'), '',
            _say(ar, f'**أنصح بـ{chosen}.** ', f'**I recommend: {chosen}.** ') + found['why'][lang], '',
            _say(ar, f"- الإصلاح: {repair['cards']} بطاقة (صغيرة {small}، متوسطة {medium}، كبيرة {large})، تمس {repair['files']} ملفًا، نحو {_span(repair['minutes'], ar)}.",
                 f"- Repair: {repair['cards']} cards ({small} small, {medium} medium, {large} large), touching {repair['files']} files, about {_span(repair['minutes'], ar)}."),
            _say(ar, f"- إعادة البناء: {rebuild['files']} ملفًا في {rebuild['components']} جزءًا تُكتب من جديد، نحو {_span(rebuild['minutes'], ar)}.",
                 f"- Rebuild: {rebuild['files']} files in {rebuild['components']} parts written anew, about {_span(rebuild['minutes'], ar)}."),
            '', found['basis'][lang], '']


def _this_run(report):
    """The record of this check: its checkpoint while it runs (the reports are written before its manifest), else its
    manifest."""
    return _read_json(report / 'run-checkpoint.json', None) or _read_json(report / 'run-manifest.json', {})


def _incomplete_lines(report, lang, ar):
    stages = _this_run(report).get('stages') or {}
    missing = [name for name, row in stages.items() if row.get('status') in ('failed', 'not_reached')]
    if not missing: return []
    return ['## ' + _say(ar, 'ما لم يكتمل', 'What did not complete'), '',
            _say(ar, 'هذه الأجزاء من الفحص لم تكتمل، فما وجدته فيها قد يكون ناقصًا: ',
                 'These parts of the check did not complete, so what they would have found may be missing: ')
            + _say(ar, '، ', ', ').join(plain.stage(name, lang) for name in missing), '']


def _path_lines(report, lang, ar):
    """What a check of some paths looked at, and what it did not: kept from an earlier check (its date), or not seen."""
    from ...core.contracts.check_paths import PATHS
    manifest = _this_run(report)
    paths = manifest.get('paths') or ['complete']
    if 'complete' in paths: return []
    name = lambda p: PATHS[p]['names'][1 if ar else 0]
    others = [p for p in PATHS if p not in paths and p != 'complete']
    return ['## ' + _say(ar, 'مسار هذا الفحص', "This check's path"), '',
            _say(ar, 'تبع هذا الفحص: ', 'This check followed: ') + _say(ar, '، ', ', ').join(name(p) for p in paths) + '. '
            + _say(ar, 'ولم ينظر في: ', 'It did not look at: ') + _say(ar, '، ', ', ').join(name(p) for p in others) + _say(ar, '؛ ', '; ')
            + _not_looked_at(manifest, ar), '']


def _not_looked_at(manifest, ar):
    """What became of the paths a check did not look at: their results kept from an earlier check (its date), or none."""
    kept = sorted(row['checked_at'] for row in (manifest.get('stages') or {}).values() if row.get('checked_at'))
    return (_say(ar, f'نتائجها هنا من فحص {kept[0][:10]}.', f'their results here are those of the check of {kept[0][:10]}.') if kept else
            _say(ar, 'لم تُفحص هذه المرة: افحص مسارها، أو الفحص الشامل، لتراها.', 'they were not checked this time: check their path, or the complete check, to see them.'))


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
    """The project's name: its folder's, or the project's for EAOS's own copy of a branch (eaos/journeys/guided/ source)."""
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
    gaps = big_gaps(_this_run(report), lang)          # the coverage ledger's big gaps, in red before anything else
    if gaps: lines += [*gaps, '']
    lines += layers.critical(report, lang)            # a broken critical boundary, in red at the top (M6.11)
    if not tasks:
        lines += [_say(ar, 'لم أجد مشاكل تحتاج إصلاحًا.', 'I found no problems that need fixing.'), '']
    else:
        lines += _problem_lines(report, tasks, summary_counts(report), lang, ar)
    lines += layers.lines(report, lang)
    lines += _path_lines(report, lang, ar) + _incomplete_lines(report, lang, ar)
    lines += _one_page_lines(report, ar)
    lines += _closing_lines(ar)
    page = report / 'START-HERE.md'
    page.write_text('\n'.join(lines), encoding='utf-8')
    return page
