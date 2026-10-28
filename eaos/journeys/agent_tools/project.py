"""The project an assistant's call is about, its state, and its jobs: a call that takes longer than a tool call waits
returns a job (eaos/core/project/jobs.py) that `wait` follows; the Studio opened on it.
"""
import json
import os
from pathlib import Path

from .. import guided
from ...core.project import jobs
from ...core.system import launch
from ...core import toolchain
from ...core.project import state as project_state
from ...core.system.clock import now


# A person's answer comes at least this long after the question: sooner, nobody was asked (EAOS_ANSWER_SECONDS: tests).
ANSWER_SECONDS, WAIT = int(os.environ.get('EAOS_ANSWER_SECONDS') or 30), 50   # WAIT: seconds a tool call waits for its job
PAGE, EVIDENCE = 30, 24     # EVIDENCE: facts shown behind one card, enough for every function its check judges


# ---------------------------------------------------------------- the project and its state

class SeveralProjects(ValueError):
    """A folder that is no project but holds several git repositories directly under it: the person says which."""
    def __init__(self, folder, projects):
        super().__init__(f'{folder} holds several projects: {", ".join(str(p) for p in projects[:10])}; pass one as `project`')
        self.projects = projects


def repositories_under(folder):
    """The git repositories directly under `folder` (one level down), sorted."""
    try: return sorted(child for child in Path(folder).iterdir() if child.is_dir() and (child / '.git').exists())
    except OSError: return []


def locate(folder):
    """The project a folder means: itself when it is one (eaos/core/project/state.looks_like_project); a folder with no project file
    and exactly one git repository directly under it (the assistant opened in the folder above) means that repository; with several, SeveralProjects: the
    person chooses, EAOS never guesses."""
    if not folder.is_dir() or project_state.looks_like_project(folder): return folder
    found = repositories_under(folder)
    if len(found) > 1: raise SeveralProjects(folder, found)
    return found[0] if found else folder


def _project_folder(project, new):
    """The project's folder, checked: made when it is to be built, else it must exist and look like a project."""
    folder = Path(project or os.getcwd()).expanduser().resolve()
    if not new and not _state_in(folder): folder = locate(folder)
    if new or (_state_in(folder) or {}).get('mode') == 'build':
        if folder in (Path.home().resolve(), Path(folder.anchor)):
            raise ValueError(f'not a project folder: {folder} (make an empty folder for the new project and open the assistant there)')
        folder.mkdir(parents=True, exist_ok=True)
        return folder
    if not folder.is_dir(): raise ValueError(f'project folder not found: {folder}')
    if not project_state.looks_like_project(folder):
        raise ValueError(f'not a project folder: {folder} (no .git, package.json or other project file at its top; '
                         'pass the project folder as `project`)')
    return folder


def _state_in(folder):
    """The EAOS state kept for `folder`, None when it is not a folder or has none."""
    return project_state.load(folder) if folder.is_dir() else None


def state_of(project=None, new=False):
    """The project's state, made on first use. `new`: a project still to be built from its plan, whose folder may be
    empty or not there yet (it is made); never the home folder or the disk's root."""
    folder = _project_folder(project, new)
    state = project_state.load(folder)
    if not state:
        state = {'schema_version': 1, 'project': str(folder), 'workspace': str(guided.workspace(folder)),
                 'started': now(), 'questions': [], 'lang': guided.language()}
    # its report's folder kept from the start: a run of its app is shown only that folder (eaos/live/isolation/sandbox.py _own)
    if not state.get('outputs') and guided.outputs(state): guided.save(state)
    return state


def _head(state):
    """The last commit of the branch EAOS works on (eaos/core/project/branches.py)."""
    return guided.tip(state)


def tool_digest():
    """This EAOS's own code, as a fingerprint (eaos/core/system/version_info.py): a report made by an older EAOS is checked again."""
    from ...core.system.version_info import digest
    return digest()


def _current(state, head):
    """The check on record is for this code (this commit, or it plus EAOS's own merged fixes), by this EAOS."""
    return guided.same_code(state, state.get('scanned_commit'), head) and state.get('scanned_with') == tool_digest()


def _report(state):
    report = guided.report_of(state)
    if not (report / 'plan.json').is_file():
        raise LookupError('this project has not been checked yet: call `audit` first')
    return report


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _job_answer(job, seconds, project):
    """A job's record as a tool answers it: the result when it ended in time, else how to follow it."""
    record = jobs.wait(job, seconds, project)
    if record['status'] == 'done': return {'job': job, 'status': 'done', **(record['result'] or {})}
    if record['status'] == 'failed':
        return {'job': job, 'status': 'failed', 'error': record['error'], 'log': record['log'],
                'what_now': guided.explain(RuntimeError(record['error']))['en']['fix']}
    return {'job': job, 'status': 'running', 'progress': record['progress'], 'started': record['started'],
            'what_now': f'Call `wait` with job="{job}" to follow it; keep going until it is done.'}


