"""Time left, from real history only: a range, never a bare percentage, and nothing on a first run.

`estimate(state, now)` reads a folded state (fold.py). Its `previous` holds each stage's seconds in the last run of
the same flow and `previous_steps` each step's; nothing else is used:

- the stages still waiting cost what they cost last time, scaled by how this run compares with the last one so far
  (the stages both runs finished: this run's seconds over last run's, held between 0.25 and 4);
- a running stage with a counted step (`progress.count`, 37 of 156) costs the time its done items took, spread over
  the items left: the stage's own pace, measured now;
- any other running stage costs what is left of its scaled last time (none when it already ran longer);
- a stage the last run did not finish is unknown and named, never guessed.

The answer is {'low', 'high'} in whole seconds (15% either side of the centre, at least 10 s), `basis`
('previous_run'), `pace` (the scale) and `unknown` (stages with no history). A first run, or a run that is not
running, gives {'basis': 'first_run'} or None: the page then shows the elapsed time only and says why.
"""
from datetime import datetime

BAND = 0.15
MIN_BAND = 10.0
PACE_LIMITS = (0.25, 4.0)
# Below this many seconds of stages finished in both runs, the comparison is noise: the pace stays 1.
PACE_AFTER = 5.0


def _at(text):
    try: return datetime.fromisoformat(str(text).replace('Z', '+00:00')).timestamp()
    except (TypeError, ValueError): return None


def pace(state):
    """This run's seconds over the last run's, for the stages both finished ok (1.0 until there is enough of them)."""
    previous = state.get('previous') or {}
    now_seconds = then_seconds = 0.0
    for stage in state.get('stages') or []:
        before = previous.get(stage['name'])
        if stage.get('state') == 'ok' and isinstance(before, (int, float)) and isinstance(stage.get('seconds'), (int, float)):
            now_seconds += stage['seconds']
            then_seconds += before
    if then_seconds < PACE_AFTER: return 1.0
    low, high = PACE_LIMITS
    return min(max(now_seconds / then_seconds, low), high)


def _counted(stage, elapsed):
    """Seconds left of a running stage from its own counted step, or None when it has none worth reading."""
    for step in reversed(stage.get('steps') or []):
        if step.get('kind') == 'count' and step.get('status') == 'running' and step.get('total') and step.get('done'):
            return elapsed * (step['total'] - step['done']) / step['done']
    return None


def _left(stage, before, scale, now):
    """Seconds a waiting or running stage still costs, or None when the last run gives nothing to go by."""
    known = isinstance(before, (int, float))
    if stage.get('state') == 'waiting': return before * scale if known else None
    began = _at(stage.get('started_at'))
    elapsed = max(now - began, 0.0) if began is not None else 0.0
    counted = _counted(stage, elapsed)
    if counted is not None: return counted
    return max(before * scale - elapsed, 0.0) if known else None


def estimate(state, now):
    """{'low', 'high', 'basis', 'pace', 'unknown'} for a running flow (`now`: seconds since the epoch), or
    {'basis': 'first_run'} when there is no last run to learn from, or None when nothing is running."""
    if (state or {}).get('state') != 'running': return None
    previous = state.get('previous') or {}
    if not previous: return {'basis': 'first_run'}
    scale = pace(state)
    left, unknown = 0.0, []
    for stage in state.get('stages') or []:
        if stage.get('state') != 'running' and not (stage.get('state') == 'waiting' and stage.get('requested', True)): continue
        cost = _left(stage, previous.get(stage['name']), scale, now)
        if cost is None: unknown.append(stage['name'])
        else: left += cost
    band = max(left * BAND, MIN_BAND)
    return {'low': int(max(left - band, 0)), 'high': int(left + band + 0.5), 'basis': 'previous_run',
            'pace': round(scale, 2), 'unknown': unknown}
