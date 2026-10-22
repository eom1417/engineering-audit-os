"""Every external tool at its pinned version, installed without root, and checked by one command.

upstreams/toolchain.json is the only list. `install` puts each tool under $EAOS_ENGINE_TOOLS (default
~/.eaos/tools): a release is downloaded and accepted only if its sha256 matches the pinned one,
a Python tool goes into that directory's own virtualenv, a Node tool into its own prefix; every executable
is linked into bin/. `doctor` reports, per tool, whether the binary is there and at the pinned version.
Nothing here uses sudo or a system package manager: a tool that needs one says so and stops.

One install runs at a time on a computer (`machine_lock`), shared by every project. It installs WORKERS tools at once,
in the order the check needs them, and writes each tool as a stage of the `tools` flow (home()/progress/tools.jsonl,
eaos/progress/log.py), its download as a counted step: the Studio's "Preparing the tools" page reads that file, and
`readiness` tells the check which of the tools it needs on a project are ready, still coming, or failed.
"""
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import threading
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import progress

# upstreams/toolchain.json, else its packaged mirror (tools/validate.py keeps them identical; an installed EAOS has no upstreams/)
_SOURCE = Path(__file__).resolve().parent.parent / 'upstreams/toolchain.json'
REGISTRY = _SOURCE if _SOURCE.is_file() else Path(__file__).resolve().parent / 'data/toolchain.json'
VERSION = re.compile(r'(\d+\.\d+\.\d+)')
FLOW = 'tools'
# Tools installed at once: the downloads overlap, and a 4 GB computer copes with three npm installs side by side
WORKERS = 3
CHUNK, TRIVY_CACHE, DAY = 2 ** 20, 'cache/trivy', 24 * 3600
_PIP = threading.Lock()                 # one virtualenv for every Python tool: pip installs into it one at a time


def registry():
    """The pinned tools, and those the person added (eaos/tools_catalog.py: <home>/toolchain-added.json)."""
    base = json.loads(REGISTRY.read_text(encoding='utf-8'))
    added = Path(os.environ.get(base['home']['env']) or base['home']['default']).expanduser() / 'toolchain-added.json'
    return {**base, 'tools': base['tools'] + json.loads(added.read_text(encoding='utf-8'))['tools']} if added.is_file() else base


SKIP = {'.git', 'node_modules', '.venv', 'venv', '__pycache__', 'dist', 'build', '.next', 'vendor'}


def project_files(target):
    """The project's files, relative to its root, without dependency and build directories."""
    target, found = Path(target), []
    for base, directories, names in os.walk(target):
        directories[:] = [d for d in directories if d not in SKIP]
        found += [(Path(base) / name).relative_to(target).as_posix() for name in names]
    return found


RULES = {
    'all': lambda files: True,
    'js': lambda files: any(f.endswith(('.ts', '.tsx', '.js', '.jsx')) for f in files),
    'react': lambda files: any(f.endswith(('.tsx', '.jsx')) for f in files),
    'node_package': lambda files: 'package.json' in files,
    'python': lambda files: any(f.endswith('.py') for f in files),
    'sql': lambda files: any(f.endswith('.sql') for f in files),
    'ci_or_iac': lambda files: any(f.startswith('.github/workflows/') or f.endswith(('Dockerfile', '.tf')) for f in files),
    'openapi': lambda files: any(f.split('/')[-1].startswith(('openapi.', 'swagger.')) for f in files),
}


def rule_applies(rule, files):
    """Whether a tool's `applies` rule (upstreams/toolchain.json) holds for a project's files."""
    test = RULES.get(rule)
    return bool(test(files)) if test else False


def for_the_check(tool, files):
    """Whether the check needs `tool` on a project with these files before it starts: the tool names the check stage
    that runs it (`check`) and its `applies` rule holds there, as eaos/engines/tool.py:declined decides."""
    return bool(tool.get('check')) and rule_applies(tool.get('applies', 'all'), files)


def needed(files):
    """The names of the tools the check needs on a project with these files."""
    return [tool['name'] for tool in registry()['tools'] if for_the_check(tool, files)]


