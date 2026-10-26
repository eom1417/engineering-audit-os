"""REPORT.html's work log: who did what, when, and where the work stopped."""
from ...analysis.presentation import model as M
from ...core.language.markup import both as T, esc
from .html import lit, num, said, tech


# ---------------------------------------------------------------- the work log: who did what, when, and where it stopped

TOOL_WORDS = {
    'audit': ('فحص المشروع كله', 'checked the whole project'), 'choose_branch': ('اختار الفرع', 'chose the branch'),
    'run_setup': ('جهّز تشغيل البرنامج في نسخة معزولة', 'prepared running the app in an isolated copy'),
    'run_try': ('جرّب تشغيل البرنامج', 'tried running the app'), 'safety_net': ('سجّل شاشات البرنامج وسرعته', 'recorded the app’s screens and speed'),
    'fix_start': ('فتح دفعة إصلاح', 'opened a fix batch'), 'fix_edit': ('أصلح بطاقة وتحقق منها', 'fixed a card and checked it'),
    'fix_skip': ('ترك بطاقة مع السبب', 'left a card out, with the reason'), 'fix_finish': ('أغلق الدفعة وفحصها كلها', 'closed the batch and checked it whole'),
    'accept': ('أدخل الفرع في فرعك', 'took the branch into yours'), 'undo': ('ألغى الفرع المنتظر', 'threw the waiting branch away'),
    'note': ('كتب ملاحظة', 'wrote a note'), 'blueprint_start': ('بدأ مشروعًا من خطته', 'started a project from its plan'),
    'blueprint_spec': ('راجع مواصفات المنتج', 'checked the product spec'), 'blueprint_design': ('رسم البنية المستهدفة', 'drew the target'),
    'build_start': ('فتح مرحلة بناء', 'opened a build milestone'), 'build_edit': ('بنى بطاقة', 'built a card'),
    'build_skip': ('ترك بطاقة بناء', 'left a build card out'), 'build_finish': ('أغلق مرحلة البناء', 'closed the build milestone'),
    'wait': ('تابع عملًا جاريًا', 'followed a running job'), 'status': ('قرأ أين وصل العمل', 'read where the work is'),
}
JOB_WORDS = {'fix batch': ('دفعة الإصلاح', 'fix batch'), 'build milestone': ('مرحلة البناء', 'build milestone')}


def when(at):
    """An ISO time as a person reads it: the date and the minute, UTC."""
    return str(at or '').replace('T', ' ')[:16]


def who(name):
    return f'<span class="chip who" data-literal="1">{esc(name or "?")}</span>'


def work_log(progress):
    """Where the work stopped, what is open and left, the next step, then the last steps and the notes, newest first."""
    h = (progress or {}).get('handover')
    head = f'<h3 id="work-log">{T("سجل العمل وأين وقفنا", "Work log and where we stopped")}</h3>'
    if not _started(h):
        return head + (f'<div class="card" data-part="work-log">{T("لم يبدأ أي عمل بعد: حين يبدأ مساعد ذكي (Claude Code أو Codex) الفحص أو الإصلاح، تظهر هنا كل خطوة، ومن قام بها، ومتى، وأين وقف.", "No work has started yet: when an AI assistant (Claude Code or Codex) starts the check or the fixes, every step shows here, who took it, when, and where it stopped.", "p")}</div>')
    status = _wl_status(h)
    timeline = _wl_timeline([s for s in h.get('last_steps') or [] if isinstance(s, dict)])
    notes_html = _wl_notes([x for x in h.get('notes') or [] if isinstance(x, dict) and x.get('note')])
    return head + f'<div class="card wl" data-part="work-log">{status}<div class="wl-body">{timeline}{notes_html}</div></div>'


def _started(h):
    """Whether the handover holds any work: a step, open work, an assistant, a note or a card in progress."""
    return isinstance(h, dict) and bool(h.get('last_steps') or h.get('open_work') or h.get('last_assistant') or h.get('notes') or h.get('in_progress'))


