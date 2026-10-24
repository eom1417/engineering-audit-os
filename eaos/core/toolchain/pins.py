"""The pinned tools (eaos/data/toolchain.json, and those the person added): the tools home and where each tool lives
in it, which tools a project needs, and the build of a released tool for this computer."""
import json
import os
import shutil
import sys
from pathlib import Path

REGISTRY = Path(__file__).resolve().parents[2] / 'data/toolchain.json'
TRIVY_CACHE = 'cache/trivy'


def registry():
    """The pinned tools, and those the person added (eaos/core/tools_catalog.py: <home>/toolchain-added.json)."""
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
    """Whether a tool's `applies` rule (eaos/data/toolchain.json) holds for a project's files."""
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


def node_modules(name):
    """The node_modules folder of the named npm tool, where a helper script resolves it from."""
    tool = next(t for t in registry()['tools'] if t['name'] == name)
    return npm_prefix(tool) / 'node_modules'


def venv_of(tool):
    """The virtualenv of a Python tool: the shared one, or its own (install.own_venv) when its dependencies would move a
    version another tool there relies on."""
    return home() / (f"venv-{tool['name']}" if tool['install'].get('own_venv') else 'venv')


STAGE_FILTERS = {'assessment': lambda stages: any(s <= 'S07' for s in stages),
                 'execution': lambda stages: any(s > 'S07' for s in stages)}


def selected(names=None, stage=None, skip=()):
    skipped, wanted = set(skip), set(names or ())
    keep = STAGE_FILTERS.get(stage, lambda stages: True)
    return [t for t in registry()['tools']
            if t['name'] not in skipped and (not names or t['name'] in wanted) and keep(t['stages'])]


def _link(source, name):
    target = home() / 'bin' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() or target.exists(): target.unlink()
    target.symlink_to(source)


def browsers():
    """Where the pinned Playwright keeps its browser: EAOS's own tools folder, the same on Linux and on a Mac
    (Playwright's default differs between them, and a restart or a cache clean-up must not take it away)."""
    return Path(os.environ.get('PLAYWRIGHT_BROWSERS_PATH') or home() / 'browsers')


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


def uv():
    """The uv the installer brought (~/.eaos/app/uv/uv), or one on PATH, or None."""
    return str(brought) if (brought := Path.home() / '.eaos/app/uv/uv').exists() else shutil.which('uv')


def tool_env():
    """The environment a pinned tool runs or installs in: without EAOS's own Python settings. With PYTHONPATH, pip took
    a dependency EAOS happens to carry (attrs for Semgrep) as already installed, so a fresh tools folder missed it; with
    PYTHONSAFEPATH, a tool's script no longer imports its sibling modules (CodeQL's Python extractor failed)."""
    return {name: value for name, value in os.environ.items() if name not in ('PYTHONPATH', 'PYTHONSAFEPATH')}


def npm_prefix(tool):
    """Where an npm tool is installed: its own folder, so two tools never share (and clash over) one dependency's
    version; Playwright stays in node/, where the lock and NODE_PATH find it."""
    return home() / 'node' if tool['name'] == 'playwright' else home() / 'npm' / tool['name']
