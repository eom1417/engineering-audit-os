"""Fix a batch of plan cards at once, and hand the result over as a branch (NS9.T4).

One card at a time behind every gate costs about twelve minutes a card; the first milestone of a real project
holds more than a hundred. So a batch (a wave) is executed together, and the expensive gates run once:

  1. The candidate: a clone of the authorised commit (eaos/execute.candidate); its branch is handed over as
     eaos/<branch>/wave-<n>, or the name the person gave in the fix preview.
  2. Each card: its codemod, or the assistant's edit (eaos/execute), committed alone, then the quick gate: no
     new broken code. A card that breaks something is taken back at once (its commit is dropped).
  3. The acceptance of every card from one collection of facts (batch_acceptance); a card whose problem is
     still there is dropped the same way.
  4. The project's own checks and the behaviour lock, once for the whole batch. When they fail, the batch is
     split in half until the card responsible is found (culprits), and only the cards that pass together stay.
  5. runtime/execution.json gets one row per card; the kept commits are the branch.

apply() fetches that branch into the person's project without touching their current branch or files;
undo() deletes it again while it is not merged. Nothing else in the project is written.

A wave is the flow `fix` of the live map (FLOW), drawn from the state at each save (draw, called by guided.save) to
<runtime>/progress/fix.jsonl: each card a step of `change`, then the end checks as they are reached, then the handover.
"""
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import progress
from . import ledger
from .decisions import ready, waiting
from .ledger import TRAILER, key, keys
from .progress.flow import OPTIONAL, Stage
from .execute import candidate, git, original_checks, project_checks, record, regressions, run_codemod

SIZE = 10
FLOW = (
    Stage('open', description='Make the separate copy the fixes are tried in, from the commit you allowed'),
    Stage('change', requires=('open',),
          description='Change the code card by card, by a codemod or your assistant; a change that breaks something '
                      'is taken back at once'),
    Stage('acceptance', requires=('change',), description='Check that each fixed problem is really gone'),
    Stage('gates', requires=('acceptance',),
          description="Run your project's own checks and compare every recorded screen, once for the whole batch"),
    Stage('culprit', requires=('gates',), necessity=OPTIONAL, absent_when='the batch passed its checks',
          description='Split the batch in half until the change that broke a check is found'),
    Stage('handover', requires=('gates',),
          description='Write down every card\'s result and hand the kept changes over as a branch in your project'),
)
FIX = 'fix'                     # the flow a batch draws (draw)
PHASES = {'acceptance': 'acceptance', 'regenerate': 'gates', 'gates': 'gates', 'control': 'gates', 'bisect': 'culprit'}
HANDED = ('applied', 'accepted', 'empty')
DEADCODE = re.compile(r"== \('([^']+)', '([^']*)', '([\w-]+)'\)")


def plan(report):
    """plan.json, each card with its key (eaos/ledger.py), which its commit carries."""
    data = json.loads((Path(report) / 'plan.json').read_text(encoding='utf-8'))
    ids = keys(data.get('tasks') or [])
    for card in data.get('tasks') or []: card['key'] = ids[card['id']]
    return data


def ready_cards(report, state=None):
    """The ready cards in the plan's order: milestone by milestone, and inside one, as the plan lists them; without a card
    the ledger holds other than open, nor one tried before (the state's `tried`, by key: a new check numbers the cards
    again) unless the ledger opened it again (ledger._reopen_waited), nor one waiting for a card not done yet
    (decisions.waiting), which goes in a later batch."""
    if not (Path(report) / 'plan.json').is_file(): return []
    book, tried = _book(state), set((state or {}).get('tried') or ())
    done = ledger.done(book)
    return [card for card in _in_order(plan(report)) if ready(card) and _free(card['key'], book, tried) and not waiting(card, done)]


def _free(key, book, tried):
    """Whether a batch may take the card: open in the ledger, and not tried before unless the ledger opened it again."""
    entry = book.get(key) or {'state': 'open'}
    return entry['state'] == 'open' and (key not in tried or bool(entry.get('reopened')))


def _in_order(data):
    """The plan's cards milestone by milestone, then the rest as listed."""
    by_id = {card['id']: card for card in data.get('tasks') or [] if card.get('id')}
    order = [card_id for milestone in data.get('milestones') or [] for card_id in milestone['tasks']]
    return [by_id[i] for i in dict.fromkeys(order + list(by_id)) if i in by_id]


