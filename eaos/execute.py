"""What every fix runs in the sandbox: the candidate clone, a card's codemod, the gates (nothing newly broken, the
project's own checks that passed before still pass) and the row of runtime/execution.json. The batch itself is
eaos/waves.py; the assistant's edits come through the MCP tools (eaos/agent_tools.py fix_edit).

Nothing is written to the original project; the candidate is a clone, and its commit is the reviewable change.
"""
import json
import re
import subprocess
from pathlib import Path

from .artifact_contracts import contracts, validate

def git(where, *args):
    return subprocess.run(['git', '-C', str(where), *args], capture_output=True, text=True)


def candidate(target, runtime, card_id):
    """A clone of the authorised commit, fresh for this card."""
    import shutil
    grant = json.loads((Path(runtime) / 'authorization.json').read_text(encoding='utf-8'))
    where = Path(runtime) / 'candidates' / card_id
    shutil.rmtree(where, ignore_errors=True)
    where.parent.mkdir(parents=True, exist_ok=True)
    for args in (('clone', '--quiet', '--no-hardlinks', str(target), str(where)),):
        done = subprocess.run(['git', *args], capture_output=True, text=True)
        if done.returncode: raise RuntimeError(f'clone failed: {done.stderr[-300:]}')
    if git(where, 'checkout', '--quiet', grant['commit']).returncode: raise RuntimeError('the authorised commit is not in the target')
    git(where, 'checkout', '--quiet', '-b', f'eaos/{card_id.lower()}')
    return where


def _facts_by_id(report):
    """Every fact of the report's fact sets, by id; a set that does not read is skipped."""
    facts_by_id = {}
    for path in sorted((Path(report) / 'facts').glob('*.json')):
        try: data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError): continue
        facts_by_id.update((fact['id'], fact) for fact in data.get('facts') or [] if isinstance(fact, dict) and fact.get('id'))
    return facts_by_id


def run_codemod(card, root, report):
    """The card's codemod on the candidate, rebuilt from the report's facts exactly as the plan's dry run built it."""
    from .codemods import _commands, card_for
    detail = card_for(card, _facts_by_id(report), root)
    steps = _commands(detail, Path(root)) if detail else None
    if not steps: raise RuntimeError(f"{card['id']}: its codemod cannot be rebuilt from the report's facts")
    for step, _ in steps:
        if callable(step): step()
        else: subprocess.run(step, cwd=root, capture_output=True, text=True, timeout=600, check=True)


def surfaces(facts):
    """The HTTP endpoints and mounts a set of entry-point facts names: (method, route)."""
    return {(f['value'].get('http_method'), f['value'].get('route')) for f in facts
            if f.get('kind') == 'entry_point' and (f.get('value') or {}).get('surface') == 'http'}


def new_breakage(report, root, collected=None):
    """What the change broke: broken-code findings of severity high the report did not have, and any HTTP endpoint
    or mount that is gone. A fix that makes a problem disappear by deleting what users reach is not a fix.
    `collected` is a collection of facts on `root` the caller already made."""
    import tempfile
    from .facts.run import collect
    key = lambda f: (f['value']['rule'], f['location'].get('path'), f['location'].get('symbol'))
    before = {key(f) for f in json.loads((Path(report) / 'facts/broken.json').read_text(encoding='utf-8'))['facts']}
    entry_file = Path(report) / 'facts/entrypoints.json'
    had = surfaces(json.loads(entry_file.read_text(encoding='utf-8'))['facts']) if entry_file.is_file() else None
    with tempfile.TemporaryDirectory(prefix='eaos-breakage-') as out:
        if collected: out = str(collected)
        else: collect(root, out, ['syntax', 'resolve', 'broken'] + (['entrypoints'] if had is not None else []))
        after = json.loads((Path(out) / 'facts/broken.json').read_text(encoding='utf-8'))['facts']
        has = surfaces(json.loads((Path(out) / 'facts/entrypoints.json').read_text(encoding='utf-8'))['facts']) if had is not None else set()
    broke = sorted(f['value']['message'] for f in after if f['value'].get('severity') == 'high' and key(f) not in before)
    if had is not None:
        broke += [f'the endpoint {method} {route} is gone' for method, route in sorted(had - has, key=str)]
    return broke


