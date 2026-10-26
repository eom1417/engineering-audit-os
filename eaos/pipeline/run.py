"""Execute the declared pipeline and record, for every stage, what happened and what did not.

A stage that fails does not silently take the run with it: its dependents are recorded as skipped
with the reason, the independent stages still run, and the manifest is the honest account of the
whole attempt. A stage that never ran leaves a reason, never a gap. One stage's run is stage_run.py's;
here are the run of them all, its manifest, and the checks a person asks for (check, focused, again, resume).
"""
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from ..core.progress import ProgressLog, previous_seconds
from ..core.progress.flow import incomplete, partial
from ..core.system.usage import FILE as USAGE
from .runners.live_app import close_app
from .path_choice import resolve
from ..report.documents.run import document
from .coverage import ledger
from .loops import switched_off
from .rounds import Rounds
from .schedule import LimitedProvider, assistants, run_ready
from .stage_run import CHECKPOINT, FAILED, NOT_REACHED, OK, SKIPPED, UNAVAILABLE, Context, _stage, _write
from .stages import BY_NAME, ORDER, STAGES, dependents

MANIFEST = 'run-manifest.json'


def _runners():
    """Imported lazily: a pipeline declaration must be readable without importing the whole product."""
    from .runners import by_rules as runners
    return runners.RUNNERS


def execute(target, out, *, only=(), skip=(), language='ar', exclude=(), engines=None, provider=None,
            goal=None, audit_run=None, runners=None, intake=None,
            max_files=100000, max_bytes=2_000_000, policy_path=None, _completed=None, progress=None, without_tools=(),
            runtime=None, mode='normal', paths=None, patterns=None, sign_in=None):  # limits: parameters -- the run's keyword-only options, passed through as **options by check, again and resume
    """`progress(done, total, stage)` is called before each stage that will run, so a person waiting sees where
    the run is; it never changes what runs. `without_tools`: the tools whose install failed and the person started
    without; the manifest records them (`options`). `runtime`: the folder the app is run in, an isolated copy, given only
    once the person agreed to run it; without it every live stage says so. `mode`: how many stages and assistants run at
    once (eaos/pipeline/schedule.py: normal, speed, one). `paths`: the check's paths (eaos/pipeline/path_choice.py), recorded;
    `patterns`: the card patterns the plan keeps, None for all. `sign_in`: how the page stages sign in to the app
    (eaos/journeys/check_choices.py options: how, the published address named for this check, the project's folder).

    Every event of the run is also appended to `<out>/run-progress.jsonl` (eaos/core/progress/log.py): the run's start
    with the declared stages, each stage's start, its steps, its end with its status, reason, seconds and artifacts,
    and the run's end. Every stage gets exactly one end, so the folded file equals the manifest when the run is over;
    a run stopped or broken midway ends the stage it was in and every stage it did not reach before it says so.
    While a stage runs it is the current stage of eaos/core/progress/context.py, so `progress.count()` anywhere below it
    reports into it."""
    target, out = _outside(target, out)
    if isinstance(getattr(provider, 'config', None), dict): provider.config['usage'] = str(out / USAGE)    # eaos/core/system/usage.py
    runners = runners if runners is not None else _runners()
    _refuse_unknown(only, skip)
    context = Context(target=target, out=out, language=language, exclude=list(exclude), engines=engines,
                      provider=provider, goal=goal,
                      audit_run=audit_run, max_files=max_files, max_bytes=max_bytes, policy_path=policy_path,
                      intake=_resolved(intake), runtime=str(runtime) if runtime else None, assistants=assistants(mode),
                      patterns=patterns, sign_in=dict(sign_in or {}))
    if provider: context['provider'] = LimitedProvider(provider, context.assistants)
    requested = _requested(only, (*skip, *switched_off(paths or ['complete'])))
    completed = _completed or {}
    context['again'] = bool(completed)          # within a check run before: a tool run again joins the others' results
    started_at = datetime.now(timezone.utc).isoformat(timespec='seconds')
    began = time.monotonic()
    todo = _todo(requested, completed)
    head = _head(context, started_at, requested)
    head['options']['without_tools'] = sorted(without_tools)
    head.update(mode=mode, paths=paths or ['complete'])     # not options: a check goes on in another mode or path
    log = ProgressLog(out)
    log.started(STAGES, requested, previous_seconds(out), mode=mode, assistants=context.assistants.count)
    run = {'completed': completed, 'requested': requested, 'results': {}, 'blocked': {}, 'log': log, 'context': context,
           'runners': runners, 'progress': progress, 'todo': todo, 'out': out, 'began': began, 'head': head,
           'lock': threading.RLock()}
    # What a stage reads of the run: the stages ended so far. It only asks of those it waits for, so it reads them
    # ended whatever else runs beside it (tests/pipeline/test_parallel.py).
    context['manifest_so_far'] = {'stages': run['results'], 'status': 'RUNNING'}
    return _go(run, mode)


