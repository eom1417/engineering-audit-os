"""What every adapter of an installed command-line tool shares: its pin, its version, and the two ways it
can decline to run (not installed; nothing in this project for it to read).

The pin lives in upstreams/toolchain.json and nowhere else; `eaos tools install` puts the binary where
eaos.engines.process.which looks first.
"""
import re

from .contract import NOT_APPLICABLE, UNAVAILABLE, Report
from .process import run, which

VERSION = re.compile(r'(\d+\.\d+\.\d+)')


def pinned(name):
    from ..toolchain import registry
    return next(t['version'] for t in registry()['tools'] if t['name'] == name)


def version(binary, args=('--version',)):
    """The version the installed binary prints, or None when it is absent or prints none."""
    path = which(binary)
    if not path: return None
    code, out, error, _ = run([path, *args], timeout=120)
    found = VERSION.search(out + error)
    return found.group(1) if found else None


def declined(name, binary, target):
    """A Report when the tool cannot or need not run here, else None. Checked in that order: a tool that is
    not installed is reported as absent even where it would not apply, so an install gap is never hidden."""
    found = version(binary)
    if found is None:
        return Report(name, None, pinned(name), UNAVAILABLE,
                      reason=f'{binary} is not installed: python -m eaos tools install --only {name}')
    from ..toolchain import applies
    applicable, rule = applies(name, target)
    if not applicable:
        return Report(name, found, pinned(name), NOT_APPLICABLE,
                      reason=f'nothing here for {name} to read (it applies to: {rule})')
    return None