# The security engines that answer in seconds: they run on every change a batch makes (edit_gates).
GATE_ENGINES = ('bandit', 'gitleaks')


def _facts(folder, name):
    file = Path(folder) / 'facts' / f'{name}.json'
    return json.loads(file.read_text(encoding='utf-8'))['facts'] if file.is_file() else []


def _copies(folder, paths):
    """The copied blocks and functions with an occurrence in `paths`."""
    from .fact_claims import worth_a_claim
    touches = lambda f: paths & {o['path'] for o in f['value']['occurrences']}
    found = {f['input_sha'] for f in _facts(folder, 'metrics') if f['kind'] == 'clone_cluster' and touches(f)}
    return found | {f['value']['shape_sha'] for f in _facts(folder, 'fingerprint') if f['kind'] == 'duplicate_cluster' and touches(f)
                    and worth_a_claim(f['value']['occurrences'], f['value'].get('shared_size', 0))}


def _dead(folder, paths):
    return {(f['value']['rule'], f['location'].get('path'), f['location'].get('symbol')) for f in _facts(folder, 'deadcode')
            if f['location'].get('path') in paths}


def _excess(folder, paths):
    """The decisions past the complexity limit of the functions and methods in `paths`, summed over all of them: code
    moved between the files keeps its sum, and a class (the sum of its methods) is not one more function."""
    from .code_laws import MAX_COMPLEXITY
    return sum(max(0, f['value']['branches'] - MAX_COMPLEXITY) for f in _facts(folder, 'metrics')
               if f['kind'] == 'metric' and f['value']['scope'] in ('function', 'method') and f['location']['path'] in paths)


def new_debt(report, collected, paths):
    """What a change added against the code laws (eaos/code_laws.py) in the files it touched (`paths`), from the facts
    of the report (before) and `collected` (after): a copied block or function, dead code, more decisions past the
    complexity limit across those files (splitting a function of 60 into three of 20 is less; a new one of 20 is
    more; moving one into a new module is neither), or a security finding of an engine both ran (GATE_ENGINES, fast
    enough for every change). A change that adds any is taken back like a breakage."""
    from .code_laws import MAX_COMPLEXITY
    from .weaknesses import new as new_weaknesses
    paths = set(paths)
    was, now = _excess(report, paths), _excess(collected, paths)
    copied = _copies(collected, paths) - _copies(report, paths)
    added = [f'{len(copied)} copied block(s) or function(s): call the one home instead'] if copied else []
    added += [f'dead code: {symbol or path} ({rule})' for rule, path, symbol in sorted(_dead(collected, paths) - _dead(report, paths))]
    if now > was: added.append(f'more complex: {now - was} decisions more past the limit of {MAX_COMPLEXITY} per function')
    added += [f'a security finding: {rule} ({engine}) in {path}'
              for engine, rule, path in new_weaknesses(report, collected, paths)]
    return added


def edit_gates(where, root, card, changed, repair):
    """(what one change of a batch broke or added against the code laws, the card's own check's exit: None for a
    repair), from one collection of facts on the copy `root`; `where`: (report, project, runtime). A change to the app's
    files also runs the app's own checks (app_breakage): an unused import in a Studio file broke its type check, then
    its build, and was found only when the 51 changes of a batch met (EAOS, 2026-10-14)."""
    import tempfile
    from .facts.run import collect
    from .waves import batch_acceptance, engines_for
    report, project, runtime = where
    with tempfile.TemporaryDirectory(prefix='eaos-edit-facts-') as out:
        collect(root.resolve(), out, engines=engines_for([card]))
        broke = new_breakage(report, root, collected=out) + new_debt(report, out, changed) + app_breakage(project, runtime, root, changed)
        return broke, None if repair else batch_acceptance(report, [card], root, collected=out).get(card['id'])


