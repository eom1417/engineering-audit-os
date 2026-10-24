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

run_lock() is the screens part of the flow `safety` of the live map (FLOW, written by eaos/journeys/guided.py:safety_run to
<runtime>/progress/safety.jsonl): each pass runs with EAOS's stream reporter (eaos/templates/screens/
stream-reporter.mjs), which writes a line per test to behavior-lock/stream.jsonl as it begins and ends; Screens
follows that file and reports one step per spec file, with its shot once written. The approval tests run in the same
passes with EAOS's pinned pytest (_approvals), each spec file a step too; their approved files are the recording of
the code's interfaces, as the snapshots are of the screens.
"""
import contextvars
import json
import os
import re
import shutil
import threading
from pathlib import Path

from ..core import progress
from ..core.progress.flow import OPTIONAL, Stage

# The specs this runs are written by eaos/live/lock_specs.py.

# ── NS26: the lock, run on the original code ────────────────────────────────────────────────────────────
# The browser reaches loopback only: Chromium sends every other host to a proxy nobody answers on, so a
# page's call to production or a third party fails inside the run instead of leaving the machine.
LOCK_CONFIG = """import base from './playwright.config';

// Written by EAOS for a run in the sandbox: the generated config, with every non-loopback host refused.
// Loopback is named in the bypass list: every other host goes to a proxy nobody answers on.
const offline = { launchOptions: { args: ['--proxy-server=http://127.0.0.1:9', '--proxy-bypass-list=127.0.0.1;localhost;[::1]'] } };
export default {
  ...base,
  reporter: [['json', { outputFile: process.env.EAOS_LOCK_REPORT }], ['./stream-reporter.mjs', { outputFile: process.env.EAOS_LOCK_STREAM }]],
  use: { ...base.use, ...offline },
  projects: (base.projects ?? []).map((project) => ({ ...project, use: { ...project.use, ...offline } })),
};
"""


# The approval tests run from the copy's root with this file as their settings: the project's pytest settings and
# conftest files stay out. ApprovalTests reads its reporter from APPROVAL_TESTS_USE_REPORTER: the first pass approves
# what it receives (the recording), every later one prints the difference.
APPROVALS_INI = "[pytest]\n# Written by EAOS: the lock's approval tests, run without the project's pytest settings.\n"
APPROVE = 'approvaltests.reporters.ReporterThatAutomaticallyApproves'
COMPARE = 'approvaltests.reporters.PythonNativeReporter'


SCREENSHOT = re.compile(r'toHaveScreenshot.*?Snapshot: ([\w.-]+)\.png', re.S)
ANSI = re.compile(r'\x1b\[[0-9;]*m')


def failing_tests(runtime, name):
    """The titles of the screen tests that failed in the lock run `name` (behavior-lock/playwright-<name>.json)."""
    try: report = json.loads((Path(runtime) / 'behavior-lock' / f'playwright-{name}.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): return set()
    found = set()

    def walk(suite):
        for spec in suite.get('specs') or []:
            if any(status in ('failed', 'timedOut') for status, _ in _outcomes(spec, ())): found.add(spec.get('title'))
        for child in suite.get('suites') or []: walk(child)
    for suite in report.get('suites') or []: walk(suite)
    return found


def _declared(status, message, declared):
    """A test failed only because its screen looks different, on a screen the batch's design cards say they change
    (`declared` snapshot names, eaos/journeys/waves.py declared_screens): their change, not a breakage."""
    found = SCREENSHOT.search(ANSI.sub('', message or '')) if status == 'failed' else None
    return 'passed' if found and ('*' in declared or found.group(1) in declared) else status


def spec_statuses(report, declared=(), known=()):
    """{spec path: (status, reason)} from a Playwright JSON report: a spec passes when none of its tests failed
    and at least one ran; one whose every test was skipped is quarantined with the skip's reason."""
    found = {}

    def walk(suite, file=None):
        file = suite.get('file') or file
        for spec in suite.get('specs') or []:
            found.setdefault(file, []).extend(_outcomes(spec, declared, spec.get('title') in known))
        for child in suite.get('suites') or []: walk(child, file)
    for suite in report.get('suites') or []: walk(suite)
    return _verdicts(found)


