"""A project run for the execution stages, from a declared run profile, inside eaos.live.isolation.sandbox.Sandbox.

The profile (<runtime>/run.json, contract schemas/artifacts/run-profile.schema.json) is data the owner can read
and correct: how the project installs, builds, starts and signs a user in. Nothing here guesses a command.

    {"schema_version": 1, "app": "app",
     "install": [["npm", "ci", "--ignore-scripts"]],
     "build":   [["npm", "run", "build"]],
     "prepare": [["node", "scripts/provision-runtime-role.mjs"]],
     "start":   ["node", "dist-server/main.mjs"], "port": 5188, "health": "/api/health",
     "env": {"NODE_ENV": "development", "CO_LOCAL_ONLY": "1"},
     "sign_in": ["node", "<runtime>/sign-in.mjs"],
     "checks":  [["npm", "run", "typecheck"], ["npm", "run", "lint"], ["npm", "test"]]}

`checks` are the project's own gates: a card whose change makes one of them fail, where it passed on the
original, is not done (eaos/journeys/fix/execute.py).

`env` holds only values the run itself chooses (a local database address, a key generated for the run); the
owner's secrets never appear in it, and the sandbox passes on nothing else but the names the authorization
lists. Commands that need the local database or the registry run with the network; every other one without.
The browser the lock drives reaches loopback only: every other host is refused, so a run never touches
production or a third party.
"""
import json
import os
import re
import secrets
import shutil
import socket
from pathlib import Path

from ..isolation.sandbox import AuthorizationError, Sandbox, head



def load_profile(runtime):
    """The run profile, keeping its contract, or an error naming what is wrong."""
    from ...core.contracts.artifact_rules import contracts, validate
    path = Path(runtime) / 'run.json'
    if not path.is_file(): raise AuthorizationError(f'run profile: {path} is missing; it declares how the project runs')
    profile = json.loads(path.read_text(encoding='utf-8'))
    problems = validate(profile, contracts()['run-profile'])
    if problems: raise AuthorizationError(f'run profile: {problems[0]}')
    return profile


def _printed_fixtures(out):
    """The E2E_* values of the last JSON object a seed printed that holds any, wherever it is; {} when none."""
    for line in reversed(out.strip().splitlines()):
        try: printed = json.loads(line)
        except ValueError: continue
        fixtures = {k: str(v) for k, v in printed.items() if re.fullmatch(r'E2E_[A-Z0-9_]+', str(k))} if isinstance(printed, dict) else {}
        if fixtures: return fixtures
    return {}


def kinds_folder(state):
    """Where the seed beside session file `state` saves a session per kind of user (eaos/live/access/roles.py): <kind>.json."""
    return Path(state).parent / 'sessions'


def _unfrozen(argv):
    """The same install without holding to the lockfile, when it held to it: `npm ci` and `--frozen-lockfile` refuse a
    lockfile older than its package.json (the corpus' Supabase and Next.js apps), where `npm install` brings it up to
    date in the run's own copy."""
    argv = [str(part) for part in argv]
    if argv[:2] == ['npm', 'ci']: return ['npm', 'install', *argv[2:]]
    if '--frozen-lockfile' not in argv: return None
    loose = [part for part in argv if part != '--frozen-lockfile']
    return loose + (['--no-frozen-lockfile'] if 'pnpm' in argv else [])


