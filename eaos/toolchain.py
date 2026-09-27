"""Every external tool at its pinned version, installed without root, and checked by one command.

upstreams/toolchain.json is the only list. `install` puts each tool under $EAOS_ENGINE_TOOLS (default
/workspace/engine-tools): a release is downloaded and accepted only if its sha256 matches the pinned one,
a Python tool goes into that directory's own virtualenv, a Node tool into its own prefix; every executable
is linked into bin/. `doctor` reports, per tool, whether the binary is there and at the pinned version.
Nothing here uses sudo or a system package manager: a tool that needs one says so and stops.
"""
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

# The source is upstreams/toolchain.json; an installed package reads its packaged mirror, which
# tools/validate.py keeps identical (an installed EAOS has no upstreams/ folder beside it).
_SOURCE = Path(__file__).resolve().parent.parent / 'upstreams/toolchain.json'
REGISTRY = _SOURCE if _SOURCE.is_file() else Path(__file__).resolve().parent / 'data/toolchain.json'
VERSION = re.compile(r'(\d+\.\d+\.\d+)')


def registry():
    return json.loads(REGISTRY.read_text(encoding='utf-8'))


SKIP = {'.git', 'node_modules', '.venv', 'venv', '__pycache__', 'dist', 'build', '.next', 'vendor'}


def project_files(target):
    """The project's files, relative to its root, without dependency and build directories."""
    target, found = Path(target), []
    for base, directories, names in os.walk(target):
        directories[:] = [d for d in directories if d not in SKIP]
        found += [(Path(base) / name).relative_to(target).as_posix() for name in names]
    return found


def rule_applies(rule, files):
    """Whether a tool's `applies` rule (upstreams/toolchain.json) holds for a project's files."""
    if rule == 'all': return True
    if rule == 'js': return any(f.endswith(('.ts', '.tsx', '.js', '.jsx')) for f in files)
    if rule == 'sql': return any(f.endswith('.sql') for f in files)
    if rule == 'ci_or_iac': return any(f.startswith('.github/workflows/') or f.endswith(('Dockerfile', '.tf')) for f in files)
    if rule == 'openapi': return any(f.split('/')[-1].startswith(('openapi.', 'swagger.')) for f in files)
    return False


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


def _checkout(tool):
    return home() / tool['install']['dir']


def found_version(tool):
    if tool['install']['method'] == 'git':
        # A pinned repository of data (rules), not a program: its version is the commit it is at.
        done = subprocess.run(['git', '-C', str(_checkout(tool)), 'rev-parse', 'HEAD'], capture_output=True, text=True)
        return (done.stdout.strip(), '') if done.returncode == 0 else (None, 'not installed')
    path = binary_path(tool)
    if not path: return None, 'not installed'
    try:
        # A tool that runs on another (the Structurizr CLI on the JRE) finds it in the pinned bin first.
        done = subprocess.run([path, *tool.get('version_args', ['--version'])], capture_output=True, text=True, timeout=120,
                              env={**os.environ, 'NO_COLOR': '1', 'PATH': str(home() / 'bin') + os.pathsep + os.environ.get('PATH', '')})
    except (OSError, subprocess.TimeoutExpired) as problem:
        return None, f'{path} --version failed: {problem}'
    match = VERSION.search(done.stdout + done.stderr)
    if not match: return None, f'{path} --version printed no version'
    missing = _companions_missing(tool)
    if missing: return None, missing
    # A release numbered one way may report another (the Structurizr CLI reports its parser's version):
    # `version_reports` names what the pinned release prints, and the pinned version stands for it.
    if tool.get('version_reports'):
        return (tool['version'], '') if match.group(1) == tool['version_reports'] else (match.group(1), '')
    return match.group(1), ''


def _companions_missing(tool):
    """An npm tool's companion packages (install.with) at their pinned versions, or what is not."""
    for spec in tool['install'].get('with', []):
        name, _, wanted = spec.rpartition('@')
        manifest = home() / 'node/node_modules' / name / 'package.json'
        try: found = json.loads(manifest.read_text(encoding='utf-8')).get('version')
        except (OSError, ValueError): found = None
        if found != wanted: return f'{name} {wanted} is not installed beside it (found {found})'
    return ''


