"""NS17.T5 — run a project's code only with the owner's authorization, in a copy, without secrets.

Interface this task must provide:
    from eaos.sandbox import Sandbox, AuthorizationError
    box = Sandbox(target, authorization, workdir, stage)
      target         the project (never modified: the sandbox runs a copy made by eaos.verify.isolated_copy)
      authorization  path to authorization.json (schemas/artifacts/authorization.schema.json)
      stage          e.g. "S05"; raises AuthorizationError if the file is missing, invalid, expired
                     (ISO date in "expires" before today), for another commit than the target's HEAD,
                     or does not list the stage
    box.start(argv, port, health_path="/health", timeout=30)   runs argv inside the copy; returns once
                                                               http://127.0.0.1:port/health answers 200
    box.run(argv, timeout=60) -> (exit_code, stdout, stderr)
    box.stop()                                                 kills the whole process group
    workdir/sandbox-run.json                                   schemas/artifacts/sandbox-run.schema.json
    The process environment holds PATH, HOME (a temporary directory), LANG, and the names in env_allow; nothing else.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = Path(__file__).parent / 'fixtures/sandbox-app'
sys.path.insert(0, str(ROOT / 'tools'))


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.project = self.tmp / 'project'
        shutil.copytree(APP, self.project)
        git = lambda *a: subprocess.run(['git', '-C', str(self.project), *a], check=True, capture_output=True, text=True)
        git('init', '-q'); git('add', '.')
        git('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'app')
        self.commit = git('rev-parse', 'HEAD').stdout.strip()
        self.workdir = self.tmp / 'work'; self.workdir.mkdir()
        os.environ['EAOS_ACCEPTANCE_SECRET_TOKEN'] = 'never-leaks'
        os.environ['EAOS_ACCEPTANCE_ALLOWED'] = 'visible'

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def authorization(self, **change):
        record = {'schema_version': 1, 'project': 'fixture', 'commit': self.commit, 'granted_by': 'acceptance test',
                  'stages': ['S05'], 'env_allow': ['EAOS_ACCEPTANCE_ALLOWED'],
                  'expires': (date.today() + timedelta(days=1)).isoformat(), **change}
        path = self.tmp / 'authorization.json'
        path.write_text(json.dumps(record))
        return path

    def test_no_run_without_a_valid_authorization(self):
        from eaos.sandbox import Sandbox, AuthorizationError
        for bad in ({'commit': '0' * 40}, {'stages': ['S10']}, {'expires': (date.today() - timedelta(days=1)).isoformat()}):
            with self.assertRaises(AuthorizationError, msg=bad):
                Sandbox(self.project, self.authorization(**bad), self.workdir, 'S05')
        with self.assertRaises(AuthorizationError):
            Sandbox(self.project, self.tmp / 'absent.json', self.workdir, 'S05')

    def test_the_app_runs_in_a_copy_without_secrets(self):
        from eaos.sandbox import Sandbox
        from eaos.engines.process import state_digest
        before = state_digest(self.project)
        box = Sandbox(self.project, self.authorization(), self.workdir, 'S05')
        port = free_port()
        box.start([sys.executable, 'server.py', '--port', str(port)], port, '/health', timeout=30)
        try:
            names = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{port}/env', timeout=5).read())
        finally:
            box.stop()
        self.assertIn('EAOS_ACCEPTANCE_ALLOWED', names)
        self.assertNotIn('EAOS_ACCEPTANCE_SECRET_TOKEN', names)
        self.assertEqual(set(names) - {'PATH', 'HOME', 'LANG', 'EAOS_ACCEPTANCE_ALLOWED', 'PWD', 'SHLVL', '_', 'LC_CTYPE'}, set())
        with self.assertRaises(OSError):
            urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=2)
        self.assertEqual(state_digest(self.project), before)

    def test_every_run_is_recorded_by_its_contract(self):
        from eaos.sandbox import Sandbox
        from contracts import contracts, validate
        box = Sandbox(self.project, self.authorization(), self.workdir, 'S05')
        code, out, _ = box.run([sys.executable, '-c', 'print("hi")'], timeout=30)
        box.stop()
        self.assertEqual((code, out.strip()), (0, 'hi'))
        record = json.loads((self.workdir / 'sandbox-run.json').read_text(encoding='utf-8'))
        self.assertEqual(validate(record, contracts()['sandbox-run']), [])
        if record['backend'] == 'process':
            self.assertIn('network not isolated', record['limitations'])


if __name__ == '__main__':
    unittest.main()
