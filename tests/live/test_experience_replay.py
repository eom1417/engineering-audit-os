"""Save and replay (M10.4): a journey that reached its goal is done again with no assistant; one the app no longer
allows replays red with the step it broke at; one that never reached its goal is skipped; replays join the lock."""
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from eaos.live import agent
from eaos.live.experience import actor, replay
from eaos.live.screens.audit import missing

PAGE = """<html><body><label>Name <input id="n"></label><button onclick="history.pushState({}, '', '/saved');
document.getElementById('m').innerText = 'Saved'">{label}</button><main id="m">New profile</main></body></html>"""
PERSONA = {'id': 'buyer', 'role': 'user', 'name': 'Sara', 'about': 'a first-time buyer'}
GOAL = {'name': 'buyer.profile', 'goal': 'Save my profile', 'start': '/', 'done_when': 'the page says Saved'}
STEPS = ({'action': 'fill', 'target': {'role': 'textbox', 'name': 'Name', 'nth': 0}, 'value': 'Sara'},
         {'action': 'click', 'target': {'role': 'button', 'name': 'Save', 'nth': 0}})


class App(BaseHTTPRequestHandler):
    label = 'Save'

    def log_message(self, *args): pass

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(PAGE.replace('{label}', App.label).encode())


class Scripted:
    def __init__(self, *steps): self.steps = list(steps)

    def complete(self, messages, **options): return {'result': self.steps.pop(0)}, {}


def _no_assistant(test):
    """`test` run with every assistant call of the actor and the agent refused."""
    def run(self):
        refuse = mock.Mock(side_effect=AssertionError('a replay never asks the assistant'))
        with mock.patch.object(actor, '_next', refuse), mock.patch.object(agent, '_next', refuse): test(self)
    return run


@unittest.skipIf(missing('playwright'), 'EAOS Playwright is not installed')
class ReplayTests(unittest.TestCase):
    def setUp(self):
        App.label = 'Save'
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), App)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.report = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.journeys = self.report / 'experience' / actor.JOURNEYS
        with agent.Browser(self.base, self.journeys / 'buyer--profile') as browser:
            journey = actor.act(browser, PERSONA, GOAL, Scripted(*STEPS, {'action': 'done'}))
        self.assertTrue(journey['reached'])
        actor.save(self.journeys, journey)
        actor.save(self.journeys, {**journey, 'goal': 'buyer.order', 'reached': False, 'stuck': 'no order button'})

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    @_no_assistant
    def test_a_saved_journey_replays_green_and_one_that_never_reached_is_skipped(self):
        record = replay.replay_all(self.base, {'user': None}, self.report)
        found = {r['goal']: r for r in record['replays']}
        self.assertEqual(record['summary'], {'green': 1, 'red': 0, 'skipped': 1})
        self.assertEqual((found['buyer.profile']['status'], found['buyer.profile']['screens']), ('green', ['/', '/saved']))
        self.assertEqual(found['buyer.order']['status'], 'skipped')
        self.assertEqual(json.loads((self.report / 'experience/replays.json').read_text())['summary'], record['summary'])
        self.assertTrue(any((self.report / 'experience/replays/buyer--profile').glob('step-*.jpg')))
        self.assertEqual([r['status'] for r in replay.as_lock(record)], ['quarantined', 'passed'])

    @_no_assistant
    def test_a_renamed_button_replays_red_with_the_step_it_broke_at(self):
        App.label = 'Keep'
        record = replay.replay_all(self.base, {}, self.report)
        broken = next(r for r in record['replays'] if r['goal'] == 'buyer.profile')
        self.assertEqual((broken['status'], broken['broken_at']), ('red', 2))
        self.assertIn('Save', broken['error'])
        self.assertEqual(record['summary']['red'], 1)
        row = next(r for r in replay.as_lock(record) if r['status'] == 'failed')
        self.assertEqual(row['path'], 'experience/journeys/buyer--profile.json')
        self.assertTrue(row['reason'].startswith('step 2:'))


if __name__ == '__main__':
    unittest.main()
