"""The sandbox refuses without the owner's grant, runs in a copy, and records what it could not isolate."""
import json
import os
import socket
import subprocess
import sys
import time
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
        self.commit('app')
        self.grant = Path(self.tmp) / 'authorization.json'
        self.write_grant()

    def commit(self, message):
        git(self.project, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qam' if message != 'app' else '-qm', message)
        return git(self.project, 'rev-parse', 'HEAD')

    def write_grant(self, **change):
        record = {'schema_version': 1, 'project': 'p', 'commit': git(self.project, 'rev-parse', 'HEAD'),
                  'granted_by': 'owner', 'stages': ['S05'], 'env_allow': [],
                  'expires': date.today().isoformat(), **change}
        self.grant.write_text(json.dumps(record))

    def box(self):
        return sandbox.Sandbox(self.project, self.grant, Path(self.tmp) / 'work', 'S05')

    def record(self):
        return json.loads((Path(self.tmp) / 'work/sandbox-run.json').read_text())

    def test_the_grant_holds_through_its_day_for_its_commit_and_a_descendant_only_from_s08(self):
        self.assertEqual(sandbox.refusal(self.grant, 'S05'), '')
        self.write_grant(expires=(date.today() - timedelta(days=1)).isoformat())
        self.assertIn('expired', sandbox.refusal(self.grant, 'S05'))
        self.write_grant(stages=['S05', 'S08'])
        (self.project / 'app.py').write_text('print("changed")\n')
        head = self.commit('candidate')
        with self.assertRaisesRegex(sandbox.AuthorizationError, 'granted for commit'):
            self.box()
        self.assertEqual(sandbox.refusal(self.grant, 'S08', head, self.project), '')
        self.assertIn('granted for commit', sandbox.refusal(self.grant, 'S05', head, self.project))
        self.write_grant(stages=['S08'], commit='0' * 40)
        self.assertIn('granted for commit', sandbox.refusal(self.grant, 'S08', head, self.project), 'an unrelated commit')

    def test_the_copy_is_the_authorised_commit_without_env_files_or_unallowed_secrets_and_the_project_stays_as_it_was(self):
        (self.project / '.gitignore').write_text('.env\n')
        (self.project / '.env.example').write_text('DATABASE_URL=\n')
        (self.project / 'config').mkdir()
        (self.project / 'config/.env.production').write_text('DATABASE_URL=postgres://prod\n')
        git(self.project, 'add', '-A'); self.commit('env')
        self.write_grant()
        (self.project / '.env').write_text('DATABASE_URL=postgres://real-production\n')     # ignored, real
        (self.project / 'app.py').write_text('print("unsaved edit")\n')                        # not committed
        box = self.box()
        copy = box.copy
        self.assertFalse((copy / '.env').exists(), 'the real .env never reaches the copy')
        self.assertFalse((copy / 'config/.env.production').exists(), 'a committed .env is removed too')
        self.assertTrue((copy / '.env.example').is_file())
        self.assertEqual((copy / 'app.py').read_text(), 'print("app")\n', 'the copy is the commit, not the working folder')
        code, out, _ = box.run([sys.executable, '-c', 'import os; open("written.txt", "w").write("x"); print(os.getcwd())'], cwd='.')
        self.assertEqual(code, 0)
        self.assertEqual(Path(out.strip()).resolve(), copy.resolve())
        self.assertTrue((copy / 'written.txt').is_file())
        self.assertFalse((self.project / 'written.txt').exists())
        with self.assertRaises(sandbox.AuthorizationError):
            box.run(['true'], cwd='../../')
        with mock.patch.dict(os.environ, {'OWNER_SECRET_TOKEN': 'do-not-leak'}):
            env = self.box().environment({'DATABASE_URL': 'postgres://local'})
        self.assertEqual(env['DATABASE_URL'], 'postgres://local')
        self.assertNotIn('OWNER_SECRET_TOKEN', env)

    def test_network_is_cut_where_the_kernel_allows_it_and_the_record_says_when_it_is_not(self):
        box = self.box()
        if box.offline:
            listener = socket.socket(); listener.bind(('127.0.0.1', 0)); listener.listen(1)
            port = listener.getsockname()[1]
            try:
                code, _, _ = box.run([sys.executable, '-c', f'import socket; socket.create_connection(("127.0.0.1", {port}), 2)'])
            finally:
                listener.close()
            self.assertNotEqual(code, 0)
            self.assertEqual(self.record()['backend'], 'unshare')
        with mock.patch.object(sandbox, '_network_isolation', return_value=()):
            box = self.box()
        box.run([sys.executable, '-c', 'pass'])
        self.assertEqual(self.record()['backend'], 'process')
        self.assertIn('network not isolated', self.record()['limitations'])

    def test_a_service_that_stops_says_why_and_the_record_keeps_its_exit(self):
        with self.assertRaisesRegex(RuntimeError, 'APP_URL must be an https'):
            self.box().start([sys.executable, '-c', 'import sys; print("APP_URL must be an https address"); sys.exit(1)'], 9, '/')
        with self.assertRaisesRegex(RuntimeError, 'exited with 3 before answering'):
            self.box().start([sys.executable, '-c', 'raise SystemExit(3)'], 9, '/health', timeout=10)
        record = self.record()
        self.assertTrue(any(line.startswith('network not isolated for the started service') for line in record['limitations']))
        self.assertEqual(record['commands'][-1]['exit'], 3)

    def test_a_timeout_kills_the_whole_process_group_and_dispose_keeps_only_the_record(self):
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
                time.sleep(0.1)
        copy, home = box.copy, box.home
        box.dispose()
        self.assertFalse(copy.exists())
        self.assertFalse(home.exists())
        self.assertTrue((Path(self.tmp) / 'work/sandbox-run.json').is_file())
