"""The sign-in page's back end: the pinned Chromium the person signs in to their app with, while a check asks for it
(eaos/live/sign_in.py). The Studio's page (console/src/places/waiting/signin.js, reached from Waiting for you) shows it and
passes on their clicks and typing; `eaos sign-in` opens it in a window when this computer has a display, else serves the
same page on a port of its own, until the session is saved (eaos/interfaces/api/server.py serve_sign_in).

    GET  /api/sign-in           {asked, open, kept, codes}: what the check asks (null: nothing), whether the browser is
                                open, whether a session made by hand is kept, what the app sent (its output, its mail)
    POST /api/sign-in/open      the browser opened on the app                                      -> {url, title, picture}
    POST /api/sign-in/input     {do: look|click|type|key|scroll|back, x, y, text, key, dy}         -> {url, title, picture}
    POST /api/sign-in/done      the session saved (its owner only), the browser closed, the check goes on signed in
    POST /api/sign-in/skip      the check goes on signed out
    POST /api/sign-in/forget    the project's sessions removed

Every route is under the Studio's guard (eaos/interfaces/api/guard.py): the launch token, and CSRF and the Origin on a write.
Nothing typed is kept or logged; the session file never reaches the report, a branch or the assistant.
"""
import json
import os
import select
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from ...journeys import guided
from ...live import sign_in
from ...core import toolchain

SCRIPT = Path(__file__).resolve().parents[2] / 'templates/screens/sign-in.mjs'
_OPEN = {}                  # workspace -> the Browser open in this process


class Browser:
    """The pinned Chromium on `base`, saving to `state` when the person is done; headed: a window they drive."""

    def __init__(self, base, state, headed=False):
        self.folder = tempfile.TemporaryDirectory(prefix='eaos-sign-in-')
        config = Path(self.folder.name) / 'config.json'
        config.write_text(json.dumps({'base': base, 'state': str(state), 'headed': headed,
                                      'modules': {'playwright': str(toolchain.home() / 'node/node_modules')}}), encoding='utf-8')
        self.process = subprocess.Popen(['node', str(SCRIPT), str(config)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, start_new_session=True,
                                        env={**os.environ, 'PLAYWRIGHT_BROWSERS_PATH': str(toolchain.browsers())})
        self.lock = threading.Lock()

    def send(self, command, timeout=90):
        """One command to the browser, and its answer."""
        with self.lock:
            if self.process.poll() is not None: raise LookupError('the sign-in browser has closed: open it again')
            self.process.stdin.write(json.dumps(command) + '\n')
            self.process.stdin.flush()
            if not select.select([self.process.stdout], [], [], timeout)[0]: raise TimeoutError('the sign-in browser did not answer')
            return json.loads(self.process.stdout.readline() or '{}')

    def done(self):
        """The session saved and the browser ended: True when it was saved."""
        saved = self.send({'do': 'done'}).get('saved')
        self.end()
        return bool(saved)

    def end(self):
        if self.process.poll() is None:
            try: self.process.communicate(json.dumps({'do': 'close'}) + '\n', timeout=10)
            except (subprocess.TimeoutExpired, OSError, ValueError): self.process.kill()
        self.process.wait()
        self.folder.cleanup()


def _state(project):
    return guided.load(project)


def _asked(workspace):
    record = sign_in.asked(workspace)
    if record is None: raise LookupError('the check does not wait for a sign-in now')
    return record


def status(project):
    state = _state(project)
    record = sign_in.asked(state['workspace'])
    return {'asked': {k: record[k] for k in ('asked', 'until', 'base', 'why', 'published')} if record else None,
            'open': state['workspace'] in _OPEN, 'kept': sign_in.by_hand(sign_in.session(guided.runtime_of(state))),
            'codes': sign_in.codes(record) if record else None}


def open_browser(project, headed=False):
    """The browser on the address the check asks for (an open one is shown as it is)."""
    workspace = _state(project)['workspace']
    record = _asked(workspace)
    if workspace not in _OPEN: _OPEN[workspace] = Browser(record['base'], record['session'], headed)
    return _OPEN[workspace].send({'do': 'look'})


def drive(project, command):
    if command.get('do') not in ('look', 'click', 'type', 'key', 'scroll', 'back'): raise ValueError('do is one of look, click, type, key, scroll, back')
    browser = _OPEN.get(_state(project)['workspace'])
    if browser is None: raise LookupError('the sign-in browser is not open: open it first')
    return browser.send(command)


def done(project):
    """The person is in: the session saved by hand (kept as their way to sign in), and the check goes on."""
    state = _state(project)
    browser = _OPEN.pop(state['workspace'], None)
    if browser is None or not browser.done(): raise LookupError('the sign-in browser is not open: open it, sign in, then press done')
    sign_in.answer(state['workspace'], sign_in.SIGNED_IN)
    from ...journeys.check_choices import keep
    if keep(state, sign_in='hand'): guided.save(state)
    return status(state['project'])


def close(project):
    """The sign-in browser of `project` ended, when one is open: nothing is saved."""
    browser = _OPEN.pop(_state(project)['workspace'], None)
    if browser: browser.end()


def waits(project):
    """Whether a check still waits for the person to sign in."""
    return sign_in.asked(_state(project)['workspace']) is not None


def skip(project):
    close(project)
    sign_in.answer(_state(project)['workspace'], sign_in.SIGNED_OUT)
    return status(project)


def forget(project):
    state = _state(project)
    return {'forgotten': len(sign_in.forget(state['workspace'])), **status(state['project'])}


def routes(ctx):
    """The routes above, for the server of `ctx` (none without a project)."""
    if ctx.project is None: return []
    project = str(ctx.project)
    return [('GET', '/api/sign-in', lambda request: _answer(status, project)),
            ('POST', '/api/sign-in/open', lambda request: _answer(open_browser, project)),
            ('POST', '/api/sign-in/input', lambda request: _answer(drive, project, request['body'] or {})),
            ('POST', '/api/sign-in/done', lambda request: _answer(done, project)),
            ('POST', '/api/sign-in/skip', lambda request: _answer(skip, project)),
            ('POST', '/api/sign-in/forget', lambda request: _answer(forget, project))]


def _answer(function, *args):
    try: return function(*args)
    except LookupError as problem: return 409, {'error': 'sign_in', 'message': str(problem)}
    except (ValueError, TimeoutError) as problem: return 400, {'error': 'sign_in', 'message': str(problem)}


# ---------------------------------------------------------------- `eaos sign-in`

def display():
    """Whether this computer shows windows (a Mac, or a desktop session): the browser then opens in one."""
    return sys.platform == 'darwin' or bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'))
