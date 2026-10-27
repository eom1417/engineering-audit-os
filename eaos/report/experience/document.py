"""EXPERIENCE.md and the Studio's experience/story.json (M10.8), both from story(report) (eaos/report/experience/story.py).

    write(report, language)   <report>/EXPERIENCE.md in Arabic ('ar') or English ('en'), and <report>/experience/story.json;
                              (the page's path, the data's path)

The page tells each persona's goals step by step with the picture of each step (relative Markdown images), the
difficulties ranked, the time per task, the tickets, the replays that broke, the services the data did not cover, and
the records that are missing; a missing record is said, never a failure. Each sentence keeps its two languages side
by side (_say), as eaos/report/documents/layers.py does.
"""
import json
from pathlib import Path
from urllib.parse import quote

from ..documents.markdown import Page, clip, escape
from .story import FOLDER, story

PAGE = 'EXPERIENCE.md'
DATA = 'story.json'
STATUS = {'reached': ('وصل إلى هدفه', 'reached the goal'), 'stuck': ('علق', 'got stuck'), 'stopped': ('توقف قبل الهدف', 'stopped before the goal'),
          'blocked': ('لم يبدأ: انتظر هدفًا لم يتم', 'blocked: waited for a goal that did not finish'), 'not_run': ('لم يُجرَّب', 'not run')}
VERDICT = {'confirm': ('مؤكدة', 'confirmed'), 'doubt': ('مشكوك فيها', 'in doubt'), 'reject': ('مرفوضة', 'rejected')}
KIND = {'find': ('صعب إيجاده', 'hard to find'), 'understand': ('صعب فهمه', 'hard to understand'), 'finish': ('صعب إكماله', 'hard to finish'),
        'error': ('خطأ', 'an error'), 'stuck': ('علق', 'stuck')}
SEVERITY = {'high': ('عالية', 'high'), 'medium': ('متوسطة', 'medium'), 'low': ('منخفضة', 'low')}


def _say(ar, arabic, english): return arabic if ar else english


def _word(table, key, ar):
    return table[key][0 if ar else 1] if key in table else str(key or '-')


def _cell(text):
    return escape(clip(text if text is not None else '-', 120)).replace('|', '\\|')


