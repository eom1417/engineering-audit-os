"""The browser agent (eaos/live/agent.py, M5.2): the assistant drives the browser a step at a time towards a goal, each
step recorded with its picture, and the record replays with no assistant; a step that would delete is refused."""
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from eaos.live import agent
from eaos.live.screens.audit import missing

# A hash-routed app whose second screen only a tab button opens: no link, no address in a menu.
PAGE = """<html><body><nav><button onclick="location.hash='#/reports'">Reports</button>
<button onclick="document.body.dataset.gone='yes'">Delete everything</button></nav>
<main id="m"></main><script>
const draw = () => { document.getElementById('m').innerText = location.hash === '#/reports' ? 'Monthly reports' : 'Home'; };
addEventListener('hashchange', draw); draw();</script></body></html>"""
# A server-rendered form (Django, WTForms): each field named by its <label>, its `name` attribute the code's own.
FORM = """<html><body><form><label for="id_first_name">First name:</label><input id="id_first_name" name="first_name">
<textarea name="post"></textarea><p id="out"></p></form></body></html>"""


class App(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write((FORM if self.path == '/form' else PAGE).encode())


class Scripted:
    """An assistant that answers the steps it is given, and says what it was shown."""
    def __init__(self, *steps):
        self.steps, self.seen = list(steps), []

    def complete(self, messages, **options):
        self.seen.append(messages[-1]['content'])
        return (self.steps.pop(0) if self.steps else {'action': 'done'}), {}     # as Claude's adapter answers: the object itself


@unittest.skipIf(missing('playwright'), 'EAOS Playwright is not installed')
class AgentTests(unittest.TestCase):
    def test_the_assistant_reaches_a_screen_behind_a_button_and_the_replay_reaches_it_with_none(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), App)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with tempfile.TemporaryDirectory() as tmp:
                assistant = Scripted({'action': 'click', 'target': {'role': 'button', 'name': 'Delete everything', 'nth': 0}},
                                     {'action': 'click', 'target': {'role': 'button', 'name': 'Reports', 'nth': 0}, 'why': 'a tab'})
                with agent.Browser(base, Path(tmp) / 'explore') as browser:
                    record = agent.explore(browser, agent.SCREENS, assistant)
                self.assertEqual(record['screens'], ['/', '/#/reports'])
                self.assertIn('refused', record['steps'][0]['error'], 'a step that deletes is never pressed')
                self.assertIn('"Reports"', assistant.seen[0], 'the assistant is shown the controls it may use')
                self.assertTrue((Path(tmp) / 'explore' / record['steps'][1]['picture']).is_file(), 'each step keeps its picture')
                with agent.Browser(base, Path(tmp) / 'replay') as browser:
                    self.assertEqual(agent.replay(browser, record), {'screens': ['/', '/#/reports']})
                    gone = {**record, 'steps': [{'action': 'click', 'target': {'role': 'tab', 'name': 'Gone', 'nth': 0}}]}
                    self.assertEqual(agent.replay(browser, gone)['broken_at'], 1)
        finally:
            server.shutdown()

    def test_a_labelled_field_is_listed_by_its_label_and_filled_by_what_was_listed(self):
        # the simulated users of django-locallibrary and flask-microblog were shown "first_name" and "post", the fields'
        # `name` attributes, which no fill could find: every form goal got stuck (M10.10)
        server = ThreadingHTTPServer(('127.0.0.1', 0), App)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as tmp, agent.Browser(f'http://127.0.0.1:{server.server_port}', Path(tmp)) as browser:
                page = browser.do({'op': 'open', 'path': '/form'})
                self.assertEqual([c['name'] for c in page['controls'] if c['role'] == 'textbox'], ['First name:', 'post'])
                for name in ('First name:', 'post'):
                    done = browser.do({'op': 'fill', 'target': {'role': 'textbox', 'name': name, 'nth': 0}, 'value': 'Ingrid'})
                    self.assertTrue(done['ok'], done.get('error'))
        finally:
            server.shutdown()


if __name__ == '__main__':
    unittest.main()