def _outcomes(spec, declared, known=False):
    """[(status, message)] of one spec's tests; a test that never ran, skipped with its reason. `known`: it fails on the
    code before the batch too (eaos/journeys/waves.py _against_control), so it says nothing of the batch."""
    tests = spec.get('tests') or []
    ran = [(result.get('status'), ANSI.sub('', (result.get('error') or {}).get('message', ''))) for test in tests for result in test.get('results') or []]
    return ([('passed' if known else _declared(status, message, declared), message) for status, message in ran] or
            [('skipped', (test.get('annotations') or [{}])[0].get('description', '')) for test in tests])


def _verdicts(found):
    """{spec file: (status, reason)} from {spec file: [(test status, message)]}, by the rule of spec_statuses()."""
    return {file: _spec_status(outcomes) for file, outcomes in found.items()}


def _spec_status(outcomes):
    failed = [message for status, message in outcomes if status in ('failed', 'timedOut', 'interrupted')]
    if failed: return 'failed', failed[0][:300]
    if any(status == 'passed' for status, _ in outcomes): return 'passed', ''
    return 'quarantined', 'every test was skipped: ' + (next((m for s, m in outcomes if m), '') or 'needs a fixture')


def approval_statuses(junit):
    """{spec path: (status, reason)} from pytest's JUnit XML report of the approval tests, by the rule of
    spec_statuses(); a test file that could not even be imported fails with its error."""
    from xml.etree import ElementTree
    try: cases = list(ElementTree.parse(junit).getroot().iter('testcase'))
    except (OSError, ElementTree.ParseError): return {}
    found = {}
    for case in cases:
        module = case.get('classname') or case.get('name') or ''      # a file that did not import is named in `name`
        found.setdefault(module.replace('.', '/') + '.py', []).append(_outcome(case))
    return _verdicts(found)


def _outcome(case):
    """(status, message) of one JUnit test case, in the words of a Playwright report."""
    for tag, status in (('failure', 'failed'), ('error', 'failed'), ('skipped', 'skipped')):
        found = case.find(tag)
        if found is not None: return status, found.get('message') or found.text or ''
    return 'passed', ''


def _prepare(live, report, recorded=None):
    """The lock folder in the sandbox copy: the report's specs, the offline config, and what the original recorded
    in `recorded` (behavior-lock/ of the runtime folder) if given."""
    lock = live.sandbox.copy / '.eaos-lock'
    shutil.rmtree(lock, ignore_errors=True)
    shutil.copytree(Path(report) / 'behavior-lock', lock)
    (lock / 'lock.config.ts').write_text(LOCK_CONFIG, encoding='utf-8')
    shutil.copyfile(REPORTER, lock / REPORTER.name)
    # The specs import @playwright/test, which most projects do not install; ES modules ignore NODE_PATH. The
    # lock always runs EAOS's pinned Playwright, the version its installed browsers belong to.
    from ..core.toolchain import home
    # its real path: in the run's own view the tools are shown at their name and at their real path, two mounts, and the
    # runner (found on PATH through the same links) loads Playwright from the real one: one copy, never two
    modules = Path(os.path.realpath(home() / 'node/node_modules'))
    if modules.is_dir() and not (lock / 'node_modules').exists(): (lock / 'node_modules').symlink_to(modules, target_is_directory=True)
    # Its own package.json: a project declaring "type": "module" must not change how the lock's files load.
    (lock / 'package.json').write_text('{"private": true, "type": "commonjs"}\n', encoding='utf-8')
    (lock / '.auth').mkdir(exist_ok=True)
    (lock / '.auth/user.json').write_text(json.dumps({'cookies': [], 'origins': []}), encoding='utf-8')
    if (lock / 'approvals').is_dir(): (lock / 'pytest.ini').write_text(APPROVALS_INI, encoding='utf-8')
    if recorded is not None: _restore(Path(recorded), lock)
    return lock


def _keep(lock, recorded):
    """What the first pass recorded, kept in `recorded` for every later run: the screens' snapshots (snapshots/) and
    the approved interfaces (approved/). A folder exists only when something was recorded in it."""
    shutil.rmtree(recorded / 'snapshots', ignore_errors=True)
    if (lock / '__screenshots__').is_dir(): shutil.copytree(lock / '__screenshots__', recorded / 'snapshots')
    shutil.rmtree(recorded / 'approved', ignore_errors=True)
    for path in sorted((lock / 'approvals').glob('*.approved.txt')):
        (recorded / 'approved').mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, recorded / 'approved' / path.name)


