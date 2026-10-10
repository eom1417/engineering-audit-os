"""`eaos studio` and the `open_studio` tool: the live Studio of a project, started once and reused.

This module finds, records and starts the server without importing it (`eaos studio` itself runs in
server.run_foreground), so the `open_studio` tool does not depend on the server and the command centre it mounts,
which call the MCP tools back.

One server per project. Its address, port, process and token are kept in ~/.eaos/studio/<workspace>.json, readable by
the person only, so a second `eaos studio` (or `open_studio`) reopens the running one instead of starting another.
A record whose process is gone, or whose server does not answer with its token, is replaced.

`eaos studio` runs the server in the terminal until Ctrl-C. `open_studio` starts it as its own process (the assistant's
call must return) and waits until it answers. The server rebuilds the Studio data from the ledger first, as
open_report does, so the Studio shows what is in the person's branch now; a project not checked yet opens on the
Studio's empty state, which says how to start.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from .. import guided

STARTUP = 15.0           # seconds open_studio waits for the server it started to answer


def records_folder():
    return guided.home() / 'studio'


def record_path(state):
    return records_folder() / f"{Path(state['workspace']).name}.json"


def _alive(pid):
    try: os.kill(int(pid), 0)
    except (OSError, ValueError, TypeError): return False
    return True


def answers(record, timeout=2.0):
    """True when the server of `record` answers /api/session with its token."""
    try:
        request = urllib.request.Request(f"http://127.0.0.1:{record['port']}/api/session", headers={'X-EAOS-Token': record['token']})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status == 200 and json.loads(response.read()).get('mode') == 'live'
    except (OSError, ValueError, KeyError):
        return False


def running(state):
    """The record of the project's live server when it is up and answering, else None (a stale record is removed)."""
    path = record_path(state)
    try: record = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError): return None
    if _alive(record.get('pid')) and answers(record): return record
    path.unlink(missing_ok=True)
    return None


def _write_record(state, record):
    folder = records_folder()
    folder.mkdir(parents=True, exist_ok=True)
    path = record_path(state)
    temporary = path.with_name(f'.{path.name}.tmp')
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        json.dump(record, handle)
    os.replace(temporary, path)


def url_of(record, route=''):
    """The Studio's address with its launch token; `route` (`/scan`, the live map) opens that page, the token then in
    the route's query (studio/public/boot.js reads both forms)."""
    origin = record.get('remote_origin')
    if origin:
        from ..studio.actions.security import Locks
        Locks(record['port'], remote_origin=origin)
    base = origin or f"http://127.0.0.1:{record['port']}"
    return f"{base}/#{route}?token={record['token']}" if route else f"{base}/#token={record['token']}"


def prepare(project=None):
    """The project's state and its report folder, with the Studio data rebuilt from the ledger when it was checked."""
    from ..agent_tools import project_state
    state = project_state(project)
    report = guided.report_of(state)
    if guided.scan_done(state):
        guided.reconcile(state)
        guided.publish(state)
        guided.save(state)
    return state, report


def open_studio(project=None, show=True, route=''):
    """`open_studio`: the live Studio's address (on `route`, when given), starting its server in the background when it
    is not running. The server runs from the EAOS workspace folder with PYTHONSAFEPATH=1, so neither the folder it
    starts in nor the project (which may be EAOS's own repository) can put another `eaos` before this one. It rebuilds
    no data: a server it starts does (run_foreground), and a running one's is kept by every step that changes it, so a
    check asked for starts at once."""
    from ..agent_tools import project_state
    state = project_state(project)
    found = running(state)
    started = False
    if not found:
        logs = Path(state['workspace']) / 'logs'
        logs.mkdir(parents=True, exist_ok=True)
        with open(logs / 'studio-server.log', 'ab') as log:
            # The same EAOS as this one, wherever the project folder is
            here = str(Path(__file__).resolve().parents[2])
            env = {**os.environ, 'PYTHONSAFEPATH': '1',
                   'PYTHONPATH': os.pathsep.join([here, *filter(None, [os.environ.get('PYTHONPATH')])])}
            subprocess.Popen([sys.executable, '-m', 'eaos', 'studio', state['project'], '--no-open'], cwd=state['workspace'], env=env,
                             stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True, close_fds=True)
        deadline = time.monotonic() + STARTUP
        while time.monotonic() < deadline and not found:
            time.sleep(0.25)
            found = running(state)
        started = bool(found)
        if not found:
            return {'error': 'the Studio server did not start in time', 'log': str(logs / 'studio-server.log'),
                    'what_now': 'Tell the person the live Studio could not start, and offer open_report (the report page) instead.'}
    url = url_of(found, route)
    opened = _open(url, show)
    return {'studio': url, 'opened_in_browser': opened, 'started': started, 'live': True,
            'checked': guided.scan_done(state),
            'what_now': ('Tell the person the Studio is open in their browser' if opened else
                         'Give the person this address to open in their browser on this computer (it works only here)')
                        + '; it updates by itself after every check, batch, merge and decision. '
                        + ('' if guided.scan_done(state) else 'The project is not checked yet: offer audit first. ')
                        + 'Do not paste the address anywhere else: it holds the key of this session.'}


def _open(url, show):
    if not show: return False
    import webbrowser
    try: return bool(webbrowser.open(url))
    except Exception: return False
