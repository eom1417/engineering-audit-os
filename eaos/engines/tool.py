"""What every adapter of an installed command-line tool shares: its pin, its version, and the two ways it
can decline to run (not installed; nothing in this project for it to read).

The pin lives in eaos/data/toolchain.json and nowhere else; `eaos tools install` puts the binary where
eaos.engines.process.which looks first.
"""
import functools
import re
import shutil
from pathlib import Path

from .contract import ERROR, NOT_APPLICABLE, UNAVAILABLE, Report
from .process import run, which

VERSION = re.compile(r'(\d+\.\d+\.\d+)')
SLOW = (120, 600)                 # seconds a version check may take: then again, on a loaded host


def pinned(name):
    from ..core.toolchain import registry
    return next(t['version'] for t in registry()['tools'] if t['name'] == name)


def version(binary, args=('--version',)):
    """The version the installed binary prints, or None when it is absent or prints none. A binary that is there but
    does not answer in time (on a busy machine 120 s were not enough) is asked again with longer, then counted
    as installed, its version 'unknown': never taken for a tool that is not installed."""
    path = which(binary)
    if not path: return None
    for limit in SLOW:
        code, out, error, _ = run([path, *args], timeout=limit)
        found = VERSION.search(out + error)
        if found: return found.group(1)
        if not (code == 127 and 'timed out' in error): return None
    return 'unknown'


def package_version(name, binary):
    """The version of an npm tool that has no --version (the react-docgen CLI): the one its pinned package
    records, when its command is installed; else None."""
    if not which(binary): return None
    from ..core import toolchain
    record = next(t for t in toolchain.registry()['tools'] if t['name'] == name)
    return toolchain.package_version(record)


def relative(path, root=None):
    """A path a tool printed (`./src/a.ts`, or absolute under `root`) in its project-relative form.
    An absolute path outside `root` is kept as printed rather than mangled into a wrong relative one."""
    if root is not None and Path(path).is_absolute():
        try: path = Path(path).resolve().relative_to(Path(root).resolve())
        except ValueError: return str(path)
    path = str(path).replace('\\', '/')
    while path.startswith('./'): path = path[2:]
    return path


def excluded(path, patterns):
    """Whether a project-relative path lies under an excluded entry. An entry is a directory name (`dist`) or a
    relative path (`components/ui`) and matches at any depth, as in eaos/facts/source.py: `src/components/ui/x.tsx`
    is under `components/ui`."""
    return any(f'/{pattern.strip("/")}/' in f'/{path}/' for pattern in patterns if pattern.strip('/'))


def declined(name, binary, target, probe=None):
    """A Report when the tool cannot or need not run here, else None (`started`)."""
    return started(name, binary, target, probe)[0]


def started(name, binary, target, probe=None):
    """(a Report when the tool cannot or need not run here, else None; the version found), the version read once.
    Checked in that order: a tool that is not installed is reported as absent even where it would not apply, so an
    install gap is never hidden. `probe` is the adapter's own version reader, for a tool whose version
    `version(binary)` cannot read."""
    found = probe() if probe else version(binary)
    if found is None:
        return Report(name, None, pinned(name), UNAVAILABLE,
                      reason=f'{binary} is not installed: python -m eaos tools install --only {name}'), None
    from ..core.toolchain import applies
    applicable, rule = applies(name, target)
    if not applicable:
        return Report(name, found, pinned(name), NOT_APPLICABLE,
                      reason=f'nothing here for {name} to read (it applies to: {rule})'), found
    return None, found


def engine(name, binary, fresh=False):
    """An adapter's analyze(target, workdir, exclude=(), formats=None), from its body(target, folder, exclude, formats,
    version found): declined here when the tool cannot or need not run (`started`), else the body run in the engine's
    own folder of the run's work folder (`folder`, emptied first when `fresh`)."""
    def adapter(body):
        @functools.wraps(body)
        def analyze(target, workdir, exclude=(), formats=None):
            declined, found = started(name, binary, target)
            return declined or body(target, folder(workdir, name, fresh), exclude, formats, found)
        return analyze
    return adapter


def folder(workdir, name, fresh=False):
    """The engine's own folder in the run's work folder, emptied first when `fresh`."""
    out = Path(workdir) / name
    if fresh and out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    return out


def failed(name, found, seconds, code, error):
    """The Report of a run that ended in error: the tool's last words, or its exit code."""
    return Report(name, found, pinned(name), ERROR, seconds=seconds, reason=error.strip()[-300:] or f'exit {code}')
