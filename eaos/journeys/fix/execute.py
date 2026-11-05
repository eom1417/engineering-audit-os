"""What every fix runs in the sandbox: the candidate clone, a card's codemod, the gates (nothing newly broken, the
project's own checks that passed before still pass) and the row of runtime/execution.json. The batch itself is
eaos/journeys/fix/waves; the assistant's edits come through the MCP tools (eaos/journeys/agent_tools/ fix_edit).

Nothing is written to the original project; the candidate is a clone, and its commit is the reviewable change.
"""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

from ...core.contracts.artifact_rules import contracts, validate
from ...core.system.clock import now

def git(where, *args):
    return subprocess.run(['git', '-C', str(where), *args], capture_output=True, text=True)


def set_aside(copy):
    """Nothing EAOS finds where a new copy goes is deleted: it may hold the only trace of a change. An empty folder goes; the
    rest moves beside it under a name of its own, where `eaos clean` judges it as any copy."""
    copy = Path(copy)
    if copy.is_dir() and not copy.is_symlink() and not any(copy.iterdir()): return copy.rmdir()
    if not (copy.exists() or copy.is_symlink()): return None
    aside = None
    while aside is None or aside.exists() or aside.is_symlink(): aside = copy.with_name(f'{copy.name}.left-{os.urandom(6).hex()}')
    return copy.rename(aside)


def candidate(target, runtime, card_id):
    """A clone of the authorised commit, fresh for this card."""
    grant = json.loads((Path(runtime) / 'authorization.json').read_text(encoding='utf-8'))
    where = Path(runtime) / 'candidates' / card_id
    set_aside(where)
    where.parent.mkdir(parents=True, exist_ok=True)
    for args in (('clone', '--quiet', '--no-hardlinks', str(target), str(where)),):
        done = subprocess.run(['git', *args], capture_output=True, text=True)
        if done.returncode: raise RuntimeError(f'clone failed: {done.stderr[-300:]}')
    if git(where, 'checkout', '--quiet', grant['commit']).returncode: raise RuntimeError('the authorised commit is not in the target')
    git(where, 'checkout', '--quiet', '-b', f'eaos/{card_id.lower()}')
    return where


def own_batch(target, runtime, name):
    """A clone of the authorised commit for one batch (a wave of fixes, a batch of moves or of the context): (root, base).
    PermissionError when the person's agreement does not cover the commit now."""
    from ...live.isolation.sandbox import head, refusal
    reason = refusal(Path(runtime) / 'authorization.json', 'S08', head(target))
    if reason: raise PermissionError(reason)
    root = candidate(target, runtime, name)
    return root, git(root, 'rev-parse', 'HEAD').stdout.strip()


def commit_all(root, message, paths=None):
    """Everything the batch changed in the copy (only `paths` when given: never what a run left there), as EAOS. A
    path a move took away is in neither the tree nor the index: named, git refused the whole add, and a move batch was
    committed without its rewritten imports (M9.5: the app no longer started after the moves)."""
    if paths is not None:      # forced: a batch's own path in a folder the project ignores (lib/, build/) is still its
        paths = [p for p in paths if (Path(root) / p).exists() or git(root, 'ls-files', '--', p).stdout.strip()]
        if not paths: raise RuntimeError('the batch left nothing to commit')
    added = git(root, 'add', '-A', *(['-f', '--', *paths] if paths is not None else []))
    if added.returncode: raise RuntimeError(f'git add failed: {added.stderr.strip()[-300:]}')
    if git(root, '-c', 'user.name=EAOS', '-c', 'user.email=eaos@localhost', 'commit', '--quiet', '-m', message).returncode:
        raise RuntimeError('the batch left nothing to commit')