def _book(state):
    """The ledger's cards by key; none before the project has one."""
    return ((ledger.load(state) if (state or {}).get('project') else None) or {}).get('cards') or {}


def too_early(state, cards):
    """Why the cards asked for cannot open a batch yet: some wait for cards not done (decisions.waiting); else None."""
    done = ledger.done(_book(state))
    early = {card['id']: waiting(card, done) for card in cards if waiting(card, done)}
    if not early: return None
    return {'error': '; '.join(f'{c} waits for {", ".join(w)}' for c, w in list(early.items())[:5]) + ': no batch was opened',
            'waits': early, 'what_now': 'A card goes in a batch once the cards it waits for are done (a module is split after '
                                        'its complex functions are simplified): call fix_start again without these cards.'}


def next_batch(report, state, size=SIZE):
    return [card['id'] for card in ready_cards(report, state)[:size]]


# ---------------------------------------------------------------- one collection, every acceptance

def engines_for(cards):
    """The engines a collection of facts on a changed copy runs: the security gate's (eaos/execute.py GATE_ENGINES),
    and those a card's own recheck asks again (a security card names the engines that found it)."""
    from .execute import GATE_ENGINES
    named = set()
    for card in cards:
        argv = card.get('verify_command') or []
        if 'recheck' in argv and '--spec' in argv:
            named |= set((json.loads(argv[argv.index('--spec') + 1]).get('specification') or {}).get('engines') or [])
    return sorted(set(GATE_ENGINES) | named)


def edit_gates(where, root, card, changed, repair):
    """(what one change of a batch broke or added against the code laws, the card's own check's exit (None for a
    repair), what that check still finds when it fails, so the assistant fixes what is left), from one collection of facts
    on the copy `root`; `where`: (report, project, runtime). A change to the app's
    files also runs the app's own checks (app_breakage): an unused import in a Studio file broke its type check, then
    its build, and was found only when the 51 changes of a batch met (EAOS, 2026-10-14)."""
    from .execute import app_breakage, new_breakage
    from .facts.run import collect
    from .gates import debt, words
    report, project, runtime = where
    with tempfile.TemporaryDirectory(prefix='eaos-edit-facts-') as out:
        collect(root.resolve(), out, engines=engines_for([card]))
        broke = (new_breakage(report, root, collected=out) + words(debt(report, out, changed, had=_sizes_before(root, changed)))
                 + app_breakage(project, runtime, root, changed))
        exit_code = None if repair else batch_acceptance(report, [card], root, collected=out).get(card['id'])
        return broke, exit_code, _still(card, out) if exit_code not in (0, None) else ''


def batch_acceptance(report, cards, root, collected=None):
    """{card id: exit code} for every card's acceptance, from one collection of facts on `root` (`collected`,
    when the caller already made it, with engines_for(cards)). A `recheck --spec` acceptance and the dead-code check
    are read from that collection; anything else runs as written."""
    from .facts.run import collect, read_available
    out = Path(collected) if collected else Path(tempfile.mkdtemp(prefix='eaos-wave-facts-'))
    if not collected: collect(Path(root).resolve(), out, engines=engines_for(cards))
    sets = read_available(out)
    dead = {(f['location'].get('path'), f['location'].get('symbol'), f['value'].get('rule'))
            for f in (sets.get('deadcode') or {}).get('facts', [])}
    return {card['id']: _acceptance_exit(card, sets, dead, out, root) for card in cards}


def _probe_exit(spec, sets, out):
    from .probes import decide_probe
    if (spec.get('specification') or {}).get('query') == 'load_blocker_present' and 'load_model' not in sets:
        from .load_model import compute, project
        sets['load_model'] = project(compute(out))
    status, _ = decide_probe(spec, sets)
    return 0 if status == 'REFUTED' else 1 if status in ('CONFIRMED', 'PARTIAL') else 2


def _sizes_before(root, paths):
    """Each changed file's lines in the copy just before the change (counted as facts/metrics counts them): a file over the
    limit is judged by whether this change grew it, not by the check on record, which an earlier batch may have outgrown
    (EAOS, 2026-10-15: a repair that left an 876-line test file as long was refused as growing it from 861)."""
    out = {}
    for path in paths:
        shown = git(root, 'show', f'HEAD~1:{path}')
        if not shown.returncode: out[path] = len(shown.stdout.split('\n'))
    return out