def _todo(requested, completed):
    """The stages this run runs, in their declared order: the ones requested and not completed before."""
    return [stage.name for stage in STAGES if stage.name in requested and stage.name not in completed]


def _go(run, mode):
    """Every stage run as soon as what it waits for has ended, then the manifest; a run stopped or broken midway says
    so in its progress file, then the error goes on."""
    log, began, context = run['log'], run['began'], run['context']
    try:
        rounds = Rounds(run)
        run_ready(ORDER, lambda name: _stage(BY_NAME[name], run), mode, quick=set(ORDER) - set(run['todo']), rounds=rounds)
        manifest = _manifest(run['head'], began, run['results'], rounds.record())
        (run['out'] / CHECKPOINT).unlink(missing_ok=True)
    except BaseException as problem:                    # stopped or broken: the file says so, then the error goes on
        log.finish('STOPPED' if isinstance(problem, KeyboardInterrupt) else 'ERROR',
                   reason=f'{type(problem).__name__}: {problem}'[:300], seconds=round(time.monotonic() - began, 2))
        raise
    finally:
        close_app(context)
    log.finish(manifest['status'], seconds=manifest['seconds'], counts=manifest['counts'])
    return manifest


def _outside(target, out):
    """(target, out) resolved, `out` outside the target and made, without the documents a check no longer writes."""
    target, out = Path(target).resolve(), Path(out).resolve()
    if out == target or target in out.parents:
        raise ValueError('Pipeline output must live outside the target; the target stays read-only')
    out.mkdir(parents=True, exist_ok=True)
    for name in RETIRED: (out / name).unlink(missing_ok=True)
    return target, out


def _refuse_unknown(only, skip):
    unknown = sorted((set(only) | set(skip)) - set(ORDER))
    if unknown:
        raise ValueError('Unknown stage: ' + ', '.join(unknown))


def _resolved(intake): return str(Path(intake).resolve()) if intake else None


def _requested(only, skip):
    wanted, skipped = set(only), set(skip)
    return [name for name in ORDER if (not only or name in wanted) and name not in skipped]


def _head(context, started_at, requested):
    """What the manifest says of the run whatever its stages do, its options read from the run's `context`; with the
    stages so far it is also the checkpoint written after each stage, which a run stopped or killed midway is resumed
    from."""
    from ..core.project.workspace import inventory
    return {'contract_version': 1, 'target': str(context.target), 'out': str(context.out), 'started_at': started_at,
            'requested': requested,
            'options': {'language': context.language, 'exclude': list(context.exclude), 'max_files': context.max_files,
                        'max_bytes': context.max_bytes,
                        'policy_path': str(context.policy_path) if context.policy_path else None, 'intake': context.intake},
            'source_fingerprint': inventory(context.target, max_files=context.max_files, max_bytes=context.max_bytes)['fingerprint']}


def _manifest(head, began, results, loops):
    """The run's record: its stages' rows and each loop's outcome (`loops`, eaos/pipeline/rounds.py), written with RUN.md."""
    manifest = {
        **{key: head[key] for key in ('contract_version', 'target', 'out', 'started_at', 'mode', 'paths') if key in head},
        'seconds': round(time.monotonic() - began, 2), 'requested': head['requested'],
        'stages': results, 'loops': loops, 'coverage': ledger(results, loops),
        'counts': _counts(results),
        'status': completion_status(results),
        'limits': 'A stage that did not run proves nothing. Read the skipped and unavailable rows before '
                  'reading the findings: they are the shape of what this run could not see.',
        'options': head['options'], 'source_fingerprint': head['source_fingerprint'],
        'measured': _measured(Path(head['out']) / MANIFEST, results),
    }
    _write(Path(head['out']) / MANIFEST, manifest)
    # RUN.md beside it: what ran, what did not and why, read before any finding.
    (Path(head['out']) / 'RUN.md').write_text(document(manifest, head['options']['language'] or 'ar').render(), encoding='utf-8')
    return manifest


def _counts(results):
    """{status: how many stages ended with it}, for every status a stage can end with."""
    return {state: sum(1 for row in results.values() if row['status'] == state) for state in (OK, SKIPPED, UNAVAILABLE, FAILED, NOT_REACHED)}