def ordered(tools, files=()):
    """The order the check needs them: first what the check needs on this project, then the rest; each group by its
    first stage (S01 before S04)."""
    return sorted(tools, key=lambda tool: (not for_the_check(tool, files), min(tool['stages'])))


def applies(name, target):
    """(applies, rule) for the named tool on a project."""
    rule = next((t.get('applies', 'all') for t in registry()['tools'] if t['name'] == name), 'all')
    return rule_applies(rule, project_files(target)), rule


def home():
    record = registry()['home']
    return Path(os.environ.get(record['env']) or record['default']).expanduser()


def binary_path(tool):
    """The pinned directory first, then PATH, the same order eaos.engines.process.which uses."""
    pinned = home() / 'bin' / tool['binary']
    if pinned.exists() and os.access(pinned, os.X_OK): return str(pinned)
    return shutil.which(tool['binary'])


def checkout(tool):
    return home() / tool['install']['dir']


def _git_version(tool):
    # A pinned repository of data (rules), not a program: its version is the commit it is at.
    done = subprocess.run(['git', '-C', str(checkout(tool)), 'rev-parse', 'HEAD'], capture_output=True, text=True)
    return (done.stdout.strip(), '') if done.returncode == 0 else (None, 'not installed')


def _library_version(tool):
    # A Node library EAOS's own helper scripts import (axe, the CSS analyzer): it has no executable, and its
    # version is the one its package.json declares in the tool's own prefix.
    found = package_version(tool, tool['install']['package'])
    if not found: return None, 'not installed'
    missing = _companions_missing(tool)
    return (None, missing) if missing else (found, '')


def _version_output(tool, path):
    """(what `path --version` printed, None), or (None, why it could not run)."""
    try:
        # A tool that runs on another (the Structurizr CLI on the JRE) finds it in the pinned bin first.
        done = subprocess.run([path, *tool.get('version_args', ['--version'])], capture_output=True, text=True, timeout=120,
                              env={**tool_env(), 'NO_COLOR': '1', 'PATH': str(home() / 'bin') + os.pathsep + os.environ.get('PATH', '')})
    except (OSError, subprocess.TimeoutExpired) as problem:
        return None, f'{path} --version failed: {problem}'
    return done.stdout + done.stderr, None


def _patterned_version(tool, path, output):
    # A tool numbered with two parts (vulture 2.16) names its own pattern; the rest read as x.y.z.
    match = re.search(tool['version_pattern'], output)
    if not match: return None, f'{path} --version printed no version'
    missing = _companions_missing(tool)
    return (None, missing) if missing else (match.group(1), '')


def _version_match(tool, output):
    # A tool may print another program's version first (dependency-cruiser names the Node.js it refuses):
    # the pinned version anywhere in the output is the tool's own; a refusal of Node.js is said as such.
    if tool['version'] in VERSION.findall(output) and not tool.get('version_reports'):
        return re.search('(' + re.escape(tool['version']) + ')', output)
    return VERSION.search(output)


def _refuses_node(tool, output):
    return (tool['version'] not in output and re.search(r'node', output, re.I)
            and re.search(r'not supported|unsupported|requires|engine', output, re.I))


def _reported_version(tool, path, output):
    match = _version_match(tool, output)
    if _refuses_node(tool, output):
        return None, f"{tool['name']} needs a newer Node.js than this computer has ({output.strip()[:160]})"
    if not match: return None, f'{path} --version printed no version'
    missing = _companions_missing(tool)
    if missing: return None, missing
    # A release numbered one way may report another (the Structurizr CLI reports its parser's version):
    # `version_reports` names what the pinned release prints, and the pinned version stands for it.
    if tool.get('version_reports'):
        return (tool['version'], '') if match.group(1) == tool['version_reports'] else (match.group(1), '')
    return match.group(1), ''


def _binary_version(tool, path):
    if tool.get('version_from') == 'package':
        # A command with no --version (the react-docgen CLI): the version is the one its npm package records.
        found = package_version(tool)
        return (found, '') if found else (None, f"{tool['install']['package']} is not installed in {npm_prefix(tool)}")
    output, failure = _version_output(tool, path)
    if failure: return None, failure
    if tool.get('version_pattern'): return _patterned_version(tool, path, output)
    return _reported_version(tool, path, output)


