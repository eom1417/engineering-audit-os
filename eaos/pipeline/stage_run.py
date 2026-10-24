"""One stage of a check run (eaos/pipeline/run.py runs them all): whether it runs here or why not (resumed, not
requested, blocked by a prerequisite), its runner called under its own progress step, and its row of the manifest. What
a stage ends with is written under the run's lock, with the checkpoint a run stopped midway resumes from."""
import json
import time
from contextvars import ContextVar

from ..core.progress import using
from .live_app import PAGE_STAGES, close_app
from .stages import BY_NAME, SkipStage, dependents

OK, SKIPPED, UNAVAILABLE, FAILED, NOT_REACHED = 'ok', 'skipped', 'unavailable', 'failed', 'not_reached'
CHECKPOINT = 'run-checkpoint.json'


_STEP = ContextVar('eaos_stage_step', default=None)


class Context(dict):
    """What stages hand each other. Plain data, so a resumed run can rebuild it. `step` is the running stage's own
    stepper, whatever runs beside it."""

    def __getattr__(self, name):
        if name == 'step': return _STEP.get()
        try:
            return self[name]
        except KeyError as missing:
            raise AttributeError(name) from missing


def _settled(stage, run):
    """(row, resumed) of a stage that does not run here: resumed, not requested, or blocked; None when it runs."""
    if stage.name in run['completed']: return run['completed'][stage.name], True
    if stage.name not in run['requested']:
        if run['head']['paths'] != ['complete']: return _row(stage, SKIPPED, "outside this check's paths", code='outside_paths'), False
        return _row(stage, SKIPPED, 'not requested in this run', code='not_requested'), False
    unmet = [name for name in stage.requires if not _satisfied(name, run['results'], run['out'])]
    if unmet: run['blocked'].setdefault(stage.name, ('Prerequisites not completed: ' + ', '.join(unmet), 'prerequisites_missing'))
    if stage.name not in run['blocked']: return None
    reason, code = run['blocked'][stage.name]
    return _row(stage, NOT_REACHED, reason, code=code), False


def _stage(stage, run):
    with run['lock']: settled = _settled(stage, run)
    if settled is None:
        _run_stage(stage, run)
        return
    row, resumed = settled
    with run['lock']:
        run['results'][stage.name] = row
        run['log'].ended(row, **({'resumed': True} if resumed else {}))
        if PAGE_STAGES <= run['results'].keys(): close_app(run['context'])


def _run_stage(stage, run):
    """One stage, run while others may run beside it; what it ends with is written under the run's lock."""
    context, log, results = run['context'], run['log'], run['results']
    with run['lock']:
        if run['progress']: run['progress'](sum(name in results for name in run['todo']), len(run['todo']), stage.name)
        log.stage_started(stage.name)
    step = log.stepper(stage.name)
    token = _STEP.set(step)
    try:
        with using(step if log.enabled else None): row = _one(stage, context, run['runners'], results)
    finally: _STEP.reset(token)
    with run['lock']:
        results[stage.name] = row
        log.ended(row)
        _write(run['out'] / CHECKPOINT, {**run['head'], 'stages': results})
        _block_dependents(stage, results, run['blocked'])
        if PAGE_STAGES <= results.keys(): close_app(context)


def _block_dependents(stage, results, blocked):
    status = results[stage.name]['status']
    if status not in (FAILED, UNAVAILABLE, SKIPPED, NOT_REACHED) or _absent(stage.name, results): return
    reason = f"{stage.name} did not produce its artifacts ({status})"
    for name in dependents(stage.name):
        blocked.setdefault(name, (reason, 'prerequisite_failed'))


def _write(path, record):
    path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding='utf-8')


def _absent(name, results):
    """An optional stage that did not apply here (no assistant, no engine) and said why: the stages after it run without
    its output. Only a failure of it, or a stage it could not reach, holds them back."""
    stage = BY_NAME.get(name)
    return bool(stage) and stage.necessity == 'optional' and results.get(name, {}).get('status') in (UNAVAILABLE, SKIPPED)


def _satisfied(name, results, out):
    """A prerequisite is met when it ran here, when an earlier run already left its artifacts, or when it is optional
    and absent here with its reason.

    Requiring it to run in this run made --only unusable: re-rendering one stage over a finished
    report reported "prerequisites not completed" while every input sat on disk beside it.
    """
    if results.get(name, {}).get('status') == OK or _absent(name, results):
        return True
    stage = BY_NAME.get(name)
    return bool(stage) and bool(stage.produces) and all((out / artifact).exists() for artifact in stage.produces)


def _row(stage, status, reason, seconds=0.0, artifacts=(), detail=None, code=''):
    """One stage's row of the manifest. `code` is the stable word for the reason (`reason_code`), present only when
    the stage has a reason: the Studio shows its text from eaos/data/errors.json in the person's language."""
    row = {'stage': stage.name, 'status': status, 'reason': reason, 'seconds': round(seconds, 2),
           'necessity': stage.necessity, 'produces': list(stage.produces),
           'artifacts': sorted(artifacts), 'detail': detail or {}}
    if code: row['reason_code'] = code
    return row


def _one(stage, context, runners, results):
    runner = runners.get(stage.name)
    if runner is None:
        return _row(stage, FAILED, 'no runner is registered for this stage', code='no_runner')
    began = time.monotonic()
    try:
        outcome = runner(context) or {}
    except SkipStage as reason:
        # an assistant lost midway leaves the stage absent like any optional one (the stages after it still run), but
        # says so: the check is then PARTIAL, never COMPLETE, and the Studio offers to run the lost stages again
        lost = {'assistant_lost': reason.lost} if reason.lost else None
        return _row(stage, UNAVAILABLE, str(reason), time.monotonic() - began, detail=lost, code=reason.code or 'not_applicable')
    except Exception as problem:                       # one stage must not decide the fate of the rest
        return _row(stage, FAILED, f'{type(problem).__name__}: {problem}'[:300], time.monotonic() - began, code='stage_error')
    return _ended(stage, context, outcome, time.monotonic() - began)


def _ended(stage, context, outcome, seconds):
    """The row of a stage whose runner returned `outcome`: failed when a declared artifact is missing, else ok, saying
    what its tools or its assistant left undone."""
    present = [name for name in stage.produces if (context.out / name).exists()]
    missing = [name for name in stage.produces if name not in present]
    if missing:
        return _row(stage, FAILED, 'declared artifacts were not written: ' + ', '.join(missing),
                    seconds, present, outcome, code='artifacts_missing')
    failed = outcome.get('tools_failed')
    if failed: return _row(stage, OK, 'these tools failed: ' + ', '.join(sorted(failed)), seconds, present, outcome, code='tools_failed')
    if outcome.get('assistant_lost'):   # its assistant answered part of it (ai_runners._partly): the check is PARTIAL
        return _row(stage, OK, outcome['assistant_lost']['why'], seconds, present, outcome, code='ai_partial')
    return _row(stage, OK, '', seconds, present, outcome)
