"""Page stages share one real server and sign-in; failure and interruption leave neither a server nor a copy."""
import json
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path

from eaos.live.app.run import LiveRun
from eaos.live.app.setup import authorize, free_port
from eaos.pipeline.runners.live_app import shared_app
from eaos.pipeline.run import execute
from eaos.live.app.profile import write_profile
from eaos.live.screens.audit import missing
from pipeline.test_run import fake_runners

SERVER = '''import os, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
with Path(sys.argv[2]).open('a') as stream: stream.write('start\\n')
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        signed = self.headers.get('Cookie') == 'session=' + os.environ['AUTH_SECRET']
        self.send_response(200 if self.path == '/health' or signed else 401)
        self.end_headers()
        self.wfile.write(b'signed in' if signed else b'health')
HTTPServer(('127.0.0.1', int(sys.argv[1])), Handler).serve_forever()
'''
SEED = '''import json, os, sys
from pathlib import Path
with Path(sys.argv[1]).open('a') as stream: stream.write('seed\\n')
Path(os.environ['EAOS_STORAGE_STATE']).write_text(json.dumps({'cookies': [
    {'name': 'session', 'value': os.environ['AUTH_SECRET'], 'domain': '127.0.0.1', 'path': '/', 'expires': -1,
     'httpOnly': True, 'secure': False, 'sameSite': 'Lax'}], 'origins': []}))
'''


class SetupTests(unittest.TestCase):
    def test_the_apps_own_test_browsers_are_never_installed_to_run_it(self):
        # A real build: the setup ran `npx playwright install chromium`, whose shared folder is read only in the isolated
        # run, so the finished product's screens were never pictured.
        from eaos.live.app.run import _test_browsers
        self.assertTrue(_test_browsers(['npx', 'playwright', 'install', 'chromium']))
        self.assertTrue(_test_browsers(['pnpm', 'exec', 'playwright', 'install', '--with-deps']))
        self.assertFalse(_test_browsers(['npm', 'install']))

    def test_eaos_scripts_in_the_app_load_eaos_playwright_never_the_apps_own(self):
        # A real build: the probe, written into the app's copy, loaded the app's own Playwright (another version, no
        # browsers), so every page stage stopped. One variable names EAOS's own, for the probe and the seed alike.
        from eaos.live.app import assist as live_assist
        from eaos.live.app.setup import PROBE
        from eaos.core.toolchain import home
        with tempfile.TemporaryDirectory() as tmp:
            app, eaos = Path(tmp) / 'app', Path(tmp) / 'eaos-playwright'
            (app / 'node_modules/playwright').mkdir(parents=True)
            (app / 'node_modules/playwright/index.js').write_text("throw new Error('the app own playwright')")
            eaos.mkdir()
            (eaos / 'index.js').write_text("module.exports = { chromium: { launch: async () => { throw new Error('eaos playwright') } } }")
            (app / '.eaos-probe.cjs').write_text(PROBE)
            done = subprocess.run(['node', '.eaos-probe.cjs'], cwd=app, capture_output=True, text=True, timeout=60,
                                  env={'PATH': __import__('os').environ['PATH'], 'EAOS_PLAYWRIGHT': str(eaos), 'BASE_URL': 'http://127.0.0.1:9'})
        self.assertIn('eaos playwright', done.stdout + done.stderr)
        self.assertNotIn('the app own playwright', done.stdout + done.stderr)
        run = LiveRun.__new__(LiveRun)
        run.profile, run.runtime, run.apart = {}, Path(tempfile.gettempdir()), None
        run.database_url = lambda: None
        self.assertEqual(run.run_env()['EAOS_PLAYWRIGHT'], str(home() / 'node/node_modules/playwright'))
        self.assertIn('process.env.EAOS_PLAYWRIGHT', live_assist.PROMPT if hasattr(live_assist, 'PROMPT') else Path(live_assist.__file__).read_text())


class SharedAppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.target, self.runtime = self.root / 'project', self.root / 'runtime'
        self.target.mkdir()
        import os
        from unittest import mock
        from eaos.core.project.places import workspace
        home = mock.patch.dict(os.environ, {'EAOS_HOME': str(self.root / 'eaos-home')})    # this machine's projects aside
        home.start()
        self.addCleanup(home.stop)
        workspace(self.target).mkdir(parents=True)          # this fixture's folder is the run's own report
        (workspace(self.target) / 'state.json').write_text(json.dumps({'outputs': str(self.root)}))
        (self.target / 'server.py').write_text(SERVER)
        (self.target / 'seed.py').write_text(SEED)
        for argv in (['git', 'init', '-q'], ['git', 'add', '.'],
                     ['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.test', 'commit', '-qm', 'fixture']):
            subprocess.run(argv, cwd=self.target, check=True, capture_output=True)
        self.counts = self.root / 'counts.txt'
        install = "from pathlib import Path; p=Path(__import__('sys').argv[1]); p.write_text(p.read_text()+'install\\n' if p.exists() else 'install\\n')"
        write_profile(self.runtime, {'schema_version': 1, 'install': [[sys.executable, '-c', install, str(self.counts)]],
            'start': [sys.executable, '-u', 'server.py', str(free_port()), str(self.counts)], 'port': 1,
            'health': '/health', 'seed': [[sys.executable, 'seed.py', str(self.counts)]]})
        profile = json.loads((self.runtime / 'run.json').read_text())
        profile['port'] = int(profile['start'][3])
        write_profile(self.runtime, profile)
        authorize(self.target, self.runtime, 'Test')

    def test_page_stages_install_start_and_seed_once_and_keep_the_same_signed_session(self):
        for mode in ('one', 'normal', 'speed'):
            with self.subTest(mode=mode):
                self.counts.unlink(missing_ok=True)
                seen = []

                def page(context):
                    live, base, state = shared_app(context)
                    seen.append((live.sandbox.folder, base, state.read_bytes()))
                    cookie = json.loads(state.read_text())['cookies'][0]['value']
                    request = urllib.request.Request(base + '/', headers={'Cookie': 'session=' + cookie})
                    with urllib.request.urlopen(request) as response: self.assertEqual(response.read(), b'signed in')
                    return {}

                runners = fake_runners()
                for name in ('journeys', 'crawl', 'screens'):
                    def visit(context, write=runners[name]):
                        page(context)
                        return write(context)
                    runners[name] = visit
                result = execute(self.target, self.root / mode, runners=runners, runtime=self.runtime, mode=mode)
                self.assertEqual(result['status'], 'COMPLETE', {n: r.get('reason') for n, r in result['stages'].items() if r['status'] == 'failed'})
                self.assertEqual(len(seen), 3)
                self.assertEqual(seen, [seen[0]] * 3)
                self.assertEqual(self.counts.read_text().splitlines(), ['install', 'start', 'seed'])
                self.assertFalse(seen[0][0].exists())
                with self.assertRaises(OSError): urllib.request.urlopen(seen[0][1], timeout=1)
        live = LiveRun(self.target, self.runtime, 'S05')
        try:
            self.assertEqual(live.run_env()['AUTH_SECRET'], json.loads(seen[0][2])['cookies'][0]['value'],
                             'a later run accepts the session made by this profile')
        finally: live.stop()

    @unittest.skipIf(missing('playwright'), 'the pinned Playwright is not installed')
    def test_a_session_signed_in_by_hand_outlives_the_seed_and_is_asked_again_only_once_it_expired(self):
        from eaos.live.access import sign_in
        from eaos.pipeline.runners.live_app import close_app
        from eaos.pipeline.run import Context
        from live.test_sign_in import _as_the_person
        profile = json.loads((self.runtime / 'run.json').read_text())
        profile['env'] = {'AUTH_SECRET': 'a' * 48}
        write_profile(self.runtime, profile)
        state, workspace = sign_in.session(self.runtime), self.root / 'workspace'
        for cookie, asked in (('a' * 48, False), ('expired', True)):
            with self.subTest(asked=asked):
                state.write_text(json.dumps({'cookies': [{'name': 'session', 'value': cookie, 'domain': '127.0.0.1', 'path': '/', 'expires': -1,
                                                          'httpOnly': True, 'secure': False, 'sameSite': 'Lax'}], 'origins': []}))
                sign_in.mark(state)
                person = _as_the_person(workspace, 'a' * 48) if asked else None
                context = Context(target=self.target, runtime=str(self.runtime), out=self.root, sign_in={'folder': str(workspace)})
                try:
                    shared_app(context)
                    self.assertTrue(sign_in.by_hand(state), "the seed never replaces the person's session")
                    self.assertFalse(context['sign_in']['gave_up'], 'it works, or works again once the person signed in')
                finally: close_app(context)
                self.assertEqual(person is not None and not person.is_alive(), asked, 'asked only when it had expired')
                self.assertEqual(json.loads(state.read_text())['cookies'][0]['value'], 'a' * 48)

    def test_failure_or_stop_in_a_page_stage_stops_the_shared_app_and_removes_its_copy(self):
        for problem in (RuntimeError('failed page'), KeyboardInterrupt()):
            with self.subTest(problem=type(problem).__name__):
                seen = []

                def broken(context):
                    live, base, _ = shared_app(context)
                    seen.append((live.sandbox.folder, base))
                    raise problem

                runners = fake_runners()
                runners['crawl'] = broken
                if isinstance(problem, KeyboardInterrupt):
                    with self.assertRaises(KeyboardInterrupt):
                        execute(self.target, self.root / 'stopped', runners=runners, runtime=self.runtime)
                else:
                    result = execute(self.target, self.root / 'failed', runners=runners, runtime=self.runtime)
                    self.assertEqual(result['stages']['crawl']['status'], 'failed')
                self.assertFalse(seen[0][0].exists())
                with self.assertRaises(OSError): urllib.request.urlopen(seen[0][1], timeout=1)