def found_version(tool):
    if tool['install']['method'] == 'git': return _git_version(tool)
    if tool['install'].get('library'): return _library_version(tool)
    path = binary_path(tool)
    if not path: return None, 'not installed'
    return _binary_version(tool, path)


def package_version(tool, name=None):
    """The version of the npm package `name` (default: the tool's own package) installed in the tool's prefix, or
    None."""
    manifest = npm_prefix(tool) / 'node_modules' / (name or tool['install']['package']) / 'package.json'
    try: return json.loads(manifest.read_text(encoding='utf-8')).get('version')
    except (OSError, ValueError): return None


def node_modules(name):
    """The node_modules folder of the named npm tool, where a helper script resolves it from."""
    tool = next(t for t in registry()['tools'] if t['name'] == name)
    return npm_prefix(tool) / 'node_modules'


def _companions_missing(tool):
    """A tool's companion packages (install.with: npm `name@version`, pip `name==version`) at their pinned versions,
    or what is not."""
    pip = tool['install']['method'] == 'pip'
    for spec in tool['install'].get('with', []):
        name, _, wanted = spec.partition('==') if pip else spec.rpartition('@')
        found = pip_version(name, venv_of(tool)) if pip else package_version(tool, name)
        if found != wanted: return f'{name} {wanted} is not installed beside it (found {found})'
    return ''


def venv_of(tool):
    """The virtualenv of a Python tool: the shared one, or its own (install.own_venv) when its dependencies would move a
    version another tool there relies on."""
    return home() / (f"venv-{tool['name']}" if tool['install'].get('own_venv') else 'venv')


def pip_version(name, venv=None):
    """The version of the Python package `name` installed in the tools' virtualenv (or `venv`), or None."""
    for record in ((venv or home() / 'venv') / 'lib').glob(f"python*/site-packages/{name.replace('-', '_')}-*.dist-info"):
        return record.name[len(name) + 1:-len('.dist-info')]
    return None


STAGE_FILTERS = {'assessment': lambda stages: any(s <= 'S07' for s in stages),
                 'execution': lambda stages: any(s > 'S07' for s in stages)}


def selected(names=None, stage=None, skip=()):
    skipped, wanted = set(skip), set(names or ())
    keep = STAGE_FILTERS.get(stage, lambda stages: True)
    return [t for t in registry()['tools']
            if t['name'] not in skipped and (not names or t['name'] in wanted) and keep(t['stages'])]


def _with_browsers(tool, ok, reason):
    """Playwright counts as ready only with its browsers."""
    if not (ok and tool['name'] == 'playwright'): return ok, reason
    missing = browser_missing()
    return (False, missing) if missing else (ok, reason)


def _release_unavailable(tool, reason):
    try: release_spec(tool)
    except Unavailable as problem: return str(problem), True
    return reason, False


def _doctor_row(tool):
    found, reason = found_version(tool)
    ok = found == tool['version']
    if found and not ok: reason = f'found {found}, pinned {tool["version"]}'
    ok, reason = _with_browsers(tool, ok, reason)
    reason, unavailable = _release_unavailable(tool, reason) if not ok and tool['install']['method'] == 'release' else (reason, False)
    row = {'name': tool['name'], 'role': tool['role'], 'stages': tool['stages'], 'pinned': tool['version'],
           'found': found, 'ok': ok, 'reason': reason, 'unavailable': unavailable}
    if tool.get('license_note'): row['license_note'] = tool['license_note']
    return row


def doctor(names=None, stage=None, skip=()):
    return {'tools': [_doctor_row(tool) for tool in selected(names, stage, skip)]}


def _link(source, name):
    target = home() / 'bin' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() or target.exists(): target.unlink()
    target.symlink_to(source)


TAR_MODES = {'tar.gz': 'r:gz', 'tar.xz': 'r:xz'}


