"""The sandbox refuses without the owner's grant, runs in a copy, and records what it could not isolate."""
import json
import os
import socket
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

from shared_fixture import Workspace

from eaos import sandbox


def git(project, *args):
    return subprocess.run(['git', '-C', str(project), *args], check=True, capture_output=True, text=True).stdout.strip()


class SandboxTests(Workspace):
    def setUp(self):
        super().setUp()
        self.project = Path(self.tmp) / 'project'
        self.project.mkdir()
        (self.project / 'app.py').write_text('print("app")\n')
        git(self.project, 'init', '-q'); git(self.project, 'add', '.')
        git(self.project, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'app')
        self.grant = Path(self.tmp) / 'authorization.json'
        self.write_grant()

    def write_grant(self, **change):
        record = {'schema_version': 1, 'project': 'p', 'commit': git(self.project, 'rev-parse', 'HEAD'),
                  'granted_by': 'owner', 'stages': ['S05'], 'env_allow': [],
                  'expires': date.today().isoformat(), **change}
        self.grant.write_text(json.dumps(record))

    def box(self):
        return sandbox.Sandbox(self.project, self.grant, Path(self.tmp) / 'work', 'S05')

    def test_a_date_grant_is_valid_through_that_whole_day(self):
        self.assertEqual(sandbox.refusal(self.grant, 'S05'), '')
        self.write_grant(expires=(date.today() - timedelta(days=1)).isoformat())
        self.assertIn('expired', sandbox.refusal(self.grant, 'S05'))

    def test_a_grant_for_another_commit_is_refused(self):
        (self.project / 'app.py').write_text('print("changed")\n')
        git(self.project, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qam', 'change')
        with self.assertRaisesRegex(sandbox.AuthorizationError, 'granted for commit'):
            self.box()

    def test_commands_run_in_a_copy_and_leave_the_project_as_it_was(self):
        box = self.box()
        code, _, _ = box.run([sys.executable, '-c', 'open("written.txt", "w").write("x")'])
        self.assertEqual(code, 0)
        self.assertTrue((box.copy / 'written.txt').is_file())
        self.assertFalse((self.project / 'written.txt').exists())

    def test_a_command_has_no_network_where_the_kernel_allows_it(self):
        box = self.box()
        if not box.offline: self.skipTest('unshare -rn is not allowed here; the record says network not isolated')
        listener = socket.socket(); listener.bind(('127.0.0.1', 0)); listener.listen(1)
        port = listener.getsockname()[1]
        try:
            code, _, _ = box.run([sys.executable, '-c', f'import socket; socket.create_connection(("127.0.0.1", {port}), 2)'])
        finally:
            listener.close()
        self.assertNotEqual(code, 0)
        record = json.loads((Path(self.tmp) / 'work/sandbox-run.json').read_text())
        self.assertEqual(record['backend'], 'unshare')

    def test_without_network_isolation_the_record_says_so(self):
        with mock.patch.object(sandbox, '_network_isolation', return_value=()):
            box = self.box()
        box.run([sys.executable, '-c', 'pass'])
        record = json.loads((Path(self.tmp) / 'work/sandbox-run.json').read_text())
        self.assertEqual(record['backend'], 'process')
        self.assertIn('network not isolated', record['limitations'])

    def test_a_timeout_kills_the_whole_process_group(self):
        box = self.box()
        marker = Path(self.tmp) / 'child.pid'
        script = (f'import subprocess, sys, time; p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"]); '
                  f'open({str(marker)!r}, "w").write(str(p.pid)); time.sleep(60)')
        code, _, err = box.run([sys.executable, '-c', script], timeout=3)
        self.assertNotEqual(code, 0)
        self.assertIn('stopped after 3s', err)
        child = int(marker.read_text())
        with self.assertRaises(ProcessLookupError):
            for _ in range(50):
                os.kill(child, 0)
                __import__('time').sleep(0.1)

    def test_a_started_service_keeps_the_network_and_the_record_says_so(self):
        box = self.box()
        with self.assertRaisesRegex(RuntimeError, 'exited with 3 before answering'):
            box.start([sys.executable, '-c', 'raise SystemExit(3)'], 9, '/health', timeout=10)
        record = json.loads((Path(self.tmp) / 'work/sandbox-run.json').read_text())
        self.assertTrue(any(line.startswith('network not isolated for the started service') for line in record['limitations']))
        self.assertEqual(record['commands'][-1]['exit'], 3)


class SandboxEnvironmentTests(SandboxTests):
    """What a run chose is passed; what this process holds, and was not allowed, never is."""

    def test_extra_values_pass_and_an_unallowed_secret_does_not(self):
        with mock.patch.dict(os.environ, {'OWNER_SECRET_TOKEN': 'do-not-leak'}):
            env = self.box().environment({'DATABASE_URL': 'postgres://local'})
        self.assertEqual(env['DATABASE_URL'], 'postgres://local')
        self.assertNotIn('OWNER_SECRET_TOKEN', env)

    def test_a_working_folder_outside_the_copy_is_refused(self):
        box = self.box()
        with self.assertRaises(sandbox.AuthorizationError):
            box.run(['true'], cwd='../../')
        code, out, _ = box.run([sys.executable, '-c', 'import os;print(os.getcwd())'], cwd='.')
        self.assertEqual(code, 0)
        self.assertEqual(Path(out.strip()).resolve(), box.copy.resolve())
