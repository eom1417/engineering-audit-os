"""The simulation from start to end (M10), the one sequence every door calls: the plan (the scenario and its data),
the run on the app's isolated copy (the history seeded, the personas with their hand-offs, the support desk), and the
replays of the saved journeys. The judging of what the personas met is judging.py's; the report is report/experience.

    prepare(report, provider)                      experience/scenario.json and data.json
    simulate(report, project, app, provider)       experience/run.json, journeys/, tickets.json (and the history seeded)
    judged(report, app, provider)                  experience/difficulties.json, the `experience` facts
    replays(report, app)                           experience/replays.json

`app`: {'base': the copy's address, 'sessions': {kind of user: its browser state or None}, 'runtime': the run's folder
or None (its database is seeded only then), 'database': the copy's SQLite file, if any}.
"""
import json
from contextlib import contextmanager
from pathlib import Path

from ...live.agent import Browser
from ...live.experience import actor, cast, replay, second, seed, support
from . import domain_data, judging, scenario as scenarios


def _read(report, name):
    try: return json.loads((Path(report) / 'experience' / name).read_text(encoding='utf-8'))
    except (OSError, ValueError): return None


def prepare(report, provider=None):
    """The scenario, then the data that fits it (each by rules when there is no assistant)."""
    planned = scenarios.plan(report, provider)
    return planned, domain_data.plan(report, provider, planned)


def _retry_browser(app, report):
    """The support desk's fresh browser for one more try: its own folder, so the first try's pictures stay."""
    @contextmanager
    def opened(persona, goal):
        folder = Path(report) / 'experience' / 'journeys' / actor.file_name(goal['name']).replace('.json', '--again')
        with Browser(app['base'], folder, app['sessions'].get(persona.get('role'))) as browser: yield browser
    return opened


def simulate(report, project, app, provider):
    """The run: the history seeded into the copy's own database, then every goal in order with the support desk."""
    planned, data = _read(report, 'scenario.json'), _read(report, 'data.json')
    if not planned: planned, data = prepare(report, provider)
    seeded = seed.seed(data or {}, {k: app.get(k) for k in ('runtime', 'database', 'apart')})
    desk = support.Desk(provider, project, _retry_browser(app, report), cast.typed_values(data))
    ran = cast.run(app, planned, {'order': scenarios.order(planned), 'data': data, 'on_stuck': desk}, provider, report)
    desk.save(report)
    return {**ran, 'seeded': seeded}


def replays(report, app):
    """Every saved journey replayed with no assistant."""
    return replay.replay_all(app['base'], app['sessions'], report)


def judged(report, app, provider):
    """Each difficulty met again (or not) by a fresh persona on a fresh browser, then ruled on: experience/difficulties.json
    and the confirmed ones as the `experience` facts the plan makes cards of."""
    goals = cast.goals_by_name(_read(report, 'scenario.json') or {})

    def attempt(name):
        persona, goal = goals[name]
        folder = Path(report) / 'experience' / 'journeys' / actor.file_name(name).replace('.json', '--second')
        with Browser(app['base'], folder, app['sessions'].get(persona.get('role'))) as browser:
            return second.second_attempt(browser, persona, goal, provider)
    judging.confirm(report, attempt)
    return judging.judge(report, provider)
