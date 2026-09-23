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


def fingerprint(root):
    root = Path(root).resolve()
    digest = hashlib.sha256()
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root)
        if any(part in {'.git', '.venv', '__pycache__', 'node_modules'} for part in rel.parts): continue
        if path.is_symlink():
            digest.update(str(rel).encode() + b'->' + str(path.readlink()).encode())
        elif path.is_file():
            digest.update(str(rel).encode() + b'\0' + hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


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
    before = fingerprint(target)
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
    after = fingerprint(target)
    result['after_sha256'] = after
    if before != after:
        return {**result, 'status': 'inconclusive', 'errors': ['Check changed the candidate; review and rebind before acceptance.']}
    return {**result, 'status': 'pass' if code == check['expected_exit'] else 'fail'}
