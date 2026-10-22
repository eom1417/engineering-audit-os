"""Running the app is part of the check once the person agreed (eaos/pipeline/stages.py setup, record, screens,
baseline): without consent, or when the app does not start, each live stage says why and the check completes; with a
running app its records are written before the claims, and the load model reads the measured speed."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.pipeline.run import execute
from eaos.pipeline.stages import ORDER

ROOT = Path(__file__).resolve().parents[1]
LIVE = ('setup', 'record', 'screens', 'baseline')


class FakeRun:
    profile = {}

    def __init__(self, *args, **kwargs): pass
    def freeze(self): pass
    def setup(self): pass
    def start(self): return 'http://127.0.0.1:9'
    def seed(self, base, storage=None): pass
    def stop(self): pass


# the app's page for an address it does not have, as the screens open it (eaos/roles.py nowhere_of)
PROBED = {'text': 'Home', 'others': [{'text': 'Not found'}]}
WALKED = {'specs': 1, 'walked': [{'spec': 'a.spec.ts', 'pages': ['/'], 'status': 'passed', 'reason': ''}], 'failed': 0,
          'recordings': ['a.rrweb.json'], 'traces': [], 'recordings_dropped': [], 'traces_dropped': []}


def started(target, runtime, report=None, provider=None, say=None):
    Path(runtime).mkdir(parents=True, exist_ok=True)
    (Path(runtime) / 'run.json').write_text(json.dumps({'baseline': {'verified': True}}), encoding='utf-8')
    return {'ok': True, 'attempts': 1, 'limitations': [], 'page': None}


def scenario(report):
    (Path(report) / 'nfr/k6').mkdir(parents=True, exist_ok=True)
    (Path(report) / 'nfr/k6/qs-001.js').write_text('// k6', encoding='utf-8')
    return []


def audited(urls, viewports, variants, out=None, **options):
    shot = Path(out) / 'screenshots/00-index-light-phone.png'
    shot.parent.mkdir(parents=True, exist_ok=True)
    shot.write_bytes(b'png')
    return {'status': 'observed', 'tools': {'playwright': 'x'},
            'rows': [{'url': urls[0], 'viewport': v['name'], 'failures': [], 'screenshot': str(shot)} for v in viewports]}


class LiveInTheCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.target = self.base / 'shop'
        shutil.copytree(ROOT / 'tests/fixtures/polyglot', self.target)

    def run_check(self, name, **options):
        manifest = execute(self.target, self.base / name, language='en', **options)
        return manifest, {stage: (manifest['stages'][stage]['status'], manifest['stages'][stage].get('reason_code')) for stage in LIVE}

    def test_without_consent_or_when_the_app_does_not_start_every_live_stage_says_why_and_the_check_completes(self):
        manifest, live = self.run_check('none')
        self.assertEqual(live, {stage: ('unavailable', 'no_run_consent') for stage in LIVE})
        self.assertEqual(manifest['status'], 'COMPLETE')
        failed = {'ok': False, 'attempts': 3, 'limitations': ['npm ci failed'], 'page': None}
        from eaos.assistants.readiness import NoAssistant
        with mock.patch('eaos.live_setup.authorize'), mock.patch('eaos.live_setup.setup', return_value=failed) as setup:
            manifest, live = self.run_check('down', runtime=self.base / 'runtime', provider=NoAssistant('declined', 'without AI'))
        self.assertIsNone(setup.call_args.kwargs['provider'], 'without AI the app is set up without one, never asked of its stand-in')
        self.assertEqual(live, {'setup': ('unavailable', 'app_not_running'), 'record': ('unavailable', 'app_not_running'),
                                'screens': ('unavailable', 'app_not_running'), 'baseline': ('unavailable', 'app_not_running')})
        self.assertIn('npm ci failed', manifest['stages']['record']['reason'])
        self.assertEqual(json.loads((self.base / 'down/live/setup.json').read_text())['limitations'], ['npm ci failed'])
        self.assertEqual(manifest['status'], 'COMPLETE')

    def test_an_app_with_no_load_scenario_is_not_measured_and_says_why(self):
        with mock.patch('eaos.live_setup.authorize'), mock.patch('eaos.live_setup.setup', side_effect=started), \
                mock.patch('eaos.behavior_lock.run_lock', return_value={'results': []}), mock.patch('eaos.live_run.LiveRun', FakeRun), mock.patch('eaos.live_setup.probe', return_value=PROBED), \
                mock.patch('eaos.behavior_lock.run_journeys', return_value=WALKED), \
                mock.patch('eaos.screens.audit.page_audit', side_effect=audited), mock.patch('eaos.screens.audit.lighthouse', return_value={}), \
                mock.patch('eaos.screens.crawl.crawl', return_value={'status': 'observed', 'routes': []}), \
                mock.patch('eaos.nfr.write', return_value=[]), mock.patch('eaos.runtime_baseline.run_baseline') as measured:
            manifest, live = self.run_check('no-scenario', runtime=self.base / 'runtime')
        self.assertEqual(live['baseline'], ('unavailable', 'no_load_scenario'))
        measured.assert_not_called()
        self.assertEqual(manifest['status'], 'COMPLETE')

    def test_a_running_app_is_recorded_pictured_and_measured_before_the_claims(self):
        lock = {'results': [{'path': 'a.spec.ts', 'status': 'passed'}, {'path': 'b.spec.ts', 'status': 'failed'}]}
        speed = {'conditions': {'vus': 100}, 'scenarios': [{'id': 'QS-001', 'threshold': {'p95_ms': 800.0, 'error_rate': 0.01},
                                                                  'before': {'p95_ms': 312.5, 'error_rate': 0}}]}
        with mock.patch('eaos.live_setup.authorize'), mock.patch('eaos.live_setup.setup', side_effect=started), \
                mock.patch('eaos.behavior_lock.run_lock', return_value=lock), mock.patch('eaos.live_run.LiveRun', FakeRun), mock.patch('eaos.live_setup.probe', return_value=PROBED), \
                mock.patch('eaos.behavior_lock.run_journeys', return_value=WALKED), \
                mock.patch('eaos.screens.audit.page_audit', side_effect=audited), \
                mock.patch('eaos.screens.audit.lighthouse', return_value={'status': 'observed', 'scores': {'performance': 91}}), \
                mock.patch('eaos.screens.crawl.crawl', return_value={'status': 'observed', 'routes': [{'path': '/about'}]}), \
                mock.patch('eaos.nfr.write', side_effect=scenario), mock.patch('eaos.runtime_baseline.run_baseline', return_value=speed):
            manifest, live = self.run_check('up', runtime=self.base / 'runtime')
        self.assertEqual(manifest['status'], 'COMPLETE')
        self.assertEqual(manifest['stages']['crawl']['detail'], {'pages': 1})
        self.assertEqual({stage: status for stage, (status, _) in live.items()}, {stage: 'ok' for stage in LIVE})
        self.assertEqual({k: manifest['stages']['record']['detail'][k] for k in ('specs', 'passed')}, {'specs': 2, 'passed': 1})
        screens = json.loads((self.base / 'up/live/screens.json').read_text())
        self.assertEqual([row['screenshot'] for row in screens['rows']][0], 'live/screens/screenshots/00-index-light-phone.png')
        self.assertEqual(json.loads((self.base / 'up/load-model.json').read_text())['measured']['scenarios'][0]['p95_ms'], 312.5)
        self.assertLess(max(ORDER.index(stage) for stage in LIVE), ORDER.index('claims'))

    def test_an_app_whose_code_names_no_page_locks_walks_and_loads_the_pages_the_crawl_found(self):
        # A real check (HungerLab, an SPA with no client router): the code named no page, so lock, record, journeys and
        # baseline stood still while the crawl had found and pictured the pages; and the Studio showed 0 screens.
        from eaos import lock_specs
        speed = {'conditions': {'vus': 10}, 'scenarios': []}
        with mock.patch('eaos.live_setup.authorize'), mock.patch('eaos.live_setup.setup', side_effect=started), \
                mock.patch('eaos.behavior_lock.run_lock', return_value={'results': []}), mock.patch('eaos.live_run.LiveRun', FakeRun), \
                mock.patch('eaos.live_setup.probe', return_value=PROBED), mock.patch('eaos.behavior_lock.run_journeys', return_value=WALKED), \
                mock.patch('eaos.screens.audit.page_audit', side_effect=audited), mock.patch('eaos.lock_specs.surfaces', return_value={}), \
                mock.patch('eaos.screens.audit.lighthouse', return_value={'status': 'observed', 'scores': {'performance': 91}}), \
                mock.patch('eaos.screens.crawl.crawl', return_value={'status': 'observed', 'routes': [{'path': '/'}, {'path': '/#/tasks/1'}, {'path': '/#/tasks/2'}]}), \
                mock.patch('eaos.nfr.write', side_effect=scenario), mock.patch('eaos.runtime_baseline.run_baseline', return_value=speed):
            manifest, live = self.run_check('up', runtime=self.base / 'runtime')
        self.assertLess(ORDER.index('crawl'), ORDER.index('lock'), 'the lock reads the crawl')
        self.assertEqual({stage: manifest['stages'][stage]['status'] for stage in ('lock', 'record', 'journeys', 'baseline')},
                         {stage: 'ok' for stage in ('lock', 'record', 'journeys', 'baseline')})
        self.assertEqual(lock_specs.crawled_pages(self.base / 'up'), ['/', '/#/tasks/1'], 'one page per template')
        plan = json.loads((self.base / 'up/behavior-lock/plan.json').read_text())
        self.assertIn('page /#/tasks/1', [s['feature'] for s in plan['specs']], 'one spec per page: an unsteady page is refused alone')
        self.assertTrue((self.base / 'up/studio/manifest.json').is_file(), 'the Studio is written once the screens are pictured')
        self.assertEqual(json.loads((self.base / 'up/studio/head.json').read_text()).get('not_run'), [], 'nothing stood still')


if __name__ == '__main__':
    unittest.main()


class LoadTarget(unittest.TestCase):
    def test_a_load_on_a_server_of_the_pages_alone_is_refused_and_one_on_the_program_runs(self):
        # EAOS on itself (2026-10-13): the baseline loaded `vite preview`, whose fallback answered /api/* with the page
        # in 8 ms, and the Python server behind the Studio was never measured.
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from eaos import runtime_baseline

        def serve(api):
            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    body = b'{"ok": true}' if api and self.path.startswith('/api/') else b'<html>the app</html>'
                    if api == 'signin' and self.path.startswith('/api/'): return self.send_error(401)
                    if api == 'missing' and self.path.startswith('/api/'): return self.send_error(404)
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(body)

                def log_message(self, *_): pass
            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            self.addCleanup(server.shutdown)
            return f'http://127.0.0.1:{server.server_address[1]}'

        with mock.patch('eaos.nfr.server_routes', return_value=['/', '/api/session', '/api/runs', '/index.html']):
            with self.assertRaisesRegex(RuntimeError, 'serves only its pages'):
                runtime_baseline.refuse_a_page_server('report', serve(api=False))
            with self.assertRaisesRegex(RuntimeError, 'serves only its pages'):    # its routes not found: still the pages
                runtime_baseline.refuse_a_page_server('report', serve(api='missing'))
            runtime_baseline.refuse_a_page_server('report', serve(api=True))
            runtime_baseline.refuse_a_page_server('report', serve(api='signin'))        # the program, behind its sign-in

    def test_the_load_sends_the_programs_token_and_leaves_out_what_a_plain_request_cannot_load(self):
        # EAOS on itself (2026-10-14): its routes answered 401 without the Studio's token, /api/events streams forever,
        # and four routes need a value: the load measured refusals and timeouts, never the program.
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from eaos import runtime_baseline

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/api/events':
                    self.send_response(200); self.send_header('Content-Type', 'text/event-stream'); self.end_headers()
                    return
                code = 400 if self.path == '/api/file' else 200 if self.headers.get('X-Token') == 'secret' or self.path == '/' else 401
                self.send_response(code); self.end_headers()

            def log_message(self, *_): pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        with tempfile.TemporaryDirectory() as copy:
            Path(copy, 'token').write_text('secret\n')
            live = mock.Mock(profile={'app': '.', 'baseline': {'headers': {'X-Token': {'file': 'token'}}}}, sandbox=mock.Mock(copy=Path(copy)))
            sent = runtime_baseline.headers(live)
        kept, left = runtime_baseline.loadable(f'http://127.0.0.1:{server.server_address[1]}', ['/', '/api/runs', '/api/events', '/api/file'], sent)
        self.assertEqual((sent, kept, sorted(left)), ({'X-Token': 'secret'}, ['/', '/api/runs'], ['/api/events', '/api/file']))
