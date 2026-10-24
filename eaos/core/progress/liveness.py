"""Whether a run that has not ended is still heard from: the map never glows for a run nobody hears from.

The writer adds a `run.alive` line whenever ALIVE_EVERY seconds pass without any other line, and says so in
`run.started` (`alive_every`). A reader then judges a run that never ended:

- `interrupted` when its process is known to be gone (same machine, the process number no longer exists);
- `stalled` when the run promised heartbeats and nothing was written for more than STALLED_AFTER seconds;
- otherwise it is still `running`.

A run written without the promise (an older EAOS) is never called stalled: its silence proves nothing.
"""
import os
import socket
from pathlib import Path

RUNNING, STALLED, INTERRUPTED = 'running', 'stalled', 'interrupted'
ALIVE_EVERY = 10.0
STALLED_AFTER = 30.0


def alive(state):
    """False when a run that never ended was started by a process on this machine that is gone (it was stopped or
    crashed); True when it may still be running; None when it cannot be told (another machine, no process number)."""
    if state.get('state') != RUNNING: return None
    if not state.get('pid') or state.get('host') != socket.gethostname(): return None
    try: os.kill(int(state['pid']), 0)
    except ProcessLookupError: return False
    except PermissionError: return True
    except (OSError, ValueError): return None
    return True


def heard_at(path):
    """When the progress file was last written (seconds since the epoch, the reader's clock), or None."""
    try: return Path(path).stat().st_mtime
    except OSError: return None


def judge(state, heard, now, living=None):
    """The run's state as a reader shows it: `interrupted` when `living` is False, `stalled` when the run promised
    heartbeats and the last line (`heard`) is more than STALLED_AFTER seconds before `now`, else the folded state."""
    if state.get('state') != RUNNING: return state.get('state')
    if living is False: return INTERRUPTED
    if state.get('alive_every') and heard is not None and now - heard > STALLED_AFTER: return STALLED
    return RUNNING