def _start(kind, state, arguments, seconds=WAIT, runner='eaos.journeys.agent_tools', watch=False):  # limits: parameters -- the job and how it is waited for, run and watched, each set apart by its callers
    """Start a job once the project's running one ended (waited for up to `seconds`: eaos/journeys/fix/lanes.py), and answer as `_job_answer`
    does. `watch`: the live Studio is opened on its map first (once, before the job writes anything), its address in `watch`."""
    route = '/scan' if kind != 'audit' or toolchain.ready(state['project']) else '/tools'
    studio = _watch(state, route) if watch and not jobs.running(state['project']) else None
    try:
        with jobs.alone(state['project'], seconds): job = jobs.start(kind, state['project'], arguments, runner=runner)
    except jobs.Busy as busy:
        return {'job': busy.record['id'], 'status': 'busy', 'kind': busy.record['kind'], 'progress': busy.record['progress'],
                'what_now': f"Another piece of work is running for this project: call `wait` with job=\"{busy.record['id']}\" first."}
    answer = _job_answer(job, seconds, state['project'])
    if studio and route == '/tools':
        answer.update(watch=studio['studio'], what_now=TOOLS_FIRST)
    elif studio:
        told = ('Tell the person the live map of this work is open in their browser.' if studio['opened_in_browser'] else
                'Before anything else, write the person a message with the `watch` address, the live map of this work, which '
                'still shows how it went once it ends and stays the same every time (it opens on this computer only).')
        answer.update(watch=studio['studio'], what_now=f"{told} {answer.get('what_now', '')}".strip())
    return answer


TOOLS_FIRST = ('Tell the person the EAOS Studio is open on "Preparing the tools" (give them the `watch` address if it did not '
               'open in their browser): every tool it installs, live; the check starts by itself once the tools it needs '
               'are ready. Then call `wait` with the job to follow it. If it fails because a tool could not be installed, '
               'the person picks Retry or "Start without it" there, or tells you, and you call `tools_check` with '
               'retry=true, or `audit` with without_tools=true.')


def _watch(state, route='/scan'):
    """open_studio on `route`, in the browser unless the Studio asked (EAOS_STUDIO_RUN); None headless or when it cannot start."""
    try: opened = {} if os.environ.get(launch.HEADLESS) else open_studio(state['project'], show=not os.environ.get('EAOS_STUDIO_RUN'), route=route)
    except Exception: return None
    return opened if 'studio' in opened else None


def open_studio(project=None, show=True, route='', address=None):
    """`open_studio`: the live Studio's address (on `route`, when given), starting its server in the background when it
    is not running. The server runs from the EAOS workspace folder with PYTHONSAFEPATH=1, so neither the folder it
    starts in nor the project (which may be EAOS's own repository) can put another `eaos` before this one. It rebuilds
    no data: a server it starts does (run_foreground), and a running one's is kept by every step that changes it, so a
    check asked for starts at once. `address`: this computer is a remote server reached at that routed address
    (launch.serve_remotely); a running Studio that answers elsewhere starts again there."""
    state = state_of(project)
    if address:
        try: pattern = launch.serve_remotely(address)
        except ValueError as problem: return {'error': str(problem), 'what_now': 'Pass the exact https address your environment routes to a port.'}
        running = launch.running(state)
        if running and running.get('remote_origin') != pattern.format(port=running['port']): launch.stop(running)
    found, started = launch.start(state)
    if not found:
        return {'error': 'the Studio server did not start in time', 'log': str(Path(state['workspace']) / 'logs/studio-server.log'),
                'what_now': 'Tell the person the live Studio could not start, and offer open_report (the report page) instead.'}
    url = launch.url_of(found, route)
    opened = launch._open(url, show)
    return {'studio': url, 'opened_in_browser': opened, 'started': started, 'live': True,
            'checked': guided.scan_done(state),
            'what_now': ('Tell the person the Studio is open in their browser' if opened else
                         'Send the person this address now, without being asked: it stays the same, and the Studio keeps '
                         'running on this server after your session ends' if found.get('remote_origin') else
                         'Give the person this address to open in their browser on this computer (it works only here)')
                        + '; it updates by itself after every check, batch, merge and decision. '
                        + ('' if guided.scan_done(state) else 'The project is not checked yet: offer audit first. ')
                        + 'Do not paste the address anywhere else.'}


def wait(job, seconds=WAIT, project=None):          # a job of this project only: another project's is not found
    return _job_answer(job, min(max(int(seconds), 0), 300), state_of(project)['project'])
