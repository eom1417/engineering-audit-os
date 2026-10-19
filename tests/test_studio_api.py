"""The Studio's local server (eaos/api/): the guard, the read API generated from the schemas, the live feed, the
stream with its replay, the mount point of the action API, and `eaos studio` / `open_studio` on a real project."""
import hashlib
import json
import os
import socket
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
import studio_synthetic  # noqa: E402

PORT = 48123
KINDS = ('scan', 'batch', 'merge', 'decision')


def report_with_data(where, cards=30):
    folder = Path(where) / 'report' / 'studio'
    contracts = artifact_contracts.contracts()
    # Only the sections the contract still has: tools/studio_synthetic.py also builds the removed `quality` section.
    sections = {name: body for name, body in studio_synthetic.build(cards=cards, components=6).items() if f'studio-{name}' in contracts}
    problems = studio_synthetic.write(folder, sections)
    assert not problems, problems
    return folder.parent


def client(report, mounts=None):
    keys = server.Keys(port=PORT)
    app = server.create_app(report, name='shop', keys=keys, mounts=mounts or [], watch=False)
    return TestClient(app, base_url=f'http://127.0.0.1:{PORT}'), keys, app


def _load(folder, name):
    return json.loads((Path(folder) / f'{name}.json').read_text(encoding='utf-8'))


def publish(folder, changed):
    """Write the changed sections whole, then the manifest with their new digests: what export.export does."""
    folder = Path(folder)
    manifest = _load(folder, 'manifest')
    for name, data in changed.items():
        blob = export._write(folder, name, data)
        entry = next(s for s in manifest['sections'] if s['name'] == name)
        entry.update(sha256=hashlib.sha256(blob).hexdigest(), bytes=len(blob))
    if 'head' in changed: manifest['scanned'] = changed['head']['scanned']
    export._write(folder, 'manifest', manifest)


def mutate(folder, kind, number):
    """One event on a Studio data folder, written the way the exporter writes it: a new check, a batch delivered, the
    batch merged, a new decision."""
    folder = Path(folder)
    if kind == 'scan':
        head = _load(folder, 'head')
        head['scanned'] = {**head['scanned'], 'commit': hashlib.sha1(f'live-{number}'.encode()).hexdigest()}
        return publish(folder, {'head': head})
    if kind in ('batch', 'merge'):
        cards = _load(folder, 'cards')
        state = 'in_batch' if kind == 'batch' else 'done'
        pool = [c for c in cards['cards'] if c['state'] == ('open' if kind == 'batch' else 'in_batch')]
        min(pool, key=lambda c: c['id'])['state'] = state
        return publish(folder, {'cards': cards})
    decisions = _load(folder, 'decisions')
    decisions['decisions'].insert(0, {'id': f'live-{number}', 'question': f'Live decision {number}?', 'recommendation': 'Keep it.',
                                      'options': [{'id': 'yes', 'label': 'Yes'}, {'id': 'later', 'label': 'Later'}], 'blocks': [],
                                      'state': 'waiting', 'answer': None, 'plan': None, 'asked': '', 'tool': None})
    publish(folder, {'decisions': decisions})


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

    def test_the_token_and_the_host_are_required_compared_safely_and_never_logged_or_shown(self):
        for path in ('/api/session', '/api/sections/cards', '/api/events'):
            self.assertEqual(self.http.get(path).status_code, 401, path)
        wrong = self.keys.token[:-1] + 'x'
        self.assertEqual(self.http.get('/api/session', headers={'X-EAOS-Token': wrong}).status_code, 401)
        with mock.patch('hmac.compare_digest', wraps=__import__('hmac').compare_digest) as compare:
            answer = self.http.get('/api/session', headers=self.token)
        self.assertTrue(compare.called)
        self.assertEqual((answer.status_code, answer.json()['mode']), (200, 'live'))
        self.assertFalse(guard.same(None, 'x') or guard.same('', ''))
        self.assertEqual(self.http.get('/api/session', headers={**self.token, 'Host': f'evil.example:{PORT}'}).status_code, 421,
                         'DNS rebinding: a page that renames itself 127.0.0.1 is refused')
        self.assertEqual(self.http.get('/', headers={'Host': 'evil.example'}).status_code, 421)
        self.assertEqual(self.http.get('/api/session', headers={**self.token, 'Host': f'localhost:{PORT}'}).status_code, 200)
        portless = guard.Guard(None, server.Keys())      # an app made without keys answers on the port it listens on
        scope = lambda host: {'server': ('127.0.0.1', 43381), 'path': '/', 'method': 'GET', 'headers': [(b'host', host)]}
        self.assertIsNone(portless.refusal(scope(b'127.0.0.1:43381')))
        self.assertEqual(portless.refusal(scope(b'evil.example:43381'))[0], 421)
        with self.assertRaises(ValueError):
            server.bind(0, host='0.0.0.0')
        sock = server.bind(0)
        self.addCleanup(sock.close)
        self.assertEqual(sock.getsockname()[0], '127.0.0.1')
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

    def test_a_write_needs_csrf_and_this_origin_and_the_read_api_has_none(self):
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
        headers = {**self.token, 'X-EAOS-CSRF': csrf, **origin}
        for path in ('/api/session', '/api/manifest', '/api/sections/cards', '/api/openapi.json'):
            self.assertIn(self.http.post(path, headers=headers).status_code, (404, 405), path)
        self.assertEqual(self.http.post('/', headers=headers).status_code, 405)


