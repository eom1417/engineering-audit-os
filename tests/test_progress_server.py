"""The live map's server and entry (live scan map v2, phase 3): /api/progress, /api/report-file, the feed over every
progress file, the `watch` address of the assistant's tools and of `eaos start`, and the Studio that open_studio starts
never importing the checked project's own `eaos` (G12)."""
import os
import signal
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tests'))

from eaos import agent_tools, behavior_lock, cli, guided, jobs, live_setup, progress, waves  # noqa: E402
from eaos.api import launch, server  # noqa: E402
from eaos.pipeline import STAGES  # noqa: E402
from eaos.pipeline.stages import ORDER  # noqa: E402
from test_continuity import Base as Checked  # noqa: E402
from test_mcp import git_project  # noqa: E402
from test_studio_api import PORT, report_with_data  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

FLOWS = {'check': STAGES, 'setup': live_setup.FLOW, 'safety': behavior_lock.FLOW, 'fix': waves.FLOW}


class Project(unittest.TestCase):
    """A git project with its guided state, its report with Studio data, and a server over both."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(self.tmp.name) / 'home')})
        env.start()
        self.addCleanup(env.stop)
        self.project = git_project(Path(self.tmp.name) / 'shop')
        self.state = agent_tools.project_state(str(self.project))
        self.report = report_with_data(guided.report_of(self.state).parent)
        self.runtime = guided.runtime_of(self.state)

    def client(self):
        keys = server.Keys(port=PORT)
        app = server.create_app(self.report, project=self.project, keys=keys, mounts=[], watch=False)
        return TestClient(app, base_url=f'http://127.0.0.1:{PORT}'), keys, app

    def get(self, route, **params):
        http, keys, _ = self.client()
        return http.get(route, params=params, headers={'X-EAOS-Token': keys.token})


class ProgressRoute(Project):
    def test_the_journey_and_every_flow_folded_and_laid_out(self):
        log = progress.ProgressLog(self.runtime, 'setup', pulse=False, sampler=None)
        log.started(live_setup.FLOW, [s.name for s in live_setup.FLOW], {})
        log.emit('stage.started', stage='detect')
        body = self.get('/api/progress').json()
        self.assertEqual([(s['id'], s['flow']) for s in body['journey']], list(guided.FLOWS.items()))
        self.assertEqual(sorted(body['flows']), sorted(FLOWS))
        for flow, declared in FLOWS.items():
            self.assert_drawn(body['flows'][flow]['stages'], declared, flow)
        setup = body['flows']['setup']
        self.assertEqual((setup['state'], setup['flow'], setup['stages'][0]['state']), ('running', 'setup', 'running'))
        self.assertEqual((body['flows']['fix']['state'], body['flows']['fix']['run']), ('none', None), 'not run yet: declared, waiting')
        self.assertEqual(body['journey'][1]['state'], 'running')
        self.assertNotIn('pid', setup)
        self.assertTrue(body['now'] and body['feed_last'])
        log.finish('STOPPED')

    def assert_drawn(self, stages, declared, flow):
        """The map's nodes and edges are the declaration's, each edge going down a layer."""
        self.assertEqual([s['name'] for s in stages], [s.name for s in declared], flow)
        edges = [(need, s['name']) for s in stages for need in s['requires']]
        self.assertEqual(edges, [(need, s.name) for s in declared for need in s.requires], flow)
        layer = {s['name']: s['layer'] for s in stages}
        self.assertTrue(all(layer[after] > layer[before] for before, after in edges), flow)

    def test_a_stage_added_to_a_flow_appears_with_no_other_change(self):
        added = live_setup.FLOW + (progress.Stage('smoke', requires=('detect',), description='A stage added in a test'),)
        with mock.patch.object(live_setup, 'FLOW', added):
            stages = self.get('/api/progress').json()['flows']['setup']['stages']
        self.assertEqual((stages[-1]['name'], stages[-1]['requires'], stages[-1]['layer']), ('smoke', ['detect'], 1))

    def test_scan_progress_is_the_check_flow_of_progress(self):
        log = progress.ProgressLog(self.report)
        log.started(STAGES, list(ORDER), {})
        log.emit('stage.started', stage='facts')
        whole, alone = self.get('/api/progress').json()['flows']['check'], self.get('/api/scan-progress').json()
        self.assertEqual({k: v for k, v in alone.items() if k not in ('now', 'feed_last')}, whole)

    def test_without_a_project_only_the_check(self):
        http, keys, _ = report_client(self.report)
        body = http.get('/api/progress', headers={'X-EAOS-Token': keys.token}).json()
        self.assertEqual((body['journey'], list(body['flows'])), ([], ['check']))

    def test_the_token_guards_it_and_the_document_lists_it(self):
        http, keys, _ = self.client()
        self.assertEqual(http.get('/api/progress').status_code, 401)
        for route in ('/api/report-file', '/api/screen'): self.assertEqual(http.get(route, params={'path': 'a.md'}).status_code, 401)
        paths = http.get('/api/openapi.json', headers={'X-EAOS-Token': keys.token}).json()['paths']
        self.assertTrue({'/api/progress', '/api/scan-progress', '/api/report-file', '/api/screen'} <= set(paths))


def report_client(report):
    keys = server.Keys(port=PORT)
    app = server.create_app(report, name='shop', keys=keys, mounts=[], watch=False)
    return TestClient(app, base_url=f'http://127.0.0.1:{PORT}'), keys, app


class ReportFile(Project):
    def test_a_text_file_of_the_report_is_served_as_plain_text(self):
        (self.report / 'EXECUTIVE.md').write_text('# تقرير\n<script>alert(1)</script>\n', encoding='utf-8')
        answer = self.get('/api/report-file', path='EXECUTIVE.md')
        self.assertEqual((answer.status_code, answer.text), (200, '# تقرير\n<script>alert(1)</script>\n'))
        self.assertEqual(answer.headers['content-type'], 'text/plain; charset=utf-8', 'never rendered, even html')
        self.assertEqual((answer.headers['content-security-policy'], answer.headers['x-content-type-options']), ('sandbox', 'nosniff'))
        self.assertEqual(self.get('/api/report-file', path='studio/manifest.json').status_code, 200, 'a file in a sub-folder')

    def test_paths_that_leave_the_report_are_refused(self):
        outside = Path(self.tmp.name) / 'secret.md'
        outside.write_text('secret\n')
        (self.report / 'link.md').symlink_to(outside)
        (self.report / 'up').symlink_to(Path(self.tmp.name), target_is_directory=True)
        for path in ('../secret.md', 'studio/../../secret.md', '..', str(outside), '/etc/passwd', '~/secret.md',
                     'link.md', 'up/secret.md', 'a\0b.md', ''):
            answer = self.get('/api/report-file', path=path)
            self.assertEqual((answer.status_code, answer.json()['error']), (400, 'path'), path)
            self.assertNotIn('secret', answer.text)

    def test_only_existing_text_files_up_to_two_megabytes(self):
        (self.report / 'shot.png').write_bytes(b'\x89PNG\r\n')
        (self.report / 'bytes.txt').write_bytes(b'\xff\xfe\x00')
        (self.report / 'big.json').write_text('x' * (2 * 2 ** 20 + 1))
        (self.report / 'edge.json').write_text('x' * (2 * 2 ** 20))
        for path, status, error in (('missing.md', 404, 'not_found'), ('studio', 404, 'not_found'), ('shot.png', 415, 'type'),
                                    ('bytes.txt', 415, 'type'), ('big.json', 413, 'size')):
            answer = self.get('/api/report-file', path=path)
            self.assertEqual((answer.status_code, answer.json()['error']), (status, error), path)
        self.assertEqual(self.get('/api/report-file', path='edge.json').status_code, 200)

    def test_a_recorded_screen_is_served_and_nothing_else_of_the_runtime_folder(self):
        shots = self.runtime / 'behavior-lock' / 'snapshots' / 'home.spec.ts'
        shots.mkdir(parents=True)
        (shots / 'home.png').write_bytes(b'\x89PNG\r\n')
        (self.runtime / 'run.png').write_bytes(b'\x89PNG\r\n')
        (shots / 'notes.txt').write_text('x')
        answer = self.get('/api/screen', path='behavior-lock/snapshots/home.spec.ts/home.png')
        self.assertEqual((answer.status_code, answer.content, answer.headers['content-type']), (200, b'\x89PNG\r\n', 'image/png'))
        for path, status in (('run.png', 400), ('behavior-lock/snapshots/home.spec.ts/notes.txt', 400),
                             ('behavior-lock/snapshots/../../run.png', 400), ('behavior-lock/snapshots/gone.png', 404)):
            self.assertEqual(self.get('/api/screen', path=path).status_code, status, path)


class FeedOverFlows(Project):
    def test_every_progress_file_is_followed_each_event_naming_its_flow(self):
        check = progress.ProgressLog(self.report)
        check.started(STAGES, list(ORDER), {})
        safety = progress.ProgressLog(self.runtime, 'safety', pulse=False, sampler=None)
        safety.started(behavior_lock.FLOW, [s.name for s in behavior_lock.FLOW], {})
        _, _, app = self.client()
        feed = app.state.ctx.feed
        self.assertEqual(feed.poll(), [], 'what the files held at start is the starting state')
        check.emit('stage.started', stage='facts')
        safety.emit('stage.started', stage='prepare')
        setup = progress.ProgressLog(self.runtime, 'setup', pulse=False, sampler=None)   # a file that appears later
        setup.started(live_setup.FLOW, [s.name for s in live_setup.FLOW], {})
        added = feed.poll()
        self.assertEqual([(e['kind'], e['data']['flow'], e['data']['event']) for e in added],
                         [('progress', 'check', 'stage.started'), ('progress', 'safety', 'stage.started'),
                          ('progress', 'setup', 'run.started')])
        self.assertEqual(added[2]['text'], {'en': 'Setting up your app started', 'ar': 'بدأ تجهيز برنامجك'})
        self.assertEqual([e['seq'] for e in added], sorted(e['seq'] for e in added), 'one numbering for every flow')
        self.assertEqual(feed.poll(), [])
        second = progress.ProgressLog(self.runtime, 'safety', pulse=False, sampler=None)  # a new run: a new inode
        second.started(behavior_lock.FLOW, ['prepare'], {})
        self.assertEqual([(e['data']['flow'], e['data']['event'], e['data']['run']) for e in feed.poll()],
                         [('safety', 'run.started', second.run)])
        for log in (check, safety, setup, second): log.finish('STOPPED')

    def test_history_files_are_not_followed(self):
        _, _, app = self.client()
        kept = progress.history_folder(self.runtime, 'fix')
        kept.mkdir(parents=True)
        (kept / 'old.jsonl').write_text('{"seq": 1, "event": "run.started", "flow": "fix", "run": "old"}\n')
        self.assertEqual(app.state.ctx.feed.poll(), [])


class Watch(Checked):
    """The assistant's long tools open the live map once and answer with its address."""

    def setUp(self):
        super().setUp()
        self.opened = {'studio': 'http://127.0.0.1:9/#/scan?token=k' + 'k' * 20, 'opened_in_browser': True}
        for target, value in ((jobs, 'start'), (jobs, 'wait')):
            patcher = mock.patch.object(target, value, side_effect=self.fake(value))
            patcher.start()
            self.addCleanup(patcher.stop)
        self.studio = mock.patch.object(launch, 'open_studio', return_value=self.opened)
        self.open = self.studio.start()
        self.addCleanup(self.studio.stop)

    @staticmethod
    def fake(name):
        if name == 'start': return lambda kind, project, arguments, runner=None: f'{kind}-1'
        return lambda job, seconds: {'status': 'running', 'progress': {'done': 0, 'total': 26}, 'started': 'now'}

    def ready(self):
        state = guided.load(self.project)
        state['setup'] = {'commit': state['scanned_commit'], 'ok': True}
        state['consent'] = {'run_and_fix': True}
        guided.save(state)

    def test_each_long_tool_answers_with_the_live_map(self):
        self.ready()
        detected = {'profile': {'start': [['npm', 'run', 'dev']]}, 'limitations': []}
        with mock.patch.object(live_setup, 'authorize'), mock.patch.object(live_setup, 'detect', return_value=detected), \
                mock.patch.object(live_setup, 'write_profile'):
            answers = {'run_setup': agent_tools.run_setup(str(self.project), person_agreed=True),
                       'safety_net': agent_tools.safety_net(str(self.project)),
                       'fix_start': agent_tools.fix_start(str(self.project), cards=['TASK-001']),
                       'audit': agent_tools.audit(str(self.project), fresh=True)}
        for name, answer in answers.items():
            self.assertEqual((answer['status'], answer['watch']), ('running', self.opened['studio']), name)
            self.assertTrue(answer['what_now'].startswith('Tell the person the live map'), name)
            self.assertIn('Call `wait`', answer['what_now'], name)
        self.assertEqual(self.open.call_args_list, [mock.call(str(self.project), show=True, route='/scan')] * 4, 'once per tool')

    def test_a_run_the_studio_started_does_not_open_another_tab(self):
        with mock.patch.dict(os.environ, {'EAOS_STUDIO_RUN': 'run-1'}):
            agent_tools.audit(str(self.project), fresh=True)
        self.assertEqual(self.open.call_args.kwargs['show'], False)

    def test_an_address_not_opened_is_given_to_the_person(self):
        self.open.return_value = {**self.opened, 'opened_in_browser': False}
        answer = agent_tools.audit(str(self.project), fresh=True)
        self.assertTrue(answer['what_now'].startswith('Before anything else, write the person a message with the `watch` address'))

    def test_the_work_starts_without_its_map_when_the_studio_cannot(self):
        for broken in ({'side_effect': OSError('no port')}, {'return_value': {'error': 'did not start in time'}}):
            self.open.configure_mock(**{'side_effect': None, **broken})
            answer = agent_tools.audit(str(self.project), fresh=True)
            self.assertEqual(answer['status'], 'running')
            self.assertNotIn('watch', answer)

    def test_busy_or_short_tools_do_not_open_it(self):
        with mock.patch.object(jobs, 'running', return_value={'id': 'audit-0', 'kind': 'audit', 'progress': {}}):
            self.assertEqual(agent_tools.audit(str(self.project), fresh=True)['status'], 'busy')
        agent_tools.status(str(self.project))
        self.open.assert_not_called()


