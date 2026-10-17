"""Execute the declared pipeline and record, for every stage, what happened and what did not.

A stage that fails does not silently take the run with it: its dependents are recorded as skipped
with the reason, the independent stages still run, and the manifest is the honest account of the
whole attempt. A stage that never ran leaves a reason, never a gap.
"""
import json
import threading
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

from ..progress import ProgressLog, previous_seconds, using
from ..usage import FILE as USAGE
from .live_app import PAGE_STAGES, close_app
from .paths import resolve
from .schedule import LimitedProvider, assistants, run_ready
from .stages import BY_NAME, ORDER, STAGES, SkipStage, dependents

OK, SKIPPED, UNAVAILABLE, FAILED, NOT_REACHED = 'ok', 'skipped', 'unavailable', 'failed', 'not_reached'
MANIFEST = 'run-manifest.json'
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


def _runners():
    """Imported lazily: a pipeline declaration must be readable without importing the whole product."""
    from . import runners
    return runners.RUNNERS


def execute(target, out, *, only=(), skip=(), language='ar', exclude=(), engines=None, provider=None,
            goal=None, audit_run=None, runners=None, intake=None,
            max_files=100000, max_bytes=2_000_000, policy_path=None, _completed=None, progress=None, without_tools=(),
            runtime=None, mode='normal', paths=None, patterns=None):
    """`progress(done, total, stage)` is called before each stage that will run, so a person waiting sees where
    the run is; it never changes what runs. `without_tools`: the tools whose install failed and the person started
    without; the manifest records them (`options`). `runtime`: the folder the app is run in, an isolated copy, given only
    once the person agreed to run it; without it every live stage says so. `mode`: how many stages and assistants run at
    once (eaos/pipeline/schedule.py: normal, speed, one). `paths`: the check's paths (eaos/pipeline/paths.py), recorded;
    `patterns`: the card patterns the plan keeps, None for all.

    Every event of the run is also appended to `<out>/run-progress.jsonl` (eaos/progress/log.py): the run's start
    with the declared stages, each stage's start, its steps, its end with its status, reason, seconds and artifacts,
    and the run's end. Every stage gets exactly one end, so the folded file equals the manifest when the run is over;
    a run stopped or broken midway ends the stage it was in and every stage it did not reach before it says so.
    While a stage runs it is the current stage of eaos/progress/context.py, so `progress.count()` anywhere below it
    reports into it."""
    target, out = _outside(target, out)
    if isinstance(getattr(provider, 'config', None), dict): provider.config['usage'] = str(out / USAGE)    # eaos/usage.py
    runners = runners if runners is not None else _runners()
    _refuse_unknown(only, skip)
    context = Context(target=target, out=out, language=language, exclude=list(exclude), engines=engines,
                      provider=provider, goal=goal,
                      audit_run=audit_run, max_files=max_files, max_bytes=max_bytes, policy_path=policy_path,
                      intake=_resolved(intake), runtime=str(runtime) if runtime else None, assistants=assistants(mode),
                      patterns=patterns)
    if provider: context['provider'] = LimitedProvider(provider, context.assistants)
    requested = _requested(only, skip)
    completed = _completed or {}
    context['again'] = bool(completed)          # within a check run before: a tool run again joins the others' results
    started_at = datetime.now(timezone.utc).isoformat(timespec='seconds')
    began = time.monotonic()
    todo = [stage.name for stage in STAGES if stage.name in requested and stage.name not in completed]
    head = _head(target, out, started_at, requested, language, exclude, max_files, max_bytes, policy_path, intake)
    head['options']['without_tools'] = sorted(without_tools)
    head.update(mode=mode, paths=paths or ['complete'])     # not options: a check goes on in another mode or path
    log = ProgressLog(out)
    log.started(STAGES, requested, previous_seconds(out), mode=mode)
    run = {'completed': completed, 'requested': requested, 'results': {}, 'blocked': {}, 'log': log, 'context': context,
           'runners': runners, 'progress': progress, 'todo': todo, 'out': out, 'began': began, 'head': head,
           'lock': threading.RLock()}
    # What a stage reads of the run: the stages ended so far. It only asks of those it waits for, so it reads them
    # ended whatever else runs beside it (tests/test_pipeline_parallel.py).
    context['manifest_so_far'] = {'stages': run['results'], 'status': 'RUNNING'}
    try:
        run_ready(ORDER, lambda name: _stage(BY_NAME[name], run), mode, quick=set(ORDER) - set(todo))
        manifest = _manifest(head, began, run['results'])
        (out / CHECKPOINT).unlink(missing_ok=True)
    except BaseException as problem:                    # stopped or broken: the file says so, then the error goes on
        log.finish('STOPPED' if isinstance(problem, KeyboardInterrupt) else 'ERROR',
                   reason=f'{type(problem).__name__}: {problem}'[:300], seconds=round(time.monotonic() - began, 2))
        raise
    finally:
        close_app(context)
    log.finish(manifest['status'], seconds=manifest['seconds'], counts=manifest['counts'])
    return manifest


