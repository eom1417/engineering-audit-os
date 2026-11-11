"""Every integrity hash a change adds to a lock file, checked against the registry it names: a hash written by hand is
refused. A wrong hash makes `npm ci` fail while the batch's own checks still pass, which is what an assistant gets by
writing the hashes of a bumped package "from memory". npm's package-lock.json and npm-shrinkwrap.json
(`dist.integrity` of the registry's version record), uv.lock (PyPI's sha256 of each file)."""
import json
import re
from pathlib import Path
from ....kernel.system.files import tomllib
from ....kernel.system.process import run_command
from ....kernel.system.web import opened

NPM_LOCKS = ('package-lock.json', 'npm-shrinkwrap.json')
TARBALL = re.compile(r'^(https?://.+?)/((?:@[^/]+/)?([^/]+))/-/\3-(.+)\.tgz$')


def wrong(root, changed):
    """What is wrong with the hashes the last commit of the copy `root` added, one line each: only the hashes that
    change wrote are asked for, against the lock file's text in the commit before it."""
    found = []
    for path in changed:
        name, file = Path(path).name, Path(root) / path
        if not file.is_file() or name not in (*NPM_LOCKS, 'uv.lock'): continue
        pairs = _npm if name in NPM_LOCKS else _uv
        old = _before(root, path)
        added = pairs(file.read_text(encoding='utf-8')) - (pairs(old) if old else set())
        found += [f'{path}: {said}' for said in _checked(added, name in NPM_LOCKS)]
    return found


def _before(root, path):
    """The file's text in the commit before the last one, or None when that commit made it."""
    shown = run_command(['git', '-C', str(root), 'show', f'HEAD~1:{path}'], timeout=60)
    return shown.stdout if not shown.returncode else None


def _npm(text):
    """{(tarball url, integrity)} of an npm lock file."""
    try: packages = (json.loads(text).get('packages') or {}).values()
    except ValueError: return set()
    return {(row['resolved'], row['integrity']) for row in packages
            if isinstance(row, dict) and row.get('resolved') and row.get('integrity')}


def _uv(text):
    """{(name, version, file name, sha256)} of every sdist and wheel of a uv.lock."""
    try: packages = tomllib.loads(text).get('package') or []
    except tomllib.TOMLDecodeError: return set()
    return {(row['name'], row.get('version'), file['url'].rsplit('/', 1)[-1], file['hash'].removeprefix('sha256:'))
            for row in packages for file in [row.get('sdist') or {}, *(row.get('wheels') or [])]
            if file.get('url') and str(file.get('hash', '')).startswith('sha256:')}


def _checked(added, npm):
    """The added hashes that do not match the registry, or could not be checked against it."""
    said, records = [], {}
    for pair in sorted(added):
        key = _npm_record(pair[0]) if npm else f'https://pypi.org/pypi/{pair[0]}/{pair[1]}/json'
        if not key: continue
        if key not in records: records[key] = _read(key)
        record, what = records[key], pair[0] if npm else pair[2]
        if record is None: said.append(f'the hash of {what} could not be checked against its registry')
        elif (_npm_hash(record) != pair[1]) if npm else (_pypi_sha(record, pair[2]) != pair[3]):
            said.append(f'the hash of {what} is not the one its registry publishes: '
                        'a lock file is written by its own tool, never by hand')
    return said


def _npm_record(url):
    """The registry address of a tarball's version record, or None for a tarball not on a registry."""
    match = TARBALL.match(url)
    return f'{match[1]}/{match[2]}/{match[4]}' if match else None


def _npm_hash(record):
    return (record.get('dist') or {}).get('integrity')


def _pypi_sha(record, filename):
    return next((row['digests']['sha256'] for row in record.get('urls') or [] if row.get('filename') == filename), None)


def _read(url):
    try:
        with opened(url, headers={'Accept': 'application/json'}, timeout=30) as answer: return json.loads(answer.read())
    except (OSError, ValueError): return None
