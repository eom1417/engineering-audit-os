"""The last runs of each flow, kept whole so a finished (or killed) run can be read and replayed later.

log.py copies a run into `<folder>/progress/history/<flow>/<run>.jsonl` when it ends, and copies the file a new run
replaces before it is replaced; at most HISTORY_KEEP runs are kept per flow, the newest by run id (which begins with
its start time). `runs()` lists them, newest first, each with what its fold says.
"""
from .fold import fold_file
from .log import HISTORY_KEEP, history_folder

__all__ = ['HISTORY_KEEP', 'runs', 'path_of']


def runs(folder, flow='check'):
    """[{run, path, state, status, started_at, ended_at, seconds}] of the kept runs of `flow`, newest first."""
    out = []
    for path in sorted(history_folder(folder, flow).glob('*.jsonl'), reverse=True):
        state = fold_file(path)
        out.append({'run': path.stem, 'path': str(path), 'state': state['state'], 'status': state['status'],
                    'started_at': state['started_at'], 'ended_at': state['ended_at'], 'seconds': state['seconds']})
    return out


def path_of(folder, flow, run):
    """The kept file of one run, or None (a run id is a file name: nothing else is accepted)."""
    name = str(run)
    if not name or '/' in name or '\\' in name or name.startswith('.'): return None
    path = history_folder(folder, flow) / f'{name}.jsonl'
    return path if path.is_file() else None
