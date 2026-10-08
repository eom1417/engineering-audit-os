"""The Studio's local server (eaos/api/): the guard, the read API generated from the schemas, the live feed, the
stream with its replay, the mount point of the action API, and `eaos studio` / `open_studio` on a real project."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))

from starlette.routing import Route  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from eaos import artifact_contracts  # noqa: E402
from eaos.api import events as feed_module, guard, read, server  # noqa: E402
from eaos.studio import export  # noqa: E402
import studio_live_trial  # noqa: E402
import studio_synthetic  # noqa: E402

PORT = 48123


def report_with_data(where, cards=30):
    folder = Path(where) / 'report' / 'studio'
    problems = studio_synthetic.write(folder, studio_synthetic.build(cards=cards, components=6))
    assert not problems, problems
    return folder.parent


def client(report, mounts=None):
    keys = server.Keys(port=PORT)
    app = server.create_app(report, name='shop', keys=keys, mounts=mounts or [], watch=False)
    return TestClient(app, base_url=f'http://127.0.0.1:{PORT}'), keys, app


class Guard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.report = report_with_data(self.tmp.name)

        def mount(ctx):
            async def echo(request):
                return JSONResponse({'ok': True, 'body': (await request.json())})
            return [Route('/api/test/echo', echo, methods=['POST'])]
        self.http, self.keys, _ = client(self.report, [mount])
        self.token = {'X-EAOS-Token': self.keys.token}

    def test_the_api_refuses_without_the_token_and_with_a_wrong_one(self):
        self.assertEqual(self.http.get('/api/session').status_code, 401)
        self.assertEqual(self.http.get('/api/session', headers={'X-EAOS-Token': self.keys.token[:-1] + 'x'}).status_code, 401)
        self.assertEqual(self.http.get('/api/sections/cards').status_code, 401)
        self.assertEqual(self.http.get('/api/events').status_code, 401)
        answer = self.http.get('/api/session', headers=self.token)
        self.assertEqual(answer.status_code, 200)
        self.assertEqual(answer.json()['mode'], 'live')

    def test_another_host_name_is_refused_even_with_the_token(self):
        answer = self.http.get('/api/session', headers={**self.token, 'Host': f'evil.example:{PORT}'})
        self.assertEqual(answer.status_code, 421, 'DNS rebinding: a page that renames itself 127.0.0.1 is refused')
        self.assertEqual(self.http.get('/', headers={'Host': 'evil.example'}).status_code, 421)
        self.assertEqual(self.http.get('/api/session', headers={**self.token, 'Host': f'localhost:{PORT}'}).status_code, 200)

    def test_a_write_needs_csrf_and_this_origin(self):
        csrf = self.http.get('/api/session', headers=self.token).json()['csrf']
        origin = {'Origin': f'http://127.0.0.1:{PORT}'}
        post = lambda headers: self.http.post('/api/test/echo', json={'a': 1}, headers=headers).status_code
        self.assertEqual(post(self.token), 403)
        self.assertEqual(post({**self.token, 'X-EAOS-CSRF': csrf}), 403, 'no Origin')
        self.assertEqual(post({**self.token, 'X-EAOS-CSRF': csrf, 'Origin': 'http://evil.example'}), 403)
        self.assertEqual(post({**self.token, 'X-EAOS-CSRF': csrf[::-1] + 'x', **origin}), 403)
        self.assertEqual(post({'X-EAOS-CSRF': csrf, **origin}), 401)
        self.assertEqual(post({**self.token, 'X-EAOS-CSRF': csrf, **origin}), 200)
        self.assertEqual(post({**self.token, 'X-EAOS-CSRF': csrf, 'Referer': f'http://localhost:{PORT}/#/problems'}), 200)

    def test_the_read_api_has_no_write(self):
        csrf = self.http.get('/api/session', headers=self.token).json()['csrf']
        headers = {**self.token, 'X-EAOS-CSRF': csrf, 'Origin': f'http://127.0.0.1:{PORT}'}
        for path in ('/api/session', '/api/manifest', '/api/sections/cards', '/api/openapi.json'):
            self.assertIn(self.http.post(path, headers=headers).status_code, (404, 405), path)
        self.assertEqual(self.http.post('/', headers=headers).status_code, 405)

    def test_the_token_is_compared_in_constant_time(self):
        with mock.patch('hmac.compare_digest', wraps=__import__('hmac').compare_digest) as compare:
            self.http.get('/api/session', headers=self.token)
        self.assertTrue(compare.called)
        self.assertFalse(guard.same(None, 'x'))
        self.assertFalse(guard.same('', ''))

    def test_the_token_never_reaches_a_log_or_the_page(self):
        wrong = self.keys.token[::-1]
        with self.assertLogs('eaos.studio.server', level='WARNING') as logged:
            self.http.get('/api/session', headers={'X-EAOS-Token': wrong})
            self.http.post('/api/test/echo', json={}, headers=self.token)
        text = '\n'.join(logged.output)
        self.assertIn('token', text)
        self.assertIn('csrf', text, 'a refusal says why')
        for secret in (self.keys.token, wrong, self.keys.csrf):
            self.assertNotIn(secret, text)
        self.assertNotIn(self.keys.token, self.http.get('/').text)
        self.assertNotIn(self.keys.token, self.http.get('/api/session', headers=self.token).text)
        boot = (server.ASSETS / 'boot.js').read_text(encoding='utf-8')
        self.assertIn("sessionStorage.setItem('eaos.token'", boot)
        self.assertIn("history.replaceState(null, '', location.pathname + location.search + route)", boot, 'the token leaves the address')

    def test_it_listens_on_loopback_only(self):
        with self.assertRaises(ValueError):
            server.bind(0, host='0.0.0.0')
        sock = server.bind(0)
        self.addCleanup(sock.close)
        self.assertEqual(sock.getsockname()[0], '127.0.0.1')


class ReadApi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.report = report_with_data(self.tmp.name)
        self.http, self.keys, _ = client(self.report)
        self.headers = {'X-EAOS-Token': self.keys.token}

    def get(self, path):
        return self.http.get(path, headers=self.headers)

    def test_every_section_of_the_contract_has_its_route_and_its_schema(self):
        contract = {name[len('studio-'):] for name in artifact_contracts.contracts() if name.startswith('studio-')} - {'manifest'}
        self.assertEqual(set(read.section_schemas()), contract)
        spec = self.get('/api/openapi.json').json()
        self.assertEqual(spec['openapi'], '3.1.0')
        for name in contract:
            path = spec['paths'][f'/api/sections/{name}']['get']
            self.assertEqual(path['responses']['200']['content']['application/json']['schema'], {'$ref': f'/api/schemas/{name}'})
            self.assertEqual(self.get(f'/api/schemas/{name}').json(), artifact_contracts.contracts()[f'studio-{name}'])

    def test_a_section_is_the_file_the_exporter_wrote_byte_for_byte(self):
        folder = self.report / 'studio'
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(self.get('/api/manifest').content, (folder / 'manifest.json').read_bytes())
        for entry in manifest['sections']:
            body = self.get(f"/api/sections/{entry['name']}")
            self.assertEqual(body.status_code, 200, entry['name'])
            self.assertEqual(hashlib.sha256(body.content).hexdigest(), entry['sha256'], entry['name'])
            self.assertEqual(body.headers['cache-control'], 'no-store')

    def test_an_unwritten_section_answers_with_its_coverage_row_and_an_unknown_one_is_refused(self):
        folder = self.report / 'studio'
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        manifest['sections'] = [s for s in manifest['sections'] if s['name'] != 'functions']
        (folder / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        answer = self.get('/api/sections/functions')
        self.assertEqual(answer.status_code, 404)
        self.assertEqual(answer.json()['error'], 'not_written')
        self.assertEqual(answer.json()['coverage']['section'], 'functions')
        self.assertEqual(self.get('/api/sections/..%2F..%2Fetc').status_code, 404)
        self.assertEqual(self.get('/api/sections/secrets').json()['error'], 'unknown')

    def test_no_check_yet_is_an_empty_state(self):
        empty = Path(self.tmp.name) / 'empty'
        (empty / 'studio').mkdir(parents=True)
        http, keys, _ = client(empty)
        answer = http.get('/api/manifest', headers={'X-EAOS-Token': keys.token})
        self.assertEqual((answer.status_code, answer.json()['error']), (404, 'empty'))
        self.assertEqual(http.get('/api/session', headers={'X-EAOS-Token': keys.token}).json()['sections'], [])

    def test_the_page_may_call_this_server_and_nothing_else_and_the_assets_stay_in_their_folder(self):
        page = self.http.get('/')
        self.assertEqual(page.status_code, 200)
        self.assertIn("connect-src 'self'", page.text)
        self.assertNotIn("connect-src 'none'", page.text)
        self.assertNotIn(self.keys.token, page.text, 'the page itself never holds the token')
        snapshot = (server.ASSETS / 'index.html').read_text(encoding='utf-8')
        self.assertIn("connect-src 'none'", snapshot, 'opened from a file, the Studio stays offline')
        self.assertEqual(self.http.get('/boot.js').status_code, 200)
        self.assertEqual(self.http.get('/assets/studio.js').status_code, 200)
        for path in ('/../eaos/api/guard.py', '/%2e%2e/%2e%2e/pyproject.toml', '/SOURCE.json/../../cli.py', '/nope.js'):
            self.assertEqual(self.http.get(path).status_code, 404, path)

    def test_the_session_names_the_feed_and_whether_actions_are_mounted(self):
        session = self.get('/api/session').json()
        self.assertEqual(session['feed']['source'], 'manifest')
        self.assertFalse(session['actions'])
        self.assertIn('cards', session['sections'])
        self.assertNotIn('token', json.dumps(session).lower().replace('csrf', ''))


class FeedEvents(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.report = report_with_data(self.tmp.name)
        self.folder = self.report / 'studio'
        self.feed = feed_module.Feed(self.report)
        self.assertEqual(self.feed.poll(), [], 'the state the feed starts from is not an event')

    def kinds(self, events):
        return [e['kind'] for e in events]

    def test_each_event_kind_comes_from_what_changed_in_the_manifest(self):
        cards = json.loads((self.folder / 'cards.json').read_text(encoding='utf-8'))
        opened = sorted(c['id'] for c in cards['cards'] if c['state'] == 'open')
        studio_live_trial.mutate(self.folder, 'scan', 1)
        got = self.feed.poll()
        self.assertEqual(self.kinds(got), ['scan.done'])
        self.assertEqual(set(got[0]['sections']), {'head'})
        self.assertEqual(got[0]['source'], 'manifest')
        studio_live_trial.mutate(self.folder, 'batch', 2)
        got = self.feed.poll()
        self.assertEqual(self.kinds(got), ['batch.delivered'])
        self.assertEqual(got[0]['data']['cards'], [opened[0]])
        studio_live_trial.mutate(self.folder, 'merge', 3)
        self.assertEqual(self.kinds(self.feed.poll()), ['branch.merged'])
        studio_live_trial.mutate(self.folder, 'decision', 4)
        got = self.feed.poll()
        self.assertEqual(self.kinds(got), ['decision.asked'])
        self.assertEqual(got[0]['data']['decisions'], ['live-4'])
        self.assertEqual(self.feed.poll(), [], 'nothing changed, nothing published')
        decisions = json.loads((self.folder / 'decisions.json').read_text(encoding='utf-8'))
        decisions['decisions'][0].update(state='answered', answer='yes')
        studio_live_trial.publish(self.folder, {'decisions': decisions})
        self.assertEqual(self.kinds(self.feed.poll()), ['decision.answered'])
        studio_live_trial.publish(self.folder, {'docs': {**json.loads((self.folder / 'docs.json').read_text(encoding='utf-8')), 'docs': []}})
        self.assertEqual(self.kinds(self.feed.poll()), ['studio.updated'])

    def test_every_event_has_both_languages_and_a_growing_number(self):
        for n, kind in enumerate(studio_live_trial.KINDS, 1):
            studio_live_trial.mutate(self.folder, kind, n)
            self.feed.poll()
        rows = list(self.feed.events)
        self.assertEqual([r['seq'] for r in rows], list(range(1, len(rows) + 1)))
        for row in rows:
            self.assertTrue(row['text']['en'] and row['text']['ar'])
            self.assertTrue(row['id'].startswith(self.feed.epoch + '-'))

    def test_a_missed_event_is_replayed_and_a_foreign_or_too_old_id_asks_for_a_reset(self):
        start = self.feed.last_id()
        for n, kind in enumerate(studio_live_trial.KINDS, 1):
            studio_live_trial.mutate(self.folder, kind, n)
            self.feed.poll()
        missed, reset = self.feed.since(start)
        self.assertFalse(reset)
        self.assertEqual(self.kinds(missed), ['scan.done', 'batch.delivered', 'branch.merged', 'decision.asked'])
        missed, reset = self.feed.since(missed[1]['id'])
        self.assertEqual((self.kinds(missed), reset), (['branch.merged', 'decision.asked'], False))
        self.assertEqual(self.feed.since('another-3'), ([], True), 'an id of an earlier server')
        self.assertEqual(self.feed.since(f'{self.feed.epoch}-99'), ([], True))
        small = feed_module.Feed(self.report, keep=2)
        first = small.last_id()
        for n in range(3): small.publish('studio.updated')
        self.assertEqual(small.since(first), ([], True), 'older than what the feed keeps')
        self.assertEqual(self.feed.since(None), ([], False))

    def test_the_event_log_is_the_source_once_it_exists(self):
        log = self.report / 'events.jsonl'
        log.write_text(json.dumps({'kind': 'branch.merged', 'seq': 1}) + '\n' + '{"kind": "half', encoding='utf-8')
        got = self.feed.poll()
        self.assertEqual(self.feed.source, 'events')
        self.assertEqual([(e['kind'], e['source']) for e in got], [('branch.merged', 'events')])
        with log.open('a', encoding='utf-8') as handle: handle.write(' written"}\n')
        self.assertEqual([e['kind'] for e in self.feed.poll()], ['half written'], 'a line is read once it is whole')

    def test_an_action_publishes_into_the_same_numbers(self):
        event = self.feed.publish('action', data={'action': 'audit'}, text={'en': 'Check started', 'ar': 'بدأ الفحص'})
        self.assertEqual((event['source'], event['seq']), ('action', 1))


class PlainMount(unittest.TestCase):
    """The hook the action API mounts by: framework-free handlers under the same guard."""

    def test_plain_handlers_mount_next_to_the_read_api(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        report = report_with_data(tmp.name)
        seen = {}

        def mount(ctx):
            seen['ctx'] = ctx
            def runs(call):
                event = ctx.publish('action', {'action': call['body']['action']})
                return 202, {'run': 'r1', 'event': event['id'], 'saw_token': 'x-eaos-token' in call['headers']}
            def listing(call):
                return {'runs': [], 'q': call['query'].get('q')}
            return [('POST', '/api/runs', runs), ('GET', '/api/runs', listing)]
        http, keys, app = client(report, [mount])
        token = {'X-EAOS-Token': keys.token}
        session = http.get('/api/session', headers=token).json()
        self.assertTrue(session['actions'])
        self.assertEqual(http.get('/api/runs?q=x', headers=token).json(), {'runs': [], 'q': 'x'})
        write = {**token, 'X-EAOS-CSRF': session['csrf'], 'Origin': f'http://127.0.0.1:{PORT}'}
        self.assertEqual(http.post('/api/runs', json={'action': 'audit'}, headers=token).status_code, 403)
        answer = http.post('/api/runs', json={'action': 'audit'}, headers=write)
        self.assertEqual(answer.status_code, 202)
        self.assertFalse(answer.json()['saw_token'], 'a handler never sees the token')
        self.assertEqual(app.state.ctx.feed.events[-1]['data'], {'action': 'audit'})
        self.assertIs(seen['ctx'], app.state.ctx)


def _get(url, token=None, timeout=5):
    request = urllib.request.Request(url, headers={'X-EAOS-Token': token} if token else {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response: return response.status, response.read()
    except urllib.error.HTTPError as error: return error.code, error.read()


def sse_frames(port, token, last=None, count=1, timeout=10):
    """The first `count` named frames of the stream, read off a real socket."""
    import http.client
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=timeout)
    headers = {'X-EAOS-Token': token, 'Accept': 'text/event-stream'}
    if last: headers['Last-Event-ID'] = last
    connection.request('GET', '/api/events', headers=headers)
    response = connection.getresponse()
    frames, block = [], {}
    try:
        while len(frames) < count:
            line = response.fp.readline().decode('utf-8').rstrip('\r\n')
            if not line:
                if block.get('event'): frames.append(block)
                block = {}
                continue
            if line.startswith(':'): continue
            field, _, value = line.partition(':')
            block[field] = value.lstrip(' ')
    finally:
        connection.close()
    return response.status, frames


class LiveServer(unittest.TestCase):
    """The real server on a free port: token refusal, a read, and an SSE event after a manifest change."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.report = report_with_data(self.tmp.name)
        self.app = server.create_app(self.report, name='shop')
        self.ctx = self.app.state.ctx
        sock = server.bind(0)
        self.ctx.keys.port = self.port = sock.getsockname()[1]
        servers = []
        self.thread = threading.Thread(target=server.serve, args=(self.app, sock, servers.append), daemon=True)
        self.thread.start()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and _get(f'http://127.0.0.1:{self.port}/api/session', self.ctx.keys.token)[0] != 200:
            time.sleep(0.1)
        def stop():
            servers[0].should_exit = True
            self.thread.join(5)
        self.addCleanup(stop)

    def test_refusal_a_read_and_an_event_after_the_manifest_changes(self):
        base, token = f'http://127.0.0.1:{self.port}', self.ctx.keys.token
        self.assertEqual(_get(f'{base}/api/sections/cards')[0], 401)
        status, body = _get(f'{base}/api/sections/cards', token)
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)['cards']), 30)
        status, frames = sse_frames(self.port, token)
        self.assertEqual((status, frames[0]['event']), (200, 'hello'))
        last = frames[0]['id']
        result = {}
        reader = threading.Thread(target=lambda: result.update(zip(('status', 'frames'), sse_frames(self.port, token, last=last))))
        reader.start()
        time.sleep(0.5)
        written = time.monotonic()
        studio_live_trial.mutate(self.report / 'studio', 'scan', 1)
        reader.join(10)
        self.assertLess(time.monotonic() - written, 5)
        event = json.loads(result['frames'][0]['data'])
        self.assertEqual((result['frames'][0]['event'], event['kind'], event['sections']), ('studio', 'scan.done', ['head']))
        self.assertEqual(result['frames'][0]['id'], event['id'])

    def test_a_reconnect_replays_what_was_missed_and_an_old_server_id_resets(self):
        token = self.ctx.keys.token
        _, frames = sse_frames(self.port, token)
        last = frames[0]['id']
        studio_live_trial.mutate(self.report / 'studio', 'batch', 1)
        studio_live_trial.mutate(self.report / 'studio', 'decision', 2)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and len(self.ctx.feed.events) < 2: time.sleep(0.1)
        _, frames = sse_frames(self.port, token, last=last, count=2)
        self.assertEqual([json.loads(f['data'])['kind'] for f in frames], ['batch.delivered', 'decision.asked'])
        _, frames = sse_frames(self.port, token, last='deadbeef-7')
        self.assertEqual(frames[0]['event'], 'reset')