def _measured(path, results):
    """{stage: seconds} each stage took the last time it ran ok, in this run or an earlier one: a stage this run could
    not run (its assistant lost midway) keeps its earlier time, so the estimate of running it again is not zero."""
    try: before = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError): before = {}
    kept = {**(before.get('measured') or {}), **{name: row['seconds'] for name, row in (before.get('stages') or {}).items() if _timed(row)}}
    return {**kept, **{name: row['seconds'] for name, row in results.items() if _timed(row)}}


def _timed(row):
    """Whether a stage's row ended ok with its seconds."""
    return isinstance(row, dict) and row.get('status') == OK and isinstance(row.get('seconds'), (int, float))


def completion_status(results):
    if any(incomplete(row) for row in results.values()): return 'INCOMPLETE'
    if any(partial(row) or row.get('reason_code') == 'tools_failed' for row in results.values()): return 'PARTIAL'
    return 'COMPLETE'


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
# The documents and records a check no longer writes (M1.4: 27 documents down to 8, their records kept; M1.5:
# reports.json, which nothing read): any run removes a previous check's,
# or the output contract (R13) finds them undeclared and the Studio's Library lists them as if current.
RETIRED = ('CONTRACTS.md', 'COUPLING-ATLAS.md', 'DECISION-BRIEF.md', 'DOMAIN-AND-DATA.md', 'ENGINES.md', 'EVOLUTION.md',
           'FEATURES.md', 'FLOWS.md', 'LOAD-MODEL.md', 'MEASUREMENTS.md', 'ONBOARDING.md', 'POLICY.md', 'PROVENANCE.md',
           'RISK-REGISTER.md', 'ROADMAP.md', 'SEMANTIC.md', 'SUSTAINABILITY.md', 'SYSTEM-MAP.md', 'transform-plan.md',
           'reports.json')
PICTURES = ('live/screens', 'live/crawl', 'nodes/*/runs', 'ideal/run-*')     # what `eaos clean --pictures` removes from every report


def bulky(out, patterns=None):
    """The paths of report `out` that match `patterns`, by default the previous check's bulky data (BULKY and the
    engines' scratch)."""
    from ..facts.engine_findings import SCRATCH
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


def check(target, out, again_from=None, checked=False, paths=None, go_on=False, **options):  # limits: parameters -- the check's own choices (again, go on, focus); the run's options pass on as **options
    """A check the person asked for: a fresh full run, which first clears the previous check's bulky data (clear) unless
    it runs some stages only. `go_on`: a run that did not end (stopped, broken or killed midway: its checkpoint is there)
    goes on from that checkpoint instead, unless the source changed since; a new check never does (one stopped and
    started again went on at 31 of 37 stages). `again_from`: the last check goes on from that stage (again). `paths`:
    the check follows those paths only (focused)."""
    if again_from: return again(target, out, again_from, checked=checked, **options)
    if go_on and (Path(out) / CHECKPOINT).is_file():
        try: return resume(target, out, **options)
        except ValueError: pass                         # the source or the options changed since: its evidence is stale
    (Path(out) / CHECKPOINT).unlink(missing_ok=True)    # a run stopped midway is no part of a new check
    chosen = resolve(paths)
    if chosen['stages'] is not None: return focused(target, out, chosen, checked, **options)
    if not options.get('only'): clear(out)
    (Path(out) / USAGE).unlink(missing_ok=True)        # a fresh run counts its own use from nothing
    return execute(target, out, paths=chosen['paths'], **options)     # `complete` and the options it switches on


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
    `checked`: `target` is the very commit the check read clean (eaos/journeys/guided/ source), so the same code whatever
    caches lay beside it then (.cache, egg-info), and the files' fingerprint is not asked."""
    stages = (stage,) if isinstance(stage, str) else tuple(stage)
    for name in stages:
        if name not in BY_NAME: raise ValueError(f'there is no stage named {name}')
    if _previous(out) is None: raise ValueError('there is no check to go on from: run a check first')
    return resume(target, out, redo={s for name in stages for s in (name, *dependents(name, reading=True))}, checked=checked, **options)


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
    merged['counts'] = _counts(merged['stages'])
    merged['coverage'] = ledger(merged['stages'], merged.get('loops'))
    merged['resumed_from'] = previous['started_at']
    _write(Path(out) / MANIFEST, merged)
    return merged


def same_source(target, out):
    """The last check's options when `target` is the code it read; ValueError when there is no check or the code changed."""
    previous = _previous(out)
    if previous is None: raise ValueError('there is no check to go on from: run a check first')
    return _resumable(target, previous)


def _resumable(target, previous):
    """The previous run's options, once it is shown to be about this source: the same files, wherever the copy is."""
    from ..core.project.workspace import inventory
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
