"""A test account by rules (eaos/live/test_account.py): the app's own sign-up and sign-in pages filled as a person fills
them, with no assistant (the corpus' sign-in app was seen signed out without one)."""
import json
import os
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from urllib.parse import parse_qs

from eaos.live import test_account
from eaos.live.screens.audit import missing

FORM = ('<html><body><form method="post"><input name="username"><input name="email" type="email">'
        '<input name="password" type="password"><input name="password2" type="password"><button>Register</button></form></body></html>')


class App(BaseHTTPRequestHandler):
    """An app with a sign-up page the sign-in page links to: its accounts in memory, a cookie once signed in."""
    users = {}

    def log_message(self, *args): pass

    def _send(self, code, body='', **headers):
        self.send_response(code)
        self.send_header('Content-Type', 'text/html')
        for name, value in headers.items(): self.send_header(name.replace('_', '-'), value)
        self.end_headers()
        self.wfile.write(body.encode())

    def do_GET(self):
        if self.path.startswith('/auth/login'):
            return self._send(200, '<form method="post"><input name="username"><input name="password" type="password">'
                                   '<button>Sign In</button></form><a href="/auth/register">Click to Register!</a>')
        if self.path == '/auth/register': return self._send(200, FORM)
        if 'who=' in (self.headers.get('Cookie') or ''): return self._send(200, '<h1>Hi demo</h1>')
        self._send(404 if self.path != '/' else 302, '', Location='/auth/login?next=/')

    def do_POST(self):
        form = {k: v[0] for k, v in parse_qs(self.rfile.read(int(self.headers['Content-Length'])).decode()).items()}
        if self.path == '/auth/register':
            if form['username'] in App.users: return self._send(200, FORM)        # the name is taken
            App.users[form['username']] = form['password']
            return self._send(302, '', Location='/auth/login')
        if App.users.get(form.get('username')) == form.get('password'):
            return self._send(302, '', Location='/', Set_Cookie='who=demo; Path=/')
        self._send(200, '<form method="post"><input name="username"><input name="password" type="password"><button>Sign In</button></form>')


class TestAccountTests(unittest.TestCase):
    @unittest.skipIf(missing('playwright'), 'EAOS Playwright is not installed')
    def test_the_rules_sign_up_then_sign_in_and_a_wrong_password_says_what_it_tried(self):
        from eaos.core.toolchain import home
        server = ThreadingHTTPServer(('127.0.0.1', 0), App)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with tempfile.TemporaryDirectory() as tmp:
                run = lambda password: subprocess.run(['node', str(test_account.SCRIPT)], capture_output=True, text=True, timeout=180, env={
                    **os.environ, 'BASE_URL': base, 'EAOS_STORAGE_STATE': f'{tmp}/state.json', 'EAOS_TEST_PASSWORD': password,
                    'EAOS_PLAYWRIGHT': str(home() / 'node/node_modules/playwright'), 'EAOS_SIGN_IN_PAGE': base + '/auth/login?next=/'})
                done = run('Secret-123Aa1!')
                self.assertEqual(json.loads(done.stdout.splitlines()[-1]), {'E2E_USER': 'demo', 'E2E_PASSWORD': 'Secret-123Aa1!'}, done.stderr)
                self.assertEqual(App.users, {'demo': 'Secret-123Aa1!'}, 'signed up at the page the sign-in page links to')
                self.assertIn('who', Path(f'{tmp}/state.json').read_text())
                wrong = run('another-one')
                self.assertEqual(wrong.returncode, 1)
                self.assertEqual(json.loads(wrong.stdout.splitlines()[-1])['tried'][:2],
                                 [{'did': 'signed_in', 'at': '/auth/login?next=/'}, {'did': 'signed_up', 'at': '/auth/register'}])
        finally:
            server.shutdown()

    def test_a_rule_that_got_in_becomes_the_runs_seed_and_one_that_did_not_changes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            (runtime / 'run.json').write_text(json.dumps({'schema_version': 1, 'app': '.', 'install': [['true']], 'start': ['true'],
                                                          'port': 1, 'health': '/', 'env': {}, 'checks': []}))
            state = runtime / 'session.json'
            live = SimpleNamespace(runtime=runtime, profile={'env': {}}, run=mock.Mock(return_value=(1, '{"signed_in": false, "tried": []}', '')))
            self.assertEqual(test_account.by_rules(live, 'http://127.0.0.1:1', state, None), [{'did': 'no_form'}])
            self.assertNotIn('seed', json.loads((runtime / 'run.json').read_text()))
            state.write_text('{}')
            live.run.return_value = (0, '{"E2E_USER": "demo"}', '')
            self.assertEqual(test_account.by_rules(live, 'http://127.0.0.1:1', state, None), [])
            profile = json.loads((runtime / 'run.json').read_text())
            self.assertEqual(profile['seed'], [['node', str(runtime / 'setup/sign-up.cjs')]])
            self.assertEqual(profile['env']['EAOS_TEST_USER'], 'demo')


if __name__ == '__main__':
    unittest.main()
