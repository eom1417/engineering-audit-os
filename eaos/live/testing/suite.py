"""A test suite's health (eaos/live/testing/verify.py run_profile measures it): each test's time, from the runner's own report
switched on for the run, and the tests that run no line another test does not run too, from Coverage.py's dynamic
contexts."""
import json
import os
from collections import defaultdict
from pathlib import Path

# Per-test measurements, read from the runners' own reports and Coverage.py's "who tests what" (dynamic contexts):
# how long each test takes, and which tests run no line another test does not run too (redundant).
COVERAGERC = '[run]\nbranch = True\ndynamic_context = test_function\n'
TIMING = {'pytest': ['--junitxml=.eaos-junit.xml'], 'vitest': ['--reporter=default', '--reporter=json', '--outputFile.json=.eaos-tests.json'],
          'jest': ['--json', '--outputFile=.eaos-tests.json']}


def with_timing(argv, app):
    """The test command with its runner's own per-test report switched on; `npm test` passes it through `--`."""
    words = [Path(str(a)).name for a in argv]
    runner = next((r for r in TIMING if any(w == r or w.startswith(r + '.') for w in words)), None)
    if runner is None and words[:2] in (['npm', 'test'], ['npm', 'run']):
        runner = _npm_test_runner(app)
        return [*argv, '--', *TIMING[runner]] if runner else argv
    return [*argv, *TIMING[runner]] if runner else argv


def _npm_test_runner(app):
    """The runner (vitest or jest) the app's npm test script calls, or None."""
    try: script = json.loads((Path(app) / 'package.json').read_text(encoding='utf-8'))['scripts']['test']
    except (OSError, ValueError, KeyError, TypeError): script = ''
    return next((r for r in ('vitest', 'jest') if r in script), None)


def test_times(app):
    """[(test, file, seconds)] from a JUnit XML (pytest) or a Jest-format JSON (vitest, jest) report, if one was written."""
    app = Path(app)
    return _junit_times(app / '.eaos-junit.xml') + _jest_times(app / '.eaos-tests.json', app)


def _junit_times(junit):
    if not junit.is_file(): return []
    from defusedxml import ElementTree as ET       # a report the project's tests wrote: no entities
    return [(f"{case.get('classname', '')}::{case.get('name', '')}", case.get('file') or case.get('classname', ''), float(case.get('time') or 0))
            for case in ET.parse(junit).iter('testcase')]


def _jest_times(report, app):
    if not report.is_file(): return []
    return [(case.get('fullName') or case.get('title') or '', os.path.relpath(suite.get('name') or '', app), (case.get('duration') or 0) / 1000)
            for suite in json.loads(report.read_text(encoding='utf-8')).get('testResults') or []
            for case in suite.get('assertionResults') or []]


def redundant_tests(contexts):
    """The tests every line of which another test also runs: {test: lines} from Coverage.py's contexts."""
    runs = defaultdict(int)
    for lines in contexts.values():
        for line in lines: runs[line] += 1
    return sorted(test for test, lines in contexts.items() if lines and all(runs[line] > 1 for line in lines))


def suite_health(app, contexts):
    """What the person's assistant judges the test suite on: its size, its time, its slowest and its redundant tests."""
    times = test_times(app)
    redundant = redundant_tests(contexts)
    total = sum(seconds for _, _, seconds in times)
    return {'tests': len(times) or len(contexts), 'seconds': round(total, 1),
            'slowest': [{'test': t, 'file': f, 'seconds': round(s, 2)} for t, f, s in sorted(times, key=lambda r: -r[2])[:10]],
            'redundant': redundant[:30], 'redundant_count': len(redundant),
            'redundant_share': round(len(redundant) / len(contexts), 3) if contexts else None,
            'source': 'the runner\'s own per-test report; Coverage.py dynamic contexts (dynamic_context = test_function)'}