def browsers():
    """Where the pinned Playwright keeps its browser: EAOS's own tools folder, the same on Linux and on a Mac
    (Playwright's default differs between them, and a restart or a cache clean-up must not take it away)."""
    return Path(os.environ.get('PLAYWRIGHT_BROWSERS_PATH') or home() / 'browsers')


def browser_missing():
    """'' when the pinned Playwright's Chromium is in browsers(), else what is missing."""
    manifest = home() / 'node/node_modules/playwright-core/browsers.json'
    try: wanted = {b['name']: b['revision'] for b in json.loads(manifest.read_text(encoding='utf-8'))['browsers']}
    except (OSError, ValueError, KeyError): return 'Playwright is not installed'
    for name, folder in (('chromium', 'chromium'), ('chromium-headless-shell', 'chromium_headless_shell')):
        if name in wanted and not (browsers() / f'{folder}-{wanted[name]}').is_dir(): return f'{name} {wanted[name]} is not installed'
    return ''


def install_browsers(echo=print):
    """Download the browser the pinned Playwright drives (no administrator rights; the system libraries a
    Linux computer may lack are named in the error, and `playwright install-deps` needs an administrator)."""
    if not browser_missing(): return
    playwright = home() / 'bin/playwright'
    done = subprocess.run([str(playwright), 'install', 'chromium', 'chromium-headless-shell'], capture_output=True, text=True,
                          env={**tool_env(), 'PLAYWRIGHT_BROWSERS_PATH': str(browsers())}, timeout=1800)
    if done.returncode: raise RuntimeError('the browser did not install: ' + (done.stdout + done.stderr)[-400:])
    echo(f"install chromium for playwright in {browsers()}")


class Unavailable(RuntimeError):
    """The tool publishes no build for this computer: EAOS goes on without it and says so."""


def platform_key():
    import platform
    system = {'darwin': 'darwin', 'linux': 'linux'}.get(sys.platform, sys.platform)
    machine = {'aarch64': 'arm64', 'amd64': 'x86_64'}.get(platform.machine().lower(), platform.machine().lower())
    return f'{system}-{machine}'


def release_spec(tool):
    """The pinned build of a released tool for this computer (install.platforms), or Unavailable."""
    spec, platforms = tool['install'], tool['install'].get('platforms')
    if not platforms: return spec if platform_key() == 'linux-x86_64' else _unavailable(tool)
    return platforms.get(platform_key()) or _unavailable(tool)


def _unavailable(tool):
    raise Unavailable(f"{tool['name']} publishes no build for this computer ({platform_key()})")


def _download(url, part, step):
    """The file at `url` written to `part` (never held in memory: a CodeQL bundle is 1.2 GB), carried on from what an
    earlier attempt left there (an HTTP range), `step(done, total)` in bytes as it comes."""
    have = part.stat().st_size if part.exists() else 0
    request = urllib.request.Request(url, headers={'Range': f'bytes={have}-'} if have else {})
    try: response = urllib.request.urlopen(request, timeout=300)
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
    if spec.get('tree'):
        # A whole directory (a JRE, a CLI with its jars): extracted with no path escaping the folder.
        if spec['archive'] == 'zip':
            with zipfile.ZipFile(blob) as archive:
                unsafe = next((name for name in archive.namelist() if name.startswith('/') or '..' in Path(name).parts), None)
                if unsafe: raise RuntimeError(f"{tool['name']}: unsafe path {unsafe!r} in the archive; nothing installed")
                archive.extractall(folder)
        else:
            with tarfile.open(fileobj=blob, mode=TAR_MODES[spec['archive']]) as archive:
                archive.extractall(folder, filter='data')
        target = folder / spec['entry']
        if not target.is_file(): raise RuntimeError(f"{tool['name']}: {spec['entry']} is not in the archive")
    else:
        (target := folder / tool['binary']).write_bytes(blob.read() if spec['archive'] == 'binary' else _member(tool, spec, blob))
    target.chmod(0o755)
    before = (home() / 'bin' / tool['binary']).resolve()           # the version linked until now (CodeQL's is 1.4 GB)
    _link(target, tool['binary'])
    if folder.parent in before.parents and folder not in before.parents: shutil.rmtree(folder.parent / before.relative_to(folder.parent).parts[0])


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


