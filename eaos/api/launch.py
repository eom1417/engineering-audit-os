"""The live Studio's record: one server per project, found and reused without importing the server.

Its address, port, process and token are kept in ~/.eaos/studio/<workspace>.json, readable by the person only, so a
second `eaos studio` (server.run_foreground) or `open_studio` (agent_tools.open_studio) reopens the running one instead
of starting another. A record whose process is gone, or whose server does not answer with its token, is replaced. It
imports neither the server nor the tools, so the guided commands, the tools and the server all read it.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from ..places import home

STARTUP = 15.0       # seconds `start` waits for the server it started to answer


def records_folder():
    return home() / 'studio'


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


def start(state):
    """(record, started): the project's live server, started in the background when it is not running; (None, False)
    when it did not answer in time. It runs from the EAOS workspace folder with PYTHONSAFEPATH=1, so neither the folder
    it starts in nor the project (which may be EAOS's own repository) can put another `eaos` before this one."""
    found = running(state)
    if found: return found, False
    logs = Path(state['workspace']) / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    with open(logs / 'studio-server.log', 'ab') as log:
        here = str(Path(__file__).resolve().parents[2])
        env = {**os.environ, 'PYTHONSAFEPATH': '1', 'PYTHONPATH': os.pathsep.join([here, *filter(None, [os.environ.get('PYTHONPATH')])])}
        subprocess.Popen([sys.executable, '-m', 'eaos', 'studio', state['project'], '--no-open'], cwd=state['workspace'], env=env,
                         stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True, close_fds=True)
    deadline = time.monotonic() + STARTUP
    while time.monotonic() < deadline and not found:
        time.sleep(0.25)
        found = running(state)
    return found, bool(found)


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


def _open(url, show):
    if not show: return False
    import webbrowser
    try: return bool(webbrowser.open(url))
    except Exception: return False
