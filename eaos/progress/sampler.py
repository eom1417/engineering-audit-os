"""Which external programs the run has started right now, seen from outside: no subprocess call site is touched.

Every few seconds while a stage runs, the writer asks the system for its process table,

    ps -A -o pid=,ppid=,etime=,comm=

(POSIX flags that both Linux procps and the macOS ps accept), keeps the processes that descend from the run's own
process, and reports them as `[{name, pid, since}]`: semgrep-core started by pysemgrep started by EAOS, trivy,
playwright, k6. Linux prints `comm` as a short name (15 characters at most); macOS prints the executable's full path,
so a name that is a path keeps only its last part. Both may contain spaces, so `comm` is everything after the third
column.

If `ps` is missing, fails, times out or prints something that does not contain the run's own process, the sampler
turns itself off and says why once; the run is unaffected.
"""
import os
import subprocess
from datetime import datetime, timedelta, timezone

COMMAND = ('ps', '-A', '-o', 'pid=,ppid=,etime=,comm=')
MOST = 8


def elapsed(text):
    """Seconds of a `ps` etime value, `[[dd-]hh:]mm:ss`; None when it is not one."""
    try:
        days, dash, rest = text.strip().rpartition('-')
        if dash and not days.isdigit(): return None
        parts = [int(p) for p in rest.split(':')]
        if not 2 <= len(parts) <= 3 or any(p < 0 for p in parts): return None
        while len(parts) < 3: parts.insert(0, 0)
        hours, minutes, seconds = parts
        return (int(days) if days else 0) * 86400 + hours * 3600 + minutes * 60 + seconds
    except ValueError:
        return None


def parse(text):
    """The rows of the process table as (pid, ppid, seconds, name); lines that are not rows are left out."""
    rows = []
    for line in text.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 4: continue
        try: pid, ppid = int(parts[0]), int(parts[1])
        except ValueError: continue
        seconds = elapsed(parts[2])
        if seconds is None: continue
        name = parts[3].strip()
        if name.startswith('/'): name = name.rstrip('/').rsplit('/', 1)[-1]      # macOS: the executable's full path
        rows.append((pid, ppid, seconds, name))
    return rows


def descendants(rows, root, leave=()):
    """The rows below `root` in the process tree (not `root` itself, not the pids in `leave`), in pid order."""
    children = {}
    for row in rows: children.setdefault(row[1], []).append(row)
    found, todo = [], [root]
    while todo:
        for row in children.get(todo.pop(), []):
            if row[0] in leave or row[0] == root or any(row[0] == f[0] for f in found): continue
            found.append(row)
            todo.append(row[0])
    return sorted(found)


def programs(rows, root, leave=(), at=None):
    """`[{name, pid, since}]` of the descendants of `root`, at most MOST of them; `since` is when each one started."""
    at = at or datetime.now(timezone.utc)
    return [{'name': name, 'pid': pid, 'since': (at - timedelta(seconds=seconds)).isoformat(timespec='seconds')}
            for pid, _, seconds, name in descendants(rows, root, leave)[:MOST]]


class Sampler:
    """`sample()` gives the programs running under `root` now, or None once `ps` proved unusable (`reason` says why)."""

    def __init__(self, root=None, command=COMMAND, timeout=5.0):
        self.root = root or os.getpid()
        self.command = list(command)
        self.timeout = timeout
        self.off = False
        self.reason = ''

    def table(self):
        """The text `ps` printed and the pid of that `ps` (which is itself a child of the run, and is left out)."""
        with subprocess.Popen(self.command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True) as child:
            try:
                out, _ = child.communicate(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                child.kill()
                child.communicate()
                raise
            if child.returncode != 0: raise OSError(f'ps exited with {child.returncode}')
            return out, child.pid

    def sample(self):
        if self.off: return None
        try:
            out, own = self.table()
            rows = parse(out)
            if not any(row[0] == self.root for row in rows): raise ValueError('ps did not list the run itself')
        except (OSError, ValueError, subprocess.SubprocessError) as problem:
            self.off, self.reason = True, f'the running programs cannot be seen: {type(problem).__name__}: {problem}'[:200]
            return None
        return programs(rows, self.root, leave={own})
