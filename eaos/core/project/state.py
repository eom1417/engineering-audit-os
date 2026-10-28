"""A project's state, the one record of it: ~/.eaos/projects/<name>-<id>/state.json (or under $EAOS_HOME). The CLI, MCP,
the Studio and every stage read and write it here and nowhere else (M3.2): what was chosen and asked, the check on
record, the batches, each branch's part (eaos/core/project/branches.py KEYS).

The journeys save it through eaos/journeys/guided/ save, which first tidies the batches (eaos/journeys/fix/waves.saved).
"""
import json
import os
from pathlib import Path

from .branches import suffix
from .places import home, workspace
from ...core.system.files import read_json
from ...core.system.clock import now

FILE = 'state.json'
# A folder with one of these is a project; the person's home and a drive's root never are.
PROJECT_MARKERS = ('.git', 'package.json', 'pyproject.toml', 'requirements.txt', 'go.mod', 'Cargo.toml', 'composer.json',
                   'Gemfile', 'pom.xml', 'build.gradle', 'deno.json', 'index.html')


def load(project):
    """The state of the project in `project`, or None before its first start."""
    return of_workspace(workspace(project))


def of_workspace(folder):
    """The state kept in an EAOS workspace folder, or None (none there, or one that does not read)."""
    return read_json(Path(folder) / FILE)


def write(state):
    """The state written whole, stamped: an assistant beside it never reads half of it."""
    (where := Path(state['workspace'])).mkdir(parents=True, exist_ok=True)
    state['updated'] = now()
    (new := where / f'.state-{os.urandom(4).hex()}.json').write_text(json.dumps(state, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    new.replace(where / FILE)


def every():
    """Every project's state on this computer that reads, in the order of their folders."""
    out = []
    for record in sorted((home() / 'projects').glob(f'*/{FILE}')):
        out.append(read_json(record))
    return [row for row in out if row is not None]


def looks_like_project(folder):
    folder = Path(folder).resolve()
    if folder in (Path.home().resolve(), Path(folder.anchor)): return False
    return any((folder / marker).exists() for marker in PROJECT_MARKERS)


def current(project='.'):
    """The state of the project in this folder, or of the nearest folder above it that was started."""
    here = Path(project).resolve()
    for folder in (here, *here.parents):
        state = load(folder)
        # A record left by an older EAOS that scanned the home folder is never a project to go on with.
        if state and looks_like_project(folder): return state
    raise LookupError('no EAOS project here: run eaos start first')


def runtime_of(state):
    """The run's working folder of the branch EAOS works on, beside its state."""
    return Path(state['workspace']) / ('runtime' + suffix(state))


def waiting_batch(state):
    """The last batch handed over and waiting for the person's decision (accept or undo), or None."""
    return next((w for w in reversed(state.get('waves') or []) if w.get('status') == 'applied'), None)
