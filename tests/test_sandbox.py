"""The sandbox refuses without the owner's grant, runs in a copy, and records what it could not isolate."""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
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
        home = mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(self.tmp) / 'eaos-home')})   # this machine's projects aside
        home.start()
        self.addCleanup(home.stop)
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
        # a Python app's install once went into EAOS's own environment (the python PATH finds) and broke it: a Python
        # command runs in the run's own virtual environment, first on PATH whatever PATH the run chose
        box = self.box()
        env = box.environment({'PATH': os.environ['PATH']}, ['python3', '-m', 'pip', 'install', '-e', '.'])
        self.assertEqual((env['PATH'].split(os.pathsep)[0], env['VIRTUAL_ENV']), (str(box.folder / 'python/bin'), str(box.folder / 'python')))
        self.assertEqual(box.run(['python3', '-c', 'import sys; print(sys.prefix)'])[1].strip(), str(box.folder / 'python'))

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
        with mock.patch.object(sandbox, '_network_isolation', return_value=()), \
                mock.patch.object(sandbox, '_view_refusal', return_value='no user namespaces'):
            box = self.box()
        box.run([sys.executable, '-c', 'pass'])
        self.assertEqual(self.record()['backend'], 'process')
        self.assertIn('network not isolated', self.record()['limitations'])
        self.assertIn('not isolated: no user namespaces', self.record()['limitations'])

    def test_a_service_that_stops_says_why_and_the_record_keeps_its_exit(self):
        with self.assertRaisesRegex(RuntimeError, 'APP_URL must be an https'):
            self.box().start([sys.executable, '-c', 'import sys; print("APP_URL must be an https address"); sys.exit(1)'], 9, '/')
        with self.assertRaisesRegex(RuntimeError, 'exited with 3 before answering'):
            self.box().start([sys.executable, '-c', 'raise SystemExit(3)'], 9, '/health', timeout=10)
        record = self.record()
        self.assertTrue(any(line.startswith('network not isolated for the started service') for line in record['limitations']))
        self.assertEqual(record['commands'][-1]['exit'], 3)

    def test_a_port_another_program_holds_is_given_up_and_only_the_runs_own_service_counts_as_answering(self):
        import http.server
        import threading
        from eaos.live_run import LiveRun
        other = http.server.ThreadingHTTPServer(('127.0.0.1', 0), http.server.SimpleHTTPRequestHandler)
        threading.Thread(target=other.serve_forever, daemon=True).start()
        self.addCleanup(other.server_close)
        self.addCleanup(other.shutdown)
        taken = other.server_address[1]                         # another project's app, answering 200
        with self.assertRaisesRegex(RuntimeError, 'no 200'):
            self.box().start([sys.executable, '-c', 'import time; time.sleep(30)'], taken, '/', timeout=3)
        (Path(self.tmp) / 'run.json').write_text(json.dumps({'schema_version': 1, 'install': [], 'port': taken, 'health': '/',
                                                             'start': [sys.executable, '-m', 'http.server', str(taken), '--bind', '127.0.0.1'],
                                                             'env': {'APP_URL': f'http://127.0.0.1:{taken}'}}))
        live = LiveRun(self.project, self.tmp, 'S05')
        try: base = live.start()
        finally: live.stop()
        self.assertNotEqual(base, f'http://127.0.0.1:{taken}')
        self.assertEqual(live.extra()['APP_URL'], base, 'every value naming the port moves with it')

    def test_a_timeout_kills_the_whole_process_group_and_dispose_keeps_only_the_record(self):
        box = self.box()
        marker = box.tmp / 'child.pid'
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

    def test_the_next_run_removes_what_a_killed_run_left_and_never_what_a_live_run_holds(self):
        live, left = self.box(), Path(self.tmp) / 'work/home-left-by-a-killed-run'
        (left / '.cache').mkdir(parents=True)
        self.box().dispose()
        self.assertFalse(left.exists())
        self.assertTrue(live.copy.is_dir())
        self.assertEqual(live.environment()['TMPDIR'], str(live.tmp))
        live.dispose()


