"""The project an assistant's call is about, its state, and its jobs: a call that takes longer than a tool call waits
returns a job (eaos/core/project/jobs.py) that `wait` follows.
"""
import json
import os
from pathlib import Path

from .. import guided
from ...core.project import jobs
from ...core.project import state as project_state
from ...core.system.clock import now


# A person's answer comes at least this long after the question: sooner, nobody was asked (EAOS_ANSWER_SECONDS: tests).
# WAIT: seconds a tool call waits for its job
ANSWER_SECONDS, WAIT = int(os.environ.get('EAOS_ANSWER_SECONDS') or 30), 50
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
    """The project a folder means: itself when it is one (eaos/core/project/state.looks_like_project); a folder with
    no project file and exactly one git repository directly under it (the assistant opened in the folder above)
    means that repository; with several, SeveralProjects: the person chooses, EAOS never guesses."""
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
    # its report's folder kept from the start: a run of its app is shown only that folder
    # (eaos/live/isolation/sandbox.py _own)
    if not state.get('outputs') and guided.outputs(state): guided.save(state)
    return state


def _head(state):
    """The last commit of the branch EAOS works on (eaos/core/project/branches.py)."""
    return guided.tip(state)


def tool_digest():
    """This EAOS's own code, as a fingerprint (eaos/core/system/version_info.py): a report made by an older EAOS is
    checked again."""
    from ...core.system.version_info import digest
    return digest()


def _current(state, head):
    """The check on record is for this code (this commit, or it plus EAOS's own merged fixes), by this EAOS."""
    return guided.same_code(state, state.get('scanned_commit'), head) and state.get('scanned_with') == tool_digest()


def _report(state):
    report = guided.report_of(state)
    if not (report / 'plan.json').is_file():
        raise LookupError(_stopped(report) or 'this project has not been checked yet: call `audit` first')
    return report


def _stopped(report):
    """The step a check that ran stopped at and why, from its manifest; '' when no check ran here."""
    path = report / 'run-manifest.json'
    stages = (_read(path).get('stages') or {}) if path.is_file() else {}
    name, row = next(((name, row) for name, row in stages.items() if row.get('status') == 'failed'), (None, None))
    return f"the check stopped at its `{name}` step: {row.get('reason') or 'no reason recorded'}"[:600] if name else ''


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


def busy_answer(record):
    """What a tool answers when something holds the project and it did nothing: `error` makes a run say so,
    not `done`."""
    job = record['id']
    return {'job': job, 'status': 'busy', 'kind': record['kind'], 'progress': record.get('progress'),
            'error': f"a {record['kind']} is running for this project, so nothing was done",
            'what_now': (f'Another piece of work is running for this project: call `wait` with job="{job}" first, then ask again.' if job else
                         'Another step is at work on this project: ask again in a moment.')}


def _start(kind, state, arguments, seconds=WAIT, runner='eaos.journeys.agent_tools'):
    """Start a job once the project's running one ended (waited for up to `seconds`: eaos/journeys/fix/lanes.py),
    and answer as `_job_answer` does."""
    try:
        with jobs.alone(state['project'], seconds): job = jobs.start(kind, state['project'], arguments, runner=runner)
    except jobs.Busy as busy:
        return busy_answer(busy.record)
    return _job_answer(job, seconds, state['project'])


def wait(job, seconds=WAIT, project=None):          # a job of this project only: another project's is not found
    return _job_answer(job, min(max(int(seconds), 0), 300), state_of(project)['project'])
