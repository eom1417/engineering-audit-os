"""What every fix runs in the sandbox: the candidate clone, a card's codemod, the gates (nothing newly broken, the
project's own checks that passed before still pass) and the row of runtime/execution.json. The batch itself is
eaos/journeys/fix/waves; the assistant's edits come through the MCP tools (eaos/journeys/agent_tools/ fix_edit).

Nothing is written to the original project; the candidate is a clone, and its commit is the reviewable change.
"""
import json
import re
import subprocess
from pathlib import Path

from ...core.contracts.artifact_rules import contracts, validate

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


def run_codemod(card, root, report):
    """The card's codemod on the candidate, rebuilt from the report's facts exactly as the plan's dry run built it."""
    from ...analysis.repair.codemods import _commands, card_for
    from ...facts.store import by_id
    detail = card_for(card, by_id(report, (card.get('evidence') or {}).get('fact_ids') or []), root)
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
    """What the change broke (eaos/analysis/repair/gates.py structure, against the report): a forbidden import, a file in no layer of the
    project's policy, an import cycle, a broken reference of high severity, a boundary of the layers (M6); and any HTTP
    endpoint or mount that is gone.
    A fix that makes a problem disappear by deleting what users reach is not a fix. `collected` is a collection of facts
    on `root` the caller already made."""
    import tempfile
    from ...facts.run import collect
    from ...analysis.repair.gates import structure, words
    from ...analysis.target_state.policy import load_policy
    entry_file = Path(report) / 'facts/entrypoints.json'
    had = surfaces(json.loads(entry_file.read_text(encoding='utf-8'))['facts']) if entry_file.is_file() else None
    try: policy = load_policy(root)[0]
    except (ValueError, OSError): policy = None
    with tempfile.TemporaryDirectory(prefix='eaos-breakage-') as out:
        if collected: out = str(collected)
        else: collect(root, out, ['syntax', 'resolve', 'graph', 'broken', 'domain', 'runtime', 'secrets', 'config']
                      + (['entrypoints'] if had is not None else []))
        broke = words(structure(report, out, policy)) + _layers_broken(report, root, out)
        has = surfaces(json.loads((Path(out) / 'facts/entrypoints.json').read_text(encoding='utf-8'))['facts']) if had is not None else set()
    if had is not None:
        broke += [f'the endpoint {method} {route} is gone' for method, route in sorted(had - has, key=str)]
    return broke


def _layers_broken(report, root, out):
    """The boundaries of the layers (eaos/analysis/layers/) a change broke, when the check read them."""
    from ...analysis import layers
    before = layers._read(Path(report) / layers.RECORD)
    return layers.introduced(before, layers.check(root, out)) if before else []


# The security engines that answer in seconds: they run on every change a batch makes (eaos/journeys/fix/waves edit_gates).
GATE_ENGINES = ('bandit', 'gitleaks')


def app_breakage(project, runtime, root, changed):
    """The run profile's checks (a type check, a lint, the app's tests: seconds, not the whole suite) that a change to
    files of the app broke on the copy `root`, against the same checks on the authorised commit; [] when it touches no
    file of the app, or the app may not run here."""
    from ...live.app.run import load_profile
    from ...live.isolation.sandbox import AuthorizationError
    try: app = (load_profile(runtime).get('app') or '.').strip('/')
    except AuthorizationError: return []
    if app != '.' and not any(path.startswith(app + '/') for path in changed): return []
    return [f'the app\'s own check failed: {check}' for check in
            regressions(original_checks(project, runtime), project_checks(root, runtime, 'S09', 'edit', python=False))]


def project_checks(target, runtime, stage, name, python=True):
    """[{argv, exit}] of the run profile's checks on target, installed in a sandbox copy, and its Python tests (the
    profile's checks run in the app's folder; a Python suite beside it is the project's too; `python` false: the
    profile's alone); [] when there are none. Every command's output tail is kept in runtime/checks-<name>-log.json."""
    from ...live.app.run import LiveRun
    live = LiveRun(target, runtime, stage)
    from ...live.testing.verify import python_tests
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
    from ...live.isolation.sandbox import head
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
