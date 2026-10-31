"""Running a program as EAOS runs every one: in its own process group, so a person's stop or a timeout ends its children
too, and one that writes nothing for STUCK seconds is ended as stuck."""
import os
import signal
import subprocess
import time
from contextvars import ContextVar

STOP = ContextVar('eaos_stop', default=None)


def check_cancelled():
    if STOP.get() is not None and STOP.get().is_set(): raise KeyboardInterrupt()


def communicate(process, timeout):
    """communicate(), observing the check's stop even when called from a stage's worker thread."""
    deadline = time.monotonic() + timeout
    while True:
        check_cancelled()
        remaining = deadline - time.monotonic()
        if remaining <= 0: raise subprocess.TimeoutExpired(process.args, timeout)  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- only the timeout of the run above, nothing is started here
        try: return process.communicate(timeout=min(0.25, remaining))
        except subprocess.TimeoutExpired:
            if time.monotonic() >= deadline: raise


def run_command(argv, timeout, **options):
    """Capture a command in its own process group; interruption or timeout kills its children too."""
    check_cancelled()
    with subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors='backslashreplace', start_new_session=True, **options) as child:  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- the one runner of list argvs its callers build, never a shell
        try:
            out, err = communicate(child, timeout)
            return subprocess.CompletedProcess(argv, child.returncode, out, err)  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- only the record of the run above, nothing is started here
        finally:
            if child.poll() is None: _end(child)

STUCK = 1200   # seconds with no output at all from the assistant: it is stuck, however long the work may take


class Stuck(Exception):
    """The assistant gave no output at all for STUCK seconds, so it was ended."""


def _end(process):
    try: os.killpg(process.pid, signal.SIGKILL)
    except OSError: process.kill()
    process.wait()


def wait(process, outputs, cancel=None):
    """Wait for `process` (started in its own session) however long it works. Its whole group is ended only when the
    person stops it (`cancel` set, or a stop reaching this process), or when nothing is written to any of `outputs`
    (open files) for STUCK seconds: then Stuck is raised."""
    sizes, quiet = None, time.monotonic()
    try:
        while process.poll() is None and not (cancel is not None and cancel.is_set()):
            check_cancelled()
            now = [os.fstat(output.fileno()).st_size for output in outputs]
            if now != sizes: sizes, quiet = now, time.monotonic()
            elif time.monotonic() - quiet > STUCK:
                raise Stuck(f'the assistant gave no output at all for {STUCK // 60} minutes, so it was stuck and was ended')
            time.sleep(0.25)
    finally:
        if process.poll() is None: _end(process)
