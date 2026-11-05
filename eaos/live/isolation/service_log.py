"""A started service's log (eaos/live/isolation/sandbox.py writes it): what it said last, and the log bounded once it
stopped."""
import os
from pathlib import Path

LOG_KEPT = 256 * 1024


def tail(path, size=2000):
    """The end of a service's log: what it said before it stopped, which is what anyone fixing it needs."""
    try: return Path(path).read_text(encoding='utf-8', errors='replace')[-size:].strip()
    except OSError: return ''


def bounded(path, size=LOG_KEPT):
    """A stopped service's log cut to its last `size` bytes: what it said last is what anyone fixing it reads (a load
    test's request lines grew one to 258 MB, kept beside the run, 2026-11-05)."""
    try:
        with open(path, 'rb+') as log:
            if log.seek(0, os.SEEK_END) <= size: return
            log.seek(-size, os.SEEK_END)
            end = log.read()
            log.seek(0)
            log.write(end)
            log.truncate()
    except OSError: return
