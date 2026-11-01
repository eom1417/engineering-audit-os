"""What `eaos clean` may remove of the isolated copies under each project's runtimes: only a copy proved to hold nothing of
anyone's. No work is open or waiting on it (the state and the runs say, never its name), nothing in it is uncommitted, each
commit made in it is held by the person's project (those it came with, as its origin refs said when it was cloned, are not its
own, whatever the project did with them since), and whatever git ignores there the project ignores too (node_modules: rebuilt). A copy's
reflog is not counted: every change a check took back is in it. Whatever cannot be proved stays, and is said: a copy may hold
the only trace of a change."""
import shutil
from pathlib import Path

from ...core.project import jobs
from ...core.project.places import home, workspace
from ...core.project.runs import TERMINAL
from ...core.project.state import of_workspace
from ...core.system.files import read_json
from .project import _git

REMOVING, PROVED = '.removing-', '.proved'       # a proved copy moved aside, and a file naming that very folder: a stop leaves it to the next clean
# What a copy's or this computer's settings could hide or run while it is looked at; its filters are its own, EAOS made it.
QUIET = ('-c', 'core.fsmonitor=false', '-c', 'core.excludesFile=', '-c', 'core.ignoreCase=false', '-c', 'core.hooksPath=/dev/null')
UNREADABLE = (OSError, ValueError, KeyError, TypeError, AttributeError)
WHY = {'unknown': ('حالة المشروع مفقودة أو لا تُقرأ', "the project's state is missing or does not read"),
       'project': ('مجلد المشروع غير موجود للمقارنة', "the project's folder is not there to compare with"),
       'working': ('عمل يجري أو ينتظر، أو سجل مهمة أو تشغيل لا يُقرأ (jobs وruns في مجلد المشروع)',
                   "work is running or waiting, or a job's or a run's record does not read (jobs and runs in the project's folder)"),
       'open': ('دفعة مفتوحة', 'a batch is open on it'),
       'folder': ('ليست مستودع git', 'it is not a git repository'),
       'inner': ('فيها مستودعات خاصة بها', 'it holds repositories of its own'),
       'unreadable': ('تعذرت قراءتها', 'it could not be read'),
       'uncommitted': ('فيها تغييرات غير محفوظة', 'it holds uncommitted changes'),
       'commits': ('فيها commits غير موجودة في المشروع', "it holds commits that are not in the project"),
       'failed': ('تعذر حذفها', 'it could not be removed')}


def cleared():
    """(bytes freed, [(the copy kept, why)]) over every project; one that cannot be read stops no other."""
    freed, kept = 0, []
    for folder in (home() / 'projects').glob('*'):
        try: gone, left = _project_cleared(folder)
        except UNREADABLE: gone, left = 0, [(folder, 'unknown')]
        freed += gone
        kept += left
    return freed, kept


def working(folder):
    """Whether a job or a run of this project's EAOS folder may still need its files, or that cannot be told."""
    try: return _waiting(folder)
    except UNREADABLE: return True


def _project_cleared(folder):
    freed, kept, copies = _listed(folder)
    if not copies: return freed, kept
    try:
        with jobs.alone(of_workspace(folder)['project']): gone, left = _judged(folder, copies)     # no job starts while copies go
    except jobs.Busy:
        gone, left = 0, [(copy, 'working') for copy in copies]
    except UNREADABLE:
        gone, left = 0, [(copy, 'unknown') for copy in copies if copy.exists()]
    return freed + gone, kept + left


def _listed(folder):
    """(bytes freed ending a stopped clean, what would not go, the copies to judge) of every runtime of this project."""
    freed, kept, copies = 0, [], []
    for candidates in (*folder.glob('runtime/candidates'), *folder.glob('runtime-*/candidates')):
        gone, left = _stopped_ones_ended(candidates)
        freed, kept = freed + gone, kept + left
        copies += [entry for entry in candidates.iterdir() if entry.is_dir() or entry.is_symlink()]
    return freed, kept, copies


