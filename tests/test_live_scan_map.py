"""The live scan map (owner request 2026-10-09): the check writes its own progress, the Studio's server follows it.

The pipeline appends one line per event to <report>/run-progress.jsonl (eaos/pipeline/progress.py); the live feed
publishes each new line as a `progress` event (eaos/api/events.py); /api/scan-progress gives the folded state and
each stage's place (eaos/api/read.py). Fake runners stand in for the real stages, so the order is the declaration's
own and every case runs in a moment.
"""
import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'tools'))

from eaos.api import read, server  # noqa: E402
from eaos.pipeline import MANIFEST, STAGES, SkipStage, check, execute, progress, resume  # noqa: E402
from eaos.pipeline.stages import ORDER  # noqa: E402
from test_pipeline_run import fake_runners  # noqa: E402
from test_studio_api import _get, client, report_with_data, sse_frames  # noqa: E402

COMPARED = ('status', 'reason', 'seconds', 'artifacts')


def stepping_runners(**behaviour):
    """The fake runners, with `facts` and `engines` reporting steps the way the real ones do."""
    runners = fake_runners(**behaviour)
    plain_facts, plain_engines = runners['facts'], runners['engines']

    def facts(context):
        names = ['syntax', 'resolve', 'graph']
        for name in names: context.step(name, 0, len(names), 'waiting')
        for done, name in enumerate(names):
            context.step(name, done, len(names), 'running')
            context.step(name, done + 1, len(names), 'ok', 0.01)
        return plain_facts(context)

    def engines(context):
        context.step('semgrep', 0, 2, 'waiting')
        context.step('trivy', 0, 2, 'waiting')
        context.step('semgrep', 0, 2, 'running')
        context.step('semgrep', 1, 2, 'observed', 0.2)
        context.step('trivy', 1, 2, 'running')
        context.step('trivy', 2, 2, 'unavailable', 0.0, reason='trivy is not installed')
        return plain_engines(context)

    runners.update(facts=facts, engines=engines)
    return runners


def project():
    folder = Path(tempfile.mkdtemp(prefix='scanmap-src-'))
    (folder / 'app.py').write_text('print(1)\n', encoding='utf-8')
    return folder


