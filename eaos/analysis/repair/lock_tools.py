"""The upgrades a lock file's own tool makes module by module (eaos/analysis/repair/codemods.py runs them on a copy):
Go's `go get` then `go mod tidy`, Cargo's `cargo update --precise`. Each fetches into a cache of its own, removed after,
and writes the manifest and the lock alone."""
import os
import subprocess
import tempfile
from pathlib import Path


def _go_steps(members, executable, copy):
    """Each module moved to its fixed version by its own `go get`, unless an earlier one already moved it past (a fixed
    x/net needs a newer x/sys: asking x/sys at its own fix in the same go get is refused), then `go mod tidy`: go.mod
    and go.sum alone are written, the modules fetched into a cache of its own, removed after; Go never downloads
    another toolchain."""
    folder, wanted = Path(copy) / members[0]['folder'], [(m['package'], 'v' + str(m['fixed']).removeprefix('v')) for m in members]
    return [(lambda: _go(executable, folder, wanted), f"go get {' '.join(f'{p}@{v}' for p, v in wanted)} && go mod tidy")]


def _go(executable, folder, wanted):
    with tempfile.TemporaryDirectory(prefix='eaos-go-') as cache:
        env = {**os.environ, 'GOMODCACHE': cache, 'GOFLAGS': '-modcacherw', 'GOTOOLCHAIN': 'local'}
        run = lambda *argv: _run([executable, *argv], folder, env)
        for module, fixed in wanted:
            if _semver(run('list', '-m', '-f', '{{.Version}}', module).strip()) < _semver(fixed): run('get', f'{module}@{fixed}')
        run('mod', 'tidy')


def _run(argv, folder, env):
    done = subprocess.run(argv, cwd=folder, capture_output=True, text=True, timeout=600, env=env)  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- go or cargo at its path, a list argv built here, in an isolated copy, no shell
    if done.returncode: raise OSError(f"{Path(argv[0]).name} {argv[1]} exited {done.returncode}: {(done.stderr or done.stdout).strip()[-240:]}")
    return done.stdout


def _semver(version):
    """A Go module version, comparable: v1.2.3 above its pre-releases and pseudo-versions (v1.2.4-0.2026... is below
    v1.2.4)."""
    base, _, pre = version.removeprefix('v').partition('-')
    return (*(int(part) if part.isdigit() else 0 for part in (base.split('.') + ['0', '0'])[:3]), not pre)


def _cargo_steps(members, executable, copy):
    """Each crate moved to its fixed version by `cargo update -p <name>@<version> --precise <fixed>`: Cargo.lock alone
    is written, nothing built."""
    folder = Path(copy) / members[0]['folder']
    wanted = [(f"{m['package']}@{m['version']}", str(m['fixed']).removeprefix('v')) for m in members]
    return [(lambda: _cargo(executable, folder, wanted), ' && '.join(f'cargo update -p {p} --precise {v}' for p, v in wanted))]


def _cargo(executable, folder, wanted):
    with tempfile.TemporaryDirectory(prefix='eaos-cargo-') as cache:
        env = {**os.environ, 'CARGO_HOME': cache}
        for crate, fixed in wanted: _run([executable, 'update', '-p', crate, '--precise', fixed], folder, env)


LOCK_TOOLS = {'go': _go_steps, 'cargo': _cargo_steps}