def app_breakage(project, runtime, root, changed):
    """The run profile's checks (a type check, a lint, the app's tests: seconds, not the whole suite) that a change to
    files of the app broke on the copy `root`, against the same checks on the authorised commit; [] when it touches no
    file of the app, or the app may not run here."""
    from .live_run import load_profile
    from .sandbox import AuthorizationError
    try: app = (load_profile(runtime).get('app') or '.').strip('/')
    except AuthorizationError: return []
    if app != '.' and not any(path.startswith(app + '/') for path in changed): return []
    return [f'the app\'s own check failed: {check}' for check in
            regressions(original_checks(project, runtime), project_checks(root, runtime, 'S09', 'edit', python=False))]


def project_checks(target, runtime, stage, name, python=True):
    """[{argv, exit}] of the run profile's checks on target, installed in a sandbox copy, and its Python tests (the
    profile's checks run in the app's folder; a Python suite beside it is the project's too; `python` false: the
    profile's alone); [] when there are none. Every command's output tail is kept in runtime/checks-<name>-log.json."""
    from .live_run import LiveRun
    live = LiveRun(target, runtime, stage)
    from .verify import python_tests
    checks = [(argv, False) for argv in live.profile.get('checks') or []] + \
        [(argv, True) for argv in (python_tests(target, live.profile) if python else [])]
    if not checks: return []
    try:
        live.setup()
        rows = []
        for argv, at_root in checks:
            code, out, err = live.run(argv, timeout=1800, at_root=at_root)
            rows.append({'argv': argv, 'exit': code, 'failing': failing(out + err)})
        return rows
    finally:
        live.stop()
        live.record(f'runtime/checks-{name}-log.json')


def original_checks(target, runtime):
    """The checks on the authorised commit, run once and kept beside the run (runtime/checks-original.json)."""
    from .sandbox import head
    path = Path(runtime) / 'runtime/checks-original.json'
    commit = head(target)
    if path.is_file():
        kept = json.loads(path.read_text(encoding='utf-8'))
        if kept.get('commit') == commit: return kept['checks']
    checks = project_checks(target, runtime, 'S08', 'original')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'commit': commit, 'checks': checks}, indent=1) + '\n', encoding='utf-8')
    return checks


TAP_FAILURE = re.compile(r'^\s*not ok \d+ - (.+?)(?:\s+#.*)?$', re.M)
PYTHON_FAILURE = re.compile(r'^(?:(?:FAIL|ERROR): (\S+ \([^)]*\))|FAILED (\S+))', re.M)   # unittest, pytest -q


def failing(output):
    """The names of the failing tests a TAP reporter (node --test, tap...), unittest or pytest printed: sorted, unique."""
    return sorted(set(TAP_FAILURE.findall(output)) | {a or b for a, b in PYTHON_FAILURE.findall(output)})


def regressions(before, after):
    """What the change broke: a check that passed and now fails, or, for a test suite already failing on the
    original, a test that passed and now fails. A failure the original already had is not the change's."""
    was = {tuple(c['argv']): c for c in before}
    return [broke for check in after if (broke := _regression(was.get(tuple(check['argv'])), check))]


def _regression(old, check):
    """What one check says the change broke (it passed and now fails, or it fails with new failing tests), or None."""
    if old is None or check['exit'] == 0: return None
    if old['exit'] == 0: return ' '.join(check['argv'])
    new = sorted(set(check.get('failing') or []) - set(old['failing'])) if old.get('failing') else []
    return f"{' '.join(check['argv'])} ({len(new)} new failing: {new[0]})" if new else None


def record(runtime, row):
    path = Path(runtime) / 'runtime/execution.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'schema_version': 1, 'tasks': []}
    data['tasks'] = [t for t in data['tasks'] if t['id'] != row['id']] + [row]
    problems = validate(data, contracts()['execution-log'])
    if problems: raise RuntimeError(f'execution.json would break its contract: {problems[0]}')
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return data
