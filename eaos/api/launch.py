"""The live Studio's record: one server per project, found and reused without importing the server.

Its address, port, process and token are kept in ~/.eaos/studio/<workspace>.json, readable by the person only, so a
second `eaos studio` (server.run_foreground) or `open_studio` (agent_tools.open_studio) reopens the running one instead
of starting another. A record whose process is gone, or whose server does not answer with its token, is replaced. It
imports neither the server nor the tools, so the guided commands, the tools and the server all read it.

On a remote server the Studio belongs to the computer: told its routed address once (`serve_remotely`), it answers
there with a plain address that stays the same, and runs as a systemd service that outlives the assistant's session.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from .. import __version__
from ..places import home

STARTUP = 15.0       # seconds `start` waits for the server it started to answer
HEADLESS = 'EAOS_HEADLESS'   # set in the headless host (eaos/govern.py) and the runs it starts: their steps open no Studio
SHELL_ONLY = frozenset({'PWD', 'OLDPWD', 'SHLVL', '_', 'TERM', 'COLUMNS', 'LINES', 'TMUX', 'TMUX_PANE', 'STY'})   # not passed on


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
    if found and found.get('version') == __version__: return found, False
    if found: _retire(state, found)          # an EAOS updated under a Studio still running the old one (HungerLab: 0.0.59)
    env, argv = own_env(), [sys.executable, '-m', 'eaos', 'studio', state['project'], '--no-open']
    if not (durable() and _as_service(state, argv, env, log_path(state, 'studio-server.log'))): detach(state, argv, env, 'studio-server.log')
    deadline = time.monotonic() + STARTUP
    while time.monotonic() < deadline and not found:
        time.sleep(0.25)
        found = running(state)
    return found, bool(found)


def own_env(**extra):
    """The environment of a process this EAOS starts (`extra` added): PYTHONSAFEPATH=1 and this EAOS first on the path."""
    here = str(Path(__file__).resolve().parents[2])
    return {**os.environ, **extra, 'PYTHONSAFEPATH': '1', 'PYTHONPATH': os.pathsep.join([here, *filter(None, [os.environ.get('PYTHONPATH')])])}


def log_path(state, name):
    logs = Path(state['workspace']) / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    return logs / name


def detach(state, argv, env, log, mode='ab'):
    """`argv` in a session of its own, from the project's EAOS workspace folder, its output in logs/`log` (`mode` 'wb':
    each start writes it again, so it stays bounded)."""
    with open(log_path(state, log), mode) as out:
        subprocess.Popen(argv, cwd=state['workspace'], env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=out,
                         start_new_session=True, close_fds=True)


def durable():
    """True when this computer keeps its Studios as systemd services (~/.eaos/studio-service says `systemd`, as
    install.sh writes it on a server run by systemd): a Studio then belongs to the computer, not to the session of the
    assistant that asked for it, which a remote server ends with the session; it restarts after a crash, on its kept
    port and token. Elsewhere (a person's own computer) it is a process in a session of its own."""
    try: chosen = (home() / 'studio-service').read_text(encoding='utf-8').strip()
    except OSError: return False
    return chosen == 'systemd' and Path('/run/systemd/system').is_dir() and bool(shutil.which('systemd-run'))


def service_name(state):
    return 'eaos-studio-' + re.sub(r'[^A-Za-z0-9_-]', '-', Path(state['workspace']).name)


def _as_service(state, argv, env, log):
    """The server as a transient systemd service of its own; False when systemd refused it. Its environment is the
    asker's, passed by name only (no value on a command line); a unit still starting is waited for, not doubled."""
    unit, user = service_name(state), ([] if os.geteuid() == 0 else ['--user'])
    systemctl = lambda *words: subprocess.run(['systemctl', *user, *words, unit], capture_output=True, text=True)
    if systemctl('is-active').stdout.strip() in ('active', 'activating', 'reloading'): return True
    systemctl('reset-failed')
    names = sorted(name for name in env if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name) and name not in SHELL_ONLY)
    done = subprocess.run(['systemd-run', *user, f'--unit={unit}', f"--description=EAOS Studio of {Path(state['project']).name}",
                           '--collect', '--service-type=exec', f"--working-directory={state['workspace']}",
                           '--property=Restart=on-failure', '--property=RestartSec=2s',
                           f'--property=StandardOutput=append:{log}', f'--property=StandardError=append:{log}',
                           *(f'--setenv={name}' for name in names), *argv], env=env, capture_output=True, text=True)
    return done.returncode == 0



