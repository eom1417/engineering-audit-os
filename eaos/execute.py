"""Execute one card of an audit's plan (NS9): its codemod, or a model's edit, then its gates, all in the sandbox.

A card of plan.json already says what is wrong, which files hold it, what the change is, and the command that
decides whether it is done (its acceptance: the claim's own probe, rerun on the changed copy). So a card can be
executed without a second, model-driven review of the whole project:

  1. A candidate is cloned from the authorised commit into <runtime>/candidates/<card>/.
  2. The change: the card's codemod when it has one that changes files; otherwise the model, which receives the
     card and the full text of the card's files, and answers with find-and-replace edits. Every edit must name one
     of the card's files, and its `find` must occur exactly once; anything else is refused, not repaired.
  3. The change is committed in the candidate, a descendant of the authorised commit (the sandbox accepts it
     for stages S08 onward, never an unrelated commit).
  4. The gates, in order, each stopping the card: the acceptance command must exit 0 on the candidate; the
     change must break nothing the audit reads as broken (an import of a file that is gone, an undefined name),
     judged by rerunning the broken-code detector on the candidate against the report's own facts; every check
     the run profile declares (the project's own typecheck, lint and tests) that passes on the original must
     pass on the candidate; the behaviour lock recorded on the original (NS26) must still pass on the candidate.
  5. runtime/execution.json gets one row: id, tool (codemod or model), status, acceptance_exit.

Nothing is written to the original project; the candidate is a clone, and its commit is the reviewable change.
"""
import json
import re
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .artifact_contracts import contracts, validate

MAX_FILE_CHARS = 120_000
SYSTEM = """You are the engineer executing one card of an engineering plan in a copy of a real project.
The card states the problem, the evidence, the change and the invariant to keep. You receive the full text of
every file the card may change. Make the smallest change that removes the problem and keeps behaviour identical
for users. Do not rename anything else, reformat, or touch code the card does not concern.

Answer with one JSON object:
{"action": "final", "result": {"summary": "<one sentence>", "edits": [{"path": "<one of the card's files>",
 "find": "<exact text that occurs once in that file>", "replace": "<its replacement>"}]}}
`find` must be copied exactly from the file, long enough to occur once. Several edits may touch one file, in order.
If the change cannot be made safely within these files, answer {"action": "final", "result": {"summary":
"<why>", "edits": []}}."""


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


def apply_edits(root, edits, allowed):
    """Apply find-and-replace edits; every refusal names its reason, and nothing is half-applied."""
    staged = {}
    for edit in edits:
        path = edit.get('path')
        if path not in allowed: raise ValueError(f'{path}: not one of the card\'s files')
        text = staged.get(path, (Path(root) / path).read_text(encoding='utf-8'))
        find, replace = edit.get('find'), edit.get('replace')
        if not isinstance(find, str) or not isinstance(replace, str) or not find:
            raise ValueError(f'{path}: an edit needs text to find and its replacement')
        if text.count(find) != 1: raise ValueError(f'{path}: the text to find occurs {text.count(find)} times, not once')
        staged[path] = text.replace(find, replace, 1)
    for path, text in staged.items(): (Path(root) / path).write_text(text, encoding='utf-8')
    return sorted(staged)


def model_messages(card, root):
    files = []
    for path in card['paths']:
        text = (Path(root) / path).read_text(encoding='utf-8', errors='replace')
        if len(text) > MAX_FILE_CHARS: raise ValueError(f'{path}: {len(text)} characters is more than a model call carries whole')
        files.append(f'=== {path}\n{text}')
    brief = {key: card.get(key) for key in ('id', 'title', 'pattern', 'paths', 'change', 'invariants', 'before', 'after', 'rollback')}
    brief['acceptance'] = [step['expect'] for step in card.get('acceptance') or []]
    return [{'role': 'system', 'content': SYSTEM},
            {'role': 'user', 'content': 'The card:\n' + json.dumps(brief, ensure_ascii=False, indent=1) + '\n\nThe files:\n' + '\n\n'.join(files)}]


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


def acceptance(card, root):
    """The card's own acceptance argv, run on the candidate: its exit code."""
    argv = card.get('verify_command') or []
    if not argv: return None
    return subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=1800).returncode


def new_breakage(report, root):
    """Broken-code findings of severity high on the candidate that the report did not have: what the change broke."""
    import tempfile
    from .facts.run import collect
    key = lambda f: (f['value']['rule'], f['location'].get('path'), f['location'].get('symbol'))
    before = {key(f) for f in json.loads((Path(report) / 'facts/broken.json').read_text(encoding='utf-8'))['facts']}
    with tempfile.TemporaryDirectory(prefix='eaos-breakage-') as out:
        collect(root, out, ['syntax', 'resolve', 'broken'])
        after = json.loads((Path(out) / 'facts/broken.json').read_text(encoding='utf-8'))['facts']
    return sorted(f['value']['message'] for f in after if f['value'].get('severity') == 'high' and key(f) not in before)


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