def _outside(target, out):
    target, out = Path(target).resolve(), Path(out).resolve()
    if out == target or target in out.parents:
        raise ValueError('Pipeline output must live outside the target; the target stays read-only')
    out.mkdir(parents=True, exist_ok=True)
    return target, out


def _refuse_unknown(only, skip):
    unknown = sorted((set(only) | set(skip)) - set(ORDER))
    if unknown:
        raise ValueError('Unknown stage: ' + ', '.join(unknown))


def _resolved(intake): return str(Path(intake).resolve()) if intake else None


def _requested(only, skip):
    wanted, skipped = set(only), set(skip)
    return [name for name in ORDER if (not only or name in wanted) and name not in skipped]


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


def _head(target, out, started_at, requested, language, exclude, max_files, max_bytes, policy_path, intake):
    """What the manifest says of the run whatever its stages do; with the stages so far it is also the checkpoint
    written after each stage, which a run stopped or killed midway is resumed from."""
    from ..workspace import inventory
    return {'contract_version': 1, 'target': str(target), 'out': str(out), 'started_at': started_at,
            'requested': requested,
            'options': {'language': language, 'exclude': list(exclude), 'max_files': max_files, 'max_bytes': max_bytes,
                        'policy_path': str(policy_path) if policy_path else None,
                        'intake': str(Path(intake).resolve()) if intake else None},
            'source_fingerprint': inventory(target, max_files=max_files, max_bytes=max_bytes)['fingerprint']}


def _manifest(head, began, results):
    manifest = {
        **{key: head[key] for key in ('contract_version', 'target', 'out', 'started_at', 'mode', 'paths') if key in head},
        'seconds': round(time.monotonic() - began, 2), 'requested': head['requested'],
        'stages': results,
        'counts': {state: sum(1 for row in results.values() if row['status'] == state)
                   for state in (OK, SKIPPED, UNAVAILABLE, FAILED, NOT_REACHED)},
        'status': completion_status(results),
        'limits': 'A stage that did not run proves nothing. Read the skipped and unavailable rows before '
                  'reading the findings: they are the shape of what this run could not see.',
        'options': head['options'], 'source_fingerprint': head['source_fingerprint'],
    }
    _write(Path(head['out']) / MANIFEST, manifest)
    return manifest


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


def completion_status(results):
    if any(row['status'] in {FAILED, NOT_REACHED} or
           (row['necessity'] == 'required' and row['status'] == UNAVAILABLE) for row in results.values()):
        return 'INCOMPLETE'
    if any((row['necessity'] == 'required' and row['status'] == SKIPPED) or row.get('reason_code') == 'tools_failed'
           for row in results.values()):
        return 'PARTIAL'
    return 'COMPLETE'


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
        return _row(stage, UNAVAILABLE, str(reason), time.monotonic() - began, code=reason.code or 'not_applicable')
    except Exception as problem:                       # one stage must not decide the fate of the rest
        return _row(stage, FAILED, f'{type(problem).__name__}: {problem}'[:300], time.monotonic() - began, code='stage_error')
    seconds = time.monotonic() - began
    present = [name for name in stage.produces if (context.out / name).exists()]
    missing = [name for name in stage.produces if name not in present]
    if missing:
        return _row(stage, FAILED, 'declared artifacts were not written: ' + ', '.join(missing),
                    seconds, present, outcome, code='artifacts_missing')
    failed = outcome.get('tools_failed')
    if failed: return _row(stage, OK, 'these tools failed: ' + ', '.join(sorted(failed)), seconds, present, outcome, code='tools_failed')
    return _row(stage, OK, '', seconds, present, outcome)


def _previous(out):
    """The record a resume starts from: the checkpoint of a run stopped midway, else the last manifest; None."""
    for name in (CHECKPOINT, MANIFEST):
        if (Path(out) / name).is_file(): return json.loads((Path(out) / name).read_text(encoding='utf-8'))
    return None


# A new complete check replaces these of the previous one: its pictures and crawl, the engines' working folders and
# the assistant's raw runs and cached decisions (the cache keys on the prompt, which names a picture, not what it shows).
# The ledger, the history and the state stay. 230 MB of pictures and 130 MB of runs piled up on EAOS's own report, and
# the ideal plan's raw runs another 40 MB (its record of them, ideal/runs.json, stays).
# START-HERE.md too: kept, a check that never reached its reports showed the counts of the one before.
BULKY = ('live/screens', 'live/screens.json', 'live/crawl', 'live/crawl.json', 'nodes/*/runs', 'nodes/*/cache', 'ideal/run-*',
         'START-HERE.md')
PICTURES = ('live/screens', 'live/crawl', 'nodes/*/runs', 'ideal/run-*')     # what `eaos clean --pictures` removes from every report


def bulky(out, patterns=None):
    """The paths of report `out` that match `patterns`, by default the previous check's bulky data (BULKY and the
    engines' scratch)."""
    from ..facts.external import SCRATCH
    out = Path(out)
    patterns = patterns or (*BULKY, *(f'engines/{part}' for part in SCRATCH))
    return sorted({path for pattern in patterns for path in out.glob(pattern)})