def _table(page, head, rows):
    page.lines += ['', '| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head), *('| ' + ' | '.join(map(_cell, r)) + ' |' for r in rows)]


def _image(page, alt, path):
    if path: page.lines += ['', f'![{escape(alt)}]({quote(path)})']


def _overview(page, told, ar):
    goals = told['time']
    reached = sum(g['status'] == 'reached' for g in goals)
    red = told['replays']['summary'].get('red', 0)
    page.para(_say(ar, f'جُرّب {len(goals)} هدفًا لـ{len(told["personas"])} شخصية: وصل منها {reached}. '
                       f'{len(told["difficulties"]["ranked"])} صعوبة، و{len(told["tickets"])} طلب دعم، و{red} إعادة تشغيل فشلت.',
                   f'{len(goals)} goal(s) tried by {len(told["personas"])} persona(s): {reached} reached. '
                   f'{len(told["difficulties"]["ranked"])} difficulty(ies), {len(told["tickets"])} ticket(s), {red} replay(s) broke.'))


def _in(record, key, ar):
    """A record's text in the page's language (key_ar), else as written."""
    return (record.get(key + '_ar') if ar else None) or record.get(key)


def _difficulty(page, d, ar):
    title = _in(d, 'title', ar) or d.get('note')
    verdict, severity = _word(VERDICT, d.get('verdict'), ar), _word(SEVERITY, d.get('severity'), ar)
    page.heading(f"{d.get('id')}: {title}", 3)
    page.para(_say(ar, f"{verdict}، خطورتها {severity}، في {d.get('goal')}. ", f"{verdict}, {severity} severity, in {d.get('goal')}. ")
              + str(d.get('why') or ''))
    page.items([_say(ar, 'لتكرارها: ', 'To reproduce: ') + str(step) for step in d.get('repro') or []])
    fix = _in(d, 'fix', ar)
    if fix: page.para(_say(ar, 'الحل: ', 'The fix: ') + fix)
    if d.get('card'): page.para(_say(ar, 'بطاقة إصلاحها: ', 'Its fix card: ') + f"`{d['card']}`")
    for picture in (d.get('pictures') or [])[:1]: _image(page, title, picture)


def _difficulties(page, told, ar):
    if not told['difficulties']['ranked']: return
    page.heading(_say(ar, 'الصعوبات مرتبة', 'The difficulties, ranked'))
    for d in told['difficulties']['ranked']: _difficulty(page, d, ar)


def _time(page, told, ar):
    if not told['time']: return
    page.heading(_say(ar, 'الوقت لكل مهمة', 'Time per task'))
    _table(page, [_say(ar, 'الهدف', 'Goal'), _say(ar, 'الشخصية', 'Persona'), _say(ar, 'النتيجة', 'Result'),
                  _say(ar, 'الثواني', 'Seconds'), _say(ar, 'طلبات المساعد', 'Assistant calls')],
           [(g['name'], g['persona'], _word(STATUS, g['status'], ar), g['seconds'], g['calls']) for g in told['time']])
    if told['seconds'] is not None:
        page.para(_say(ar, f"المجموع: {told['seconds']} ثانية و{told['calls']} طلبًا.", f"In all: {told['seconds']} seconds and {told['calls']} calls."))


def _steps(page, goal, ar):
    for n, step in enumerate(goal['steps'], 1):
        said = ' '.join(str(p) for p in (step['action'], step['target'], f'«{step["value"]}»' if step['value'] else None) if p)
        error = _say(ar, f" خطأ: {step['error']}", f" Error: {step['error']}") if step['error'] else ''
        page.para(_say(ar, f'الخطوة {n}: ', f'Step {n}: ') + f"{said}: {step['why'] or ''} → {step['landed'] or '-'}.{error}")
        _image(page, _say(ar, f'الخطوة {n}', f'Step {n}'), step['picture'])
    page.items([f"{_say(ar, 'الخطوة', 'Step')} {f.get('step')} ({_word(KIND, f.get('kind'), ar)}): {f.get('note')}" for f in goal['friction']])


def _personas(page, told, ar):
    for persona in told['personas']:
        page.heading(f"{persona['name']}" + (f" ({persona['role']})" if persona['role'] else ''))
        if persona['about']: page.para(persona['about'])
        for goal in persona['goals']:
            page.heading(f"{goal['name']}: {_word(STATUS, goal['status'], ar)}", 3)
            if goal['wanted']: page.para(_say(ar, 'المطلوب: ', 'Wanted: ') + goal['wanted'])
            if goal['why']: page.para(_say(ar, 'السبب: ', 'Why: ') + goal['why'])
            _steps(page, goal, ar)


def _tickets(page, told, ar):
    if not told['tickets']: return
    page.heading(_say(ar, 'طلبات الدعم', 'The tickets'))
    page.items([f"{t.get('id')} ({t.get('goal')}): {t.get('asked')} → {t.get('answer') or '-'} "
                + _say(ar, f"(بعدها: {_word(STATUS, t.get('after'), ar)}{'، صُعّد' if t.get('escalated') else ''})",
                       f"(after: {_word(STATUS, t.get('after'), ar)}{', escalated' if t.get('escalated') else ''})") for t in told['tickets']])


def _replays(page, told, ar):
    replays = told['replays']
    if replays['summary']:
        page.heading(_say(ar, 'إعادة التشغيل بلا مساعد', 'Replays without an assistant'))
        page.para(_say(ar, f"نجحت {replays['summary'].get('green', 0)} وفشلت {replays['summary'].get('red', 0)}.",
                       f"{replays['summary'].get('green', 0)} green, {replays['summary'].get('red', 0)} red."))
        page.items([f"{r.get('goal')}: {r.get('error') or r.get('broken_at') or ''}" for r in replays['red']])


def _rest(page, told, ar):
    """The services not covered, the rejected difficulties, and the missing records."""
    sections = ((_say(ar, 'خدمات لم تُغطَّ في التجربة', 'Services not covered by the trial'), [f"{s.get('service')}: {s.get('why')}" for s in told['not_covered']]),
                (_say(ar, 'صعوبات رُفضت', 'Difficulties rejected'), [f"{d.get('id')} ({d.get('goal')}): {d.get('note')}. {d.get('why') or ''}" for d in told['difficulties']['rejected']]),
                (_say(ar, 'سجلات ناقصة', 'Missing records'), [f'{FOLDER}/{name}' for name in told['missing']]))
    for title, rows in sections:
        if rows: page.heading(title); page.items(rows)


def page_text(told, language):
    """EXPERIENCE.md's text from a story, in `language` ('ar' or 'en')."""
    ar = language == 'ar'
    page = Page(_say(ar, 'تجربة المستخدمين', "The users' experience"))
    if told['ran']: _overview(page, told, ar)
    else: page.para(_say(ar, 'لم تُجرَّب تجربة المستخدمين في هذا الفحص.', "The users' experience was not tried in this check."))
    for part in (_difficulties, _time, _personas, _tickets, _replays, _rest): part(page, told, ar)
    return page.text()


def write(report, language):
    """<report>/EXPERIENCE.md and <report>/experience/story.json from story(report); (the page's path, the data's path)."""
    report, told = Path(report), story(report)
    data = report / FOLDER / DATA
    data.parent.mkdir(parents=True, exist_ok=True)
    data.write_text(json.dumps(told, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    (report / PAGE).write_text(page_text(told, language), encoding='utf-8')
    return report / PAGE, data