def _restore(recorded, lock):
    """The recording kept by _keep(), put back where the tools look for it."""
    if (recorded / 'snapshots').is_dir():
        shutil.rmtree(lock / '__screenshots__', ignore_errors=True)
        shutil.copytree(recorded / 'snapshots', lock / '__screenshots__')
    if not (lock / 'approvals').is_dir(): return
    for path in sorted((recorded / 'approved').glob('*.approved.txt')):
        shutil.copyfile(path, lock / 'approvals' / path.name)


def _pages_from_app(report, target, base, runtime):
    """When the lock has no page (the code names none, no check crawled the app yet), the running app is crawled once
    and its pages written to live/crawl.json, where the lock reads its stand-in pages (eaos/live/lock_specs.py crawled_pages);
    True when the lock was built again with them. A real incident: a fix batch refused for "0 screens recorded"."""
    from . import lock_specs
    from .screens.crawl import crawl, distinct
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
    # person's own session, when they signed in by hand, takes its place (eaos/live/sign_in.py lend).
    live.seed(base, lock / '.auth/user.json')
    from .sign_in import lend
    lend(live, base, lock / '.auth/user.json')
    return base


def _pass(live, lock, base, output, update):
    output.parent.mkdir(parents=True, exist_ok=True)
    argv = ['playwright', 'test', '--config', 'lock.config.ts', '--project=lock', '--no-deps', '--workers=1',
            *(['--update-snapshots=all'] if update else [])]
    stream = output.parent / STREAM
    if stream.exists(): stream.unlink()
    screens = Screens(stream, lock / '__screenshots__', output.parent / 'snapshots', keep=update).start()
    try:
        code, out, err = live.sandbox.run(argv, timeout=3600, network=True, cwd='.eaos-lock',
                                          env={**live.extra(), 'BASE_URL': base, 'EAOS_LOCK_REPORT': str(output),
                                               'EAOS_LOCK_STREAM': str(stream)})
    finally:
        screens.stop()
    live.log.append({'argv': argv, 'exit': code, 'tail': (out + err)[-3000:]})     # why a spec did not run
    try: return json.loads(output.read_text(encoding='utf-8'))
    except (OSError, ValueError): return {}


