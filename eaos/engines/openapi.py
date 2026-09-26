"""Where a project keeps its OpenAPI or Swagger specification, and the version of it before the last change."""
import subprocess
from pathlib import Path

SKIPPED = {'node_modules', '.git', 'dist', 'build', 'vendor', '.venv', 'venv'}
SUFFIXES = ('.yaml', '.yml', '.json')


def specifications(target, exclude=()):
    root, found = Path(target), []
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if set(relative.parts) & (SKIPPED | set(exclude)) or not path.is_file(): continue
        if path.name.startswith(('openapi.', 'swagger.')) and path.suffix in SUFFIXES: found.append(relative.as_posix())
    return found


def previous(target, spec):
    """(commit, text) of the spec as it was before the last commit that changed it; (None, None) if none."""
    log = subprocess.run(['git', '-C', str(target), 'log', '-n', '2', '--format=%H', '--', spec], capture_output=True, text=True)
    commits = log.stdout.split() if log.returncode == 0 else []
    if len(commits) < 2: return None, None
    shown = subprocess.run(['git', '-C', str(target), 'show', f'{commits[1]}:{spec}'], capture_output=True, text=True)
    return (commits[1], shown.stdout) if shown.returncode == 0 else (None, None)
