"""The second attempt of a goal (M10.7): a fresh actor runs the same goal again on a fresh browser, told nothing of the
first attempt, so a difficulty it meets again is not the first actor's own slip.

    second_attempt(browser, persona, goal, provider, difficulty=None)   {reached, same, journey}
    met(journey, difficulty)                                             whether a journey met that difficulty again
    screen(journey, kind, number)                                        the screen a difficulty happened on

A difficulty is {kind: find|understand|finish|error|stuck, screen}: met again when the persona gives up again (kind
'stuck': a journey a budget or the assistant ended did not meet it, it only did not finish), or a friction note of the same kind is left on the same screen. The difficulty is only compared after the
journey ends; the actor never sees it.
"""
from .actor import act

GOAL = ('name', 'goal', 'start', 'done_when', 'events')     # all the fresh actor is told: never the first attempt


def screen(journey, kind, number=None):
    """The screen of step `number` (an error is where it landed, any other friction where it began); of a stuck goal,
    where the journey ended."""
    steps = journey.get('steps') or []
    if kind == 'stuck' or not number or number > len(steps):
        return (steps[-1].get('landed') or steps[-1].get('at')) if steps else journey.get('start')
    step = steps[number - 1]
    return step.get('landed') if kind == 'error' else step.get('at')


def met(journey, difficulty):
    """True when `journey` met `difficulty` again: stuck again, or the same kind of friction on the same screen."""
    if not journey: return False
    if difficulty['kind'] == 'stuck': return bool(journey.get('stuck')) and not journey.get('stopped') and not journey.get('reached')
    return any(f.get('kind') == difficulty['kind'] and screen(journey, f['kind'], f.get('step')) == difficulty.get('screen')
               for f in journey.get('friction') or [])


def second_attempt(browser, persona, goal, provider, difficulty=None):
    """The goal run again by a fresh actor on `browser` (a new one, given by the caller): {reached, same, journey};
    `same` compares the journey with `difficulty` when one is given. `goal['values']` are the goal's typed values
    (data.json's through_ui), the same the first attempt typed."""
    journey = act(browser, persona, {k: goal[k] for k in GOAL if goal.get(k)}, provider, goal.get('values'))
    return {'reached': bool(journey.get('reached')), 'same': bool(difficulty) and met(journey, difficulty), 'journey': journey}
