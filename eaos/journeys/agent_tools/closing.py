"""Closing a batch while nothing is using it: under the lock jobs start by, then the state's, the lock order everywhere
(jobs first), so no job loses its copy and no write of the lanes comes back over a closing."""
from pathlib import Path

from .. import guided
from ..fix import lanes
from ..guided import copies
from ...core.project import jobs
from .project import busy_answer, state_of


def _open(state):
    wave = state.get('open_wave')
    if not wave: raise LookupError('no batch is open: call fix_start first')
    return wave


def _settled(project):
    """(why nothing may start, the state brought up to git with a batch that no longer fits closed): under the jobs'
    lock, let go before the job starts, as its own start takes it. A helper closes nothing, and a running job owns
    what is here."""
    state = state_of(project)
    if stop := lanes.not_yours(state): return stop, state
    try:
        with jobs.alone(state['project']):
            if stop := lanes.not_yours(state_of(project)): return stop, state
            guided.reconcile(state)
            guided.retire_stale_batch(state)
    except jobs.Busy as busy:
        return busy_answer(busy.record), state
    return None, state


def fix_abandon(project=None):
    """Close the open batch without handing anything over: its copy is removed and its cards can be picked again."""
    where = state_of(project)['project']
    try:
        with jobs.alone(where):         # at once: what a job is using never goes, and an assistant is not kept waiting
            state = state_of(project)
            if stop := lanes.not_yours(state): return stop
            _open(state)
            if copies.queued(Path(state['workspace'])): return _a_run_is_queued()
            wave = _open(state)
            guided.close_batch(state, 'abandoned', wave.get('last_error') or '')
    except jobs.Busy as busy:
        return busy_answer(busy.record)
    return {'status': 'abandoned', 'batch': wave['number'], 'cards': wave['cards'],
            'what_now': 'Tell the person the batch was closed and nothing in their project changed.'}


def _a_run_is_queued():
    return {'status': 'busy', 'error': 'a run is queued for this project, or a run\'s record does not read, so nothing was done',
            'what_now': 'Let the queued run end, or stop it in the Studio, then ask again.'}