def execute(report, target, runtime, card_id, provider=None, lock=True):
    """Run one card through change and gates; returns its execution.json row."""
    report, runtime = Path(report), Path(runtime)
    card = next((t for t in json.loads((report / 'plan.json').read_text(encoding='utf-8'))['tasks'] if t['id'] == card_id), None)
    if card is None: raise ValueError(f'{card_id} is not in {report}/plan.json')
    if (card.get('decision') or {}).get('readiness') != 'ready' or card.get('kind') != 'remediate':
        raise ValueError(f'{card_id} is not a ready repair: an investigation waits for a person\'s decision')
    from .sandbox import head, refusal
    reason = refusal(runtime / 'authorization.json', 'S08', head(target))
    if reason: raise PermissionError(reason)
    root = candidate(target, runtime, card_id)
    log = {'card': card_id, 'started': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    uses_codemod = ((card.get('codemod') or {}).get('dry_run') or {}).get('files_changed', 0) > 0
    row = {'id': card_id, 'tool': 'codemod' if uses_codemod else 'model', 'status': 'FAILED', 'acceptance_exit': -1}
    try:
        if uses_codemod:
            run_codemod(card, root, report)
            log['change'] = card['codemod']['command']
        else:
            if provider is None: raise ValueError('this card has no codemod: a model provider is needed')
            answer, _ = provider.complete(model_messages(card, root))
            result = answer.get('result') or {}
            log['summary'] = result.get('summary')
            if not result.get('edits'):
                row['status'] = 'NEEDS_REVIEW'
                row['result'] = 'the model made no edit: ' + str(result.get('summary'))[:300]
                return record(runtime, row)['tasks'][-1]
            log['changed'] = apply_edits(root, result['edits'], set(card['paths']))
        git(root, 'add', '-A')
        commit = git(root, '-c', 'user.name=EAOS', '-c', 'user.email=eaos@localhost', 'commit', '--quiet', '-m',
                     f"{card_id}: {card['title'][:70]}\n\nExecuted by EAOS ({row['tool']}); acceptance: {card['acceptance'][0]['expect'] if card.get('acceptance') else '-'}")
        if commit.returncode: raise RuntimeError('the change left nothing to commit')
        log['commit'] = git(root, 'rev-parse', 'HEAD').stdout.strip()
        (root.parent / f'{card_id}.patch').write_text(git(root, 'format-patch', '-1', '--stdout').stdout, encoding='utf-8')
        row['acceptance_exit'] = acceptance(card, root)
        if row['acceptance_exit'] != 0:
            row['result'] = f"acceptance exited {row['acceptance_exit']}: {shlex.join(card['verify_command'])[:200]}"
            return record(runtime, row)['tasks'][-1]
        broke = new_breakage(report, root)
        log['new_breakage'] = broke
        if broke:
            row['result'] = f'the change broke {len(broke)} thing(s): {broke[0]}'[:400]
            return record(runtime, row)['tasks'][-1]
        before = original_checks(target, runtime)
        if before:
            after = project_checks(root, runtime, 'S09', card_id)
            log['checks'] = {'original': before, 'candidate': after}
            failed = regressions(before, after)
            if failed:
                row['result'] = f"the project's own check failed on the change: {', '.join(failed)}"[:400]
                return record(runtime, row)['tasks'][-1]
        if lock:
            from .behavior_lock import verify_lock
            verdict = verify_lock(report, root, runtime, name=f'candidate-{card_id}')
            log['lock'] = verdict
            if verdict['failed']:
                row['result'] = f"the behaviour lock broke on {verdict['failed']} of {verdict['specs']} specs"
                return record(runtime, row)['tasks'][-1]
        row['status'] = 'VERIFIED_IN_ISOLATED_COPY'
        row['result'] = f"{log.get('commit', '')[:12]}: acceptance 0" + (f"; lock {log['lock']['passed']}/{log['lock']['specs']}" if lock else '')
        return record(runtime, row)['tasks'][-1]
    except (ValueError, RuntimeError, subprocess.CalledProcessError, OSError) as problem:
        row['result'] = f'{type(problem).__name__}: {problem}'[:400]
        return record(runtime, row)['tasks'][-1]
    finally:
        (runtime / 'candidates' / f'{card_id}.json').write_text(json.dumps(log, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
