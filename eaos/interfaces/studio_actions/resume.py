"""A run whose assistant stopped mid-way goes on by itself (eaos/interfaces/studio_actions/runs.py): the work is the computer's,
not one assistant's.

When the assistant's process ends in failure (its usage limit, a sign-in that expired, a crash), the run stays
running: after a short wait it starts again with an assistant signed in now, the same one, or another one when
the first hit its limit or lost its sign-in, and that assistant reads EAOS's `status` and the handover of the one
before, so a batch goes on from the card it stopped at. After RESUMES tries, or when no assistant answers, the run
stops as failed with why, and Retry goes on the same way.
"""
import re
import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ...ai.assistant import readiness
from ...core.project.runs import TERMINAL

RESUMES = 3                  # times a run goes on by itself
WAITS = (20, 120, 600)       # seconds before each time: a sign-in refreshes in seconds, a limit lifts in minutes
GONE = ('limit', 'sign_in_expired', 'not_signed_in')    # the assistant itself cannot go on: another one first
LONGEST = 8 * 3600           # seconds a run waits at most for a spent limit to come back, as its assistant said when
CONTINUE = ('This work was started by an assistant that stopped before the end ({why}). Call `status` first: its handover '
            'says what was done; go on from there, without redoing what is kept.\n\n')


def _answers(name):
    """The assistant answers a one-word question now: its sign-in status alone said a revoked Codex was ready, and the
    work handed to it stopped at once (2026-11-04)."""
    return readiness.check(name)['ready'] if name in readiness.NAMES else False


def next_assistant(adapters, current, problem, ready=_answers):
    """The assistant the run goes on with: one that answers now, another one first when the current one hit its limit
    or lost its sign-in."""
    others = [name for name in adapters if name != current]
    order = others + [current] if problem in GONE else [current] + others
    return next((name for name in order if name in adapters and ready(name)), None)


def seconds_until(back, now=None):
    """Seconds until a spent limit comes back, from the assistant's words ("7:40am (UTC)", "5 PM", "in 2 hours"), a minute
    more; None when they say no time EAOS can read, or one further than LONGEST."""
    now, text = now or datetime.now(timezone.utc), str(back or '')
    seconds = _span(text.lower()) if re.match(r'\d+\s*(hour|minute)', text.lower()) else _clock(text, now)
    return seconds + 60 if seconds is not None and seconds <= LONGEST else None


def _span(text):
    amount, unit = re.match(r'(\d+)\s*(hour|minute)', text).groups()
    return int(amount) * (3600 if unit == 'hour' else 60)


def _clock(text, now):
    """Seconds until a time of day, in UTC or the time zone named in brackets; None without a readable one."""
    clock, zone = re.match(r'(\d{1,2})(?::(\d{2}))?\s*([ap]m)?', text.lower()), _zone(text)
    if not clock or not (clock[2] or clock[3]) or zone is None: return None
    hour, minute = _hour(clock), int(clock[2] or 0)
    if hour > 23 or minute > 59: return None
    here = now.astimezone(zone)
    at = here.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return ((at if at > here else at + timedelta(days=1)) - here).total_seconds()


def _hour(clock):
    """The hour of a matched time of day on a 24-hour clock."""
    return int(clock[1]) % 12 + (12 if clock[3] == 'pm' else 0) if clock[3] else int(clock[1])


def _zone(text):
    """The time zone named in brackets ("(UTC)", "(Asia/Riyadh)"), UTC when none is named, None for one not known."""
    named = (re.search(r'\(([^)]+)\)', text) or [None, 'utc'])[1].strip()
    try: return timezone.utc if named.upper() == 'UTC' else ZoneInfo(named)
    except (KeyError, ValueError): return None


def after_failure(manager, run, reason):
    """True when the run goes on by itself after its assistant failed with `reason`; False: it fails as before."""
    record = manager.store.load(run)
    done = record.get('resumes') or 0
    if record.get('mode') != 'assistant' or done >= RESUMES or record.get('pending_question'): return False
    wait = WAITS[done]
    manager.store.update(run, resumes=done + 1, pid=None)
    manager.store.append(run, 'step', {'en': f'The assistant stopped ({reason[:200]}): the work goes on by itself in {wait} seconds, from where it stopped',
                                       'ar': f'المساعد وقف ({reason[:200]}): الشغل يكمل لحاله بعد {wait} ثانية، من محل ما وقف'},
                         {'tool': None, 'resume': done + 1, 'of': RESUMES})
    threading.Thread(target=_go_on, args=(manager, run, reason, wait), daemon=True).start()
    return True


def _go_on(manager, run, reason, wait):
    if manager._closed.wait(wait): return
    record = manager.store.load(run)
    if record.get('state') in TERMINAL or record.get('state') != 'running': return     # stopped by the person meanwhile
    name = next_assistant(manager.adapters, record.get('assistant'), readiness.classify(reason))
    if name is None and (later := _until_back(manager, run, reason)):
        if manager._closed.wait(later): return
        name = next_assistant(manager.adapters, record.get('assistant'), readiness.classify(reason))
    if name is None:
        return manager._fail(run, f'no assistant answers to go on ({reason[:200]})',
                             {'en': 'Sign in to Claude Code or Codex (or wait for its limit to lift), then press Retry: it goes on from where it stopped.',
                              'ar': 'سجّل الدخول في Claude Code أو Codex (أو انتظر لين يرجع حدّه)، ثم اضغط «أعد»: يكمل من محل ما وقف.'})
    if name != record.get('assistant'):
        manager.store.append(run, 'step', {'en': f'Going on with {manager.adapters[name].name}', 'ar': f'نكمل مع {manager.adapters[name].name}'},
                             {'tool': None, 'assistant': name})
    manager.store.update(run, assistant=name)
    manager._launch(run, manager.adapters[name], CONTINUE.format(why=reason[:200]) + manager.prompt_of(record))


def _until_back(manager, run, reason):
    """Seconds to wait for the limit the assistant hit to come back, when it said when, said in the run; None otherwise."""
    wait = seconds_until(readiness.resets_at(reason)) if readiness.classify(reason) == 'limit' else None
    if wait: manager.store.append(run, 'step', {'en': f'No assistant answers now: waiting until its limit comes back ({readiness.resets_at(reason)}), then going on',
                                                'ar': f'ما فيه مساعد يرد الحين: أنتظر لين يرجع حدّه ({readiness.resets_at(reason)})، ثم أكمل'},
                                  {'tool': None, 'waits': round(wait)})
    return wait


def release(manager, run):
    """A batch the stopped run leaves open with no change kept is closed, so its cards are open again (56 cards of a
    stranger's PHP project stayed "in the batch" after its assistant's limit, 2026-11-04); one with kept changes stays,
    and Retry goes on with it."""
    from ...core.project import state as project_state
    from ...journeys import agent_tools
    wave = (project_state.load(manager.project) or {}).get('open_wave')
    if not wave or wave.get('kept'): return
    closed = agent_tools.fix_abandon(str(manager.project))
    if closed.get('status') == 'abandoned':
        manager.store.append(run, 'step', {'en': f"Batch {closed['batch']} kept no change: closed, its {len(closed['cards'])} cards are open again",
                                           'ar': f"الدفعة {closed['batch']} ما احتفظت بأي تغيير: انقفلت، وبطاقاتها الـ{len(closed['cards'])} رجعت مفتوحة"},
                             {'tool': None, 'batch': closed['batch']})