class Addresses(unittest.TestCase):
    def test_the_live_map_address_carries_the_token_in_its_route(self):
        record = {'port': 8123, 'token': 't' * 32}
        self.assertEqual(launch.url_of(record), f"http://127.0.0.1:8123/#token={'t' * 32}")
        self.assertEqual(launch.url_of(record, '/scan'), f"http://127.0.0.1:8123/#/scan?token={'t' * 32}")
        routed = {**record, 'remote_origin': 'https://shop--8123.dev.remote.e-m.sa'}
        self.assertEqual(launch.url_of(routed, '/scan'), f"https://shop--8123.dev.remote.e-m.sa/#/scan?token={'t' * 32}",
                         'a Remote record gives its routed address')

    def test_eaos_start_prints_and_opens_the_live_map_when_the_studio_runs(self):
        address = f"http://127.0.0.1:8123/#/scan?token={'t' * 32}"
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(tmp) / 'home')}), \
                mock.patch.object(guided, 'doctor_rows', return_value=[]), mock.patch.object(guided, 'advance', return_value=0), \
                mock.patch.object(launch, 'running', return_value={'port': 8123, 'token': 't' * 32}), \
                mock.patch.object(launch, '_open') as opened, mock.patch.object(guided, 'say') as said:
            project = git_project(Path(tmp) / 'shop')
            cli.main(['start', str(project), '--lang', 'en', '--no-watch'])
            opened.assert_not_called()
            cli.main(['start', str(project), '--lang', 'en'])
        opened.assert_called_once_with(address, True)
        self.assertIn(mock.call(f'Watch the work live on its map: {address}'), said.call_args_list)

    def test_nothing_is_said_when_the_studio_is_not_running(self):
        with mock.patch.object(launch, 'running', return_value=None), mock.patch.object(guided, 'say') as said:
            guided.watch({'lang': 'ar'}, None)
        said.assert_not_called()


