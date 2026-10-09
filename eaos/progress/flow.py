"""The flows after the check, written with the same writer: setting up the app, recording its screens, fixing.

A flow declares its stages as data, the way eaos/pipeline/stages.py declares the check's:

    FLOW = (Stage('detect', description='...'), Stage('attempt', requires=('detect',), description='...'), ...)

and runs inside `with Flow(folder, 'setup', FLOW):`, which writes `<folder>/progress/setup.jsonl` (log.py). The code
that does the work marks where it is with the module functions below, which are no-ops when no flow is running, so
every caller outside a flow (a test, the CLI, the assistant's tools) is unchanged:

    progress.begin('attempt')                  # the stage starts; the one before it, still open, ends ok
    progress.step('attempt 2', 1, 5, 'failed', reason='...', reason_code='...')
    progress.skip('baseline', 'the app has no production build', 'no_build')
    progress.end('attempt', 'failed', reason='...', code='app_not_answering')

Every declared stage gets exactly one end: a stage the code neither ran nor skipped is ended by the flow's end
(log.finish), `failed` if it was running and `not_reached` otherwise, and the run is then INCOMPLETE. A flow stopped
by Ctrl-C ends STOPPED, one broken by an error ends ERROR; the error goes on.
"""
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from . import context
from .fold import fold_file
from .log import ProgressLog

OK, SKIPPED, FAILED, NOT_REACHED = 'ok', 'skipped', 'failed', 'not_reached'
REQUIRED, OPTIONAL = 'required', 'optional'
_flow = ContextVar('eaos_progress_flow', default=None)


@dataclass(frozen=True)
class Stage:
    """One declared stage of a flow: what it needs before it, what it does, and when it may be absent."""
    name: str
    requires: tuple = ()
    description: str = ''
    absent_when: str = ''
    necessity: str = REQUIRED
    produces: tuple = ()


def errors(stages):
    """Structural problems of a flow's declaration; [] when it is sane (the same rules as the check's)."""
    found, seen = [], set()
    for stage in stages:
        if stage.name in seen: found.append(f'{stage.name}: declared twice')
        seen.add(stage.name)
        found += [f'{stage.name}: requires {need}, which no earlier stage provides' for need in stage.requires if need not in seen]
        if stage.necessity == OPTIONAL and not stage.absent_when.strip():
            found.append(f'{stage.name}: optional without saying when it may be absent')
        if not stage.description.strip(): found.append(f'{stage.name}: says nothing about what it does')
    return sorted(found)


def previous_stage_seconds(path):
    """{stage: seconds} of the stages that ended ok in the run the file at `path` holds; {} on a first run."""
    return {s['name']: s['seconds'] for s in fold_file(path)['stages']
            if s.get('state') == OK and isinstance(s.get('seconds'), (int, float))}


def completion(rows, missing=()):
    """The run's status by the check's rule (eaos/pipeline/run.py:completion_status): INCOMPLETE when a stage failed,
    was not reached, or a required one was unavailable; PARTIAL when a required one was skipped; else COMPLETE."""
    rows = list(rows)
    if missing or any(r['status'] in (FAILED, NOT_REACHED) or (r['necessity'] == REQUIRED and r['status'] == 'unavailable')
                      for r in rows):
        return 'INCOMPLETE'
    if any(r['necessity'] == REQUIRED and r['status'] == SKIPPED for r in rows): return 'PARTIAL'
    return 'COMPLETE'


