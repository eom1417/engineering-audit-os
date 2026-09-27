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
import secrets
from pathlib import Path

from .sandbox import AuthorizationError, Sandbox, head

BROWSERS = Path(os.environ.get('PLAYWRIGHT_BROWSERS_PATH') or Path.home() / '.cache/ms-playwright')


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

    def __init__(self, target, runtime, stage):
        self.runtime = Path(runtime)
        self.profile = load_profile(runtime)
        self.sandbox = Sandbox(target, self.runtime / 'authorization.json', self.runtime / 'sandbox', stage)
        self.commit = head(target)
        self.log = []

    def extra(self):
        """The run's own values and the tools' locations; never an owner secret (those pass by name only)."""
        from .toolchain import home
        if not hasattr(self, '_extra'):
            self._extra = {**{k: str(v) for k, v in (self.profile.get('env') or {}).items()},
                           'PATH': f"{home() / 'bin'}{os.pathsep}{os.environ.get('PATH', '/usr/bin:/bin')}",
                           'NODE_PATH': str(home() / 'node/node_modules'), 'PLAYWRIGHT_BROWSERS_PATH': str(BROWSERS)}
            self._extra.setdefault('AUTH_SECRET', secrets.token_urlsafe(48))   # generated for this run, never the owner's
        return self._extra

    def run(self, argv, timeout=900, network=True, env=None):
        """(exit, stdout, stderr) of argv in the app folder of the copy, with the run's environment."""
        result = self.sandbox.run(argv, timeout=timeout, network=network, cwd=self.profile.get('app') or None,
                                  env={**self.extra(), **(env or {})})
        self.log.append({'argv': [str(a) for a in argv], 'exit': result[0], 'tail': (result[1] + result[2])[-2000:]})
        return result

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
        """Stop the project and remove its copy; the run's records stay in the runtime folder."""
        self.sandbox.dispose()

    def record(self, name):
        (self.runtime / name).write_text(json.dumps({'commit': self.commit, 'commands': self.log}, ensure_ascii=False, indent=1) + '\n',
                                         encoding='utf-8')
