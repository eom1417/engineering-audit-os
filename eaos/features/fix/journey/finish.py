"""Handing a batch of fixes over (the job behind the MCP fix_finish), and the repair on top of it.

Every kept change goes together through the project's checks (eaos/features/fix/journey/waves finish_batch). When the
changes pass one by one but fail together, no sound card is left out at first: the answer asks the assistant for
a repair on top of them, a fix_edit on the card REPAIR, and fix_finish runs again; only after REPAIRS repairs, or
when asked to leave them out, halving finds the cards responsible. A batch that passes becomes a branch waiting for
the person, or lands on its base branch when the person chose so. """

from pathlib import Path

from ...guided import journey as guided
from ....kernel.project import state as project_state
from ....kernel.system.clock import now
from ....kernel.system.files import read_json

REPAIR = 'REPAIR'        # the card of a repair on top of the batch
REPAIRS = 3             # repairs tried before the cards responsible are left out
STEPS = {'acceptance': (0, "every problem is gone, all changes together"),
         'regenerate': (1, 'rebuilding the files the build makes'),
         'security': (1, 'the security engines on every change together'),
         'gates': (1, "the project's own checks and every screen"),
         'control': (1, 'the same checks on the code before the batch, to tell its changes from their surroundings'),
         'bisect': (2, 'finding the change that broke something')}


def open_step(wave):
    """status's next step while the batch is open."""
    if wave.get('gates_failed'):
        return (f'fix_edit card="{REPAIR}", then fix_finish',
                f"batch {wave['number']}: its changes fail the checks together "
                f"({wave['gates_failed'][:200]}); repair them on top")
    return 'fix_edit, then fix_finish', f"batch {wave['number']} is open"


def repair_card(wave):
    number = len(wave.get('repairs') or []) + 1
    return {'id': REPAIR, 'title': "Make the batch's changes pass the project's checks together",
            'key': f"repair-{wave['number']}-{number}"}


def repaired(state, root, changed, diff):
    """A repair kept: its commit stays on top of the batch, and fix_finish runs again."""
    wave = state['open_wave']
    wave.setdefault('repairs', []).append(guided._git(root, 'rev-parse', 'HEAD').stdout.strip())
    wave.pop('gates_failed', None)
    guided.save(state)
    return {'card': REPAIR, 'kept': True, 'files': changed, 'diff': diff,
            'what_now': 'The repair is kept on top of the batch: call fix_finish again, '
                        'to run every check on all of it.'}


def finish_job(project, arguments, progress):
    from .regenerate import keep_guide, regenerate
    from .waves import GatesFailed, finish_batch
    state = project_state.load(project)
    if stop := guided.stale_refusal(state): return stop
    wave = state['open_wave']
    was = guided._git(wave['root'], 'rev-parse', 'HEAD').stdout.strip()
    repairs = wave.get('repairs') or []
    try:
        summary = finish_batch(guided.report_of(state), guided.source(state), project_state.runtime_of(state), wave,
                               # no screen recorded: its own checks hold it
                               lock=not (state.get('setup') or {}).get('no_interface'),
                               say=lambda kind, *_: _phase(project, kind, progress), repairs=repairs,
                               bisect=bool(arguments.get('leave_out')) or len(repairs) >= REPAIRS,
                               before_writing=lambda: guided.refuse_if_stale(project_state.load(project)),
                               regenerate=lambda root: (
                                   regenerate(root, project_state.runtime_of(state), wave['base'],
                                              wave['number']),
                                   keep_guide(root, guided.report_of(state), state['project'], wave['number'],
                                              wave['base'])))
    # the batch stays as it was, even stopped mid-way: its copy back to its kept changes
    except BaseException as problem:
        guided._git(wave['root'], 'cherry-pick', '--abort')
        guided._git(wave['root'], 'reset', '--hard', '--quiet', was or wave['base'])
        guided._git(wave['root'], 'clean', '-fdq')
        state = project_state.load(project)
        if isinstance(problem, guided.StaleBatch): return _no_hand_over(state, problem)
        if isinstance(problem, GatesFailed): return _repair_asked(state, problem, len(repairs))
        if not isinstance(problem, Exception): raise          # stopped by the person: nothing failed, the batch goes on
        state['open_wave']['last_error'] = f'{type(problem).__name__}: {problem}'[:500]
        guided.save(state)
        raise
    return _handed_over(project, wave, summary)


def _no_hand_over(state, stale):
    state['open_wave'].pop('phases', None)      # the live map shows no hand-over that never came
    guided.save(state)
    return stale.answer


