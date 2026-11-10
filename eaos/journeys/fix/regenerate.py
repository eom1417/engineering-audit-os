"""The files a project's build generates and keeps in git, rebuilt from a batch's own source before its checks.

A project may commit what its build makes (EAOS ships its built Studio in eaos/data/studio, and a test checks it is
built from today's source). A batch that changes that source then fails the project's checks together, though every
change is right, and the assistant cannot run the build from its edits: sound fixes would be left out for it. So when
the batch's changes touch the app the run profile builds, its build runs in a sandbox copy of the batch, and every
file it changed that git keeps comes back as one commit on top. A build that fails changes nothing here: the
project's own checks then say why.
"""
import subprocess
from pathlib import Path

from .execute import git
from ...live.app.run import LiveRun, load_profile
from ...live.isolation.sandbox import AuthorizationError

CARD = {'id': 'REGENERATED', 'title': "Rebuild the files the build generates from the batch's source"}


def regenerate(root, runtime, base, number):
    """The commit of the rebuilt files on top of the batch in `root`, or None when nothing had to be rebuilt."""
    from .waves import commit
    try:
        profile = load_profile(runtime)
        build = (profile.get('baseline') or {}).get('build') or profile.get('build')
        if not build or not git(root, 'diff', '--name-only', f'{base}..HEAD', '--',
                                profile.get('app') or '.').stdout.strip(): return None
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
    try: return commit(root, {**CARD, 'key': f'regenerated-{number}'})
    except RuntimeError: return None


def keep_guide(root, report, project, number, base):
    """The project's extension guide brought up to date as one commit on top of the batch, from the check's own read,
    only when the project held one at `base` and the batch moved or removed a path it names; else None. A fix batch
    never writes a guide or a context file the project did not have: a guide is made by the context batch, on a branch
    of its own, so a fix branch never carries files the person never asked for. A batch never fails for its guide."""
    from .waves import commit
    from ...analysis.repair import project_guide
    path = project_guide.existing(root, base)
    if not path or not _moved_named(root, base, path): return None
    drawn = project_guide.drawn_from_report(root, report, project)
    if not drawn or not project_guide.refresh(root, path, drawn, Path(project).name): return None
    try: return commit(root, {'id': 'EXTENDING', 'title': 'Update the extension guide for the moved files',
                              'key': f'extending-{number}'})
    except RuntimeError: return None


def _moved_named(root, base, path):
    """Whether the batch moved or removed, since `base`, a file the guide at `path` names."""
    rows = [line.split('\t') for line in git(root, 'diff', '--name-status', '-M', f'{base}..HEAD').stdout.splitlines()]
    gone = [row[1] for row in rows if len(row) > 1 and row[0][:1] in 'DR']
    guide = git(root, 'show', f'{base}:{path}').stdout
    return any(f'`{old}`' in guide for old in gone)


def _bring_back(root, copy):
    """Every file the build changed in `copy` that git keeps in `root`, written there; tracked files it removed,
    removed. The copy started as exactly the tracked files of `root`'s commit (eaos/live/isolation/sandbox.py
    committed_copy)."""
    tracked = set(git(root, 'ls-files').stdout.splitlines())
    made = _files(copy)
    ignored = set(subprocess.run(['git', '-C', str(root), 'check-ignore', '--stdin'], input='\n'.join(made),
                                 capture_output=True, text=True).stdout.splitlines())
    changed = [rel for rel in made if rel not in ignored
               and (rel not in tracked or (root / rel).read_bytes() != (copy / rel).read_bytes())]
    for rel in changed:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes((copy / rel).read_bytes())
    gone = [rel for rel in tracked - set(made) if not Path(rel).name.startswith('.env')]
    for rel in gone: (root / rel).unlink(missing_ok=True)
    return changed + gone


def _files(copy):
    """Every file of `copy`, relative to it, outside node_modules and .git."""
    return [str(p.relative_to(copy)) for p in copy.rglob('*')
            if p.is_file() and not {'node_modules', '.git'} & set(p.relative_to(copy).parts)]