def uv():
    """The uv the installer brought (~/.eaos/app/uv/uv), or one on PATH, or None."""
    return str(brought) if (brought := Path.home() / '.eaos/app/uv/uv').exists() else shutil.which('uv')


def _pip(tool):
    """A Python tool in its own environment under the tools home. With uv when there is one: the environments
    the installer makes have no pip, and some Pythons have no ensurepip to make one."""
    with _PIP: _pip_one(tool)


def tool_env():
    """The environment a pinned tool runs or installs in: without EAOS's own Python settings. With PYTHONPATH, pip took
    a dependency EAOS happens to carry (attrs for Semgrep) as already installed, so a fresh tools folder missed it; with
    PYTHONSAFEPATH, a tool's script no longer imports its sibling modules (CodeQL's Python extractor failed)."""
    return {name: value for name, value in os.environ.items() if name not in ('PYTHONPATH', 'PYTHONSAFEPATH')}


def _pip_one(tool):
    venv, env = venv_of(tool), tool_env()   # no download cache: a tool installs once, and the caches kept each one
    wanted = [f"{tool['install']['package']}=={tool['version']}", *tool['install'].get('with', [])]
    runner = uv()
    if not (venv / 'bin/python').exists():
        if runner: subprocess.run([runner, 'venv', '--quiet', '--no-cache', '--python', sys.executable, str(venv)], check=True, env=env)
        else: subprocess.run([sys.executable, '-m', 'venv', str(venv)], check=True, env=env)
    if runner and not (venv / 'bin/pip').exists():
        subprocess.run([runner, 'pip', 'install', '--quiet', '--no-cache', '--python', str(venv / 'bin/python'), *wanted], check=True, env=env)
    else:
        subprocess.run([str(venv / 'bin/pip'), 'install', '-q', '--no-cache-dir', *wanted], check=True, env=env)
    _link(venv / 'bin' / tool['binary'], tool['binary'])


def npm_prefix(tool):
    """Where an npm tool is installed: its own folder, so two tools never share (and clash over) one dependency's
    version; Playwright stays in node/, where the lock and NODE_PATH find it."""
    return home() / 'node' if tool['name'] == 'playwright' else home() / 'npm' / tool['name']