def selected(names=None, stage=None, skip=()):
    tools = [t for t in registry()['tools'] if t['name'] not in set(skip)]
    if names: tools = [t for t in tools if t['name'] in set(names)]
    if stage == 'assessment': tools = [t for t in tools if any(s <= 'S07' for s in t['stages'])]
    elif stage == 'execution': tools = [t for t in tools if any(s > 'S07' for s in t['stages'])]
    return tools


def doctor(names=None, stage=None, skip=()):
    rows = []
    for tool in selected(names, stage, skip):
        found, reason = found_version(tool)
        ok = found == tool['version']
        if found and not ok: reason = f'found {found}, pinned {tool["version"]}'
        if ok and tool['name'] == 'playwright':
            missing = browser_missing()
            if missing: ok, reason = False, missing
        unavailable = False
        if not ok and tool['install']['method'] == 'release':
            try: release_spec(tool)
            except Unavailable as problem: reason, unavailable = str(problem), True
        row = {'name': tool['name'], 'role': tool['role'], 'stages': tool['stages'], 'pinned': tool['version'],
               'found': found, 'ok': ok, 'reason': reason, 'unavailable': unavailable}
        if tool.get('license_note'): row['license_note'] = tool['license_note']
        rows.append(row)
    return {'tools': rows}


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
                          env={**os.environ, 'PLAYWRIGHT_BROWSERS_PATH': str(browsers())}, timeout=1800)
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
    spec = tool['install']
    platforms = spec.get('platforms')
    if not platforms: return spec if platform_key() == 'linux-x86_64' else _unavailable(tool)
    return platforms.get(platform_key()) or _unavailable(tool)


def _unavailable(tool):
    raise Unavailable(f"{tool['name']} publishes no build for this computer ({platform_key()})")


def _release(tool):
    spec = release_spec(tool)
    with urllib.request.urlopen(spec['url'], timeout=300) as response: blob = response.read()
    digest = hashlib.sha256(blob).hexdigest()
    if digest != spec['sha256']:
        raise RuntimeError(f"{tool['name']}: sha256 {digest} does not match the pinned {spec['sha256']}; nothing installed")
    folder = home() / 'releases' / f"{tool['name']}-{tool['version']}"
    folder.mkdir(parents=True, exist_ok=True)
    if spec.get('tree'):
        # A whole directory (a JRE, a CLI with its jars): extracted with no path escaping the folder.
        if spec['archive'] == 'zip':
            import zipfile
            with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                for name in archive.namelist():
                    if name.startswith('/') or '..' in Path(name).parts:
                        raise RuntimeError(f"{tool['name']}: unsafe path {name!r} in the archive; nothing installed")
                archive.extractall(folder)
        else:
            with tarfile.open(fileobj=io.BytesIO(blob), mode=TAR_MODES[spec['archive']]) as archive:
                archive.extractall(folder, filter='data')
        target = folder / spec['entry']
        if not target.is_file(): raise RuntimeError(f"{tool['name']}: {spec['entry']} is not in the archive")
        target.chmod(0o755)
        _link(target, tool['binary'])
        return
    if spec['archive'] == 'binary':
        target = folder / spec['member']
        target.write_bytes(blob)
    else:
        with tarfile.open(fileobj=io.BytesIO(blob), mode=TAR_MODES[spec['archive']]) as archive:
            member = next((m for m in archive.getmembers() if m.name.rsplit('/', 1)[-1] == spec['member'] and m.isfile()), None)
            if member is None: raise RuntimeError(f"{tool['name']}: {spec['member']} is not in the archive")
            target = folder / spec['member']
            target.write_bytes(archive.extractfile(member).read())
    target.chmod(0o755)
    _link(target, tool['binary'])


def uv():
    """The uv the installer brought (~/.eaos/app/uv/uv), or one on PATH, or None."""
    brought = Path.home() / '.eaos/app/uv/uv'
    return str(brought) if brought.exists() else shutil.which('uv')


