"""Execution evidence: what the tests actually touch, in an isolated copy of the target.

Without this the dossier can only say what the source looks like. With it, a claim can be
CONFIRMED by something that ran, and untested critical paths stop being a guess.

    run(target, out, command)           a command run in a plain isolated copy (isolated_copy), Python coverage
    run_profile(target, out, runtime)   the check's way, once the person agreed to run their app: the run profile's own
                                        test commands (<runtime>/run.json `checks`) in the sandbox copy, Python coverage
                                        or Node's own V8 coverage (NODE_V8_COVERAGE) per file
    declared(target, out, reason)       what the files alone say: which test imports which file; nothing runs

Each writes verification.json and the `verification` fact set the dossier and the assistant read; run_profile also
measures the suite's health (eaos/live/testing/suite.py).
"""
from collections import defaultdict
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from ...facts import digest, make
from ...facts.source import Source
from ...facts.store import read_set, write_set
from .python_suite import DEFAULT_COMMANDS, INTERPRETER, command as _python_suite

NAME = 'verification'
VERSION = '1'
from ...core.project.workspace import SKIP_DIRS, write
from .suite import COVERAGERC, suite_health, with_timing

LIMITATIONS = [
    'An isolated copy is not an operating-system sandbox; do not run untrusted projects here.',
    'Coverage reflects the command that was run, not all behaviour the system can exhibit.',
    'An uncovered line is not proof of dead code; it is proof this command did not reach it.',
    'Test discovery by path convention misses suites that do not follow it.',
    'Commands run with the interpreter running EAOS unless an absolute one is configured; a project needing its own virtualenv must configure the command explicitly.',
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
        completed = subprocess.run(argv, cwd=project, env=environment, capture_output=True, text=True,  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- the project's own declared command, a list argv, run in its isolated copy with the person's consent, no shell
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
        from ...facts.run import collect
        from ...facts.run import GRAPH_PREREQUISITES
        collect(target, out, GRAPH_PREREQUISITES, source=source)
    sets = _read_sets(out, needed)
    tests, declared = discover_tests(source, sets)
    result = {'target': str(target), 'out': str(out), 'test_files': tests,
              'declared_coverage': declared, 'executed': False, 'limitations': LIMITATIONS}
    if not execute:
        result['reason'] = 'Execution was not requested; only declared (import-based) coverage is reported.'
        write(out / 'verification.json', result)
        return result
    with tempfile.TemporaryDirectory() as workspace:
        project = isolated_copy(target, Path(workspace) / 'project')
        attempts, chosen = _first_passing(project, [command] if command else DEFAULT_COMMANDS, timeout)
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
        files = _coverage_rows(data)
        reachable = _reachable(sets)
        result.update({'coverage': files,
                       'overall_percent': round(data.get('totals', {}).get('percent_covered', 0.0), 1),
                       'entry_reachable_files': len(reachable),
                       'uncovered_entry_reachable_files': _uncovered(reachable, files)})
    write(out / 'verification.json', result)
    publish_facts(out, result)
    return result


def _read_sets(out, names):
    """{name: fact set} of the `names` the report holds."""
    return {name: read_set(out, name) for name in names if (out / 'facts' / (name + '.json')).is_file()}


def _first_passing(project, candidates, timeout):
    """(every attempt, the first that passed or None): the commands run in order until one passes."""
    attempts = []
    for argv in candidates:
        outcome = run_command(project, coverage_command(argv) or argv, timeout)
        attempts.append(outcome)
        if outcome['exit_code'] == 0: return attempts, outcome
    return attempts, None


def _coverage_rows(data):
    """{path: covered lines, statements, percent, missing lines} from a Coverage.py JSON report."""
    files = {}
    for name, entry in sorted(data.get('files', {}).items()):
        relative = Path(name).as_posix()
        if relative.startswith('./'): relative = relative[2:]
        summary = entry.get('summary', {})
        files[relative] = {'covered_lines': summary.get('covered_lines', 0),
                           'statements': summary.get('num_statements', 0),
                           'percent': round(summary.get('percent_covered', 0.0), 1),
                           'missing_lines': entry.get('missing_lines', [])[:40]}
    return files


def _reachable(sets):
    """The files an entry point can reach, from the graph facts."""
    return {fact['location']['path'] for fact in sets.get('graph', {}).get('facts', [])
            if fact['kind'] == 'graph_node' and fact['value'].get('entry_distance') is not None}


def _uncovered(reachable, files):
    return sorted(path for path in reachable if files.get(path, {}).get('percent', 0) == 0)


TEST_WORDS = re.compile(r'(^|[^a-z])(test|tests|pytest|unittest|vitest|jest|mocha)([^a-z]|$)')


def python_tests(target, profile=None):
    """[the command that runs a Python project's own tests from its root] (python_suite.py), as the coverage stage and
    the batch gates (eaos/journeys/fix/execute.py) run them; [] without any, or when the run profile runs a suite."""
    if any(Path(str(argv[0])).name in INTERPRETER_NAMES for argv in test_commands(profile)): return []   # the profile runs them
    found = _python_suite(target)
    return [found] if found else []


def test_commands(profile):
    """The run profile's checks that run tests (npm test, pytest, vitest...), not its typecheck or lint."""
    return [argv for argv in (profile or {}).get('checks') or [] if any(TEST_WORDS.search(str(part).lower()) for part in argv)]


def declared(target, out, reason, source=None):
    """verification.json with only the declared coverage (which test file imports which file) and `reason`: why
    nothing ran. Overwrites a record an earlier check left, which would otherwise speak for this one."""
    target, out = Path(target).resolve(), Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    sets = _read_sets(out, ('resolve',))
    tests, covered = discover_tests(source or Source(target), sets)
    result = {'target': str(target), 'out': str(out), 'test_files': tests, 'declared_coverage': covered, 'executed': False,
              'reason': reason, 'limitations': LIMITATIONS}
    write(out / 'verification.json', result)
    return result


def v8_coverage(folder, root):
    """{path: {functions, functions_hit, percent}} from Node's V8 coverage files in `folder`, for the project's own
    source files under `root` (the sandbox copy): a function counts as run when its outermost range ran."""
    root = Path(root).resolve().as_posix().rstrip('/') + '/'
    files = {}
    for path in sorted(Path(folder).glob('*.json')):
        try: scripts = json.loads(path.read_text(encoding='utf-8')).get('result') or []
        except (OSError, ValueError): continue
        for script in scripts:
            relative = _own_source(script, root)
            if relative: _count_functions(files.setdefault(relative, {'functions': 0, 'functions_hit': 0}), script)
    return {path: {**row, 'percent': round(100 * row['functions_hit'] / row['functions'], 1) if row['functions'] else 100.0}
            for path, row in files.items()}


def _own_source(script, root):
    """The script's path relative to `root` when it is one of the project's own source files, else None."""
    from ...core.contracts.vocabulary import classify
    url = str(script.get('url') or '')
    name = url[len('file://'):] if url.startswith('file://') else url
    if not name.startswith(root) or '/node_modules/' in name: return None
    relative = name[len(root):].split('?')[0]
    return relative if classify(relative) == 'source' else None


def _count_functions(row, script):
    """Add a script's named functions to its row, and those whose outermost range ran."""
    for function in script.get('functions') or []:
        ranges = function.get('ranges') or []
        if not ranges or not function.get('functionName'): continue
        row['functions'] += 1
        row['functions_hit'] += ranges[0].get('count', 0) > 0


def run_profile(target, out, runtime, timeout=1800):
    """The run profile's test commands in the sandbox copy (eaos/live/app/run.py), with coverage: verification.json and the
    `verification` facts. Raises LookupError when the profile names no test command. The project's own interpreter
    and test runner are used as the profile declares them; Python commands run under `-m coverage` when the project
    has coverage installed, and every command runs with NODE_V8_COVERAGE, which Node fills on its own."""
    from ..app.run import LiveRun, load_profile
    target, out, runtime = Path(target).resolve(), Path(out).resolve(), Path(runtime)
    out.mkdir(parents=True, exist_ok=True)
    profile = load_profile(runtime)
    suites = _suites(target, profile)
    if not suites: raise LookupError("the run profile's checks name no test command, and no Python suite was found")
    live = LiveRun(target, runtime, 'S05', apart='tests')     # its own database: it runs beside the page stages
    v8 = runtime / 'verify-v8'
    shutil.rmtree(v8, ignore_errors=True)
    v8.mkdir(parents=True)
    source = Source(target)
    sets = _read_sets(out, ('resolve', 'graph'))
    tests, covered = discover_tests(source, sets)
    result = {'target': str(target), 'out': str(out), 'test_files': tests, 'declared_coverage': covered,
              'executed': False, 'limitations': LIMITATIONS, 'attempts': []}
    files, health = {}, []
    try:
        live.setup()
        for suite in suites:
            at_root = suite[1]
            folder = live.sandbox.copy / ('' if at_root else live.profile.get('app') or '')
            (folder / '.eaos-coveragerc').write_text(COVERAGERC, encoding='utf-8')
            python, ran = _run_tests(live, suite, folder, v8, timeout)
            result['attempts'] += ran
            covered, contexts = _python_coverage(live, python, folder, at_root) if python else ({}, {})
            files.update(covered)
            health.append(suite_health(folder, contexts))
        result['suite'] = _one_suite(health)
        for path, row in v8_coverage(v8, live.sandbox.copy).items():
            files.setdefault(path, {'covered_lines': row['functions_hit'], 'statements': row['functions'], 'percent': row['percent'],
                                    'unit': 'functions'})
    finally:
        live.stop()
        live.record('verify-log.json')
        shutil.rmtree(v8, ignore_errors=True)
    result['executed'] = bool(result['attempts'])
    result['command'] = [str(a) for a in suites[0][0][0]]
    result['passed'] = all(a['exit_code'] == 0 for a in result['attempts'])
    if files: result.update(_coverage_summary(files, sets))
    else:
        result['reason'] = ('The tests ran, but no coverage could be read from them (no Python coverage module in the project, '
                            'and no Node process wrote V8 coverage).')
    write(out / 'verification.json', result)
    publish_facts(out, result)
    return result


def _suites(target, profile):
    """[(test commands, run from the root)] of the project's suites: the profile's tests, and a Python suite beside it."""
    # The profile's tests run in the app's folder; a Python suite beside it (eaos/journeys/fix/execute.py python_tests) from the root.
    return [(group, at_root) for group, at_root in ((test_commands(profile), False), (python_tests(target, profile), True)) if group]


def _one_suite(suites):
    """The health of every suite the project has, as one: their tests and time added, the slowest and redundant of all."""
    if len(suites) == 1: return suites[0]
    slowest = sorted((row for s in suites for row in s['slowest']), key=lambda row: -row['seconds'])[:10]
    redundant = [row for s in suites for row in s['redundant']]
    tests, count = sum(s['tests'] for s in suites), sum(s['redundant_count'] for s in suites)
    return {**suites[0], 'tests': tests, 'seconds': round(sum(s['seconds'] for s in suites), 1), 'slowest': slowest,
            'redundant': redundant[:30], 'redundant_count': count, 'redundant_share': round(count / tests, 3) if tests else None}


def _run_tests(live, suite, app, v8, timeout):
    """Run each test command of `suite` ((commands, run from the root), _suites) in the sandbox, Python ones under
    coverage when the project has it, each with its runner's per-test report and Node's V8 coverage on. (The Python
    that ran coverage or None, a row per run.)"""
    (commands, at_root), python, attempts = suite, None, []
    for argv in commands:
        started = time.monotonic()
        run_argv = argv
        if Path(str(argv[0])).name in INTERPRETER_NAMES | {Path(INTERPRETER).name} and live.run([argv[0], '-c', 'import coverage'], timeout=60, at_root=at_root)[0] == 0:
            run_argv, python = [argv[0], '-m', 'coverage', 'run', '--rcfile=.eaos-coveragerc', *argv[1:]], argv[0]
        code, stdout, stderr = live.run(with_timing(run_argv, app), timeout=timeout, env={'NODE_V8_COVERAGE': str(v8)}, at_root=at_root)
        attempts.append({'argv': [str(a) for a in argv], 'exit_code': code, 'timed_out': f'stopped after {timeout}s' in stderr,
                         'duration_seconds': round(time.monotonic() - started, 2), 'output_tail': (stdout + stderr)[-2000:]})
    return python, attempts


def _python_coverage(live, python, app, at_root=False):
    """({path: coverage row}, {test: lines it ran}) from Coverage.py's report with its contexts; empty when none was made."""
    files, contexts = {}, {}
    code, _, _ = live.run([python, '-m', 'coverage', 'json', '--rcfile=.eaos-coveragerc', '--show-contexts', '-o', '.eaos-coverage.json'],
                          timeout=300, at_root=at_root)
    report = app / '.eaos-coverage.json'
    if code != 0 or not report.is_file(): return files, contexts
    prefix = '' if at_root else Path(live.profile.get('app') or '.').as_posix().strip('./')
    for name, entry in json.loads(report.read_text(encoding='utf-8')).get('files', {}).items():
        for line, tests in (entry.get('contexts') or {}).items():
            for test in filter(None, tests): contexts.setdefault(test, set()).add((name, line))
        relative = Path(name).as_posix().removeprefix('./')
        relative = f'{prefix}/{relative}' if prefix else relative
        summary = entry.get('summary', {})
        files[relative] = {'covered_lines': summary.get('covered_lines', 0), 'statements': summary.get('num_statements', 0),
                           'percent': round(summary.get('percent_covered', 0.0), 1)}
    return files, contexts


def _coverage_summary(files, sets):
    """The coverage fields of verification.json: per file, overall, and the entry-reachable files no test ran."""
    reachable = _reachable(sets)
    total = sum(row['statements'] or 0 for row in files.values())
    return {'coverage': dict(sorted(files.items())),
            'overall_percent': round(100 * sum(row['covered_lines'] or 0 for row in files.values()) / total, 1) if total else 0.0,
            'entry_reachable_files': len(reachable),
            'uncovered_entry_reachable_files': _uncovered(reachable, files)}


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
    write_set(out, NAME, NAME, VERSION, LIMITATIONS, {'facts': facts, 'input_sha': fingerprint, 'summary': summary,
                                                     'available': bool(result.get('executed')), 'reason': result.get('reason')})
    return facts