class ProgressFile(unittest.TestCase):
    def run_check(self, **options):
        out = Path(tempfile.mkdtemp(prefix='scanmap-out-'))
        manifest = execute(project(), out, **options)
        return manifest, out, progress.read(out)

    def assert_folded_equals_manifest(self, state, manifest):
        for row in state['stages']:
            kept = manifest['stages'][row['name']]
            got = {'status': row['state'], 'reason': row['reason'], 'seconds': row['seconds'], 'artifacts': row['artifacts']}
            self.assertEqual(got, {key: kept[key] for key in COMPARED}, row['name'])
        self.assertEqual((state['state'], state['status'], state['counts']), ('done', manifest['status'], manifest['counts']))

    def test_events_come_in_order_and_every_stage_ends_exactly_once(self):
        manifest, out, rows = self.run_check(runners=stepping_runners())
        self.assertEqual([r['seq'] for r in rows], list(range(1, len(rows) + 1)))
        self.assertEqual((rows[0]['event'], rows[-1]['event']), ('run.started', 'run.ended'))
        self.assertEqual([s['name'] for s in rows[0]['stages']], list(ORDER), 'the stages come from stages.py, as data')
        self.assertEqual(rows[0]['stages'][1]['requires'], ['facts'])
        self.assertEqual({r['run'] for r in rows}, {rows[0]['run']})
        ends = [r['stage'] for r in rows if r['event'] == 'stage.ended']
        self.assertEqual(sorted(ends), sorted(ORDER), 'exactly one end per stage')
        for name in ORDER:
            began = [i for i, r in enumerate(rows) if r['event'] == 'stage.started' and r['stage'] == name]
            ended = [i for i, r in enumerate(rows) if r['event'] == 'stage.ended' and r['stage'] == name]
            self.assertEqual(len(began), 1, name)
            self.assertLess(began[0], ended[0], name)
            steps = [i for i, r in enumerate(rows) if r['event'] == 'stage.step' and r['stage'] == name]
            self.assertTrue(all(began[0] < i < ended[0] for i in steps), f'{name}: its steps sit inside it')
            for need in BY_REQUIRES[name]:
                need_end = next(i for i, r in enumerate(rows) if r['event'] == 'stage.ended' and r['stage'] == need)
                self.assertLess(need_end, began[0], f'{name} starts after {need} ended')
        self.assert_folded_equals_manifest(progress.fold(rows), manifest)

    def test_steps_of_the_long_stages_are_folded_with_their_own_status(self):
        _, _, rows = self.run_check(runners=stepping_runners())
        state = progress.fold(rows)
        by = {s['name']: s for s in state['stages']}
        self.assertEqual([(s['name'], s['status']) for s in by['facts']['steps']], [('syntax', 'ok'), ('resolve', 'ok'), ('graph', 'ok')])
        engines = {s['name']: s for s in by['engines']['steps']}
        self.assertEqual(engines['semgrep']['status'], 'observed')
        self.assertEqual((engines['trivy']['status'], engines['trivy']['reason']), ('unavailable', 'trivy is not installed'))
        self.assertEqual(by['claims']['steps'], [], 'other stages keep stage-level progress only')

    def test_blocked_and_unavailable_stages_carry_their_reason_when_decided(self):
        manifest, _, rows = self.run_check(runners=stepping_runners(probe=RuntimeError('boom'), semantic=SkipStage('no provider')))
        ended = {r['stage']: r for r in rows if r['event'] == 'stage.ended'}
        self.assertEqual((ended['semantic']['status'], ended['semantic']['reason']), ('unavailable', 'no provider'))
        self.assertEqual(ended['probe']['status'], 'failed')
        self.assertIn('boom', ended['probe']['reason'])
        self.assertEqual(ended['plan']['status'], 'not_reached')
        self.assertIn('probe', ended['plan']['reason'])
        self.assertFalse(any(r['event'] == 'stage.started' and r['stage'] == 'plan' for r in rows), 'a blocked stage never starts')
        self.assert_folded_equals_manifest(progress.fold(rows), manifest)

    def test_not_requested_and_resumed_stages_also_end_once(self):
        manifest, out, rows = self.run_check(only=['facts', 'features'], runners=stepping_runners())
        ended = [r for r in rows if r['event'] == 'stage.ended']
        self.assertEqual(len(ended), len(STAGES))
        self.assertEqual({r['stage']: r['reason'] for r in ended if r['status'] == 'skipped'}['claims'], 'not requested in this run')
        self.assert_folded_equals_manifest(progress.fold(rows), manifest)
        # a failed run, resumed: the stages it kept end at once, marked resumed
        first = execute(project_dir := project(), out2 := Path(tempfile.mkdtemp()), runners=stepping_runners(probe=RuntimeError('x')))
        self.assertEqual(first['stages']['probe']['status'], 'failed')
        again = resume(project_dir, out2, runners=stepping_runners())
        rows = progress.read(out2)
        state = progress.fold(rows)
        by = {s['name']: s for s in state['stages']}
        self.assertTrue(by['facts']['resumed'])
        self.assertEqual(by['facts']['state'], 'ok')
        self.assertFalse(by['probe']['resumed'])
        self.assertEqual(again['stages']['probe']['status'], 'ok')
        self.assertEqual(len([r for r in rows if r['event'] == 'stage.ended']), len(STAGES))

    def test_a_check_asked_for_starts_afresh_unless_the_last_run_did_not_end(self):
        folder, out = project(), Path(tempfile.mkdtemp())
        execute(folder, out, runners=fake_runners())
        check(folder, out, runners=fake_runners())
        rows = progress.read(out)
        started = {r['stage'] for r in rows if r['event'] == 'stage.started'}
        self.assertEqual(started, set(ORDER), 'a complete report is checked again from the start')
        self.assertFalse(any(r.get('resumed') for r in rows))
        with self.assertRaises(KeyboardInterrupt):
            execute(folder, out, runners=fake_runners(probe=KeyboardInterrupt()))
        check(folder, out, runners=fake_runners())
        by = {s['name']: s for s in progress.fold(progress.read(out))['stages']}
        self.assertTrue(by['facts']['resumed'], 'a stopped run goes on from where it stopped')
        self.assertFalse(by['probe']['resumed'])

    def test_a_run_that_breaks_says_so_and_a_new_run_is_a_new_file(self):
        out = Path(tempfile.mkdtemp())
        execute(project(), out, runners=fake_runners())
        first = (out / progress.PROGRESS).stat().st_ino
        previous_run = progress.read(out)[0]['run']
        from unittest import mock
        with mock.patch('eaos.pipeline.run._manifest', side_effect=RuntimeError('disk full')):
            with self.assertRaises(RuntimeError):
                execute(project(), out, runners=fake_runners())
        rows = progress.read(out)
        self.assertNotEqual(rows[0]['run'], previous_run)
        self.assertNotEqual((out / progress.PROGRESS).stat().st_ino, first, 'a new run replaces the file (a new inode)')
        self.assertEqual((rows[-1]['event'], rows[-1]['status']), ('run.ended', 'ERROR'))
        self.assertIn('disk full', rows[-1]['reason'])
        self.assertEqual(rows[0]['previous']['facts'], 0.0, 'the last run\'s seconds per stage, for an estimate')

    def test_a_run_whose_process_is_gone_is_interrupted_not_running_for_ever(self):
        out = Path(tempfile.mkdtemp())
        log = progress.ProgressLog(out)
        log.started(STAGES, list(ORDER), {})
        log.emit('stage.started', stage='facts')
        state = progress.fold(progress.read(out))
        self.assertIs(progress.alive(state), True, 'this process is alive')
        dead = 2 ** 22 + 12345
        while True:
            try: os.kill(dead, 0); dead += 1
            except ProcessLookupError: break
            except PermissionError: dead += 1
        state['pid'] = dead
        self.assertIs(progress.alive(state), False)
        state['host'] = 'another-machine'
        self.assertIsNone(progress.alive(state), 'another machine: cannot be told')

    def test_writing_progress_never_breaks_the_run(self):
        out = Path(tempfile.mkdtemp())
        (out / progress.PROGRESS).mkdir()               # the path cannot be written as a file
        manifest = execute(project(), out, runners=fake_runners())
        self.assertEqual(manifest['status'], 'COMPLETE')


