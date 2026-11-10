"""Running the app is part of the check once the person agreed (eaos/pipeline/stages.py setup, record, screens):
without consent, or when the app does not start, each live stage says why and the check completes; with a running app
its records are written before the claims."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.pipeline.run import execute
from eaos.pipeline.stages import ORDER

ROOT = Path(__file__).resolve().parents[2]
LIVE = ('setup', 'record', 'screens')


class FakeRun:
    profile = {}

    def __init__(self, *args, **kwargs): pass
    def freeze(self): pass
    def setup(self): pass
    def start(self): return 'http://127.0.0.1:9'
    def seed(self, base, storage=None): pass
    def stop(self, out=None): pass


# the app's page for an address it does not have, as the screens open it (eaos/live/access/roles.py nowhere_of)
PROBED = {'text': 'Home', 'others': [{'text': 'Not found'}]}
WALKED = {'specs': 1, 'walked': [{'spec': 'a.spec.ts', 'pages': ['/'], 'status': 'passed', 'reason': ''}], 'failed': 0,
          'recordings': ['a.rrweb.json'], 'traces': [], 'recordings_dropped': [], 'traces_dropped': []}


def started(target, runtime, report=None, provider=None, say=None):
    Path(runtime).mkdir(parents=True, exist_ok=True)
    (Path(runtime) / 'run.json').write_text(json.dumps({'baseline': {'verified': True}}), encoding='utf-8')
    return {'ok': True, 'attempts': 1, 'limitations': [], 'page': None}


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
        from eaos.ai.assistant.readiness import NoAssistant
        with mock.patch('eaos.live.app.setup.authorize'), mock.patch('eaos.live.app.setup.setup', return_value=failed) as setup:
            manifest, live = self.run_check('down', runtime=self.base / 'runtime', provider=NoAssistant('declined', 'without AI'))
        self.assertIsNone(setup.call_args.kwargs['provider'], 'without AI the app is set up without one, never asked of its stand-in')
        self.assertEqual(live, {'setup': ('unavailable', 'app_not_running'), 'record': ('unavailable', 'app_not_running'),
                                'screens': ('unavailable', 'app_not_running')})
        self.assertIn('npm ci failed', manifest['stages']['record']['reason'])
        self.assertEqual(json.loads((self.base / 'down/live/setup.json').read_text())['limitations'], ['npm ci failed'])
        self.assertEqual(manifest['status'], 'COMPLETE')

    def test_a_running_app_is_recorded_and_pictured_before_the_claims(self):
        lock = {'results': [{'path': 'a.spec.ts', 'status': 'passed'}, {'path': 'b.spec.ts', 'status': 'failed'}]}
        with mock.patch('eaos.live.app.setup.authorize'), mock.patch('eaos.live.app.setup.setup', side_effect=started), \
                mock.patch('eaos.live.behavior.lock.run_lock', return_value=lock), mock.patch('eaos.live.app.run.LiveRun', FakeRun), mock.patch('eaos.live.app.setup.probe', return_value=PROBED), \
                mock.patch('eaos.live.behavior.lock.run_journeys', return_value=WALKED), \
                mock.patch('eaos.live.screens.audit.page_audit', side_effect=audited), \
                mock.patch('eaos.live.screens.audit.lighthouse', return_value={'status': 'observed', 'scores': {'performance': 91}}), \
                mock.patch('eaos.live.screens.crawl.crawl', return_value={'status': 'observed', 'routes': [{'path': '/about'}]}):
            manifest, live = self.run_check('up', runtime=self.base / 'runtime')
        self.assertEqual(manifest['status'], 'COMPLETE')
        self.assertEqual(manifest['stages']['crawl']['detail'], {'pages': 1})
        self.assertEqual({stage: status for stage, (status, _) in live.items()}, {stage: 'ok' for stage in LIVE})
        self.assertEqual({k: manifest['stages']['record']['detail'][k] for k in ('specs', 'passed')}, {'specs': 2, 'passed': 1})
        screens = json.loads((self.base / 'up/live/screens.json').read_text())
        self.assertEqual([row['screenshot'] for row in screens['rows']][0], 'live/screens/screenshots/00-index-light-phone.png')
        self.assertLess(max(ORDER.index(stage) for stage in LIVE), ORDER.index('claims'))

    def test_an_app_whose_code_names_no_page_locks_and_walks_the_pages_the_crawl_found(self):
        # An SPA with no client router: the code names no page, yet lock, record and journeys run on the pages the
        # crawl found and pictured.
        from eaos.live.behavior import specs as lock_specs
        with mock.patch('eaos.live.app.setup.authorize'), mock.patch('eaos.live.app.setup.setup', side_effect=started), \
                mock.patch('eaos.live.behavior.lock.run_lock', return_value={'results': []}), mock.patch('eaos.live.app.run.LiveRun', FakeRun), \
                mock.patch('eaos.live.app.setup.probe', return_value=PROBED), mock.patch('eaos.live.behavior.lock.run_journeys', return_value=WALKED), \
                mock.patch('eaos.live.screens.audit.page_audit', side_effect=audited), mock.patch('eaos.live.behavior.specs.surfaces', return_value={}), \
                mock.patch('eaos.live.screens.audit.lighthouse', return_value={'status': 'observed', 'scores': {'performance': 91}}), \
                mock.patch('eaos.live.screens.crawl.crawl', return_value={'status': 'observed', 'routes': [{'path': '/'}, {'path': '/#/tasks/1'}, {'path': '/#/tasks/2'}]}):
            manifest, live = self.run_check('up', runtime=self.base / 'runtime')
        self.assertLess(ORDER.index('crawl'), ORDER.index('lock'), 'the lock reads the crawl')
        self.assertEqual({stage: manifest['stages'][stage]['status'] for stage in ('lock', 'record', 'journeys')},
                         {stage: 'ok' for stage in ('lock', 'record', 'journeys')})
        self.assertEqual(lock_specs.crawled_pages(self.base / 'up'), ['/', '/#/tasks/1'], 'one page per template')
        plan = json.loads((self.base / 'up/behavior-lock/plan.json').read_text())
        self.assertIn('page /#/tasks/1', [s['feature'] for s in plan['specs']], 'one spec per page: an unsteady page is refused alone')


if __name__ == '__main__':
    unittest.main()