def _approvals(live, lock, output, update):
    """{spec path: (status, reason)} of one run of the approval tests with EAOS's pinned pytest, in the copy and
    without network. The project's own modules import from the copy's root, never EAOS's; no pytest setting, conftest
    or plugin of the project's takes part. With `update` every interface received is approved: the recording. Each
    spec is a step of the running stage."""
    from ..core.toolchain import home
    pytest = home() / 'bin/pytest'
    if not pytest.exists(): raise RuntimeError('the approval tests need EAOS\'s pinned pytest: run `eaos tools install --only pytest`')
    names = sorted(f'approvals/{path.name}' for path in (lock / 'approvals').glob('test_*.py'))
    for name in names: progress.step(name, 0, len(names), 'waiting')
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists(): output.unlink()
    argv = [str(pytest), f'{lock.name}/approvals', '-c', f'{lock.name}/pytest.ini', '-p', 'no:cacheprovider',
            '--continue-on-collection-errors', '-q', f'--junitxml={output}']
    code, out, err = live.sandbox.run(argv, timeout=1800, env={
        **live.extra(), 'PYTHONPATH': str(Path(live.sandbox.copy).resolve()), 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
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


def _run_specs(live, lock, base, recorded, stem, update, declared=(), known=()):
    """{spec file: (status, reason)} of one pass of every spec the lock holds: the screens with Playwright, the
    interfaces of the code with pytest; their reports are playwright-<stem>.json and approvals-<stem>.xml in `recorded`."""
    statuses = {}
    if (lock / 'playwright.config.ts').is_file():
        statuses.update(spec_statuses(_pass(live, lock, base, recorded / f'playwright-{stem}.json', update=update), declared, known))
    if (lock / 'approvals').is_dir():
        statuses.update(_approvals(live, lock, recorded / f'approvals-{stem}.xml', update))
    return statuses


def _results(report, statuses):
    results = []
    for spec in json.loads((Path(report) / 'behavior-lock/plan.json').read_text(encoding='utf-8'))['specs']:
        name = Path(spec['path']).name
        status, reason = next(((s, r) for file, (s, r) in statuses.items() if Path(file).name == name),
                              ('error', 'the spec did not run') if spec['path'] else
                              ('quarantined', ('nothing to run: ' + ', '.join(spec.get('surfaces') or ['no surface']))[:300]))
        results.append({'path': spec['path'], 'status': status, **({'reason': reason} if reason else {})})
    return results


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
REPORTER = Path(__file__).resolve().parents[1] / 'templates/screens/stream-reporter.mjs'
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
FAILED_STATUSES = ('failed', 'timedOut', 'interrupted')


class Screens:
    """Follows the stream reporter's lines while one pass runs, and reports one step per spec file of the running
    stage (eaos/core/progress): running at its first test, then ok, failed or skipped once all its tests ended, with the
    seconds they took and the spec's first shot. With `keep`, the shot is copied at once to where the recording is
    kept (`snapshots`), the same file run_lock copies there after the pass. Never raises; a no-op outside a flow."""

    def __init__(self, stream, shots, snapshots, keep=False, every=0.5):
        self.stream, self.shots, self.snapshots, self.keep, self.every = Path(stream), Path(shots), Path(snapshots), keep, every
        self.offset, self.buffer = 0, b''
        self.planned, self.outcomes, self.seconds, self.finished = {}, {}, {}, []
        self.halt = threading.Event()
        self.thread = None

    def start(self):
        if progress.current() is None: return self
        self.thread = threading.Thread(target=contextvars.copy_context().run, args=(self._follow,), daemon=True,
                                       name='eaos-screens')
        self.thread.start()
        return self

    def stop(self):
        self.halt.set()
        if self.thread is not None:
            self.thread.join(timeout=5)
            self.thread = None
            try: self.read()
            except Exception: pass
        return self

    def _follow(self):
        while not self.halt.wait(self.every):
            try: self.read()
            except Exception: pass

    def read(self):
        """The lines written since the last read, each reported; a line still being written waits for its end."""
        try:
            with self.stream.open('rb') as handle:
                handle.seek(self.offset)
                chunk = handle.read()
        except OSError:
            return
        self.offset += len(chunk)
        self.buffer += chunk
        *lines, self.buffer = self.buffer.split(b'\n')
        for line in lines:
            try: row = json.loads(line)
            except ValueError: continue
            if isinstance(row, dict): self.handle(row)

    def handle(self, row):
        event, name = row.get('event'), row.get('file')
        total = len(self.planned)
        if event == 'plan':
            self.planned = {str(f): int(n) for f, n in (row.get('files') or {}).items()}
            total = len(self.planned)
            for name in self.planned: progress.step(name, 0, total, 'waiting')
        elif event == 'test.begin' and name in self.planned and name not in self.outcomes:
            self.outcomes[name] = []
            progress.step(name, len(self.finished), total, 'running')
        elif event == 'test.end' and name in self.planned and name not in self.finished:
            self.outcomes.setdefault(name, []).append((row.get('status'), row.get('error') or ''))
            self.seconds[name] = self.seconds.get(name, 0.0) + (row.get('duration') or 0) / 1000
            if len(self.outcomes[name]) < self.planned[name]: return
            self.finished.append(name)
            status, reason, code = self.verdict(self.outcomes[name])
            progress.step(name, len(self.finished), total, status, round(self.seconds[name], 2), reason, code,
                          artifact=self.shot(row.get('shots') or []))

    @staticmethod
    def verdict(outcomes):
        """(status, reason, reason_code) of one spec file, by the rule of spec_statuses()."""
        failed = [error for status, error in outcomes if status in FAILED_STATUSES]
        if failed: return 'failed', failed[0][:200], 'screen_failed'
        if any(status == 'passed' for status, _ in outcomes): return 'ok', '', ''
        return 'skipped', 'every test was skipped: it needs a fixture', 'screen_needs_fixture'

    def shot(self, shots):
        """The spec's first shot, as a path relative to the run's folder (behavior-lock/snapshots/...), or ''."""
        for name in shots:
            source = self.shots / name
            if '..' in Path(name).parts or not source.is_file(): continue
            kept = self.snapshots / name
            if self.keep:
                try:
                    kept.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, kept)
                except OSError:
                    continue
            return f'{self.snapshots.parent.name}/{self.snapshots.name}/{name}'
        return ''


def run_lock(report, target, runtime, app=None):
    """behavior-lock/results.json in `runtime`: the report's specs, run twice on the original code in the sandbox.

    The first pass records each screen as it is today and approves each interface of the code (kept in
    behavior-lock/snapshots and behavior-lock/approved for every later run); the second must match them. A spec that
    passes the second pass locks today's behaviour; one that differs between two runs of the same code is not
    deterministic and fails. Needs <runtime>/authorization.json granting S05 and <runtime>/run.json. `app`: the check's
    running app (eaos/pipeline/live_app.py shared_app), recorded on as it is, with the person's session; else its own."""
    from .run import LiveRun
    report, runtime = Path(report), Path(runtime)
    recorded = runtime / 'behavior-lock'
    if not (report / 'behavior-lock').is_dir() and not (runtime / 'run.json').is_file():     # nothing to lock, no app to crawl
        return {'results': [], 'limitations': ['the program has no feature to lock']}
    progress.begin('prepare')
    live = app[0] if app else LiveRun(target, runtime, 'S05')
    if not app: live.freeze()
    try:
        progress.begin('start')
        lock = _prepare(live, report) if (report / 'behavior-lock').is_dir() else None
        base = _shared(app, lock) if app else _start(live, lock or live.sandbox.copy / '.eaos-lock')
        if _pages_from_app(report, target, base, runtime): lock = _prepare(live, report)
        if lock is None:         # the code names no feature and the running app no page: nothing is recorded, said so
            return {'results': [], 'limitations': ['the program has no feature to lock']}
        progress.begin('record')
        _run_specs(live, lock, base, recorded, 'record', update=True)
        _keep(lock, recorded)
        progress.begin('verify')
        results = _results(report, _run_specs(live, lock, base, recorded, 'verify', update=False))
        progress.end('verify', detail={'screens': len(results), 'passed': sum(r['status'] == 'passed' for r in results)})
    finally:
        if not app: live.stop()
        live.record('behavior-lock/run-log.json')
    return _write(runtime, 'results.json', live, results)


# The journeys are kept light: at most JOURNEYS rrweb recordings of at most RECORDING_BYTES each, and a Playwright trace
# only for a failing journey, at most TRACES of them and only when it is under TRACE_BYTES; the rest are deleted and
# counted, so a large app never fills the disk with replays nobody asked for.
JOURNEYS, RECORDING_BYTES, TRACES, TRACE_BYTES = 20, 1_500_000, 3, 2_000_000


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
    return lock, recorder, _shared(app, lock) if app else _start(live, lock)


def run_journeys(report, target, runtime, folder, app=None):
    """Each page spec of the lock run once more on today's code, with rrweb recording every page and Playwright's trace
    kept for a failing journey: <folder>/rrweb/<test>.rrweb.json (the page, replayable) and <folder>/traces/<n>.zip
    (every step's picture, the network and the console of a failure), both capped (cap_journeys). Needs what run_lock
    needs; returns {specs, walked: [{spec, pages, status, reason}], failed, recordings, traces, *_dropped}."""
    from .run import LiveRun
    from ..core.toolchain import node_modules
    folder = Path(folder)
    for part in ('traces', 'rrweb', 'results'): shutil.rmtree(folder / part, ignore_errors=True)
    (folder / 'rrweb').mkdir(parents=True)
    bundle = node_modules('rrweb') / 'rrweb/dist/rrweb.umd.cjs'
    if not bundle.is_file(): raise FileNotFoundError(f'rrweb is not installed ({bundle}): python -m eaos tools install --only rrweb')
    live = app[0] if app else LiveRun(target, runtime, 'S05')
    try:
        lock, recorder, base = _journey_start(live, report, runtime, bundle, app)
        argv = ['playwright', 'test', '--config', 'lock.config.ts', '--project=lock', '--no-deps', '--workers=1',
                '--trace=retain-on-failure', '--output', str(folder / 'results')]
        code, out, err = live.sandbox.run(argv, timeout=3600, network=True, cwd='.eaos-lock', env={
            **live.extra(), 'BASE_URL': base, 'EAOS_LOCK_REPORT': str(folder / 'report.json'),
            'EAOS_LOCK_STREAM': str(folder / STREAM), 'EAOS_RRWEB': str(recorder), 'EAOS_JOURNEYS': str(folder / 'rrweb')})
        live.log.append({'argv': argv, 'exit': code, 'tail': (out + err)[-3000:]})
    finally:
        if not app: live.stop()
        live.record('behavior-lock/journeys-log.json')
    traces = sorted((folder / 'results').glob('**/trace.zip'))
    (folder / 'traces').mkdir(exist_ok=True)
    for number, trace in enumerate(traces, 1): shutil.move(str(trace), folder / 'traces' / f'{number:03d}-{trace.parent.name[:80]}.zip')
    shutil.rmtree(folder / 'results', ignore_errors=True)
    (folder / STREAM).unlink(missing_ok=True)
    return _journey_results(folder, report)


def _journey_results(folder, report):
    """The walked specs and bounded recordings, whether the app belonged to the journeys or the check."""
    statuses = spec_statuses(json.loads((folder / 'report.json').read_text(encoding='utf-8'))) if (folder / 'report.json').is_file() else {}
    plan = json.loads((Path(report) / 'behavior-lock/plan.json').read_text(encoding='utf-8'))
    pages = {Path(s['path']).name: [x for x in s.get('surfaces') or [] if not str(x).startswith(('GET ', 'POST ', 'PUT ', 'PATCH ', 'DELETE '))]
             for s in plan.get('specs') or [] if s.get('tool') == 'playwright' and s.get('path')}
    walked = [{'spec': name, 'pages': pages.get(Path(name).name, [])[:20], 'status': status, 'reason': reason[:300]}
              for name, (status, reason) in sorted(statuses.items())]
    return {'specs': len(statuses), 'walked': walked, 'failed': sum(w['status'] == 'failed' for w in walked), **cap_journeys(folder)}


def verify_lock(report, target, runtime, name='results-after', declared=(), known=()):
    """The lock recorded on the original, run once on `target` (a candidate EAOS committed on the granted commit):
    behavior-lock/<name>.json, and {specs, passed, failed}. Needs what the original recorded, screens or interfaces of
    the code. No recording is ever updated here; a screen in `declared` may look different (spec_statuses)."""
    from .run import LiveRun
    report, runtime = Path(report), Path(runtime)
    recorded = runtime / 'behavior-lock'
    if not any((recorded / kept).is_dir() for kept in ('snapshots', 'approved')):
        raise RuntimeError('nothing recorded on the original, neither a screen nor an interface of the code: '
                           'run `eaos live lock` first')
    live = LiveRun(target, runtime, 'S09')
    lock = _prepare(live, report, recorded)
    try:
        base = _start(live, lock)
        results = _results(report, _run_specs(live, lock, base, recorded, name, update=False, declared=declared, known=known))
    finally:
        live.stop()
        live.record(f'behavior-lock/run-log-{name}.json')
    _write(runtime, f'{name}.json', live, results)
    return _judged(_passed_before(runtime, results), results)


def _passed_before(runtime, results):
    """The specs that passed on the original (all of `results` when it has no record)."""
    original = runtime / 'behavior-lock/results.json'
    if not original.is_file(): return {r['path'] for r in results}
    return {r['path'] for r in json.loads(original.read_text(encoding='utf-8'))['results'] if r['status'] == 'passed'}


def _judged(passed_before, results):
    """{specs, passed, failed, already_failing}. A spec that did not pass on the original (its recording failed, or it
    never had one) cannot be broken by a change: only a spec that passed there and fails here counts against it."""
    failing = [r for r in results if r['status'] in ('failed', 'error')]
    return {'specs': len(results), 'passed': sum(r['status'] == 'passed' for r in results),
            'failed': sum(r['path'] in passed_before for r in failing),
            'already_failing': sorted(r['path'] for r in failing if r['path'] not in passed_before)}
