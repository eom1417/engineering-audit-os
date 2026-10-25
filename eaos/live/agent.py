"""The browser agent (M5.2): one layer that drives a running app's browser towards a goal with the person's assistant,
records each step with its picture, and replays the recorded steps with no assistant at all. Screen discovery uses it
after the rules and the links (pipeline/pages.py crawl): the screens behind buttons, tabs and welcomes are reached once
by the assistant, then every later check reaches them again for free. M10's simulated users stand on the same layer.

    Browser(base, out, storage_state)   the browser (eaos/templates/screens/agent.mjs), a step at a time: .do(command)
    explore(browser, goal, provider)    steps chosen by the assistant until it is done or LIMITS end it: the record
    replay(browser, record)             the recorded steps again, no assistant: the screens reached, where it broke

The steps name controls by role and name ({"role": "tab", "name": "Reports", "nth": 0}), never by a reference that
lives one page only, so a replay finds them again; a step that deletes, pays, sends or signs out is refused in the
browser itself. Open-source agents (browser-use, Stagehand) need a model key of their own, which EAOS never holds (it
works through the person's assistant), and the Playwright MCP's steps are not replayable: this layer is EAOS's own
(docs/DECISIONS.md, 2026-10-25).
"""
import json
import select
import subprocess
import tempfile
import time
from pathlib import Path

STEPS, SECONDS = 15, 480            # the most steps and seconds one exploration may take
ANSWER = 90                         # seconds the browser may take to answer one step

SYSTEM = """You drive a web browser, one step at a time, on a web app that runs on this computer in an isolated copy,
towards a goal. Each turn you get the page now (its address, title, text, the controls a person could use, and a
picture you may open with Read) and the steps so far. Answer with one JSON object, the next step:
{"action": "click" | "fill" | "press" | "open" | "back" | "done", "target": {"role", "name", "nth"} (one of the
controls listed, as listed), "value": "text to type (fill), a key (press) or an address of this app (open)",
"why": "one short line"}.
Never delete, pay, send, publish or sign out; a form you fill is the check's own copy, so type plain sample values.
Answer "done" once the goal is reached or nothing more can be reached."""
SCREENS = ('Reach every screen of this app a person can reach from here: open each menu, tab, button and welcome '
           'step that leads somewhere new, and come back. Screens already seen: {seen}. A screen is new when its '
           'address or its content is new.')


class Browser:
    """The browser agent's browser, open until closed (a context manager)."""

    def __init__(self, base, out, storage_state=None):
        from ..core.toolchain import browsers, home
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=True)
        for old in self.out.glob('step-*.jpg'): old.unlink()        # one exploration's pictures, never piled up
        self._config = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
        json.dump({'modules': {'playwright': str(home() / 'node/node_modules')}, 'base': base, 'out': str(self.out),
                   'storage_state': str(storage_state) if storage_state else None}, self._config)
        self._config.close()
        script = Path(__file__).resolve().parents[1] / 'templates/screens/agent.mjs'
        import os
        self.process = subprocess.Popen(['node', str(script), self._config.name], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, start_new_session=True,
                                        env={**os.environ, 'PLAYWRIGHT_BROWSERS_PATH': str(browsers())})

    def do(self, command):
        """The page after one step ({ok, error?, path, title, text, controls, picture}); {ok: False} when it gave no answer."""
        try:
            self.process.stdin.write(json.dumps(command) + '\n')
            self.process.stdin.flush()
        except OSError:
            return {'ok': False, 'error': 'the browser has ended'}
        ready, _, _ = select.select([self.process.stdout], [], [], ANSWER)
        line = self.process.stdout.readline() if ready else ''
        try: return json.loads(line)
        except ValueError: return {'ok': False, 'error': 'the browser gave no answer'}

    def __enter__(self): return self

    def __exit__(self, *_):
        try:
            self.process.stdin.write('{"op": "close"}\n')
            self.process.stdin.close()
            self.process.wait(20)
        except (OSError, subprocess.TimeoutExpired):
            self.process.kill()
        self.process.stdout.close()
        Path(self._config.name).unlink(missing_ok=True)


def _command(step):
    """The browser command of a recorded or proposed step."""
    action = step.get('action')
    if action == 'open': return {'op': 'open', 'path': step.get('value') or '/'}
    if action == 'press': return {'op': 'press', 'key': step.get('value') or 'Enter'}
    return {'op': action, 'target': step.get('target') or {}, 'value': step.get('value')}


def _brief(page, steps, goal):
    """What the assistant reads before choosing the next step."""
    return json.dumps({'goal': goal, 'steps_so_far': [{k: s.get(k) for k in ('action', 'target', 'value', 'landed', 'error')} for s in steps[-10:]],
                       'page_now': {k: page.get(k) for k in ('path', 'title', 'text', 'controls', 'error')},
                       'picture': page.get('picture')}, ensure_ascii=False)


def explore(browser, goal, provider, start='/'):
    """{goal, steps: [{action, target, value, why, at, landed, picture, error?}], screens}: the steps the assistant chose
    towards `goal` from `start`, until it said done, a step failed three times running, or STEPS or SECONDS ended it."""
    page, steps, failed, began = browser.do({'op': 'open', 'path': start}), [], 0, time.monotonic()
    screens = [page.get('path')] if page.get('ok') else []
    while len(steps) < STEPS and time.monotonic() - began < SECONDS and failed < 3:
        try: step = _next(browser, provider, page, steps, goal.format(seen=screens))
        except Exception as problem: return _record(goal, start, steps, screens, f'the assistant could not go on: {problem}'[:300])
        if step.get('action') not in ('click', 'fill', 'press', 'open', 'back'): break
        before, page = page.get('path'), browser.do(_command(step))
        steps.append({**{k: step.get(k) for k in ('action', 'target', 'value', 'why')}, 'at': before, 'landed': page.get('path'),
                      'picture': Path(page.get('picture') or '').name, **({'error': page['error']} if page.get('error') else {})})
        failed = failed + 1 if page.get('error') else 0
        if page.get('path') and page['path'] not in screens: screens.append(page['path'])
    return _record(goal, start, steps, screens)


def _next(browser, provider, page, steps, goal):
    """The step the assistant chooses on `page` (its smallest model: a step is plain work)."""
    messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': _brief(page, steps, goal)}]
    return provider.complete(messages, small=True, stage='explore', reads=str(browser.out))[0].get('result') or {}


def _record(goal, start, steps, screens, stopped=''):
    return {'goal': goal, 'start': start, 'steps': steps, 'screens': screens, **({'stopped': stopped} if stopped else {})}


def replay(browser, record):
    """{screens, broken_at?}: the recorded steps that worked, done again with no assistant from where they began; a step
    whose control is gone stops the replay (broken_at: its number), the screens reached before it kept."""
    page = browser.do({'op': 'open', 'path': record.get('start') or '/'})
    screens = [page.get('path')] if page.get('ok') else []
    for number, step in enumerate((s for s in record.get('steps') or [] if not s.get('error')), 1):
        page = browser.do(_command(step))
        if not page.get('ok'): return {'screens': screens, 'broken_at': number, 'error': page.get('error')}
        if page.get('path') and page['path'] not in screens: screens.append(page['path'])
    return {'screens': screens}
