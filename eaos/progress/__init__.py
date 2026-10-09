"""Progress of every long piece of work EAOS does, written as it happens and read the same way by every reader.

- log.py: the writer (`ProgressLog`), one JSON line per event in a flow's progress file;
- context.py: `count()` and `step()`, which code deep inside a stage calls to say where it is (no-ops outside a run);
- sampler.py: which external programs the run has started right now;
- liveness.py: `run.alive` and how a reader tells a quiet run from a dead one (`stalled`, `interrupted`);
- fold.py: the single Python fold of the lines into one state per flow;
- flow.py: the flows after the check (set up, record the screens, fix): `Flow`, and `begin`/`end`/`skip`/`stage`,
  which the code doing the work calls to say which declared stage it is in (no-ops outside a flow);
- estimate.py: time left as a range, from the last run's seconds only;
- history.py: the last runs of each flow, kept whole;
- reasons.py: the person's words for each `reason_code` (eaos/data/errors.json -> reasons).

The events are declared in eaos/data/schemas/progress.json.
"""
from .context import count, current, step, using
from .estimate import estimate
from .flow import Flow, Stage, begin, current_flow, end, skip, stage
from .fold import ENDED, RUNNING, WAITING, apply, empty, fold, fold_file, read
from .liveness import ALIVE_EVERY, STALLED_AFTER, alive, heard_at, judge
from .log import (HISTORY_KEEP, PROGRESS, SCHEMA, ProgressLog, history_folder, now, path_for, previous_seconds,
                  previous_steps, stage_rows)
from .reasons import reason_text

__all__ = ['ALIVE_EVERY', 'ENDED', 'HISTORY_KEEP', 'PROGRESS', 'RUNNING', 'SCHEMA', 'STALLED_AFTER', 'WAITING', 'Flow',
           'ProgressLog', 'Stage', 'alive', 'apply', 'begin', 'count', 'current', 'current_flow', 'empty', 'end',
           'estimate', 'fold', 'fold_file', 'heard_at', 'history_folder', 'judge', 'now', 'path_for',
           'previous_seconds', 'previous_steps', 'read', 'reason_text', 'skip', 'stage', 'stage_rows', 'step', 'using']
