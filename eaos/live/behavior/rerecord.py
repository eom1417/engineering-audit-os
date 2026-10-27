"""A kept batch's declared screens recorded again on its code (M9.7), apart from the lock's original pictures: the next
card on code that holds the batch's commit is compared with them (intended.py restore_intended). Its own module: it runs
the lock's passes (lock.py), which read intended.py, so intended.py never imports lock.py."""
import subprocess
from pathlib import Path

from ..app.run import LiveRun
from .folder import _prepare, lend_kinds
from .intended import FOLDER, _keep_screens, _remember, restore_intended
from .lock import LockPass, _run_specs, _start


def record_intended(report, target, runtime, screens):
    """The declared `screens` recorded again on `target` (a kept batch's copy, at its commit), kept for every later run on
    code that holds the commit: behavior-lock/intended/<commit>/, and the screens recorded."""
    recorded = Path(runtime) / 'behavior-lock'
    commit = subprocess.run(['git', '-C', str(target), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    live = LiveRun(target, runtime, 'S09')
    lock = _prepare(live, report, recorded)
    restore_intended(recorded, lock, target)
    try:
        base = _start(live, lock)
        lend_kinds(report, lock, lock / '.auth/user.json')
        _run_specs(live, lock, base, recorded, LockPass('intended', update=True))
    finally:
        live.stop()
        live.record('behavior-lock/run-log-intended.json')
    kept = _keep_screens(lock / '__screenshots__', recorded / FOLDER / commit, screens)
    _remember(recorded, commit, kept)
    return kept
