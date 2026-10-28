"""The data the server keeps on disk (M14.3): the files of the copy written while the app ran, outside what it built,
installed or logged; beside a database, the data is kept in two places.

    written(copy, since, database=None)   [{path, bytes}]
"""
from pathlib import Path

SKIPPED = {'node_modules', '.git', '.venv', 'venv', '__pycache__', '.next', '.nuxt', '.svelte-kit', 'dist', 'build',
           '.cache', 'coverage', '.turbo', '.parcel-cache', '.vite', 'logs', 'tmp', '.expo'}
DATA = {'.json', '.jsonl', '.ndjson', '.csv', '.tsv', '.xml', '.yaml', '.yml', '.txt', '.dat', '.png', '.jpg', '.jpeg',
        '.webp', '.gif', '.pdf', '.bin'}
OWN = ('.eaos', 'package-lock.json', 'tsconfig.tsbuildinfo')       # what EAOS or the tools write while they run
LISTED = 20


def written(copy, since, database=None):
    """The data files the run wrote into the copy after `since` (a time), the run's own database file left out."""
    copy = Path(copy)
    found = [p for p in sorted(copy.rglob('*')) if _data(p, p.relative_to(copy), database)]
    return [{'path': p.relative_to(copy).as_posix(), 'bytes': p.stat().st_size} for p in found if p.stat().st_mtime >= since][:LISTED]


def _data(path, rel, database):
    """Whether a file of the copy can hold the app's data: a data kind, outside what it installs or builds and what
    EAOS writes, not the run's database itself."""
    if SKIPPED & set(rel.parts[:-1]) or path.suffix.lower() not in DATA or any(part.startswith(OWN) for part in rel.parts): return False
    return path.is_file() and not path.is_symlink() and not (database and path == Path(database))
