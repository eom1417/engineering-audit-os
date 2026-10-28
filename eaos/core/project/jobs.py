"""Long EAOS work as a job an AI assistant follows (docs/MCP.md).

A check takes minutes and a batch of fixes longer; an assistant's tool call does not wait that long. So each
long piece of work runs as its own process, detached from the MCP server (it survives the assistant closing),
and writes what it has done to the project's own ~/.eaos/projects/<workspace>/jobs/<id>.json:

  {"id", "kind", "project", "status": "running" | "done" | "failed", "progress": {"done", "total", "stage"},
   "result": {...} once done, "error": "..." once failed, "log": path, "started", "ended", "pid"}

`start` launches one; started under `alone`, one at a time per project: a second waits its turn (the assistants of one
batch, eaos/journeys/fix/lanes.py, take turns at EAOS's checks). `read` and `wait` follow a job, for the project
they name only: another project's job is not found.
A project keeps its last KEEP jobs. The analyzers a job runs keep their caches in the project's own cache folder
(EAOS_ENGINE_CACHE, eaos/engines/process.py), removed when the job ends: no project reads what another's left. The work itself is JOBS[kind] of the module the record names (`runner`,
eaos.journeys.agent_tools by default), found by name so that it and this module do not import each other.
"""
import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from ...core.system.files import read_json


KEEP = 30           # the jobs a project keeps; older ended ones go with their logs
LEGACY_DAYS = 1     # the one folder older EAOS versions shared between projects goes once none of it is this recent


def folder(project):
    from .places import workspace
    return workspace(project) / 'jobs'


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def cache(project):
    return folder(project).parent / 'cache'


def _path(job, project):
    if not job or '/' in job or '..' in job: raise ValueError(f'no job named {job!r}')
    return folder(project) / f'{job}.json'


def _write(record):
    path = _path(record['id'], record['project'])
    path.parent.mkdir(parents=True, exist_ok=True)
    # a temporary file of its own per writer (as core/project/runs.py): the job and its progress write the same record at
    # once, and a shared name was renamed away under the other (the golden trial's clean twin, 2026-10-27)
    temporary = path.with_name(path.name + f'.{os.getpid()}.{threading.get_ident()}.tmp')
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    temporary.replace(path)


def read(job, project):
    path = _path(job, project)
    if not path.is_file(): raise ValueError(f'no job named {job!r} in this project')
    record = json.loads(path.read_text(encoding='utf-8'))
    if record['status'] == 'running' and not _alive(record.get('pid')):
        record.update(status='failed', ended=_now(), error='the job stopped before it finished (the computer slept or the process was '
                      'killed); start it again' + (': the batch keeps every change it kept, and fix_finish goes on from them'
                                                   if record.get('kind') == 'fix_finish' else ''))
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
    for path in sorted(folder(project).glob('*.json'), reverse=True):
        record = read_json(path, {})
        if record.get('status') == 'running' and (kind is None or record['kind'] == kind):
            record = read(record['id'], project)
            if record['status'] == 'running': return record
    return None


def fixing(project):
    """Whether a job of the open fix batch (its start, an edit, its hand-over) is running."""
    return any(running(project, kind) for kind in ('fix_start', 'fix_edit', 'fix_finish'))


def _prune(project):
    """Keep the project's last KEEP jobs (a running one always), and drop the shared folder of older versions."""
    for path in sorted(folder(project).glob('*.json'), key=lambda found: found.stat().st_mtime)[:-KEEP]:
        running = read_json(path, {}).get('status') == 'running'
        if not running:
            path.unlink(missing_ok=True)
            path.with_suffix('.log').unlink(missing_ok=True)
    from .places import home
    legacy = home() / 'jobs'
    if legacy.is_dir() and all(time.time() - found.stat().st_mtime > LEGACY_DAYS * 86400 for found in legacy.iterdir()):
        shutil.rmtree(legacy, ignore_errors=True)


class Busy(Exception):
    """Another job of the project still runs: `record` is its."""

    def __init__(self, record):
        super().__init__(record['id'])
        self.record = record


