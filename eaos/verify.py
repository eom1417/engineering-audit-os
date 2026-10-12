"""Execution evidence: what the tests actually touch, in an isolated copy of the target.

Without this the dossier can only say what the source looks like. With it, a claim can be
CONFIRMED by something that ran, and untested critical paths stop being a guess.

    run(target, out, command)           a command run in a plain isolated copy (isolated_copy), Python coverage
    run_profile(target, out, runtime)   the check's way, once the person agreed to run their app: the run profile's own
                                        test commands (<runtime>/run.json `checks`) in the sandbox copy, Python coverage
                                        or Node's own V8 coverage (NODE_V8_COVERAGE) per file
    declared(target, out, reason)       what the files alone say: which test imports which file; nothing runs

Each writes verification.json and the `verification` fact set the dossier and the assistant read.
"""
from collections import defaultdict
import json
import os
import re
from pathlib import Path
import sys
import shutil
import subprocess
import tempfile
import time
from .facts import digest, make
from .facts.source import Source
from .facts.store import read_set, write_set

NAME = 'verification'
VERSION = '1'
from .workspace import SKIP_DIRS, write

LIMITATIONS = [
    'An isolated copy is not an operating-system sandbox; do not run untrusted projects here.',
    'Coverage reflects the command that was run, not all behaviour the system can exhibit.',
    'An uncovered line is not proof of dead code; it is proof this command did not reach it.',
    'Test discovery by path convention misses suites that do not follow it.',
    'Commands run with the interpreter running EAOS unless an absolute one is configured; a project needing its own virtualenv must configure the command explicitly.',
]
# The interpreter running EAOS is the one guaranteed to exist and to have the runtime extra
# installed. Assuming a bare `python` on PATH silently loses all execution evidence on systems
# that only ship `python3`.
INTERPRETER = sys.executable or 'python3'
DEFAULT_COMMANDS = [
    [INTERPRETER, '-m', 'pytest', '-q'],
    [INTERPRETER, '-m', 'unittest', 'discover', '-s', 'tests'],
]
INTERPRETER_NAMES = {'python', 'python3', 'py'}


def isolated_copy(target, destination):
    destination.mkdir(parents=True)
    for base, directories, names in os.walk(target):
        directories[:] = sorted(d for d in directories if d not in SKIP_DIRS and not (Path(base) / d).is_symlink())
        for name in sorted(names):
            source_path = Path(base) / name
            if source_path.is_symlink() or not source_path.is_file(): continue
            relative = source_path.relative_to(target)
            (destination / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination / relative)
    return destination


def run_command(project, argv, timeout):
    environment = {k: v for k, v in os.environ.items() if k in {'PATH', 'HOME', 'LANG', 'TMPDIR', 'SystemRoot', 'WINDIR'}}
    started = time.monotonic()
    try:
        completed = subprocess.run(argv, cwd=project, env=environment, capture_output=True, text=True,
                                   timeout=timeout, check=False)
        output, code, timed_out = (completed.stdout + completed.stderr)[-4000:], completed.returncode, False
    except subprocess.TimeoutExpired:
        output, code, timed_out = 'command exceeded its timeout', None, True
    except OSError as error:
        output, code, timed_out = 'command could not start: ' + type(error).__name__, None, False
    return {'argv': argv, 'exit_code': code, 'timed_out': timed_out,
            'duration_seconds': round(time.monotonic() - started, 2), 'output_tail': output}


def coverage_command(argv):
    """Instrument a Python command, resolving a bare interpreter name to the one actually running."""
    if not argv: return None
    head = Path(argv[0]).name
    if head not in INTERPRETER_NAMES and argv[0] != INTERPRETER: return None
    interpreter = argv[0] if Path(argv[0]).is_absolute() and Path(argv[0]).exists() else INTERPRETER
    return [interpreter, '-m', 'coverage', 'run', '--branch', *argv[1:]]


def parse_coverage(project):
    report = run_command(project, [INTERPRETER, '-m', 'coverage', 'json', '-o', '.eaos-coverage.json'], 120)
    path = project / '.eaos-coverage.json'
    if report['exit_code'] != 0 or not path.is_file(): return None, report
    data = json.loads(path.read_text())
    path.unlink(missing_ok=True)
    (project / '.coverage').unlink(missing_ok=True)
    return data, report


