"""A PostgreSQL of the run's own, on 127.0.0.1, for a project that needs a database to start.

The project's own database is never used: a run gets an empty one here, created for it, and the project's own
migrations fill it; the project's checks get a copy of it of their own (copy()), dropped when they end. The binaries
come from the `pgserver` package (Apache-2.0, installed with EAOS's `live` extra), so nothing needs an administrator;
a PostgreSQL already installed on the machine is the fallback.
It answers 127.0.0.1 only, to a password of its own (scram-sha-256) kept in <runtime>/database/password, readable by
the person only and carried in the address the run gets: another project's run on this computer cannot connect.

State lives in <runtime>/database/: data, log, password and server.json {port, bin}. start() is idempotent: the server
of this runtime, as its own postmaster.pid says, is reused. Every run that created a database on it holds users.lock
(shared) until its stop(), and the last one leaving stops the server, keeping the data for the next step: runs side by
side, each on a database of its own (eaos/features/app_run/adapters/app/run.py), never stop one another's. Under root the data
sits in the temporary folder instead, with a note naming its runtime beside it: once that runtime is gone, the next
start() removes the data, so no data outlives a deleted project.
"""
import contextlib
import fcntl
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
from ....kernel.system.errors import noted


def binaries():
    """The folder holding initdb, pg_ctl and psql, or None."""
    try:
        from pgserver._commands import POSTGRES_BIN_PATH
        if (Path(POSTGRES_BIN_PATH) / 'initdb').exists(): return Path(POSTGRES_BIN_PATH)
    except ImportError as error:
        noted('pgserver is not installed: the initdb on the path is used', error)
    found = shutil.which('initdb')
    if found: return Path(found).parent
    candidates = sorted(glob.glob('/usr/lib/postgresql/*/bin/initdb')
                        + glob.glob('/opt/homebrew/opt/postgresql*/bin/initdb')
                        + glob.glob('/usr/local/opt/postgresql*/bin/initdb'))
    return Path(candidates[-1]).parent if candidates else None


def _sockets(root):
    ident = hashlib.sha256(root.as_posix().encode('utf-8')).hexdigest()[:10]
    # a socket's path must stay short (macOS's own temporary folder is too long); one folder per project
    return Path('/tmp' if Path('/tmp').is_dir() else tempfile.gettempdir()) / f'eaos-pg-{ident}'  # nosec B108


def _private(path, text):
    """Write a password to path, readable by its owner alone from the first byte."""
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as out: out.write(text)


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


COPY = '_checks_'     # in the name of a database copy(): one a killed run left is dropped when the server starts again
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
        _open_to(copy.parent, owner)
        with tempfile.TemporaryDirectory(prefix='.partial-', dir=copy.parent) as partial:
            made = Path(partial) / 'pgserver-copy'
            shutil.copytree(install, made / 'pgserver' / 'pginstall', symlinks=True,
                            ignore=shutil.ignore_patterns('include'))
            if (install.parent.parent / 'pgserver.libs').is_dir():
                shutil.copytree(install.parent.parent / 'pgserver.libs', made / 'pgserver.libs', symlinks=True)
            for folder, _, _ in os.walk(made): _open_to(folder, owner)
            os.replace(made, copy)
    return copy / 'pgserver' / 'pginstall' / 'bin'


def _open_to(folder, owner):
    """A folder the dedicated account owns, closed to every other account."""
    shutil.chown(folder, user=owner, group=owner)
    os.chmod(folder, 0o700)  # nosemgrep: python.lang.security.audit.insecure-file-permissions -- 0o700 closes the folder to every other account


def _as_owner():
    """PostgreSQL refuses to run as root: under root, a dedicated account runs it (created once)."""
    if os.name == 'nt' or os.geteuid() != 0: return None
    import pwd
    try: pwd.getpwnam('eaos-pg')
    except KeyError:
        subprocess.run(['useradd', '--system', '--no-create-home', '-s', '/usr/sbin/nologin', 'eaos-pg'], check=True)
    return 'eaos-pg'


