"""One tool installed at its pinned version, without root: a release downloaded (carried on from what an earlier
attempt left), accepted only at its pinned sha256 and unpacked; a Python tool into the tools' virtualenv, a Node tool
into its own prefix, a repository at its pinned commit; Playwright with its browser."""
import hashlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from ..system.web import opened
from .pins import _link, browsers, checkout, home, npm_prefix, registry, release_spec, tool_env, uv, venv_of
from .versions import browser_missing, found_version

CHUNK = 2 ** 20
TAR_MODES = {'tar.gz': 'r:gz', 'tar.xz': 'r:xz'}
_PIP = threading.Lock()                 # one virtualenv for every Python tool: pip installs into it one at a time


def install_browsers(echo=print):
    """Download the browser the pinned Playwright drives (no administrator rights; the system libraries a
    Linux computer may lack are named in the error, and `playwright install-deps` needs an administrator)."""
    if not browser_missing(): return
    playwright = home() / 'bin/playwright'
    done = subprocess.run([str(playwright), 'install', 'chromium', 'chromium-headless-shell'], capture_output=True, text=True,  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- a list argv of a tool EAOS installs at its pin, no shell
                          env={**tool_env(), 'PLAYWRIGHT_BROWSERS_PATH': str(browsers())}, timeout=1800)
    if done.returncode: raise RuntimeError('the browser did not install: ' + (done.stdout + done.stderr)[-400:])
    echo(f"install chromium for playwright in {browsers()}")


def _download(url, part, step):
    """The file at `url` written to `part` (never held in memory: a CodeQL bundle is 1.2 GB), carried on from what an
    earlier attempt left there (an HTTP range), `step(done, total)` in bytes as it comes."""
    have = part.stat().st_size if part.exists() else 0
    request = urllib.request.Request(url, headers={'Range': f'bytes={have}-'} if have else {})
    try: response = opened(request, timeout=300, files=True)
    except urllib.error.HTTPError as problem:
        if problem.code == 416 and have: return                         # the earlier attempt had it all
        raise
    with response:
        if have and response.status != 206: have = 0                   # the server sends it whole
        _write(response, part, have, step)


def _write(response, part, have, step):
    done, total = have, have + int(response.headers.get('Content-Length') or 0)
    with part.open('ab' if have else 'wb') as handle:
        while chunk := response.read(CHUNK):
            handle.write(chunk)
            done += len(chunk)
            step(done, max(total, done))


def _release(tool, step=lambda done, total: None):
    spec = release_spec(tool)
    part = home() / 'downloads' / f"{tool['name']}-{tool['version']}.part"
    part.parent.mkdir(parents=True, exist_ok=True)
    _download(spec['url'], part, step)
    try:
        with part.open('rb') as blob:
            digest = hashlib.sha256()
            while chunk := blob.read(CHUNK): digest.update(chunk)
            if (digest := digest.hexdigest()) != spec['sha256']:
                raise RuntimeError(f"{tool['name']}: sha256 {digest} does not match the pinned {spec['sha256']}; nothing installed")
            blob.seek(0)
            _unpack(tool, spec, blob)
    finally:
        part.unlink(missing_ok=True)


def _unpack(tool, spec, blob):
    """The checked archive (an open file) unpacked into the tool's release folder, its binary linked; the older version goes."""
    folder = home() / 'releases' / f"{tool['name']}-{tool['version']}"
    folder.mkdir(parents=True, exist_ok=True)
    if spec.get('tree'): target = _tree(tool, spec, blob, folder)
    else: (target := folder / tool['binary']).write_bytes(blob.read() if spec['archive'] == 'binary' else _member(tool, spec, blob))
    target.chmod(0o755)
    before = (home() / 'bin' / tool['binary']).resolve()           # the version linked until now (CodeQL's is 1.4 GB)
    _link(target, tool['binary'])
    if folder.parent in before.parents and folder not in before.parents: shutil.rmtree(folder.parent / before.relative_to(folder.parent).parts[0])


def _tree(tool, spec, blob, folder):
    """A whole directory (a JRE, a CLI with its jars) extracted into `folder` with no path escaping it; its entry."""
    if spec['archive'] == 'zip':
        with zipfile.ZipFile(blob) as archive:
            unsafe = next((name for name in archive.namelist() if name.startswith('/') or '..' in Path(name).parts), None)
            if unsafe: raise RuntimeError(f"{tool['name']}: unsafe path {unsafe!r} in the archive; nothing installed")
            archive.extractall(folder)  # nosec B202: every name was checked just above
    else:
        with tarfile.open(fileobj=blob, mode=TAR_MODES[spec['archive']]) as archive:
            archive.extractall(folder, filter='data')  # nosec B202: the 'data' filter refuses any path leaving the folder
    target = folder / spec['entry']
    if not target.is_file(): raise RuntimeError(f"{tool['name']}: {spec['entry']} is not in the archive")
    return target


def _member(tool, spec, blob):
    """The tool's file inside a tar or zip archive (an open file): the path the pin names, compared by its last part,
    so `./reforge`, `k6-v2.3.0-macos-arm64/k6` and `reforge` all find the same file."""
    wanted = spec['member'].rsplit('/', 1)[-1]
    if spec['archive'] == 'zip':
        with zipfile.ZipFile(blob) as archive:
            name = next((n for n in archive.namelist() if not n.endswith('/') and n.rsplit('/', 1)[-1] == wanted), None)
            if name is None: raise RuntimeError(f"{tool['name']}: {spec['member']} is not in the archive")
            return archive.read(name)
    with tarfile.open(fileobj=blob, mode=TAR_MODES[spec['archive']]) as archive:
        member = next((m for m in archive.getmembers() if m.isfile() and m.name.rsplit('/', 1)[-1] == wanted), None)
        if member is None: raise RuntimeError(f"{tool['name']}: {spec['member']} is not in the archive")
        return archive.extractfile(member).read()