class StudioProcess(unittest.TestCase):
    """G12: the Studio open_studio starts never imports an `eaos` from the project (EAOS checking itself)."""

    def test_a_project_with_its_own_eaos_package_is_not_imported(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(tmp) / 'home')}):
            project = git_project(Path(tmp) / 'eaos-repo')
            marker = Path(tmp) / 'imported'
            (project / 'eaos').mkdir()
            (project / 'eaos' / '__init__.py').write_text(f'open({str(marker)!r}, "w").write("the checked code")\nraise SystemExit(3)\n')
            (project / 'eaos' / '__main__.py').write_text(f'open({str(marker)!r}, "w").write("the checked code")\n')
            opened = launch.open_studio(str(project), show=False, route='/scan')
            record = launch.running(agent_tools.project_state(str(project)))
            try:
                self.assertEqual((opened.get('started'), opened.get('error')), (True, None), opened)
                self.assertIn('/#/scan?token=', opened['studio'])
                self.assertFalse(marker.exists(), 'the started Studio imported the project\'s own eaos')
            finally:
                if record: os.kill(record['pid'], signal.SIGTERM)
            deadline = time.monotonic() + 10
            while record and time.monotonic() < deadline and launch._alive(record['pid']): time.sleep(0.1)


if __name__ == '__main__':
    unittest.main()
