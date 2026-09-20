"""Execution evidence: what the tests actually touch, in an isolated copy of the target.

Without this the dossier can only say what the source looks like. With it, a claim can be
CONFIRMED by something that ran, and untested critical paths stop being a guess.
"""
from collections import defaultdict
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from .facts import digest, make
from .facts.source import Source
from .facts.store import read_set, write_set

NAME = 'verification'
VERSION = '1'
from .workspace import SKIP_DIRS, read, write

LIMITATIONS = [
    'An isolated copy is not an operating-system sandbox; do not run untrusted projects here.',
    'Coverage reflects the command that was run, not all behaviour the system can exhibit.',
    'An uncovered line is not proof of dead code; it is proof this command did not reach it.',
    'Test discovery by path convention misses suites that do not follow it.',
]
DEFAULT_COMMANDS = [
    ['python', '-m', 'pytest', '-q'],
    ['python', '-m', 'unittest', 'discover', '-s', 'tests'],
]


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
    return ['python', '-m', 'coverage', 'run', '--branch', *argv[1:]] if argv[:1] == ['python'] else None


def parse_coverage(project):
    report = run_command(project, ['python', '-m', 'coverage', 'json', '-o', '.eaos-coverage.json'], 120)
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
        collect(target, out, ['syntax', 'resolve', 'entrypoints', 'config', 'metrics', 'history', 'graph'], source=source)
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
