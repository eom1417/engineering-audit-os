"""The isolated copy of one milestone of a build, on its own branch: `steps.py` opens it under the jobs' lock."""
import shutil
import subprocess
from pathlib import Path

from .. import guided
from .checks import _git
from ..fix.execute import set_aside
from .blueprint import folder


def _milestone_copy(state, runtime, number):
    """The isolated copy of milestone `number` on its own branch, stacked on the branch the last milestone ended on."""
    root = runtime / 'candidates' / f'BUILD-{number}'
    set_aside(root)
    root.parent.mkdir(parents=True, exist_ok=True)
    clone = subprocess.run(['git', 'clone', '-q', '--no-hardlinks', state['project'], str(root)], capture_output=True, text=True)
    if clone.returncode: raise RuntimeError(f'could not copy the project: {clone.stderr[-300:]}')
    previous = (state.get('built') or [None])[-1]
    if previous and previous.get('branch'):             # stacked: this milestone starts where the last one ended
        _git(root, 'fetch', '-q', state['project'], f"{previous['branch']}:{previous['branch']}")
        _git(root, 'checkout', '-q', previous['branch'])
    _git(root, 'checkout', '-q', '-b', f'eaos/build-{number}')
    if number == 1: _commit_blueprint(state, root)
    return root


def _commit_blueprint(state, root):
    """The target as part of the project: its policy at the top, the blueprint in docs/blueprint/."""
    where = folder(state)
    shutil.copyfile(where / 'eaos.policy.json', Path(root) / 'eaos.policy.json')
    docs = Path(root) / 'docs' / 'blueprint'
    docs.mkdir(parents=True, exist_ok=True)
    for source in [where / name for name in ('BLUEPRINT.md', 'product-spec.json', 'stack.json', 'plan.json')] + \
            [guided.report_of(state) / 'target-architecture.json']:
        if source.is_file(): shutil.copyfile(source, docs / source.name)
    _git(root, 'add', '-A')
    _git(root, '-c', 'user.name=EAOS', '-c', 'user.email=eaos@localhost', 'commit', '-q', '-m',
         'The blueprint: target structure, policy and build plan (EAOS)')
