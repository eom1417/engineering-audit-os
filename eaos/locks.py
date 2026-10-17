"""A file lock every project's processes share: many readers, or one writer that waits until none reads.

A leaf module, so the tools' installer (eaos/toolchain.py) and an engine that reads what it installs (eaos/engines/trivy.py)
share it without importing each other.
"""
import fcntl
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def held(folder, shared=True):
    """`folder`/.lock held: shared by readers, alone by a writer (who waits for every reader to finish)."""
    Path(folder).mkdir(parents=True, exist_ok=True)
    with open(Path(folder) / '.lock', 'a') as handle:
        fcntl.flock(handle, fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
        yield