class LiveRun:
    """One authorised run: install, build, prepare and start the project in a sandbox copy, then stop it."""

    # The keys a profile's `baseline` may override: the load baseline runs the build, not the dev server, and may run it
    # from another folder (`app`: a program whose server sits at the root, its pages in a folder it builds).
    BASELINE_KEYS = ('app', 'install', 'build', 'prepare', 'start', 'port', 'health', 'env', 'seed', 'start_timeout')

    def __init__(self, target, runtime, stage, mode='lock', apart=''):
        self.runtime = Path(runtime)
        # `apart` names a run that shares no data with the others (the project's tests): its own empty database and data
        # folder, so it runs beside them
        self.apart = apart
        self.profile = load_profile(runtime)
        if 'AUTH_SECRET' not in (self.profile.get('env') or {}):
            from .profile import write_profile
            self.profile.setdefault('env', {})['AUTH_SECRET'] = secrets.token_urlsafe(48)
            write_profile(runtime, self.profile)
        self.auth_secret = self.profile['env']['AUTH_SECRET']
        if mode == 'baseline':
            override = self.profile.get('baseline') or {}
            for key in self.BASELINE_KEYS:
                if key in override: self.profile[key] = override[key]
            # The load test opens the pages without signing in: the lock's sign-in is not the production run's.
            self.profile['seed'] = override.get('seed') or []
        self.sandbox = Sandbox(target, self.runtime / 'authorization.json', self.runtime / 'sandbox', stage)
        self.commit = head(target)
        self.log = []
        self.fixtures = {}

    def database_url(self):
        """The run's own PostgreSQL (eaos/core/system/local_db.py), started on first use, when the profile declares one."""
        database = self.profile.get('database') or {}
        # A value naming {database_url} needs a database, declared or not.
        if database.get('kind') != 'postgres' and any('{database_url}' in str(v) for v in (self.profile.get('env') or {}).values()):
            database = {'kind': 'postgres', 'name': 'app'}
        if database.get('kind') != 'postgres': return None
        if not hasattr(self, '_database'):
            from ...core.system.local_db import LocalPostgres
            self._database = LocalPostgres(self.runtime)
            self._database_url = self._database.create('_'.join(filter(None, (database['name'], self.apart))))
        return self._database_url

    def run_env(self):
        """The run's own values and the tools' locations; never an owner secret (those pass by name only).
        `{database_url}` in a value is the run's own database."""
        from ...core.toolchain import browsers, home
        if not hasattr(self, '_extra'):
            url = self.database_url()
            env = self.profile.get('env') or {}
            folder = None
            if any('{run_dir}' in str(v) for v in env.values()):
                # the run's own folder outside the app: backups, uploads
                folder = self.runtime / '-'.join(filter(None, ('run-data', self.apart)))
                folder.mkdir(parents=True, exist_ok=True)
            mail = str(self._mail_port())
            fill = lambda value: (str(value).replace('{database_url}', url) if url else str(value)).replace('{run_dir}', str(folder)).replace('{mail_port}', mail)
            self._extra = {**{k: self._frozen(k, fill(v)) for k, v in (self.profile.get('env') or {}).items()},
                           'PATH': f"{home() / 'bin'}{os.pathsep}{os.environ.get('PATH', '/usr/bin:/bin')}",
                           'NODE_PATH': str(home() / 'node/node_modules'), 'PLAYWRIGHT_BROWSERS_PATH': str(browsers()),
                           # the one copy of the tools, for an app that is EAOS itself: it installed 611 MB of its own
                           'EAOS_ENGINE_TOOLS': str(home()),
                           # EAOS's own Playwright, by its path: Node finds the app's own first (another version, no browsers)
                           'EAOS_PLAYWRIGHT': str(home() / 'node/node_modules/playwright')}
            self._extra.setdefault('AUTH_SECRET', getattr(self, 'auth_secret', None) or secrets.token_urlsafe(48))
        return self._extra

    def _mail_port(self):
        """The port the app sends its mail to ({mail_port}, eaos/live/app/setup.py MAIL_NAMES): the run's Mailpit, started on
        first use, so a code or a link the app e-mails is shown beside the sign-in page and never leaves this computer;
        9 (nobody answers) when the app sends none or Mailpit is not installed."""
        from ...core.toolchain import home
        binary = home() / 'bin/mailpit'
        if not hasattr(self, '_mailpit') and binary.exists() and any('{mail_port}' in str(v) for v in (self.profile.get('env') or {}).values()):
            import subprocess
            from ...core.system.local_db import free_port
            smtp, page = free_port(), free_port()
            self._mailpit = smtp, f'http://127.0.0.1:{page}', subprocess.Popen(  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- mailpit at its pin, a list argv on free local ports, no shell
                [str(binary), '--smtp', f'127.0.0.1:{smtp}', '--listen', f'127.0.0.1:{page}', '--quiet'],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return self._mailpit[0] if hasattr(self, '_mailpit') else 9

    def mail(self):
        """The address of the run's Mailpit (its page and API), or None when the app sends no mail there."""
        return self._mailpit[1] if hasattr(self, '_mailpit') else None

    def _outside(self, value):
        """A folder outside the project and the run that the app reads (its data), named by an absolute path."""
        path = Path(str(value))
        return path.is_absolute() and path.is_dir() and self.runtime.resolve() not in path.resolve().parents

    def _frozen(self, name, value):
        """The copy of such a folder kept when the screens were recorded (freeze), so every later run reads the data
        they were recorded on; the folder itself when none was kept."""
        copy = self.runtime / 'frozen' / name
        return str(copy) if self._outside(value) and copy.is_dir() else value

    def freeze(self):
        """Keep a copy of every folder outside the project the app reads, for this recording and every run after it:
        a live folder changes under the runs (EAOS's Studio reads the report a batch rewrites), and a screen compared
        on other data differs whatever the change (EAOS on itself, 2026-10-13: every card of a batch failed so)."""
        for name, value in (self.profile.get('env') or {}).items():
            if not self._outside(value): continue
            copy = self.runtime / 'frozen' / name
            shutil.rmtree(copy, ignore_errors=True)
            shutil.copytree(value, copy)
        self.__dict__.pop('_extra', None)

    def run(self, argv, timeout=900, network=True, env=None, at_root=False):
        """(exit, stdout, stderr) of argv in the app folder of the copy (its root with `at_root`), with the run's environment."""
        result = self.sandbox.run(argv, timeout=timeout, network=network, cwd=None if at_root else self.profile.get('app') or None,
                                  env={**self.run_env(), **(env or {})})
        self.log.append({'argv': [str(a) for a in argv], 'exit': result[0], 'tail': (result[1] + result[2])[-6000:]})
        return result

    def seed(self, base, storage_state=None):
        """Run the profile's seed commands against the started app. A seed may print, as its last line, a JSON
        object of fixture values it created ({"E2E_PROFILEID": "..."}): they join the run's environment, so the
        lock opens the screens that need them. A session per kind of user (eaos/live/access/roles.py) goes in EAOS_SESSIONS_DIR,
        <kind>.json, made again at each seed. Stops at the first seed that fails, with its output."""
        env = {'BASE_URL': base}
        if storage_state:
            folder = kinds_folder(storage_state)
            shutil.rmtree(folder, ignore_errors=True)
            folder.mkdir(parents=True)
            env.update(EAOS_STORAGE_STATE=str(storage_state), EAOS_SESSIONS_DIR=str(folder))
        for argv in self.profile.get('seed') or []:
            code, out, err = self.run(argv, env=env)
            if code: raise RuntimeError(f"seed failed ({' '.join(map(str, argv))}): {(out + err)[-1500:]}")
            self.seed_output = (out + err)[-3000:]
            fixtures = _printed_fixtures(out)
            self.run_env().update(fixtures)
            self.fixtures.update(fixtures)
        for made in [storage_state, *kinds_folder(storage_state).glob('*.json')] if storage_state else []:
            if Path(made).is_file(): Path(made).chmod(0o600)            # a signed-in session: its owner's alone
        return self.fixtures

    def setup(self):
        """Install, build and prepare; stops at the first command that fails, with its output."""
        for phase in ('install', 'build', 'prepare'):
            for argv in self.profile.get(phase) or []:
                if _test_browsers(argv): continue
                code, out, err = self.run(argv)
                if code != 0 and phase == 'install' and _unfrozen(argv):
                    code, out, err = self.run(_unfrozen(argv))        # a lockfile behind its package.json: install as a person would
                if code != 0:
                    raise RuntimeError(f"{phase} failed ({' '.join(map(str, argv))}): {(out + err)[-1500:]}")

    def start(self):
        """Start the project and return its address once the health route answers. A port another program holds now (the
        profile chose it free once) is given up for a free one, in the command and in every value naming it."""
        port = self.profile['port']
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try: probe.bind(('127.0.0.1', port))
            except OSError:
                probe.bind(('127.0.0.1', 0))
                port = probe.getsockname()[1]
        if port != self.profile['port']:
            swap = lambda text: re.sub(rf"(?<![\w.]){self.profile['port']}(?!\w)", str(port), str(text))
            self.profile.update(port=port, start=[swap(part) for part in self.profile['start']],
                                env={name: swap(value) for name, value in (self.profile.get('env') or {}).items()})
            self.__dict__.pop('_extra', None)
        base = f"http://127.0.0.1:{self.profile['port']}"
        self.sandbox.start(self.profile['start'], base + self.profile.get('health', '/'),
                           timeout=self.profile.get('start_timeout', 90), cwd=self.profile.get('app') or None, env=self.run_env())
        return base

    def stop(self):
        """Stop the project and remove its copy, leave the run's database (stopped once no other run is on it, its data
        kept for the next step) and stop its Mailpit (its mail with it); the run's records stay in the runtime folder."""
        self.sandbox.dispose()
        if hasattr(self, '_database'): self._database.stop()
        if hasattr(self, '_mailpit'):
            self._mailpit[2].terminate()
            self._mailpit[2].wait(10)

    def record(self, name):
        (self.runtime / name).parent.mkdir(parents=True, exist_ok=True)
        (self.runtime / name).write_text(json.dumps({'commit': self.commit, 'commands': self.log}, ensure_ascii=False, indent=1) + '\n',
                                         encoding='utf-8')


def _test_browsers(argv):
    """`playwright install` (the app's own test browsers): never needed to run the app, which EAOS pictures with its own
    browsers, and their shared folder is read only in the isolated run (a real build: the setup stopped on it)."""
    words = [str(word) for word in argv]
    return any(word.endswith('playwright') for word in words) and 'install' in words
