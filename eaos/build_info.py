"""Which EAOS this is: its version, the commit it was installed from, and a fingerprint of its own code.

Every page EAOS makes for a person says which EAOS made it and when, so that an old page is never taken for a new
one: after an update, a page whose fingerprint is not this EAOS's is rebuilt (eaos/guided.publish).
"""
import hashlib
import json
import subprocess
from functools import lru_cache
from pathlib import Path

from . import __version__

HERE = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def digest():
    """This EAOS's own code, as a fingerprint: a report made by an older EAOS is checked again, not reused."""
    code = hashlib.sha256()
    for path in sorted(HERE.rglob('*.py')):
        if '__pycache__' not in path.parts: code.update(path.read_bytes())
    return code.hexdigest()[:16]


@lru_cache(maxsize=1)
def studio_digest():
    """The Studio's built assets and its data contract, as a fingerprint of their own: a change to the interface alone
    rebuilds the Studio without forcing a new check, which digest() would (NS36)."""
    code = hashlib.sha256()
    for path in sorted([*(HERE / 'data/studio').rglob('*'), *(HERE / 'data/schemas/artifacts').glob('studio-*.schema.json')]):
        if path.is_file():
            code.update(path.relative_to(HERE).as_posix().encode('utf-8') + b'\0')
            code.update(path.read_bytes())
    return code.hexdigest()[:16]


@lru_cache(maxsize=1)
def commit():
    """The commit EAOS was installed from (pip's record of a git install), else the commit of the checkout it runs
    from; '' when neither says."""
    try:
        from importlib.metadata import distribution
        url = json.loads(distribution('engineering-audit-os').read_text('direct_url.json') or '{}')
        if (url.get('vcs_info') or {}).get('commit_id'): return url['vcs_info']['commit_id'][:12]
    except Exception:                       # not installed as a package, or installed without a record: the checkout
        pass
    done = subprocess.run(['git', '-C', str(HERE), 'rev-parse', '--short=12', 'HEAD'], capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else ''


def stamp(built):
    return {'version': __version__, 'commit': commit(), 'digest': digest(), 'built': built}
