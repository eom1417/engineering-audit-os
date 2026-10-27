"""One batch of cards executed in the candidate behind its gates, kept or taken back, and handed over as a branch."""
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ....core import progress
from ....core.project.ledger import TRAILER, key
from ..execute import git, original_checks, own_batch, project_checks, record, regressions, run_codemod
from .acceptance import _still, batch_acceptance, engines_for
from .cards import plan


# ---------------------------------------------------------------- one change, its gates

def edit_gates(where, root, card, changed, repair):
    """(what one change of a batch broke or added against the code laws, the card's own check's exit (None for a
    repair), what that check still finds when it fails, so the assistant fixes what is left), from one collection of facts
    on the copy `root`; `where`: (report, project, runtime). A change to the app's
    files also runs the app's own checks (app_breakage): an unused import in a Studio file broke its type check, then
    its build, and was found only when the 51 changes of a batch met (EAOS, 2026-10-14)."""
    from ..execute import app_breakage, new_breakage
    from ....facts.run import collect
    from ....analysis.repair.gates import debt, words
    report, project, runtime = where
    with tempfile.TemporaryDirectory(prefix='eaos-edit-facts-') as out:
        collect(root.resolve(), out, engines=engines_for([card]))
        broke = (new_breakage(report, root, collected=out) + words(debt(report, out, changed, had=_sizes_before(root, changed)))
                 + app_breakage(project, runtime, root, changed))
        exit_code = None if repair else batch_acceptance(report, [card], root, collected=out).get(card['id'])
        return broke, exit_code, _still(card, out) if exit_code not in (0, None) else ''


def _sizes_before(root, paths):
    """Each changed file's lines in the copy just before the change (counted as facts/metrics counts them): a file over the
    limit is judged by whether this change grew it, not by the check on record, which an earlier batch may have outgrown
    (EAOS, 2026-10-15: a repair that left an 876-line test file as long was refused as growing it from 861)."""
    out = {}
    for path in paths:
        shown = git(root, 'show', f'HEAD~1:{path}')
        if not shown.returncode: out[path] = len(shown.stdout.split('\n'))
    return out


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
    batch's design cards declare may look different (`declared`, eaos/live/behavior/lock.py): that is their change."""
    if batch['before']:
        broken = regressions(batch['before'], project_checks(batch['root'], batch['runtime'], 'S09', name))
        if broken: return "the project's own check failed: " + ', '.join(broken)
    if batch['lock']:
        from ....live.behavior.lock import LockPass, verify_lock
        verdict = verify_lock(batch['report'], batch['root'], batch['runtime'],
                              LockPass(name, declared=batch['declared'], known=batch.get('known') or (), intended=batch.get('intended')))
        if verdict['failed']:      # every screen that differs, at once: one per run cost a batch hours
            from ....live.behavior.lock import failing_tests
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
    to review; a page's errors and its server's answers stay locked. A design card that declares the screens it changes
    (`changes_screens`) is judged by its declaration instead (intended_screens)."""
    return {'*'} if any((card.get('design') or {}).get('findings') and not card.get('changes_screens') for card in cards) else set()


def intended_screens(cards):
    """{screen: the words its cards add} of the batch's cards that declare the screens they change on purpose
    (eaos/live/behavior/intended.py): on those screens only the declared addition passes the lock."""
    from ....live.behavior.intended import screens_of
    return screens_of(cards)


def open_batch(target, runtime, number):
    """The wave's candidate, cloned from the authorised commit: (root, base)."""
    return own_batch(target, runtime, f'WAVE-{number}')


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
    kept = _secure(batch, kept, failed, list(options.get('repairs') or ()))
    if kept:                                    # the files the build makes, rebuilt from the batch's source
        say('regenerate')
        regenerate(batch['root'])
    progress.begin('gates')
    batch.update(before=original_checks(target, batch['runtime']), declared=declared_screens(cards[c] for c in kept),
                 intended=intended_screens(map(cards.get, kept)))
    kept = _through_gates(batch, kept, failed)
    _new_truth(batch, kept, cards)
    progress.begin('handover')
    _record_cards(batch, wave, kept, failed)
    return _write_wave(batch, wave, kept, failed)


def _accepted(batch, cards, kept, failed, repairs):
    """The kept cards whose problem is gone and whose commit still applies beside the others (the repairs on top)."""
    exits = batch_acceptance(batch['report'], [cards[c] for c in kept], batch['root'])
    for card_id, code in exits.items():     # no check of its own (None): kept on the gates, as fix_edit keeps it
        if code not in (0, None): failed[card_id] = f'its problem is still there (acceptance exited {code})'
    _rebuilt_without(batch, kept, failed, repairs)
    _acceptance_steps(kept, failed, exits)
    return {c: s for c, s in kept.items() if c not in failed}