class ReadApi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.report = report_with_data(self.tmp.name)
        self.http, self.keys, _ = client(self.report)
        self.headers = {'X-EAOS-Token': self.keys.token}

    def get(self, path):
        return self.http.get(path, headers=self.headers)

    def test_every_section_is_routed_with_its_schema_and_served_byte_for_byte(self):
        contract = {name[len('studio-'):] for name in artifact_contracts.contracts() if name.startswith('studio-')} - {'manifest'}
        self.assertEqual(set(read.section_schemas()), contract)
        spec = self.get('/api/openapi.json').json()
        self.assertEqual(spec['openapi'], '3.1.0')
        for name in contract:
            path = spec['paths'][f'/api/sections/{name}']['get']
            self.assertEqual(path['responses']['200']['content']['application/json']['schema'], {'$ref': f'/api/schemas/{name}'})
            self.assertEqual(self.get(f'/api/schemas/{name}').json(), artifact_contracts.contracts()[f'studio-{name}'])
        folder = self.report / 'studio'
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(self.get('/api/manifest').content, (folder / 'manifest.json').read_bytes())
        for entry in manifest['sections']:
            body = self.get(f"/api/sections/{entry['name']}")
            self.assertEqual(body.status_code, 200, entry['name'])
            self.assertEqual(hashlib.sha256(body.content).hexdigest(), entry['sha256'], entry['name'])
            self.assertEqual(body.headers['cache-control'], 'no-store')
        # one document of the library is read alone, with the pictures it points at: never the whole library for it
        library = json.loads((folder / 'library.json').read_text(encoding='utf-8'))
        doc = library['documents'][0]
        cut = self.get(f"/api/sections/library?only={doc['id']}").json()
        self.assertEqual([d['id'] for d in cut['documents']], [doc['id']])
        self.assertTrue(all(i['id'].rsplit('/', 1)[-1] in doc['text'] for i in cut['images']))
        session = self.get('/api/session').json()
        self.assertEqual((session['feed']['source'], session['actions']), ('manifest', False))
        self.assertIn('cards', session['sections'])
        self.assertNotIn('token', json.dumps(session).lower().replace('csrf', ''))
        catalog = {'schema_version': 1, 'source_locale': 'ar', 'translations': {'en': {'نعم': 'Yes'}}}
        (folder / 'locale.json').write_text(json.dumps(catalog), encoding='utf-8')
        self.assertEqual(self.http.get('/api/locales/en').status_code, 401, 'a translation sits behind the token too')
        self.assertEqual(self.get('/api/locales/en').json(), catalog)
        self.assertEqual(self.get('/api/locales/ar').status_code, 404)

    def test_an_unwritten_or_unknown_section_and_no_check_yet_answer_plainly(self):
        folder = self.report / 'studio'
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        manifest['sections'] = [s for s in manifest['sections'] if s['name'] != 'functions']
        (folder / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        answer = self.get('/api/sections/functions')
        self.assertEqual((answer.status_code, answer.json()['error']), (404, 'not_written'))
        self.assertEqual(answer.json()['coverage']['section'], 'functions')
        self.assertEqual(self.get('/api/sections/..%2F..%2Fetc').status_code, 404)
        self.assertEqual(self.get('/api/sections/secrets').json()['error'], 'unknown')
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

    def test_each_event_kind_comes_from_what_changed_until_the_event_log_takes_over(self):
        cards = _load(self.folder, 'cards')
        opened = sorted(c['id'] for c in cards['cards'] if c['state'] == 'open')
        mutate(self.folder, 'scan', 1)
        got = self.feed.poll()
        self.assertEqual(self.kinds(got), ['scan.done'])
        self.assertEqual((set(got[0]['sections']), got[0]['source']), ({'head'}, 'manifest'))
        mutate(self.folder, 'batch', 2)
        got = self.feed.poll()
        self.assertEqual((self.kinds(got), got[0]['data']['cards']), (['batch.delivered'], [opened[0]]))
        mutate(self.folder, 'merge', 3)
        self.assertEqual(self.kinds(self.feed.poll()), ['branch.merged'])
        mutate(self.folder, 'decision', 4)
        got = self.feed.poll()
        self.assertEqual((self.kinds(got), got[0]['data']['decisions']), (['decision.asked'], ['live-4']))
        self.assertEqual(self.feed.poll(), [], 'nothing changed, nothing published')
        decisions = _load(self.folder, 'decisions')
        decisions['decisions'][0].update(state='answered', answer='yes')
        publish(self.folder, {'decisions': decisions})
        self.assertEqual(self.kinds(self.feed.poll()), ['decision.answered'])
        publish(self.folder, {'docs': {**_load(self.folder, 'docs'), 'docs': []}})
        self.assertEqual(self.kinds(self.feed.poll()), ['studio.updated'])
        log = self.report / 'events.jsonl'
        log.write_text(json.dumps({'kind': 'branch.merged', 'seq': 1}) + '\n' + '{"kind": "half', encoding='utf-8')
        got = self.feed.poll()
        self.assertEqual(self.feed.source, 'events')
        self.assertEqual([(e['kind'], e['source']) for e in got], [('branch.merged', 'events')])
        with log.open('a', encoding='utf-8') as handle: handle.write(' written"}\n')
        self.assertEqual(self.kinds(self.feed.poll()), ['half written'], 'a line is read once it is whole')

    def test_a_missed_event_is_replayed_and_a_foreign_or_too_old_id_asks_for_a_reset(self):
        start = self.feed.last_id()
        for n, kind in enumerate(KINDS, 1):
            mutate(self.folder, kind, n)
            self.feed.poll()
        action = self.feed.publish('action', data={'action': 'audit'}, text={'en': 'Check started', 'ar': 'بدأ الفحص'})
        self.assertEqual((action['source'], action['seq']), ('action', 5), 'an action is numbered with the rest')
        rows = list(self.feed.events)
        self.assertEqual([r['seq'] for r in rows], list(range(1, len(rows) + 1)))
        for row in rows:
            self.assertTrue(row['text']['en'] and row['text']['ar'])
            self.assertTrue(row['id'].startswith(self.feed.epoch + '-'))
        missed, reset = self.feed.since(start)
        self.assertFalse(reset)
        self.assertEqual(self.kinds(missed), ['scan.done', 'batch.delivered', 'branch.merged', 'decision.asked', 'action'])
        missed, reset = self.feed.since(missed[1]['id'])
        self.assertEqual((self.kinds(missed), reset), (['branch.merged', 'decision.asked', 'action'], False))
        self.assertEqual(self.feed.since('another-3'), ([], True), 'an id of an earlier server')
        self.assertEqual(self.feed.since(f'{self.feed.epoch}-99'), ([], True))
        small = feed_module.Feed(self.report, keep=2)
        first = small.last_id()
        for n in range(3): small.publish('studio.updated')
        self.assertEqual(small.since(first), ([], True), 'older than what the feed keeps')
        self.assertEqual(self.feed.since(None), ([], False))


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


def _fetch(url, headers=None, timeout=5):
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response: return response.status, response.read()
    except urllib.error.HTTPError as error: return error.code, error.read()


def _get(url, token=None, timeout=5):
    return _fetch(url, {'X-EAOS-Token': token} if token else {}, timeout)


FORGED = {'Sec-Fetch-Site': 'same-origin', 'Sec-Fetch-Dest': 'script'}      # what the Studio's own page would send


def _own_address():
    """This computer's address on its network (not loopback), or None."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(('192.0.2.1', 9))           # no packet is sent: it picks the address a reply would come to
            return probe.getsockname()[0]
        except OSError:
            return None


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
    """The real server on a free port: token refusal, a read, an SSE event after a manifest change, and the replay."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.report = report_with_data(self.tmp.name)
        # The feed also tails the tools' install (eaos/api/events.py): this test's own folder, not the computer's.
        patcher = mock.patch.dict(os.environ, {'EAOS_ENGINE_TOOLS': str(Path(self.tmp.name) / 'tools')})
        patcher.start()
        self.addCleanup(patcher.stop)
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

    def test_a_read_an_event_within_seconds_and_a_reconnect_that_replays_what_was_missed(self):
        base, token = f'http://127.0.0.1:{self.port}', self.ctx.keys.token
        self.assertEqual(_get(f'{base}/api/sections/cards')[0], 401)
        status, body = _get(f'{base}/api/sections/cards', token)
        self.assertEqual((status, len(json.loads(body)['cards'])), (200, 30))
        status, frames = sse_frames(self.port, token)
        self.assertEqual((status, frames[0]['event']), (200, 'hello'))
        last = frames[0]['id']
        result = {}
        reader = threading.Thread(target=lambda: result.update(zip(('status', 'frames'), sse_frames(self.port, token, last=last))))
        reader.start()
        time.sleep(0.5)
        written = time.monotonic()
        mutate(self.report / 'studio', 'scan', 1)
        reader.join(10)
        self.assertLess(time.monotonic() - written, 5)
        event = json.loads(result['frames'][0]['data'])
        self.assertEqual((result['frames'][0]['event'], event['kind'], event['sections']), ('studio', 'scan.done', ['head']))
        self.assertEqual(result['frames'][0]['id'], event['id'])
        last = event['id']
        mutate(self.report / 'studio', 'batch', 2)
        mutate(self.report / 'studio', 'decision', 3)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and len(self.ctx.feed.events) < 3: time.sleep(0.1)
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
        self.env = {**{k: v for k, v in os.environ.items() if k != 'EAOS_REMOTE_ORIGIN'}, 'EAOS_HOME': str(Path(self.tmp.name) / 'home'), 'PYTHONPATH': str(ROOT)}
        patcher = mock.patch.dict(os.environ, {'EAOS_HOME': self.env['EAOS_HOME']})
        patcher.start()
        self.addCleanup(patcher.stop)

    def records(self):
        return list((Path(self.env['EAOS_HOME']) / 'studio').glob('*.json'))

    def studio(self):
        process = subprocess.Popen([sys.executable, '-m', 'eaos', 'studio', str(self.project), '--no-open'], env=self.env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: process.poll() is None and process.kill())
        return process

    def stop_later(self, pid):
        def stop():
            try: os.kill(pid, 15)
            except OSError: pass
        self.addCleanup(stop)
        return stop

    def test_eaos_studio_serves_until_stopped_is_reused_and_gives_its_token_in_its_address_only(self):
        process = self.studio()
        line = process.stdout.readline()
        self.assertIn('EAOS Studio, live: http://127.0.0.1:', line)
        url = line.split('live: ', 1)[1].strip()
        base, token = url.split('/#token=')
        page = _fetch(f'{base}/', {'Sec-Fetch-Site': 'none', 'Sec-Fetch-Dest': 'document'})[1].decode('utf-8')
        self.assertNotIn('live-token.js', page, 'the address carries the token; the page never asks the server for it')
        self.assertEqual(_fetch(f'{base}/live-token.js', FORGED)[0], 404, "another program on this computer, with the page's headers")
        self.assertEqual(_get(f'{base}/api/session')[0], 401)
        status, body = _get(f'{base}/api/session', token)
        self.assertEqual((status, json.loads(body)['project']['name']), (200, 'shop'))
        self.assertEqual(_get(f'{base}/api/manifest', token)[0], 404, 'not checked yet: the empty state')
        [record] = self.records()
        self.assertEqual(oct(record.stat().st_mode & 0o777), '0o600')
        again = subprocess.run([sys.executable, '-m', 'eaos', 'studio', str(self.project), '--no-open'], env=self.env,
                               capture_output=True, text=True, timeout=60)
        self.assertIn('already open', again.stdout)
        self.assertIn(url, again.stdout)
        process.terminate()
        process.wait(10)
        self.assertEqual(self.records(), [], 'a stopped server leaves no record behind')
        restarted = self.studio()
        self.assertIn(url, restarted.stdout.readline(), 'a restarted Studio keeps its address')
        self.assertEqual(_get(f'{base}/api/session', token)[0], 200, 'and its token: a saved address keeps working')
        restarted.terminate()
        restarted.wait(10)

    def test_in_the_background_on_a_remote_server_the_studio_gives_its_plain_remote_address(self):
        env = {**self.env, 'EAOS_REMOTE_ORIGIN': 'https://shop--{port}.dev.remote.e-m.sa'}
        done = subprocess.run([sys.executable, '-m', 'eaos', 'studio', str(self.project), '--background', '--no-open'], env=env,
                              capture_output=True, text=True, timeout=60)
        [record] = self.records()
        saved = json.loads(record.read_text(encoding='utf-8'))
        self.stop_later(saved['pid'])
        self.assertEqual(done.returncode, 0, done.stderr)
        address = done.stdout.strip().split('EAOS Studio: ', 1)[1]
        # The page it opens depends on this computer (the tools page where they are not installed); the address does not.
        self.assertEqual(address.split('#', 1)[0], f"https://shop--{saved['port']}.dev.remote.e-m.sa/", 'the Remote address carries no token')
        host = {'Host': f"shop--{saved['port']}.dev.remote.e-m.sa"}
        status, page = _fetch(f"http://127.0.0.1:{saved['port']}/", host)
        self.assertEqual(status, 200, 'it answers to its Remote name')
        self.assertIn('live-token.js', page.decode('utf-8'), 'behind the Remote sign-in the page also reads its token from its server')
        for address in filter(None, ('127.0.0.1', _own_address())):
            self.assertEqual(_fetch(f"http://{address}:{saved['port']}/live-token.js", {**host, **FORGED})[0], 404,
                             f'a program on this computer ({address}) with the Remote name and the page\'s headers')
            self.assertEqual(_fetch(f"http://{address}:{saved['port']}/live-token.js",
                                    {**host, **FORGED, 'X-Forwarded-For': '8.8.8.8', 'X-Forwarded-Proto': 'https'})[0], 404,
                             f'nor ({address}) when it names another computer in a forwarding header')

    def test_open_studio_starts_it_in_the_background_and_reuses_it(self):
        from eaos import agent_tools
        from eaos.api import launch
        first = agent_tools.open_studio(str(self.project), show=False)
        [record] = self.records()
        pid = json.loads(record.read_text(encoding='utf-8'))['pid']
        stop = self.stop_later(pid)
        self.assertTrue(first['started'] and first['live'])
        self.assertFalse(first['checked'])
        self.assertTrue(first['studio'].startswith('http://127.0.0.1:'))
        second = agent_tools.open_studio(str(self.project), show=False)
        self.assertEqual((second['studio'], second['started']), (first['studio'], False))
        stop()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and launch._alive(pid): time.sleep(0.1)
        self.assertIsNone(launch.running(server.prepare(str(self.project))[0]), 'a dead server is not reused')


class Switcher(unittest.TestCase):
    def test_the_switcher_lists_each_project_and_opens_its_own_studio_which_goes_when_idle_but_not_while_a_run_waits(self):
        from eaos import guided
        from eaos.api import launch
        from eaos.studio.actions import adapters
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, {'EAOS_HOME': f'{folder}/home'}), \
                mock.patch.object(adapters, 'installed', return_value={}):
            states = []
            for name, scanned in (('shop', '2026-10-16'), ('blog', '2026-10-17')):
                (Path(folder) / name).mkdir()
                state = {'project': f'{folder}/{name}', 'workspace': str(guided.workspace(Path(folder) / name)), 'scanned': scanned}
                guided.save(state)
                states.append(guided.load(Path(folder) / name))
            health = guided.report_of(states[1]) / 'studio/health.json'
            health.parent.mkdir(parents=True)
            health.write_text(json.dumps({'score': {'value': 0.83}}))
            keys = server.Keys(port=PORT)
            app = server.create_app(report_with_data(folder), project=Path(folder) / 'shop', keys=keys, watch=False)
            headers = {'X-EAOS-Token': keys.token, 'X-EAOS-CSRF': keys.csrf, 'Origin': f'http://127.0.0.1:{PORT}'}
            with TestClient(app, base_url=f'http://127.0.0.1:{PORT}') as local:
                listed = local.get('/api/projects', headers=headers).json()['projects']
                self.assertEqual([(p['name'], p['current'], p['score'], p['studio']) for p in listed],
                                 [('blog', False, 0.83, False), ('shop', True, None, False)])
                with mock.patch.object(launch, 'start', return_value=({'port': 9, 'token': 't' * 32}, True)) as started:
                    opened = local.post('/api/projects/open', headers=headers, json={'workspace': listed[0]['workspace']}).json()
                self.assertEqual(opened['studio'], f"http://127.0.0.1:9/#token={'t' * 32}")
                self.assertEqual(started.call_args.args[0]['project'], f'{folder}/blog', "the other project's own server")
                self.assertEqual(local.post('/api/projects/open', headers=headers, json={'workspace': 'x'}).status_code, 404)
                ctx = app.state.ctx
                self.assertFalse(ctx.idle(time.monotonic()), 'a client was just here')
                later = time.monotonic() + server.IDLE + 1
                self.assertTrue(ctx.idle(later))
                engine_store = guided.workspace(Path(folder) / 'shop') / 'runs'
                (engine_store / 'r1').mkdir(parents=True)
                (engine_store / 'r1/run.json').write_text(json.dumps({'id': 'r1', 'state': 'queued'}))
                self.assertFalse(ctx.idle(later), 'a queued run keeps its server')


