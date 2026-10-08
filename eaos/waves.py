"""Fix a batch of plan cards at once, and hand the result over as a branch (NS9.T4).

One card at a time behind every gate costs about twelve minutes a card; the first milestone of a real project
holds more than a hundred. So a batch (a wave) is executed together, and the expensive gates run once:

  1. The candidate: a clone of the authorised commit, on branch eaos/wave-<n> (eaos/execute.candidate).
  2. Each card: its codemod, or the assistant's edit (eaos/execute), committed alone, then the quick gate: no
     new broken code. A card that breaks something is taken back at once (its commit is dropped).
  3. The acceptance of every card from one collection of facts (batch_acceptance); a card whose problem is
     still there is dropped the same way.
  4. The project's own checks and the behaviour lock, once for the whole batch. When they fail, the batch is
     split in half until the card responsible is found (culprits), and only the cards that pass together stay.
  5. runtime/execution.json gets one row per card; the kept commits are the branch.

apply() fetches that branch into the person's project without touching their current branch or files;
undo() deletes it again while it is not merged. Nothing else in the project is written.
"""
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .ledger import TRAILER, key, keys
from .execute import apply_edits, candidate, git, model_messages, new_breakage, original_checks, project_checks, record, regressions, run_codemod

SIZE = 10
DEADCODE = re.compile(r"== \('([^']+)', '([^']*)', '([\w-]+)'\)")


def plan(report):
    """plan.json, each card with its key (eaos/ledger.py), which its commit carries."""
    data = json.loads((Path(report) / 'plan.json').read_text(encoding='utf-8'))
    ids = keys(data.get('tasks') or [])
    for card in data.get('tasks') or []: card['key'] = ids[card['id']]
    return data


def ready(card):
    return card.get('kind') == 'remediate' and (card.get('decision') or {}).get('readiness') == 'ready'


def ready_cards(report, skip=()):
    """The ready cards in the plan's order: milestone by milestone, and inside one, as the plan lists them."""
    if not (Path(report) / 'plan.json').is_file(): return []
    data = plan(report)
    by_id = {card['id']: card for card in data.get('tasks') or [] if card.get('id')}
    order = [card_id for milestone in data.get('milestones') or [] for card_id in milestone['tasks']]
    order += [card_id for card_id in by_id if card_id not in set(order)]
    return [by_id[i] for i in dict.fromkeys(order) if i in by_id and ready(by_id[i]) and i not in set(skip)]


def next_batch(report, done, size=SIZE):
    return [card['id'] for card in ready_cards(report, done)[:size]]


# ---------------------------------------------------------------- one collection, every acceptance

def batch_acceptance(report, cards, root, collected=None):
    """{card id: exit code} for every card's acceptance, from one collection of facts on `root` (`collected`,
    when the caller already made it). A `recheck --spec` acceptance and the dead-code check are read from that
    collection; anything else runs as written."""
    from .facts.run import collect, read_available
    from .probes import decide_probe
    out = Path(collected) if collected else Path(tempfile.mkdtemp(prefix='eaos-wave-facts-'))
    if not collected: collect(Path(root).resolve(), out)
    sets = read_available(out)
    dead = {(f['location'].get('path'), f['location'].get('symbol'), f['value'].get('rule'))
            for f in (sets.get('deadcode') or {}).get('facts', [])}
    exits = {}
    for card in cards:
        argv = card.get('verify_command') or []
        if 'recheck' in argv and '--spec' in argv:
            spec = json.loads(argv[argv.index('--spec') + 1])
            if (spec.get('specification') or {}).get('query') == 'load_blocker_present' and 'load_model' not in sets:
                from .load_model import compute, project
                sets['load_model'] = project(compute(out))
            status, _ = decide_probe(spec, sets)
            exits[card['id']] = 0 if status == 'REFUTED' else 1 if status in ('CONFIRMED', 'PARTIAL') else 2
        elif argv and (found := DEADCODE.search(argv[-1])):
            exits[card['id']] = 1 if found.groups() in dead else 0
        elif argv:
            exits[card['id']] = subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=1800).returncode
        else:
            exits[card['id']] = None
    return exits


# ---------------------------------------------------------------- the batch

