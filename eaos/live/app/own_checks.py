"""The checks a project with no interface is kept safe by, from its own manifest: a Rust crate's tests (`cargo test`,
its build with them), a Go module's (`go vet`, `go test`), a PHP library's PHPUnit, a Python project's own tests in
the run's environment. Each fetches what it needs at install, with the network; Rust and Go run their checks from the lock alone (`--locked`,
`--offline`): a stranger's Rust command-line tool could not be fixed at all (2026-11-04)."""
import json
from pathlib import Path

BY_MANIFEST = (
    ('Cargo.toml', [['cargo', 'fetch', '--locked']], [['cargo', 'test', '--locked', '--offline']]),
    ('go.mod', [['go', 'mod', 'download']], [['go', 'vet', './...'], ['go', 'test', './...']]),
)


def found(project):
    """(install commands, checks) of the first manifest at the project's root; ([['true']], []) without one."""
    root = Path(project)
    return next(((install, checks) for name, install, checks in BY_MANIFEST if (root / name).is_file()), None) or _php(root) or _python(root)


def _php(root):
    """A PHP library's Composer install and its PHPUnit suite; None without one."""
    from . import detect_php
    checks = detect_php.checks(root)
    return (detect_php.install(root), checks) if checks else None


def _python(root):
    """A Python project's install and its own tests, run by the run's own environment where that install put pytest
    (EAOS's interpreter has neither the project's packages nor pytest)."""
    from .python_install import MANIFESTS, install
    from ..testing.python_suite import command
    tests = command(root) if any((root / name).is_file() for name in MANIFESTS) else None
    return (install(root), [['python', *tests[1:]]]) if tests else ([['true']], [])


def refreshed(runtime, project):
    """True when the run profile of a project with no interface had no checks and now has those of its manifest (and
    their installs): a profile an older EAOS drafted keeps the checks it knew, and a library updated EAOS on was still
    found unprotected (2026-11-05)."""
    path = Path(runtime) / 'run.json'
    profile = json.loads(path.read_text(encoding='utf-8'))
    install, checks = found(project)
    if profile.get('checks') or not checks: return False
    kept = [step for step in profile.get('install') or [] if step != ['true']]
    profile.update(install=kept + [step for step in install if step not in kept], checks=checks)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return True


def unknown_app(project=None):
    """An app EAOS does not know how to start by itself (no JavaScript or Python web app, no static site): a draft starting nothing
    (no earlier app's profile kept) with its own manifest's checks (eaos/live/app/own_checks.py, its safety when it has no interface);
    the assistant works out how to start it from the project's own documentation (_attempts), safe() judging every command."""
    from ...core.system.local_db import free_port
    install, checks = found(project) if project else ([['true']], [])
    profile = {'schema_version': 1, 'app': '.', 'install': install, 'start': ['true'], 'port': free_port(), 'health': '/',
               'start_timeout': 180, 'env': {}, 'checks': checks}
    return {'profile': profile, 'facts': {'folder': '.', 'manager': None, 'framework': None, 'database': None, 'env_names': [],
                                          'reason': 'no package.json with a dev or start script: the assistant works out how to start it'},
            'limitations': []}