def discover_tests(source, sets):
    tests, covered_by = [], defaultdict(set)
    edges = {(fact['location']['path'], fact['value'].get('to_path')) for fact in sets.get('resolve', {}).get('facts', [])
             if fact['resolution'] == 'RESOLVED'}
    for item in source.readable():
        if source.category(item['path']) != 'test': continue
        tests.append(item['path'])
        for origin, destination in edges:
            if origin == item['path'] and destination: covered_by[destination].add(item['path'])
    return sorted(tests), {path: sorted(files) for path, files in covered_by.items()}


def run(target, out, command=None, timeout=900, execute=True):
    target, out = Path(target).resolve(), Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    source = Source(target)
    needed = ['syntax', 'resolve', 'entrypoints', 'graph']
    if not all((out / 'facts' / (name + '.json')).is_file() for name in needed):
        # Verification needs the graph to know which files an entry point can reach.
        from .facts.run import collect
        from .facts.run import GRAPH_PREREQUISITES
        collect(target, out, GRAPH_PREREQUISITES, source=source)
    sets = {name: read_set(out, name) for name in needed if (out / 'facts' / (name + '.json')).is_file()}
    tests, declared = discover_tests(source, sets)
    result = {'target': str(target), 'out': str(out), 'test_files': tests,
              'declared_coverage': declared, 'executed': False, 'limitations': LIMITATIONS}
    if not execute:
        result['reason'] = 'Execution was not requested; only declared (import-based) coverage is reported.'
        write(out / 'verification.json', result)
        return result
    with tempfile.TemporaryDirectory() as workspace:
        project = isolated_copy(target, Path(workspace) / 'project')
        candidates = [command] if command else DEFAULT_COMMANDS
        attempts = []
        chosen = None
        for argv in candidates:
            instrumented = coverage_command(argv)
            outcome = run_command(project, instrumented or argv, timeout)
            attempts.append(outcome)
            if outcome['exit_code'] == 0:
                chosen = outcome
                break
        result['attempts'] = attempts
        result['executed'] = chosen is not None
        if chosen is None:
            result['reason'] = 'No configured or default test command completed successfully in the isolated copy.'
            write(out / 'verification.json', result)
            return result
        data, report = parse_coverage(project)
        result['command'] = chosen['argv']
        if data is None:
            result['reason'] = 'The command ran but coverage data could not be produced; install the runtime extra.'
            write(out / 'verification.json', result)
            return result
        files = {}
        for name, entry in sorted(data.get('files', {}).items()):
            relative = Path(name).as_posix()
            if relative.startswith('./'): relative = relative[2:]
            summary = entry.get('summary', {})
            files[relative] = {'covered_lines': summary.get('covered_lines', 0),
                               'statements': summary.get('num_statements', 0),
                               'percent': round(summary.get('percent_covered', 0.0), 1),
                               'missing_lines': entry.get('missing_lines', [])[:40]}
        reachable = {fact['location']['path'] for fact in sets.get('graph', {}).get('facts', [])
                     if fact['kind'] == 'graph_node' and fact['value'].get('entry_distance') is not None}
        uncovered_critical = sorted(path for path in reachable if files.get(path, {}).get('percent', 0) == 0)
        result.update({'coverage': files,
                       'overall_percent': round(data.get('totals', {}).get('percent_covered', 0.0), 1),
                       'entry_reachable_files': len(reachable),
                       'uncovered_entry_reachable_files': uncovered_critical})
    write(out / 'verification.json', result)
    publish_facts(out, result)
    return result


TEST_WORDS = re.compile(r'(^|[^a-z])(test|tests|pytest|unittest|vitest|jest|mocha)([^a-z]|$)')


def test_commands(profile):
    """The run profile's checks that run tests (npm test, pytest, vitest...), not its typecheck or lint."""
    return [argv for argv in (profile or {}).get('checks') or [] if any(TEST_WORDS.search(str(part).lower()) for part in argv)]


def declared(target, out, reason, source=None):
    """verification.json with only the declared coverage (which test file imports which file) and `reason`: why
    nothing ran. Overwrites a record an earlier check left, which would otherwise speak for this one."""
    target, out = Path(target).resolve(), Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    sets = {name: read_set(out, name) for name in ('resolve',) if (out / 'facts' / (name + '.json')).is_file()}
    tests, covered = discover_tests(source or Source(target), sets)
    result = {'target': str(target), 'out': str(out), 'test_files': tests, 'declared_coverage': covered, 'executed': False,
              'reason': reason, 'limitations': LIMITATIONS}
    write(out / 'verification.json', result)
    return result


