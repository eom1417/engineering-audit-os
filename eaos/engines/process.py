"""Running a pinned analyzer, and keeping the target byte-identical while it runs.

The target is read-only: an engine that writes where it reads runs on a copy of its own (GitNexus). Nothing here
ever runs a script belonging to the analysed project.
"""
import os
import shutil
import subprocess
import time
from hashlib import sha256
from pathlib import Path

from ..core import toolchain
from ..core.system.process import run_command

DEFAULT_TIMEOUT = 600
SKIP_DIRECTORIES = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', 'dist', 'build', '.mypy_cache'}


def which(binary):
    """The pinned engine directory first, then the ambient PATH."""
    pinned = toolchain.home() / 'bin' / binary
    if pinned.is_file() and os.access(pinned, os.X_OK):
        return str(pinned)
    return shutil.which(binary)


def run(command, cwd=None, timeout=DEFAULT_TIMEOUT, env=None):
    """Run an engine and return (exit code, stdout, stderr, seconds). Never raises on a bad exit."""
    started = time.monotonic()
    cache = os.environ.get('EAOS_ENGINE_CACHE')     # the project's own (eaos/core/project/jobs.py): no cache shared between projects
    try:
        done = run_command(command, cwd=cwd, timeout=timeout,
                           env={**toolchain.tool_env(), 'NO_COLOR': '1', **({'XDG_CACHE_HOME': cache} if cache else {}), **(env or {})})
    except (OSError, subprocess.TimeoutExpired) as problem:
        return 127, '', str(problem), time.monotonic() - started
    return done.returncode, done.stdout, done.stderr, time.monotonic() - started


def state_digest(target):
    """A cheap fingerprint of the target tree: path, size and mtime of every source file.

    Compared before and after the engines run, it proves no analyzer edited the project.
    """
    digest = sha256()
    for root, directories, files in os.walk(target):
        directories[:] = sorted(d for d in directories if d not in SKIP_DIRECTORIES)
        for name in sorted(files):
            path = Path(root) / name
            try:
                stat = path.stat()
            except OSError:
                continue
            digest.update(f'{path.relative_to(target)}|{stat.st_size}|{stat.st_mtime_ns}\n'.encode('utf-8'))
    return digest.hexdigest()