def _phase(project, kind, progress):
    """A phase of the batch's end reached: told to the job, and kept on the open batch so the live map shows it."""
    if kind not in STEPS: return
    progress(STEPS[kind][0], 3, STEPS[kind][1])
    state = project_state.load(project)
    state['open_wave'].setdefault('phases', {}).setdefault(kind, now('milliseconds'))
    guided.save(state)


def _repair_asked(state, failure, repaired_already):
    state['open_wave']['gates_failed'] = failure.why[:500]
    guided.save(state)
    return {'status': 'gates_failed', 'why': failure.why, 'failing': failure.output,
            'repairs_left': REPAIRS - repaired_already,
            'what_now': 'Every change passed on its own, but together they fail the project\'s checks (`failing` is '
                        'what the checks printed). Nothing is lost: find the cause in the code with fix_read and '
                        'repair it on top, with '
                        f'fix_edit and card="{REPAIR}" (an import cycle between parts of a split module, '
                        'a file the split forgot, a function grown past the limit...), then call fix_finish again. '
                        'Only if no repair can work, call fix_finish with leave_out=true: the cards responsible are '
                        'then found and left out.'}


def _score(state, wave, summary):
    """How the batch did on the first try, and the cards it failed that an earlier batch failed too: a card failing
    twice is EAOS's defect, not the person's project (its card or its check is wrong), and is said so."""
    from ....kernel.project.ledger import load
    book, keys = (load(state) or {}).get('cards') or {}, wave.get('keys') or {}
    again = [c for c in summary['failed'] if (book.get(keys.get(c)) or {}).get('attempts', 0) >= 1]
    return {'first_try': f"{len(summary['kept'])} of {len(wave['cards'])} kept on the first try",
            **({'failed_again': again,
                'eaos_defect': 'These cards failed in an earlier batch too: tell the person this is a '
                'defect of EAOS (the card or its check), to report, not a problem of their project.'} if again else {})}


def _handed_over(project, wave, summary):
    """The batch closed: its record among the waves, its branch in the project when it kept something."""
    from .waves import apply as hand_over
    from .split import said as split_said, split
    state = project_state.load(project)
    score = _score(state, wave, summary)
    record = _record(state, wave, summary)
    if summary['kept']:
        hand_over(state['project'], summary)
        record.update(split((guided.report_of(state), project_state.runtime_of(state), state['project']),
                            wave, summary))
        record['status'] = 'applied'
        record['tip'] = guided._git(state['project'], 'rev-parse', summary['branch']).stdout.strip()
        state['applied'] = True
    state.setdefault('waves', []).append(record)
    state['tried'] = sorted(set(state.get('tried') or []) | set((wave.get('keys') or {}).values()))     # keys: ids move
    state.pop('open_wave', None)
    guided.save(state)
    guided.publish_fixes(state, record)
    guided.save(state)
    files = (guided._git(state['project'], 'diff', '--stat', f"{wave['base']}..{summary['branch']}").stdout.strip()
             if summary['kept'] else '')
    if wave.get('direct') and record['status'] == 'applied':
        return _land(state['project'], record, files)
    said, words = _said_too(state, wave, summary['branch'])    # a branch that kept nothing has no diff
    pieces, piece_words = split_said(record)
    return {'batch': wave['number'], 'branch': summary['branch'] if summary['kept'] else None, 'kept': summary['kept'],
            'failed': summary['failed'], 'changes': summary['stat'], 'files': files[-4000:], **score, **said, **pieces,
            **({'continued_on': wave['continues']} if wave.get('continues') else {}),
            'what_now': (f"Tell the person, in plain words, what was fixed and that it is on the branch "
                         f"{summary['branch']}; "
                         "their current branch is unchanged. Ask whether to take it in (accept) or throw it away "
                         "(undo). "
                         "The report counts these fixes as done only once they are taken in."
                         if summary['kept'] else 'No change passed every gate; nothing reached the project.')
                        + piece_words + words}


def _said_too(state, wave, branch=None):
    """What the person hears beside the fixes, ({answer keys}, the words for the assistant): the project's own checks
    that could not run on the original or rewrite the files instead of checking them (eaos/features/fix/journey/execute.py
    not_run, rewrites, from the run's record of them, never run again), the files a card changed beyond its own
    (beyond), the newer Go a go.mod of the batch's `branch` now needs (go_raised), the packages it moved
    several major versions (big_jumps), and how many cards were left out (put_off)."""
    from .execute import not_run, rewrites
    from ....kernel.project.ledger import go_raised
    from .jumps import big_jumps
    checks = (read_json(Path(project_state.runtime_of(state)) / 'runtime/checks-original.json')
              or {}).get('checks') or []
    unrun, writing = not_run(checks), rewrites(checks)
    wider = wave.get('beyond') or {}
    go = go_raised(state['project'], f"{wave['base']}..{branch}") if branch else []
    jumps = big_jumps(state['project'], wave['base'], branch) if branch else []
    put_off = sum(str(why).startswith('skipped:') for why in (wave.get('failed') or {}).values())
    return {'checks_not_run': unrun, 'checks_rewriting': writing, 'beyond_the_cards': wider, 'go_raised': go,
            'big_jumps': jumps, 'put_off': put_off}, (
        _moved_words(go, jumps) + _put_off_words(put_off) + _checks_words(unrun, writing, wider))