def _pip(tool):
    """A Python tool in its own environment under the tools home. With uv when there is one: the environments
    the installer makes have no pip, and some Pythons have no ensurepip to make one."""
    with _PIP: _pip_one(tool)


def _pip_one(tool):
    venv, env = venv_of(tool), tool_env()   # no download cache: a tool installs once, and the caches kept each one
    wanted = [f"{tool['install']['package']}=={tool['version']}", *tool['install'].get('with', [])]
    runner = uv()
    if not (venv / 'bin/python').exists():
        if runner: subprocess.run([runner, 'venv', '--quiet', '--no-cache', '--python', sys.executable, str(venv)], check=True, env=env)  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- uv at its pin making the tools venv, a list argv, no shell
        else: subprocess.run([sys.executable, '-m', 'venv', str(venv)], check=True, env=env)  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- this Python making the tools venv, a list argv, no shell
    if runner and not (venv / 'bin/pip').exists():
        subprocess.run([runner, 'pip', 'install', '--quiet', '--no-cache', '--python', str(venv / 'bin/python'), *wanted], check=True, env=env)  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- the pinned requirements of the registry, a list argv, no shell
    else:
        subprocess.run([str(venv / 'bin/pip'), 'install', '-q', '--no-cache-dir', *wanted], check=True, env=env)  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- the pinned requirements of the registry, a list argv, no shell
    if tool['install'].get('library'): return       # a library EAOS's own script imports (Presidio): no command to link
    _link(venv / 'bin' / tool['binary'], tool['binary'])


def _npm(tool):
    (prefix := npm_prefix(tool)).mkdir(parents=True, exist_ok=True)
    npm = shutil.which('npm')
    if not npm: raise RuntimeError(f"{tool['name']}: npm is not installed; install Node.js 18 or newer, then run this again")
    env = {**tool_env(), **tool['install'].get('env', {})}
    with tempfile.TemporaryDirectory(prefix='eaos-npm-cache-') as cache:   # npm's own kept 1.5 GB of the tools
        subprocess.run([npm, 'install', '--prefix', str(prefix), '--cache', cache, '--no-audit', '--no-fund', '--loglevel=error',  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- npm installing the registry's pinned packages, a list argv, no shell
                        f"{tool['install']['package']}@{tool['version']}", *tool['install'].get('with', [])], check=True, env=env)
    if tool['install'].get('library'): return
    _link(prefix / 'node_modules/.bin' / tool['binary'], tool['binary'])


def _git(tool):
    """Fetch exactly the pinned commit of a repository into its own directory under the tools home."""
    folder, spec = checkout(tool), tool['install']
    folder.mkdir(parents=True, exist_ok=True)
    for argv in (['init', '-q'], ['remote', 'remove', 'origin'], ['remote', 'add', 'origin', spec['repository']],
                 ['fetch', '-q', '--depth', '1', 'origin', tool['version']], ['checkout', '-q', '--force', 'FETCH_HEAD']):
        done = subprocess.run(['git', '-C', str(folder), *argv], capture_output=True, text=True)
        if done.returncode and argv[:2] != ['remote', 'remove']:
            raise RuntimeError(f"{tool['name']}: git {' '.join(argv)} failed: {done.stderr.strip()[-200:]}")


def _ensure(tool, step, echo):
    """The tool at its pinned version, installed when it is not; with Playwright its browser."""
    found, _ = found_version(tool)
    if found == tool['version']:
        echo(f"ok      {tool['name']} {found}")
    else:
        if tool.get('license_note'): echo(f"note    {tool['name']}: {tool['license_note']}")
        method = tool['install']['method']
        if method == 'release': _release(tool, lambda done, total: step('download', done, total, kind='count'))
        else: {'pip': _pip, 'npm': _npm, 'git': _git}[method](tool)
        found, reason = found_version(tool)
        if found != tool['version']: raise RuntimeError(reason or f'installed {found}, pinned {tool["version"]}')
        echo(f"install {tool['name']} {found}")
    if tool['name'] == 'playwright': install_browsers(echo)


# The caches of tools no longer pinned (Trivy's, retired in M18.1), removed with the tools themselves.
RETIRED_CACHES = ('cache/trivy', 'cache/trivy-next')


def retire():
    """Remove from the tools home what no pinned tool owns: a release, an npm prefix or an own virtualenv of a tool the
    registry no longer lists, the caches of retired tools and the links left pointing at nothing. What EAOS installed,
    EAOS removes when it stops using it. Returns what was removed, relative to the tools home."""
    base = home()
    gone = _unowned(base, {t['name'] for t in registry()['tools']})
    for folder in gone: shutil.rmtree(folder, ignore_errors=True)
    links = [link for link in (base / 'bin').glob('*') if link.is_symlink() and not link.exists()]
    for link in links: link.unlink()
    return sorted(str(path.relative_to(base)) for path in gone + links)


def _unowned(base, names):
    """The folders of the tools home that belong to no tool in `names`."""
    releases = [f for f in (base / 'releases').glob('*') if not _owned(f.name, names)]
    prefixes = [f for f in (base / 'npm').glob('*') if f.name not in names]
    venvs = [f for f in base.glob('venv-*') if f.name.removeprefix('venv-') not in names]
    return releases + prefixes + venvs + [base / c for c in RETIRED_CACHES if (base / c).exists()]


def _owned(release, names):
    """Whether a release folder (`<name>-<version>`) is one of `names`."""
    return any(release == name or release.startswith(f'{name}-') for name in names)