def _stopped_ones_ended(candidates):
    freed, failed = 0, []
    for marker in candidates.glob(f'{REMOVING}*{PROVED}'):
        aside = marker.with_name(marker.name.removesuffix(PROVED))
        if not marker.is_file() or (aside.is_dir() and marker.read_text() != _identity(aside)): continue    # not what it names
        gone, left = _finished(aside, marker)
        freed, failed = freed + gone, failed + left
    return freed, failed


def _finished(aside, marker):
    """(bytes freed, what would not go), the mark going last."""
    size = _size(aside) if aside.is_dir() else 0
    shutil.rmtree(aside, ignore_errors=True)
    if aside.exists(): return 0, [(aside, 'failed')]
    marker.unlink()
    return size, []


def _identity(folder):
    return str(folder.stat().st_ino)


def _judged(folder, copies):
    """Under the jobs' lock, from the state as it is now: a job that ended while this waited may have opened a batch."""
    state = of_workspace(folder)
    why = _none_may_go(folder, state)
    if why: return 0, [(copy, why) for copy in copies]
    opened = _open_folders(state)
    rows = {copy: _why_kept_or_unreadable(copy, state['project'], opened) for copy in copies}
    gone, failed = _removed([copy for copy in rows if not rows[copy]])
    return gone, failed + [(copy, rows[copy]) for copy in rows if rows[copy]]


def _none_may_go(folder, state):
    why = _cannot_tell(state, folder)
    if why: return why
    if _waiting(folder): return 'working'
    return 'unknown' if _open_folders(state) is None else None


def _size(folder):
    from ...live.isolation.sandbox import _size as size
    return size(folder)


def _removed(proved):
    """(bytes freed, those that would not go)."""
    freed, failed = 0, []
    for copy in proved:
        aside = copy.with_name(REMOVING + copy.name)
        marker = aside.with_name(aside.name + PROVED)
        if _moved_aside(copy, aside, marker):
            gone, left = _finished(aside, marker)
            freed, failed = freed + gone, failed + left
        else: failed.append((aside if aside.exists() else copy, 'failed'))
    return freed, failed


def _moved_aside(copy, aside, marker):
    """Moved first: stopped before the mark is written, the copy is intact and only judged again."""
    if marker.exists(): return False
    try:
        copy.rename(aside)
        marker.write_text(_identity(aside))
    except OSError:
        return False
    return True


def _cannot_tell(state, folder):
    """Why this state cannot tell what is safe in `folder`; None when it can."""
    if not isinstance(state, dict) or not state.get('project') or not state.get('workspace'): return 'unknown'
    if {Path(state['workspace']).resolve(), workspace(state['project']).resolve()} != {folder.resolve()}: return 'unknown'
    return None if Path(state['project']).is_dir() else 'project'


def _waiting(folder):
    """Whether a job is alive, a record of a job or a run does not read, a run has not ended (queued, or going on), or the queue names one."""
    if any(_job_holds(path) for path in (folder / 'jobs').glob('*.json')): return True
    runs = folder / 'runs'
    queue = read_json(runs / 'queue.json') if (runs / 'queue.json').exists() else []
    return not all(_ended(run) for run in (*(entry for entry in runs.glob('*') if entry.is_dir() and entry.name != 'chat'), *(runs / str(name) for name in queue)))


def _job_holds(path):
    job = _record(path, 'id', 'status')
    return job is None or (job['status'] == 'running' and jobs._alive(job.get('pid')))


def _ended(run):
    record = _record(run / 'run.json', 'state')
    return bool(record) and record['state'] in TERMINAL


def _record(path, *needed):
    record = read_json(path)
    return record if isinstance(record, dict) and all(key in record for key in needed) else None


def _why_kept_or_unreadable(copy, project, opened):
    try: return _why_kept(copy, project, opened)
    except UNREADABLE: return 'unreadable'