def _pip(tool):
    """A Python tool in its own environment under the tools home. With uv when there is one: the environments
    the installer makes have no pip, and some Pythons have no ensurepip to make one."""
    venv, wanted = home() / 'venv', f"{tool['install']['package']}=={tool['version']}"
    runner = uv()
    if not (venv / 'bin/python').exists():
        if runner: subprocess.run([runner, 'venv', '--quiet', '--python', sys.executable, str(venv)], check=True)
        else: subprocess.run([sys.executable, '-m', 'venv', str(venv)], check=True)
    if runner and not (venv / 'bin/pip').exists():
        subprocess.run([runner, 'pip', 'install', '--quiet', '--python', str(venv / 'bin/python'), wanted], check=True)
    else:
        subprocess.run([str(venv / 'bin/pip'), 'install', '-q', wanted], check=True)
    _link(venv / 'bin' / tool['binary'], tool['binary'])


def _npm(tool):
    prefix = home() / 'node'
    prefix.mkdir(parents=True, exist_ok=True)
    npm = shutil.which('npm')
    if not npm: raise RuntimeError(f"{tool['name']}: npm is not installed; install Node.js 18 or newer, then run this again")
    env = {**os.environ, **tool['install'].get('env', {})}
    subprocess.run([npm, 'install', '--prefix', str(prefix), '--no-audit', '--no-fund', '--loglevel=error',
                    f"{tool['install']['package']}@{tool['version']}", *tool['install'].get('with', [])], check=True, env=env)
    _link(prefix / 'node_modules/.bin' / tool['binary'], tool['binary'])


def _git(tool):
    """Fetch exactly the pinned commit of a repository into its own directory under the tools home."""
    folder, spec = _checkout(tool), tool['install']
    folder.mkdir(parents=True, exist_ok=True)
    for argv in (['init', '-q'], ['remote', 'remove', 'origin'], ['remote', 'add', 'origin', spec['repository']],
                 ['fetch', '-q', '--depth', '1', 'origin', tool['version']], ['checkout', '-q', '--force', 'FETCH_HEAD']):
        done = subprocess.run(['git', '-C', str(folder), *argv], capture_output=True, text=True)
        if done.returncode and argv[:2] != ['remote', 'remove']:
            raise RuntimeError(f"{tool['name']}: git {' '.join(argv)} failed: {done.stderr.strip()[-200:]}")


def install(names=None, stage=None, skip=(), echo=print):
    """Install what is missing or at another version. Returns the tools that could not be installed."""
    failed = []
    for tool in selected(names, stage, skip):
        found, _ = found_version(tool)
        if found == tool['version']:
            echo(f"ok      {tool['name']} {found}")
            if tool['name'] == 'playwright':
                try: install_browsers(echo)
                except (RuntimeError, OSError, subprocess.SubprocessError) as problem:
                    echo(f"FAILED  playwright browser: {problem}"); failed.append('playwright-browser')
            continue
        if tool.get('license_note'): echo(f"note    {tool['name']}: {tool['license_note']}")
        try:
            {'release': _release, 'pip': _pip, 'npm': _npm, 'git': _git}[tool['install']['method']](tool)
            found, reason = found_version(tool)
            if found != tool['version']: raise RuntimeError(reason or f'installed {found}, pinned {tool["version"]}')
            echo(f"install {tool['name']} {found}")
            if tool['name'] == 'playwright': install_browsers(echo)
        except Unavailable as problem:
            echo(f"skip    {problem}")
        except (RuntimeError, OSError, subprocess.CalledProcessError) as problem:
            echo(f"FAILED  {tool['name']}: {problem}")
            failed.append(tool['name'])
    return failed


def main(args):
    names = args.only.split(',') if getattr(args, 'only', None) else None
    skip = args.skip.split(',') if getattr(args, 'skip', None) else ()
    if args.action == 'doctor':
        report = doctor(names, args.stage, skip)
        if args.json: print(json.dumps(report, ensure_ascii=False, indent=1))
        else:
            for row in report['tools']:
                print(f"{'ok  ' if row['ok'] else 'MISS'} {row['name']:20} pinned {row['pinned']:10} {row['found'] or '-':10} {row['reason']}")
        return 0 if all(row['ok'] for row in report['tools']) else 1
    return 1 if install(names, args.stage, skip) else 0
