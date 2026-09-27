"""What the handover kit needs to know about the project: its stack, how it installs and tests, and its target.

Read from the project's own files (read only, nothing runs) and from the report's records. When the project
directory is not reachable, every flag is False and the kit says less rather than guessing.
"""
import json
import re
from pathlib import Path

from ..toolchain import project_files, registry

LOCKS = (('bun.lock', 'bun'), ('bun.lockb', 'bun'), ('pnpm-lock.yaml', 'pnpm'), ('yarn.lock', 'yarn'), ('package-lock.json', 'npm'))


def _load(path, default):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


def profile(report):
    report = Path(report)
    dossier = _load(report / 'dossier.json', {})
    target = (dossier.get('provenance') or {}).get('target')
    root = Path(target) if target and Path(target).is_dir() else None
    files = project_files(root) if root else []
    top = set(files)
    package = _load(root / 'package.json', {}) if root else {}
    scripts = package.get('scripts') or {}
    js = any(f.endswith(('.ts', '.tsx', '.js', '.jsx')) for f in files)
    python = any(f.endswith('.py') for f in files)
    manager = next((tool for lock, tool in LOCKS if lock in top), 'npm') if package else None
    return {
        'name': root.name if root else report.name,
        'root': root, 'files': files, 'js': js and bool(package), 'python': python and not package,
        'package_manager': manager, 'scripts': scripts,
        'lockfile': next((lock for lock, _ in LOCKS if lock in top), None),
        'tsconfig': 'tsconfig.json' in top,
        'pyproject': 'pyproject.toml' in top, 'requirements': 'requirements.txt' in top,
        'pytest': 'pytest.ini' in top or any(f.startswith('tests/') and f.endswith('.py') for f in files),
        'openapi': sorted(f for f in files if f.split('/')[-1].startswith(('openapi.', 'swagger.'))),
        'ci_or_iac': any(f.startswith('.github/workflows/') or f.endswith(('Dockerfile', '.tf')) for f in files),
        'sql': any(f.endswith('.sql') for f in files),
        'target': _load(report / 'target-architecture.json', {}),
        'intake': _load(report / 'intake.json', {}),
        'features': (_load(report / 'features.json', {}) or {}).get('features') or [],
    }


def pin(name):
    """The toolchain entry of a tool, so the kit uses exactly the versions EAOS itself was measured with."""
    return next(tool for tool in registry()['tools'] if tool['name'] == name)


def reference(report_profile):
    from ..reference_architecture import by_id, rooted
    target = report_profile['target'] or {}
    return rooted(by_id(target['reference']), target.get('root') or '') if target.get('reference') else None


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', str(text).lower()).strip('-') or 'service'
