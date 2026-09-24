"""Acceptance checks the planner owns, run by a task's `acceptance` command after `measure` has audited the corpus.

A task written to be executed by any model cannot be accepted by a test that same model writes: it could
write one that passes. These checks read what the audit actually produced on every corpus project, and the
tests under acceptance/ are written with the plan and locked by acceptance/LOCK.json.

Usage (run `python tools/north_star.py measure` first, so the reports are current):
  python tools/acceptance.py adapter NAME                 # NAME observed on every corpus project it applies to,
                                                          # with a contract sample in tests/contracts/NAME.json
  python tools/acceptance.py contract NAME [--where EXPR] # artifact NAME present and valid in every report;
                                                          # EXPR is a Python expression over `data`
  python tools/acceptance.py emitted PREFIX [PREFIX ...]  # handover/validation.json has files under each
                                                          # PREFIX in every report, and their tool accepted all
  python tools/acceptance.py file PATH                    # PATH exists in every report
  python tools/acceptance.py facts KIND PROJECT [--min N]  # the audit of PROJECT holds at least N (default 1) facts of KIND
  python tools/acceptance.py dsl PATH [--names FIELD]     # PATH is a balanced Structurizr workspace, naming every
                                                          # target-architecture.json FIELD[].name when given
  python tools/acceptance.py test NAME                    # run acceptance/test_NAME.py, after checking the lock
  python tools/acceptance.py lock --check                 # acceptance/ matches acceptance/LOCK.json
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import north_star_measure as measure  # noqa: E402
from contracts import contracts, load_valid, validate  # noqa: E402

LOCK = ROOT / 'acceptance/LOCK.json'


def record():
    return json.loads((ROOT / 'docs/north-star.json').read_text(encoding='utf-8'))


def projects():
    """(name, report dir, runtime dir) for every corpus project; fails loudly if the corpus was never audited."""
    rows = []
    for spec in record()['corpus']:
        out = measure.REPORTS / spec['name']
        if not (out / '.north-star.json').is_file():
            raise SystemExit(f"{spec['name']}: no audited report in {out}; run python tools/north_star.py measure first")
        rows.append((spec['name'], out, measure.RUNTIME / spec['name']))
    return rows


def verdict(failures, what):
    for line in failures: print('FAIL ' + line)
    if not failures: print('PASS ' + what)
    return 1 if failures else 0


def adapter(name):
    rules = {a['name']: a['applies'] for a in record().get('adopted_adapters', [])}
    if name not in rules: return verdict([f'{name} is not in adopted_adapters'], name)
    failures = [] if (ROOT / f'tests/contracts/{name}.json').is_file() else [f'tests/contracts/{name}.json is missing']
    for project, out, _ in projects():
        class Spec: pass
        spec = Spec(); spec.name = project
        if not measure.applies(spec, rules[name]): continue
        observed = ((measure.load(out, 'facts/external.json', {}) or {}).get('summary') or {}).get('engines_observed') or []
        if name not in observed: failures.append(f'{project}: {name} not in facts/external.json summary.engines_observed {observed}')
    return verdict(failures, f'adapter {name}')


def contract(name, where=None):
    if name not in contracts(): return verdict([f'no contract named {name}; see python tools/contracts.py --list'], name)
    failures = []
    for project, out, runtime in projects():
        path = (runtime if name in __import__('contracts').RUNTIME else out) / contracts()[name]['x-artifact']
        if not path.is_file(): failures.append(f'{project}: {path} does not exist'); continue
        try: data = json.loads(path.read_text(encoding='utf-8'))
        except ValueError as error: failures.append(f'{project}: {path} is not JSON: {error}'); continue
        problems = validate(data, contracts()[name])
        failures += [f'{project}: {problem}' for problem in problems[:10]]
        if not problems and where and not eval(where, {}, {'data': data}):  # planner-written expression
            failures.append(f'{project}: condition does not hold: {where}')
    return verdict(failures, f'contract {name}' + (f' where {where}' if where else ''))


def emitted(prefixes):
    failures = []
    for project, out, _ in projects():
        files = (load_valid('handover-validation', out) or {}).get('files')
        if files is None: failures.append(f'{project}: handover/validation.json missing or breaks its contract'); continue
        for prefix in prefixes:
            rows = [f for f in files if f['path'] == prefix or (prefix.endswith('/') and f['path'].startswith(prefix))]
            if not rows: failures.append(f'{project}: no generated file at {prefix}')
            failures += [f"{project}: {f['path']} rejected by {f['tool']}: {f.get('reason') or f.get('output', '')[:200]}"
                         for f in rows if not f['ok']]
    return verdict(failures, 'emitted ' + ' '.join(prefixes))


def file(path):
    failures = [f'{project}: {path} does not exist' for project, out, _ in projects() if not (out / path).exists()]
    return verdict(failures, f'file {path}')


def facts(kind, project, minimum=1):
    rows = [(name, out) for name, out, _ in projects() if name == project]
    if not rows: return verdict([f'{project} is not in the corpus'], f'facts {kind}')
    count = len(measure.facts(rows[0][1], kind))
    return verdict([] if count >= minimum else [f'{project}: {count} fact(s) of kind {kind}, expected at least {minimum}'],
                   f'facts {kind} in {project}: {count}')


def dsl(path, field=None):
    failures = []
    for project, out, _ in projects():
        target = out / path
        if not target.is_file(): failures.append(f'{project}: {path} does not exist'); continue
        text = target.read_text(encoding='utf-8')
        if text.count('{') != text.count('}'): failures.append(f'{project}: unbalanced braces in {path}')
        for word in ('workspace', 'model', 'views'):
            if word not in text: failures.append(f'{project}: {path} has no {word} block')
        if field:
            names = [row.get('name') for row in (measure.load(out, 'target-architecture.json', {}) or {}).get(field) or []]
            absent = [name for name in names if name and f'"{name}"' not in text]
            if not names: failures.append(f'{project}: target-architecture.json has no {field}')
            if absent: failures.append(f'{project}: {len(absent)} {field} not named in {path}, e.g. {absent[:3]}')
    return verdict(failures, f'dsl {path}')


def digests():
    return {path.relative_to(ROOT / 'acceptance').as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((ROOT / 'acceptance').rglob('*'))
            if path.is_file() and path.name != 'LOCK.json' and '__pycache__' not in path.parts}


def lock(check):
    current = digests()
    if not check:
        LOCK.write_text(json.dumps(current, indent=1, sort_keys=True) + '\n', encoding='utf-8')
        print(f'locked {len(current)} files')
        return 0
    recorded = json.loads(LOCK.read_text(encoding='utf-8')) if LOCK.is_file() else {}
    changed = sorted(name for name in set(current) | set(recorded) if current.get(name) != recorded.get(name))
    return verdict([f'acceptance/{name} differs from acceptance/LOCK.json: only the planner changes acceptance tests'
                    for name in changed], 'acceptance tests match their lock')


def test(name):
    if lock(check=True): return 1
    done = subprocess.run([sys.executable, '-m', 'unittest', f'acceptance.test_{name}', '-v'], cwd=ROOT)
    return done.returncode


def main(argv):
    if not argv: print(__doc__, file=sys.stderr); return 2
    command, rest = argv[0], argv[1:]
    option = lambda flag: rest[rest.index(flag) + 1] if flag in rest else None
    if command == 'adapter' and len(rest) == 1: return adapter(rest[0])
    if command == 'contract' and rest: return contract(rest[0], option('--where'))
    if command == 'emitted' and rest: return emitted(rest)
    if command == 'file' and len(rest) == 1: return file(rest[0])
    if command == 'dsl' and rest: return dsl(rest[0], option('--names'))
    if command == 'facts' and len(rest) >= 2: return facts(rest[0], rest[1], int(option('--min') or 1))
    if command == 'test' and len(rest) == 1: return test(rest[0])
    if command == 'lock': return lock(check='--check' in rest)
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
