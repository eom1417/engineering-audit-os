"""A PostgreSQL of the run's own, on 127.0.0.1, for a project that needs a database to start.

The owner's database is never used: a run gets an empty one here, created for it, and the project's own
migrations fill it. The binaries come from the `pgserver` package (Apache-2.0, installed with EAOS's `live`
extra), so nothing needs an administrator; a PostgreSQL already installed on the machine is the fallback.
It answers 127.0.0.1 only, to a password of its own (scram-sha-256) kept in <runtime>/database/password, readable by
the person only and carried in the address the run gets: another project's run on this computer cannot connect.

State lives in <runtime>/database/: data, log, password and server.json {port, bin}. start() is idempotent: the server
of this runtime, as its own postmaster.pid says, is reused; stop() stops it and keeps the data for the next step. Under root the data
sits in the temporary folder instead, with a note naming its runtime beside it: once that runtime is gone, the next
start() removes the data (356 such databases had kept 16 GB after their projects were deleted).
"""
import glob
import hashlib
import json
import os
import secrets
import shutil
import socket
import stat
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


def _sockets(root):
    ident = hashlib.sha256(root.as_posix().encode('utf-8')).hexdigest()[:10]
    return Path('/tmp' if Path('/tmp').is_dir() else tempfile.gettempdir()) / f'eaos-pg-{ident}'


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


SHARED = Path('/opt/eaos-pg')     # where the dedicated account runs pgserver's binaries from, under root


