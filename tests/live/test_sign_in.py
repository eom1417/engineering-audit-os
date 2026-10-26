"""Signing in to the app a check opens: the need seen, the person waited for while the other stages go on, the browser
they sign in with, the page alone for a terminal, a published site read only, and the session kept theirs alone."""
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from eaos.live.access import sign_in
from eaos.pipeline.runners import sign_in as sign_in_stage
from eaos.pipeline.run import execute
from eaos.live.screens.audit import missing
from pipeline.test_run import fake_runners
from eaos.core.project import state as project_state

OTP_APP = Path(__file__).parents[1] / 'fixtures/otp_app'
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
        from eaos.live.app.setup import routes
        (self.root / 'behavior-lock').mkdir()
        (self.root / 'behavior-lock/plan.json').write_text(json.dumps({'specs': [{'surfaces': ['/logout', '/settings', '/sign-out', '/reports']}]}))
        self.assertEqual(routes(self.root), ['/settings', '/reports'], 'the probe of a session never opens a page that ends it')
        runners = fake_runners()
        runners['session'] = sign_in_stage.session
        (self.root / 'project').mkdir()
        app = (SimpleNamespace(), 'http://127.0.0.1:1', self.root / 'runtime/session.json')
        with mock.patch.object(sign_in_stage, 'shared_app', return_value=app), mock.patch('eaos.live.access.test_users.unreached', return_value={}), \
                mock.patch.object(sign_in_stage, '_test_users') as made, mock.patch.object(sign_in_stage, '_ask') as asked:
            result = execute(self.root / 'project', self.root / 'out', runners=runners, runtime=self.root / 'runtime',
                             sign_in={'folder': str(self.root)})
        self.assertEqual(result['stages']['session']['status'], 'ok')
        self.assertEqual(json.loads((self.root / 'out/live/sign-in.json').read_text()), {'schema_version': 1, 'needed': False})
        made.assert_not_called()                        # every page opens and the code has no view: nothing made
        asked.assert_not_called()

    def test_an_app_that_signs_in_by_itself_still_gets_its_views_and_nobody_is_asked(self):
        # chief-ops in development opens as support by itself: no sign-in seen, its program's pages a "not found"
        context = SimpleNamespace(out=self.root / 'out', target=self.root / 'project', provider=object())
        context.setdefault = lambda key, default: default
        (self.root / 'out').mkdir()
        app = (SimpleNamespace(), 'http://127.0.0.1:1', self.root / 'runtime/session.json')
        with mock.patch.object(sign_in_stage, '_live'), mock.patch.object(sign_in_stage, 'shared_app', return_value=app), \
                mock.patch.object(sign_in_stage.sign_in, 'from_code', return_value=[]), \
                mock.patch.object(sign_in_stage.sign_in, 'from_pages', return_value=[]), \
                mock.patch.object(sign_in_stage, '_setup_page', return_value=None), \
                mock.patch('eaos.live.access.test_users.unreached', return_value={'/access': 'src/programme/Access.tsx', '/rota': None}), \
                mock.patch.object(sign_in_stage, '_test_users', return_value='') as made, \
                mock.patch.object(sign_in_stage, '_ask') as asked, mock.patch.object(sign_in_stage, '_keep') as kept:
            sign_in_stage.session(context)
        made.assert_called_once_with(context, *app)
        asked.assert_not_called()
        self.assertEqual(kept.call_args.args[2], {'schema_version': 1, 'needed': False, 'views': 'test_user',
                                                  'unreached': ['/access', '/rota']})

    def test_a_sign_in_that_did_not_take_is_asked_again_on_the_page_the_app_sends_to(self):
        # "I signed in" with the pages still signed out once ended the wait as if nobody came; the browser opened the
        # first page instead of the sign-in the pages are sent to
        page = {'url': 'http://127.0.0.1:4100/', 'others': [{'path': '/notes', 'url': 'http://127.0.0.1:4100/login?next=%2Fnotes'}]}
        self.assertEqual(sign_in.page_of(page, 'http://127.0.0.1:5200'), 'http://127.0.0.1:5200/login?next=%2Fnotes')
        live = SimpleNamespace(runtime=self.root / 'runtime', mail=lambda: None)
        context = SimpleNamespace(out=self.root)
        with mock.patch.object(sign_in, 'ask') as ask, mock.patch.object(sign_in, 'wait', return_value=sign_in.SIGNED_IN), \
                mock.patch.object(sign_in, 'works', side_effect=[False, True]), mock.patch.object(sign_in, 'service_log', return_value=None):
            sign_in_stage._ask(context, {}, live, 'http://127.0.0.1:5200', Path('session.json'))
        self.assertEqual([call.args[3] for call in ask.call_args_list], ['needed', 'not_signed_in'])

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
                        mock.patch.object(sign_in, 'WAIT', 2), mock.patch.object(sign_in_stage.sign_in, 'works', side_effect=works):
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
    def test_the_person_signs_in_by_hand_with_the_code_the_app_prints_and_mails_and_the_browser_saves_and_ends(self):
        from eaos.interfaces.studio_server.sign_in import Browser
        from eaos.live.app.setup import free_port
        from eaos.core.toolchain import home
        port, log, smtp, mail = free_port(), self.root / 'app.log', free_port(), free_port()
        catcher = [] if not (home() / 'bin/mailpit').exists() else [subprocess.Popen(
            [str(home() / 'bin/mailpit'), '--smtp', f'127.0.0.1:{smtp}', '--listen', f'127.0.0.1:{mail}', '--quiet'])]
        for process in catcher: self.addCleanup(process.wait); self.addCleanup(process.terminate)
        with open(log, 'w') as output:
            app = subprocess.Popen(['node', 'server.mjs'], cwd=OTP_APP, env={**os.environ, 'PORT': str(port), 'AUTH_SECRET': 's' * 40,
                                   **({'SMTP_HOST': '127.0.0.1', 'SMTP_PORT': str(smtp)} if catcher else {})}, stdout=output, stderr=output)
        self.addCleanup(app.wait)
        self.addCleanup(app.terminate)
        time.sleep(0.8)
        browser = Browser(f'http://127.0.0.1:{port}/', self.root / 'session.json')
        self.assertTrue(browser.send({'do': 'look'})['url'].endswith('/login'))
        for command in ({'do': 'key', 'key': 'Tab'}, {'do': 'type', 'text': 'me@example.test'}, {'do': 'key', 'key': 'Enter'}):
            shown = browser.send(command)
        self.assertIn('/verify', shown['url'])
        said = sign_in.codes({'log': str(log), 'mail': f'http://127.0.0.1:{mail}' if catcher else None})
        code = re.findall(r'code for me@example.test: (\d{6})', '\n'.join(said['output']))[-1]
        if catcher:
            for _ in range(20):
                if said['mail']: break
                time.sleep(0.25)
                said = sign_in.codes({'mail': f'http://127.0.0.1:{mail}'})
            self.assertEqual((said['mail'][0]['to'], said['mail'][0]['subject']), ('me@example.test', 'Your sign-in code'))
            self.assertIn(code, said['mail'][0]['text'], 'the mail the app sent is caught here, never sent out')
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
        from eaos.live.screens.crawl import discover
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

    def test_lighthouse_on_a_published_site_never_carries_the_persons_session(self):
        from eaos.pipeline.runners import pages
        from eaos.live.screens import crawl
        session = self.root / 'published-session.json'
        session.write_text(json.dumps({'cookies': [{'name': 'session', 'value': 'live'}], 'origins': []}))
        measured = []
        speed = lambda url, out=None, storage_state=None, **_: measured.append(storage_state) or {'status': 'unavailable', 'reason': 'x'}
        with mock.patch.object(crawl, 'lighthouse', side_effect=speed), \
                mock.patch.object(crawl, 'discover', return_value=([{'path': '/', 'status': 'observed', 'depth': 0}], '')):
            crawl.crawl('https://app.example.com', self.root, storage_state=session, read_only=True)
        context = SimpleNamespace(out=self.root, get=lambda key, default=None: {'sign_in': {'published': 'https://app.example.com',
                                                                                             'folder': str(self.root)}}.get(key, default))
        with mock.patch('eaos.live.screens.audit.lighthouse', side_effect=speed), \
                mock.patch('eaos.live.screens.audit.page_audit', return_value={'status': 'observed', 'rows': [], 'tools': {}}):
            pages._audit_pages(context, {'/': ['/']}, None, None, 'https://app.example.com', session, None, True)
        self.assertEqual(measured, [None, None], 'Lighthouse loads the live site as any visitor, never signed in')

    def test_the_sign_in_page_alone_answers_behind_its_guard_and_ends_once_the_person_answers(self):
        from eaos.interfaces import govern
        from eaos.journeys import guided
        from eaos.interfaces.studio_server import server
        from eaos.ai.assistant import headless as adapters
        project, apps = self.root / 'shop', []
        project.mkdir()
        (project / 'package.json').write_text('{}')
        with mock.patch.dict(os.environ, {'EAOS_HOME': str(self.root / 'home'), 'EAOS_REMOTE_ORIGIN': 'https://shop--{port}.dev.remote.e-m.sa'}), \
                mock.patch.object(adapters, 'installed', return_value={}), \
                mock.patch.object(server, 'create_app', side_effect=lambda *a, made=server.create_app, **k: apps.append(made(*a, **k)) or apps[-1]):
            guided.save({'project': str(project), 'workspace': str(guided.workspace(project))})
            workspace = project_state.load(project)['workspace']
            sign_in.ask(workspace, 'http://127.0.0.1:1', Path(workspace) / 'runtime/session.json', 'needed')
            self.assertEqual([row['kind'] for row in govern.waiting(str(project))], ['sign_in'])
            said = []
            alone = threading.Thread(target=server.serve_sign_in, args=(str(project), said.append))
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
        from eaos.journeys import guided
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