def _still(card, out):
    """What a card's own probe still finds on the copy, in its words; '' when its check is not a probe."""
    from .facts.run import read_available
    from .probes import decide_probe
    argv = card.get('verify_command') or []
    if not ('recheck' in argv and '--spec' in argv): return ''
    return decide_probe(json.loads(argv[argv.index('--spec') + 1]), read_available(out))[1]


def _acceptance_exit(card, sets, dead, out, root):
    """One card's acceptance exit: read from the collection when it is a probe or the dead-code check, else run."""
    argv = card.get('verify_command') or []
    if 'recheck' in argv and '--spec' in argv:
        return _probe_exit(json.loads(argv[argv.index('--spec') + 1]), sets, out)
    found = DEADCODE.search(argv[-1]) if argv else None
    if found: return 1 if found.groups() in dead else 0
    if argv: return subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=1800).returncode
    return None


# ---------------------------------------------------------------- the batch

def change(card, root, report):
    """Make one card's change in the candidate with its codemod: (tool, summary). A card without one is the
    assistant's to edit (fix_edit)."""
    uses_codemod = ((card.get('codemod') or {}).get('dry_run') or {}).get('files_changed', 0) > 0
    if not uses_codemod: raise ValueError('this card has no codemod: the assistant edits it')
    run_codemod(card, root, report)
    return 'codemod', card['codemod']['command']


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


def without(wave, card):
    """An open batch's copy rebuilt without a kept card: every other kept change and repair takes its new commit, and
    one that no longer applies without it fails, saying so, instead of staying kept with a commit the copy lacks."""
    wave['kept'].pop(card)
    repairs = wave.get('repairs') or []
    dropped = set(rebuild(wave['root'], wave['base'], list(wave['kept'].values()) + repairs))
    made = iter(git(wave['root'], 'rev-list', '--reverse', f"{wave['base']}..HEAD").stdout.split())
    for other, sha in list(wave['kept'].items()):
        if sha in dropped:
            wave['kept'].pop(other)
            wave['failed'][other] = f'its change no longer applies once {card} was skipped'
        else: wave['kept'][other] = next(made)
    if repairs: wave['repairs'] = [next(made) for sha in repairs if sha not in dropped]


def gates(batch, name):
    """'' when the project's checks and the lock pass on the batch's copy as it is now, else why not. A screen the
    batch's design cards declare may look different (`declared`, eaos/behavior_lock.py): that is their change."""
    if batch['before']:
        broken = regressions(batch['before'], project_checks(batch['root'], batch['runtime'], 'S09', name))
        if broken: return "the project's own check failed: " + ', '.join(broken)
    if batch['lock']:
        from .behavior_lock import verify_lock
        verdict = verify_lock(batch['report'], batch['root'], batch['runtime'], name=name, declared=batch['declared'],
                              known=batch.get('known') or ())
        if verdict['failed']:      # every screen that differs, at once: one per run cost a batch hours
            from .behavior_lock import failing_tests
            return (f"the behaviour lock broke on {verdict['failed']} of {verdict['specs']} specs: "
                    + '; '.join(sorted(failing_tests(batch['runtime'], name)))[:600])
    return ''


def culprits(batch, commits, found=None):
    """{commit: why it fails the gates}, found by halving: each half is tested on `base` alone with the files its build
    makes rebuilt (without them every half failed the same way, and every change touching the Studio was left out),
    and each run keeps its own logs (named by its first commit and its size), so a culprit carries its own reason."""
    found = {} if found is None else found
    half = len(commits) // 2
    for part in (commits[:half], commits[half:]):
        if not part: continue
        _rebuilt(batch, part)
        batch['say']('bisect')
        why = gates(batch, f"{batch['name']}-bisect-{part[0][:8]}-{len(part)}")
        if why and len(part) == 1: found[part[0]] = why
        elif why: culprits(batch, part, found)
    return found


def _rebuilt(batch, commits):
    """The copy as `base` plus exactly `commits`, and the files its build makes rebuilt from them."""
    rebuild(batch['root'], batch['base'], commits)
    if commits: batch['regenerate'](batch['root'])