def _retire(state, record):
    """Stop a Studio of another EAOS version: its service, which would otherwise come back, else its process."""
    if durable(): subprocess.run(['systemctl', *([] if os.geteuid() == 0 else ['--user']), 'stop', service_name(state)], capture_output=True)
    stop(record)


def stop(record, seconds=10.0):
    """Stop the server of `record` (it removes its record as it ends) and wait for it."""
    try: os.kill(int(record['pid']), 15)
    except (OSError, ValueError, KeyError): return
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and _alive(record['pid']): time.sleep(0.1)


def serve_remotely(address):
    """This computer is a remote server whose ports the person reaches at `address` (its routed address for one port,
    or the pattern with {port}), as the assistant there knows it: every Studio answers there, behind that sign-in, with
    a plain address (~/.eaos/remote-origin), and runs as a systemd service when systemd runs the computer
    (~/.eaos/studio-service). The pattern, or ValueError for an address that is not a Remote one."""
    from ..studio.actions.security import Locks
    pattern = re.sub(r'--\d{1,5}(?=\.)', '--{port}', str(address or '').strip().rstrip('/'), count=1)
    if '{port}' not in pattern: raise ValueError(f'{address}: not a routed address with its port')
    Locks(8765, remote_origin=pattern.format(port=8765))
    home().mkdir(parents=True, exist_ok=True)
    (home() / 'remote-origin').write_text(pattern + '\n', encoding='utf-8')
    if Path('/run/systemd/system').is_dir() and shutil.which('systemd-run'):
        (home() / 'studio-service').write_text('systemd\n', encoding='utf-8')
    return pattern


REMOTE_ORIGIN = 'EAOS_REMOTE_ORIGIN'


def remote_template():
    """The address every Studio of this computer is reached at when it runs on a remote server: $EAOS_REMOTE_ORIGIN, else
    the one line of ~/.eaos/remote-origin, a Remote project address with {port} for the Studio's port
    (https://<project>--{port}.dev.remote.e-m.sa); None on a person's own computer, where the address is localhost."""
    text = os.environ.get(REMOTE_ORIGIN)
    if text is None:
        try: text = (home() / 'remote-origin').read_text(encoding='utf-8')
        except OSError: return None
    text = text.strip()
    return text if '{port}' in text else None


def token_path(state):
    """The project's launch token, kept across restarts (read only by the person), so an address that carries it, saved
    or bookmarked, keeps opening the Studio."""
    return records_folder() / f"{Path(state['workspace']).name}.token"


def port_path(state):
    return records_folder() / f"{Path(state['workspace']).name}.port"


def kept_port(state):
    """The port the project's Studio used last, so its address stays the same; 0 (any free one) the first time."""
    try: return int(port_path(state).read_text(encoding='utf-8').strip())
    except (OSError, ValueError): return 0


def keep_port(state, port):
    records_folder().mkdir(parents=True, exist_ok=True)
    port_path(state).write_text(f'{port}\n', encoding='utf-8')


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
    """The Studio's address; `route` (`/scan`, the live map) opens that page. It carries the launch token, kept across
    restarts so the address stays the same, in the route's query when there is a route (console/src/boot.js reads
    both): no program on this computer can ask the server for it. Only a Remote address behind the Remote sign-in is
    plain (`page_reads_token`): its page reads the token from its server, which never gives it to this computer."""
    origin = record.get('remote_origin') or f"http://127.0.0.1:{record['port']}"
    if record.get('remote_origin'):
        from ..studio.actions.security import Locks
        Locks(record['port'], remote_origin=origin)
    if record.get('page_reads_token'):     # behind the Remote sign-in the page reads its token from its server
        return f"{origin}/" + (f'#{route}' if route else '')
    return f"{origin}/#{route}?token={record['token']}" if route else f"{origin}/#token={record['token']}"


def _open(url, show):
    if not show: return False
    import webbrowser
    try: return bool(webbrowser.open(url))
    except Exception: return False