def _wl_status(h):
    """Where we stopped: the last to work, what is open now, the next step, the progress and how to continue."""
    work, job, waiting, busy = (_dict_of(h, k) for k in ('open_work', 'running_job', 'waiting_for_the_person', 'in_progress'))
    now = _wl_now(job, work, waiting, busy)
    step = _wl_next_step(job, busy, work, waiting)
    p = h.get('progress') if isinstance(h.get('progress'), dict) else {}
    tally = (f'<p class="small">{T(f"التقدم في فرعك: أُغلق {num(p.get("closed", 0), "cards closed")} من {num(p.get("total", 0), "cards in the plan")}", f"Progress in your branch: {num(p.get("closed", 0), "cards closed")} of {num(p.get("total", 0), "cards in the plan")} closed")}</p>' if p else '')
    return (f'<div class="card wl-status"><h4>{T("أين وقفنا", "Where we stopped")}</h4>{_wl_last(h)}<ul class="small wl-now">{"".join(now)}</ul>'
            f'<p class="small"><b>{T("الخطوة التالية:", "The next step:")}</b> {step}</p>{tally}'
            + (f'<details><summary>{T("للمساعد الذكي الذي يكمل", "For the AI assistant that continues")}</summary>{tech(h["how_to_continue"])}</details>' if h.get('how_to_continue') else '')
            + '</div>')


def _dict_of(h, key):
    return h.get(key) if isinstance(h.get(key), dict) else None


def _wl_open_work(work):
    """The open batch or milestone: what was kept, not kept and left, and why each was not kept."""
    label = _wl_work_label(work)
    kept, not_kept, left = work.get('kept') or [], work.get('not_kept') or {}, work.get('left') or []
    rows = [f'<li>{label}: ' + T(f'نجح {num(M.collection_count(kept), "cards kept in the open batch")}، ولم ينجح {num(M.collection_count(not_kept), "cards not kept in the open batch")}، وبقي {num(M.collection_count(left), "cards left in the open batch")}',
                                     f'{num(M.collection_count(kept), "cards kept in the open batch")} kept, {num(M.collection_count(not_kept), "cards not kept in the open batch")} not kept, {num(M.collection_count(left), "cards left in the open batch")} left') + '</li>']
    if left: rows.append(f'<li>{T("الباقي:", "Left:", cls="lbl")} {" ".join(lit(c) for c in list(left)[:20]) or T("لا شيء", "none")}</li>')
    rows += [f'<li>{T("لم ينجح:", "Not kept:", cls="lbl")} {lit(card)} {tech(str(why)[:200])}</li>'
             for card, why in (list(not_kept.items())[:8] if isinstance(not_kept, dict) else [])]
    return rows


def _wl_work_label(work):
    """The open work's name: a fix batch or a build milestone, and its number."""
    kind = JOB_WORDS.get(work.get('kind'), (work.get('kind') or '', work.get('kind') or ''))
    number = work.get('number') if work.get('number') is not None else work.get('milestone')
    return (T(f'{esc(kind[0])} مفتوحة', f'Open {esc(kind[1])}') + (' ' + (num(number, 'the number of the open batch') if isinstance(number, int) else lit(number)) if number is not None else ''))


def _wl_files_read(read):
    if not read: return ''
    return (f'<div class="small">{T("قرأ من الملفات:", "Files it read:", cls="lbl")} {" ".join(lit(f) for f in read[:8])}'
            + (T(f' و{num(M.remaining(read, 8), "more files read")} غيرها', f' and {num(M.remaining(read, 8), "more files read")} more') if len(read) > 8 else '') + '</div>')


def _wl_busy(busy):
    """The card the last assistant was on, since when, the files it read and how its last try ended."""
    since = (T(f' منذ {num(when(busy.get("since")), "when this card was started (UTC)")}', f' since {num(when(busy.get("since")), "when this card was started (UTC)")}')
             if busy.get('since') else '')
    by = f' {who(busy["by"])}' if busy.get('by') else ''
    read = [f for f in busy.get('files_read') or [] if isinstance(f, str)]
    return (f'<li>{T(f"كان يعمل على البطاقة {lit(busy["card"])}", f"Was working on card {lit(busy["card"])}")}{by}{since}'
            + _wl_files_read(read)
            + (f'<div class="small">{T("آخر محاولة:", "Last try:", cls="lbl")} {tech(str(busy["last_try"])[:300])}</div>' if busy.get('last_try') else '')
            + '</li>')


