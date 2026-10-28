"""What a behaviour lock's pass says, spec by spec (eaos/live/behavior/lock.py runs the passes): read from its reports
once it ended (Playwright's JSON, pytest's JUnit XML), and followed live from EAOS's stream reporter while it runs
(Screens), by one rule: a spec passes when none of its tests failed and at least one ran."""
import contextvars
import json
import re
import shutil
import threading
from pathlib import Path

from ...core import progress
from ...core.system.files import read_json

SCREENSHOT = re.compile(r'toHaveScreenshot.*?Snapshot: ([\w.-]+)\.png', re.S)
WORDS = re.compile(r'([\w.-]+)\.text\.txt')      # a screen's words differ (specs.py): a design card may change them too
ANSI = re.compile(r'\x1b\[[0-9;]*m')
FAILED_STATUSES = ('failed', 'timedOut', 'interrupted')


def failing_tests(runtime, name):
    """The titles of the screen tests that failed in the lock run `name` (behavior-lock/playwright-<name>.json), and in its
    passes as each kind of user (playwright-<name>@<kind>.json)."""
    found = set()
    for path in sorted((Path(runtime) / 'behavior-lock').glob(f'playwright-{name}*.json')):
        if path.stem == f'playwright-{name}' or path.stem.startswith(f'playwright-{name}@'): found |= _failed_titles(path)
    return found


def _failed_titles(path):
    report = read_json(path)
    if report is None: return set()
    found = set()

    def walk(suite):
        for spec in suite.get('specs') or []:
            if any(status in ('failed', 'timedOut') for status, _ in _outcomes(spec, ((), None, ''))): found.add(spec.get('title'))
        for child in suite.get('suites') or []: walk(child)
    for suite in report.get('suites') or []: walk(suite)
    return found


def _declared(status, message, declared, intended=(None, '')):
    """A test failed only because its screen looks different, on a screen the batch's design cards say they change
    (`declared` snapshot names, eaos/journeys/fix/waves/ declared_screens): their change, not a breakage. `intended`:
    (the pass's Intended or None, the spec file): on a screen a card declares it changes, only its declared addition
    passes (eaos/live/behavior/intended.py judged)."""
    said = ANSI.sub('', message or '')
    found = (SCREENSHOT.search(said) or WORDS.search(said)) if status == 'failed' else None
    if not found: return status
    if '*' in declared or found.group(1) in declared: return 'passed'
    from .intended import judged
    return 'passed' if intended[0] and judged(intended[1], found.group(1), said, intended[0]) else status


def spec_statuses(report, declared=(), known=(), intended=None):
    """{spec path: (status, reason)} from a Playwright JSON report: a spec passes when none of its tests failed
    and at least one ran; one whose every test was skipped is quarantined with the skip's reason. `intended`: the pass's
    declared changes (eaos/live/behavior/intended.py for_pass), or None."""
    found = {}

    def walk(suite, file=None):
        file = suite.get('file') or file
        for spec in suite.get('specs') or []:
            found.setdefault(file, []).extend(_outcomes(spec, (declared, intended, file), spec.get('title') in known))
        for child in suite.get('suites') or []: walk(child, file)
    for suite in report.get('suites') or []: walk(suite)
    return _verdicts(found)


def _outcomes(spec, declared, known=False):
    """[(status, message)] of one spec's tests; a test that never ran, skipped with its reason. `declared`: (the declared
    screens, the pass's Intended or None, the spec file). `known`: it fails on the code before the batch too
    (eaos/journeys/fix/waves/ _against_control), so it says nothing of the batch."""
    tests = spec.get('tests') or []
    ran = _ran(tests)
    screens, intended, file = declared
    return ([('passed' if known else _declared(status, message, screens, (intended, file)), message) for status, message in ran] or
            [('skipped', (test.get('annotations') or [{}])[0].get('description', '')) for test in tests])


def _ran(tests):
    """[(status, message)] of every result of the tests that ran."""
    return [(result.get('status'), ANSI.sub('', (result.get('error') or {}).get('message', ''))) for test in tests for result in test.get('results') or []]


def _verdicts(found):
    """{spec file: (status, reason)} from {spec file: [(test status, message)]}, by the rule of spec_statuses()."""
    return {file: _spec_status(outcomes) for file, outcomes in found.items()}


def _spec_status(outcomes):
    failed = [message for status, message in outcomes if status in FAILED_STATUSES]
    if failed: return 'failed', failed[0][:300]
    if any(status == 'passed' for status, _ in outcomes): return 'passed', ''
    return 'quarantined', 'every test was skipped: ' + (next((m for s, m in outcomes if m), '') or 'needs a fixture')


def approval_statuses(junit):
    """{spec path: (status, reason)} from pytest's JUnit XML report of the approval tests, by the rule of
    spec_statuses(); a test file that could not even be imported fails with its error."""
    from defusedxml import DefusedXmlException, ElementTree      # a report the project's tests wrote: no entities
    try: cases = list(ElementTree.parse(junit).getroot().iter('testcase'))
    except (OSError, ElementTree.ParseError, DefusedXmlException): return {}
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
        if event == 'plan': self._plan(row)
        elif event == 'test.begin' and name in self.planned and name not in self.outcomes: self._begin(name)
        elif event == 'test.end' and name in self.planned and name not in self.finished: self._end(name, row)

    def _plan(self, row):
        """The spec files of the pass and their test counts, each a step waiting."""
        self.planned = {str(f): int(n) for f, n in (row.get('files') or {}).items()}
        for name in self.planned: progress.step(name, 0, len(self.planned), 'waiting')

    def _begin(self, name):
        """A spec file's first test began: its step runs."""
        self.outcomes[name] = []
        progress.step(name, len(self.finished), len(self.planned), 'running')

    def _end(self, name, row):
        """A test of a spec file ended; once all of them did, its step's verdict, seconds and first shot."""
        self.outcomes.setdefault(name, []).append((row.get('status'), row.get('error') or ''))
        self.seconds[name] = self.seconds.get(name, 0.0) + (row.get('duration') or 0) / 1000
        if len(self.outcomes[name]) < self.planned[name]: return
        self.finished.append(name)
        status, reason, code = self.verdict(self.outcomes[name])
        progress.step(name, len(self.finished), len(self.planned), status, round(self.seconds[name], 2), reason, code,
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
