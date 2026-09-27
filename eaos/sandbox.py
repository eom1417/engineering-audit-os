"""Run a project's own code: only with the owner's authorization, in a copy, without secrets.

The execution stages (S05's run half, S08-S14) need the project running. Nothing here starts before
refusal() finds nothing wrong with authorization.json: it must keep its contract, not be expired, name
the stage, and, when a target is given, name the commit the target is at. The project itself is never
touched: every command runs in a copy made by eaos.verify.isolated_copy, as its own process group, with
an environment of PATH, a temporary HOME, LANG, and the names the owner listed in env_allow.

Where the kernel allows it (unshare -rn), a command runs with no network, so a test suite cannot reach
anything outside. A started service must answer the host, so it keeps the network; that, and every other
thing this sandbox could not isolate, is written to sandbox-run.json -> limitations, never implied.
"""
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path


class AuthorizationError(Exception):
    """The owner's authorization does not allow this run."""


def refusal(path, stage, commit=None):
    """Why authorization.json at `path` does not allow `stage` (at `commit`), or '' when it does."""
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
        return f"authorization: granted for commit {grant['commit'][:12]}, but the project is at {commit[:12]}"
    return ''


def head(target):
    done = subprocess.run(['git', '-C', str(target), 'rev-parse', 'HEAD'], capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else ''


def _network_isolation():
    """The prefix that runs a command with no network, or () where the kernel does not allow it."""
    unshare = shutil.which('unshare')
    if not unshare: return ()
    try:
        done = subprocess.run([unshare, '-rn', 'true'], capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return ()
    return (unshare, '-rn') if done.returncode == 0 else ()


class Sandbox:
    def __init__(self, target, authorization, workdir, stage):
        self.target, self.workdir, self.stage = Path(target), Path(workdir), stage
        commit = head(self.target)
        if not commit:
            raise AuthorizationError(f'{self.target} is not a git checkout: an authorization names a commit')
        reason = refusal(authorization, stage, commit)
        if reason: raise AuthorizationError(reason)
        self.allowed = json.loads(Path(authorization).read_text(encoding='utf-8'))['env_allow']
        self.workdir.mkdir(parents=True, exist_ok=True)
        from .verify import isolated_copy
        self.copy = isolated_copy(self.target, Path(tempfile.mkdtemp(dir=self.workdir, prefix='copy-')) / 'project')
        self.home = Path(tempfile.mkdtemp(dir=self.workdir, prefix='home-'))
        self.offline = _network_isolation()
        self.started, self.commands = [], []
        self.limitations = ['the filesystem outside the copy is readable', 'processes run as the invoking user']
        if not self.offline: self.limitations.append('network not isolated')
        self._record()

    def environment(self, extra=None):
        """PATH, a temporary HOME, LANG, the names the owner allowed, and `extra`: values the run itself chose
        (a local database address, tool locations), never taken from this process's environment."""
        env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'HOME': str(self.home),
               'LANG': os.environ.get('LANG', 'C.UTF-8')}
        env.update({name: os.environ[name] for name in self.allowed if name in os.environ})
        env.update({name: str(value) for name, value in (extra or {}).items()})
        return env

    def _record(self):
        record = {'schema_version': 1, 'backend': 'unshare' if self.offline else 'process',
                  'commands': self.commands, 'limitations': sorted(set(self.limitations))}
        (self.workdir / 'sandbox-run.json').write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')

    def _note(self, argv, network):
        if network and self.offline:
            self.limitations.append(f"network allowed for: {' '.join(map(str, argv))[:120]}")

    def _inside(self, cwd):
        """A working folder inside the copy (cwd is relative to it); never outside."""
        where = (self.copy / cwd).resolve() if cwd else self.copy
        if where != self.copy.resolve() and self.copy.resolve() not in where.parents:
            raise AuthorizationError(f'{cwd} is outside the copy')
        return where

    def run(self, argv, timeout=60, network=False, cwd=None, env=None):
        """(exit code, stdout, stderr) of argv run in the copy (or `cwd` inside it); with no network unless `network`."""
        argv = [str(part) for part in argv]
        self._note(argv, network)
        full = argv if network or not self.offline else [*self.offline, *argv]
        started = time.monotonic()
        process = subprocess.Popen(full, cwd=self._inside(cwd), env=self.environment(env), stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            out, err = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._kill(process)
            out, err = process.communicate()
            err += f'\nstopped after {timeout}s'
        self.commands.append({'argv': argv, 'exit': process.returncode, 'seconds': round(time.monotonic() - started, 2)})
        self._record()
        return process.returncode, out, err

    def start(self, argv, port, health_path='/health', timeout=30, cwd=None, env=None):
        """Start a service in the copy and return once http://127.0.0.1:port<health_path> answers 200."""
        argv = [str(part) for part in argv]
        self.limitations.append(f"network not isolated for the started service: {' '.join(argv)[:120]}")
        log = open(self.workdir / f'service-{len(self.started)}.log', 'w', encoding='utf-8')
        process = subprocess.Popen(argv, cwd=self._inside(cwd), env=self.environment(env), stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        self.started.append((process, argv, time.monotonic(), log))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                self.stop()
                raise RuntimeError(f'{argv[0]} exited with {process.returncode} before answering; see {log.name}')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}{health_path}', timeout=2) as response:
                    if response.status == 200: return
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(0.3)
        self.stop()
        raise RuntimeError(f'no 200 from http://127.0.0.1:{port}{health_path} within {timeout}s; see {log.name}')

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