def v8_coverage(folder, root):
    """{path: {functions, functions_hit, percent}} from Node's V8 coverage files in `folder`, for the project's own
    source files under `root` (the sandbox copy): a function counts as run when its outermost range ran."""
    from .vocabulary import classify
    root = Path(root).resolve().as_posix().rstrip('/') + '/'
    files = {}
    for path in sorted(Path(folder).glob('*.json')):
        try: scripts = json.loads(path.read_text(encoding='utf-8')).get('result') or []
        except (OSError, ValueError): continue
        for script in scripts:
            url = str(script.get('url') or '')
            name = url[len('file://'):] if url.startswith('file://') else url
            if not name.startswith(root) or '/node_modules/' in name: continue
            relative = name[len(root):].split('?')[0]
            if classify(relative) != 'source': continue
            row = files.setdefault(relative, {'functions': 0, 'functions_hit': 0})
            for function in script.get('functions') or []:
                ranges = function.get('ranges') or []
                if not ranges or not function.get('functionName'): continue
                row['functions'] += 1
                row['functions_hit'] += ranges[0].get('count', 0) > 0
    return {path: {**row, 'percent': round(100 * row['functions_hit'] / row['functions'], 1) if row['functions'] else 100.0}
            for path, row in files.items()}


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
        try: script = json.loads((Path(app) / 'package.json').read_text(encoding='utf-8'))['scripts']['test']
        except (OSError, ValueError, KeyError, TypeError): script = ''
        runner = next((r for r in ('vitest', 'jest') if r in script), None)
        return [*argv, '--', *TIMING[runner]] if runner else argv
    return [*argv, *TIMING[runner]] if runner else argv


def test_times(app):
    """[(test, file, seconds)] from a JUnit XML (pytest) or a Jest-format JSON (vitest, jest) report, if one was written."""
    rows, app = [], Path(app)
    junit = app / '.eaos-junit.xml'
    if junit.is_file():
        import xml.etree.ElementTree as ET
        for case in ET.parse(junit).iter('testcase'):
            rows.append((f"{case.get('classname', '')}::{case.get('name', '')}", case.get('file') or case.get('classname', ''),
                         float(case.get('time') or 0)))
    report = app / '.eaos-tests.json'
    if report.is_file():
        for suite in json.loads(report.read_text(encoding='utf-8')).get('testResults') or []:
            for case in suite.get('assertionResults') or []:
                rows.append((case.get('fullName') or case.get('title') or '', os.path.relpath(suite.get('name') or '', app),
                             (case.get('duration') or 0) / 1000))
    return rows


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