def _npm(tool):
    (prefix := npm_prefix(tool)).mkdir(parents=True, exist_ok=True)
    npm = shutil.which('npm')
    if not npm: raise RuntimeError(f"{tool['name']}: npm is not installed; install Node.js 18 or newer, then run this again")
    env = {**tool_env(), **tool['install'].get('env', {})}
    with tempfile.TemporaryDirectory(prefix='eaos-npm-cache-') as cache:   # npm's own kept 1.5 GB of the tools
        subprocess.run([npm, 'install', '--prefix', str(prefix), '--cache', cache, '--no-audit', '--no-fund', '--loglevel=error',
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


def trivy_db():
    """Trivy's vulnerability database in the tools' cache (its metadata.json), or None when there is none yet."""
    found = home() / TRIVY_CACHE / 'db/metadata.json'
    return found if found.is_file() else None


def _download_db(cache):
    trivy = home() / 'bin/trivy'
    done = subprocess.run([str(trivy), 'fs', '--download-db-only', '--quiet', '--cache-dir', str(cache)], capture_output=True,
                          text=True, timeout=1800)
    if done.returncode: raise RuntimeError('the vulnerability database did not download: ' + (done.stdout + done.stderr)[-300:])


def refresh_db():
    """A new vulnerability database, downloaded beside the one in use and moved in whole, so a check reading the old
    one (`--skip-db-update`) is never disturbed; nothing while an install runs. Returns 0, or 1 when it could not be
    had."""
    from .locks import held
    cache, fresh, old = home() / TRIVY_CACHE, home() / 'cache/trivy-next', home() / TRIVY_CACHE / 'db-old'
    with machine_lock(wait=False) as mine:
        if not mine: return 0
        shutil.rmtree(fresh, ignore_errors=True)
        try: _download_db(fresh)
        except (RuntimeError, OSError, subprocess.SubprocessError) as problem:
            print(problem)
            return 1
        shutil.rmtree(old, ignore_errors=True)
        with held(cache, shared=False):             # no scan of any project reads it while it is swapped
            if (cache / 'db').exists(): (cache / 'db').rename(old)
            (fresh / 'db').rename(cache / 'db')
        for folder in (old, fresh): shutil.rmtree(folder, ignore_errors=True)
    return 0


def _db_old():
    found = trivy_db()
    if not found: return False
    try: downloaded = json.loads(found.read_text(encoding='utf-8'))['DownloadedAt']
    except (OSError, ValueError, KeyError): return True
    at = datetime.fromisoformat(re.sub(r'(\.\d{6})\d*', r'\1', downloaded).replace('Z', '+00:00'))
    return (datetime.now(timezone.utc) - at).total_seconds() > DAY


def _ensure(tool, step, echo):
    """The tool at its pinned version, installed when it is not; with Playwright its browser, with Trivy its
    vulnerability database."""
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
    if tool['name'] == 'trivy' and not trivy_db(): _download_db(home() / TRIVY_CACHE)


def _install_one(tool, log, echo):
    """One tool as one stage of the tools flow; its name when it could not be installed, else ''."""
    name, began = tool['name'], time.monotonic()
    log.stage_started(name)
    row = {'stage': name, 'status': 'ok', 'reason': '', 'necessity': 'required', 'artifacts': []}
    try:
        _ensure(tool, log.stepper(name), echo)
    except Unavailable as problem:
        echo(f"skip    {problem}")
        row.update(status='unavailable', reason=str(problem), reason_code='tool_unavailable')
    except Exception as problem:              # one tool that fails, however, never stops the others
        row.update(status='failed', reason=f'{type(problem).__name__}: {problem}'[:300], reason_code='tool_failed')
        echo(f"FAILED  {name}: {row['reason']}")
    log.ended({**row, 'seconds': round(time.monotonic() - began, 2)})
    return name if row['status'] == 'failed' else ''


@contextmanager
def machine_lock(wait=True):
    """One install at a time on this computer, whichever project or command asked: a second waits for the first
    (`wait=False`: yields False at once instead)."""
    path = home() / 'install.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as handle:
        try: fcntl.flock(handle, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        except BlockingIOError:
            yield False
            return
        yield True


def installing():
    """Whether an install holds the lock now (nothing is written to find out)."""
    path = home() / 'install.lock'
    if not path.exists(): return False
    with path.open() as handle:
        try: fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: return True
    return False


def stages(tools):
    """The tools as the stages of the tools flow, each described by its pinned version."""
    return [progress.Stage(tool['name'], description=tool['version']) for tool in tools]


def install(names=None, stage=None, skip=(), echo=print, project=None):
    """Install what is missing or at another version, WORKERS at a time, in the order the check needs them on
    `project`, each tool a stage of the tools flow; asked again while it ran (`prepare`), it runs once more for what
    failed. Returns the tools that could not be installed."""
    tools = ordered(selected(names, stage, skip), project_files(project) if project else ())
    with machine_lock():
        failed = _run(tools, echo)
        while failed and _asked_again(): failed = _run(tools, echo)
    return failed


def _run(tools, echo):
    log = progress.ProgressLog(home(), FLOW, sampler=False)
    log.started(stages(tools), [tool['name'] for tool in tools], {})
    began = time.monotonic()
    with ThreadPoolExecutor(WORKERS) as pool:
        failed = [name for name in pool.map(lambda tool: _install_one(tool, log, echo), tools) if name]
    log.finish('INCOMPLETE' if failed else 'COMPLETE', seconds=round(time.monotonic() - began, 2))
    return failed


def _asked_again():
    asked = home() / 'install.again'
    if not asked.exists(): return False
    asked.unlink()
    return True


def stale():
    """Whether the next start installs again: the last install did not end with every tool ready, a tool's pin changed
    since, or a tool's command is gone."""
    state = progress.fold(progress.read(home(), FLOW))
    if state['status'] != 'COMPLETE': return True
    pinned = {s['name']: s['description'] for s in state['stages']}
    tools = registry()['tools']
    commands = [t for t in tools if t['install']['method'] != 'git' and not t['install'].get('library')]
    return any(pinned.get(t['name']) != t['version'] for t in tools) or any(not (home() / 'bin' / t['binary']).exists() for t in commands)


def _spawn(argv, log):
    """`python -m eaos <argv>` of this same EAOS, on its own: it outlives whoever started it."""
    here = str(Path(__file__).resolve().parents[1])
    env = {**os.environ, 'PYTHONSAFEPATH': '1', 'PYTHONPATH': os.pathsep.join([here, *filter(None, [os.environ.get('PYTHONPATH')])])}
    home().mkdir(parents=True, exist_ok=True)
    with open(home() / log, 'ab') as out:
        return subprocess.Popen([sys.executable, '-m', 'eaos', *argv], cwd=home(), env=env, stdin=subprocess.DEVNULL,
                                stdout=out, stderr=out, start_new_session=True, close_fds=True)


def prepare(project=None):
    """Interface first: called when EAOS opens on a project, it starts the full install in the background when one is
    needed (`stale`), in the order this project needs the tools, and waits until it holds the lock; an install already
    running is asked to try again what failed once it ends. A vulnerability database a day old is refreshed in the
    background. Returns True when it started the install."""
    if installing():
        (home() / 'install.again').touch()
        return False
    if not stale():
        if _db_old(): _spawn(['tools', 'refresh'], 'refresh.log')
        return False
    child = _spawn(['tools', 'install', *(['--project', str(project)] if project else [])], 'install.log')
    deadline = time.monotonic() + 30
    while child.poll() is None and not installing() and time.monotonic() < deadline: time.sleep(0.1)
    return True


def readiness(files):
    """What the check waits for on a project with these files: {needed, pending, failed: {name: reason}, ready}. A
    needed tool is ready once its stage of the last install ended ok (or it has no build for this computer); pending
    while an install runs and has not finished it; failed otherwise, with the reason its install gave."""
    state = progress.fold(progress.read(home(), FLOW))
    shown = {s['name']: s for s in state['stages']}
    running = installing()
    pending, failed = [], {}
    for name in needed(files):
        stage = shown.get(name) or {'state': 'waiting', 'reason': ''}
        if stage['state'] in ('ok', 'unavailable'): continue
        if running and stage['state'] in ('waiting', 'running'): pending.append(name)
        else: failed[name] = stage['reason'] or 'not installed'
    return {'needed': needed(files), 'pending': pending, 'failed': failed, 'ready': not pending and not failed}


def ready(project):
    """Whether every tool the check needs on `project` is ready now."""
    return readiness(project_files(project))['ready']


def wait_for_check(project, echo=lambda done, total: None, install=True, every=2.0):
    """The readiness of the check's tools on `project` once none of them is still coming. When they are not all ready
    it starts the install first (`install`; a failed tool is tried again), then calls `echo(done, total)` each time
    another of them is ready or failed."""
    files, said = project_files(project), None
    if install and not readiness(files)['ready']: prepare(project)
    while True:
        gate = readiness(files)
        done = len(gate['needed']) - len(gate['pending'])
        if done != said: echo(done, len(gate['needed']))
        said = done
        if not gate['pending']: return gate
        time.sleep(every)


def _show(report, as_json):
    if as_json: print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        for row in report['tools']:
            print(f"{'ok  ' if row['ok'] else 'MISS'} {row['name']:20} pinned {row['pinned']:10} {row['found'] or '-':10} {row['reason']}")
    return 0 if all(row['ok'] for row in report['tools']) else 1


def main(args):
    names = args.only.split(',') if getattr(args, 'only', None) else None
    skip = args.skip.split(',') if getattr(args, 'skip', None) else ()
    if args.action == 'doctor': return _show(doctor(names, args.stage, skip), args.json)
    if args.action == 'refresh': return refresh_db()
    return 1 if install(names, args.stage, skip, project=args.project) else 0