class Flow:
    """One run of a declared flow. Used as a context manager; `begin`, `end`, `skip` mark the stages."""

    def __init__(self, folder, name, stages, requested=None, **options):
        self.name, self.stages = name, tuple(stages)
        self.declared = {stage.name: stage for stage in self.stages}
        self.requested = list(requested) if requested is not None else list(self.declared)
        self.clock = options.get('clock', time.monotonic)
        self.log = ProgressLog(folder, name, **options)
        self.results, self.began = {}, {}
        self.current = None
        self._step_token = self._flow_token = None
        self.started_at = None

    # the run

    def __enter__(self):
        try: previous = previous_stage_seconds(self.log.path)
        except Exception: previous = {}
        self.started_at = self.clock()
        self.log.started(self.stages, self.requested, previous)
        self._flow_token = _flow.set(self)
        for name in self.declared:
            if name not in self.requested: self.skip(name, 'not requested in this run', 'not_requested')
        return self

    def __exit__(self, kind, problem, trace):
        if self._flow_token is not None:
            _flow.reset(self._flow_token)
            self._flow_token = None
        seconds = round(self.clock() - self.started_at, 2)
        if problem is not None:
            self._release()
            status = 'STOPPED' if isinstance(problem, (KeyboardInterrupt, SystemExit)) else 'ERROR'
            self.log.finish(status, reason=f'{type(problem).__name__}: {problem}'[:300], seconds=seconds)
            return False
        if self.current: self.end(self.current)
        missing = [name for name in self.declared if name not in self.results]
        counts = {state: sum(1 for row in self.results.values() if row['status'] == state) + (len(missing) if state == NOT_REACHED else 0)
                  for state in (OK, SKIPPED, 'unavailable', FAILED, NOT_REACHED)}
        status = completion(self.results.values(), missing)
        self.log.finish(status, reason='' if not missing else 'the flow ended before: ' + ', '.join(missing),
                        seconds=seconds, counts=counts)
        return False

    # the stages

    def begin(self, name):
        """`name` starts now; the stage still open before it ends ok. A stage not declared, or already ended, is left."""
        if name not in self.declared or name in self.results or name == self.current: return
        if self.current: self.end(self.current)
        self.log.stage_started(name)
        self.began[name], self.current = self.clock(), name
        self._step_token = context._current.set(self.log.stepper(name) if self.log.enabled else None)

    def end(self, name=None, status=OK, reason='', code='', artifacts=(), detail=None):
        """`name` (default: the running stage) ends with `status`; its seconds are measured from its begin."""
        name = name or self.current
        if name is None or name not in self.declared or name in self.results: return
        if name == self.current: self._release()
        seconds = round(self.clock() - self.began[name], 2) if name in self.began else 0.0
        row = {'stage': name, 'status': status, 'reason': reason, 'seconds': seconds,
               'necessity': self.declared[name].necessity, 'artifacts': sorted(artifacts), 'detail': detail or {}}
        if code: row['reason_code'] = code
        self.results[name] = row
        self.log.ended(row)

    def skip(self, name, reason, code, status=SKIPPED):
        """`name` does not run here, and why: `reason` in EAOS's words, `code` for the person's language."""
        self.end(name, status, reason, code)

    def _release(self):
        if self._step_token is not None:
            context._current.reset(self._step_token)
            self._step_token = None
        self.current = None


def current_flow():
    """The flow running in this context, or None."""
    return _flow.get()


def begin(name):
    """Mark the running flow's stage `name` as started; a no-op outside a flow or for a stage it does not declare."""
    flow = _flow.get()
    if flow is not None: _safely(flow.begin, name)


def end(name=None, status=OK, reason='', code='', artifacts=(), detail=None):
    flow = _flow.get()
    if flow is not None: _safely(flow.end, name, status, reason, code, artifacts, detail)


def skip(name, reason, code, status=SKIPPED):
    flow = _flow.get()
    if flow is not None: _safely(flow.skip, name, reason, code, status)


@contextmanager
def stage(name, code='stage_error'):
    """The block is the stage `name`: begun on entry, ended ok on exit, or failed with the error, which goes on."""
    begin(name)
    try:
        yield
    except Exception as problem:
        end(name, FAILED, f'{type(problem).__name__}: {problem}'[:300], code)
        raise
    end(name)


def _safely(call, *args):
    try: call(*args)
    except Exception:                                   # marking where a flow is must not change what it does
        pass