BY_REQUIRES = {s.name: s.requires for s in STAGES}


class ProgressApi(unittest.TestCase):
    """The file reaches the page: the folded state for a page opened mid-run, and the events after it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.report = report_with_data(self.tmp.name)

    def test_a_page_opened_mid_run_gets_the_whole_state_with_places(self):
        log = progress.ProgressLog(self.report)
        log.started(STAGES, list(ORDER), {'facts': 12.0})
        log.emit('stage.started', stage='facts')
        log.stepper('facts')('syntax', 0, 19, 'running')
        log.ended({'stage': 'facts', 'status': 'ok', 'reason': '', 'seconds': 3.2, 'necessity': 'required',
                   'artifacts': ['facts/index.json'], 'detail': {'facts': 120, 'exclude': ['a', 'b']}})
        log.emit('stage.started', stage='features')
        http, keys, _ = client(self.report)
        answer = http.get('/api/scan-progress', headers={'X-EAOS-Token': keys.token})
        self.assertEqual(answer.status_code, 200)
        body = answer.json()
        by = {s['name']: s for s in body['stages']}
        self.assertEqual((body['state'], by['facts']['state'], by['features']['state'], by['claims']['state']),
                         ('running', 'ok', 'running', 'waiting'))
        self.assertEqual(by['facts']['detail'], {'facts': 120}, 'only short scalars of what a stage reported')
        self.assertEqual(by['facts']['steps'][0]['name'], 'syntax')
        self.assertEqual((by['facts']['layer'], by['features']['layer']), (0, 1), 'placed by the layered layout')
        self.assertTrue(all(by[n]['layer'] > by[need]['layer'] for n in by for need in by[n]['requires']))
        self.assertEqual(body['previous'], {'facts': 12.0})
        self.assertNotIn('pid', body)
        self.assertTrue(body['now'] and body['feed_last'])
        self.assertEqual(http.get('/api/scan-progress').status_code, 401, 'the token guards it like every /api/ route')
        self.assertIn('/api/scan-progress', http.get('/api/openapi.json', headers={'X-EAOS-Token': keys.token}).json()['paths'])

    def test_no_check_yet_is_the_declared_stages_waiting(self):
        http, keys, _ = client(self.report)
        body = http.get('/api/scan-progress', headers={'X-EAOS-Token': keys.token}).json()
        self.assertEqual((body['state'], [s['name'] for s in body['stages']]), ('none', list(ORDER)))
        self.assertEqual({s['state'] for s in body['stages']}, {'waiting'})

    def test_the_feed_publishes_new_lines_only_and_follows_a_new_run(self):
        log = progress.ProgressLog(self.report)
        log.started(STAGES, list(ORDER), {})
        _, _, app = client(self.report)
        feed = app.state.ctx.feed
        self.assertEqual(feed.poll(), [], 'what the file held at start is the starting state, not events')
        log.emit('stage.started', stage='facts')
        added = feed.poll()
        self.assertEqual([(e['kind'], e['source'], e['data']['event']) for e in added], [('progress', 'progress', 'stage.started')])
        self.assertEqual(added[0]['text'], {'en': 'Stage facts started', 'ar': 'بدأت مرحلة facts'})
        with (self.report / progress.PROGRESS).open('a', encoding='utf-8') as handle:
            handle.write('{"seq": 3, "event": "stage.ste')                       # half a line
        self.assertEqual(feed.poll(), [], 'a line still being written waits')
        with (self.report / progress.PROGRESS).open('a', encoding='utf-8') as handle:
            handle.write('p", "stage": "facts", "step": "syntax"}\n')
        self.assertEqual([e['data']['step'] for e in feed.poll()], ['syntax'])
        second = progress.ProgressLog(self.report)
        second.started(STAGES, ['facts'], {})
        added = feed.poll()
        self.assertEqual([(e['data']['event'], e['data']['run']) for e in added], [('run.started', second.run)])


class ProgressStream(unittest.TestCase):
    """The real server: events written to run-progress.jsonl arrive on /api/events, and a reconnect replays them."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.report = report_with_data(self.tmp.name)
        self.app = server.create_app(self.report, name='shop')
        self.ctx = self.app.state.ctx
        sock = server.bind(0)
        self.ctx.keys.port = self.port = sock.getsockname()[1]
        servers = []
        thread = threading.Thread(target=server.serve, args=(self.app, sock, servers.append), daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and _get(f'http://127.0.0.1:{self.port}/api/session', self.ctx.keys.token)[0] != 200:
            time.sleep(0.1)
        def stop():
            servers[0].should_exit = True
            thread.join(5)
        self.addCleanup(stop)

    def test_events_reach_the_stream_and_a_reconnect_with_last_event_id_replays_them(self):
        token = self.ctx.keys.token
        _, frames = sse_frames(self.port, token)
        hello = frames[0]['id']
        result = {}
        reader = threading.Thread(target=lambda: result.update(zip(('status', 'frames'), sse_frames(self.port, token, last=hello, count=2))))
        reader.start()
        time.sleep(0.4)
        written = time.monotonic()
        log = progress.ProgressLog(self.report)
        log.started(STAGES, list(ORDER), {})
        log.emit('stage.started', stage='facts')
        reader.join(10)
        self.assertLess(time.monotonic() - written, 5)
        got = [json.loads(f['data']) for f in result['frames']]
        self.assertEqual([(e['kind'], e['data']['event']) for e in got], [('progress', 'run.started'), ('progress', 'stage.started')])
        self.assertEqual([s['name'] for s in got[0]['data']['stages']], list(ORDER))
        # the page lost its connection after the first event: it reconnects with that id and gets what it missed
        log.ended({'stage': 'facts', 'status': 'ok', 'reason': '', 'seconds': 1.0, 'necessity': 'required', 'artifacts': []})
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and len(self.ctx.feed.events) < 3: time.sleep(0.1)
        _, frames = sse_frames(self.port, token, last=result['frames'][0]['id'], count=2)
        self.assertEqual([json.loads(f['data'])['data']['event'] for f in frames], ['stage.started', 'stage.ended'])
        # and what it reads to repaint matches what the events built
        status, body = _get(f'http://127.0.0.1:{self.port}/api/scan-progress', token)
        state = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(state['last_seq'], 3)
        self.assertEqual({s['name']: s['state'] for s in state['stages']}['facts'], 'ok')


if __name__ == '__main__':
    unittest.main()