def declared_screens(cards):
    """The screens a batch may change the look of: every one ('*') when it holds a design card, else none. A design card
    changes a shared part (a font, a card, a strip) that shows on pages its finding never named: by those pages, each run
    found one more screen and 33 sound design cards were left out (EAOS, 2026-10-15). Their pictures are the next check's
    to review; a page's errors and its server's answers stay locked."""
    return {'*'} if any((card.get('design') or {}).get('findings') for card in cards) else set()


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


class GatesFailed(Exception):
    """The kept changes pass one by one but fail the project's checks together: `why`, and the failing commands' output,
    for a repair on top of them before any card is left out."""
    def __init__(self, why, output):
        super().__init__(why)
        self.why, self.output = why, output


def finish_batch(report, target, runtime, wave, **options):
    """Every kept change of `wave` (the open batch: number, root, base, cards, kept, failed, tools, deliver_as) together,
    then options['repairs'] (commits made on top of them after a failure): the acceptances from one collection of facts,
    then the project's checks and the behaviour lock once (options['lock'], default True). When they fail, GatesFailed
    asks for a repair, unless options['bisect'] (default True): then halving finds the culprits, left out. The kept
    commits become the wave's branch in the candidate, its patches and wave.json beside the run, and one execution.json
    row per card. options['say'] names each step; options['regenerate'] rebuilds the files the build makes."""
    say, regenerate = options.get('say') or (lambda *_: None), options.get('regenerate') or (lambda root: None)
    batch = {'report': Path(report), 'root': Path(wave['root']), 'runtime': Path(runtime), 'base': wave['base'],
             'name': f"wave-{wave['number']}", 'lock': options.get('lock', True), 'say': say,
             'bisect': options.get('bisect', True), 'regenerate': regenerate}
    cards = {card['id']: card for card in plan(batch['report'])['tasks'] if card['id'] in set(wave['cards'])}
    kept, failed = dict(wave['kept']), dict(wave['failed'])
    say('acceptance')
    progress.begin('acceptance')
    if kept: kept = _accepted(batch, cards, kept, failed, list(options.get('repairs') or ()))
    else: progress.skip('acceptance', 'no change was kept to check', 'nothing_kept')
    if kept:                                    # the files the build makes, rebuilt from the batch's source
        say('regenerate')
        regenerate(batch['root'])
    progress.begin('gates')
    batch.update(before=original_checks(target, batch['runtime']), declared=declared_screens(cards[c] for c in kept))
    kept = _through_gates(batch, kept, failed)
    progress.begin('handover')
    _record_cards(batch, wave, kept, failed)
    return _write_wave(batch, wave, kept, failed)


def _accepted(batch, cards, kept, failed, repairs):
    """The kept cards whose problem is gone and whose commit still applies beside the others (the repairs on top)."""
    exits = batch_acceptance(batch['report'], [cards[c] for c in kept], batch['root'])
    for card_id, code in exits.items():     # no check of its own (None): kept on the gates, as fix_edit keeps it
        if code not in (0, None): failed[card_id] = f'its problem is still there (acceptance exited {code})'
    still = [kept[c] for c in kept if c not in failed]
    for sha in set(rebuild(batch['root'], batch['base'], still + repairs)) - set(repairs):
        failed[next(c for c, s in kept.items() if s == sha)] = 'it no longer applies once the others are in'
    _acceptance_steps(kept, failed, exits)
    return {c: s for c, s in kept.items() if c not in failed}


def _acceptance_steps(kept, failed, exits):
    """One progress step per kept card: ok, or why it was left out."""
    for done, card_id in enumerate(kept, 1):
        code = '' if card_id not in failed else 'acceptance_failed' if exits.get(card_id) not in (0, None) else 'no_longer_applies'
        progress.step(card_id, done, len(kept), 'failed' if card_id in failed else 'ok', reason=failed.get(card_id, ''),
                      reason_code=code)


