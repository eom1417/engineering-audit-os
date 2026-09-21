"""Execute the declared pipeline and record, for every stage, what happened and what did not.

A stage that fails does not silently take the run with it: its dependents are recorded as skipped
with the reason, the independent stages still run, and the manifest is the honest account of the
whole attempt. A stage that never ran leaves a reason, never a gap.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .stages import BY_NAME, OPTIONAL, ORDER, STAGES, SkipStage, dependents

OK, SKIPPED, UNAVAILABLE, FAILED, NOT_REACHED = 'ok', 'skipped', 'unavailable', 'failed', 'not_reached'
MANIFEST = 'run-manifest.json'


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
            test_command=None, site=True, goal=None, audit_run=None, runners=None):
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
                      audit_run=audit_run)
    requested = [name for name in ORDER if (not only or name in set(only)) and name not in set(skip)]
    results, blocked = {}, {}
    started_at = datetime.now(timezone.utc).isoformat(timespec='seconds')
    began = time.monotonic()
    for stage in STAGES:
        if stage.name not in requested:
            results[stage.name] = _row(stage, SKIPPED, 'not requested in this run')
            continue
        if stage.name in blocked:
            results[stage.name] = _row(stage, NOT_REACHED, blocked[stage.name])
            continue
        context['manifest_so_far'] = {'stages': dict(results), 'seconds': round(time.monotonic() - began, 2),
                                      'status': 'RUNNING'}
        results[stage.name] = _one(stage, context, runners, results)
        if results[stage.name]['status'] in (FAILED, UNAVAILABLE, SKIPPED, NOT_REACHED):
            reason = f"{stage.name} did not produce its artifacts ({results[stage.name]['status']})"
            for name in dependents(stage.name):
                blocked.setdefault(name, reason)
    manifest = {
        'contract_version': 1, 'target': str(target), 'out': str(out), 'started_at': started_at,
        'seconds': round(time.monotonic() - began, 2), 'requested': requested,
        'stages': results,
        'counts': {state: sum(1 for row in results.values() if row['status'] == state)
                   for state in (OK, SKIPPED, UNAVAILABLE, FAILED, NOT_REACHED)},
        'status': 'COMPLETE' if not any(row['status'] == FAILED for row in results.values()) else 'INCOMPLETE',
        'limits': 'A stage that did not run proves nothing. Read the skipped and unavailable rows before '
                  'reading the findings: they are the shape of what this run could not see.',
    }
    (out / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    return manifest


def _row(stage, status, reason, seconds=0.0, artifacts=(), detail=None):
    return {'stage': stage.name, 'status': status, 'reason': reason, 'seconds': round(seconds, 2),
            'necessity': stage.necessity, 'produces': list(stage.produces),
            'artifacts': sorted(artifacts), 'detail': detail or {}}


def _one(stage, context, runners, results):
    runner = runners.get(stage.name)
    if runner is None:
        return _row(stage, FAILED, 'no runner is registered for this stage')
    began = time.monotonic()
    try:
        outcome = runner(context) or {}
    except SkipStage as reason:
        return _row(stage, UNAVAILABLE, str(reason), time.monotonic() - began)
    except Exception as problem:                       # one stage must not decide the fate of the rest
        return _row(stage, FAILED, f'{type(problem).__name__}: {problem}'[:300], time.monotonic() - began)
    seconds = time.monotonic() - began
    present = [name for name in stage.produces if (context.out / name).exists()]
    missing = [name for name in stage.produces if name not in present]
    if missing:
        return _row(stage, FAILED, 'declared artifacts were not written: ' + ', '.join(missing),
                    seconds, present, outcome)
    return _row(stage, OK, '', seconds, present, outcome)


def resume(target, out, **options):
    """Re-run only what a previous attempt did not complete."""
    path = Path(out) / MANIFEST
    if not path.is_file():
        return execute(target, out, **options)
    previous = json.loads(path.read_text(encoding='utf-8'))
    done = {name for name, row in previous['stages'].items() if row['status'] == OK}
    remaining = [name for name in ORDER if name not in done]
    if not remaining:
        return previous
    merged = execute(target, out, only=remaining, **options)
    for name in done:
        merged['stages'][name] = previous['stages'][name]
    merged['counts'] = {state: sum(1 for row in merged['stages'].values() if row['status'] == state)
                        for state in (OK, SKIPPED, UNAVAILABLE, FAILED, NOT_REACHED)}
    merged['resumed_from'] = previous['started_at']
    (Path(out) / MANIFEST).write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding='utf-8')
    return merged