def change(card, root, report, provider):
    """Make one card's change in the candidate: its codemod, or the assistant's edit. (tool, summary)."""
    uses_codemod = ((card.get('codemod') or {}).get('dry_run') or {}).get('files_changed', 0) > 0
    if uses_codemod:
        run_codemod(card, root, report)
        return 'codemod', card['codemod']['command']
    if provider is None: raise ValueError('this card has no codemod: a model provider is needed')
    answer, _ = provider.complete(model_messages(card, root))
    result = answer.get('result') or {}
    if not result.get('edits'): raise ValueError('the assistant made no edit: ' + str(result.get('summary'))[:200])
    apply_edits(root, result['edits'], set(card['paths']))
    return 'model', result.get('summary') or ''


def commit(root, card, tool):
    git(root, 'add', '-A')
    done = git(root, '-c', 'user.name=EAOS', '-c', 'user.email=eaos@localhost', 'commit', '--quiet', '-m',
               f"{card['id']}: {card['title'][:70]}\n\nExecuted by EAOS ({tool}).\n\n{TRAILER}: {card.get('key') or key(card)}")
    if done.returncode: raise RuntimeError('the change left nothing to commit')
    return git(root, 'rev-parse', 'HEAD').stdout.strip()


def rebuild(root, base, commits):
    """The candidate as `base` plus exactly `commits`, in order; the commits that no longer apply, returned."""
    git(root, 'reset', '--hard', '--quiet', base)
    dropped = []
    for sha in commits:
        if git(root, 'cherry-pick', '--allow-empty', sha).returncode:
            git(root, 'cherry-pick', '--abort')
            dropped.append(sha)
    return dropped


def gates(report, root, runtime, name, before, lock):
    """'' when the project's checks and the lock pass on `root`, else why not."""
    if before:
        broken = regressions(before, project_checks(root, runtime, 'S09', name))
        if broken: return "the project's own check failed: " + ', '.join(broken)
    if lock:
        from .behavior_lock import verify_lock
        verdict = verify_lock(report, root, runtime, name=name)
        if verdict['failed']: return f"the behaviour lock broke on {verdict['failed']} of {verdict['specs']} screens"
    return ''


def culprits(report, root, runtime, base, commits, before, lock, name, say, found=None):
    """The commits that make the gates fail, by halving: each half is tested on `base` alone."""
    found = [] if found is None else found
    if not commits: return found
    if len(commits) == 1:
        found.append(commits[0])
        return found
    half = len(commits) // 2
    for part in (commits[:half], commits[half:]):
        rebuild(root, base, part)
        say('bisect')
        if gates(report, root, runtime, f'{name}-bisect', before, lock):
            culprits(report, root, runtime, base, part, before, lock, name, say, found)
    return found


def open_batch(target, runtime, number):
    """The wave's candidate, cloned from the authorised commit: (root, base)."""
    from .sandbox import head, refusal
    reason = refusal(Path(runtime) / 'authorization.json', 'S08', head(target))
    if reason: raise PermissionError(reason)
    root = candidate(target, runtime, f'WAVE-{number}')
    return root, git(root, 'rev-parse', 'HEAD').stdout.strip()


def drop_last(root):
    """Take back the change being tried: its commit, and anything it left behind."""
    git(root, 'reset', '--hard', '--quiet', 'HEAD~1')
    git(root, 'clean', '-fdq')


def run_batch(report, target, runtime, number, card_ids, provider=None, lock=True, say=lambda *_: None):
    """Execute one wave; {'wave', 'branch', 'kept': [...], 'failed': {card: reason}, 'root', 'base'}."""
    report, runtime = Path(report), Path(runtime)
    cards = {card['id']: card for card in plan(report)['tasks'] if card['id'] in set(card_ids)}
    root, base = open_batch(target, runtime, number)
    kept, failed, tools = {}, {}, {}
    for index, card_id in enumerate(card_ids, 1):
        card = cards[card_id]
        say('card', index, len(card_ids), card)
        try:
            tools[card_id], _ = change(card, root, report, provider)
            sha = commit(root, card, tools[card_id])
            broke = new_breakage(report, root)
            if broke:
                git(root, 'reset', '--hard', '--quiet', 'HEAD~1')
                failed[card_id] = f'it broke something: {broke[0]}'
                continue
            kept[card_id] = sha
        except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as problem:
            git(root, 'reset', '--hard', '--quiet', 'HEAD')
            git(root, 'clean', '-fdq')
            failed[card_id] = f'{type(problem).__name__}: {problem}'[:300]
    return finish_batch(report, target, runtime, number, root, base, card_ids, kept, failed, tools, lock=lock, say=say)


