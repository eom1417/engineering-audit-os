"""What every adapter of an installed command-line tool shares: its pin, its version, and the two ways it
can decline to run (not installed; nothing in this project for it to read).

The pin lives in upstreams/toolchain.json and nowhere else; `eaos tools install` puts the binary where
eaos.engines.process.which looks first.
"""
import re
from pathlib import Path

from .contract import NOT_APPLICABLE, UNAVAILABLE, Report
from .process import run, which

VERSION = re.compile(r'(\d+\.\d+\.\d+)')


def pinned(name):
    from ..toolchain import registry
    return next(t['version'] for t in registry()['tools'] if t['name'] == name)


def version(binary, args=('--version',), pattern=VERSION):
    """The version the installed binary prints, or None when it is absent or prints none.

    A tool numbered in two parts (vulture 2.16) passes its own pattern."""
    path = which(binary)
    if not path: return None
    code, out, error, _ = run([path, *args], timeout=120)
    found = re.search(pattern, out + error)
    return found.group(1) if found else None


def package_version(name, binary):
    """The version of an npm tool that has no --version (the react-docgen CLI): the one its pinned package
    records, when its command is installed; else None."""
    if not which(binary): return None
    from .. import toolchain
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


def fnmatch_literal(text):
    """`text` as an fnmatch pattern that matches only itself (a target path holding `[` or `*`)."""
    return re.sub(r'([\[\]*?])', r'[\1]', text)


def declined(name, binary, target, probe=None):
    """A Report when the tool cannot or need not run here, else None. Checked in that order: a tool that is
    not installed is reported as absent even where it would not apply, so an install gap is never hidden.
    `probe` is the adapter's own version reader, for a tool whose version `version(binary)` cannot read."""
    found = probe() if probe else version(binary)
    if found is None:
        return Report(name, None, pinned(name), UNAVAILABLE,
                      reason=f'{binary} is not installed: python -m eaos tools install --only {name}')
    from ..toolchain import applies
    applicable, rule = applies(name, target)
    if not applicable:
        return Report(name, found, pinned(name), NOT_APPLICABLE,
                      reason=f'nothing here for {name} to read (it applies to: {rule})')
    return None