def run_profile(target, out, runtime, timeout=1800):
    """The run profile's test commands in the sandbox copy (eaos/live_run.py), with coverage: verification.json and the
    `verification` facts. Raises LookupError when the profile names no test command. The project's own interpreter
    and test runner are used as the profile declares them; Python commands run under `-m coverage` when the project
    has coverage installed, and every command runs with NODE_V8_COVERAGE, which Node fills on its own."""
    from .live_run import LiveRun
    target, out, runtime = Path(target).resolve(), Path(out).resolve(), Path(runtime)
    out.mkdir(parents=True, exist_ok=True)
    live = LiveRun(target, runtime, 'S05')
    commands = test_commands(live.profile)
    if not commands: raise LookupError("the run profile's checks name no test command")
    v8 = runtime / 'verify-v8'
    shutil.rmtree(v8, ignore_errors=True)
    v8.mkdir(parents=True)
    source = Source(target)
    sets = {name: read_set(out, name) for name in ('resolve', 'graph') if (out / 'facts' / (name + '.json')).is_file()}
    tests, covered = discover_tests(source, sets)
    result = {'target': str(target), 'out': str(out), 'test_files': tests, 'declared_coverage': covered,
              'executed': False, 'limitations': LIMITATIONS, 'attempts': []}
    files, python, contexts = {}, None, {}
    try:
        live.setup()
        app = live.sandbox.copy / (live.profile.get('app') or '')
        (app / '.eaos-coveragerc').write_text(COVERAGERC, encoding='utf-8')
        for argv in commands:
            started = time.monotonic()
            run_argv = argv
            if Path(str(argv[0])).name in INTERPRETER_NAMES and live.run([argv[0], '-c', 'import coverage'], timeout=60)[0] == 0:
                run_argv, python = [argv[0], '-m', 'coverage', 'run', '--rcfile=.eaos-coveragerc', *argv[1:]], argv[0]
            run_argv = with_timing(run_argv, app)
            code, stdout, stderr = live.run(run_argv, timeout=timeout, env={'NODE_V8_COVERAGE': str(v8)})
            result['attempts'].append({'argv': [str(a) for a in argv], 'exit_code': code, 'timed_out': f'stopped after {timeout}s' in stderr,
                                       'duration_seconds': round(time.monotonic() - started, 2), 'output_tail': (stdout + stderr)[-2000:]})
        if python:
            code, _, _ = live.run([python, '-m', 'coverage', 'json', '--rcfile=.eaos-coveragerc', '--show-contexts', '-o', '.eaos-coverage.json'],
                                  timeout=300)
            report = app / '.eaos-coverage.json'
            if code == 0 and report.is_file():
                prefix = Path(live.profile.get('app') or '.').as_posix().strip('./')
                for name, entry in json.loads(report.read_text(encoding='utf-8')).get('files', {}).items():
                    for line, tests in (entry.get('contexts') or {}).items():
                        for test in tests:
                            if test: contexts.setdefault(test, set()).add((name, line))
                    relative = Path(name).as_posix().removeprefix('./')
                    relative = f'{prefix}/{relative}' if prefix else relative
                    summary = entry.get('summary', {})
                    files[relative] = {'covered_lines': summary.get('covered_lines', 0), 'statements': summary.get('num_statements', 0),
                                       'percent': round(summary.get('percent_covered', 0.0), 1)}
        result['suite'] = suite_health(app, contexts)
        for path, row in v8_coverage(v8, live.sandbox.copy).items():
            files.setdefault(path, {'covered_lines': row['functions_hit'], 'statements': row['functions'], 'percent': row['percent'],
                                    'unit': 'functions'})
    finally:
        live.stop()
        live.record('verify-log.json')
        shutil.rmtree(v8, ignore_errors=True)
    result['executed'] = bool(result['attempts'])
    result['command'] = [str(a) for a in commands[0]]
    result['passed'] = all(a['exit_code'] == 0 for a in result['attempts'])
    if files:
        reachable = {fact['location']['path'] for fact in sets.get('graph', {}).get('facts', [])
                     if fact['kind'] == 'graph_node' and fact['value'].get('entry_distance') is not None}
        total = sum(row['statements'] or 0 for row in files.values())
        result.update({'coverage': dict(sorted(files.items())),
                       'overall_percent': round(100 * sum(row['covered_lines'] or 0 for row in files.values()) / total, 1) if total else 0.0,
                       'entry_reachable_files': len(reachable),
                       'uncovered_entry_reachable_files': sorted(p for p in reachable if files.get(p, {}).get('percent', 0) == 0)})
    else:
        result['reason'] = ('The tests ran, but no coverage could be read from them (no Python coverage module in the project, '
                            'and no Node process wrote V8 coverage).')
    write(out / 'verification.json', result)
    publish_facts(out, result)
    return result


def publish_facts(out, result):
    """Execution results become facts so a claim can cite something that actually ran."""
    facts = []
    fingerprint = digest(json.dumps(result.get('command') or [], sort_keys=True).encode('utf-8'))
    for path, value in sorted((result.get('coverage') or {}).items()):
        facts.append(make('coverage_hit', NAME, VERSION, fingerprint, {'path': path},
                          {'percent': value['percent'], 'covered_lines': value['covered_lines'],
                           'statements': value['statements'], 'executed': value['percent'] > 0},
                          limitations=LIMITATIONS))
    measured = set(result.get('coverage') or {})
    for path in result.get('uncovered_entry_reachable_files', []):
        if path in measured: continue
        # A file the run never imported has no coverage row; record the absence as a fact of its own.
        facts.append(make('coverage_hit', NAME, VERSION, fingerprint, {'path': path},
                          {'percent': 0.0, 'covered_lines': 0, 'statements': None, 'executed': False,
                           'note': 'Not imported by the executed command; no coverage row was produced.'},
                          limitations=LIMITATIONS))
    facts.sort(key=lambda fact: fact['location']['path'])
    summary = {'executed': result.get('executed', False), 'command': result.get('command'),
               'overall_percent': result.get('overall_percent'),
               'test_files': len(result.get('test_files', [])),
               'uncovered_entry_reachable_files': result.get('uncovered_entry_reachable_files', []),
               'interpretation': 'Coverage of the command that ran. Not proof of correctness, and not proof that uncovered code is dead.'}
    write_set(out, NAME, NAME, VERSION, facts, fingerprint, LIMITATIONS, summary,
              available=bool(result.get('executed')), reason=result.get('reason'))
    return facts
