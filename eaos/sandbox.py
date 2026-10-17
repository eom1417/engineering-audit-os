"""Run a project's own code: only with the owner's authorization, in a copy, without secrets.

The execution stages (S05's run half, S08-S14) need the project running. Nothing here starts before
refusal() finds nothing wrong with authorization.json: it must keep its contract, not be expired, name
the stage, and, when a target is given, name the commit the target is at. The project itself is never
touched: every command runs in a copy of the authorised commit (committed_copy: never the working folder,
and never a .env file), as its own process group, with
an environment of PATH, a temporary HOME and TMPDIR, LANG, and the names the owner listed in env_allow.

A run's copy, HOME and TMPDIR share one folder, held (flock) while the run lives: dispose() removes it, and the next
run removes any folder no live run holds, so a check stopped or killed midway leaves nothing behind for long.

Where the kernel allows it, every command sees the disk as its own run only (eaos/sandbox_view.py): the person's HOME,
EAOS's home, the reports, the temporary folder and every project EAOS knows are hidden, its copy, the paths it is
given and the tools (read-only) are shown, so one project's code never reads another's state, sign-in or database.
A command runs with no network, so a test suite cannot reach anything outside. A started service must answer the
host, so it keeps the network; that, and every other thing this sandbox could not isolate, is written to
sandbox-run.json -> limitations, never implied.
"""
import fcntl
import functools
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path


class AuthorizationError(Exception):
    """The owner's authorization does not allow this run."""


EXECUTION_STAGES = ('S08', 'S09', 'S10', 'S11', 'S12', 'S13', 'S14')


def refusal(path, stage, commit=None, target=None):
    """Why authorization.json at `path` does not allow `stage` (at `commit`), or '' when it does.

    From S08 on, the project runs as changed by EAOS: a candidate committed on top of the granted commit. Such a
    commit is allowed when `target` is a checkout in which the granted commit is its ancestor; any other commit,
    or the same one in a repository without that history, is refused as before."""
    from .artifact_contracts import contracts, validate
    path = Path(path)
    if not path.is_file(): return f'authorization: {path} is missing; the owner writes it (docs/MASTER-BLUEPRINT.md, section 10)'
    try: grant = json.loads(path.read_text(encoding='utf-8'))
    except ValueError as error: return f'authorization: {path} is not JSON: {error}'
    problems = validate(grant, contracts()['authorization'])
    if problems: return f'authorization: {path} breaks schemas/artifacts/authorization.schema.json: {problems[0]}'
    expires = grant['expires']
    try:
        if len(expires) == 10:  # a date: valid through that whole day
            expired = date.fromisoformat(expires) < date.today()
        else:
            moment = datetime.fromisoformat(expires.replace('Z', '+00:00'))
            expired = (moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)) <= datetime.now(timezone.utc)
    except ValueError:
        return f'authorization: expires {expires!r} is not an ISO date'
    if expired: return f'authorization: expired at {expires}'
    if stage not in grant['stages']: return f"authorization: {stage} is not among the granted stages {grant['stages']}"
    if commit is not None and grant['commit'] != commit:
        descends = (stage in EXECUTION_STAGES and target is not None and subprocess.run(
            ['git', '-C', str(target), 'merge-base', '--is-ancestor', grant['commit'], commit], capture_output=True).returncode == 0)
        if not descends:
            return f"authorization: granted for commit {grant['commit'][:12]}, but the project is at {commit[:12]}"
    return ''


