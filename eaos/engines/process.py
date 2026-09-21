"""Running a pinned analyzer, and keeping the target byte-identical while it runs.

The target is read-only. One engine (enola) insists on writing its output inside the repository
it reads, so that engine reads a mirror instead: hardlinked when the filesystem allows it, copied
when it does not. Nothing here ever runs a script belonging to the analysed project.
"""
import os
import shutil
import subprocess
import time
from hashlib import sha256
from pathlib import Path

DEFAULT_TIMEOUT = 600
SKIP_DIRECTORIES = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', 'dist', 'build', '.mypy_cache'}


def which(binary):
    """The pinned engine directory first, then the ambient PATH."""
    pinned = Path('/workspace/engine-tools/bin') / binary
    if pinned.is_file() and os.access(pinned, os.X_OK):
        return str(pinned)
    return shutil.which(binary)


def run(command, cwd=None, timeout=DEFAULT_TIMEOUT, env=None):
    """Run an engine and return (exit code, stdout, stderr, seconds). Never raises on a bad exit."""
    started = time.monotonic()
    try:
        done = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                              check=False, env={**os.environ, 'NO_COLOR': '1', **(env or {})})
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


def mirror(target, workdir):
    """A throwaway copy of the target an engine may write into. Hardlinks when it can, copies when not."""
    target, destination = Path(target).resolve(), Path(workdir) / 'mirror'
    if destination.exists():
        shutil.rmtree(destination, ignore_errors=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    code, _, error, _ = run(['cp', '-al', str(target), str(destination)])
    if code == 0:
        return destination, 'hardlink'
    shutil.rmtree(destination, ignore_errors=True)
    code, _, error, _ = run(['cp', '-a', str(target), str(destination)])
    if code != 0:
        raise OSError(f'could not mirror the target for an engine that writes where it reads: {error.strip()[:200]}')
    return destination, 'copy'
