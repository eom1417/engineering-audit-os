"""The person's sign-in to their app by hand, while a check asks for it (eaos/live/access/sign_in.py): the pinned
Chromium opened in a window where this computer shows one (`eaos sign-in`), the session saved when they are done.
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

from . import guided
from ..live.access import sign_in
from ..core import toolchain
from ..core.project import state as project_state

SCRIPT = Path(__file__).resolve().parents[1] / 'templates/screens/sign-in.mjs'
_OPEN = {}                  # workspace -> the Browser open in this process


class Browser:
    """The pinned Chromium on `base`, saving to `state` when the person is done; headed: a window they drive."""

    def __init__(self, base, state, headed=False):
        self.folder = tempfile.TemporaryDirectory(prefix='eaos-sign-in-')
        config = Path(self.folder.name) / 'config.json'
        config.write_text(json.dumps({'base': base, 'state': str(state), 'headed': headed,
                                      'modules': {'playwright': str(toolchain.home() / 'node/node_modules')}}),
                          encoding='utf-8')
        self.process = subprocess.Popen(['node', str(SCRIPT), str(config)], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                        start_new_session=True,
                                        env={**os.environ, 'PLAYWRIGHT_BROWSERS_PATH': str(toolchain.browsers())})
        self.lock = threading.Lock()

    def send(self, command, timeout=90):
        """One command to the browser, and its answer."""
        with self.lock:
            if self.process.poll() is not None: raise LookupError('the sign-in browser has closed: open it again')
            self.process.stdin.write(json.dumps(command) + '\n')
            self.process.stdin.flush()
            if not select.select([self.process.stdout], [], [], timeout)[0]:
                raise TimeoutError('the sign-in browser did not answer')
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
    return project_state.load(project)


def _asked(workspace):
    record = sign_in.asked(workspace)
    if record is None: raise LookupError('the check does not wait for a sign-in now')
    return record


def status(project):
    state = _state(project)
    record = sign_in.asked(state['workspace'])
    return {'asked': {k: record[k] for k in ('asked', 'until', 'base', 'why', 'published', 'tried')
                      if k in record} if record else None,
            'open': state['workspace'] in _OPEN,
            'kept': sign_in.by_hand(sign_in.session(project_state.runtime_of(state))),
            'codes': sign_in.codes(record) if record else None}


def open_browser(project, headed=False):
    """The browser on the address the check asks for (an open one is shown as it is)."""
    workspace = _state(project)['workspace']
    record = _asked(workspace)
    if workspace not in _OPEN: _OPEN[workspace] = Browser(record['base'], record['session'], headed)
    return _OPEN[workspace].send({'do': 'look'})


def done(project):
    """The person is in: the session saved by hand (kept as their way to sign in), and the check goes on."""
    state = _state(project)
    browser = _OPEN.pop(state['workspace'], None)
    if browser is None or not browser.done():
        raise LookupError('the sign-in browser is not open: open it, sign in, then press done')
    sign_in.answer(state['workspace'], sign_in.SIGNED_IN)
    from .check_choices import keep
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


def display():
    """Whether this computer shows windows (a Mac, or a desktop session): the browser then opens in one."""
    return sys.platform == 'darwin' or bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'))
