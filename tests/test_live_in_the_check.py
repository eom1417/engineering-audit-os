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
    def setup(self): pass
    def start(self): return 'http://127.0.0.1:9'
    def seed(self, base, storage=None): pass
    def stop(self): pass


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


def audited(urls, viewports, variants, out=None):
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
        with mock.patch('eaos.live_setup.authorize'), mock.patch('eaos.live_setup.setup', return_value=failed):
            manifest, live = self.run_check('down', runtime=self.base / 'runtime')
        self.assertEqual(live, {'setup': ('unavailable', 'app_not_running'), 'record': ('unavailable', 'app_not_running'),
                                'screens': ('unavailable', 'app_not_running'), 'baseline': ('unavailable', 'app_not_running')})
        self.assertIn('npm ci failed', manifest['stages']['record']['reason'])
        self.assertEqual(json.loads((self.base / 'down/live/setup.json').read_text())['limitations'], ['npm ci failed'])
        self.assertEqual(manifest['status'], 'COMPLETE')

    def test_an_app_with_no_load_scenario_is_not_measured_and_says_why(self):
        with mock.patch('eaos.live_setup.authorize'), mock.patch('eaos.live_setup.setup', side_effect=started), \
                mock.patch('eaos.behavior_lock.run_lock', return_value={'results': []}), mock.patch('eaos.live_run.LiveRun', FakeRun), \
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
        speed = {'conditions': {'vus': 100}, 'scenarios': [{'id': 'QS-001', 'threshold': 800, 'before': {'p95_ms': 312.5, 'error_rate': 0}}]}
        with mock.patch('eaos.live_setup.authorize'), mock.patch('eaos.live_setup.setup', side_effect=started), \
                mock.patch('eaos.behavior_lock.run_lock', return_value=lock), mock.patch('eaos.live_run.LiveRun', FakeRun), \
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


if __name__ == '__main__':
    unittest.main()
