"""What a sandboxed command sees of the disk (eaos/live/sandbox.py runs it, eaos/live/sandbox_view.py applies the view):
the real folders hidden from it, the ones its run owns, and the mounts that hide the first and show again what it is
given inside the second; and whether this kernel gives a command a view of its own at all."""
import functools
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

LAUNCHER = Path(__file__).with_name('sandbox_view.py')


def _launcher(spec):
    return [sys.executable, '-I', str(LAUNCHER), json.dumps(spec)]


@functools.cache
def _view_refusal():
    """'' when a command can have a view of its own run here (a user and a mount namespace), else why it cannot."""
    try:
        done = subprocess.run([*_launcher({'offline': True, 'cwd': '/', 'mounts': [['hide', tempfile.gettempdir()]]}), 'true'],
                              capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as problem:
        return str(problem)[:200]
    return '' if done.returncode == 0 else (done.stderr.strip()[-200:] or f'exit {done.returncode}')


def hidden():
    """The real folders a sandboxed command never sees: the person's HOME, EAOS's home, its projects and Studio records,
    the reports, the temporary folder (other runs' databases), and every project EAOS knows with its report, the run's
    own included (it sees its copy, never the working folder and its .env). The outermost ones only."""
    from ..core.places import home, outputs_root
    folders = [Path.home(), home(), home() / 'projects', home() / 'studio', outputs_root(), Path('/tmp'), Path(tempfile.gettempdir())]  # nosec B108: hidden, never written
    from ..core.project_state import every
    folders += [Path(state[key]) for state in every() for key in ('project', 'outputs') if state.get(key)]
    real = {Path(os.path.realpath(folder)) for folder in folders if folder.is_dir()} - {Path('/')}
    return sorted(folder for folder in real if not any(other in folder.parents for other in real))


def _own(target, runtime):
    """The real folders a run's command may be shown again when it is given a path in them: its project's own EAOS
    workspace (records, runtime, data), its own report, and the runtime it runs from (a batch's candidate copy is
    another folder than the project, but its records, the lock's reports among them, are the project's); never another
    project's, whatever it is given."""
    from ..core.places import workspace
    # a candidate copy (a batch, a milestone) has no workspace of its own: the project's is the one above its runtime
    from ..core.project_state import FILE, of_workspace
    folder = next((p for p in (workspace(target), *Path(runtime).resolve().parents) if (p / FILE).is_file()), workspace(target))
    try: report = (of_workspace(folder) or {}).get('outputs')
    except (OSError, ValueError): report = None
    return [Path(os.path.realpath(path)) for path in (folder, report, runtime) if path]


def _within(path, folders):
    return any(path == folder or folder in path.parents for folder in folders)


def mounts(masks, keeps):
    """The launcher's mounts: each of `masks` hidden, then each (path, read_only) of `keeps` shown again at its own name
    and at its real one, outermost first, so a path shown inside a hidden folder stays shown. A kept path is shown when
    a mask hides it, a read-only one always (to make it read-only); never one that holds a mask, which it would show."""
    planned = [(mask, 'hide') for mask in masks] + [row for path, read_only in keeps for row in _shown(path, read_only, masks)]
    planned.sort(key=lambda row: len(row[0].parts))
    return [[kind, str(target), *rest] for target, kind, *rest in planned]


def _shown(path, read_only, masks):
    """The mounts that show one kept path again, at its own name and at its real one: none when it does not exist or
    holds a mask."""
    real = Path(os.path.realpath(path))
    if not real.exists() or any(_within(mask, [real]) for mask in masks): return []
    return [(target, 'show', str(real), read_only) for target in dict.fromkeys((Path(os.path.abspath(path)), real))
            if read_only or any(mask in target.parents for mask in masks)]


def named(argv, env):
    """(path, read_only) of each absolute path a command is given, in its arguments (`--x=/path` too) and its values (a
    file still to be written: its folder). The folders of PATH are given read-only. Only those inside the run's own
    workspace and report are shown again (_own): naming another project's path shows nothing."""
    found = []
    for name, text in [('', part) for part in argv] + list(env.items()):
        for piece in re.split(f'[={os.pathsep}]', str(text)):
            path = Path(piece) if piece.startswith('/') else None
            if path and not path.exists(): path = path.parent
            if path and path != Path('/') and path.exists(): found.append((str(path), name == 'PATH'))
    return found
