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


def run_codemod(card, root, report):
    """The card's codemod on the candidate, rebuilt from the report's facts exactly as the plan's dry run built it."""
    from .codemods import _commands, card_for
    facts_by_id = {}
    for path in sorted((Path(report) / 'facts').glob('*.json')):
        try: data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError): continue
        for fact in data.get('facts') or []:
            if isinstance(fact, dict) and fact.get('id'): facts_by_id[fact['id']] = fact
    detail = card_for(card, facts_by_id, root)
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


def project_checks(target, runtime, stage, name):
    """[{argv, exit}] of the run profile's checks on target, installed in a sandbox copy; [] when it declares none.
    Every command's output tail is kept in runtime/checks-<name>-log.json."""
    from .live_run import LiveRun
    live = LiveRun(target, runtime, stage)
    checks = live.profile.get('checks') or []
    if not checks: return []
    try:
        live.setup()
        rows = []
        for argv in checks:
            code, out, err = live.run(argv, timeout=1800)
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


def failing(output):
    """The names of the failing tests a TAP reporter printed (node --test, tap, and others): sorted, unique."""
    return sorted(set(TAP_FAILURE.findall(output)))


def regressions(before, after):
    """What the change broke: a check that passed and now fails, or, for a test suite already failing on the
    original, a test that passed and now fails. A failure the original already had is not the change's."""
    was = {tuple(c['argv']): c for c in before}
    broken = []
    for check in after:
        old = was.get(tuple(check['argv']))
        if old is None or check['exit'] == 0: continue
        if old['exit'] == 0: broken.append(' '.join(check['argv']))
        elif old.get('failing') and check.get('failing'):
            new = sorted(set(check['failing']) - set(old['failing']))
            if new: broken.append(f"{' '.join(check['argv'])} ({len(new)} new failing: {new[0]})")
    return broken


def record(runtime, row):
    path = Path(runtime) / 'runtime/execution.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'schema_version': 1, 'tasks': []}
    data['tasks'] = [t for t in data['tasks'] if t['id'] != row['id']] + [row]
    problems = validate(data, contracts()['execution-log'])
    if problems: raise RuntimeError(f'execution.json would break its contract: {problems[0]}')
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return data