def record_batch(batch, root, base, kept, refused):
    """A batch of its own (batch['kind']: moves, context) recorded beside the run, runtime/<kind>/<kind>-N/ with its
    patch and summary.json; the summary: its branch, what it kept (empty when refused) and why it refused."""
    kind, number = batch['kind'], batch['number']
    folder = Path(batch['runtime']) / kind / f'{kind}-{number}'
    folder.mkdir(parents=True, exist_ok=True)
    if kept: git(root, 'format-patch', '--quiet', '-o', str(folder), f'{base}..HEAD')
    summary = {'batch': number, 'kind': kind, 'branch': batch.get('deliver_as') or f'eaos/{kind}-{number}', 'root': str(root),
               'base': base, 'kept': kept, 'items': batch['items'], 'refused': refused, **(batch.get('extra') or {}),
               'at': now(),
               'stat': git(root, 'diff', '--shortstat', f'{base}..HEAD').stdout.strip() if kept else ''}
    (folder / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return summary


def run_codemod(card, root, report):
    """The card's codemod on the candidate, rebuilt from the report's facts exactly as the plan's dry run built it."""
    _run_codemod(card['id'], _codemod_of(card, root, report)[0], root)


def _codemod_of(card, root, report):
    """(what the card's codemod changes, {fact id: fact} of its evidence), as the plan's dry run built it."""
    from ...analysis.repair.codemods import card_for
    from ...facts.store import by_id
    facts = by_id(report, (card.get('evidence') or {}).get('fact_ids') or [])
    return card_for(card, facts, root), facts


def _run_codemod(name, detail, root):
    from ...analysis.repair.codemods import _commands
    steps = _commands(detail, Path(root)) if detail else None
    if not steps: raise RuntimeError(f"{name}: its codemod cannot be rebuilt from the report's facts")
    for step, _ in steps:
        if callable(step):
            step()
            continue
        done = subprocess.run(step, cwd=root, capture_output=True, text=True, timeout=600)  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- a codemod's argv rebuilt from the report's facts, run in the candidate copy, no shell
        # its own words (npm's ERESOLVE), never only its command line, which names this machine's paths
        if done.returncode: raise RuntimeError(f"{' '.join([Path(step[0]).name, *map(str, step[1:2])])} exited {done.returncode}: {(done.stderr or done.stdout).strip()[-240:]}")


def codemod_by_member(card, root, report):
    """A lock file card whose change failed whole, made again on the copy one package at a time: each package's upgrade
    kept only when its steps pass and the dependency tree stays valid (_dependencies_broken). Second trial on real
    projects: one package of 32 left the tree invalid, and the 31 sound upgrades were lost with it. (the facts of the
    packages kept, {package@version: why it was left}); the kept changes are staged, for the card's one commit."""
    detail, facts = _codemod_of(card, root, report)
    start, kept, left = git(root, 'rev-parse', 'HEAD').stdout.strip(), set(), {}
    for member in (detail or {}).get('group') or []:
        name, why = f"{member['package']}@{member['version']}", _member_kept(card['id'], member, root)
        if why: left[name] = why
        else: kept.add(name)
    git(root, 'reset', '--soft', '--quiet', start)
    return [fact for fact in facts.values() if str(fact['location'].get('symbol')).partition(':')[2] in kept], left


def _member_kept(name, member, root):
    """'' when one package's upgrade ran and left the dependency tree valid, committed; else why not, the copy as before."""
    try:
        _run_codemod(name, member, root)
        commit_all(root, f"{name}: {member['package']}")
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as problem:
        git(root, 'reset', '--hard', '--quiet', 'HEAD')
        git(root, 'clean', '-fdq')
        return str(problem)[:300]
    broke = _dependencies_broken(root)
    if broke: git(root, 'reset', '--hard', '--quiet', 'HEAD~1')
    return broke[0] if broke else ''


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
        broke = words(structure(report, out, policy)) + _layers_broken(report, root, out) + _dependencies_broken(root)
        has = surfaces(json.loads((Path(out) / 'facts/entrypoints.json').read_text(encoding='utf-8'))['facts']) if had is not None else set()
    if had is not None:
        broke += [f'the endpoint {method} {route} is gone' for method, route in sorted(had - has, key=str)]
    return broke


def _layers_broken(report, root, out):
    """The boundaries of the layers (eaos/analysis/layers/) a change broke, when the check read them."""
    from ...analysis import layers
    before = layers.read(Path(report) / layers.RECORD)
    return layers.introduced(before, layers.check(root, out)) if before else []


NPM_FILES = ('package.json', 'package-lock.json')


def _dependencies_broken(root):
    """What the last commit broke in the dependency tree npm reads from a package.json and its lock (npm ls: no install,
    no network, no script): a version out of the range its consumer asks, a lock behind its package.json. Trial on real
    projects (2026-11-02): an upgrade that put a package out of a plugin's range was seen only once the install broke,
    and the upgrades after it failed on it. npm only; a commit that changes neither file is not read."""
    from ...engines.process import which
    npm, changed = which('npm'), git(root, 'diff', '--name-only', 'HEAD~1', 'HEAD').stdout.split('\n')
    folders = sorted({str(PurePosixPath(path).parent) for path in changed if PurePosixPath(path).name in NPM_FILES})
    broke = []
    for folder in folders if npm else []:
        new = _npm_problems(npm, Path(root) / folder)
        if not new: continue
        with tempfile.TemporaryDirectory(prefix='eaos-dependencies-') as before:
            for name in NPM_FILES:
                shown = git(root, 'show', f'HEAD~1:{PurePosixPath(folder, name)}')
                if shown.returncode == 0: (Path(before) / name).write_text(shown.stdout, encoding='utf-8')
            new -= _npm_problems(npm, Path(before))
        broke += [f'the dependency tree is no longer valid: {problem}' for problem in sorted(new)]
    return broke


def _npm_problems(npm, folder):
    """The problems `npm ls` finds in a folder's package.json and lock, without the folder's path."""
    if not (folder / 'package.json').is_file(): return set()
    done = subprocess.run([npm, 'ls', '--all', '--package-lock-only', '--json'], cwd=folder, capture_output=True, text=True, timeout=120)  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- npm at its path, a fixed list argv, reading the lock only (no install, no script)
    try: problems = json.loads(done.stdout).get('problems') or []
    except ValueError: return set()
    return {problem.replace(f'{folder.resolve()}/', '').replace(f'{folder}/', '') for problem in problems}


# The engines that answer in seconds: they run on every change a batch makes (eaos/journeys/fix/waves edit_gates): the
# security ones, and jscpd and ast-grep for one source per pattern (M15.9).
GATE_ENGINES = ('bandit', 'gitleaks', 'jscpd', 'ast-grep')


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
    """[{argv, exit}] of the run profile's checks on target, installed in a sandbox copy (its install held to the lock,
    `npm ci`, a row too), and its Python tests (the profile's checks run in the app's folder; a Python suite beside it is
    the project's too; `python` false: the profile's alone); [] when there are none. Every command's output tail is kept
    in runtime/checks-<name>-log.json. They see a copy of the run's database of their own: what setup wrote in it, never
    what an earlier checks run wrote (a test writing a real row passed once, then failed on every later run)."""
    from ...live.app.run import LiveRun, _unfrozen
    live = LiveRun(target, runtime, stage)
    live.throwaway = True
    from ...live.testing.verify import python_tests
    checks = [(argv, False) for argv in live.profile.get('checks') or []] + \
        [(argv, True) for argv in (python_tests(target, live.profile) if python else [])]
    if not checks: return []
    try:
        live.setup()
        # the lock installing as it is, a check of its own: setup's fallback to an unfrozen install hides a broken lock
        rows = [{'argv': r['argv'], 'exit': r['exit'], 'failing': []} for r in live.log if _unfrozen(r['argv'])]
        return rows + [_check(live, target, argv, at_root) for argv, at_root in checks]
    finally:
        live.stop()
        live.record(f'runtime/checks-{name}-log.json')


def _check(live, target, argv, at_root):
    """One check's row on the run's copy. A check that changed the copy's committed files (a lint reaching `--write`)
    passes by fixing what it checks: the files are named in its row (`writes`) and put back for the next check, and its
    exit is no gate (trial on real projects: a lint always passed so)."""
    names = [name for name in git(target, 'ls-tree', '-r', '-z', '--name-only', live.commit).stdout.split('\0') if name]
    before = _stamps(live.sandbox.copy, names)
    code, out, err = live.run(argv, timeout=1800, at_root=at_root)
    row = {'argv': argv, 'exit': code, 'failing': failing(out + err)}
    after = _stamps(live.sandbox.copy, before)
    written = [name for name, stamp in before.items() if after.get(name) != stamp]
    if written:
        files = subprocess.run(['git', '-C', str(target), 'archive', '--format=tar', live.commit, '--', *[f':(literal){name}' for name in written]],
                               capture_output=True, check=True).stdout
        subprocess.run(['tar', '-x', '-C', str(live.sandbox.copy)], input=files, check=True)
        row['writes'] = written
    return row


def _stamps(copy, names):
    """{name: (size, modified)} of the files `names` the folder `copy` holds."""
    stamps = {}
    for name in names:
        try: found = (Path(copy) / name).lstat()
        except OSError: continue
        stamps[name] = (found.st_size, found.st_mtime_ns)
    return stamps


def original_checks(target, runtime):
    """The checks on the authorised commit, run once and kept beside the run (runtime/checks-original.json): read again
    while the commit and the profile's install and checks are the same (a library's profile gained its tests, and the
    failing result of before still said it had none, 2026-11-05)."""
    from ...live.app.run import load_profile
    from ...live.isolation.sandbox import head
    path = Path(runtime) / 'runtime/checks-original.json'
    profile = load_profile(runtime)
    key = {'commit': head(target), 'commands': [profile.get('install') or [], profile.get('checks') or []]}
    if path.is_file():
        kept = json.loads(path.read_text(encoding='utf-8'))
        if {name: kept.get(name) for name in key} == key: return kept['checks']
    checks = project_checks(target, runtime, 'S08', 'original')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({**key, 'checks': checks}, indent=1) + '\n', encoding='utf-8')
    return checks


