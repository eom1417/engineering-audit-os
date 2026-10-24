"""Where the running stage is inside, reported from deep code without threading a parameter through every call.

The writer of a flow (`execute()` for the check) sets the current stage's stepper around the stage with `using()`.
Code anywhere below it then calls

    progress.count('codemod trial', 37, 156)          # a counted loop: 37 of 156 done
    progress.step('semgrep', 3, 21, 'running')         # one named item of a list the stage walks through

Outside a run both are no-ops, so every existing caller and test stays as it was, and a failure of the stepper is
swallowed: reporting where a stage is never changes what the stage does.

The stepper lives in a `contextvars.ContextVar`: a thread started inside the stage does not see it unless it was
started with `contextvars.copy_context().run`, which is the only way a worker thread reports its count.
"""
from contextlib import contextmanager
from contextvars import ContextVar

RUNNING = 'running'
_current = ContextVar('eaos_progress_stepper', default=None)


def current():
    """The current stage's stepper, or None outside a run."""
    return _current.get()


@contextmanager
def using(stepper):
    """Make `stepper` the current stage's stepper for the duration of the block, then restore what was there."""
    token = _current.set(stepper)
    try:
        yield stepper
    finally:
        _current.reset(token)


def step(name, done, total, status=RUNNING, seconds=None, reason='', reason_code='', artifact=''):
    """One named item of the stage: `done` of `total` items of the stage are finished; `artifact` is what it produced
    (a path relative to the flow's folder). No-op outside a run."""
    stepper = _current.get()
    if stepper is None: return
    try: stepper(name, done, total, status, seconds, reason, reason_code=reason_code, **({'artifact': artifact} if artifact else {}))
    except Exception:                                   # reporting where a stage is must not change what it does
        pass


def bounded(done, total):
    """(done, total) as whole numbers with 0 <= done <= total."""
    total = max(int(total), 0)
    return min(max(int(done), 0), total), total


def count(name, done, total):
    """A counted loop inside the current stage: `done` of `total`. The step is `ok` exactly when done reaches total,
    and done is held between 0 and total, so a counted step that ends ok ends with done == total. No-op outside a run."""
    stepper = _current.get()
    if stepper is None: return
    try:
        done, total = bounded(done, total)
        stepper(name, done, total, 'ok' if done >= total else RUNNING, kind='count')
    except Exception:
        pass
