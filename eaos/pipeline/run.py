"""Execute the declared pipeline and record, for every stage, what happened and what did not.

A stage that fails does not silently take the run with it: its dependents are recorded as skipped
with the reason, the independent stages still run, and the manifest is the honest account of the
whole attempt. A stage that never ran leaves a reason, never a gap.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from ..progress import ProgressLog, previous_seconds, using
from .stages import BY_NAME, ORDER, STAGES, SkipStage, dependents

OK, SKIPPED, UNAVAILABLE, FAILED, NOT_REACHED = 'ok', 'skipped', 'unavailable', 'failed', 'not_reached'
MANIFEST = 'run-manifest.json'
CHECKPOINT = 'run-checkpoint.json'


class Context(dict):
    """What stages hand each other. Plain data, so a resumed run can rebuild it."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as missing:
            raise AttributeError(name) from missing


def _runners():
    """Imported lazily: a pipeline declaration must be readable without importing the whole product."""
    from . import runners
    return runners.RUNNERS


def execute(target, out, *, only=(), skip=(), language='ar', exclude=(), engines=None, provider=None,
            test_command=None, site=True, goal=None, audit_run=None, runners=None, intake=None,
            max_files=100000, max_bytes=2_000_000, policy_path=None, _completed=None, progress=None):
    """`progress(done, total, stage)` is called before each stage that will run, so a person waiting sees where
    the run is; it never changes what runs.

    Every event of the run is also appended to `<out>/run-progress.jsonl` (eaos/progress/log.py): the run's start
    with the declared stages, each stage's start, its steps, its end with its status, reason, seconds and artifacts,
    and the run's end. Every stage gets exactly one end, so the folded file equals the manifest when the run is over;
    a run stopped or broken midway ends the stage it was in and every stage it did not reach before it says so.
    While a stage runs it is the current stage of eaos/progress/context.py, so `progress.count()` anywhere below it
    reports into it."""
    target, out = Path(target).resolve(), Path(out).resolve()
    if out == target or target in out.parents:
        raise ValueError('Pipeline output must live outside the target; the target stays read-only')
    out.mkdir(parents=True, exist_ok=True)
    runners = runners if runners is not None else _runners()
    unknown = sorted((set(only) | set(skip)) - set(ORDER))
    if unknown:
        raise ValueError('Unknown stage: ' + ', '.join(unknown))
    context = Context(target=target, out=out, language=language, exclude=list(exclude), engines=engines,
                      provider=provider, test_command=test_command, site=site, goal=goal,
                      audit_run=audit_run, max_files=max_files, max_bytes=max_bytes, policy_path=policy_path,
                      intake=str(Path(intake).resolve()) if intake else None)
    requested = [name for name in ORDER if (not only or name in set(only)) and name not in set(skip)]
    results, blocked = {}, {}
    completed = _completed or {}
    started_at = datetime.now(timezone.utc).isoformat(timespec='seconds')
    began = time.monotonic()
    todo = [stage.name for stage in STAGES if stage.name in requested and stage.name not in completed]
    head = _head(target, out, started_at, requested, language, exclude, max_files, max_bytes, policy_path, intake)
    log = ProgressLog(out)
    log.started(STAGES, requested, previous_seconds(out))
    try:
        for stage in STAGES:
            if stage.name in completed:
                results[stage.name] = completed[stage.name]
                log.ended(results[stage.name], resumed=True)
                continue
            if stage.name not in requested:
                results[stage.name] = _row(stage, SKIPPED, 'not requested in this run', code='not_requested')
                log.ended(results[stage.name])
                continue
            unmet = [name for name in stage.requires if not _satisfied(name, results, out)]
            if unmet: blocked.setdefault(stage.name, ('Prerequisites not completed: ' + ', '.join(unmet), 'prerequisites_missing'))
            if stage.name in blocked:
                reason, code = blocked[stage.name]
                results[stage.name] = _row(stage, NOT_REACHED, reason, code=code)
                log.ended(results[stage.name])
                continue
            if progress: progress(todo.index(stage.name), len(todo), stage.name)
            context['manifest_so_far'] = {'stages': dict(results), 'seconds': round(time.monotonic() - began, 2),
                                          'status': 'RUNNING'}
            log.stage_started(stage.name)
            context['step'] = log.stepper(stage.name)
            with using(context['step'] if log.enabled else None):
                results[stage.name] = _one(stage, context, runners, results)
            context.pop('step', None)
            log.ended(results[stage.name])
            _write(out / CHECKPOINT, {**head, 'stages': results})
            if results[stage.name]['status'] in (FAILED, UNAVAILABLE, SKIPPED, NOT_REACHED):
                reason = f"{stage.name} did not produce its artifacts ({results[stage.name]['status']})"
                for name in dependents(stage.name):
                    blocked.setdefault(name, (reason, 'prerequisite_failed'))
        manifest = _manifest(head, began, results)
        (out / CHECKPOINT).unlink(missing_ok=True)
    except BaseException as problem:                    # stopped or broken: the file says so, then the error goes on
        log.finish('STOPPED' if isinstance(problem, KeyboardInterrupt) else 'ERROR',
                   reason=f'{type(problem).__name__}: {problem}'[:300], seconds=round(time.monotonic() - began, 2))
        raise
    log.finish(manifest['status'], seconds=manifest['seconds'], counts=manifest['counts'])
    return manifest


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
        **{key: head[key] for key in ('contract_version', 'target', 'out', 'started_at')},
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


