"""The behaviour lock: a spec for every feature, describing what the system does today, before anything changes.

Generation is static: nothing from the project runs here. Each feature (features.json) gets specs in its
own tool's format, written under behavior-lock/ in the report:

  pages          Playwright (behavior-lock/playwright/<feature>.spec.ts): every route is opened, its console
                 errors and page errors are compared with a text snapshot, and the page with a screenshot.
                 The first run on the original code (NS26) records both; that recording is the lock.
  http routes    Playwright request tests: a GET's status is recorded the same way. A route that writes is
                 not called blindly: it is skipped and marked needs_fixture.
  Python code    ApprovalTests (behavior-lock/approvals/test_<feature>.py): the public interface of the
                 feature's import-safe modules (names and signatures) is approved as it is today. A module
                 whose top level runs code (a Streamlit page, a script) is never imported.

A route with a parameter ($id, :id) reads it from E2E_<PARAM>; without it the test is skipped and the
surface is marked needs_fixture in plan.json, never dropped. Sign-in, when the owner grants E2E_USER and
E2E_PASSWORD (authorization.json -> env_allow), happens once in auth.setup.ts; no value is written here.
Every spec describes today's behaviour, not the intended one: a console error today is recorded, not fixed.

run_lock() is the screens part of the flow `safety` of the live map (FLOW, written by eaos/journeys/guided/:safety_run to
<runtime>/progress/safety.jsonl): each pass runs with EAOS's stream reporter (eaos/templates/screens/
stream-reporter.mjs), which writes a line per test to behavior-lock/stream.jsonl as it begins and ends; Screens
follows that file and reports one step per spec file, with its shot once written. The approval tests run in the same
passes with EAOS's pinned pytest (_approvals), each spec file a step too; their approved files are the recording of
the code's interfaces, as the snapshots are of the screens.
"""
import json
import shutil
from pathlib import Path
from typing import NamedTuple

from ...core import progress
from ...core.progress.flow import OPTIONAL, Stage
from .folder import LOCK_CONFIG, _keep, _prepare, lend_kinds, passes  # noqa: F401  (LOCK_CONFIG: read here by the tests)
from .results import Screens, _declared, approval_statuses, failing_tests, spec_statuses  # noqa: F401  (the names others read here)
from ...core.system.files import read_json

# The specs this runs are written by eaos/live/behavior/specs.py, its folder made by live/behavior/folder.py, its passes read by
# live/behavior/results.py.

# ApprovalTests reads its reporter from APPROVAL_TESTS_USE_REPORTER: the first pass approves what it receives (the
# recording), every later one prints the difference.
APPROVE = 'approvaltests.reporters.ReporterThatAutomaticallyApproves'
COMPARE = 'approvaltests.reporters.PythonNativeReporter'


