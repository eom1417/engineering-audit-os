"""Signing in to the app a check opens: the need seen, the person waited for while the other stages go on, the browser
they sign in with, the page alone for a terminal, a published site read only, and the session kept theirs alone."""
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from eaos import sign_in
from eaos.pipeline import sign_in_stage
from eaos.pipeline.run import execute
from eaos.screens.audit import missing
from test_pipeline_run import fake_runners

OTP_APP = Path(__file__).parent / 'fixtures/otp_app'
SIGNED_OUT_PAGE = {'path': '/', 'status': 200, 'url': 'http://127.0.0.1:1/login', 'password': 0, 'others': [
    {'path': '/settings', 'status': 200, 'url': 'http://127.0.0.1:1/settings', 'password': 0}]}


def _as_the_person(workspace, cookie='signed'):
    """The person on the sign-in page: once the check asks, the browser saves their session and they say they are in."""
    def answer():
        while not sign_in.asked(workspace): time.sleep(0.05)
        record = sign_in.asked(workspace)
        Path(record['session']).write_text(json.dumps({'cookies': [{'name': 'session', 'value': cookie, 'domain': '127.0.0.1', 'path': '/',
                                                                    'expires': -1, 'httpOnly': True, 'secure': False, 'sameSite': 'Lax'}], 'origins': []}))
        sign_in.answer(workspace, sign_in.SIGNED_IN)
    thread = threading.Thread(target=answer, daemon=True)
    thread.start()
    return thread


class SignInTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_the_need_shows_in_a_redirect_to_the_sign_in_and_nothing_is_asked_without_one(self):
        self.assertEqual(sign_in.from_pages(SIGNED_OUT_PAGE), ['/ showed the sign-in page http://127.0.0.1:1/login'])
        self.assertEqual(sign_in.from_pages({**SIGNED_OUT_PAGE, 'url': 'http://127.0.0.1:1/'}), [])
        (self.root / 'features.json').write_text(json.dumps({'features': [{'name': 'auth', 'surfaces': ['/login']}, {'name': 'shop', 'surfaces': ['/']}]}))
        self.assertEqual(sign_in.from_code(self.root), ['/login: a sign-in route of the code'])
        runners = fake_runners()
        runners['session'] = sign_in_stage.session
        (self.root / 'project').mkdir()
        with mock.patch.object(sign_in_stage, 'shared_app') as started:
            result = execute(self.root / 'project', self.root / 'out', runners=runners, runtime=self.root / 'runtime',
                             sign_in={'folder': str(self.root)})
        self.assertEqual(result['stages']['session']['status'], 'ok')
        self.assertEqual(json.loads((self.root / 'out/live/sign-in.json').read_text())['needed'], False)
        started.assert_not_called()                     # no app started, nothing asked

    def test_the_check_waits_for_the_person_while_the_stages_that_open_no_page_go_on(self):
        project, workspace = self.root / 'project', self.root / 'workspace'
        project.mkdir()
        live = SimpleNamespace(runtime=self.root / 'runtime', mail=lambda: None, sandbox=SimpleNamespace(started=[]))
        live.runtime.mkdir()
        for answered in (False, True):
            with self.subTest(answered=answered):
                seen, out = {}, self.root / f'out-{answered}'
                runners = fake_runners()

                def setup(context, write=runners['setup']):
                    write(context)
                    (context.out / 'live/setup.json').write_text(json.dumps({'page': SIGNED_OUT_PAGE}))
                    return {}

                def session(context):
                    seen['began'] = time.monotonic()
                    try: return sign_in_stage.session(context)
                    finally: seen['ended'] = time.monotonic()

                def measure(context, write=runners['measure']):
                    seen['measure'] = time.monotonic()
                    return write(context)
                runners.update(setup=setup, session=session, measure=measure)
                if answered: _as_the_person(workspace)
                works = lambda live, base, state, report=None: Path(state).is_file()
                with mock.patch.object(sign_in_stage, 'shared_app', return_value=(live, 'http://127.0.0.1:1', sign_in.session(live.runtime))), \
                        mock.patch.object(sign_in_stage, 'close_app'), mock.patch.object(sign_in, 'WAIT', 2), mock.patch.object(sign_in_stage.sign_in, 'works', side_effect=works):
                    sign_in.session(live.runtime).unlink(missing_ok=True)
                    result = execute(project, out, runners=runners, runtime=live.runtime, mode='normal', sign_in={'folder': str(workspace)})
                row = result['stages']['session']
                self.assertIsNone(sign_in.asked(workspace), 'the question goes once answered or no longer waited for')
                if not answered:
                    self.assertEqual((row['status'], row['reason_code']), ('unavailable', 'signed_out'), row['reason'])
                    self.assertIn('seen signed out', row['reason'])
                    self.assertLess(seen['began'], seen['measure'], 'a stage that opens no page ran while the check waited')
                    self.assertLess(seen['measure'], seen['ended'])
                else:
                    self.assertEqual((row['status'], row['detail'].get('how')), ('ok', 'hand'), row)
                    record = (out / 'live/sign-in.json').read_text()
                    self.assertNotIn('signed', json.loads(record).get('evidence', [''])[0])
                    self.assertNotIn('cookies', record, 'the report never holds the session')
                    self.assertEqual(os.stat(sign_in.session(live.runtime)).st_mode & 0o777, 0o600)

    @unittest.skipIf(missing('playwright'), 'the pinned Playwright is not installed')
    def test_the_person_signs_in_by_hand_with_the_code_the_app_prints_and_the_browser_saves_and_ends(self):
        from eaos.api.sign_in import Browser
        from eaos.live_setup import free_port
        port, log = free_port(), self.root / 'app.log'
        with open(log, 'w') as output:
            app = subprocess.Popen(['node', 'server.mjs'], cwd=OTP_APP, env={**os.environ, 'PORT': str(port), 'AUTH_SECRET': 's' * 40},
                                   stdout=output, stderr=output)
        self.addCleanup(app.wait)
        self.addCleanup(app.terminate)
        time.sleep(0.8)
        browser = Browser(f'http://127.0.0.1:{port}/', self.root / 'session.json')
        self.assertTrue(browser.send({'do': 'look'})['url'].endswith('/login'))
        for command in ({'do': 'key', 'key': 'Tab'}, {'do': 'type', 'text': 'me@example.test'}, {'do': 'key', 'key': 'Enter'}):
            shown = browser.send(command)
        self.assertIn('/verify', shown['url'])
        said = sign_in.codes({'log': str(log)})['output']
        code = re.findall(r'code for me@example.test: (\d{6})', '\n'.join(said))[-1]
        for command in ({'do': 'key', 'key': 'Tab'}, {'do': 'type', 'text': code}, {'do': 'key', 'key': 'Enter'}):
            shown = browser.send(command)
        self.assertTrue(shown['url'].endswith('/dashboard') and shown['picture'])
        self.assertTrue(browser.done())
        self.assertIsNotNone(browser.process.returncode, 'the browser has ended')
        self.assertEqual(os.stat(self.root / 'session.json').st_mode & 0o777, 0o600)
        cookie = json.loads((self.root / 'session.json').read_text())['cookies'][0]
        request = urllib.request.Request(f'http://127.0.0.1:{port}/reports/1', headers={'Cookie': f"session={cookie['value']}"})
        with urllib.request.urlopen(request) as response: self.assertIn(b'Only me@example.test', response.read())

    @unittest.skipIf(missing('playwright'), 'the pinned Playwright is not installed')
    def test_a_published_site_is_read_with_get_only_and_never_through_a_link_that_signs_out(self):
        from eaos.screens.crawl import discover
        asked = []

        class Site(BaseHTTPRequestHandler):
            def log_message(self, *args): pass

            def _page(self):
                asked.append((self.command, self.path))
                body = {'/': '<a href="/a">a</a> <a href="/logout">out</a> <a href="/items/1/delete">x</a>',
                        '/a': "<p>a</p><script>fetch('/track', {method: 'POST'})</script>"}.get(self.path, 'ok')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(body.encode())
            do_GET = do_POST = _page
        site = ThreadingHTTPServer(('127.0.0.1', 0), Site)
        threading.Thread(target=site.serve_forever, daemon=True).start()
        self.addCleanup(site.server_close)
        self.addCleanup(site.shutdown)
        (self.root / 'session.json').write_text(json.dumps({'cookies': [], 'origins': []}))
        routes, error = discover(f'http://127.0.0.1:{site.server_address[1]}/', storage_state=self.root / 'session.json', read_only=True)
        self.assertFalse(error)
        self.assertEqual(sorted(row['path'] for row in routes), ['/', '/a'])
        self.assertEqual({method for method, _ in asked}, {'GET'})
        self.assertFalse([path for _, path in asked if 'logout' in path or 'delete' in path])

    def test_the_sign_in_page_alone_answers_behind_its_guard_and_ends_once_the_person_answers(self):
        from eaos import govern, guided
        from eaos.api import server, sign_in as page
        from eaos.studio.actions import adapters
        project, apps = self.root / 'shop', []
        project.mkdir()
        (project / 'package.json').write_text('{}')
        with mock.patch.dict(os.environ, {'EAOS_HOME': str(self.root / 'home'), 'EAOS_REMOTE_ORIGIN': 'https://shop--{port}.dev.remote.e-m.sa'}), \
                mock.patch.object(adapters, 'installed', return_value={}), \
                mock.patch.object(server, 'create_app', side_effect=lambda *a, made=server.create_app, **k: apps.append(made(*a, **k)) or apps[-1]):
            guided.save({'project': str(project), 'workspace': str(guided.workspace(project))})
            workspace = guided.load(project)['workspace']
            sign_in.ask(workspace, 'http://127.0.0.1:1', Path(workspace) / 'runtime/session.json', 'needed')
            self.assertEqual([row['kind'] for row in govern.waiting(str(project))], ['sign_in'])
            said = []
            alone = threading.Thread(target=page.serve_alone, args=(str(project), said.append))
            alone.start()
            for _ in range(300):
                if said or not alone.is_alive(): break
                time.sleep(0.05)
            address = said[0]
            port = int(re.search(r'--(\d+)\.', address)[1])
            self.assertEqual(address, f'https://shop--{port}.dev.remote.e-m.sa/#/sign-in', 'its routed address, the token read behind the Remote sign-in')
            host = {'Host': f'shop--{port}.dev.remote.e-m.sa'}
            with self.assertRaises(urllib.error.HTTPError) as refused:
                urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}/api/sign-in', headers=host), timeout=5)
            self.assertEqual(refused.exception.code, 401)
            keys = apps[0].state.ctx.keys
            request = urllib.request.Request(f'http://127.0.0.1:{port}/api/sign-in', headers={**host, 'X-EAOS-Token': keys.token})
            with urllib.request.urlopen(request, timeout=5) as response: self.assertEqual(json.loads(response.read())['asked']['why'], 'needed')
            session = urllib.request.Request(f'http://127.0.0.1:{port}/api/session', headers={**host, 'X-EAOS-Token': keys.token})
            with urllib.request.urlopen(session, timeout=5) as response: self.assertFalse(json.loads(response.read()).get('actions'), 'no other action')
            govern.answer(str(project), govern.SIGN_IN, sign_in.SIGNED_OUT)
            alone.join(15)
            self.assertFalse(alone.is_alive(), 'the page alone ends once the check no longer waits')
            self.assertEqual(json.loads((Path(workspace) / sign_in.ASKED).read_text())['state'], sign_in.SIGNED_OUT)

    def test_the_session_is_its_owners_and_eaos_clean_forgets_it(self):
        from eaos import guided
        home = self.root / 'home'
        with mock.patch.dict(os.environ, {'EAOS_HOME': str(home)}):
            state = home / 'projects/shop/runtime/session.json'
            state.parent.mkdir(parents=True)
            state.write_text(json.dumps({'cookies': [], 'origins': []}))
            sign_in.mark(state)
            self.assertTrue(sign_in.by_hand(state))
            self.assertEqual(os.stat(state).st_mode & 0o777, 0o600)
            guided.clean(SimpleNamespace(lang='en', pictures=False))
            self.assertFalse(state.exists())


if __name__ == '__main__':
    unittest.main()