def _wl_now(job, work, waiting, busy):
    """What is open now: a running job, the open batch, a branch waiting for the person, the card in progress."""
    now = []
    if job:
        name = lit(job.get('kind') or job.get('id') or '')
        now.append(T(f'عمل جارٍ الآن: {name}', f'A job is running now: {name}', 'li'))
    if work: now += _wl_open_work(work)
    if waiting:
        branch = lit(waiting.get('branch') or '')
        now.append(T(f'ينتظر قرارك: أدخل الفرع {branch} في فرعك أو ألغِه.', f'Waiting for you: take branch {branch} into yours, or throw it away.', 'li'))
    if busy and busy.get('card'): now.append(_wl_busy(busy))
    return now or [T('لا شيء مفتوح الآن.', 'Nothing is open now.', 'li')]


def _wl_next_step(job, busy, work, waiting):
    if job: return T('انتظار العمل الجاري حتى ينتهي، ثم المتابعة.', 'Wait for the running job to finish, then go on.')
    if busy and busy.get('card'): return T(f'إكمال البطاقة {lit(busy["card"])} من حيث توقفت، ثم البقية.', f'Finish card {lit(busy["card"])} from where it stopped, then the rest.')
    if work and work.get('left'): return T('إصلاح البطاقات الباقية واحدة واحدة، ثم إغلاق الدفعة وفحصها كلها.', 'Fix the cards left one by one, then close the batch and check it whole.')
    if work: return T('إغلاق الدفعة المفتوحة وفحصها كلها.', 'Close the open batch and check it whole.')
    if waiting: return T('قرارك في الفرع المنتظر: أدخله أو ألغِه.', 'Your decision on the waiting branch: take it in or throw it away.')
    return T('بدء الدفعة التالية من الخطة.', 'Start the next batch of the plan.')


def _wl_last(h):
    return (f'<p class="small">{T("آخر من عمل:", "Last to work:", cls="lbl")} {who(h.get("last_assistant"))} '
            + (T(f'في {num(when(h.get("last_activity")), "the time of the last step (UTC)")}', f'at {num(when(h.get("last_activity")), "the time of the last step (UTC)")}') if h.get('last_activity') else '')
            + (f' · {T("الفرع:", "branch:", cls="lbl")} {lit(h["branch"])}' if isinstance(h.get('branch'), str) and h.get('branch') else '') + '</p>')


def _wl_step(s):
    tool = s.get('tool') or ''
    words = TOOL_WORDS.get(tool)
    what = T(*map(esc, words)) if words else lit(tool)
    return (f'<li class="wl-step"><span class="wl-dot" aria-hidden="true"></span><div><div class="wl-head">{who(s.get("by"))} '
            f'<span class="muted small">{num(when(s.get("at")), "the time of this step (UTC)")}</span></div>'
            f'<div>{what}{(" " + lit(s["card"])) if s.get("card") else ""}</div>'
            + (f'<div class="small muted">{T("النتيجة:", "Result:", cls="lbl")} {tech(str(s["outcome"])[:300])}</div>' if s.get('outcome') else '') + '</div></li>')


def _wl_timeline(steps):
    items = [_wl_step(s) for s in reversed(steps)]
    if not items: return T('لا خطوات مسجلة بعد.', 'No step recorded yet.', 'p', 'muted small')
    return f'<h4>{T("آخر الخطوات، الأحدث أولًا", "The last steps, newest first")}</h4><ol class="timeline">{"".join(items)}</ol>'


def _wl_notes(notes):
    if not notes: return ''
    return (f'<h4>{T("ملاحظات المساعدين", "Notes from the assistants")}</h4><ul class="wl-notes">'
            + ''.join(f'<li>{who(x.get("by"))} <span class="muted small">{num(when(x.get("at")), "the time of this note (UTC)")}</span>'
                      f'{(" " + lit(x["card"])) if x.get("card") else ""}<div>{said(x["note"])}</div></li>' for x in reversed(notes)) + '</ul>')