def head(target):
    done = subprocess.run(['git', '-C', str(target), 'rev-parse', 'HEAD'], capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else ''


# A .env file holds the owner's real values (a production database, live keys). The copy never carries one:
# the run's values come from the run profile, generated for it. Examples and templates hold no secret.
ENV_EXAMPLES = ('.example', '.sample', '.template', '.dist', '.defaults')


def committed_copy(target, commit, destination):
    """The project exactly as committed at `commit`, without any .env file: not the working folder, whose
    unsaved edits and ignored files (a real .env first of all) are not what the owner authorised."""
    destination.mkdir(parents=True)
    archive = subprocess.run(['git', '-C', str(target), 'archive', '--format=tar', commit], capture_output=True)
    if archive.returncode: raise AuthorizationError(f'could not read commit {commit[:12]}: {archive.stderr.decode()[-200:]}')
    subprocess.run(['tar', '-x', '-C', str(destination)], input=archive.stdout, check=True)
    for path in destination.rglob('.env*'):
        if path.is_file() and not path.name.endswith(ENV_EXAMPLES): path.unlink()
    return destination


def _tail(path, size=2000):
    """The end of a service's log: what it said before it stopped, which is what anyone fixing it needs."""
    try: return Path(path).read_text(encoding='utf-8', errors='replace')[-size:].strip()
    except OSError: return ''


def _network_isolation():
    """The prefix that runs a command with no network, or () where the kernel does not allow it."""
    unshare = shutil.which('unshare')
    if not unshare: return ()
    try:
        done = subprocess.run([unshare, '-rn', 'true'], capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return ()
    return (unshare, '-rn') if done.returncode == 0 else ()


LAUNCHER = Path(__file__).with_name('sandbox_view.py')


def _launcher(spec):
    return [sys.executable, '-I', str(LAUNCHER), json.dumps(spec)]


@functools.cache
def _view_refusal():
    """'' when a command can have a view of its own run here (a user and a mount namespace), else why it cannot."""
    try:
        done = subprocess.run([*_launcher({'offline': True, 'cwd': '/', 'mounts': [['hide', tempfile.gettempdir()]]}), 'true'],
                              capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as problem:
        return str(problem)[:200]
    return '' if done.returncode == 0 else (done.stderr.strip()[-200:] or f'exit {done.returncode}')


def hidden():
    """The real folders a sandboxed command never sees: the person's HOME, EAOS's home, its projects and Studio records,
    the reports, the temporary folder (other runs' databases), and every project EAOS knows with its report, the run's
    own included (it sees its copy, never the working folder and its .env). The outermost ones only."""
    from .places import home, outputs_root
    folders = [Path.home(), home(), home() / 'projects', home() / 'studio', outputs_root(), Path('/tmp'), Path(tempfile.gettempdir())]
    for record in (home() / 'projects').glob('*/state.json'):
        try: state = json.loads(record.read_text(encoding='utf-8'))
        except (OSError, ValueError): continue
        folders += [Path(state[key]) for key in ('project', 'outputs') if state.get(key)]
    real = {Path(os.path.realpath(folder)) for folder in folders if folder.is_dir()} - {Path('/')}
    return sorted(folder for folder in real if not any(other in folder.parents for other in real))


def _within(path, folders):
    return any(path == folder or folder in path.parents for folder in folders)


def mounts(masks, keeps):
    """The launcher's mounts: each of `masks` hidden, then each (path, read_only) of `keeps` shown again at its own name
    and at its real one, outermost first, so a path shown inside a hidden folder stays shown. A kept path is shown when
    a mask hides it, a read-only one always (to make it read-only); never one that holds a mask, which it would show."""
    planned = [(mask, 'hide') for mask in masks]
    for path, read_only in keeps:
        real = Path(os.path.realpath(path))
        if not real.exists() or any(_within(mask, [real]) for mask in masks): continue
        for target in dict.fromkeys((Path(os.path.abspath(path)), real)):
            if read_only or any(mask in target.parents for mask in masks): planned.append((target, 'show', str(real), read_only))
    planned.sort(key=lambda row: len(row[0].parts))
    return [[kind, str(target), *rest] for target, kind, *rest in planned]


def named(argv, env):
    """(path, read_only) of each absolute path a command is given, in its arguments (`--x=/path` too) and its values (a
    file still to be written: its folder): its own things outside the copy, such as its records, its report and its
    data. The folders of PATH are given read-only."""
    found = []
    for name, text in [('', part) for part in argv] + list(env.items()):
        for piece in re.split(f'[={os.pathsep}]', str(text)):
            path = Path(piece) if piece.startswith('/') else None
            if path and not path.exists(): path = path.parent
            if path and path != Path('/') and path.exists(): found.append((str(path), name == 'PATH'))
    return found


def _listening(port):
    """The sockets listening on `port` (as /proc/<pid>/fd names them), None where /proc does not say."""
    tables = [Path(f'/proc/net/{name}') for name in ('tcp', 'tcp6')]
    if not tables[0].is_file(): return None
    rows = [row.split() for table in tables if table.is_file() for row in table.read_text().splitlines()[1:]]
    return {f'socket:[{row[9]}]' for row in rows if row[3] == '0A' and int(row[1].rsplit(':', 1)[1], 16) == port}


def _listens(port, group):
    """Whether a process of process group `group` listens on `port`; None where it cannot be told. A health answer
    counts only from the sandbox's own service, never from another project's app on that port."""
    sockets = _listening(port)
    if sockets is None: return None
    for pid in (int(name) for name in os.listdir('/proc') if name.isdigit()):
        try:
            if os.getpgid(pid) == group and any(os.readlink(f'/proc/{pid}/fd/{fd}') in sockets for fd in os.listdir(f'/proc/{pid}/fd')):
                return True
        except OSError:
            continue
    return False


class Sandbox:
    def __init__(self, target, authorization, workdir, stage):
        self.target, self.workdir, self.stage = Path(target), Path(workdir), stage
        commit = head(self.target)
        if not commit:
            raise AuthorizationError(f'{self.target} is not a git checkout: an authorization names a commit')
        reason = refusal(authorization, stage, commit, self.target)
        if reason: raise AuthorizationError(reason)
        self.allowed = json.loads(Path(authorization).read_text(encoding='utf-8'))['env_allow']
        self.workdir.mkdir(parents=True, exist_ok=True)
        with _gate(self.workdir):                          # no sweep between a folder's making and its hold
            _sweep(self.workdir)
            self.folder = Path(tempfile.mkdtemp(dir=self.workdir, prefix='run-'))
            self._held = open(self.folder / '.held', 'w')
            fcntl.flock(self._held, fcntl.LOCK_EX)
        self.copy = committed_copy(self.target, commit, self.folder / 'project')
        self.home, self.tmp = self.folder / 'home', self.folder / 'tmp'
        self.home.mkdir(); self.tmp.mkdir()
        self.refused = _view_refusal()
        self.offline = _network_isolation() if self.refused else True
        self.masks = [] if self.refused else hidden()
        self.started, self.commands = [], []
        self.limitations = ([f'not isolated: {self.refused}', 'the filesystem outside the copy is readable',
                             'processes run as the invoking user'] if self.refused else
                            ['folders of projects EAOS does not know are readable',
                             "commands with the network reach the apps other projects run on this computer"])
        self.limitations += ['the processor and memory are shared with the checks of other projects',
                             "the person's own assistant runs outside this sandbox"]
        if not self.offline: self.limitations.append('network not isolated')
        self._record()

    def environment(self, extra=None):
        """PATH, a temporary HOME and TMPDIR, LANG, the names the owner allowed, and `extra`: values the run itself chose
        (a local database address, tool locations), never taken from this process's environment. TMPDIR keeps what
        the project's own tests and tools write to a temporary folder inside the run's, removed with it."""
        env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'HOME': str(self.home), 'TMPDIR': str(self.tmp),
               'LANG': os.environ.get('LANG', 'C.UTF-8')}
        env.update({name: os.environ[name] for name in self.allowed if name in os.environ})
        env.update({name: str(value) for name, value in (extra or {}).items()})
        return env

    def _record(self):
        record = {'schema_version': 1, 'backend': 'unshare' if self.offline else 'process', 'own_view': not self.refused,
                  'commands': self.commands, 'limitations': sorted(set(self.limitations))}
        (self.workdir / 'sandbox-run.json').write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')

    def _note(self, argv, network):
        if network and self.offline:
            self.limitations.append(f"network allowed for: {' '.join(map(str, argv))[:120]}")

    def _inside(self, cwd):
        """A working folder inside the copy (cwd is relative to it); never outside."""
        where = (self.copy / cwd if cwd else self.copy).resolve()
        if where != self.copy.resolve() and self.copy.resolve() not in where.parents:
            raise AuthorizationError(f'{cwd} is outside the copy')
        return where

    def _command(self, argv, env, cwd, network):
        """(argv, folder) a command starts as: through the launcher of its own view where it works (with no network
        unless `network`), which then moves to `cwd`; as it is elsewhere."""
        if self.refused: return (argv if network or not self.offline else [*self.offline, *argv]), cwd
        from .toolchain import home
        base = [(str(self.folder), False), (str(home()), True)]
        inside = [Path(os.path.realpath(path)) for path, _ in base]
        keeps = base + [(path, ro) for path, ro in named(argv, env) if not _within(Path(os.path.realpath(path)), inside)]
        return [*_launcher({'offline': not network, 'cwd': str(cwd), 'mounts': mounts(self.masks, keeps)}), *argv], self.folder

    def run(self, argv, timeout=60, network=False, cwd=None, env=None):
        """(exit code, stdout, stderr) of argv run in the copy (or `cwd` inside it); with no network unless `network`."""
        argv = [str(part) for part in argv]
        self._note(argv, network)
        environment = self.environment(env)
        full, where = self._command(argv, environment, self._inside(cwd), network)
        started = time.monotonic()
        process = subprocess.Popen(full, cwd=where, env=environment, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, start_new_session=True)
        from .assistants.command import communicate
        try:
            out, err = communicate(process, timeout)
        except subprocess.TimeoutExpired:
            self._kill(process)
            out, err = process.communicate()
            err += f'\nstopped after {timeout}s'
        except BaseException:
            self._kill(process)
            raise
        self.commands.append({'argv': argv, 'exit': process.returncode, 'seconds': round(time.monotonic() - started, 2)})
        self._record()
        return process.returncode, out, err

    def start(self, argv, port, health_path='/health', timeout=30, cwd=None, env=None):
        """Start a service in the copy and return once http://127.0.0.1:port<health_path> answers 200, from the service
        itself (_listens): another program answering on that port does not count."""
        argv = [str(part) for part in argv]
        self.limitations.append(f"network not isolated for the started service: {' '.join(argv)[:120]}")
        log = open(self.workdir / f'service-{len(self.started)}.log', 'w', encoding='utf-8')
        environment = self.environment(env)
        full, where = self._command(argv, environment, self._inside(cwd), True)
        process = subprocess.Popen(full, cwd=where, env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        self.started.append((process, argv, time.monotonic(), log))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            from .assistants.command import check_cancelled
            check_cancelled()
            if process.poll() is not None:
                self.stop()
                raise RuntimeError(f'{argv[0]} exited with {process.returncode} before answering; see {log.name}; '
                                   f'it said: {_tail(log.name)}')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}{health_path}', timeout=2) as response:
                    if response.status == 200 and _listens(port, process.pid) is not False: return
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(0.3)
        self.stop()
        raise RuntimeError(f'no 200 from http://127.0.0.1:{port}{health_path} within {timeout}s; see {log.name}; '
                           f'it said: {_tail(log.name)}')

    @staticmethod
    def _kill(process):
        """Terminate the whole process group, then kill what is left."""
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
        except (ProcessLookupError, PermissionError):
            return
        except subprocess.TimeoutExpired:
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: return
            process.wait()

    def stop(self):
        """Stop every started service (its whole process group) and record how each ended."""
        for process, argv, started, log in self.started:
            self._kill(process)
            log.close()
            self.commands.append({'argv': argv, 'exit': process.returncode if process.returncode is not None else -1,
                                  'seconds': round(time.monotonic() - started, 2)})
        self.started = []
        self._record()

    def dispose(self):
        """Stop what runs and remove the run's folder (copy, HOME, TMPDIR): a run leaves its records, not its disk.
        (A lock run's copy with installed packages is 600 MB; three runs had kept 1.9 GB.)"""
        self.stop()
        shutil.rmtree(self.folder, ignore_errors=True)
        self._held.close()


@contextmanager
def _gate(workdir):
    with open(Path(workdir) / '.sweep', 'a') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        yield


def sweep(workdir):
    """_sweep under the gate a new run makes its folder under (eaos clean): the bytes freed."""
    with _gate(workdir): return _sweep(Path(workdir))


def _size(folder):
    return sum(f.stat().st_size for f in folder.rglob('*') if f.is_file() and not f.is_symlink())


def _sweep(workdir):
    """Remove every folder in `workdir` no live run holds: what a run stopped or killed before dispose() left (a
    sandbox folder holds nothing but runs; 170 of them had kept 6.2 GB). The bytes freed."""
    freed = 0
    for folder in (entry for entry in workdir.iterdir() if entry.is_dir()):
        try:
            with open(folder / '.held', 'a') as held:
                fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
                freed += _size(folder)
                shutil.rmtree(folder, ignore_errors=True)
        except BlockingIOError:
            continue
        except OSError:
            freed += _size(folder)
            shutil.rmtree(folder, ignore_errors=True)
    return freed
