"""Progress of every long piece of work EAOS does, written as it happens and read the same way by every reader.

- log.py: the writer (`ProgressLog`), one JSON line per event in a flow's progress file;
- context.py: `count()` and `step()`, which code deep inside a stage calls to say where it is (no-ops outside a run);
- sampler.py: which external programs the run has started right now;
- liveness.py: `run.alive` and how a reader tells a quiet run from a dead one (`stalled`, `interrupted`);
- fold.py: the single Python fold of the lines into one state per flow.

The events are declared in eaos/data/schemas/progress.json.
"""
from .context import count, current, step, using
from .fold import ENDED, RUNNING, WAITING, apply, empty, fold, fold_file, read
from .liveness import ALIVE_EVERY, STALLED_AFTER, alive, heard_at, judge
from .log import PROGRESS, SCHEMA, ProgressLog, now, path_for, previous_seconds, previous_steps, stage_rows

__all__ = ['ALIVE_EVERY', 'ENDED', 'PROGRESS', 'RUNNING', 'SCHEMA', 'STALLED_AFTER', 'WAITING', 'ProgressLog', 'alive',
           'apply', 'count', 'current', 'empty', 'fold', 'fold_file', 'heard_at', 'judge', 'now', 'path_for',
           'previous_seconds', 'previous_steps', 'read', 'stage_rows', 'step', 'using']