class TwoProjectsTests(Workspace):
    """Two projects on one computer, laid out as on a remote server: the projects and the reports reached through links
    from EAOS's home, the real folders elsewhere. Project A's code runs in A's sandbox; nothing of B's may reach it."""

    def setUp(self):
        super().setUp()
        if sandbox._view_refusal(): self.skipTest(f'no own view here: {sandbox._view_refusal()}')
        real = tempfile.TemporaryDirectory(dir='/var/tmp')        # outside the temporary folder, which is hidden anyway
        self.addCleanup(real.cleanup)
        self.real = Path(real.name)
        person = self.real / 'person'
        (person / '.eaos/studio').mkdir(parents=True)
        for link, target in (('.eaos/projects', 'state'), ('EAOS', 'reports')):
            (self.real / target).mkdir()
            (person / link).symlink_to(self.real / target)
        environ = mock.patch.dict(os.environ, {'HOME': str(person), 'EAOS_HOME': str(person / '.eaos')})
        environ.start()
        self.addCleanup(environ.stop)
        pg = tempfile.TemporaryDirectory(prefix='eaos-pg-', dir='/tmp')
        self.addCleanup(pg.cleanup)
        self.pg = Path(pg.name)
        (self.pg / 'B-DATABASE').write_text('B')
        self.a, self.b = self.project('a'), self.project('b')

    def project(self, name):
        from eaos import places
        source = self.real / 'src' / name
        source.mkdir(parents=True)
        (source / 'app.py').write_text(f'print("{name}")\n')
        git(source, 'init', '-q'); git(source, 'add', '.')
        git(source, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', name)
        (source / '.env').write_text(f'{name.upper()}_SECRET=real\n')
        workspace = places.workspace(source)
        runtime = workspace / 'runtime'
        (runtime / 'setup').mkdir(parents=True)
        (runtime / 'setup/storage-state.json').write_text(f'{name.upper()}-SESSION')
        (runtime / 'authorization.json').write_text(json.dumps({
            'schema_version': 1, 'project': name, 'commit': git(source, 'rev-parse', 'HEAD'), 'granted_by': 'owner',
            'stages': ['S05'], 'env_allow': [], 'expires': date.today().isoformat()}))
        outputs = workspace.parent.parent.parent / 'EAOS' / name
        outputs.mkdir()
        (outputs / 'REPORT.html').write_text(name)
        (workspace / 'state.json').write_text(json.dumps({'project': str(source), 'workspace': str(workspace), 'outputs': str(outputs)}))
        studio = workspace.parent.parent / 'studio' / workspace.name
        studio.with_suffix('.json').write_text(json.dumps({'token': f'{name}-token'}))
        studio.with_suffix('.token').write_text(f'{name}-token')
        return {'source': source, 'workspace': workspace, 'runtime': runtime, 'outputs': outputs, 'studio': studio}

    def box(self, project):
        return sandbox.Sandbox(project['source'], project['runtime'] / 'authorization.json', project['runtime'] / 'sandbox', 'S05')

    def test_a_new_projects_run_reads_its_own_report_whose_folder_was_never_saved(self):
        # a new project's state never kept `outputs`, so its report was hidden and k6 never found its load script
        from eaos.agent_tools import project_state
        a = self.a
        (a['workspace'] / 'state.json').write_text(json.dumps({'project': str(a['source']), 'workspace': str(a['workspace'])}))
        project_state(str(a['source']))
        script = a['outputs'] / 'technical/nfr/k6/qs-001.js'
        script.parent.mkdir(parents=True)
        script.write_text('// load')
        self.assertEqual(self.box(a).run(['cat', str(script)])[:2], (0, '// load'))

    def test_project_a_code_reads_nothing_of_project_b_by_any_name_nor_connects_to_its_database(self):
        b, real = self.b, lambda path: Path(os.path.realpath(path))
        secrets_of_b = [b['workspace'] / 'state.json', real(b['workspace']) / 'state.json', b['runtime'] / 'setup/storage-state.json',
                        real(b['runtime']) / 'setup/storage-state.json', b['studio'].with_suffix('.json'), b['studio'].with_suffix('.token'),
                        b['source'] / '.env', b['source'] / 'app.py', b['outputs'] / 'REPORT.html', real(b['outputs']) / 'REPORT.html',
                        self.pg / 'B-DATABASE', self.a['source'] / '.env']
        box = self.box(self.a)
        (box.copy / 'probe.py').write_text(
            'import glob, json, os\n'
            f'paths = {json.dumps([str(path) for path in secrets_of_b])}\n'
            'def read(path):\n'
            '    try: return open(path).read()\n'
            '    except OSError: return None\n'
            'print(json.dumps({"read": [p for p in paths if read(p) is not None], "pg": glob.glob("/tmp/eaos-pg*"),\n'
            '                  "own": read("app.py"), "home": os.access(os.environ["HOME"], os.W_OK)}))\n')
        code, out, err = box.run([sys.executable, 'probe.py'])
        self.assertEqual(code, 0, err)
        seen = json.loads(out)
        self.assertEqual((seen['read'], seen['pg']), ([], []), "A's code read B's things (or its own working folder)")
        self.assertEqual((seen['own'], seen['home']), ('print("a")\n', True), 'its own copy and HOME stay its own')
        named = ('import os, sys\nfor path in (sys.argv[1], os.environ["B_STATE"]):\n'
                 '    try: print(open(path).read())\n    except OSError: pass\n')
        code, out, err = box.run([sys.executable, '-c', named, str(b['workspace'] / 'state.json')],
                                 env={'B_STATE': str(real(b['source'])) + '/.env'})
        self.assertEqual((code, out), (0, ''), "a path of B's named to A's command is not shown for being named")
        from eaos.local_db import LocalPostgres, binaries
        if binaries() is None: return
        database = LocalPostgres(b['runtime'])
        url = database.create('app')
        self.addCleanup(lambda: (database.stop(), shutil.rmtree(database.data, True), shutil.rmtree(database.sockets, True)))
        psql = [str(binaries() / 'psql'), '-h', '127.0.0.1', '-p', url.rsplit(':', 1)[1].split('/')[0], '-U', 'postgres', '-w', '-tAc', 'select 1', 'app']
        code, _, err = box.run(psql, network=True)
        self.assertNotEqual(code, 0, "A connected to B's database without its password")
        self.assertIn('password', err)
        self.assertEqual(box.run(psql, network=True, env={'PGPASSWORD': database.password_file.read_text().strip()})[:2], (0, '1\n'))
        box.dispose()

    def test_a_batchs_copy_writes_its_reports_into_its_own_projects_runtime_and_nowhere_else(self):
        a, b = self.a, self.b
        candidate = a['runtime'] / 'candidates/wave-1'
        candidate.parent.mkdir(parents=True)
        git(candidate.parent, 'clone', '-q', str(a['source']), str(candidate))
        box = sandbox.Sandbox(candidate, a['runtime'] / 'authorization.json', a['runtime'] / 'sandbox', 'S05')
        write = 'import os, sys\nfor path in sys.argv[1:]:\n    try: open(path, "w").write("x")\n    except OSError: pass\n'
        mine, theirs = a['runtime'] / 'behavior-lock/wave-1.json', b['runtime'] / 'behavior-lock/wave-1.json'
        for path in (mine, theirs): path.parent.mkdir(parents=True)
        self.assertEqual(box.run([sys.executable, '-c', write, str(mine), str(theirs)])[0], 0)
        self.assertEqual((mine.is_file(), theirs.is_file()), (True, False), "the lock's report of a batch reaches its project, never another")
        box.dispose()

    def test_eaos_clean_leaves_the_run_another_project_holds_and_removes_what_no_run_holds(self):
        from eaos import guided
        held, left = self.box(self.b), self.b['runtime'] / 'sandbox/run-left-by-a-killed-run'
        left.mkdir()
        with mock.patch.object(guided, 'box'):
            guided.clean(mock.Mock(lang='en', pictures=False))
        self.assertTrue(held.copy.is_dir(), "eaos clean removed the copy of B's live run")
        self.assertFalse(left.exists())
        held.dispose()