@contextmanager
def alone(project, wait=0):
    """The project's jobs held: none starts, and none runs once the one running ended, waited for up to `wait` seconds
    (Busy after it)."""
    folder(project).mkdir(parents=True, exist_ok=True)
    with open(folder(project) / '.turn.lock', 'a') as turn:
        fcntl.flock(turn, fcntl.LOCK_EX)
        until = time.monotonic() + wait
        while (busy := running(project)) and time.monotonic() < until: time.sleep(1)
        if busy: raise Busy(busy)
        yield


def start(kind, project, arguments, runner='eaos.journeys.agent_tools'):
    job = f"{kind}-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{os.urandom(2).hex()}"
    log = folder(project) / f'{job}.log'
    record = {'id': job, 'kind': kind, 'runner': runner, 'project': str(project), 'arguments': arguments, 'status': 'running',
              'progress': None, 'result': None, 'error': None, 'log': str(log), 'started': _now(), 'ended': None, 'pid': None}
    _write(record)
    pid = _launch(job, project, log)
    record = json.loads(_path(job, project).read_text(encoding='utf-8'))
    record['pid'] = pid
    _write(record)
    _prune(project)
    return job


def _launch(job, project, log):
    """The job's process: a systemd service of the computer where its Studios are (launch.durable: a remote server ends
    an assistant's session with everything it started, a batch's hand-over among it), else a process in a session of
    its own. Its pid."""
    from ..system import launch
    argv = [sys.executable, '-m', 'eaos.core.project.jobs', job, str(project)]
    env = {**os.environ, 'PYTHONUNBUFFERED': '1', 'EAOS_ENGINE_CACHE': str(cache(project))}
    log.write_text('', encoding='utf-8')
    unit = 'eaos-job-' + job
    if launch.durable() and launch.as_unit(unit, argv, env, {'description': f'EAOS {job}', 'log': log, 'cwd': folder(project)}):
        for _ in range(50):          # None: it ended already, its record says how
            if (pid := launch.unit_pid(unit)) or _path(job, project).read_text(encoding='utf-8').find('"running"') < 0: return pid
            time.sleep(0.1)
        return None
    with log.open('w', encoding='utf-8') as out:
        return subprocess.Popen(argv, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True, env=env).pid  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- EAOS starts itself (sys.executable -m eaos), a list argv, no shell


def wait(job, seconds, project):
    """The job's record once it ends, or after `seconds`, whichever comes first."""
    until = time.monotonic() + max(0, seconds)
    record = read(job, project)
    while record['status'] == 'running' and time.monotonic() < until:
        time.sleep(1)
        record = read(job, project)
    return record


def progress(job, project, done, total, stage):
    record = json.loads(_path(job, project).read_text(encoding='utf-8'))
    record['progress'] = {'done': done, 'total': total, 'stage': stage}
    _write(record)


def run(job, project):
    """The job process: the work, then its result or its error in the record. A stop (SIGTERM, the Studio's stop)
    ends the work as an interrupt does, so what it started, such as an assistant in its own session, is ended too."""
    import importlib
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    path = _path(job, project)
    record = json.loads(path.read_text(encoding='utf-8'))
    try:
        runner = record.get('runner') or 'eaos.journeys.agent_tools'
        if not runner.startswith('eaos.'): raise ValueError(f'a job runs only in EAOS, not in {runner}')
        work = importlib.import_module(runner).JOBS[record['kind']]  # nosemgrep: python.lang.security.audit.non-literal-import -- the runner EAOS wrote in its own job record, one of eaos's modules (checked above)
        result = work(record['project'], record['arguments'], lambda *step: progress(job, project, *step))
        record = json.loads(path.read_text(encoding='utf-8'))
        record.update(status='done', result=result, ended=_now())
    except BaseException as problem:        # every ending is written down, so the assistant is never left waiting
        traceback.print_exc()
        record = json.loads(path.read_text(encoding='utf-8'))
        record.update(status='failed', error=f'{type(problem).__name__}: {problem}'[-3000:], ended=_now())
    shutil.rmtree(cache(project), ignore_errors=True)
    _write(record)
    return 0 if record['status'] == 'done' else 1


if __name__ == '__main__':
    raise SystemExit(run(sys.argv[1], sys.argv[2]))