def finish_batch(report, target, runtime, number, root, base, card_ids, kept, failed, tools, lock=True, say=lambda *_: None):
    """Every kept change together: the acceptances from one collection of facts, then the project's checks and
    the behaviour lock once, halving to the culprit when they fail. The kept commits become the wave's branch
    in the candidate, its patches and wave.json beside the run, and one execution.json row per card."""
    report, runtime = Path(report), Path(runtime)
    cards = {card['id']: card for card in plan(report)['tasks'] if card['id'] in set(card_ids)}
    kept, failed = dict(kept), dict(failed)
    say('acceptance')
    if kept:
        exits = batch_acceptance(report, [cards[c] for c in kept], root)
        for card_id, code in exits.items():     # no check of its own (None): kept on the gates, as fix_edit keeps it
            if code not in (0, None): failed[card_id] = f'its problem is still there (acceptance exited {code})'
        still = [kept[c] for c in kept if c not in failed]
        for sha in rebuild(root, base, still):
            failed[next(c for c, s in kept.items() if s == sha)] = 'it no longer applies once the others are in'
        kept = {c: s for c, s in kept.items() if c not in failed}
    before = original_checks(target, runtime)
    if kept:
        say('gates')
        name = f'wave-{number}'
        why = gates(report, root, runtime, name, before, lock)
        if why:
            order = list(kept.values())
            bad = culprits(report, root, runtime, base, order, before, lock, name, say)
            for card_id, sha in list(kept.items()):
                if sha in bad: failed[card_id] = why
            kept = {c: s for c, s in kept.items() if c not in failed}
            rebuild(root, base, list(kept.values()))
            if kept and gates(report, root, runtime, name, before, lock):
                for card_id in kept: failed[card_id] = 'the batch still failed its gates without the cards found responsible'
                kept = {}
                rebuild(root, base, [])
    for card_id in card_ids:
        ok = card_id in kept
        record(runtime, {'id': card_id, 'tool': tools.get(card_id, 'model'), 'status': 'VERIFIED_IN_ISOLATED_COPY' if ok else 'FAILED',
                         'acceptance_exit': 0 if ok else -1, 'result': (f'wave {number}' if ok else failed.get(card_id, ''))[:400]})
    patches = runtime / 'waves' / f'wave-{number}'
    subprocess.run(['rm', '-rf', str(patches)])
    patches.mkdir(parents=True, exist_ok=True)
    if kept: git(root, 'format-patch', '--quiet', '-o', str(patches), f'{base}..HEAD')
    summary = {'wave': number, 'branch': f'eaos/wave-{number}', 'root': str(root), 'base': base, 'kept': list(kept),
               'failed': failed, 'at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
               'stat': git(root, 'diff', '--shortstat', f'{base}..HEAD').stdout.strip()}
    (patches / 'wave.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return summary


# ---------------------------------------------------------------- handing it over

def apply(project, summary):
    """The wave's branch in the person's project, fetched from the candidate: their current branch, their
    working folder and their unsaved edits are not touched."""
    if not summary['kept']: raise ValueError('this wave kept no fix, so there is nothing to hand over')
    branch = summary['branch']
    done = git(project, 'fetch', '--quiet', summary['root'], f'+{branch}:{branch}')
    if done.returncode: raise RuntimeError(f'could not create {branch}: {done.stderr[-300:]}')
    return branch


def merged(project, branch):
    return git(project, 'merge-base', '--is-ancestor', branch, 'HEAD').returncode == 0


def undo(project, branch):
    """Delete a wave's branch; one already merged into the current branch is not undone here: that needs a revert,
    which is a decision for the person, not for EAOS."""
    if git(project, 'rev-parse', '--verify', '--quiet', branch).returncode: return 'absent'
    if merged(project, branch): return 'merged'
    git(project, 'branch', '-D', branch)
    return 'deleted'