def _through_gates(batch, kept, failed):
    """The kept cards once the project's checks and the lock ran on all of them together."""
    if not kept:
        progress.skip('gates', 'no change was kept to check', 'nothing_kept')
        progress.skip('culprit', 'no change was kept to check', 'nothing_kept')
        return kept
    batch['say']('gates')
    why = gates(batch, batch['name'])
    if why and _against_control(batch): why = gates(batch, f"{batch['name']}-again")
    if not why:
        progress.step('batch', 1, 1, 'ok')
        progress.skip('culprit', 'the batch passed its checks', 'gates_passed')
        return kept
    progress.step('batch', 1, 1, 'failed', reason=str(why)[:200], reason_code='gates_failed')
    if not batch['bisect']:
        progress.skip('culprit', 'a repair on top of the changes comes first', 'repair_asked')
        raise GatesFailed(why, failing_output(batch['runtime'], batch['name']))
    progress.begin('culprit')
    return _without_culprits(batch, kept, failed)


def _against_control(batch):
    """The batch failed: the same checks on its base alone, now. What fails there too comes from around the batch (data
    or time that moved since the recording), not from its changes: the checks are judged against this control from now
    on, so no card is blamed for it (EAOS on itself, 2026-10-13: a screen reading live data failed with every card, and
    a whole batch of sound fixes was left out). True when the control set something aside."""
    from .behavior_lock import failing_tests, verify_lock
    head, name = git(batch['root'], 'rev-parse', 'HEAD').stdout.strip(), f"{batch['name']}-control"
    batch['say']('control')
    rebuild(batch['root'], batch['base'], [])
    try:
        before = project_checks(batch['root'], batch['runtime'], 'S09', name) if batch['before'] else batch['before']
        if batch['lock']: verify_lock(batch['report'], batch['root'], batch['runtime'], name=name)
        known = failing_tests(batch['runtime'], name) if batch['lock'] else set()
    finally:
        git(batch['root'], 'reset', '--hard', '--quiet', head)
    moved = bool(known) or bool(regressions(batch['before'], before))
    batch.update(before=before, known=known)
    return moved


def failing_output(runtime, name, size=6000):
    """The end of what each failing command of the gates `name` printed (runtime/checks-<name>-log.json)."""
    try: commands = json.loads((Path(runtime) / f'runtime/checks-{name}-log.json').read_text(encoding='utf-8'))['commands']
    except (OSError, ValueError, KeyError): return []
    return [{'command': ' '.join(c['argv']), 'output': (c.get('tail') or '')[-size:]} for c in commands if c.get('exit')]


def _named(batch, commits):
    """The culprits the failure names, tried first, in one run: the batch without the changes to a file the failing checks
    print. When it then passes, they are the culprits; halving 68 changes ran the whole suite again and again, on half
    applied splits, for hours, though the output named the one file (EAOS, 2026-10-15). {} when none or all are named, or
    leaving the named ones out is not enough."""
    said = ' '.join(c['output'] for n in (batch['name'], f"{batch['name']}-again") for c in failing_output(batch['runtime'], n))
    files = {sha: git(batch['root'], 'show', '--name-only', '--format=', sha).stdout.split() for sha in commits}
    named = [sha for sha in commits if any(f in said or f.removesuffix('.py').replace('/', '.') in said for f in files[sha])]
    if not named or len(named) == len(commits): return {}
    _rebuilt(batch, [sha for sha in commits if sha not in named])
    batch['say']('bisect')
    if gates(batch, f"{batch['name']}-named"): return {}
    return {sha: "the project's checks failed naming the files it changed, and passed without it" for sha in named}


def _without_culprits(batch, kept, failed):
    bad = _named(batch, list(kept.values())) or culprits(batch, list(kept.values()))
    for card_id, sha in list(kept.items()):
        if sha in bad: failed[card_id] = bad[sha]
    kept = {c: s for c, s in kept.items() if c not in failed}
    _rebuilt(batch, list(kept.values()))
    if kept and gates(batch, batch['name']):
        for card_id in kept: failed[card_id] = 'the batch still failed its gates without the cards found responsible'
        kept = {}
        rebuild(batch['root'], batch['base'], [])
    return kept


def _record_cards(batch, wave, kept, failed):
    for card_id in wave['cards']:
        ok = card_id in kept
        record(batch['runtime'], {'id': card_id, 'tool': wave['tools'].get(card_id, 'assistant'),
                                  'status': 'VERIFIED_IN_ISOLATED_COPY' if ok else 'FAILED', 'acceptance_exit': 0 if ok else -1,
                                  'result': (f"wave {wave['number']}" if ok else failed.get(card_id, ''))[:400]})