def _reachable(bin_dir, owner):
    """Under root the dedicated account runs the binaries, and pgserver's sit in a virtualenv under /root, which it
    cannot enter: they are then copied once where it can (/opt/eaos-pg), with the libraries they find by a relative
    path (site-packages/pgserver.libs), in the same layout."""
    if subprocess.run(['test', '-x', str(bin_dir / 'pg_ctl')], user=owner).returncode == 0: return bin_dir
    install = bin_dir.resolve().parent                                   # site-packages/pgserver/pginstall
    ident = hashlib.sha256(install.as_posix().encode('utf-8')).hexdigest()[:10]
    copy = SHARED / f'pgserver-{ident}'
    if not (copy / 'pgserver' / 'pginstall' / 'bin' / 'pg_ctl').exists():
        copy.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(copy.parent, 0o755)
        with tempfile.TemporaryDirectory(prefix='.partial-', dir=copy.parent) as partial:
            made = Path(partial) / 'pgserver-copy'
            shutil.copytree(install, made / 'pgserver' / 'pginstall', symlinks=True, ignore=shutil.ignore_patterns('include'))
            if (install.parent.parent / 'pgserver.libs').is_dir():
                shutil.copytree(install.parent.parent / 'pgserver.libs', made / 'pgserver.libs', symlinks=True)
            for folder, _, _ in os.walk(made): os.chmod(folder, 0o755)
            os.replace(made, copy)
    return copy / 'pgserver' / 'pginstall' / 'bin'


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
        self.state, self.password_file = self.root / 'server.json', self.root / 'password'
        # A Unix socket's path may not pass about 104 characters (macOS) or 107 (Linux), and the data folder under
        # ~/.eaos/projects/<name>-<id>/... already does: the socket gets a short folder of its own in /tmp.
        self.sockets = _sockets(self.root.resolve())

    def _run(self, bin_dir, name, *args, check=True):
        return subprocess.run([str(bin_dir / name), *args], capture_output=True, text=True, check=check, timeout=120,
                              **({'user': self.owner} if self.owner else {}))

    def running(self):
        """server.json when the server of this data folder runs and is ready on its port, by its postmaster.pid (a port
        alone may be another project's server by now)."""
        if not self.state.is_file(): return None
        state = json.loads(self.state.read_text())
        try:
            lines = (self.data / 'postmaster.pid').read_text().splitlines()
            os.kill(int(lines[0]), 0)
        except (OSError, ValueError, IndexError):
            return None
        ready = len(lines) > 7 and lines[3].strip() == str(state['port']) and lines[7].strip() == 'ready'
        return state if ready and self.password_file.is_file() else None

    def _password(self, bin_dir):
        """The server's password, made with its data: a data folder made before it had one (trust) is made again."""
        if not self.password_file.is_file():
            self._run(bin_dir, 'pg_ctl', '-D', str(self.data), '-m', 'immediate', 'stop', check=False)
            shutil.rmtree(self.data, ignore_errors=True)
            descriptor = os.open(self.password_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, 'w') as out: out.write(secrets.token_urlsafe(24))
        return self.password_file.read_text().strip()

    def start(self):
        """The server's address, postgresql://postgres:<password>@127.0.0.1:<port>, starting it when it is not running."""
        state = self.running()
        if state: return self.url(state)
        bin_dir = binaries()
        if bin_dir is None:
            raise RuntimeError('PostgreSQL is not installed: eaos doctor --fix installs it')
        if self.owner: bin_dir = _reachable(bin_dir, self.owner)
        self.root.mkdir(parents=True, exist_ok=True)
        if self.owner:
            self.data.parent.mkdir(parents=True, exist_ok=True)
            shutil.chown(self.data.parent, self.owner)
            os.chmod(self.data.parent, stat.S_IRWXU)
            self._sweep(bin_dir)
            self.data.with_name(self.data.name + '.from').write_text(str(self.root.resolve()), encoding='utf-8')
        password = self._password(bin_dir)
        if not (self.data / 'PG_VERSION').exists():
            self.data.mkdir(parents=True, exist_ok=True)
            if self.owner: shutil.chown(self.data, self.owner)
            given = self.data.with_name(self.data.name + '.pw')         # where initdb's account reads it, then gone
            given.write_text(password)
            if self.owner: shutil.chown(given, self.owner)
            try: self._run(bin_dir, 'initdb', '-D', str(self.data), '-U', 'postgres', '--auth=scram-sha-256', f'--pwfile={given}',
                           '-E', 'UTF8', '--no-instructions')
            finally: given.unlink(missing_ok=True)
        port = free_port()
        log = self.data / 'server.log'
        self.sockets.mkdir(parents=True, exist_ok=True)
        if self.owner: shutil.chown(self.sockets, self.owner)
        self._run(bin_dir, 'pg_ctl', '-D', str(self.data), '-w', '-t', '60', '-l', str(log), '-o',
                  f"-h 127.0.0.1 -p {port} -k {self.sockets}", 'start')
        state = {'port': port, 'bin': str(bin_dir)}
        self.state.write_text(json.dumps(state))
        return self.url(state)

    def _sweep(self, bin_dir):
        """Stop and remove every database whose runtime is gone: none of them can be asked for again."""
        for note in self.data.parent.glob('*.from'):
            root = Path(note.read_text(encoding='utf-8'))
            if root.exists(): continue
            data = note.with_suffix('')
            self._run(bin_dir, 'pg_ctl', '-D', str(data), '-m', 'immediate', 'stop', check=False)
            for folder in (data, _sockets(root)): shutil.rmtree(folder, ignore_errors=True)
            note.unlink()

    def url(self, state, database='postgres'):
        return f"postgresql://postgres:{self.password_file.read_text().strip()}@127.0.0.1:{state['port']}/{database}"

    def create(self, name):
        """The address of database `name`, created empty when it does not exist."""
        state = self.running() or (self.start() and self.running())
        psql = [str(Path(state['bin']) / 'psql'), '-h', '127.0.0.1', '-p', str(state['port']), '-U', 'postgres', '-tAc']
        env = {**os.environ, 'PGPASSWORD': self.password_file.read_text().strip()}
        exists = subprocess.run(psql + [f"select 1 from pg_database where datname = '{name}'"], capture_output=True, text=True, env=env)
        if exists.stdout.strip() != '1':
            subprocess.run(psql + [f'create database "{name}"'], capture_output=True, text=True, check=True, env=env)
        return self.url(state, name)

    def stop(self):
        state = self.running()
        if state:
            self._run(Path(state['bin']), 'pg_ctl', '-D', str(self.data), '-m', 'fast', '-w', 'stop', check=False)
        if self.state.is_file(): self.state.unlink()
