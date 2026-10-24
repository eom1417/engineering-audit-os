"""The install runs: one at a time on a computer (`machine_lock`), WORKERS tools at once, each tool a stage of the
`tools` flow; started in the background when EAOS opens on a project (`prepare`); what the check waits for
(`readiness`); and the `eaos tools` command (`main`)."""
import fcntl
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

from .. import progress
from .installers import _ensure
from .pins import Unavailable, home, needed, ordered, project_files, registry, selected
from .versions import doctor

FLOW = 'tools'
# Tools installed at once: the downloads overlap, and a 4 GB computer copes with three npm installs side by side
WORKERS = 3


def _install_one(tool, log, echo):
    """One tool as one stage of the tools flow; its name when it could not be installed, else ''."""
    name, began = tool['name'], time.monotonic()
    log.stage_started(name)
    row = {'stage': name, 'status': 'ok', 'reason': '', 'necessity': 'required', 'artifacts': []}
    try:
        _ensure(tool, log.stepper(name), echo)
    except Unavailable as problem:
        echo(f"skip    {problem}")
        row.update(status='unavailable', reason=str(problem), reason_code='tool_unavailable')
    except Exception as problem:              # one tool that fails, however, never stops the others
        row.update(status='failed', reason=f'{type(problem).__name__}: {problem}'[:300], reason_code='tool_failed')
        echo(f"FAILED  {name}: {row['reason']}")
    log.ended({**row, 'seconds': round(time.monotonic() - began, 2)})
    return name if row['status'] == 'failed' else ''


@contextmanager
def machine_lock(wait=True):
    """One install at a time on this computer, whichever project or command asked: a second waits for the first
    (`wait=False`: yields False at once instead)."""
    path = home() / 'install.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as handle:
        try: fcntl.flock(handle, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        except BlockingIOError:
            yield False
            return
        yield True


def installing():
    """Whether an install holds the lock now (nothing is written to find out)."""
    path = home() / 'install.lock'
    if not path.exists(): return False
    with path.open() as handle:
        try: fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: return True
    return False


def stages(tools):
    """The tools as the stages of the tools flow, each described by its pinned version."""
    return [progress.Stage(tool['name'], description=tool['version']) for tool in tools]


def install(names=None, stage=None, skip=(), echo=print, project=None):
    """Install what is missing or at another version, WORKERS at a time, in the order the check needs them on
    `project`, each tool a stage of the tools flow; asked again while it ran (`prepare`), it runs once more for what
    failed. Returns the tools that could not be installed."""
    tools = ordered(selected(names, stage, skip), project_files(project) if project else ())
    with machine_lock():
        failed = _run(tools, echo)
        while failed and _asked_again(): failed = _run(tools, echo)
    return failed


def _run(tools, echo):
    log = progress.ProgressLog(home(), FLOW, sampler=False)
    log.started(stages(tools), [tool['name'] for tool in tools], {})
    began = time.monotonic()
    with ThreadPoolExecutor(WORKERS) as pool:
        failed = [name for name in pool.map(lambda tool: _install_one(tool, log, echo), tools) if name]
    log.finish('INCOMPLETE' if failed else 'COMPLETE', seconds=round(time.monotonic() - began, 2))
    return failed


def _asked_again():
    asked = home() / 'install.again'
    if not asked.exists(): return False
    asked.unlink()
    return True


def stale():
    """Whether the next start installs again: the last install did not end with every tool ready, a tool's pin changed
    since, or a tool's command is gone."""
    state = progress.fold(progress.read(home(), FLOW))
    if state['status'] != 'COMPLETE': return True
    pinned = {s['name']: s['description'] for s in state['stages']}
    tools = registry()['tools']
    commands = [t for t in tools if t['install']['method'] != 'git' and not t['install'].get('library')]
    return any(pinned.get(t['name']) != t['version'] for t in tools) or any(not (home() / 'bin' / t['binary']).exists() for t in commands)


def _spawn(argv, log):
    """`python -m eaos <argv>` of this same EAOS, on its own: it outlives whoever started it."""
    here = str(Path(__file__).resolve().parents[3])
    env = {**os.environ, 'PYTHONSAFEPATH': '1', 'PYTHONPATH': os.pathsep.join([here, *filter(None, [os.environ.get('PYTHONPATH')])])}
    home().mkdir(parents=True, exist_ok=True)
    with open(home() / log, 'ab') as out:
        return subprocess.Popen([sys.executable, '-m', 'eaos', *argv], cwd=home(), env=env, stdin=subprocess.DEVNULL,
                                stdout=out, stderr=out, start_new_session=True, close_fds=True)


def prepare(project=None):
    """Interface first: called when EAOS opens on a project, it starts the full install in the background when one is
    needed (`stale`), in the project's order, and waits until it holds the lock; an install already running is asked to
    retry what failed once it ends. True when it started the install."""
    if home().exists() and not os.access(home(), os.W_OK): return False   # shown read-only (in a sandbox): used as is
    if installing():
        (home() / 'install.again').touch()
        return False
    if not stale(): return False
    child = _spawn(['tools', 'install', *(['--project', str(project)] if project else [])], 'install.log')
    deadline = time.monotonic() + 30
    while child.poll() is None and not installing() and time.monotonic() < deadline: time.sleep(0.1)
    return True


def readiness(files):
    """What the check waits for on a project with these files: {needed, pending, failed: {name: reason}, ready}. A
    needed tool is ready once its stage of the last install ended ok (or it has no build for this computer); pending
    while an install runs and has not finished it; failed otherwise, with the reason its install gave."""
    state = progress.fold(progress.read(home(), FLOW))
    shown = {s['name']: s for s in state['stages']}
    running = installing()
    pending, failed = [], {}
    for name in needed(files):
        stage = shown.get(name) or {'state': 'waiting', 'reason': ''}
        if stage['state'] in ('ok', 'unavailable'): continue
        if running and stage['state'] in ('waiting', 'running'): pending.append(name)
        else: failed[name] = stage['reason'] or 'not installed'
    return {'needed': needed(files), 'pending': pending, 'failed': failed, 'ready': not pending and not failed}


def ready(project):
    """Whether every tool the check needs on `project` is ready now."""
    return readiness(project_files(project))['ready']


def wait_for_check(project, echo=lambda done, total: None, install=True, every=2.0):
    """The readiness of the check's tools on `project` once none of them is still coming. When they are not all ready
    it starts the install first (`install`; a failed tool is tried again), then calls `echo(done, total)` each time
    another of them is ready or failed."""
    files, said = project_files(project), None
    if install and not readiness(files)['ready']: prepare(project)
    while True:
        gate = readiness(files)
        done = len(gate['needed']) - len(gate['pending'])
        if done != said: echo(done, len(gate['needed']))
        said = done
        if not gate['pending']: return gate
        time.sleep(every)


def _show(report, as_json):
    if as_json: print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        for row in report['tools']:
            print(f"{'ok  ' if row['ok'] else 'MISS'} {row['name']:20} pinned {row['pinned']:10} {row['found'] or '-':10} {row['reason']}")
    return 0 if all(row['ok'] for row in report['tools']) else 1


def main(args):
    names = args.only.split(',') if getattr(args, 'only', None) else None
    skip = args.skip.split(',') if getattr(args, 'skip', None) else ()
    if args.action == 'doctor': return _show(doctor(names, args.stage, skip), args.json)
    return 1 if install(names, args.stage, skip, project=args.project) else 0
