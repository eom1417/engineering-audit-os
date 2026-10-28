"""The check as loops, declared as data (docs/ARCHITECTURE.md §3).

Each stage of eaos/pipeline/stages.py belongs to one loop, and the loops' order is the stages' declared order: moving a
stage, or a loop, is a change of this table, never of code. One runner runs them all (eaos/pipeline/schedule.py, as
soon as what a stage waits for has ended, loops side by side where nothing holds them apart); when the last stage of a
loop ends, its exit is judged (`outcome`):

    met        every stage of the loop ended ok, or is absent with its reason
    explained  a stage its goal stands on (`needs`) is absent with its reason: a gap the coverage ledger states
    not_met    a stage of it broke (failed, or not reached behind one that did)

A loop not met runs its broken stages again while its rounds last (`max_rounds`); after them it acts as `on_fail`
says: 'explain' (the gap in the coverage ledger), 'escalate' (the gap needs the person: red at the top of the report),
'stop' (nothing after it starts). While it may run again, what it broke is hidden from the stages of other loops, so
none of them is built on a round that is redone; what it made ok they read at once.

A loop with a `switch` is optional: it runs only when the check follows the path of that name, alone or beside
`complete` (an option of the full check). The fix batches (L6) are not a loop of the check: they are the fix journey's
(eaos/journeys/), run after it, card by card.
"""
from dataclasses import dataclass

ON_FAIL = ('explain', 'escalate', 'stop')
MET, EXPLAINED, NOT_MET = 'met', 'explained', 'not_met'
BROKEN = ('failed', 'not_reached')


@dataclass(frozen=True)
class Loop:
    name: str
    stages: tuple
    needs: tuple = ()
    max_rounds: int = 1
    on_fail: str = 'explain'
    switch: str = ''


LOOPS = (
    Loop('understand', ('facts', 'features', 'roles', 'intake', 'engines', 'policy'), needs=('facts',), on_fail='stop'),
    # the app's stages break on a loaded computer (a browser that timed out, an app slow to answer): one more round
    Loop('run_and_see', ('setup', 'verify', 'session', 'crawl', 'lock', 'record', 'journeys', 'screens', 'baseline', 'layers', 'keeping'),
         needs=('setup', 'screens'), max_rounds=2),
    # the layers tried on the running app: an option of the check (the `layers` path), its time said before it starts
    Loop('try_layers', ('layers_trial',), needs=('layers_trial',), switch='layers'),
    # simulated users on the running app: alone the whole simulation (the `experience` path), beside `complete` its short
    # option (one persona, the main task), its time and cost said before it starts
    Loop('try_experience', ('experience',), needs=('experience',), switch='experience'),
    Loop('judge', ('measure', 'architecture', 'load', 'readiness', 'claims', 'probe', 'sustainability', 'transform',
                   'semantic', 'plan', 'target', 'proposals', 'triage', 'visual', 'cards'), needs=('claims', 'triage')),
    Loop('envision', ('ideal', 'pipeline_gaps', 'reconcile'), needs=('ideal', 'reconcile')),
    Loop('plan', ('order', 'steps'), needs=('steps',)),
    Loop('hand_over', ('reports', 'translate'), needs=('reports',), on_fail='escalate'),
)
BY_NAME = {loop.name: loop for loop in LOOPS}
LOOP_OF = {stage: loop.name for loop in LOOPS for stage in loop.stages}


def outcome(loop, rows):
    """(state, the stages behind it) of a loop whose stages all ended, from their rows: met, explained (the needs absent
    with their reason) or not_met (the stages that failed, else those not reached)."""
    status = {name: (rows.get(name) or {}).get('status') for name in loop.stages}
    broken = [name for name in loop.stages if status[name] in BROKEN]
    if broken: return NOT_MET, _failed_first(broken, status)
    absent = [name for name in loop.needs if status.get(name) != 'ok']
    return (EXPLAINED, absent) if absent else (MET, [])


def _failed_first(broken, status):
    """Behind a loop not met, the stages that failed themselves; those only not reached behind them follow from them."""
    return [name for name in broken if status[name] == 'failed'] or broken


def switches():
    """The check paths that switch an optional loop on."""
    return {loop.switch for loop in LOOPS if loop.switch}


def switched_off(paths):
    """The stages of the optional loops a check following `paths` does not switch on."""
    return {name for loop in LOOPS if loop.switch and loop.switch not in (paths or ()) for name in loop.stages}


def errors(declared):
    """What is wrong with the loops' declaration over the `declared` stage names: a stage in no loop or in two, a loop's
    stage not declared, a need outside its loop, an unknown action."""
    found, seen = [f'{name}: in no loop' for name in sorted(set(declared) - _in_loops())], set()
    for loop in LOOPS:
        found += _loop_errors(loop, declared, seen)
        seen.update(loop.stages)
    return found


def _in_loops():
    return {name for loop in LOOPS for name in loop.stages}


def _loop_errors(loop, declared, seen):
    found = [f'{loop.name}: {name} is not a declared stage' for name in loop.stages if name not in declared]
    found += [f'{loop.name}: {name} is already in another loop' for name in loop.stages if name in seen]
    found += [f'{loop.name}: needs {name}, which is not one of its stages' for name in loop.needs if name not in loop.stages]
    if loop.on_fail not in ON_FAIL: found.append(f'{loop.name}: unknown on_fail {loop.on_fail!r}')
    if loop.max_rounds < 1: found.append(f'{loop.name}: max_rounds below 1')
    return found
