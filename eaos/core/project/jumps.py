"""The packages a change moved several major versions at once, said at the hand-over: an automatic upgrade moved a
stranger's icon tool's minimatch from 3 to 11 to reach the fixed version, and nothing told the person to try the tool
(2026-11-04). npm's lock files, before and after the change, compared package by package."""
import json
import re
from pathlib import PurePosixPath
from ..system.process import run_command

MAJORS = 2              # a move of this many major versions or more is said
LOCKS = ('package-lock.json', 'npm-shrinkwrap.json')
SHOWN = 8               # packages named at most; the count says the rest


def big_jumps(root, base, branch):
    """One sentence per package of a lock file moved MAJORS major versions or more between `base` and `branch`."""
    changed = _git(root, 'diff', '--name-only', f'{base}..{branch}').splitlines()
    found = [f'{name} {old} -> {new} ({path})' for path in changed if PurePosixPath(path).name in LOCKS
             for name, old, new in _moved(_packages(root, base, path), _packages(root, branch, path))]
    return found[:SHOWN] + ([f'and {len(found) - SHOWN} more'] if len(found) > SHOWN else [])


def _moved(before, after):
    return sorted({(name, old, after[key]) for key, (name, old) in ((k, (_name(k), v)) for k, v in before.items())
                   if key in after and _major(after[key]) - _major(old) >= MAJORS})


def _packages(root, revision, path):
    """{lock key: version} of a lock file at a revision; {} when it is not there or does not read."""
    try: rows = json.loads(_git(root, 'show', f'{revision}:{path}') or '{}').get('packages') or {}
    except ValueError: return {}
    return {key: row['version'] for key, row in rows.items() if key and isinstance(row, dict) and row.get('version')}


def _name(key):
    return key.rsplit('node_modules/', 1)[-1]


def _major(version):
    found = re.match(r'\D*(\d+)', str(version))
    return int(found[1]) if found else 0


def _git(root, *args):
    shown = run_command(['git', '-C', str(root), *args], timeout=60)
    return shown.stdout if not shown.returncode else ''
