"""A PostgreSQL of the run's own, on 127.0.0.1, for a project that needs a database to start.

The owner's database is never used: a run gets an empty one here, created for it, and the project's own
migrations fill it. The binaries come from the `pgserver` package (Apache-2.0, installed with EAOS's `live`
extra), so nothing needs an administrator; a PostgreSQL already installed on the machine is the fallback.
Authentication is `trust` because the server answers 127.0.0.1 only and holds nothing but what the run made.

State lives in <runtime>/database/: data, log, and server.json {port, bin}. start() is idempotent: a server
already running for this runtime is reused; stop() stops it and keeps the data for the next step.
"""
import glob
import json
import os
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path


def binaries():
    """The folder holding initdb, pg_ctl and psql, or None."""
    try:
        from pgserver._commands import POSTGRES_BIN_PATH
        if (Path(POSTGRES_BIN_PATH) / 'initdb').exists(): return Path(POSTGRES_BIN_PATH)
    except ImportError:
        pass
    found = shutil.which('initdb')
    if found: return Path(found).parent
    candidates = sorted(glob.glob('/usr/lib/postgresql/*/bin/initdb') + glob.glob('/opt/homebrew/opt/postgresql*/bin/initdb')
                        + glob.glob('/usr/local/opt/postgresql*/bin/initdb'))
    return Path(candidates[-1]).parent if candidates else None


def _free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def _as_owner():
    """PostgreSQL refuses to run as root: under root, a dedicated account runs it (created once)."""
    if os.name == 'nt' or os.geteuid() != 0: return None
    import pwd
    try: pwd.getpwnam('eaos-pg')
    except KeyError: subprocess.run(['useradd', '--system', '--no-create-home', '-s', '/usr/sbin/nologin', 'eaos-pg'], check=True)
    return 'eaos-pg'


class LocalPostgres:
    def __init__(self, runtime):
        self.root = Path(runtime) / 'database'
        self.owner = _as_owner()
        # Under root the data must be where the dedicated account can reach it: /root is not.
        self.data = (Path(tempfile.gettempdir()) / 'eaos-pg' / self.root.resolve().as_posix().strip('/').replace('/', '_')
                     if self.owner else self.root / 'data')
        self.state = self.root / 'server.json'

    def _run(self, bin_dir, name, *args, check=True):
        return subprocess.run([str(bin_dir / name), *args], capture_output=True, text=True, check=check, timeout=120,
                              **({'user': self.owner} if self.owner else {}))

    def running(self):
        if not self.state.is_file(): return None
        state = json.loads(self.state.read_text())
        done = subprocess.run([str(Path(state['bin']) / 'pg_isready'), '-h', '127.0.0.1', '-p', str(state['port'])],
                              capture_output=True)
        return state if done.returncode == 0 else None

    def start(self):
        """The server's address, postgresql://postgres@127.0.0.1:<port>, starting it when it is not running."""
        state = self.running()
        if state: return self.url(state)
        bin_dir = binaries()
        if bin_dir is None:
            raise RuntimeError('PostgreSQL is not installed: eaos doctor --fix installs it')
        self.root.mkdir(parents=True, exist_ok=True)
        if self.owner:
            self.data.parent.mkdir(parents=True, exist_ok=True)
            os.chmod(self.data.parent, 0o777)
        if not (self.data / 'PG_VERSION').exists():
            self.data.mkdir(parents=True, exist_ok=True)
            if self.owner: shutil.chown(self.data, self.owner)
            self._run(bin_dir, 'initdb', '-D', str(self.data), '-U', 'postgres', '--auth=trust', '-E', 'UTF8', '--no-instructions')
        port = _free_port()
        log = self.data / 'server.log'
        self._run(bin_dir, 'pg_ctl', '-D', str(self.data), '-w', '-t', '60', '-l', str(log), '-o',
                  f"-h 127.0.0.1 -p {port} -k {self.data}", 'start')
        state = {'port': port, 'bin': str(bin_dir)}
        self.state.write_text(json.dumps(state))
        return self.url(state)

    @staticmethod
    def url(state, database='postgres'):
        return f"postgresql://postgres@127.0.0.1:{state['port']}/{database}"

    def create(self, name):
        """The address of database `name`, created empty when it does not exist."""
        state = self.running() or (self.start() and self.running())
        psql = [str(Path(state['bin']) / 'psql'), '-h', '127.0.0.1', '-p', str(state['port']), '-U', 'postgres', '-tAc']
        exists = subprocess.run(psql + [f"select 1 from pg_database where datname = '{name}'"], capture_output=True, text=True)
        if exists.stdout.strip() != '1':
            subprocess.run(psql + [f'create database "{name}"'], capture_output=True, text=True, check=True)
        return self.url(state, name)

    def stop(self):
        state = self.running()
        if state:
            self._run(Path(state['bin']), 'pg_ctl', '-D', str(self.data), '-m', 'fast', '-w', 'stop', check=False)
        if self.state.is_file(): self.state.unlink()