TAP_FAILURE = re.compile(r'^\s*not ok \d+ - (.+?)(?:\s+#.*)?$', re.M)
PYTHON_FAILURE = re.compile(r'^(?:(?:FAIL|ERROR): (\S+ \([^)]*\))|FAILED (\S+))', re.M)   # unittest, pytest -q
JEST_FAILURE = re.compile(r'^\s*(?:\u25cf|FAIL\s+\S+\s+>)\s+(?!Console$)(.+?)\s*$', re.M)   # jest: "● Suite › name"; vitest: "FAIL file > name"


def failing(output):
    """The names of the failing tests a TAP reporter (node --test, tap...), unittest, pytest, jest or vitest printed:
    sorted, unique."""
    return sorted(set(TAP_FAILURE.findall(output)) | set(JEST_FAILURE.findall(output)) | {a or b for a, b in PYTHON_FAILURE.findall(output)})


def not_run(checks):
    """The project's own checks that could not run here (exit 126 or 127: their program missing or not allowed): no gate
    held a change to them, which the person is told, never silent."""
    return [' '.join(map(str, check['argv'])) for check in checks if check['exit'] in (126, 127)]


def rewrites(checks):
    """The project's own checks that rewrite the files instead of checking them (a row's `writes`): no gate, which the
    person is told."""
    return [' '.join(map(str, check['argv'])) for check in checks if check.get('writes')]


def regressions(before, after):
    """What the change broke: a check that passed and now fails, or, for a test suite already failing on the
    original, a test that passed and now fails. A failure the original already had is not the change's."""
    was = {tuple(c['argv']): c for c in before}
    return [broke for check in after if (broke := _regression(was.get(tuple(check['argv'])), check))]


def _regression(old, check):
    """What one check says the change broke (it passed and now fails, or it fails with new failing tests), or None."""
    if old is None or check['exit'] == 0 or check.get('writes'): return None
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