class Remote(unittest.TestCase):
    """A Studio behind the Remote sign-in: its exact routed origin, its kept token, and the opt-in that hands it over."""

    def test_on_a_remote_server_the_studio_is_a_service_of_the_computer_at_its_routed_address(self):
        # Chef Operations (2026-10-13): the Studio ran in the assistant's session, which the server ended overnight, and
        # its address carried the token.
        from eaos.api import launch
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, {'EAOS_HOME': folder, 'SECRET_TOKEN': 'x'}):
            self.assertFalse(launch.durable(), 'a person\'s own computer: a process of its own')
            for wrong in ('https://evil.example:8096', 'https://shop.dev.remote.e-m.sa'):
                with self.assertRaises(ValueError): launch.serve_remotely(wrong)
            with mock.patch.object(launch.shutil, 'which', return_value='/usr/bin/systemd-run'), \
                    mock.patch.object(launch.Path, 'is_dir', return_value=True):
                self.assertEqual(launch.serve_remotely('https://shop--8096.dev.remote.e-m.sa/'), 'https://shop--{port}.dev.remote.e-m.sa')
                self.assertTrue(launch.durable())
            self.assertEqual(launch.remote_template(), 'https://shop--{port}.dev.remote.e-m.sa')
            state = {'workspace': f'{folder}/projects/shop-1a2b3c4d', 'project': '/srv/shop'}
            with mock.patch.object(launch.subprocess, 'run', return_value=mock.Mock(returncode=0, stdout='inactive')) as ran:
                self.assertTrue(launch._as_service(state, ['python', '-m', 'eaos', 'studio'], dict(os.environ, PWD='/x'), Path(folder) / 'log'))
            argv = ran.call_args.args[0]
            self.assertEqual(argv[:2 if os.geteuid() == 0 else 3][-1:], ['--unit=eaos-studio-shop-1a2b3c4d'])
            self.assertIn('--property=Restart=on-failure', argv)
            self.assertIn('--setenv=SECRET_TOKEN', argv, 'the environment passes by name')
            self.assertFalse(any('=x' in word for word in argv), 'never a value on the command line')
            self.assertNotIn('--setenv=PWD', argv)

    def test_the_exact_routed_origin_keeps_every_lock(self):
        from eaos.api import launch
        from eaos.studio.actions import adapters, security
        origin = 'https://engineering-audit-os--8096.dev.remote.e-m.sa'
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, {'EAOS_HOME': folder}), mock.patch.object(adapters, 'installed', return_value={}):
            report = report_with_data(folder)
            project = Path(folder) / 'project'
            project.mkdir()
            keys = server.Keys(port=8096, remote_origin=origin)
            app = server.create_app(report, project=project, keys=keys, watch=False)
            with TestClient(app, base_url=origin) as remote:
                headers = {'X-EAOS-Token': keys.token, 'X-EAOS-CSRF': keys.csrf, 'Origin': origin}
                self.assertEqual(remote.get('/api/decisions', headers=headers).status_code, 200)
                self.assertEqual(remote.get('/api/decisions').status_code, 401)
                self.assertEqual(remote.get('/api/decisions', headers={**headers, 'Host': 'other--8096.dev.remote.e-m.sa'}).status_code, 421)
                for altered in ({'Origin': 'https://evil.example'}, {'X-EAOS-CSRF': 'bad'}):
                    self.assertEqual(remote.post('/api/decisions/missing/answer', headers={**headers, **altered}, json={}).status_code, 403)
                self.assertEqual(remote.post('/api/decisions/missing/answer', headers=headers, json={}).status_code, 404)
            with self.assertRaises(ValueError): server.Keys(port=8097, remote_origin=origin)
        for value in ('https://*.dev.remote.e-m.sa', 'http://engineering-audit-os--8095.dev.remote.e-m.sa', 'https://evil.example'):
            with self.assertRaises(ValueError): security.Locks(8095, remote_origin=value)
        record = {'port': 8096, 'token': 'fixture-not-a-secret', 'remote_origin': origin}
        self.assertTrue(launch.url_of(record).startswith(origin + '/#token='))
        self.assertTrue(launch.url_of({**record, 'remote_origin': None}).startswith('http://127.0.0.1:8096/#token='))
        with self.assertRaises(ValueError): launch.url_of({**record, 'remote_origin': 'https://evil.example'})

    def test_the_token_is_kept_privately_and_handed_to_the_page_only_when_the_owner_opted_in(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'token'
            first = server._kept_token(str(path))
            self.assertEqual(first, server._kept_token(str(path)))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            path.write_text('x' * 40)
            path.chmod(0o644)
            self.assertNotEqual(server._kept_token(str(path)), 'x' * 40, 'a file others can read gets a new token')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertIsNone(server._kept_token(None))
        ctx = lambda remote: mock.Mock(keys=server.Keys(port=8096, remote_origin='https://p--8096.dev.remote.e-m.sa' if remote else None))
        with mock.patch.dict(os.environ, {'EAOS_STUDIO_TRUST_REMOTE_LOGIN': '1'}):
            self.assertEqual((server._remote_login_trusted(ctx(True)), server._remote_login_trusted(ctx(False))), (True, False))
        with mock.patch.dict(os.environ, {'EAOS_STUDIO_TRUST_REMOTE_LOGIN': '', 'EAOS_REMOTE_ORIGIN': ''}):
            self.assertFalse(server._remote_login_trusted(ctx(True)))
        with mock.patch.dict(os.environ, {'EAOS_STUDIO_TRUST_REMOTE_LOGIN': '', 'EAOS_REMOTE_ORIGIN': 'https://p--{port}.dev.remote.e-m.sa'}):
            self.assertTrue(server._remote_login_trusted(ctx(True)), 'a computer set up for Remote opts in')
        from eaos.studio.actions import adapters
        origin = 'https://engineering-audit-os--8096.dev.remote.e-m.sa'
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, {'EAOS_HOME': folder}), mock.patch.object(adapters, 'installed', return_value={}):
            keys = server.Keys(port=8096, remote_origin=origin)
            app = server.create_app(report_with_data(folder), keys=keys, watch=False)
            gateway = mock.patch.object(server, '_gateways', return_value={'10.88.0.1'}, create=True)   # the Remote proxy's way in
            with gateway, TestClient(app, base_url=origin, client=('10.88.0.1', 443)) as remote:
                with mock.patch.dict(os.environ, {'EAOS_STUDIO_TRUST_REMOTE_LOGIN': '1'}):
                    first, second = remote.get('/').text, remote.get('/').text
                    self.assertIn('live-token.js?n=', first)
                    self.assertNotEqual(first, second, 'a new address on every load')
                    given = remote.get('/live-token.js?n=1')
                    self.assertIn(keys.token, given.text)
                    self.assertIn('no-store', given.headers['cache-control'])
                with mock.patch.dict(os.environ, {'EAOS_STUDIO_TRUST_REMOTE_LOGIN': ''}):
                    self.assertNotIn('live-token.js', remote.get('/').text)
                    self.assertEqual(remote.get('/live-token.js').status_code, 404)
            with gateway, TestClient(app, base_url=origin, client=('10.88.0.7', 40000)) as neighbour, \
                    mock.patch.dict(os.environ, {'EAOS_STUDIO_TRUST_REMOTE_LOGIN': '1'}):
                self.assertEqual(neighbour.get('/live-token.js?n=1').status_code, 404,
                                 'another container on the same bridge, with the Remote name: not the gateway, no token')
        held = tempfile.TemporaryDirectory()
        self.addCleanup(held.cleanup)
        table = Path(held.name) / 'route'
        table.write_text('Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\n'
                         'eth0\t00000000\t01219A0A\t0003\t0\t0\t100\t00000000\n'
                         'eth0\t00219A0A\t00000000\t0001\t0\t0\t100\t00FFFFFF\n')
        self.assertEqual(server._gateways(table), {'10.154.33.1'}, "the default route's gateway, from the kernel's table")
        for peer, given in (('10.154.33.1', True), ('::ffff:10.154.33.1', True), ('10.154.33.8', False), ('127.0.0.1', False), ('', False)):
            self.assertEqual(server._gateway_peer(peer, table), given, peer)


if __name__ == '__main__':
    unittest.main()
