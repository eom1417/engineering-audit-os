"""The batches at each save of the state: the open one drawn on the live map as the flow `fix` (FLOW), the copies
and older patches of the closed ones removed, and a batch's patches copied to the outputs."""
import shutil
from pathlib import Path

from ....core import progress
from ....core.progress.flow import OPTIONAL, Stage

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


def saved(state, runtime, before):
    """What a save removes for the batches (guided.save), once the state is written: only what this save closes,
    told by `before`, what it found on disk. A read saves too, and what an older EAOS or a failed removal left may
    be the only trace of a change: it stays. A closed batch's or build's commits are in the person's project by then
    (its branch), its patches beside the run (_write_wave), and nothing opens its copy again. Its bisection's logs
    go too: the batch's own gates log stays, the summary of what failed. And the patches this closing puts past the
    ones kept."""
    closing = _closing(state, before)
    for closed in closing:
        shutil.rmtree(Path(runtime) / 'candidates' / _copy_name(closed), ignore_errors=True)
        # a build's number may be a fix batch's too, and it has no bisection
        if closed.get('via') == 'build': continue
        _bisection_logs_removed(runtime, closed['number'])
    if closing:
        for number in set(older(state)) - set(older(before)): shutil.rmtree(Path(runtime) / 'waves' / f'wave-{number}', ignore_errors=True)


def _bisection_logs_removed(runtime, number):
    for log in (Path(runtime) / 'runtime').glob(f'checks-wave-{number}-bisect-*-log.json'):
        try: log.unlink()
        except OSError: pass      # as the copy's removal: the closing is written, and this does not undo it


def _closing(state, before):
    """The records this save adds for a batch `before` held open. A state that does not read, is another branch's,
    or holds no such batch closes nothing, whatever an older state in memory says."""
    if not isinstance(before, dict) or before.get('branch') not in (None, state.get('branch')): return []
    opened, known = _held_open(before), {_copy_name(wave) for wave in before.get('waves') or []}
    return [wave for wave in state.get('waves') or [] if _copy_name(wave) in opened - known]


def _held_open(state):
    wave, build = state.get('open_wave'), state.get('open_build')
    return {*([f"WAVE-{wave['number']}"] if wave else []), *([f"BUILD-{build['number']}"] if build else [])}


def _copy_name(closed):
    return f"{'BUILD' if closed.get('via') == 'build' else 'WAVE'}-{closed['number']}"


KEPT_BATCHES = 2     # the batches whose patches stay beside the run and in the outputs; the older ones are in git


def older(state):
    """The numbers of the closed batches past the last KEPT_BATCHES: their patches go (each is kept twice, beside
    the run and in the outputs); their branches and the state's record of them stay. A batch of moves or context has
    none here, so it takes no batch's place."""
    numbers = sorted({wave['number'] for wave in state.get('waves') or [] if not wave.get('kind')})
    return numbers[:-KEPT_BATCHES]


def publish(state, runtime, fixes, number):
    """<fixes>/wave-N: a copy of the batch's patches and wave.json beside the run, the older batches' copies removed."""
    source, target = Path(runtime) / 'waves' / f'wave-{number}', Path(fixes) / f'wave-{number}'
    shutil.rmtree(target, ignore_errors=True)
    if source.is_dir(): shutil.copytree(source, target)
    else: target.mkdir(parents=True)
    for old in older(state): shutil.rmtree(Path(fixes) / f'wave-{old}', ignore_errors=True)
    return target


def draw(state, runtime):
    """The open batch as the flow `fix` (waves.FLOW), drawn again from the state at each of its saves, and once more
    when it closes. No process holds a batch, the assistant's tool calls work it card by card, so nothing else draws
    it: without this the live map would read "waiting" through every batch. Called by guided.save; None when there
    is nothing to draw."""
    wave = _to_draw(state)
    if not wave: return None
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


def _to_draw(state):
    """The batch to draw: the open one, else the last closed one once (kept in `fix_drawn`); None when there is none."""
    wave, last = state.get('open_wave'), (state.get('waves') or [None])[-1]
    if wave: return wave
    if not (last or {}).get('cards') or state.get('fix_drawn') == last['number']: return None   # a build's: draw_build
    state['fix_drawn'] = last['number']
    return last


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