class LocalPostgres:
    def __init__(self, runtime):
        self.root = Path(runtime) / 'database'
        self.owner = _as_owner()
        # Under root the data must be where the dedicated account can reach it: /root is not.
        self.data = (Path(tempfile.gettempdir()) / 'eaos-pg'
                     / self.root.resolve().as_posix().strip('/').replace('/', '_')
                     if self.owner else self.root / 'data')
        self.state, self.password_file = self.root / 'server.json', self.root / 'password'
        # A Unix socket's path may not pass about 104 characters (macOS) or 107 (Linux), and the data folder under
        # ~/.eaos/projects/<name>-<id>/... already does: the socket gets a short folder of its own in /tmp.
        self.sockets = _sockets(self.root.resolve())
        self.users = self.root / 'users.lock'
        self._held = None
        self._copies = []

    def _run(self, bin_dir, name, *args, check=True):
        return subprocess.run([str(bin_dir / name), *args], capture_output=True, text=True, check=check, timeout=120,  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- PostgreSQL's own binaries at their pin, a list argv, no shell
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
            _private(self.password_file, secrets.token_urlsafe(24))
        return self.password_file.read_text().strip()

    def start(self):
        """The server's address, postgresql://postgres:<password>@127.0.0.1:<port>, starting it when it is not
        running."""
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
            _private(given, password)
            if self.owner: shutil.chown(given, self.owner)
            try: self._run(bin_dir, 'initdb', '-D', str(self.data), '-U', 'postgres',
                           '--auth=scram-sha-256', f'--pwfile={given}',
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
        self._psql(state, "select format('drop database %I with (force)', datname) from pg_database "
                   "where datname ~ (:'copy' || '[0-9a-f]{8}$') \\gexec",
                   copy=COPY)
        return self.url(state)

    def _sweep(self, bin_dir):
        """Stop and remove every database whose runtime is gone: none of them can be asked for again."""
        for note in self.data.parent.glob('*.from'):
            try: root = Path(note.read_text(encoding='utf-8'))
            except FileNotFoundError as error:          # another run's sweep took it first
                noted('the note is gone', error)
                continue
            if root.exists(): continue
            data = note.with_suffix('')
            self._run(bin_dir, 'pg_ctl', '-D', str(data), '-m', 'immediate', 'stop', check=False)
            for folder in (data, _sockets(root)): shutil.rmtree(folder, ignore_errors=True)
            note.unlink(missing_ok=True)

    def url(self, state, database='postgres'):
        return f"postgresql://postgres:{self.password_file.read_text().strip()}@127.0.0.1:{state['port']}/{database}"

    @contextlib.contextmanager
    def _server(self):
        """The running server's state, the server held until stop(). Runs side by side start the server and create their
        databases one at a time."""
        self.root.mkdir(parents=True, exist_ok=True)
        if self._held is None:
            self._held = open(self.users, 'a')
            fcntl.flock(self._held, fcntl.LOCK_SH)       # held before the server is looked at: the last stop() waits
        with open(self.root / 'start.lock', 'a') as alone:
            fcntl.flock(alone, fcntl.LOCK_EX)
            yield self.running() or (self.start() and self.running())

    def _psql(self, state, sql, **names):
        """psql on the server, `names` as psql variables quoted by psql itself (:'name' a text, :"name" a name), never
        pasted into SQL."""
        argv = [str(Path(state['bin']) / 'psql'), '-h', '127.0.0.1', '-p', str(state['port']), '-U', 'postgres', '-tA',
                '-v', 'ON_ERROR_STOP=1', *[f'--set={key}={value}' for key, value in names.items()]]
        return subprocess.run(argv, input=sql, capture_output=True, text=True,  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- psql at its pin, the names passed as psql variables, never in the SQL text
                              env={**os.environ, 'PGPASSWORD': self.password_file.read_text().strip()})

    def _ensure(self, state, name):
        if self._psql(state, "select 1 from pg_database where datname = :'name'", name=name).stdout.strip() != '1':
            self._psql(state, 'create database :"name"', name=name).check_returncode()

    def create(self, name):
        """The address of database `name`, created empty when it does not exist; the server is held until stop()."""
        with self._server() as state: self._ensure(state, name)
        return self.url(state, name)

    def copy(self, base):
        """The address of a database of this holder's alone, copied from `base` as it is now (created empty when
        missing): what setup wrote in it is there, nothing an earlier holder wrote in its copy is, and `base` is never
        written. Dropped at stop(). A base another run is connected to cannot be copied: the database is then made
        empty."""
        name = f'{base[:40]}{COPY}{secrets.token_hex(4)}'
        with self._server() as state:
            self._ensure(state, base)
            if self._psql(state, 'create database :"name" template :"base"', name=name, base=base).returncode:
                self._psql(state, 'create database :"name"', name=name).check_returncode()
        self._copies.append(name)
        return self.url(state, name)

    def stop(self):
        """Leave the server, and stop it when no other run holds it (its data stays)."""
        state = self.running()
        # FORCE ends its connections in the same step: a check may leave one open
        for name in self._copies if state else []:
            self._psql(state, 'drop database if exists :"name" with (force)', name=name)
        self._copies = []
        if self._held is not None:
            self._held.close()
            self._held = None
        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.users, 'a') as last:
            try: fcntl.flock(last, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: return              # another run is on it
            state = self.running()
            if state:
                self._run(Path(state['bin']), 'pg_ctl', '-D', str(self.data), '-m', 'fast', '-w', 'stop', check=False)
            if self.state.is_file(): self.state.unlink()
