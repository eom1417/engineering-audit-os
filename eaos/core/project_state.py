"""A project's state, the one record of it: ~/.eaos/projects/<name>-<id>/state.json (or under $EAOS_HOME). The CLI, MCP,
the Studio and every stage read and write it here and nowhere else (M3.2): what was chosen and asked, the check on
record, the batches, each branch's part (eaos/core/branches.py KEYS).

The journeys save it through eaos/journeys/guided.py save, which first tidies the batches (eaos/journeys/waves.saved).
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .branches import suffix
from .places import home, workspace

FILE = 'state.json'
# A folder with one of these is a project; the person's home and a drive's root never are.
PROJECT_MARKERS = ('.git', 'package.json', 'pyproject.toml', 'requirements.txt', 'go.mod', 'Cargo.toml', 'composer.json',
                   'Gemfile', 'pom.xml', 'build.gradle', 'deno.json', 'index.html')


def load(project):
    """The state of the project in `project`, or None before its first start."""
    return of_workspace(workspace(project))


def of_workspace(folder):
    """The state kept in an EAOS workspace folder, or None (none there, or one that does not read)."""
    try: return json.loads((Path(folder) / FILE).read_text(encoding='utf-8'))
    except FileNotFoundError: return None


def write(state):
    """The state written whole, stamped: an assistant beside it never reads half of it."""
    (where := Path(state['workspace'])).mkdir(parents=True, exist_ok=True)
    state['updated'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    (new := where / f'.state-{os.urandom(4).hex()}.json').write_text(json.dumps(state, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    new.replace(where / FILE)


def every():
    """Every project's state on this computer that reads, in the order of their folders."""
    out = []
    for record in sorted((home() / 'projects').glob(f'*/{FILE}')):
        try: out.append(json.loads(record.read_text(encoding='utf-8')))
        except (OSError, ValueError): continue
    return out


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