def clear(out, patterns=None):
    """Remove from report `out` what `patterns` match (bulky); the bytes freed."""
    import shutil
    freed = 0
    for path in bulky(out, patterns):
        if path.is_dir() and not path.is_symlink():
            freed += sum(f.stat().st_size for f in path.rglob('*') if f.is_file() and not f.is_symlink())
            shutil.rmtree(path, ignore_errors=True)
        else:
            freed += path.stat().st_size if path.is_file() else 0
            path.unlink(missing_ok=True)
    return freed


def check(target, out, again_from=None, checked=False, paths=None, **options):
    """A check the person asked for: a run that did not end (stopped, broken or killed midway: its checkpoint is there)
    goes on from that checkpoint; otherwise, or when the source changed since, a fresh full run, which first clears
    the previous check's bulky data (clear) unless it runs some stages only. `again_from`: the last check goes on from
    that stage (again). `paths`: the check follows those paths only (focused)."""
    if again_from: return again(target, out, again_from, checked=checked, **options)
    if (Path(out) / CHECKPOINT).is_file():
        try: return resume(target, out, **options)
        except ValueError: pass                         # the source or the options changed since: its evidence is stale
    chosen = resolve(paths)
    if chosen['stages'] is not None: return focused(target, out, chosen, checked, **options)
    if not options.get('only'): clear(out)
    (Path(out) / USAGE).unlink(missing_ok=True)        # a fresh run counts its own use from nothing
    return execute(target, out, **options)


def focused(target, out, chosen, checked=False, **options):
    """A check of some paths only (paths.resolve's `chosen`): on the code the last check read, only their stages run
    again and the rest of that check stays, each stage saying when it ran; on other code, or with no check before,
    only their stages run and their plan keeps only their cards. Nothing of the last check is cleared."""
    options.update(paths=chosen['paths'], engines=chosen['engines'] if 'engines' in chosen['stages'] else None)
    if _previous(out) is not None:
        try: return resume(target, out, redo=chosen['stages'], checked=checked, only=chosen['stages'], **options)
        except ValueError: pass                         # other code: none of the last check's evidence holds
    (Path(out) / USAGE).unlink(missing_ok=True)
    return execute(target, out, only=chosen['stages'], patterns=chosen['patterns'], **options)


def again(target, out, stage, checked=False, **options):
    """The last check with `stage` and every stage that reads what it makes run again (a tool that failed, a step to
    redo), the rest kept as it was: never a whole new check for one stage. `engines` names the tools to run again.
    `checked`: `target` is the very commit the check read clean (eaos/guided.py source), so the same code whatever
    caches lay beside it then (.cache, egg-info), and the files' fingerprint is not asked."""
    if stage not in BY_NAME: raise ValueError(f'there is no stage named {stage}')
    if _previous(out) is None: raise ValueError('there is no check to go on from: run a check first')
    return resume(target, out, redo=(stage, *dependents(stage, reading=True)), checked=checked, **options)


def resume(target, out, redo=(), checked=False, **options):
    """Re-run only what a previous attempt did not complete: a run stopped or killed midway from the checkpoint it
    left after its last stage, else the last manifest; and the stages in `redo` (again)."""
    previous = _previous(out)
    if previous is None:
        return execute(target, out, **options)
    _merge_options(previous.get('options', {}) if checked else _resumable(target, previous), options)
    done = _done_stages(previous, out) - set(redo)
    wanted = options.pop('only', None)
    remaining = [name for name in ORDER if name not in done and (not wanted or name in wanted)]
    if not remaining:
        return previous
    kept = {name: {**previous['stages'][name], 'checked_at': previous['stages'][name].get('checked_at') or previous['started_at']}
            for name in done}
    merged = execute(target, out, only=remaining, _completed=kept, **options)
    merged['stages'].update(kept)
    merged['counts'] = {state: sum(1 for row in merged['stages'].values() if row['status'] == state)
                        for state in (OK, SKIPPED, UNAVAILABLE, FAILED, NOT_REACHED)}
    merged['resumed_from'] = previous['started_at']
    _write(Path(out) / MANIFEST, merged)
    return merged


def _resumable(target, previous):
    """The previous run's options, once it is shown to be about this source: the same files, wherever the copy is."""
    from ..workspace import inventory
    stored = previous.get('options', {})
    fingerprint = inventory(target, max_files=stored.get('max_files', 100000), max_bytes=stored.get('max_bytes', 2_000_000))['fingerprint']
    if fingerprint != previous.get('source_fingerprint'):
        raise ValueError('Source changed; start a fresh run instead of resuming stale evidence')
    return stored


def _merge_options(stored, options):
    for key, value in stored.items():
        if key in options and options[key] != value: raise ValueError('Resume option changed: ' + key)
        options.setdefault(key, value)


def _done_stages(previous, out):
    return {name for name, row in previous['stages'].items() if row['status'] == OK
            and all((Path(out) / artifact).exists() for artifact in row['produces'])}