def _pages_from_app(report, target, base, runtime):
    """When the lock has no page (the code names none, no check crawled the app yet), the running app is crawled once
    and its pages written to live/crawl.json, where the lock reads its stand-in pages (eaos/live/behavior/specs.py crawled_pages);
    True when the lock was built again with them. A real incident: a fix batch refused for "0 screens recorded"."""
    from . import specs as lock_specs
    from ..screens.crawl import crawl, distinct
    report = Path(report)
    if lock_specs.crawled_pages(report) or lock_specs.PAGE in {row[0] for row in lock_specs.surfaces(report).values()}: return False
    found = crawl(base, Path(runtime) / 'crawl', measured=0)
    if found.get('status') != 'observed': return False
    (report / 'live').mkdir(parents=True, exist_ok=True)
    pages = [paths[0] for paths in distinct(r['path'] for r in found['routes']).values()]
    (report / 'live/crawl.json').write_text(json.dumps({'schema_version': 1, **found, 'pages': pages}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return bool(lock_specs.build(report, target)['specs'])


def _start(live, lock):
    """Set up, start and seed the project; the address it answers on."""
    live.setup()
    base = live.start()
    # A seed may sign the browser in or choose its workspace: it writes Playwright's storage state to
    # EAOS_STORAGE_STATE, and the lock opens every screen with it; the fixtures it prints join the environment. The
    # person's own session, when they signed in by hand, takes its place (eaos/live/access/sign_in.py lend).
    live.seed(base, lock / '.auth/user.json')
    from ..access.sign_in import lend
    lend(live, base, lock / '.auth/user.json')
    return base


def _pass(live, lock, base, output, how):
    """One Playwright pass; `how` is (update: record the screens, the kind of user it runs as or None, its spec files,
    the folder its screens' words are written to or None, keep: the pictures become the lock's original ones: never on
    the re-recording of a kept batch's screens, intended.py, whose pictures are kept apart by its commit, the folder the
    pages' looks are saved to)."""
    update, kind, files, words, keep, look = how
    output.parent.mkdir(parents=True, exist_ok=True)
    argv = ['playwright', 'test', '--config', 'lock.config.ts', '--project=lock', '--no-deps', '--workers=1',
            *(['--update-snapshots=all'] if update else []), *files]
    stream = output.parent / STREAM
    if stream.exists(): stream.unlink()
    screens = Screens(stream, lock / '__screenshots__', output.parent / 'snapshots', keep=keep).start()
    try:
        code, out, err = live.sandbox.run(argv, timeout=3600, network=True, cwd='.eaos-lock',
                                          env={**live.run_env(), 'BASE_URL': base, 'EAOS_LOCK_REPORT': str(output),
                                               'EAOS_LOCK_STREAM': str(stream), 'EAOS_LOCK_KIND': kind or '',
                                               'EAOS_LOCK_UPDATE': '1' if update else '', 'EAOS_LOCK_WORDS': str(words or ''),
                                               'EAOS_LOCK_LOOK': str(look or '')})
    finally:
        screens.stop()
    live.log.append({'argv': argv, 'exit': code, 'tail': (out + err)[-3000:]})     # why a spec did not run
    return read_json(output, {})


def _approvals(live, lock, output, update):
    """{spec path: (status, reason)} of one run of the approval tests with EAOS's pinned pytest, in the copy and
    without network. The project's own modules import from the copy's root, never EAOS's; no pytest setting, conftest
    or plugin of the project's takes part. With `update` every interface received is approved: the recording. Each
    spec is a step of the running stage."""
    from ...core.toolchain import home
    pytest = home() / 'bin/pytest'
    if not pytest.exists(): raise RuntimeError('the approval tests need EAOS\'s pinned pytest: run `eaos tools install --only pytest`')
    names = sorted(f'approvals/{path.name}' for path in (lock / 'approvals').glob('test_*.py'))
    for name in names: progress.step(name, 0, len(names), 'waiting')
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists(): output.unlink()
    argv = [str(pytest), f'{lock.name}/approvals', '-c', f'{lock.name}/pytest.ini', '-p', 'no:cacheprovider',
            '--continue-on-collection-errors', '-q', f'--junitxml={output}']
    code, out, err = live.sandbox.run(argv, timeout=1800, env={
        **live.run_env(), 'PYTHONPATH': str(Path(live.sandbox.copy).resolve()), 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
        'APPROVAL_TESTS_USE_REPORTER': APPROVE if update else COMPARE})
    live.log.append({'argv': argv, 'exit': code, 'tail': (out + err)[-3000:]})
    statuses = approval_statuses(output)
    if update: statuses = _approved(lock, statuses)
    for done, name in enumerate(names, 1):
        status, reason = statuses.get(name, ('error', 'the spec did not run'))
        progress.step(name, done, len(names), 'ok' if status == 'passed' else 'failed', reason=reason[:200],
                      reason_code='' if status == 'passed' else 'approval_failed')
    return statuses


def _approved(lock, statuses):
    """The recording pass's statuses: ApprovalTests fails a test whose received text it has just approved, so a spec
    whose interface is now approved passed; one that wrote nothing keeps its failure."""
    return {name: ('passed', '') if any((lock / name).parent.glob(f'{Path(name).stem}.*.approved.txt')) else status
            for name, status in statuses.items()}


class LockPass(NamedTuple):
    """One pass of the lock's specs: its name (its reports' and log's), whether it records (the first pass on the
    original), and what may differ without failing it: the screens `declared` to change, the tests `known` to fail
    before the change (spec_statuses), the screens `intended` to change by a declared addition only (intended.py)."""
    name: str
    update: bool = False
    declared: tuple = ()
    known: tuple = ()
    intended: dict = None


def _run_specs(live, lock, base, recorded, how):
    """{spec file: (status, reason)} of one pass `how` (LockPass) of every spec the lock holds: the screens with
    Playwright, the interfaces of the code with pytest; their reports are playwright-<name>.json and approvals-<name>.xml
    in `recorded`."""
    from .intended import for_pass
    statuses, words = {}, (recorded / f'words-{how.name}') if how.intended else None     # removed once judged
    for kind, files in passes(lock) if (lock / 'playwright.config.ts').is_file() else []:
        mark = f'@{kind}' if kind else ''         # a kind's pass: its specs' statuses beside the run's one session's
        report = _pass(live, lock, base, recorded / f'playwright-{how.name}{mark}.json', (how.update, kind, files, words, how.update and how.name != 'intended', recorded / 'look' / ('original' if how.update else how.name)))
        found = spec_statuses(report, how.declared, how.known, for_pass(how.intended, lock, words, kind))
        statuses.update({file + mark: status for file, status in found.items()})
    if words: shutil.rmtree(words, ignore_errors=True)
    if (lock / 'approvals').is_dir():
        statuses.update(_approvals(live, lock, recorded / f'approvals-{how.name}.xml', how.update))
    return statuses


def _results(report, statuses):
    results = []
    for spec in json.loads((Path(report) / 'behavior-lock/plan.json').read_text(encoding='utf-8'))['specs']:
        name = Path(spec['path']).name
        status, reason = next(((s, r) for file, (s, r) in statuses.items() if Path(file).name == name),
                              ('error', 'the spec did not run') if spec['path'] else
                              ('quarantined', ('nothing to run: ' + ', '.join(spec.get('surfaces') or ['no surface']))[:300]))
        results.append({'path': spec['path'], 'status': status, **({'reason': reason} if reason else {})})
        results += _kind_rows(spec['path'], statuses)
    return results


def _kind_rows(path, statuses):
    """The results of spec `path` in the passes as each kind of user (their statuses keyed <file>@<kind>)."""
    return [{'path': path, 'kind': file.rsplit('@', 1)[1], 'status': s, **({'reason': r} if r else {})}
            for file, (s, r) in statuses.items() if '@' in file and Path(file.rsplit('@', 1)[0]).name == Path(path).name]


def key(result):
    """A lock result's name: its spec, and the kind of user it ran as."""
    return result['path'] + (f"@{result['kind']}" if result.get('kind') else '')


def refused(lock):
    """[{path, status, reason}] of each screen a run_lock answer could not lock; with none recorded, why (its limitations)."""
    results = lock['results']
    return [{k: r.get(k) for k in ('path', 'status', 'reason') if r.get(k)} for r in results if r['status'] != 'passed'] \
        or ([] if results else [{'reason': '; '.join(lock.get('limitations') or ['no screen could be opened'])}])


def _write(runtime, name, live, results):
    record = {'schema_version': 1, 'commit': live.commit, 'backend': 'unshare' if live.sandbox.offline else 'process',
              'results': results, 'limitations': sorted(set(live.sandbox.limitations))}
    (Path(runtime) / 'behavior-lock').mkdir(parents=True, exist_ok=True)
    (Path(runtime) / 'behavior-lock' / name).write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return record


# ── the live map: the safety flow, and each screen as it is recorded ───────────────────────────────────────
STREAM = 'stream.jsonl'
FLOW = (
    Stage('prepare', description='Copy the report\'s specs (its screens and the interfaces of its code) into the separate '
                                 'copy, with the offline browser settings'),
    Stage('start', requires=('prepare',), description='Install, start and sign in to the app in the separate copy'),
    Stage('record', requires=('start',),
          description='Open every screen and load every interface of the code once, and record how each is today'),
    Stage('verify', requires=('record',),
          description='Open every screen and load every interface again and compare each with the recording: one that '
                      'differs between two runs of the same code is not steady and cannot guard a change'),
    Stage('speed', requires=('start',), necessity=OPTIONAL,
          absent_when='the app has no production build, or its production run did not work during the setup',
          description='Measure how fast the production build answers under many users (k6)'),
)


def run_lock(report, target, runtime, app=None):
    """behavior-lock/results.json in `runtime`: the report's specs, run twice on the original code in the sandbox.

    The first pass records each screen as it is today and approves each interface of the code (kept in
    behavior-lock/snapshots and behavior-lock/approved for every later run); the second must match them. A spec that
    passes the second pass locks today's behaviour; one that differs between two runs of the same code is not
    deterministic and fails. Needs <runtime>/authorization.json granting S05 and <runtime>/run.json. `app`: the check's
    running app (eaos/pipeline/runners/live_app.py shared_app), recorded on as it is, with the person's session; else its own."""
    from ..app.run import LiveRun
    report, runtime = Path(report), Path(runtime)
    recorded = runtime / 'behavior-lock'
    if not (report / 'behavior-lock').is_dir() and not (runtime / 'run.json').is_file():     # nothing to lock, no app to crawl
        return {'results': [], 'limitations': ['the program has no feature to lock']}
    progress.begin('prepare')
    live = app[0] if app else LiveRun(target, runtime, 'S05')
    if not app: live.freeze()
    try:
        progress.begin('start')
        lock, base = _ready(live, report, target, runtime, app)
        if lock is None:         # the code names no feature and the running app no page: nothing is recorded, said so
            return {'results': [], 'limitations': ['the program has no feature to lock']}
        progress.begin('record')
        _run_specs(live, lock, base, recorded, LockPass('record', update=True))
        _keep(lock, recorded)
        progress.begin('verify')
        results = _results(report, _run_specs(live, lock, base, recorded, LockPass('verify')))
        progress.end('verify', detail={'screens': len(results), 'passed': sum(r['status'] == 'passed' for r in results)})
    finally:
        if not app: live.stop()
        live.record('behavior-lock/run-log.json')
    return _write(runtime, 'results.json', live, results)


# The journeys are kept light: at most JOURNEYS rrweb recordings of at most RECORDING_BYTES each, and a Playwright trace
# only for a failing journey, at most TRACES of them and only when it is under TRACE_BYTES; the rest are deleted and
# counted, so a large app never fills the disk with replays nobody asked for.
JOURNEYS, RECORDING_BYTES, TRACES, TRACE_BYTES = 20, 1_500_000, 3, 2_000_000


def _ready(live, report, target, runtime, app):
    """(the lock folder, None when there is nothing to lock; the running app's address): the lock built again with the
    app's crawled pages when the code names none (_pages_from_app)."""
    lock = _prepare(live, report) if (report / 'behavior-lock').is_dir() else None
    base = _shared(app, lock) if app else _start(live, lock or live.sandbox.copy / '.eaos-lock')
    if _pages_from_app(report, target, base, runtime): lock = _prepare(live, report)
    if lock: lend_kinds(report, lock, app[2] if app else lock / '.auth/user.json')
    return lock, base


def cap_journeys(folder):
    """Delete what the caps leave out of <folder>/rrweb and <folder>/traces: {'recordings', 'traces'} kept (file names),
    and {'recordings_dropped', 'traces_dropped'}: [{name, bytes, why}]."""
    folder = Path(folder)
    kept, dropped = {'recordings': [], 'traces': []}, {'recordings_dropped': [], 'traces_dropped': []}
    for part, key, limit, count in (('rrweb', 'recordings', RECORDING_BYTES, JOURNEYS), ('traces', 'traces', TRACE_BYTES, TRACES)):
        for path in sorted((folder / part).glob('*')) if (folder / part).is_dir() else []:
            size = path.stat().st_size
            why = (f'larger than {limit} bytes' if size > limit else
                   f'more than {count} kept' if len(kept[key]) >= count else None)
            if why:
                path.unlink()
                dropped[key + '_dropped'].append({'name': path.name, 'bytes': size, 'why': why})
            else:
                kept[key].append(path.name)
    return {**kept, **dropped}


def _shared(app, lock):
    """The address of the check's running app, its session (a seed's or the person's) the lock's browser state."""
    if app[2].is_file(): shutil.copyfile(app[2], lock / '.auth/user.json')
    return app[1]


def _journey_start(live, report, runtime, bundle, app):
    """Prepare the journeys' recorder and sign-in, using the page stages' running app when supplied."""
    lock = _prepare(live, report, Path(runtime) / 'behavior-lock')
    recorder = lock / 'rrweb.js'
    shutil.copyfile(bundle, recorder)
    base = _shared(app, lock) if app else _start(live, lock)
    lend_kinds(report, lock, app[2] if app else lock / '.auth/user.json')
    return lock, recorder, base


def run_journeys(report, target, runtime, folder, app=None):
    """Each page spec of the lock run once more on today's code, with rrweb recording every page and Playwright's trace
    kept for a failing journey: <folder>/rrweb/<test>.rrweb.json (the page, replayable) and <folder>/traces/<n>.zip
    (every step's picture, the network and the console of a failure), both capped (cap_journeys). Needs what run_lock
    needs; returns {specs, walked: [{spec, pages, status, reason}], failed, recordings, traces, *_dropped}."""
    from ..app.run import LiveRun
    from ...core.toolchain import node_modules
    folder = Path(folder)
    for part in ('traces', 'rrweb', 'results'): shutil.rmtree(folder / part, ignore_errors=True)
    (folder / 'rrweb').mkdir(parents=True)
    bundle = node_modules('rrweb') / 'rrweb/dist/rrweb.umd.cjs'
    if not bundle.is_file(): raise FileNotFoundError(f'rrweb is not installed ({bundle}): python -m eaos tools install --only rrweb')
    live = app[0] if app else LiveRun(target, runtime, 'S05')
    try:
        lock, recorder, base = _journey_start(live, report, runtime, bundle, app)
        for kind, files in passes(lock): _walk(live, base, folder, (kind, files), recorder)
    finally:
        if not app: live.stop()
        live.record('behavior-lock/journeys-log.json')
    traces = sorted(folder.glob('results*/**/trace.zip'))
    (folder / 'traces').mkdir(exist_ok=True)
    for number, trace in enumerate(traces, 1): shutil.move(str(trace), folder / 'traces' / f'{number:03d}-{trace.parent.name[:80]}.zip')
    for results in folder.glob('results*'): shutil.rmtree(results, ignore_errors=True)
    (folder / STREAM).unlink(missing_ok=True)
    return _journey_results(folder, report)


def _walk(live, base, folder, kind, recorder):
    """One walk of the journeys: with the run's one session over every spec, rrweb recording each page, or as kind of user
    `kind` ((id, spec files)) over its own pages' specs, its report report@<kind>.json."""
    kind, files = kind
    mark = f'@{kind}' if kind else ''
    argv = ['playwright', 'test', '--config', 'lock.config.ts', '--project=lock', '--no-deps', '--workers=1',
            '--trace=retain-on-failure', '--output', str(folder / f'results{mark}'), *files]
    code, out, err = live.sandbox.run(argv, timeout=3600, network=True, cwd='.eaos-lock', env={
        **live.run_env(), 'BASE_URL': base, 'EAOS_LOCK_REPORT': str(folder / f'report{mark}.json'), 'EAOS_LOCK_KIND': kind or '',
        'EAOS_LOCK_STREAM': str(folder / STREAM), **({} if kind else {'EAOS_RRWEB': str(recorder), 'EAOS_JOURNEYS': str(folder / 'rrweb')})})
    live.log.append({'argv': argv, 'exit': code, 'tail': (out + err)[-3000:]})


def _journey_results(folder, report):
    """The walked specs and bounded recordings, whether the app belonged to the journeys or the check."""
    statuses = {(name, path.stem.partition('@')[2]): status for path in sorted(folder.glob('report*.json'))
                for name, status in spec_statuses(json.loads(path.read_text(encoding='utf-8'))).items()}
    pages = _pages_of(json.loads((Path(report) / 'behavior-lock/plan.json').read_text(encoding='utf-8')))
    walked = [{'spec': name, **({'kind': kind} if kind else {}), 'pages': pages.get(Path(name).name, [])[:20], 'status': status,
               'reason': reason[:300]} for (name, kind), (status, reason) in sorted(statuses.items())]
    for path in folder.glob('report@*.json'): path.unlink()
    return {'specs': len(statuses), 'walked': walked, 'failed': sum(w['status'] == 'failed' for w in walked), **cap_journeys(folder)}


def _pages_of(plan):
    """{spec file name: the pages it walks} of the plan's Playwright specs (their HTTP routes aside)."""
    return {Path(s['path']).name: [x for x in s.get('surfaces') or [] if not str(x).startswith(('GET ', 'POST ', 'PUT ', 'PATCH ', 'DELETE '))]
            for s in plan.get('specs') or [] if s.get('tool') == 'playwright' and s.get('path')}


def verify_lock(report, target, runtime, how=LockPass('results-after')):
    """The lock recorded on the original, run once on `target` (a candidate EAOS committed on the granted commit) as
    pass `how` (LockPass): behavior-lock/<its name>.json, and {specs, passed, failed}. Needs what the original recorded,
    screens or interfaces of the code. No recording is ever updated here; a screen `how.declared` may look different."""
    from ..app.run import LiveRun
    report, runtime = Path(report), Path(runtime)
    recorded = runtime / 'behavior-lock'
    if not any((recorded / kept).is_dir() for kept in ('snapshots', 'approved')):
        raise RuntimeError('nothing recorded on the original, neither a screen nor an interface of the code: '
                           'run `eaos live lock` first')
    live = LiveRun(target, runtime, 'S09')
    lock = _prepare(live, report, recorded)
    from .intended import restore_intended
    restore_intended(recorded, lock, target)         # the new truth of the kept intended changes this code holds
    try:
        base = _start(live, lock)
        lend_kinds(report, lock, lock / '.auth/user.json')
        results = _results(report, _run_specs(live, lock, base, recorded, how._replace(update=False)))
    finally:
        live.stop()
        live.record(f'behavior-lock/run-log-{how.name}.json')
    _write(runtime, f'{how.name}.json', live, results)
    return _judged(_passed_before(runtime, results), results)


def _passed_before(runtime, results):
    """The specs that passed on the original (all of `results` when it has no record)."""
    original = runtime / 'behavior-lock/results.json'
    if not original.is_file(): return {key(r) for r in results}
    return {key(r) for r in json.loads(original.read_text(encoding='utf-8'))['results'] if r['status'] == 'passed'}


def _judged(passed_before, results):
    """{specs, passed, failed, already_failing}. A spec that did not pass on the original (its recording failed, or it
    never had one) cannot be broken by a change: only a spec that passed there and fails here counts against it."""
    failing = [r for r in results if r['status'] in ('failed', 'error')]
    return {'specs': len(results), 'passed': sum(r['status'] == 'passed' for r in results),
            'failed': sum(key(r) in passed_before for r in failing),
            'already_failing': sorted(key(r) for r in failing if key(r) not in passed_before)}