def _why_kept(copy, project, opened):
    if copy.is_symlink(): return 'folder'
    if copy.resolve() in opened: return 'open'
    if not any(copy.iterdir()): return None
    if not _own_repository(copy): return 'folder'
    if _has_repositories(copy): return 'inner'
    return _uncommitted(copy, project) or _commits_only_here(copy, project)


def _open_folders(state):
    """The folders of the batches and the build the state holds open, on any branch; None when one does not say where."""
    try:
        opened = [state.get('open_wave'), state.get('open_build'), *[branch.get('open_wave') for branch in (state.get('by_branch') or {}).values()]]
        roots = [str(batch.get('root') or '') for batch in opened if batch]
    except AttributeError:
        return None
    return {Path(root).resolve() for root in roots} if all(Path(root).is_absolute() for root in roots) else None


def _own_repository(copy):
    """A repository of its own: git would otherwise answer for one around it."""
    top = _git(copy, 'rev-parse', '--show-toplevel')
    return (copy / '.git').is_dir() and not top.returncode and Path(top.stdout.strip()).resolve() == copy.resolve()


def _has_repositories(copy):
    """Repositories inside, which git would not look into: filled submodules, or linked work folders."""
    stage = _git(copy, *QUIET, 'ls-files', '--stage', '-z')
    links = [row.split('\t', 1)[1] for row in stage.stdout.split('\0') if row.startswith('160000 ')]
    return stage.returncode or any(path.is_dir() and any(path.iterdir()) for path in (copy / link for link in links)) or \
        any((copy / '.git' / inner).exists() for inner in ('modules', 'worktrees'))


def _uncommitted(copy, project):
    """Why what is in the copy's files is not all in its commits or rebuilt, or None: a file git was told not to look at, a
    change, an untracked file, or an ignored one the project itself would not ignore."""
    status = _git(copy, *QUIET, 'status', '--porcelain', '-z', '--untracked-files=all', '--ignored=matching', '--ignore-submodules=none')
    looked_at = _git(copy, *QUIET, 'ls-files', '-v')
    if status.returncode or looked_at.returncode: return 'unreadable'
    rows = [row for row in status.stdout.split('\0') if row]
    hidden = any(line[:1] != 'H' for line in looked_at.stdout.splitlines())
    return 'uncommitted' if hidden or not all(_rebuilt(row, project) for row in rows) else None


def _rebuilt(row, project):
    return row.startswith('!! ') and not _git(project, *QUIET, 'check-ignore', '-q', '--no-index', '--', row[3:]).returncode


def _commits_only_here(copy, project):
    kinds = _git(copy, 'for-each-ref', '--format=%(objecttype) %(*objecttype)')
    if kinds.returncode or {'blob', 'tree'} & set(kinds.stdout.split()): return 'unreadable' if kinds.returncode else 'commits'
    made = _git(copy, 'rev-list', 'HEAD', '--all', '--not', *_as_cloned(copy))
    if made.returncode: return 'unreadable'
    if not made.stdout.strip(): return None
    held = _git(project, 'rev-list', '--all')
    return 'commits' if held.returncode or set(made.stdout.split()) - set(held.stdout.split()) else None


def _as_cloned(copy):
    """What its origin refs said when it was cloned. A ref with no reflog has not moved since, and the first line of one that
    has says what it held before; one the copy made itself held nothing. A push or a fetch of its own moves them."""
    refs = _git(copy, 'for-each-ref', '--format=%(objectname) %(refname)', 'refs/remotes/origin').stdout.splitlines()
    return [sha for sha in (_cloned_value(copy, *row.split()) for row in refs) if sha]


def _cloned_value(copy, now, ref):
    log = copy / '.git' / 'logs' / ref
    if not log.is_file(): return now
    before = log.read_text(errors='replace').split(maxsplit=1)[0]
    return before if set(before) != {'0'} else None