class Commands(unittest.TestCase):
    """`eaos studio` and `open_studio` on a real project folder, with their own EAOS home."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        from test_mcp import git_project
        self.project = git_project(Path(self.tmp.name) / 'shop')
        self.env = {**os.environ, 'EAOS_HOME': str(Path(self.tmp.name) / 'home'), 'PYTHONPATH': str(ROOT)}
        patcher = mock.patch.dict(os.environ, {'EAOS_HOME': self.env['EAOS_HOME']})
        patcher.start()
        self.addCleanup(patcher.stop)

    def records(self):
        return list((Path(self.env['EAOS_HOME']) / 'studio').glob('*.json'))

    def test_eaos_studio_serves_until_stopped_and_a_second_one_reuses_it(self):
        process = subprocess.Popen([sys.executable, '-m', 'eaos', 'studio', str(self.project), '--no-open'], env=self.env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: process.poll() is None and process.kill())
        line = process.stdout.readline()
        self.assertIn('EAOS Studio, live: http://127.0.0.1:', line)
        url = line.split('live: ', 1)[1].strip()
        base, token = url.split('/#token=')
        self.assertEqual(_get(f'{base}/api/session')[0], 401)
        status, body = _get(f'{base}/api/session', token)
        self.assertEqual((status, json.loads(body)['project']['name']), (200, 'shop'))
        self.assertEqual(_get(f'{base}/api/manifest', token)[0], 404, 'not checked yet: the empty state')
        [record] = self.records()
        self.assertEqual(oct(record.stat().st_mode & 0o777), '0o600')
        again = subprocess.run([sys.executable, '-m', 'eaos', 'studio', str(self.project), '--no-open'], env=self.env,
                               capture_output=True, text=True, timeout=60)
        self.assertIn('already open', again.stdout)
        self.assertIn(token, again.stdout)
        process.terminate()
        process.wait(10)
        self.assertEqual(self.records(), [], 'a stopped server leaves no record behind')

    def test_open_studio_starts_it_in_the_background_and_reuses_it(self):
        from eaos.api import launch
        first = launch.open_studio(str(self.project), show=False)
        [record] = self.records()
        pid = json.loads(record.read_text(encoding='utf-8'))['pid']
        def stop():
            try: os.kill(pid, 15)
            except OSError: pass
        self.addCleanup(stop)
        self.assertTrue(first['started'] and first['live'])
        self.assertFalse(first['checked'])
        self.assertTrue(first['studio'].startswith('http://127.0.0.1:'))
        second = launch.open_studio(str(self.project), show=False)
        self.assertEqual((second['studio'], second['started']), (first['studio'], False))
        stop()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and launch._alive(pid): time.sleep(0.1)
        self.assertIsNone(launch.running(launch.prepare(str(self.project))[0]), 'a dead server is not reused')

    def test_open_studio_is_an_mcp_tool_and_eaos_studio_a_grouped_command(self):
        import asyncio
        from eaos.command_groups import group_of
        from eaos.mcp_server import build
        tools = {tool.name: tool for tool in asyncio.run(build().list_tools())}
        self.assertIn('open_studio', tools)
        annotations = tools['open_studio'].annotations
        self.assertTrue(getattr(annotations, 'read_only_hint', None) or getattr(annotations, 'readOnlyHint', None))
        self.assertEqual(group_of('studio'), 'start')


if __name__ == '__main__':
    unittest.main()
