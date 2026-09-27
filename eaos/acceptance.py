"""Run explicitly authorized behavioral checks against a revision-bound candidate.

This is a process runner, not a sandbox. Stored commands never authorize themselves.
"""
import hashlib
from pathlib import Path
import subprocess
import tempfile
import os
import signal
from .decisions import check_errors


SKIPPED = {'.git', '.venv', '__pycache__', 'node_modules'}
_FINGERPRINTS = {}


def _files(root):
    """Every file under root, sorted, with the skipped directories pruned rather than walked and filtered."""
    found = []
    for base, directories, names in os.walk(root):
        directories[:] = sorted(d for d in directories if d not in SKIPPED)
        found += [Path(base) / name for name in names]
    return sorted(found, key=lambda path: path.relative_to(root).parts)  # the order Path sorting gave before


def fingerprint(root, cached=True):
    """sha256 over every file's path and content. Assessments bind hundreds of checks to one revision, so with
    `cached` the digest is reused while no file's size or modification time has moved; the acceptance runner,
    which compares before and after a command, always reads every byte (cached=False)."""
    root = Path(root).resolve()
    files = _files(root)
    signature = None
    if cached:
        stats = []
        for path in files:
            try: stat = path.lstat()
            except OSError: continue
            stats.append((path.relative_to(root).as_posix(), stat.st_size, stat.st_mtime_ns, path.is_symlink()))
        signature = hash(tuple(stats))
        known = _FINGERPRINTS.get(str(root))
        if known and known[0] == signature: return known[1]
    digest = hashlib.sha256()
    for path in files:
        rel = path.relative_to(root)
        if path.is_symlink():
            digest.update(str(rel).encode() + b'->' + str(path.readlink()).encode())
        elif path.is_file():
            digest.update(str(rel).encode() + b'\0' + hashlib.sha256(path.read_bytes()).digest())
    value = digest.hexdigest()
    if cached: _FINGERPRINTS[str(root)] = (signature, value)
    return value


def run(check, target, *, execute=False, timeout=60):
    errors = check_errors(check)
    result = {'check_id': check.get('id') if isinstance(check, dict) else None,
              'status': 'blocked', 'executed': False, 'errors': errors}
    if errors: return result
    if check['kind'] == 'human':
        return {**result, 'errors': ['Human review required; a command cannot decide this rubric.']}
    if not execute: return {**result, 'errors': ['Explicit execution authorization required.']}
    target = Path(target).resolve()
    if not target.is_dir(): return {**result, 'errors': ['Candidate directory missing.']}
    before = fingerprint(target, cached=False)
    result['candidate_sha256'] = before
    if before != check['source_revision']:
        return {**result, 'errors': ['Candidate revision differs from the reviewed check binding.']}
    from .runtime.context import redact
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            process = subprocess.Popen(check['argv'], cwd=target, stdout=stdout, stderr=stderr,
                                       start_new_session=(os.name == 'posix'))
            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                if os.name == 'posix': os.killpg(process.pid, signal.SIGKILL)
                else: process.kill()
                process.wait()
                return {**result, 'executed': True, 'errors': ['Command timed out; process group terminated.']}
        except OSError:
            return {**result, 'errors': ['Command unavailable.']}
        stdout.seek(0); stderr.seek(0)
        # Redact full bounded text; do not slice inside a multiline credential.
        output, error = stdout.read(120001), stderr.read(120001)
        if len(output) > 120000 or len(error) > 120000:
            return {**result, 'executed': True, 'status': 'inconclusive', 'errors': ['Output exceeded capture budget.']}
        result.update(executed=True, exit_code=code,
                      stdout=redact(output.decode('utf-8', errors='replace')),
                      stderr=redact(error.decode('utf-8', errors='replace')))
    after = fingerprint(target, cached=False)
    result['after_sha256'] = after
    if before != after:
        return {**result, 'status': 'inconclusive', 'errors': ['Check changed the candidate; review and rebind before acceptance.']}
    return {**result, 'status': 'pass' if code == check['expected_exit'] else 'fail'}
