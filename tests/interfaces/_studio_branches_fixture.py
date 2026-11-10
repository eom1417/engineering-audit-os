"""Shared by the branch-control tests: git helpers and a repository with its workspace."""
import os
import subprocess
from pathlib import Path
from eaos.interfaces import runs as actions
from tests.shared_fixture import Workspace


def git(folder, *args, env=None):
    done = subprocess.run(['git', '-C', str(folder), *args], capture_output=True, text=True,
                          env={**os.environ, 'GIT_AUTHOR_NAME': 'Person', 'GIT_AUTHOR_EMAIL': 'person@example.com',
                               'GIT_COMMITTER_NAME': 'Person', 'GIT_COMMITTER_EMAIL': 'person@example.com',
                               **(env or {})})
    if done.returncode: raise AssertionError(f'git {args}: {done.stderr}')
    return done.stdout.strip()


EAOS = {'GIT_AUTHOR_NAME': 'EAOS', 'GIT_AUTHOR_EMAIL': 'eaos@localhost', 'GIT_COMMITTER_NAME': 'EAOS',
        'GIT_COMMITTER_EMAIL': 'eaos@localhost'}


def commit(folder, path, text, message, env=None):
    (Path(folder) / path).parent.mkdir(parents=True, exist_ok=True)
    (Path(folder) / path).write_text(text, encoding='utf-8')
    git(folder, 'add', path)
    git(folder, 'commit', '-q', '-m', message, env=env)
    return git(folder, 'rev-parse', 'HEAD')


class Repo(Workspace):
    """main and develop with a remote origin, a tool-owned work branch (provenance), a human branch named like a tool's.
    """

    def setUp(self):
        super().setUp()
        self.base = Path(self.tmp)
        saved = {k: os.environ.get(k) for k in ('EAOS_HOME', 'EAOS_OUTPUT')}
        self.addCleanup(lambda: [os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
                                 for k, v in saved.items()])
        os.environ.update(EAOS_HOME=str(self.base / 'home'), EAOS_OUTPUT=str(self.base / 'out'))
        self.origin = self.base / 'origin.git'
        git(self.base, 'init', '-q', '--bare', '-b', 'main', str(self.origin))
        self.project = self.base / 'project'
        self.project.mkdir()
        git(self.project, 'init', '-q', '-b', 'main')
        commit(self.project, 'app.py', 'print(1)\n', 'first')
        git(self.project, 'branch', 'develop')
        git(self.project, 'remote', 'add', 'origin', str(self.origin))
        git(self.project, 'push', '-q', 'origin', 'main', 'develop')
        git(self.project, 'remote', 'set-head', 'origin', 'main')
        git(self.project, 'switch', '-q', 'develop')
        git(self.project, 'switch', '-q', '-c', 'eaos/task-1')
        self.work_tip = commit(self.project, 'feature.py', 'x = 1\n', 'work', env=EAOS)
        git(self.project, 'switch', '-q', '-c', 'eaos/not-ours', 'develop')
        commit(self.project, 'other.py', 'y = 2\n', 'human work under a tool-like name')
        git(self.project, 'switch', '-q', 'develop')
        self.app = actions.Actions(self.project, port=8765, adapters={})
        self.addCleanup(self.app.close)
        self.app.branches.record('eaos/task-1', kind='task', base='develop',
                                 base_commit=git(self.project, 'rev-parse', 'develop'),
                                 tip=self.work_tip)

    def headers(self, **extra):
        return {'X-EAOS-Token': self.app.token, 'X-EAOS-CSRF': self.app.csrf, 'Origin': 'http://127.0.0.1:8765',
                'Host': '127.0.0.1:8765', **extra}

    def post(self, path, body=None, headers=None):
        return self.app.handle('POST', path, headers or self.headers(), body or {})

    def get(self, path):
        return self.app.handle('GET', path, self.headers(), None)

    def row(self, name, kind='local'):
        status, inventory = self.get('/api/branches')
        self.assertEqual(status, 200, inventory)
        return next((r for r in inventory['branches'] if r['name'] == name and r['kind'] == kind), None)
