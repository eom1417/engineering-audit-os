"""The resources this process can use, including container limits rather than the host's totals, and whether there is
room for more work now: what decides how much of a check runs at once, so that no computer is ever choked."""
import os
from pathlib import Path

RESERVE_MB = 768             # always left free beyond current use, for the app, an analyzer and EAOS itself
BUSY = 40                    # % of the last ten seconds work waited for a processor: the processors are saturated
STARTING = 15                # seconds a started piece of work may take to reach what it uses: it counts as using it
WAIT = 2                     # seconds between two looks at the room while work waits for it


def capacity():
    """(CPU count, memory bytes, available bytes). Unknown memory is None; reclaimable cache is available."""
    cpus = len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else os.cpu_count() or 1
    try:
        quota, period = Path('/sys/fs/cgroup/cpu.max').read_text().split()
        if quota != 'max': cpus = min(cpus, max(1, (int(quota) + int(period) - 1) // int(period)))
    except (OSError, ValueError): pass
    try: memory = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
    except (ValueError, OSError, AttributeError): memory = None
    available = memory
    try:
        info = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        available = int(info['MemAvailable'].split()[0]) * 1024
    except (OSError, ValueError, KeyError): pass
    try:
        limit = int(Path('/sys/fs/cgroup/memory.max').read_text())
        memory = min(memory, limit) if memory is not None else limit
        current = int(Path('/sys/fs/cgroup/memory.current').read_text())
        stat = dict(line.split() for line in Path('/sys/fs/cgroup/memory.stat').read_text().splitlines())
        reclaimable = sum(int(stat.get(key, 0)) for key in ('inactive_file', 'slab_reclaimable'))
        available = min(available or limit, max(0, limit - current + reclaimable))
    except (OSError, ValueError): pass
    return cpus, memory, available


def cpu_pressure():
    """The share (0-100) of the last ten seconds in which some runnable work waited for a processor; None when unknown."""
    for path in ('/sys/fs/cgroup/cpu.pressure', '/proc/pressure/cpu'):
        try:
            line = Path(path).read_text().splitlines()[0]
            return float(dict(field.split('=') for field in line.split()[1:])['avg10'])
        except (OSError, ValueError, KeyError, IndexError): continue
    return None


def room(megabytes):
    """Whether this computer can take `megabytes` more now, keeping RESERVE_MB free, its processors not saturated."""
    available, pressure = capacity()[2], cpu_pressure()
    return (available is None or available // 2 ** 20 >= megabytes + RESERVE_MB) and (pressure is None or pressure < BUSY)
