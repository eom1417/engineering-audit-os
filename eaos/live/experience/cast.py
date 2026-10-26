"""Several simulated users and their hand-offs (M10.5): every goal of the scenario in its order, one actor and one
browser each; a goal waits for the goals it needs (an approval, a reply) and is told the events they made, or is
blocked when one of them was not reached.

    run(app, scenario, plan, provider, report)   <report>/experience/run.json: each goal's ending, the events board

`plan['order']` is the goals' names in dependency order (the scenario's `order`, given by the caller: live/ never reads
analysis/); `plan['data']` is data.json, whose `through_ui` values the persona types; `plan['on_stuck']`, when given,
is asked about a journey that did not reach its goal and may answer the journey that replaces it (support, M10.6).
"""
import json
import time
from pathlib import Path

from ..agent import Browser
from . import actor

VERSION = 1
BUDGET = {'seconds': 3600, 'calls': 300}      # the whole run; past either, no new goal starts
RUN = 'run.json'


def _goals(scenario):
    """Each goal by its name '<persona>.<goal>': (its persona, the goal with its name)."""
    return {f"{p['id']}.{g['id']}": (p, {**g, 'name': f"{p['id']}.{g['id']}"})
            for p in scenario.get('personas') or [] for g in p.get('goals') or []}


def _values(data):
    """The values typed through the screens, by goal (data.json's through_ui)."""
    return {row['goal']: row.get('values') or {} for row in (data or {}).get('through_ui') or [] if row.get('goal')}


def _status(journey):
    if journey.get('reached'): return 'reached'
    return 'stopped' if journey.get('stopped') else 'stuck'


class _Board:
    """The run while it goes: each goal's ending, the events made, the time and calls spent."""

    def __init__(self, folder):
        self.folder, self.began, self.calls, self.goals, self.events = Path(folder), time.monotonic(), 0, [], []

    def _seconds(self): return round(time.monotonic() - self.began, 1)

    def waiting(self, goal):
        """Why `goal` cannot start (the run's budget, or the goals it waits for that were not reached), or None."""
        if self._seconds() >= BUDGET['seconds'] or self.calls >= BUDGET['calls']: return "the run's budget ran out", []
        reached = {g['name'] for g in self.goals if g['status'] == 'reached'}
        missing = [name for name in goal.get('waits_for') or [] if name not in reached]
        return (f"it waits for {', '.join(missing)}, which was not reached", missing) if missing else (None, [])

    def told(self, goal):
        """The events made by the goals `goal` waited for."""
        return [event for event in self.events if event['by'] in (goal.get('waits_for') or [])]

    def block(self, persona, goal, why, missing):
        self.goals.append({'name': goal['name'], 'persona': persona['id'], 'role': persona.get('role'), 'status': 'blocked',
                           'why': why, **({'waited_for': missing} if missing else {}), 'seconds': 0, 'calls': 0, 'friction': 0})

    def keep(self, persona, goal, journey, calls):
        """The goal's ending, and its event on the board when it was reached."""
        status = _status(journey)
        self.calls += calls
        self.goals.append({'name': goal['name'], 'persona': persona['id'], 'role': persona.get('role'), 'status': status,
                           **({'why': journey.get('stuck')} if status != 'reached' else {}), 'seconds': journey.get('seconds', 0),
                           'calls': calls, 'friction': len(journey.get('friction') or [])})
        if status == 'reached' and goal.get('makes'):
            self.events.append({'event': goal['makes'], 'by': goal['name'], 'at': self._seconds()})

    def write(self):
        record = {'version': VERSION, 'goals': self.goals, 'events': self.events, 'seconds': self._seconds(), 'calls': self.calls}
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / RUN).write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        return record


def _journey(app, persona, goal, provider, values):
    """The actor's journey towards `goal` in a browser of its own, signed in as the persona's role."""
    folder = Path(app['report']) / 'experience' / actor.JOURNEYS
    storage = (app.get('sessions') or {}).get(persona.get('role'))
    with Browser(app['base'], folder / Path(actor.file_name(goal['name'])).stem, storage) as browser:
        return actor.act(browser, persona, goal, provider, values)


def _helped(plan, persona, goal, journey):
    """The journey kept, and the calls spent: a journey that did not reach its goal is replaced by the one
    plan['on_stuck'] answers, when it answers one."""
    calls = journey.get('calls', 0)
    again = plan['on_stuck'](journey, persona, goal) if plan.get('on_stuck') and not journey.get('reached') else None
    return (again, calls + again.get('calls', 0)) if again else (journey, calls)


def run(app, scenario, plan, provider, report):
    """<report>/experience/run.json ({version, goals: [{name, persona, role, status: reached | stuck | stopped |
    blocked, why?, waited_for?, seconds, calls, friction}], events: [{event, by, at}], seconds, calls}), each journey
    saved in experience/journeys. `app` = {base: the running copy's address, sessions: {role: storage state or None}}."""
    goals, values, board = _goals(scenario), _values(plan.get('data')), _Board(Path(report) / 'experience')
    app = {**app, 'report': report}
    for name in (n for n in plan.get('order') or [] if n in goals):
        persona, goal = goals[name]
        why, missing = board.waiting(goal)
        if why:
            board.block(persona, goal, why, missing)
            continue
        goal = {**goal, 'events': board.told(goal)}
        journey, calls = _helped(plan, persona, goal, _journey(app, persona, goal, provider, values.get(name)))
        actor.save(board.folder / actor.JOURNEYS, journey)
        board.keep(persona, goal, journey, calls)
    return board.write()