def _satisfied(name, results, out):
    """A prerequisite is met when it ran here, or when an earlier run already left its artifacts.

    Requiring it to run in this run made --only unusable: re-rendering one stage over a finished
    report reported "prerequisites not completed" while every input sat on disk beside it.
    """
    if results.get(name, {}).get('status') == OK:
        return True
    stage = BY_NAME.get(name)
    return bool(stage) and bool(stage.produces) and all((out / artifact).exists() for artifact in stage.produces)


def completion_status(results):
    if any(row['status'] in {FAILED, NOT_REACHED} or
           (row['necessity'] == 'required' and row['status'] == UNAVAILABLE) for row in results.values()):
        return 'INCOMPLETE'
    if any(row['necessity'] == 'required' and row['status'] == SKIPPED for row in results.values()):
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
    return _row(stage, OK, '', seconds, present, outcome)


def _previous(out):
    """The record a resume starts from: the checkpoint of a run stopped midway, else the last manifest; None."""
    for name in (CHECKPOINT, MANIFEST):
        if (Path(out) / name).is_file(): return json.loads((Path(out) / name).read_text(encoding='utf-8'))
    return None


def resume(target, out, **options):
    """Re-run only what a previous attempt did not complete: a run stopped or killed midway from the checkpoint it
    left after its last stage, else the last manifest."""
    previous = _previous(out)
    if previous is None:
        return execute(target, out, **options)
    from ..workspace import inventory
    stored = previous.get('options', {})
    if str(Path(target).resolve()) != previous['target']:
        raise ValueError('Resume target differs from the original target')
    if inventory(target, max_files=stored.get('max_files', 100000), max_bytes=stored.get('max_bytes', 2_000_000))['fingerprint'] != previous.get('source_fingerprint'):
        raise ValueError('Source changed; start a fresh run instead of resuming stale evidence')
    for key, value in stored.items():
        if key in options and options[key] != value: raise ValueError('Resume option changed: ' + key)
        options.setdefault(key, value)
    done = {name for name, row in previous['stages'].items() if row['status'] == OK
            and all((Path(out) / artifact).exists() for artifact in row['produces'])}
    remaining = [name for name in ORDER if name not in done]
    if not remaining:
        return previous
    options.pop('only', None)
    merged = execute(target, out, only=remaining, _completed={name: previous['stages'][name] for name in done}, **options)
    for name in done:
        merged['stages'][name] = previous['stages'][name]
    merged['counts'] = {state: sum(1 for row in merged['stages'].values() if row['status'] == state)
                        for state in (OK, SKIPPED, UNAVAILABLE, FAILED, NOT_REACHED)}
    merged['resumed_from'] = previous['started_at']
    _write(Path(out) / MANIFEST, merged)
    return merged
