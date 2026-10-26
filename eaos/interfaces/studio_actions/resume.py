"""A run whose assistant stopped mid-way goes on by itself (eaos/interfaces/studio_actions/runs.py): the work is the computer's,
not one assistant's.

When the assistant's process ends in failure (its usage limit, a sign-in that expired, a crash), the run stays
running: after a short wait it starts again with an assistant signed in now, the same one, or another one when
the first hit its limit or lost its sign-in, and that assistant reads EAOS's `status` and the handover of the one
before, so a batch goes on from the card it stopped at. After RESUMES tries, or when no assistant answers, the run
stops as failed with why, and Retry goes on the same way.
"""
import threading

from ...ai.assistant import readiness
from ...core.project.runs import TERMINAL

RESUMES = 3                  # times a run goes on by itself
WAITS = (20, 120, 600)       # seconds before each time: a sign-in refreshes in seconds, a limit lifts in minutes
GONE = ('limit', 'sign_in_expired', 'not_signed_in')    # the assistant itself cannot go on: another one first
CONTINUE = ('This work was started by an assistant that stopped before the end ({why}). Call `status` first: its handover '
            'says what was done; go on from there, without redoing what is kept.\n\n')


def _signed_in(adapter):
    found = adapter.detect(fresh=True)
    return found['installed'] and found['logged_in']


def next_assistant(adapters, current, problem, ready=_signed_in):
    """The assistant the run goes on with: one installed and signed in now, another one first when the current one
    hit its limit or lost its sign-in."""
    others = [name for name in adapters if name != current]
    order = others + [current] if problem in GONE else [current] + others
    return next((name for name in order if name in adapters and ready(adapters[name])), None)


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
    if name is None:
        return manager._fail(run, f'no assistant answers to go on ({reason[:200]})',
                             {'en': 'Sign in to Claude Code or Codex (or wait for its limit to lift), then press Retry: it goes on from where it stopped.',
                              'ar': 'سجّل الدخول في Claude Code أو Codex (أو انتظر لين يرجع حدّه)، ثم اضغط «أعد»: يكمل من محل ما وقف.'})
    if name != record.get('assistant'):
        manager.store.append(run, 'step', {'en': f'Going on with {manager.adapters[name].name}', 'ar': f'نكمل مع {manager.adapters[name].name}'},
                             {'tool': None, 'assistant': name})
    manager.store.update(run, assistant=name)
    manager._launch(run, manager.adapters[name], CONTINUE.format(why=reason[:200]) + manager.prompt_of(record))
