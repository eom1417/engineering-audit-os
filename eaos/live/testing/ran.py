"""What ran of the project while EAOS ran it (M13.2): its own functions and lines run by its tests, by its server while
the pages were opened, and in the browser, so code reached but never run can be told from code that runs.

Each run leaves one record, <out>/live/ran-<kind>.json (`tests`, `server`, `browser`):
    {'kind', 'files': {path: {'ran': [function names], 'never': [function names]} or {'lines': [[first, last], ...]}}}
read from Node's V8 coverage (functions, their outermost range), Chromium's JS coverage through Playwright (the same
shape, by the address the page loaded) and Coverage.py's data (lines). Only the project's own source files are kept;
the raw coverage is removed once read (what EAOS makes, EAOS removes).

A server is run with coverage on only through what it already has: Node writes V8 coverage on its own when
NODE_V8_COVERAGE is set (a preload makes a SIGTERM end it through process.exit, or Node writes nothing); a Python server
run by its interpreter runs under Coverage.py when that interpreter has it (its data saved on SIGTERM). Any other
server is not measured, and its record says so.
"""
import json
import shutil
import sqlite3
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

import eaos

from ...core.contracts.vocabulary import classify
from ...core.project.workspace import write

PRELOAD = Path(eaos.__path__[0]).resolve() / 'templates/coverage/exit-on-term.cjs'
INTERPRETERS = {'python', 'python3', 'py'}
RC = '.eaos-ran-coveragerc'


def _own(path, root):
    """`path` relative to the project root when it is one of its own source files, else None."""
    name = str(path)
    if name.startswith('file://'): name = name[len('file://'):]
    root = Path(root).resolve().as_posix().rstrip('/') + '/'
    if not name.startswith(root) or '/node_modules/' in name: return None
    relative = name[len(root):].split('?')[0]
    return relative if classify(relative) == 'source' else None


def _functions(scripts, place):
    """{path: {'ran': set, 'never': set}} from V8 script coverage; `place(url)` names a script's file or None."""
    files = {}
    for script in scripts:
        path = place(str(script.get('url') or ''))
        if not path: continue
        row = files.setdefault(path, {'ran': set(), 'never': set()})
        for function in script.get('functions') or []:
            ranges, name = function.get('ranges') or [], function.get('functionName')
            if ranges and name: row['ran' if ranges[0].get('count', 0) > 0 else 'never'].add(name)
    return files


def v8(folder, root):
    """The project's functions in Node's V8 coverage files of `folder` (NODE_V8_COVERAGE)."""
    scripts = []
    for path in sorted(Path(folder).glob('*.json')):
        try: scripts += json.loads(path.read_text(encoding='utf-8')).get('result') or []
        except (OSError, ValueError): continue
    return _functions(scripts, lambda url: _own(url, root))


def browser(entries, root):
    """The project's functions in Chromium's JS coverage: a script whose address names a file of the project (a
    development server serves `/src/App.jsx`, Vite's `/@fs/<path>` too); a bundle names none and is not read."""
    root = Path(root).resolve()

    def place(url):
        path = urlsplit(url).path
        if path.startswith('/@fs/'): return _own(path[len('/@fs'):], root)
        relative = path.lstrip('/')
        return relative if relative and (root / relative).is_file() and classify(relative) == 'source' else None
    return _functions(entries, place)


def _ranges(lines):
    """[[first, last], ...] of a set of line numbers."""
    out = []
    for line in sorted(lines):
        if out and line == out[-1][1] + 1: out[-1][1] = line
        else: out.append([line, line])
    return out


def _numbits(blob):
    """The line numbers a Coverage.py numbits blob holds (bit n of byte b: line 8b + n)."""
    return {index * 8 + bit for index, byte in enumerate(blob) for bit in range(8) if byte & (1 << bit)}


def python_data(files, root):
    """{path: {'lines': ranges}} from Coverage.py data files (`.coverage.*`, SQLite), read without Coverage.py."""
    lines = {}
    for data in files:
        try:
            with sqlite3.connect(f'file:{data}?mode=ro', uri=True) as db:
                names = dict(db.execute('select id, path from file'))
                for file_id, blob in db.execute('select file_id, numbits from line_bits'):
                    path = _own(names.get(file_id, ''), root)
                    if path: lines.setdefault(path, set()).update(_numbits(blob))
        except sqlite3.Error: continue
    return {path: {'lines': _ranges(found)} for path, found in lines.items()}


def python_report(report, prefix=''):
    """{path: {'lines': ranges}} from a Coverage.py JSON report (the tests' `.eaos-coverage.json`)."""
    try: files = json.loads(Path(report).read_text(encoding='utf-8')).get('files') or {}
    except (OSError, ValueError): return {}
    out = {}
    for name, entry in files.items():
        relative = PurePosixPath(prefix, Path(name).as_posix().removeprefix('./')).as_posix()
        if classify(relative) == 'source': out[relative] = {'lines': _ranges(entry.get('executed_lines') or [])}
    return out


def _settled(row):
    """A merged row in its written form: a function that ran anywhere is no longer never run; lines as ranges."""
    if 'ran' in row: row['never'] = sorted(set(row['never']) - set(row['ran'])); row['ran'] = sorted(row['ran'])
    if 'lines' in row: row['lines'] = _ranges({n for first, last in row['lines'] for n in range(first, last + 1)})
    return row


def merged(*parts):
    """One file map from several: a function ran when any part ran it."""
    out = {}
    for part in parts:
        for path, row in part.items():
            into = out.setdefault(path, {})
            for key in ('ran', 'never'): into.setdefault(key, set()).update(row.get(key) or ())
            if 'lines' in row: into['lines'] = into.get('lines', []) + row['lines']
    return {path: _settled(row) for path, row in out.items()}


def record(out, kind, files, reason=''):
    """<out>/live/ran-<kind>.json: what this run ran, or why nothing was measured."""
    (Path(out) / 'live').mkdir(parents=True, exist_ok=True)
    write(Path(out) / 'live' / f'ran-{kind}.json', {'schema_version': 1, 'kind': kind, 'files': merged(files),
                                                     **({'reason': reason} if reason else {})})


def server(argv, env, folder, copy, python=False):
    """(argv, env) of a server started with coverage on, its data in `folder`: Node's V8 coverage always (it costs a
    Node server nothing), Coverage.py when `python` (the server is run by an interpreter that has it)."""
    folder.mkdir(parents=True, exist_ok=True)
    options = ' '.join(filter(None, [env.get('NODE_OPTIONS', ''), f'--require={PRELOAD}']))
    env = {**env, 'NODE_V8_COVERAGE': str(folder / 'v8'), 'NODE_OPTIONS': options}
    if python:
        (Path(copy) / RC).write_text(f'[run]\ndata_file = {folder / ".coverage"}\nparallel = true\nsigterm = true\n', encoding='utf-8')
        argv = [argv[0], '-m', 'coverage', 'run', f'--rcfile={Path(copy) / RC}', *argv[1:]]
    return argv, env


def server_record(out, folder, copy):
    """The server's record from what its run left in `folder`, then the raw data removed."""
    files = merged(v8(Path(folder) / 'v8', copy), python_data(sorted(Path(folder).glob('.coverage*')), copy))
    record(out, 'server', files, '' if files else 'the server wrote no coverage EAOS can read (neither Node nor a Python '
                                                 'with Coverage.py ran the project\'s own code)')
    shutil.rmtree(folder, ignore_errors=True)
