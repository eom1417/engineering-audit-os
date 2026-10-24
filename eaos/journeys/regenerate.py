"""The files a project's build generates and keeps in git, rebuilt from a batch's own source before its checks.

A project may commit what its build makes (EAOS ships its built Studio in eaos/data/studio, and a test checks it is
built from today's source). A batch that changes that source then fails the project's checks together, though every
change is right, and the assistant cannot run the build from its edits (EAOS on itself, 2026-10-13: four sound Studio
fixes were about to be left out for it). So when the batch's changes touch the app the run profile builds, its
build runs in a sandbox copy of the batch, and every file it changed that git keeps comes back as one commit on top.
A build that fails changes nothing here: the project's own checks then say why.
"""
import subprocess
from pathlib import Path

from .execute import git
from ..live.run import LiveRun, load_profile
from ..live.sandbox import AuthorizationError

CARD = {'id': 'REGENERATED', 'title': 'the files the build generates, rebuilt from the batch\'s own source'}


def regenerate(root, runtime, base, number):
    """The commit of the rebuilt files on top of the batch in `root`, or None when nothing had to be rebuilt."""
    from .waves import commit
    try:
        profile = load_profile(runtime)
        build = (profile.get('baseline') or {}).get('build') or profile.get('build')
        if not build or not git(root, 'diff', '--name-only', f'{base}..HEAD', '--', profile.get('app') or '.').stdout.strip(): return None
        live = LiveRun(root, runtime, 'S09', mode='baseline')
    except AuthorizationError: return None                  # the app may not run here: nothing to build it with
    try:
        live.setup()
        changed = _bring_back(Path(root), live.sandbox.copy)
    except RuntimeError:                                    # the build failed: the project's own checks say why
        return None
    finally:
        live.stop()
        live.record(f'runtime/regenerate-wave-{number}-log.json')
    if not changed: return None
    try: return commit(root, {**CARD, 'key': f'regenerated-{number}'}, 'eaos')
    except RuntimeError: return None


def _bring_back(root, copy):
    """Every file the build changed in `copy` that git keeps in `root`, written there; tracked files it removed,
    removed. The copy started as exactly the tracked files of `root`'s commit (eaos/live/sandbox.py committed_copy)."""
    tracked = set(git(root, 'ls-files').stdout.splitlines())
    made = [str(p.relative_to(copy)) for p in copy.rglob('*') if p.is_file() and not {'node_modules', '.git'} & set(p.relative_to(copy).parts)]
    ignored = set(subprocess.run(['git', '-C', str(root), 'check-ignore', '--stdin'], input='\n'.join(made),
                                 capture_output=True, text=True).stdout.splitlines())
    changed = [rel for rel in made if rel not in ignored and (rel not in tracked or (root / rel).read_bytes() != (copy / rel).read_bytes())]
    for rel in changed:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes((copy / rel).read_bytes())
    gone = [rel for rel in tracked - set(made) if not Path(rel).name.startswith('.env')]
    for rel in gone: (root / rel).unlink(missing_ok=True)
    return changed + gone