BATCH_ENGINES = ('semgrep',)   # the security engine too slow for every change (GATE_ENGINES), run once on the batch


def _secure(batch, kept, failed, repairs):
    """The kept cards once the slower security engine read all of them together (M7.5): a card whose change brings in a
    finding of it the check had not, in a file it changed, is left out; batch['security'] says what ran and what it found."""
    from ....facts.run import collect
    from ....analysis.assessments.weaknesses import new
    if not kept: return kept
    batch['say']('security')
    changed = {c: set(git(batch['root'], 'show', '--name-only', '--format=', sha).stdout.split()) for c, sha in kept.items()}
    with tempfile.TemporaryDirectory(prefix='eaos-batch-security-') as out:
        collect(batch['root'].resolve(), out, engines=list(BATCH_ENGINES))
        brought = new(batch['report'], out, set().union(*changed.values()))
    _blamed(changed, brought, failed)
    batch['security'] = {'engines': list(BATCH_ENGINES), 'brought': [list(row) for row in brought]}
    if any(c in failed for c in kept): _rebuilt_without(batch, kept, failed, repairs)
    return {c: s for c, s in kept.items() if c not in failed}


def _blamed(changed, brought, failed):
    """Each card whose changed files hold a finding the batch brought in, failed with it."""
    for card_id, paths in changed.items():
        mine = [f'{rule} ({engine}) in {path}' for engine, rule, path in brought if path in paths]
        if mine: failed[card_id] = 'it brings a security finding in: ' + '; '.join(mine)[:300]


def _rebuilt_without(batch, kept, failed, repairs):
    """The copy rebuilt with the kept changes not failed (the repairs on top); each that no longer applies, failed."""
    still = [kept[c] for c in kept if c not in failed]
    for sha in set(rebuild(batch['root'], batch['base'], still + repairs)) - set(repairs):
        failed[next(c for c, s in kept.items() if s == sha)] = 'it no longer applies once the others are in'


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


def _new_truth(batch, kept, cards):
    """Once a batch is kept, the screens its cards changed on purpose recorded again on its code, so the next card is
    compared with them (eaos/live/behavior/rerecord.py record_intended); the cards left out by the gates declare nothing."""
    screens = intended_screens([cards[c] for c in kept]) if batch['lock'] else {}
    if not screens: return
    from ....live.behavior.rerecord import record_intended
    batch['say']('record')
    try: record_intended(batch['report'], batch['root'], batch['runtime'], set(screens))
    except Exception as problem:    # noqa: BLE001 - the batch passed its gates: kept; the next card meets the older truth
        batch.setdefault('limitations', []).append(f'the screens this batch changed could not be recorded again: {problem}'[:400])


def _against_control(batch):
    """The batch failed: the same checks on its base alone, now. What fails there too comes from around the batch (data
    or time that moved since the recording), not from its changes: the checks are judged against this control from now
    on, so no card is blamed for it (EAOS on itself, 2026-10-13: a screen reading live data failed with every card, and
    a whole batch of sound fixes was left out). True when the control set something aside."""
    from ....live.behavior.lock import LockPass, failing_tests, verify_lock
    head, name = git(batch['root'], 'rev-parse', 'HEAD').stdout.strip(), f"{batch['name']}-control"
    batch['say']('control')
    rebuild(batch['root'], batch['base'], [])
    try:
        before = project_checks(batch['root'], batch['runtime'], 'S09', name) if batch['before'] else batch['before']
        if batch['lock']: verify_lock(batch['report'], batch['root'], batch['runtime'], LockPass(name))
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
    named = _named_in_output(batch, commits)
    if not named or len(named) == len(commits): return {}
    _rebuilt(batch, [sha for sha in commits if sha not in named])
    batch['say']('bisect')
    if gates(batch, f"{batch['name']}-named"): return {}
    return {sha: "the project's checks failed naming the files it changed, and passed without it" for sha in named}


def _named_in_output(batch, commits):
    """The commits that change a file the failing checks' output names (by its path, or a Python file by its module)."""
    said = ' '.join(c['output'] for n in (batch['name'], f"{batch['name']}-again") for c in failing_output(batch['runtime'], n))
    files = {sha: git(batch['root'], 'show', '--name-only', '--format=', sha).stdout.split() for sha in commits}
    return [sha for sha in commits if any(f in said or f.removesuffix('.py').replace('/', '.') in said for f in files[sha])]


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
               'stat': git(root, 'diff', '--shortstat', f'{base}..HEAD').stdout.strip(), **({'security': batch['security']} if batch.get('security') else {}),
               **({'limitations': batch['limitations']} if batch.get('limitations') else {})}
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
