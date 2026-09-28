"""A project run for the execution stages, from a declared run profile, inside eaos.sandbox.Sandbox.

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
original, is not done (eaos/execute.py).

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
from pathlib import Path

from .sandbox import AuthorizationError, Sandbox, head



def load_profile(runtime):
    """The run profile, keeping its contract, or an error naming what is wrong."""
    from .artifact_contracts import contracts, validate
    path = Path(runtime) / 'run.json'
    if not path.is_file(): raise AuthorizationError(f'run profile: {path} is missing; it declares how the project runs')
    profile = json.loads(path.read_text(encoding='utf-8'))
    problems = validate(profile, contracts()['run-profile'])
    if problems: raise AuthorizationError(f'run profile: {problems[0]}')
    return profile


class LiveRun:
    """One authorised run: install, build, prepare and start the project in a sandbox copy, then stop it."""

    # The keys a profile's `baseline` may override: the load baseline runs the build, not the dev server.
    BASELINE_KEYS = ('install', 'build', 'prepare', 'start', 'port', 'health', 'env', 'seed', 'start_timeout')

    def __init__(self, target, runtime, stage, mode='lock'):
        self.runtime = Path(runtime)
        self.profile = load_profile(runtime)
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
        """The run's own PostgreSQL (eaos/local_db.py), started on first use, when the profile declares one."""
        database = self.profile.get('database') or {}
        # A value naming {database_url} needs a database, declared or not.
        if database.get('kind') != 'postgres' and any('{database_url}' in str(v) for v in (self.profile.get('env') or {}).values()):
            database = {'kind': 'postgres', 'name': 'app'}
        if database.get('kind') != 'postgres': return None
        if not hasattr(self, '_database'):
            from .local_db import LocalPostgres
            self._database = LocalPostgres(self.runtime)
            self._database_url = self._database.create(database['name'])
        return self._database_url

    def extra(self):
        """The run's own values and the tools' locations; never an owner secret (those pass by name only).
        `{database_url}` in a value is the run's own database."""
        from .toolchain import browsers, home
        if not hasattr(self, '_extra'):
            url = self.database_url()
            env = self.profile.get('env') or {}
            folder = None
            if any('{run_dir}' in str(v) for v in env.values()):
                folder = self.runtime / 'run-data'      # the run's own folder outside the app: backups, uploads
                folder.mkdir(parents=True, exist_ok=True)
            fill = lambda value: (str(value).replace('{database_url}', url) if url else str(value)).replace('{run_dir}', str(folder))
            self._extra = {**{k: fill(v) for k, v in (self.profile.get('env') or {}).items()},
                           'PATH': f"{home() / 'bin'}{os.pathsep}{os.environ.get('PATH', '/usr/bin:/bin')}",
                           'NODE_PATH': str(home() / 'node/node_modules'), 'PLAYWRIGHT_BROWSERS_PATH': str(browsers())}
            self._extra.setdefault('AUTH_SECRET', secrets.token_urlsafe(48))   # generated for this run, never the owner's
        return self._extra

    def run(self, argv, timeout=900, network=True, env=None):
        """(exit, stdout, stderr) of argv in the app folder of the copy, with the run's environment."""
        result = self.sandbox.run(argv, timeout=timeout, network=network, cwd=self.profile.get('app') or None,
                                  env={**self.extra(), **(env or {})})
        self.log.append({'argv': [str(a) for a in argv], 'exit': result[0], 'tail': (result[1] + result[2])[-2000:]})
        return result

    def seed(self, base, storage_state=None):
        """Run the profile's seed commands against the started app. A seed may print, as its last line, a JSON
        object of fixture values it created ({"E2E_PROFILEID": "..."}): they join the run's environment, so the
        lock opens the screens that need them. Stops at the first seed that fails, with its output."""
        env = {'BASE_URL': base, **({'EAOS_STORAGE_STATE': str(storage_state)} if storage_state else {})}
        for argv in self.profile.get('seed') or []:
            code, out, err = self.run(argv, env=env)
            if code: raise RuntimeError(f"seed failed ({' '.join(map(str, argv))}): {(out + err)[-1500:]}")
            self.seed_output = (out + err)[-3000:]
            for line in reversed(out.strip().splitlines()):     # the last JSON object printed, wherever it is
                try: printed = json.loads(line)
                except ValueError: continue
                if not isinstance(printed, dict): continue
                fixtures = {k: str(v) for k, v in printed.items() if re.fullmatch(r'E2E_[A-Z0-9_]+', str(k))}
                if not fixtures: continue
                self.extra().update(fixtures)
                self.fixtures.update(fixtures)
                break
        return self.fixtures

    def setup(self):
        """Install, build and prepare; stops at the first command that fails, with its output."""
        for phase in ('install', 'build', 'prepare'):
            for argv in self.profile.get(phase) or []:
                code, out, err = self.run(argv)
                if code != 0:
                    raise RuntimeError(f"{phase} failed ({' '.join(map(str, argv))}): {(out + err)[-1500:]}")

    def start(self):
        """Start the project and return its address once the health route answers."""
        self.sandbox.start(self.profile['start'], self.profile['port'], self.profile.get('health', '/'),
                           timeout=self.profile.get('start_timeout', 90), cwd=self.profile.get('app') or None, env=self.extra())
        return f"http://127.0.0.1:{self.profile['port']}"

    def stop(self):
        """Stop the project and remove its copy, and stop the run's database (its data stays for the next
        step); the run's records stay in the runtime folder."""
        self.sandbox.dispose()
        if hasattr(self, '_database'): self._database.stop()

    def record(self, name):
        (self.runtime / name).parent.mkdir(parents=True, exist_ok=True)
        (self.runtime / name).write_text(json.dumps({'commit': self.commit, 'commands': self.log}, ensure_ascii=False, indent=1) + '\n',
                                         encoding='utf-8')
