"""One simulated user (M10.3): a persona drives the running copy's browser towards one goal of the scenario, on the
browser agent's layer (eaos/live/agent.py), within its step, time and call budgets; each step recorded with its
picture and what the persona found hard (the friction log).

    act(browser, persona, goal, provider, values=None)   the journey: {goal, steps, reached, stuck, friction, ...}
    save(folder, journey, attempt=None) / load(path)     the journey as experience/journeys/<persona>--<goal>[--<attempt>].json
    picture(journey, stem, name)                         a step's picture, relative to the report

A journey keeps `pictures_dir`, the folder of experience/journeys its pictures are in (its browser's own): the support
desk's retry and the judge's second attempt take theirs in <stem>--again/ and <stem>--second/, never the first's.

The assistant is passed in and asked on its light tier: a step is plain work. It answers "done" when the goal's own
sign is on the screen, "stuck" when the persona would give up; a step it found hard carries a friction note.
"""
import json
import time
from pathlib import Path

from ..agent import reach, seen, step_command, taken

VERSION = 1
BUDGET = {'steps': 25, 'seconds': 600, 'calls': 30, 'failures': 3}
ACTIONS = ('click', 'fill', 'press', 'open', 'back')
FRICTION = ('find', 'understand', 'finish', 'error')
JOURNEYS = 'journeys'

SYSTEM = """You are {name}, a person using a web app for the first time: {about}. You use it through a browser, one
step at a time, towards your goal. The app runs on this computer in an isolated copy with sample data. Each turn you get
the page now (its address, title, text, the controls a person could use, and a picture you may open with Read) and your
steps so far. Answer with one JSON object, the next step:
{{"action": "click" | "fill" | "press" | "open" | "back" | "done" | "stuck", "target": {{"role", "name", "nth"}} (one of
the controls listed, as listed), "value": "text to type (fill), a key (press) or an address of this app (open)",
"why": "one short line", "friction": null or {{"kind": "find" | "understand" | "finish" | "error", "note": "what was
hard, in one plain line"}}}}.
Act as this person would: use what the screen shows, not addresses you guess. Say "done" only when the sign that the
goal is reached is on the screen; say "stuck" (its "why" says what stopped you) when this person would give up.
Note friction whenever a step was hard to find, hard to understand, did not finish, or showed an error.
Never delete, pay, send to real people, publish or sign out."""


def _brief(page, steps, goal, values):
    """What the persona reads before choosing its next step."""
    return json.dumps({'goal': goal['goal'], 'done_when': goal.get('done_when'), 'values_to_use': values or {},
                       **({'happened_before_you': goal['events']} if goal.get('events') else {}),
                       **({'support_told_you': goal['help']} if goal.get('help') else {}),
                       **seen(page, steps)}, ensure_ascii=False)


def _next(browser, provider, persona, brief):
    """The step the persona chooses (the light tier)."""
    system = SYSTEM.format(name=persona.get('name') or persona['id'], about=persona.get('about') or persona.get('role') or 'a user')
    answer = provider.complete([{'role': 'system', 'content': system}, {'role': 'user', 'content': brief}],
                               small=True, stage='experience_actor', reads=str(browser.out))[0]
    step = answer.get('result') or answer
    return step if isinstance(step, dict) else {'action': 'stuck', 'why': f'no step: {str(step)[:200]}'}


def _friction(step, number, page):
    """The friction this step leaves: the persona's own note, or the error the page showed."""
    said = step.get('friction') if isinstance(step.get('friction'), dict) else None
    if said and said.get('kind') in FRICTION and said.get('note'): return {'step': number, 'kind': said['kind'], 'note': str(said['note'])[:300]}
    if page.get('error'): return {'step': number, 'kind': 'error', 'note': str(page['error'])[:300]}
    return None


class _Journey:
    """One goal's journey while it runs: its steps, friction and budgets."""

    def __init__(self, persona, goal, start):
        self.persona, self.goal, self.began = persona, goal, time.monotonic()
        self.steps, self.friction, self.screens, self.calls, self.failed = [], [], [], 0, 0
        self.record = {'version': VERSION, 'persona': persona['id'], 'role': persona.get('role'), 'goal': goal['name'],
                       'wanted': goal['goal'], 'start': start, 'reached': False, 'stuck': None, 'stopped': None}

    def spent(self):
        """The budget this journey ran out of, or None."""
        if len(self.steps) >= BUDGET['steps']: return 'steps'
        if time.monotonic() - self.began >= BUDGET['seconds']: return 'time'
        if self.calls >= BUDGET['calls']: return 'calls'
        return 'failures' if self.failed >= BUDGET['failures'] else None

    def take(self, step, before, page):
        self.steps.append(taken(step, before, page))
        self.failed = self.failed + 1 if page.get('error') else 0
        noted = _friction(step, len(self.steps), page)
        if noted: self.friction.append(noted)
        reach(self.screens, page)

    def done(self, **ending):
        return {**self.record, **ending, 'steps': self.steps, 'friction': self.friction, 'screens': self.screens,
                'seconds': round(time.monotonic() - self.began, 1), 'calls': self.calls}


def act(browser, persona, goal, provider, values=None):
    """The journey of `persona` towards `goal` ({name: '<persona>.<goal>', goal, start, done_when, events?: the
    hand-offs it waited for, shown to the persona}) on `browser`: the steps until the persona says done or stuck, or a
    budget ends it (`stopped`: steps, time, calls or failures)."""
    journey = _Journey(persona, goal, goal.get('start') or '/')
    if getattr(browser, 'out', None): journey.record['pictures_dir'] = Path(browser.out).name
    page = browser.do({'op': 'open', 'path': journey.record['start']})
    if page.get('ok'): reach(journey.screens, page)
    while not (spent := journey.spent()):
        journey.calls += 1
        try: step = _next(browser, provider, persona, _brief(page, journey.steps, goal, values))
        except Exception as problem: return journey.done(stopped='assistant', stuck=f'the assistant could not go on: {problem}'[:300])
        if step.get('action') == 'done': return journey.done(reached=True)
        if step.get('action') not in ACTIONS:
            return journey.done(stuck=str(step.get('why') or f"no step: {json.dumps(step)[:200]}")[:300])
        before, page = page.get('path'), browser.do(step_command(step))
        journey.take(step, before, page)
    return journey.done(stopped=spent, stuck=f'the {spent} budget ran out before the goal was reached')


def file_name(goal_name):
    """experience/journeys/<persona>--<goal>.json of a goal named '<persona>.<goal>'."""
    return goal_name.replace('.', '--', 1) + '.json'


def save(folder, journey, attempt=None):
    """The journey written in `folder` (experience/journeys); its path. The first try is <stem>.json; another attempt of
    the same goal (`attempt`: 'again' after support, 'second' for the judge) is <stem>--<attempt>.json and says so."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    name = file_name(journey['goal'])
    path = folder / (name.replace('.json', f'--{attempt}.json') if attempt else name)
    journey = {**journey, 'attempt': attempt} if attempt else journey
    path.write_text(json.dumps(journey, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return path


def picture(journey, stem, name):
    """experience/journeys/<the journey's pictures_dir, else its file's stem>/<name>: where a step's picture is."""
    return f"experience/{JOURNEYS}/{journey.get('pictures_dir') or stem}/{name}" if name else None


def load(path):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return None