def _checks_words(unrun, writing, wider):
    """What the assistant tells of the checks that held no fix and of the files changed beyond the cards."""
    return ((f" Tell them too that EAOS could not run these checks of theirs here, so no fix was held to them: "
             f"{', '.join(unrun)} "
             "(the program each needs is missing on this computer)." if unrun else '')
            + (f" Tell them these checks of theirs rewrite the files instead of checking them, so no fix was held "
               f"to them: {', '.join(writing)}." if writing else '')
            + (" Name to them each file a card changed beyond its own (beyond_the_cards) and why its fix needed it."
               if wider else ''))


def _put_off_words(count):
    """What the assistant tells of the cards it left out: how many and why, grouped, in the person's language."""
    return (f" Tell them plainly that {count} cards were left out, grouped by why, in their language, and that they "
            "can be picked again in another batch." if count else '')


def _moved_words(go, jumps):
    """What the assistant tells of the Go a go.mod now needs and of the packages moved several major versions."""
    return ((f" Tell them too that {'; '.join(go)}: everyone who builds the project needs that Go or newer."
             if go else '')
            + (f" Tell them these packages moved several major versions to reach their fix, so what uses them is "
               f"worth trying: {'; '.join(jumps)}." if jumps else ''))


def beyond(card, changed):
    """The files a card's change touched outside its own paths (each a file or a folder; '*', or none named: every
    file is its own). Kept only with the assistant's why (agent_tools/edits.py), named with it at the hand-over: the
    one-source gate may rightly make a fix reach the copies of what it changes."""
    paths = [path.rstrip('/') for path in card.get('paths') or []]
    if not paths or '*' in paths: return []
    return [path for path in changed if not any(path == own or path.startswith(own + '/') for own in paths)]


def _record(state, wave, summary):
    """The closed batch's record among the waves, empty until its branch is handed over."""
    return {'number': wave['number'], 'base': wave['base'], 'cards': wave['cards'], 'kept': summary['kept'],
            'failed': summary['failed'],
            'opened': wave.get('opened'), 'phases': (state.get('open_wave') or {}).get('phases') or {},
            'branch': summary['branch'], 'stat': summary['stat'], 'status': 'empty', 'via': 'assistant',
            'keys': wave.get('keys') or {},
            **{k: wave[k] for k in ('deliver_as', 'merge_into', 'base_branch', 'direct', 'continues') if wave.get(k)}}


def _land(project, record, files):
    """A direct batch, its gates passed: its branch merged into the base branch at once (guided.merge: a fast-forward,
    or a merge commit when git merges cleanly) and deleted, so no branch is left. When it cannot land (unsaved changes
    in the checked-out base, or a conflict), the branch stays and waits for the person like any batch."""
    state = project_state.load(project)
    wave = next(w for w in reversed(state['waves'])
                if w['number'] == record['number'] and w.get('branch') == record['branch'])
    outcome = guided.merge(state, wave)
    state = project_state.load(project)
    wave = next(w for w in reversed(state['waves'])
                if w['number'] == record['number'] and w.get('branch') == record['branch'])
    base = wave['merge_into']
    if outcome == 'merged':
        return {'batch': wave['number'], 'branch': None, 'landed_on': base, 'kept': wave['kept'],
                'failed': wave['failed'],
                'changes': wave.get('stat'), 'files': files[-4000:],
                'branch_deleted': not guided._branch_exists(state, wave['branch']),
                'what_now': f"Tell the person, in plain words, what was fixed: it passed every check and is now on "
                            f"{base} itself, "
                            'as they chose; no extra branch was left. The report counts these fixes as done.'}
    wave['direct_failed'] = outcome
    guided.save(state)
    return {'batch': wave['number'], 'branch': wave['branch'], 'landed_on': None, 'kept': wave['kept'],
            'failed': wave['failed'],
            'changes': wave.get('stat'), 'files': files[-4000:], 'not_landed': outcome,
            'what_now': f"The fixes passed every check but could not land on {base} directly ("
                        + ('it has unsaved changes' if outcome == 'unsaved_changes'
                           else 'it changed in the same places') +
                        f"): they wait on the branch {wave['branch']}. "
                        "Tell the person, then accept or undo as they decide."}
