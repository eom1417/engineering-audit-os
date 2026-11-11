"""Starting EAOS's own processes so they outlive the session that asked: in a session of their own, or as a transient
systemd service on a computer that keeps EAOS's work as services (`durable`).
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

from ..project.places import home
from eaos import HOME

HEADLESS = 'EAOS_HEADLESS'   # set in the headless host (eaos/doors/govern.py) and the runs it starts
SHELL_ONLY = frozenset({'PWD', 'OLDPWD', 'SHLVL', '_', 'TERM', 'COLUMNS', 'LINES', 'TMUX', 'TMUX_PANE',
                        'STY'})   # not passed on


def own_env(**extra):
    """The environment of a process this EAOS starts (`extra` added): PYTHONSAFEPATH=1 and this EAOS
    first on the path."""
    here = str(HOME.parent)
    return {**os.environ, **extra, 'PYTHONSAFEPATH': '1',
            'PYTHONPATH': os.pathsep.join([here, *filter(None, [os.environ.get('PYTHONPATH')])])}


def log_path(state, name):
    logs = Path(state['workspace']) / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    return logs / name


def detach(state, argv, env, log, mode='ab'):
    """`argv` in a session of its own, from the project's EAOS workspace folder, its output in logs/`log` (`mode` 'wb':
    each start writes it again, so it stays bounded)."""
    with open(log_path(state, log), mode) as out:
        subprocess.Popen(argv, cwd=state['workspace'], env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=out,  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- EAOS starts itself (sys.executable -m eaos), a list argv, no shell
                         start_new_session=True, close_fds=True)


def durable():
    """True when this computer keeps EAOS's work as systemd services (~/.eaos/studio-service says `systemd`, as
    install.sh writes it on a server run by systemd): the work then belongs to the computer, not to the session of the
    assistant that asked for it, which a remote server ends with the session. Elsewhere (a person's own computer) it is
    a process in a session of its own."""
    try: chosen = (home() / 'studio-service').read_text(encoding='utf-8').strip()
    except OSError: return False
    return chosen == 'systemd' and Path('/run/systemd/system').is_dir() and bool(shutil.which('systemd-run'))


def service_name(state, kind):
    return f'eaos-{kind}-' + re.sub(r'[^A-Za-z0-9_-]', '-', Path(state['workspace']).name)


def _systemctl(*words):
    return subprocess.run(['systemctl', *([] if os.geteuid() == 0 else ['--user']), *words],
                          capture_output=True, text=True)


def as_unit(unit, argv, env, where):
    """`argv` as a transient systemd service `unit` of this computer, so the session of the assistant that asked for it
    (which a remote server ends with the session) cannot take it down; True when systemd took it. Its environment is
    the asker's, passed by name only (no value on a command line); `where`: its description, the `log` its output is
    appended to, its `cwd`, and `extra` properties."""
    description, log, cwd, extra = where['description'], where['log'], where['cwd'], where.get('extra') or ()
    names = sorted(name for name in env if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name) and name not in SHELL_ONLY)
    done = subprocess.run(['systemd-run', *([] if os.geteuid() == 0 else ['--user']), f'--unit={unit}',
                           f'--description={description}',
                           '--collect', '--service-type=exec', f'--working-directory={cwd}', *extra,
                           f'--property=StandardOutput=append:{log}', f'--property=StandardError=append:{log}',
                           *(f'--setenv={name}' for name in names), *argv], env=env, capture_output=True, text=True)
    return done.returncode == 0


def unit_pid(unit):
    """The main process of a running unit, or None."""
    pid = _systemctl('show', '--property=MainPID', '--value', unit).stdout.strip()
    return int(pid) if pid.isdigit() and int(pid) else None
