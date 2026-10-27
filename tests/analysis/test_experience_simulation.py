"""The simulation end to end (M10) on a real browser and a tiny app: a buyer places an order, the admin waiting for it
is told and gets stuck, support escalates, a fresh admin meets it again, the judge confirms it as a fix card, the
buyer's journey replays green with no assistant, and EXPERIENCE.md tells the story."""
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from eaos.analysis.experience import simulation
from eaos.facts.store import read_set
from eaos.live.screens.audit import missing
from eaos.report.experience.document import write

PAGE = """<html><body><button onclick="location.hash='#/ordered'">Place order</button><main id="m"></main><script>
const draw = () => { document.getElementById('m').innerText = location.hash === '#/ordered' ? 'Order placed' : 'Shop'; };
addEventListener('hashchange', draw); draw();</script></body></html>"""
SCENARIO = {'version': 1, 'personas': [
    {'id': 'buyer', 'role': 'visitor', 'name': 'Sara', 'about': 'a buyer', 'goals': [
        {'id': 'order', 'goal': 'Place an order', 'start': '/', 'done_when': 'Order placed', 'waits_for': [], 'makes': 'order-placed'}]},
    {'id': 'admin', 'role': 'visitor', 'name': 'Omar', 'about': 'the shop admin', 'goals': [
        {'id': 'approve', 'goal': 'Approve the new order', 'start': '/', 'done_when': 'Approved', 'waits_for': ['buyer.order']}]}],
    'handoffs': [{'from': 'buyer.order', 'event': 'order-placed', 'to': 'admin.approve'}]}
CLICK = {'action': 'click', 'target': {'role': 'button', 'name': 'Place order', 'nth': 0}}
STUCK = {'action': 'stuck', 'why': 'there is no list of orders to approve', 'friction': None}


class App(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(PAGE.encode())


class Assistant:
    """Each stage's answers in turn; what each stage was asked, kept."""
    def __init__(self, answers):
        self.answers, self.asked = {k: list(v) for k, v in answers.items()}, []

    def complete(self, messages, **options):
        self.asked.append((options.get('stage'), messages[-1]['content']))
        return {'result': self.answers[options['stage']].pop(0)}, {}


@unittest.skipIf(missing('playwright'), 'EAOS Playwright is not installed')
class SimulationTest(unittest.TestCase):
    def test_the_whole_simulation_from_the_scenario_to_the_report(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), App)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        app = {'base': f'http://127.0.0.1:{server.server_port}', 'sessions': {}}
        try:
            with tempfile.TemporaryDirectory() as tmp:
                report = Path(tmp)
                (report / 'experience').mkdir()
                (report / 'experience/scenario.json').write_text(json.dumps(SCENARIO))
                (report / 'experience/data.json').write_text(json.dumps({'version': 1, 'seed': []}))
                verdict = {'id': 'D1', 'verdict': 'confirm', 'why': 'both admins found no orders list', 'harmed': 'the shop admin, who cannot approve orders',
                           'severity': 'high', 'title': 'The admin cannot find the new order', 'title_ar': 'المدير لا يجد الطلب الجديد',
                           'fix': 'Add the orders list to the admin menu.', 'fix_ar': 'أضف قائمة الطلبات إلى قائمة المدير.'}
                assistant = Assistant({'experience_actor': [CLICK, {'action': 'done'}, STUCK, STUCK],
                                       'experience_support': [{'answer': None, 'escalate': True, 'why': 'the app has no orders list'}],
                                       'experience_judge': [{'verdicts': [verdict]}]})
                ran = simulation.simulate(report, tmp, app, assistant)
                self.assertEqual([g['status'] for g in ran['goals']], ['reached', 'stuck'])
                self.assertEqual(ran['events'][0]['event'], 'order-placed')
                self.assertIn('order-placed', assistant.asked[2][1], 'the admin is told what happened before it')
                tickets = json.loads((report / 'experience/tickets.json').read_text())['tickets']
                self.assertEqual((tickets[0]['goal'], tickets[0]['escalated']), ('admin.approve', True))
                self.assertEqual(simulation.judged(report, app, assistant)['confirm'], 1)
                kept = json.loads((report / 'experience/journeys/admin--approve--second.json').read_text())
                self.assertEqual((kept['attempt'], kept['pictures_dir']), ('second', 'admin--approve--second'))
                second = json.loads((report / 'experience/difficulties.json').read_text())['difficulties'][0]['second']
                self.assertEqual(second['journey'], 'experience/journeys/admin--approve--second.json')
                judged = json.loads(assistant.asked[-1][1])['difficulties'][0]
                self.assertIn('second_steps', judged, 'the judge reads the second attempt it rules on')
                facts = read_set(report, 'experience')['facts']
                self.assertEqual(facts[0]['value']['title'], 'The admin cannot find the new order')
                self.assertEqual(simulation.replays(report, app)['summary'], {'green': 1, 'red': 0, 'skipped': 2})
                page, _ = write(report, 'ar')
                text = page.read_text()
                self.assertIn('المدير لا يجد الطلب الجديد', text)
                self.assertIn('experience/journeys/buyer--order/', text, 'the story shows its pictures')
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
