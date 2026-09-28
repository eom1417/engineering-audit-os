"""Long EAOS work as a job an AI assistant follows (docs/MCP.md).

A check takes minutes and a batch of fixes longer; an assistant's tool call does not wait that long. So each
long piece of work runs as its own process, detached from the MCP server (it survives the assistant closing),
and writes what it has done to ~/.eaos/jobs/<id>.json:

  {"id", "kind", "project", "status": "running" | "done" | "failed", "progress": {"done", "total", "stage"},
   "result": {...} once done, "error": "..." once failed, "log": path, "started", "ended", "pid"}

`start` launches one; `read` and `wait` follow it. The work itself is JOBS[kind] of the module the record names
(`runner`, eaos.agent_tools by default), found by name so that it and this module do not import each other.
"""
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path


def folder():
    from .guided import home
    return home() / 'jobs'


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _path(job):
    if not job or '/' in job or '..' in job: raise ValueError(f'no job named {job!r}')
    return folder() / f'{job}.json'


def _write(record):
    path = _path(record['id'])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    temporary.replace(path)


def read(job):
    path = _path(job)
    if not path.is_file(): raise ValueError(f'no job named {job!r}')
    record = json.loads(path.read_text(encoding='utf-8'))
    if record['status'] == 'running' and not _alive(record.get('pid')):
        record.update(status='failed', error='the job stopped before it finished (the computer slept or the process was killed); start it again',
                      ended=_now())
        _write(record)
    return record


def _alive(pid):
    if not pid: return True                 # not launched yet: the launcher writes the pid next
    try: os.kill(pid, 0)
    except ProcessLookupError: return False
    except PermissionError: return True
    try:                                    # a finished child not yet reaped is not alive
        return os.waitpid(pid, os.WNOHANG) == (0, 0)
    except ChildProcessError:
        return True


def running(project, kind=None):
    """The job still running for this project (and kind), if any: one piece of work at a time per project."""
    if not folder().is_dir(): return None
    for path in sorted(folder().glob('*.json'), reverse=True):
        try: record = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError): continue
        if record.get('project') == str(project) and record.get('status') == 'running' and (kind is None or record['kind'] == kind):
            record = read(record['id'])
            if record['status'] == 'running': return record
    return None


def start(kind, project, arguments, runner='eaos.agent_tools'):
    job = f"{kind}-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{os.urandom(2).hex()}"
    log = folder() / f'{job}.log'
    record = {'id': job, 'kind': kind, 'runner': runner, 'project': str(project), 'arguments': arguments, 'status': 'running',
              'progress': None, 'result': None, 'error': None, 'log': str(log), 'started': _now(), 'ended': None, 'pid': None}
    _write(record)
    with log.open('w', encoding='utf-8') as out:
        process = subprocess.Popen([sys.executable, '-m', 'eaos.jobs', job], stdout=out, stderr=subprocess.STDOUT,
                                   stdin=subprocess.DEVNULL, start_new_session=True, env={**os.environ, 'PYTHONUNBUFFERED': '1'})
    record = json.loads(_path(job).read_text(encoding='utf-8'))
    record['pid'] = process.pid
    _write(record)
    return job


def wait(job, seconds):
    """The job's record once it ends, or after `seconds`, whichever comes first."""
    until = time.monotonic() + max(0, seconds)
    record = read(job)
    while record['status'] == 'running' and time.monotonic() < until:
        time.sleep(1)
        record = read(job)
    return record


def progress(job, done, total, stage):
    record = json.loads(_path(job).read_text(encoding='utf-8'))
    record['progress'] = {'done': done, 'total': total, 'stage': stage}
    _write(record)


def run(job):
    """The job process: the work, then its result or its error in the record."""
    import importlib
    record = json.loads(_path(job).read_text(encoding='utf-8'))
    try:
        work = importlib.import_module(record.get('runner') or 'eaos.agent_tools').JOBS[record['kind']]
        result = work(record['project'], record['arguments'], lambda *step: progress(job, *step))
        record = json.loads(_path(job).read_text(encoding='utf-8'))
        record.update(status='done', result=result, ended=_now())
    except BaseException as problem:        # every ending is written down, so the assistant is never left waiting
        traceback.print_exc()
        record = json.loads(_path(job).read_text(encoding='utf-8'))
        record.update(status='failed', error=f'{type(problem).__name__}: {problem}'[-3000:], ended=_now())
    _write(record)
    return 0 if record['status'] == 'done' else 1


if __name__ == '__main__':
    raise SystemExit(run(sys.argv[1]))
