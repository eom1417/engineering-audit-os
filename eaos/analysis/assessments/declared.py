"""The dependencies the manifests beside a lock file declare, and which of them only develop or build the project.

A lock file holds what is installed, not why: the manifests in its folder and its workspace members (package.json
`workspaces`, pyproject.toml `[tool.uv.workspace] members`) say which packages the project names itself. package.json:
dependencies, optional and peer ones are `prod`, devDependencies `dev`; pyproject.toml: PEP 621 dependencies and
extras and Poetry's main dependencies are `prod`, `[dependency-groups]` and Poetry's groups `dev`. Python names are
compared in their normal form (PEP 503); a package no manifest names is pulled in by another one.
"""
import re
from pathlib import Path, PurePosixPath

from ...core.system.files import read_json, tomllib
from ...engines.security.syft import REQUIREMENT

JSON_SCOPES = {'dependencies': 'prod', 'optionalDependencies': 'prod', 'peerDependencies': 'prod', 'devDependencies': 'dev'}


def normal(name):
    """A Python package's normal name; any other name is unchanged but for its case."""
    return re.sub(r'[-_.]+', '-', str(name)).lower()


def declared(target, lock):
    """{'prod': names, 'dev': names} the manifests beside the lock file at `lock` (relative to `target`) declare."""
    folder = Path(target) / PurePosixPath(lock).parent
    names = {'prod': set(), 'dev': set()}
    for where in [folder, *_members(folder)]:
        for scope, found in _package_json(read_json(where / 'package.json', {}) or {}) + _pyproject(_toml(where)):
            names[scope] |= {normal(name) for name in found}
    return names


def _toml(folder):
    try: return tomllib.loads((folder / 'pyproject.toml').read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError): return {}


def _members(folder):
    """The workspace members' folders the manifests of `folder` list."""
    workspaces = (read_json(folder / 'package.json', {}) or {}).get('workspaces') or []
    if isinstance(workspaces, dict): workspaces = workspaces.get('packages') or []
    patterns = list(workspaces) + list(_table(_toml(folder), 'tool', 'uv', 'workspace').get('members') or [])
    return sorted({path for pattern in patterns for path in folder.glob(pattern) if path.is_dir()})


def _table(data, *keys):
    """The TOML table at `keys`, {} when any of them is missing."""
    for key in keys: data = data.get(key) or {}
    return data


def _package_json(manifest):
    return [(scope, manifest.get(key) or {}) for key, scope in JSON_SCOPES.items()]


def _requirements(lines):
    return [match.group(1) for match in map(REQUIREMENT.match, (line for line in lines if isinstance(line, str))) if match]


def _joined(table):
    """Every entry of a table of lists (extras, dependency groups), or of a table of tables' `dependencies` (Poetry's groups)."""
    return [entry for value in table.values() for entry in (value.get('dependencies') or {} if isinstance(value, dict) else value)]


def _pyproject(data):
    project, poetry = _table(data, 'project'), _table(data, 'tool', 'poetry')
    prod = _requirements(list(project.get('dependencies') or []) + _joined(_table(project, 'optional-dependencies')))
    dev = _requirements(_joined(_table(data, 'dependency-groups'))) + _joined(_table(poetry, 'group'))
    return [('prod', prod + list(_table(poetry, 'dependencies'))), ('dev', dev + list(_table(poetry, 'dev-dependencies')))]