def _write_wave(batch, wave, kept, failed):
    """The wave's patches and wave.json beside the run; the summary."""
    root, base, number, branch = batch['root'], batch['base'], wave['number'], wave.get('deliver_as')
    patches = batch['runtime'] / 'waves' / f'wave-{number}'
    subprocess.run(['rm', '-rf', str(patches)])
    patches.mkdir(parents=True, exist_ok=True)
    if kept: git(root, 'format-patch', '--quiet', '-o', str(patches), f'{base}..HEAD')
    summary = {'wave': number, 'branch': branch or f'eaos/wave-{number}', 'root': str(root), 'base': base, 'kept': list(kept),
               'failed': failed, 'at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
               'stat': git(root, 'diff', '--shortstat', f'{base}..HEAD').stdout.strip()}
    (patches / 'wave.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return summary


# ---------------------------------------------------------------- handing it over

def apply(project, summary):
    """The wave's branch in the person's project, fetched from the candidate: their current branch, their
    working folder and their unsaved edits are not touched. The candidate's checkout (its kept commits) arrives under the
    wave's name, whatever the candidate's own branch is called."""
    if not summary['kept']: raise ValueError('this wave kept no fix, so there is nothing to hand over')
    branch = summary['branch']
    done = git(project, 'fetch', '--quiet', summary['root'], f'+HEAD:refs/heads/{branch}')
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


# ---------------------------------------------------------------- the batch, on the live map

def draw(state, runtime):
    """The open batch as the flow `fix` (waves.FLOW), drawn again from the state at each of its saves, and once more when it
    closes. No process holds a batch, the assistant's tool calls work it card by card, so nothing drew it and the live map
    read "waiting" through every batch (owner, 2026-10-15). Called by guided.save; None when there is nothing to draw."""
    wave, last = state.get('open_wave'), (state.get('waves') or [None])[-1]
    if not wave:
        if not (last or {}).get('cards') or state.get('fix_drawn') == last['number']: return None   # a build's: draw_build
        wave, state['fix_drawn'] = last, last['number']
    progress.path_for(runtime, FIX).unlink(missing_ok=True)       # a drawing, not a run
    log = progress.ProgressLog(runtime, FIX, pulse=False, sampler=None, alive_every=None)
    log.started(FLOW, [s.name for s in FLOW], {}, steps={}, process=False, at=wave.get('opened'))
    _draw_cards(log, wave)
    _draw_phases(log, wave)
    if wave.get('status') in HANDED:
        log.stage_started('handover')
        _end(log, 'handover', 'ok', None, wave.get('branch') or '')
        log.finish('COMPLETE')
    elif wave.get('status'): log.finish('STOPPED', reason=wave.get('why') or wave['status'])
    else: log.close()
    return progress.path_for(runtime, FIX)


def _draw_phases(log, wave):
    """The checks at the batch's end, each from when it was reached (batch_finish._phase) to when the next one was."""
    reached = {}
    for kind, at in (wave.get('phases') or {}).items(): reached.setdefault(PHASES.get(kind, kind), at)
    phases = list(reached.items())
    for (stage, at), after in zip(phases, phases[1:] + [None]):
        log.stage_started(stage, at=at)
        if after or wave.get('status'): _end(log, stage, 'ok', after[1] if after else None)


def _draw_cards(log, wave):
    """The copy opened, then a step per card: kept, or set aside with why; the change ends once the checks begin."""
    log.stage_started('open', at=wave.get('opened'))
    _end(log, 'open', 'ok', wave.get('opened'))
    log.stage_started('change', at=wave.get('opened'))
    step, cards = log.stepper('change'), wave['cards']
    for done, card in enumerate(cards, 1):
        if card in wave['kept']: step(card, done, len(cards), 'ok', seconds=0)
        elif card in wave['failed']: step(card, done, len(cards), 'skipped', reason=str(wave['failed'][card]))
    if wave.get('phases') or wave.get('status'):
        _end(log, 'change', 'ok', next(iter((wave.get('phases') or {}).values()), None))


def _end(log, stage, status, at, artifact=''):
    log.ended({'stage': stage, 'status': status, 'reason': '', 'seconds': None, 'necessity': 'required',
               'artifacts': [artifact] if artifact else []}, **({'at': at} if at else {}))
