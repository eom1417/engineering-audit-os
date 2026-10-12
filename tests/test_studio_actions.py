"""The command centre (eaos/studio/actions): the contract, the locks, the event log, the adapters on real recorded
streams, and runs end to end with a fake assistant (tests/fixtures/studio/actions/fake_assistant.py)."""
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / 'tests/fixtures/studio/actions'
FAKE = FIXTURES / 'fake_assistant.py'

from eaos.studio import actions  # noqa: E402
from tests.shared_fixture import Workspace  # noqa: E402
from eaos.studio.actions import adapters, handoff, prompts, runs, security, selection, store  # noqa: E402


def card(id, **extra):
    return {'id': id, 'key': id.lower(), 'title': f'Problem {id}', 'kind': 'duplication', 'category': 'structure', 'severity': 'high',
            'fixable': True, 'scope': 'place', 'place': f'src/{id}.py', 'paths': [f'src/{id}.py'], 'evidence': [], 'state': 'open',
            'milestone': 'M1', **extra}


class Base(Workspace):
    """A project, its Studio data, a home of its own, and the fake assistant as Claude Code."""

    def setUp(self):
        super().setUp()
        self.base = Path(self.tmp)
        saved = {k: os.environ.get(k) for k in ('EAOS_HOME', 'EAOS_OUTPUT', 'FAKE_MODE', 'FAKE_SECONDS', 'FAKE_ARGV', 'FAKE_LOGGED_IN', 'EAOS_ASSISTANT')}
        def restore():
            for key, value in saved.items():
                if value is None: os.environ.pop(key, None)
                else: os.environ[key] = value
        self.addCleanup(restore)
        os.environ.update(EAOS_HOME=str(self.base / 'home'), EAOS_OUTPUT=str(self.base / 'out'), FAKE_MODE='question',
                          FAKE_ARGV=str(self.base / 'argv.jsonl'))
        self.project = self.base / 'project'
        (self.project / 'src').mkdir(parents=True)
        subprocess.run(['git', 'init', '-q', str(self.project)], check=True)
        self.studio = self.base / 'studio'
        self.studio.mkdir()
        cards = [card('TASK-001'), card('TASK-002', severity='low', category='security'), card('TASK-003', state='done'),
                 card('TASK-004', milestone='M2')]
        (self.studio / 'cards.json').write_text(json.dumps({'cards': cards}), encoding='utf-8')
        self.apps = []
        self.app = self.make()

    def tearDown(self):
        for app in self.apps:
            for run in app.store.all():
                if run.get('state') in ('running', 'paused') and run.get('pid'):
                    try: os.killpg(run['pid'], 9)
                    except OSError: pass
            app.close()
        time.sleep(0.3)
        super().tearDown()

    def make(self, adapters_=None, **options):
        app = actions.Actions(self.project, port=8765, studio=self.studio,
                              adapters={'claude': adapters.ClaudeCode(command=[sys.executable, str(FAKE)])} if adapters_ is None else adapters_, **options)
        self.apps.append(app)
        return app

    def headers(self, app=None, **extra):
        app = app or self.app
        return {'X-EAOS-Token': app.token, 'X-EAOS-CSRF': app.csrf, 'Origin': 'http://127.0.0.1:8765', 'Host': '127.0.0.1:8765', **extra}

    def post(self, path, body=None, app=None):
        return (app or self.app).handle('POST', path, self.headers(app), body or {})

    def get(self, path, app=None):
        return (app or self.app).handle('GET', path, self.headers(app), None)

    def start(self, verb='explain', cards=('TASK-001',), app=None, **body):
        status, preview = self.post(f'/api/actions/{verb}/preview', {'verb': verb, 'selection': {'kind': 'cards', 'cards': list(cards)}}, app)
        self.assertEqual(status, 200, preview)
        status, created = self.post('/api/runs', {'action': verb, 'verb': verb, 'selection': {'kind': 'cards', 'cards': list(cards)},
                                                  'confirm': (preview.get('confirm') or {}).get('token'), **body}, app)
        self.assertEqual(status, 200, created)
        return created['run']['id']

    def kinds(self, run, app=None):
        return [event['kind'] for event in (app or self.app).store.events(run)]


class Contract(unittest.TestCase):
    def test_the_packaged_contract_is_the_documented_one_names_every_tool_and_every_endpoint_is_routed(self):
        self.assertEqual((ROOT / 'docs/studio-actions.json').read_bytes(), (ROOT / 'eaos/data/studio-actions.json').read_bytes())
        from eaos import mcp_server
        data = actions.contract()
        names = {action['id'] for action in data['actions'] if action['tool']}
        self.assertEqual(set(mcp_server.functions()), names)
        self.assertEqual({a['id'] for a in data['actions'] if not a['tool']}, set(runs.PLANNERS))
        self.assertLessEqual(mcp_server.reading(), names)
        for action in data['actions']:
            self.assertEqual(action['inputs']['type'], 'object', action['id'])
            self.assertTrue(action['label']['ar'] and action['label']['en'])
            self.assertEqual(action['needs_assistant'], action['mode'] == 'assistant')
        self.assertEqual({a['id'] for a in data['actions'] if a['irreversible']}, {'accept', 'undo'})
        self.assertEqual(set(data['lifecycle']['states']), set(store.STATES))
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, {'EAOS_HOME': folder}):
            project = Path(folder) / 'p'
            project.mkdir()
            app = actions.Actions(project, port=8765, adapters={})
            try:
                for row in data['endpoints']:
                    path = row['path'].replace('<id>/answer', 'r-none-q1/answer').replace('<id>', 'r-none' if row['path'].startswith('/api/runs') else 'status')
                    headers = {'X-EAOS-Token': app.token, 'X-EAOS-CSRF': app.csrf, 'Origin': 'http://127.0.0.1:8765', 'Host': '127.0.0.1:8765'}
                    status, payload = app.handle(row['method'], path, headers, {})
                    if '<id>' in row['path'] and 'runs' in row['path'] or 'questions/' in path or 'decisions/' in path:
                        self.assertIn(status, (403, 404, 409), (row, payload))      # a run that does not exist, not an unknown route
                        if status == 404: self.assertIn('r-none', payload['error'], row)
                    else:
                        self.assertNotEqual(status, 404, (row, payload))
            finally:
                app.close()

    def test_every_tool_status_can_name_next_is_allowed_to_the_fix_verb(self):
        """The incident: status said fix_abandon, the fix run was not allowed it, and the stuck batch could not be closed."""
        import inspect
        from eaos import agent_tools
        source = inspect.getsource(agent_tools.status)
        named = set()
        for step in re.findall(r"step = \('([^']+)'", source) + re.findall(r"'next': \{'tool': '([^']+)'", source):
            named.update(word for word in re.split(r',? then | or ', step) if word != 'none')
        verbs = {verb['id']: set(verb['tools']) for verb in actions.contract()['verbs']}
        self.assertIn('fix_abandon', named)
        self.assertEqual(named - set(adapters.PERSON_ONLY) - verbs['fix'], set())
        for verb in ('verify', 'explain', 'plan'):
            self.assertLessEqual({'wait', 'overview', 'findings', 'plan'}, verbs[verb], verb)


class Locks(Base):
    def test_every_request_needs_the_token_and_a_post_the_csrf_token_and_the_studio_origin_and_refusals_are_logged_without_them(self):
        self.app.handle('GET', f'/api/runs?token=wrong-{self.app.token[:5]}', {'Host': '127.0.0.1:8765'}, None)
        self.app.handle('POST', '/api/runs', {**self.headers(), 'X-EAOS-CSRF': 'bad'}, {})
        text = (self.app.store.folder / 'refused.jsonl').read_text()
        rows = [json.loads(line) for line in text.splitlines()]
        self.assertEqual([(r['method'], r['path']) for r in rows], [('GET', '/api/runs'), ('POST', '/api/runs')])
        self.assertIn('CSRF', rows[1]['reason'])
        self.assertNotIn(self.app.token, text)
        self.assertNotIn(self.app.token[:5], text)
        good = self.headers()
        self.assertEqual(self.app.handle('POST', '/api/runs/reorder', good, {'order': []})[0], 200)
        for change, status in (({'X-EAOS-Token': None}, 401), ({'X-EAOS-Token': 'x'}, 401), ({'X-EAOS-CSRF': None}, 403),
                               ({'X-EAOS-CSRF': self.app.token}, 403), ({'Origin': 'http://127.0.0.1:9999'}, 403),
                               ({'Origin': 'null'}, 403), ({'Host': 'attacker.test:8765'}, 403), ({'Host': '0.0.0.0:8765'}, 403)):
            headers = {k: v for k, v in {**good, **change}.items() if v is not None}
            self.assertEqual(self.app.handle('POST', '/api/runs/reorder', headers, {'order': []})[0], status, change)
        referer = {k: v for k, v in good.items() if k != 'Origin'}
        self.assertEqual(self.app.handle('POST', '/api/runs/reorder', {**referer, 'Referer': 'http://localhost:8765/#/runs'}, {'order': []})[0], 200)
        self.assertEqual(self.app.handle('POST', '/api/runs/reorder', referer, {'order': []})[0], 403)
        host = {'Host': 'localhost:8765'}
        self.assertEqual(self.app.handle('GET', f'/api/session?token={self.app.token}', host, None)[0], 200, 'a GET may carry it in the query')
        self.assertEqual(self.app.handle('GET', '/api/session?token=nope', host, None)[0], 401)
        self.assertEqual(self.app.handle('POST', f'/api/runs/reorder?token={self.app.token}', {**host, 'X-EAOS-CSRF': self.app.csrf,
                                                                                                  'Origin': 'http://localhost:8765'}, {})[0], 401)

    def test_a_confirmation_is_single_use_bound_and_expires_and_a_fix_without_one_is_refused(self):
        locks = security.Locks(8765)
        token = locks.confirm('accept', None, '/p')['token']
        self.assertFalse(locks.spend(token, 'undo', None, '/p'))
        self.assertFalse(locks.spend(token, 'accept', None, '/other'))
        self.assertTrue(locks.spend(token, 'accept', None, '/p'))
        self.assertFalse(locks.spend(token, 'accept', None, '/p'))
        late = locks.confirm('fix', {'kind': 'card'}, '/p')['token']
        with mock.patch('time.time', return_value=time.time() + security.CONFIRM_SECONDS + 5):
            self.assertFalse(locks.spend(late, 'fix', {'kind': 'card'}, '/p'))
        self.assertFalse(security.Locks(8765).spend(locks.confirm('accept', None, '/p')['token'], 'accept', None, '/p'))
        self.assertFalse(locks.spend('not.a.token', 'accept', None, '/p'))
        status, payload = self.post('/api/runs', {'action': 'fix', 'verb': 'fix', 'selection': {'kind': 'card', 'cards': ['TASK-001']}})
        self.assertEqual((status, payload.get('needs')), (403, 'confirm'))
        self.assertEqual(self.app.store.all(), [])
        self.assertEqual(self.post('/api/runs', {'action': 'accept', 'inputs': {'person_agreed': True}})[0], 403)
        # A Fix shows and pins where it builds: a branch that moves after the preview is refused, never built on silently
        commit = lambda: subprocess.run(['git', '-C', str(self.project), '-c', 'user.name=a', '-c', 'user.email=a@b', 'commit', '-q',
                                         '--allow-empty', '-m', 'm'], check=True)
        commit()
        subprocess.run(['git', '-C', str(self.project), 'checkout', '-q', '-b', 'dev'], check=True)
        selection = {'kind': 'card', 'cards': ['TASK-001']}
        where = self.post('/api/actions/fix/preview', {'verb': 'fix', 'selection': selection})[1]['where']
        self.assertEqual((where['base']['branch'], where['deliver_as'], where['merge_into'], where['problem']), ('dev', 'eaos/dev/wave-1', 'dev', None))
        main = next(b for b in where['branches'] if b['name'] != 'dev')
        self.assertEqual(main['blocked']['code'], 'main_name', 'a protected branch that is not open takes no merge from here')
        preview = self.post('/api/actions/fix/preview', {'verb': 'fix', 'selection': selection, 'where': {'merge_into': main['name']}})[1]
        self.assertEqual((preview['where']['problem']['code'], preview['confirm']), ('protected_target', None))
        preview = self.post('/api/actions/fix/preview', {'verb': 'fix', 'selection': selection, 'where': {'deliver_as': 'eaos/mine'}})[1]
        commit()
        status, payload = self.post('/api/runs', {'action': 'fix', 'verb': 'fix', 'selection': selection, 'confirm': preview['confirm']['token'],
                                                  'where': {'deliver_as': 'eaos/mine', 'base': 'dev', 'base_commit': preview['where']['base']['commit']}})
        self.assertEqual((status, payload.get('needs')), (409, 'preview'), payload)
        self.assertIn('moved', payload['error'])
        preview = self.post('/api/actions/fix/preview', {'verb': 'fix', 'selection': selection, 'where': {'deliver_as': 'eaos/mine'}})[1]
        status, payload = self.post('/api/runs', {'action': 'fix', 'verb': 'fix', 'selection': selection, 'confirm': preview['confirm']['token'],
                                                  'where': {'deliver_as': 'eaos/mine', 'base_commit': preview['where']['base']['commit']}})
        self.assertEqual((status, payload['run']['where']['deliver_as']), (200, 'eaos/mine'), payload)
        self.assertIn('deliver_as="eaos/mine"', self.app.manager.prompt_of(self.app.store.load(payload['run']['id'])))


class EventLog(unittest.TestCase):
    def test_events_are_gapless_hash_chained_scrubbed_and_cut(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder) / 'project'
            log = store.Store(Path(folder) / 'runs', store.Scrubber(project, ['launch-token-value']))
            log.save({'id': 'r1', 'state': 'queued'}, new=True)
            for index in range(5): log.append('r1', 'step', f'step {index}', {'n': index})
            events = log.events('r1')
            self.assertEqual([e['seq'] for e in events], [1, 2, 3, 4, 5])
            self.assertEqual(events[0]['prev'], store.ZERO)
            self.assertEqual(log.verify('r1'), [])
            self.assertEqual([e['seq'] for e in log.events('r1', after=3)], [4, 5])
            words = (f'{project}/src/a.py and {Path.home()}/x with sk-ant-abcdefghijklmnopqrstuv ghp_abcdefghijklmnopqrstuvwxyz0123 '
                     'Bearer abcdefghijklmnopqrstuvwxyz and launch-token-value')
            text = json.dumps(log.append('r1', 'say', words, {'nested': [words]}, words))
            for leaked in ('sk-ant-', 'ghp_', 'abcdefghijklmnopqrstuvwxyz', 'launch-token-value', str(project), str(Path.home()) + '/x'):
                self.assertNotIn(leaked, text)
            self.assertIn('src/a.py', text)
            big = log.append('r1', 'edit', 'big', {'diff': 'x' * (store.DIFF_LIMIT + 10)})
            self.assertTrue(big['data']['cut'])
            self.assertLess(len(big['data']['diff']), store.DIFF_LIMIT + 100)
            self.assertEqual(log.verify('r1'), [])
            path = Path(folder) / 'runs/r1/events.jsonl'
            path.write_text(path.read_text().replace('step 2', 'step X'))
            self.assertTrue(log.verify('r1'), 'tampering shows')


class Adapters(unittest.TestCase):
    labels = {a['id']: a['label'] for a in actions.contract()['actions']}

    def parse(self, adapter, name):
        state, events = adapter.new_state(), []
        for line in (FIXTURES / name).read_text(encoding='utf-8').splitlines(): events += adapter.parse(line, state, self.labels)
        return state, events

    def test_real_recorded_streams_read_as_plain_events(self):
        state, events = self.parse(adapters.ClaudeCode(), 'claude-stream.jsonl')
        self.assertEqual(state['session'], 'cdf7b362-ed33-4731-9bc7-19ce5cbc4c70')
        self.assertIsNone(state['failed'])
        kinds = [kind for kind, *_ in events]
        self.assertEqual((kinds[0], kinds[-1]), ('step', 'say'))
        self.assertIn('read', kinds)
        handed = [data for kind, _, data, _ in events if kind == 'check' and data.get('branch')]
        self.assertEqual(handed[0]['branch'], 'eaos/wave-1')
        self.assertNotIn('ToolSearch', json.dumps([text for _, text, _, _ in events]))
        self.assertIn('eaos/wave-1', state['final'])
        state, events = self.parse(adapters.Codex(), 'codex-stream.jsonl')
        self.assertEqual(state['session'], '01a0ef94-aacd-7503-b6a1-7c0910b2a2b8')
        progress = [data for kind, _, data, _ in events if kind == 'progress']
        self.assertTrue(progress and all(p['total'] == 26 for p in progress))
        self.assertLessEqual({'audit', 'command'}, {data.get('tool') for kind, _, data, _ in events if kind == 'step'})
        self.assertTrue(any(tool == 'run_setup' and isinstance(payload, dict) and payload.get('status') == 'needs_agreement'
                            for tool, payload in state['eaos_results']))
        for adapter, name, tools in ((adapters.ClaudeCode(), 'claude-explain-stream.jsonl', {'finding', 'impact'}),
                                     (adapters.Codex(), 'codex-explain-stream.jsonl', {'status', 'finding', 'impact'})):
            state, events = self.parse(adapter, name)
            self.assertIsNone(state['failed'], name)
            self.assertIn('TASK-001', state['final'])
            called = {data.get('tool') for kind, _, data, _ in events if kind in ('step', 'read')}
            self.assertLessEqual(tools, called, name)
            self.assertFalse({'fix_edit', 'accept', 'undo'} & called)
            for kind, words, data, detail in events:
                if kind == 'error':
                    self.assertTrue(data['recoverable'])
                    self.assertNotIn('Error', words['en'])
                    self.assertIn('Error', detail)
        events = adapters.tool_events('fix_edit', {'card': 'TASK-1', 'edits': [{'path': 'a.py', 'find': 'x = 1\n', 'replace': 'x = 2\n'},
                                                                               {'path': 'b.py', 'content': 'new\n'}, {'path': 'c.py', 'delete': True}]}, self.labels)
        kind, _, data, _ = events[0]
        self.assertEqual((kind, data['paths']), ('edit', ['a.py', 'b.py', 'c.py']))
        for needle in ('-x = 1', '+new', '(deleted)'): self.assertIn(needle, data['diff'])
        checks = adapters.result_events('wait', {}, {'status': 'done', 'result': {'kept': False, 'card': 'TASK-1', 'why': 'a test broke'}})
        self.assertEqual((checks[0][0], checks[0][2]['passed']), ('check', False))

    def test_an_assistant_starts_with_this_eaos_only_without_the_person_only_tools_and_is_told_the_eaos_way(self):
        with tempfile.TemporaryDirectory() as folder:
            argv = adapters.ClaudeCode(command=['claude']).argv('do it', 'r1', Path(folder), session='s1')
            config = json.loads((Path(folder) / 'mcp.json').read_text())
        refused = argv[argv.index('--disallowedTools') + 1:]
        for tool in ('Bash', 'Edit', 'Write', 'mcp__eaos__accept', 'mcp__eaos__undo', 'mcp__eaos__choose_branch'): self.assertIn(tool, refused)
        self.assertIn('--strict-mcp-config', argv)
        self.assertEqual(argv[-2:], ['--resume', 's1'])
        self.assertEqual(config['mcpServers']['eaos']['env']['EAOS_STUDIO_RUN'], 'r1')
        self.assertEqual(config['mcpServers']['eaos']['args'][-1], 'mcp')
        with tempfile.TemporaryDirectory() as folder:
            argv = adapters.ClaudeCode(command=['claude']).argv('explain', 'r1', Path(folder), tools=['status', 'finding'])
        self.assertEqual(argv[argv.index('--allowedTools') + 1:argv.index('--disallowedTools')], ['mcp__eaos__status', 'mcp__eaos__finding', 'Read', 'Grep', 'Glob'])
        argv = adapters.Codex(command=['codex']).argv('go on', 'r1', Path('.'), session='t1')
        self.assertEqual((argv[:3], argv[-2:]), (['codex', 'exec', 'resume'], ['t1', 'go on']))
        self.assertIn('sandbox_mode="read-only"', argv)
        server = next(a for a in argv if a.startswith('mcp_servers.eaos='))
        self.assertIn('EAOS_STUDIO_RUN="r1"', server)
        self.assertIn('disabled_tools=["accept", "undo", "choose_branch"]', server)
        limited = next(a for a in adapters.Codex(command=['codex']).argv('x', 'r1', Path('.'), tools=['status']) if a.startswith('mcp_servers.eaos='))
        self.assertIn('enabled_tools=["status"]', limited)
        self.assertNotIn('disabled_tools', limited)
        with mock.patch('shutil.which', return_value='/usr/local/bin/eaos'):
            argv, env = adapters.eaos_server('r1', 'Codex')
        self.assertEqual(argv, [sys.executable, '-m', 'eaos', 'mcp'], 'never another eaos on the path')
        self.assertEqual(Path(env['PYTHONPATH']), ROOT)
        self.assertEqual((env['EAOS_STUDIO_RUN'], env['EAOS_ASSISTANT']), ('r1', 'Codex'))
        text = prompts.build('fix', [{'id': 'TASK-1', 'title': 'T', 'paths': ['a.py']}], Path('/p/shop'), 'ar')
        for needle in ('fix_start', 'fix_edit', 'fix_finish', 'TASK-1', 'eaos-question', 'Do not call accept, undo or choose_branch', 'Arabic'):
            self.assertIn(needle, text)
        self.assertNotIn('/p/shop', text)
        found = prompts.question_in('Words.\n```eaos-question\n{"text": "Which?", "options": ["A", {"id": "b", "label": "B"}], "recommendation": "b"}\n```')
        self.assertEqual((found['text'], [o['id'] for o in found['options']], found['recommendation']), ({'en': 'Which?', 'ar': 'Which?'}, ['o1', 'b'], 'b'))
        self.assertIsNone(prompts.question_in('```eaos-question\n{not json}\n```'))
        self.assertIsNone(prompts.question_in('no block'))
        self.assertIsNone(prompts.question_in('```eaos-question\n{"text": "x", "options": [], "recommendation": "zz"}\n```')['recommendation'])

    def test_detection_says_installed_and_logged_in_and_a_probe_that_times_out_keeps_the_last(self):
        with mock.patch.dict(os.environ, {'FAKE_LOGGED_IN': '0'}):
            found = adapters.ClaudeCode(command=[sys.executable, str(FAKE)]).detect(fresh=True)
        self.assertEqual((found['installed'], found['logged_in']), (True, False))
        self.assertFalse(adapters.ClaudeCode(command=['/nonexistent/claude']).detect()['installed'])
        ready = adapters.ClaudeCode(command=[sys.executable, str(FAKE)])
        self.assertTrue(ready.available())
        self.assertTrue(ready.detect(fresh=True)['logged_in'])
        with mock.patch.object(adapters.ClaudeCode, '_run', return_value=None):
            self.assertEqual((ready.detect(fresh=True)['installed'], ready.detect(fresh=True)['logged_in']), (True, True))
            self.assertFalse(adapters.ClaudeCode(command=[sys.executable, str(FAKE)]).detect(fresh=True)['installed'])


class Selection(Base):
    def test_every_kind_of_selection_resolves_to_open_cards_is_refused_with_its_reason_or_previewed(self):
        (self.studio / 'gaps.json').write_text(json.dumps({'gaps': [{'id': 'g1', 'component': 'orders', 'cards': ['TASK-002', 'TASK-003']}]}))
        (self.studio / 'operations.json').write_text(json.dumps({'operations': [{'id': 'op1', 'cards': ['TASK-004']}]}))
        ids = lambda s: [c['id'] for c in selection.resolve(s, self.studio)[0]]
        for chosen, expected in ((('severity', 'high'), ['TASK-001', 'TASK-004']), (('area', 'security'), ['TASK-002']),
                                 (('component', 'orders'), ['TASK-002']), (('gap', 'g1'), ['TASK-002']), (('operation', 'op1'), ['TASK-004'])):
            self.assertEqual(ids({'kind': 'group', 'group': {'by': chosen[0], 'value': chosen[1]}}), expected, chosen)
        self.assertEqual(ids({'kind': 'step', 'step': 'M2'}), ['TASK-004'])
        self.assertEqual(ids({'kind': 'card', 'cards': ['TASK-002', 'TASK-001']}), ['TASK-002'])
        _, left = selection.resolve({'kind': 'cards', 'cards': ['TASK-001', 'TASK-003']}, self.studio)
        self.assertEqual(left, [{'id': 'TASK-003', 'why': 'already done'}])
        (self.studio / 'gaps.json').unlink()
        for bad, why in (({'kind': 'cards', 'cards': ['NOPE']}, 'no card named'), ({'kind': 'cards', 'cards': ['TASK-003']}, 'already handled'),
                         ({'kind': 'group', 'group': {'by': 'gap', 'value': 'g'}}, 'gap register'), ({'kind': 'x'}, 'kind'),
                         ({'kind': 'step', 'step': 'M9'}, 'names no card')):
            with self.assertRaisesRegex(selection.SelectionError, why): selection.resolve(bad, self.studio)
        self.assertEqual(self.post('/api/actions/fix/preview', {'verb': 'fix', 'selection': {'kind': 'cards', 'cards': ['NOPE']}})[0], 400)
        (self.studio / 'cards.json').write_text(json.dumps({'cards': [card(f'TASK-{n:03d}') for n in range(10, 32)]}))
        status, preview = self.post('/api/actions/fix/preview', {'verb': 'fix', 'selection': {'kind': 'group', 'group': {'by': 'severity', 'value': 'high'}}})
        self.assertEqual(status, 200, preview)
        self.assertEqual([len(b['cards']) for b in preview['batches']], [10, 10, 2])
        self.assertEqual((len(preview['files']), preview['risk']['level'], preview['assistant']['name']), (22, 'high', 'Claude Code'))
        self.assertLess(preview['estimate']['minutes_low'], preview['estimate']['minutes_high'])
        self.assertTrue(preview['confirm']['token'] and preview['on_failure']['ar'])
        status, preview = self.post('/api/actions/explain/preview', {'verb': 'explain', 'selection': {'kind': 'card', 'cards': ['TASK-010']}})
        self.assertEqual((preview['risk']['level'], preview['confirm'], preview['batches']), ('low', None, []))


def alive(pid):
    from eaos.studio.actions.runs import alive
    return alive(pid)


class Runs(Base):
    def test_a_question_waits_in_the_inbox_and_the_answer_resumes_the_session(self):
        run = self.start('explain')
        self.assertEqual(self.app.wait(run, ('waiting_for_person', 'failed'), 30)['state'], 'waiting_for_person')
        question = self.get('/api/questions')[1]['questions'][0]
        self.assertEqual((question['run'], question['recommendation'], question['text']['ar']), (run, 'yes', 'أكمل؟'))
        self.assertEqual(self.post(f"/api/questions/{question['id']}/answer", {'option': 'maybe'})[0], 400)
        self.assertEqual(self.post(f"/api/questions/{question['id']}/answer", {'option': 'yes'})[0], 200)
        self.assertEqual(self.post(f"/api/questions/{question['id']}/answer", {'option': 'yes'})[0], 200)
        self.assertEqual(self.post(f"/api/questions/{question['id']}/answer", {'option': 'no'})[0], 409)
        done = self.app.wait(run, ('done', 'failed'), 30)
        self.assertEqual(done['state'], 'done', self.app.store.events(run))
        self.assertEqual(done['result']['answer'], 'All done.')
        argvs = [json.loads(line) for line in Path(os.environ['FAKE_ARGV']).read_text().splitlines() if '-p' in line]
        self.assertEqual(argvs[-1][-2:], ['--resume', 'fake-session'])
        self.assertIn('option "yes"', argvs[-1][argvs[-1].index('-p') + 1])
        starts = [e['text']['en'] for e in self.app.store.events(run) if e['kind'] == 'step' and e['data'].get('assistant')]
        self.assertEqual(starts, ['Claude Code started', 'Claude Code went on'])
        edits = [e for e in self.app.store.events(run) if e['kind'] == 'edit']
        self.assertIn('+x = 2', edits[0]['data']['diff'])
        self.assertIn('check', self.kinds(run))
        self.assertEqual(self.app.store.verify(run), [])

    def test_an_answer_that_closes_the_stuck_batch_closes_it_and_a_direct_step_runs_while_a_question_waits(self):
        """The incident: "yes, close the batch" was only text to a run without fix_abandon, and pressing fix_abandon from
        the palette queued behind the run that waited for that same answer."""
        calls = []
        def tool(name):
            def call(**arguments):
                calls.append(name)
                return json.dumps({'status': 'abandoned'} if name == 'fix_abandon' else {'ok': True})
            return call
        self.app.manager.tools = lambda: {a['id']: tool(a['id']) for a in actions.contract()['actions']}
        run = self.start('explain')
        self.assertEqual(self.app.wait(run, ('waiting_for_person', 'failed'), 30)['state'], 'waiting_for_person')
        direct = self.post('/api/runs', {'action': 'audit'})[1]['run']['id']
        self.assertEqual(self.app.wait(direct, ('done', 'failed'), 10)['state'], 'done', 'a direct step is not blocked by a waiting question')
        asked = prompts.question_in('```eaos-question\n{"text": "Close the stuck batch?", "options": [{"id": "close", "label": "Yes", '
                                    '"action": "fix_abandon"}, {"id": "keep", "label": "No", "action": "accept"}]}\n```')
        self.assertEqual([o.get('action') for o in asked['options']], ['fix_abandon', None], 'only the allowed action is kept')
        record = self.app.store.load(run)
        self.app.store.update(run, question={**record['question'], 'options': asked['options']})
        self.assertEqual(self.post(f"/api/questions/{record['question']['id']}/answer", {'option': 'close'})[0], 200)
        self.assertEqual(self.app.wait(run, ('done', 'failed'), 30)['state'], 'done')
        self.assertEqual(calls, ['audit', 'fix_abandon'])
        argvs = [json.loads(line) for line in Path(os.environ['FAKE_ARGV']).read_text().splitlines() if '-p' in line]
        self.assertIn('already ran fix_abandon', argvs[-1][argvs[-1].index('-p') + 1])

    def test_a_fix_run_that_kept_nothing_says_so_and_its_progress_is_its_batch(self):
        """The incident: a fix run that fixed nothing ended "done / تم", its bar reading status's "0 of 898" cards."""
        self.assertEqual(adapters.result_events('status', {}, {'progress': {'done': 0, 'total': 898}}), [])
        run = self.start('fix', cards=('TASK-001', 'TASK-002'))
        question = self.app.wait(run, ('waiting_for_person', 'failed'), 30)['question']
        self.assertEqual(self.post(f"/api/questions/{question['id']}/answer", {'option': 'yes'})[0], 200)
        ended = self.app.wait(run, ('done', 'failed'), 30)
        self.assertEqual((ended['state'], ended['result']['nothing_changed']), ('failed', True), self.app.store.events(run))
        events = self.app.store.events(run)
        self.assertEqual([(e['data']['done'], e['data']['total']) for e in events if e['kind'] == 'progress'], [(1, 2)])
        self.assertTrue(next(e for e in events if e['kind'] == 'result')['data']['nothing_changed'])
        self.assertNotIn('تم', ' '.join(e['text']['ar'] for e in events if e['kind'] == 'result'))

    def test_one_run_at_a_time_and_the_queue_is_reordered(self):
        os.environ.update(FAKE_MODE='slow', FAKE_SECONDS='2')
        first, second, third = (self.start('explain', cards=(c,)) for c in ('TASK-001', 'TASK-002', 'TASK-004'))
        self.assertEqual(self.app.wait(first, ('running',), 10)['state'], 'running')
        self.assertEqual(self.get('/api/runs')[1]['queue'], [second, third])
        self.assertEqual(self.post('/api/runs/reorder', {'order': [third]})[1]['queue'], [third, second])
        self.assertEqual(self.post('/api/runs/reorder', {'order': [first]})[0], 409)
        self.assertEqual(self.get(f'/api/runs/{third}')[1]['run']['position'], 1)
        self.assertEqual(self.app.wait(first, ('done',), 20)['state'], 'done')
        self.assertIn(self.app.wait(third, ('running', 'done'), 20)['state'], ('running', 'done'))
        self.assertEqual(self.get(f'/api/runs/{second}')[1]['run']['state'], 'queued')

    def test_pause_resume_stop_and_retry(self):
        os.environ.update(FAKE_MODE='slow', FAKE_SECONDS='6')
        run = self.start('explain')
        running = self.app.wait(run, ('running',), 10)
        time.sleep(0.6)
        self.assertEqual(self.post(f'/api/runs/{run}/pause')[1]['run']['state'], 'paused')
        time.sleep(0.5)                             # what the assistant wrote before it was paused is still read
        count = len(self.app.store.events(run))
        time.sleep(0.8)
        self.assertEqual(len(self.app.store.events(run)), count)
        self.assertEqual(self.post(f'/api/runs/{run}/resume')[1]['run']['state'], 'running')
        self.assertEqual(self.post(f'/api/runs/{run}/stop')[1]['run']['state'], 'stopped')
        pid = self.app.store.load(run).get('pid') or running.get('pid')
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and pid and alive(pid): time.sleep(0.2)
        self.assertFalse(pid and alive(pid))
        self.assertEqual(self.post(f'/api/runs/{run}/stop')[0], 409)
        os.environ['FAKE_MODE'] = 'question'
        self.assertEqual(self.post(f'/api/runs/{run}/retry')[1]['run']['state'], 'queued')
        again = self.app.wait(run, ('waiting_for_person', 'failed'), 30)
        self.assertEqual((again['state'], again['attempt']), ('waiting_for_person', 2))
        self.assertEqual(self.app.store.verify(run), [])

    def test_a_run_ends_with_its_result_or_its_reason_and_its_events_stream_and_replay(self):
        for mode, words in (('fail', 'the model is not available'), ('crash', 'code 3')):
            os.environ['FAKE_MODE'] = mode
            run = self.start('explain')
            self.assertEqual(self.app.wait(run, ('failed', 'done'), 30)['state'], 'failed')
            errors = [e for e in self.app.store.events(run) if e['kind'] == 'error']
            self.assertIn(words, errors[-1]['data']['reason'])
        os.environ['FAKE_MODE'] = 'replay'
        run = self.start('explain')
        frames = []
        reader = threading.Thread(target=lambda: frames.extend(self.app.sse(run, follow=True, heartbeat=0.5)), daemon=True)
        reader.start()
        reader.join(30)
        self.assertFalse(reader.is_alive())
        done = self.app.store.load(run)
        self.assertEqual(done['state'], 'done', self.app.store.events(run)[-3:])
        self.assertIn('eaos/wave-1', done['result']['answer'])
        self.assertLessEqual({'step', 'read', 'check', 'say', 'result'}, set(self.kinds(run)))
        ids = [int(re.match(r'id: (\d+)', f).group(1)) for f in frames if f.startswith('id:')]
        self.assertEqual(ids, list(range(1, len(ids) + 1)))
        self.assertEqual(len([f for f in self.app.sse(run, last_event_id=ids[-3]) if f.startswith('id:')]), 2)
        status, payload = self.get(f'/api/runs/{run}/events?after={ids[-2]}')
        self.assertEqual([e['seq'] for e in payload['events']], [ids[-1]])

    def test_two_servers_never_start_the_same_run(self):
        deadline = time.monotonic() + 5
        while self.app.manager._lockfile is None and time.monotonic() < deadline: time.sleep(0.05)
        other = self.make()
        self.assertFalse(other.manager._hold())
        run = self.start('explain', app=other)
        self.assertEqual(self.app.wait(run, ('waiting_for_person', 'failed'), 30)['state'], 'waiting_for_person')
        time.sleep(1)
        launches = [line for line in Path(os.environ['FAKE_ARGV']).read_text().splitlines() if '"-p"' in line]
        self.assertEqual(len(launches), 1)
        self.assertNotIn(run, other.manager.watched)

    def test_a_restart_follows_a_live_assistant_and_fails_a_dead_one_plainly(self):
        os.environ.update(FAKE_MODE='slow', FAKE_SECONDS='3')
        live = self.start('explain')
        self.app.wait(live, ('running',), 10)
        time.sleep(0.5)
        self.app.close()
        self.app.manager.children.clear()
        dead = 'r-dead'
        self.app.store.save({'id': dead, 'action': 'explain', 'verb': 'explain', 'mode': 'assistant', 'assistant': 'claude', 'state': 'running',
                             'pid': 999999, 'label': {'en': 'x', 'ar': 'x'}, 'created': '0'}, new=True)
        again = self.make()
        self.assertEqual(again.wait(dead, ('failed',), 10)['state'], 'failed')
        self.assertIn('server', again.store.events(dead)[-2]['text']['en'])
        finished = again.wait(live, ('done', 'failed'), 20)
        self.assertEqual(finished['state'], 'done', again.store.events(live)[-3:])
        self.assertEqual(finished['result']['answer'], 'finished slowly')


class Direct(Base):
    def fake_tools(self, answers):
        calls = []
        def tool(name):
            def call(**arguments):
                calls.append((name, arguments))
                answer = answers.get(name, {'ok': True})
                return json.dumps(answer(arguments) if callable(answer) else answer)
            return call
        return (lambda: {name: tool(name) for name in {a['id'] for a in actions.contract()['actions']}}), calls

    def test_a_reading_action_answers_at_once_and_a_job_is_followed_with_its_progress(self):
        from eaos import jobs
        self.app.manager.tools, calls = self.fake_tools({'status': {'next': 'audit'}, 'audit': {'job': 'audit-1', 'status': 'running'}})
        status, payload = self.post('/api/runs', {'action': 'status'})
        self.assertEqual((status, payload['run']['state'], payload['run']['result']['answer']), (200, 'done', {'next': 'audit'}))
        self.assertEqual(calls, [('status', {'project': str(self.project.resolve())})])
        self.assertEqual(self.get('/api/runs')[1]['runs'], [], 'a reading action stays out of the history')
        self.assertEqual(len(self.get('/api/runs?all=1')[1]['runs']), 1)
        self.assertEqual(self.post('/api/runs', {'action': 'findings', 'inputs': {'limit': 'many'}})[0], 400)
        state = {'n': 0}
        def read(job):
            state['n'] += 1
            if state['n'] < 3: return {'id': job, 'kind': 'audit', 'status': 'running', 'progress': {'done': state['n'], 'total': 3, 'stage': 'engines'}}
            return {'id': job, 'kind': 'audit', 'status': 'done', 'result': {'overview': 'fine'}}
        with mock.patch.object(jobs, 'read', side_effect=read):
            run = self.post('/api/runs', {'action': 'audit'})[1]['run']['id']
            done = self.app.wait(run, ('done', 'failed'), 20)
        self.assertEqual(done['state'], 'done')
        self.assertEqual([e['data']['done'] for e in self.app.store.events(run) if e['kind'] == 'progress'], [1, 2])

    def test_a_step_that_needs_consent_asks_in_the_inbox_and_only_an_explicit_yes_gives_it(self):
        os.environ['FAKE_MODE'] = 'fail'
        self.app.manager.tools, calls = self.fake_tools({'run_setup': lambda a: {'status': 'done'} if a.get('person_agreed')
                                                         else {'status': 'needs_agreement', 'ask_the_person': 'May EAOS run your app?'}})
        run = self.post('/api/runs', {'action': 'run_setup'})[1]['run']['id']
        question = self.app.wait(run, ('waiting_for_person',), 5)['question']
        self.assertEqual(question['why'], 'run consent')
        path = f"/api/questions/{question['id']}/answer"
        self.assertEqual(self.post(path, {'text': 'Explain first'})[0], 200)
        record = self.app.wait(run, ('waiting_for_person',), 5)
        self.assertEqual((record['question']['why'], record['answered'][0]['text']), ('run consent', 'Explain first'),
                         'a clarification that failed keeps the question')
        self.assertIn('error', self.kinds(run))
        os.environ.update(FAKE_MODE='slow', FAKE_SECONDS='0.2')
        question = record['question']
        path = f"/api/questions/{question['id']}/answer"
        text = '  Yes is a word, but explain first.\nAn unrelated request.  '
        for body in ({'option': 'yes', 'text': text}, {'option': ['yes']}, {'text': '   '}, {'text': 'x' * 4001}):
            self.assertEqual(self.post(path, body)[0], 400, body)
        self.assertEqual(self.post(path, {'text': text})[0], 200)
        self.assertEqual(self.post(path, {'text': text})[0], 200)
        record = self.app.wait(run, ('waiting_for_person',), 5)
        self.assertEqual(record['mode'], 'direct')
        self.assertNotEqual(record['question']['id'], question['id'])
        self.assertEqual((record['answered'][-1]['text'], record['question']['why']), (text, 'run consent'))
        self.assertFalse(any(args.get('person_agreed') for _, args in calls), 'words are never consent')
        reread = self.make().store.load(run)
        self.assertEqual(reread['answered'][-1]['text'], text)
        self.assertEqual(reread['question']['options'], question['options'])
        self.assertEqual(self.post(f"/api/questions/{reread['question']['id']}/answer", {'option': 'yes'})[0], 200)
        self.assertEqual(self.app.wait(run, ('done', 'failed'), 5)['state'], 'done')
        self.assertTrue(calls[-1][1]['person_agreed'])

    def test_the_branch_a_check_or_an_assistant_needs_is_asked_in_the_studio_and_the_choice_is_applied(self):
        chosen, manager = [], self.app.manager
        manager._choose_branch = lambda branch, said: chosen.append((branch, said))
        asked = {'status': 'needs_branch', 'branches': [{'name': 'main', 'main': True}, {'name': 'work', 'ahead_of_main': 3}], 'recommended': 'work'}
        manager.tools, calls = self.fake_tools({'audit': lambda arguments: asked if not chosen else {'status': 'started', 'checked': True}})
        run = self.post('/api/runs', {'action': 'audit'})[1]['run']['id']
        question = self.app.wait(run, ('waiting_for_person', 'done'), 5)['question']
        self.assertEqual((question['why'], question['recommendation'], [o['id'] for o in question['options']]), ('branch', 'work', ['main', 'work']))
        self.assertEqual(self.post(f"/api/questions/{question['id']}/answer", {'option': 'main'})[0], 200)
        self.assertEqual(self.app.wait(run, ('done', 'failed'), 5)['state'], 'done')
        self.assertEqual(chosen, [('main', 'main (main)')])
        self.assertEqual([name for name, _ in calls], ['audit', 'audit'], 'the check runs again on the chosen branch')
        chosen.clear()
        run = self.start('explain')
        self.app.wait(run, ('waiting_for_person', 'done', 'failed'), 30)
        manager._launch = lambda *args: None
        asked = {'status': 'needs_branch', 'recommended': 'develop', 'branches': [{'name': 'main', 'main': True}, {'name': 'develop', 'ahead_of_main': 9}]}
        manager._end_turn(run, {'eaos_results': [('status', asked)], 'texts': ['EAOS needs the branch first.']}, 0)
        question = self.app.store.load(run)['question']
        self.assertEqual((question['why'], question['recommendation']), ('branch', 'develop'))
        self.assertEqual(self.post(f"/api/questions/{question['id']}/answer", {'option': 'develop'})[0], 200)
        self.assertEqual([branch for branch, _ in chosen], ['develop'], 'answered in the Studio, the choice reaches EAOS')

    def test_accept_and_undo_need_their_confirmation_and_the_newest_waiting_branch(self):
        self.app.manager.tools, calls = self.fake_tools({'accept': {'status': 'accepted', 'branch': 'eaos/wave-1'}, 'undo': {'status': 'nothing_to_undo'}})
        for run, branch in (('r-fix', 'eaos/wave-1'), ('r-two', 'eaos/wave-2'), ('r-three', 'eaos/wave-3')):
            self.app.store.save({'id': run, 'action': 'fix', 'verb': 'fix', 'mode': 'assistant', 'state': 'done', 'label': {'en': 'x', 'ar': 'x'},
                                 'created': '0', 'result': {'branch': branch}}, new=True)
        self.app.manager.newest_waiting = lambda: 'eaos/wave-1'
        self.assertEqual(self.post('/api/runs/r-fix/accept', {})[0], 403)
        wrong = self.post('/api/actions/undo/preview')[1]['confirm']['token']
        self.assertEqual(self.post('/api/runs/r-fix/accept', {'confirm': wrong})[0], 403)
        token = self.post('/api/actions/accept/preview')[1]['confirm']['token']
        status, payload = self.post('/api/runs/r-fix/accept', {'confirm': token})
        self.assertEqual(status, 200, payload)
        self.assertEqual(calls, [('accept', {'person_agreed': True, 'project': str(self.project.resolve())})])
        self.assertEqual(self.app.store.load('r-fix')['outcome'], 'accepted')
        self.assertEqual(self.post('/api/runs/r-fix/accept', {'confirm': token})[0], 403)
        undo = lambda run: self.post(f'/api/runs/{run}/undo', {'confirm': self.post('/api/actions/undo/preview')[1]['confirm']['token']})
        self.app.manager.newest_waiting = lambda: 'eaos/wave-3'
        self.assertEqual(undo('r-fix')[0], 409, 'accepted work is not undone here')
        self.assertEqual(undo('r-two')[0], 409, "another run's branch")
        self.app.manager.newest_waiting = lambda: None
        self.assertEqual(undo('r-three')[0], 409)
        self.assertEqual(len(calls), 1)
        self.app.manager.newest_waiting = lambda: 'eaos/wave-3'
        status, payload = undo('r-three')
        self.assertEqual(status, 200, payload)
        self.assertNotIn('outcome', self.app.store.load('r-three'))
        self.assertEqual(self.kinds('r-three')[-1], 'error')


class Handoff(Base):
    def test_with_no_assistant_the_next_status_call_takes_the_request_and_a_note_closes_it(self):
        app = self.make(adapters_={})
        run = self.start('fix', app=app)
        self.assertEqual(app.wait(run, ('waiting_for_person',), 10)['state'], 'waiting_for_person')
        self.assertIn('studio-request', app.store.load(run)['handoff']['en'])
        self.assertEqual([r['run'] for r in handoff.pending(self.project)], [run])
        self.assertEqual(list(self.project.rglob('studio-requests.json')), [], 'the request waits in the EAOS workspace, never the project')
        [written] = list((self.base / 'home').rglob('studio-requests.json'))
        self.assertIn(f'studio-request {run} done', json.loads(written.read_text())[0]['request']['en'])
        from eaos import mcp_server
        with mock.patch('eaos.build_tools.status_of', side_effect=lambda project: {'next': 'audit'}), mock.patch.dict(os.environ, {'EAOS_ASSISTANT': 'Codex'}):
            answer = mcp_server._status(str(self.project))
            self.assertEqual(mcp_server._status(str(self.project)), {'next': 'audit'})
        self.assertEqual(answer['studio_request']['id'], run)
        self.assertIn('TASK-001', answer['studio_request']['request'])
        self.assertEqual(app.wait(run, ('running',), 10)['state'], 'running')
        self.assertIsNone(handoff.close(self.project, 'studio-request other done'))
        self.assertEqual(handoff.close(self.project, f'studio-request {run} done: fixed TASK-001'), run)
        self.assertEqual(app.wait(run, ('done',), 10)['result']['answer'], 'fixed TASK-001')
        self.assertEqual(handoff.pending(self.project), [])

    def test_the_studios_own_calls_neither_take_the_request_nor_use_the_person_only_tools(self):
        handoff.add(self.project, 'r1', 'do it', {'en': 'x', 'ar': 'x'})
        from eaos import mcp_server
        with mock.patch('eaos.build_tools.status_of', return_value={}), mock.patch.dict(os.environ, {'EAOS_ASSISTANT': mcp_server.STUDIO}):
            self.assertEqual(mcp_server._status(str(self.project)), {})
        self.assertEqual(len(handoff.pending(self.project)), 1)
        with mock.patch.dict(os.environ, {'EAOS_STUDIO_RUN': 'r1'}):
            for tool in mcp_server.PERSON_ONLY:
                answer = json.loads(mcp_server.functions()[tool](project=str(self.project), **({'branch': 'x'} if tool == 'choose_branch' else {})))
                self.assertIn('the person', answer['error'])


def asgi(app, method, path, headers, body=b''):
    """One request through an ASGI app, without a server or httpx: (status, body bytes)."""
    import asyncio
    sent, out = [False], {'status': None, 'body': b''}
    async def receive():
        if sent[0]:
            await asyncio.sleep(3600)                   # a client that stays until the response ends
            return {'type': 'http.disconnect'}
        sent[0] = True
        return {'type': 'http.request', 'body': body, 'more_body': False}
    async def send(message):
        if message['type'] == 'http.response.start': out['status'] = message['status']
        elif message['type'] == 'http.response.body': out['body'] += message.get('body', b'')
    target, _, query = path.partition('?')
    scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1', 'method': method, 'scheme': 'http', 'path': target,
             'raw_path': target.encode(), 'query_string': query.encode(), 'root_path': '', 'server': ('127.0.0.1', 8765),
             'client': ('127.0.0.1', 50000), 'headers': [(k.lower().encode(), v.encode()) for k, v in headers.items()]}
    asyncio.run(app(scope, receive, send))
    return out['status'], out['body']


class Mounting(Base):
    def test_mount_puts_the_api_and_the_stream_on_a_starlette_app(self):
        from starlette.applications import Starlette
        app = Starlette()
        actions.mount(app.router, self.app)
        host = {'host': '127.0.0.1:8765'}
        status, body = asgi(app, 'GET', '/api/session', {**host, 'X-EAOS-Token': self.app.token})
        self.assertEqual((status, json.loads(body)['csrf']), (200, self.app.csrf))
        self.assertEqual(asgi(app, 'GET', '/api/session', host)[0], 401)
        os.environ['FAKE_MODE'] = 'replay'
        run = self.start('explain')
        self.app.wait(run, ('done', 'failed'), 30)
        status, body = asgi(app, 'GET', f'/api/runs/{run}/events', {**host, 'X-EAOS-Token': self.app.token, 'Last-Event-ID': '2'})
        self.assertEqual(status, 200)
        self.assertTrue(body.decode().startswith('id: 3'), body[:300])
        posting = {**host, 'X-EAOS-Token': self.app.token, 'X-EAOS-CSRF': self.app.csrf, 'Origin': 'http://127.0.0.1:8765', 'content-type': 'application/json'}
        status, body = asgi(app, 'POST', '/api/runs/reorder', posting, b'{"order": []}')
        self.assertEqual((status, json.loads(body)), (200, {'queue': []}))


class ReportDecisions(Base):
    """A decision the report asks, answered in the Studio: saved once, handed to the assistant as context, never as consent."""

    def setUp(self):
        super().setUp()
        self.question = {'id': 'ideal-choice', 'question': 'Which design?', 'options': [{'id': 'a', 'label': 'Keep it'}, {'id': 'b', 'label': 'Replace it'}],
                         'blocks': ['TASK-001'], 'asked': '2026-10-09', 'tool': 'replan_ideal', 'state': 'waiting'}
        self.write_question()

    def write_question(self):
        (self.studio / 'decisions.json').write_text(json.dumps({'decisions': [self.question]}))

    def answer_report(self, option='a', text=None, app=None):
        _, payload = self.get('/api/decisions', app)
        return self.post('/api/decisions/ideal-choice/answer', {'scope': payload['decisions'][0]['scope'], 'option': option, 'text': text}, app)

    def response(self, app=None):
        return self.get('/api/decisions', app)[1]['decisions'][0]['response']

    def test_an_answer_queues_one_run_with_its_exact_input_once_across_threads_restarts_and_languages(self):
        self.question['revision'] = 'source-question-v1'
        self.write_question()
        results = []
        threads = [threading.Thread(target=lambda: results.append(self.answer_report())) for _ in range(5)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertTrue(all(status == 200 for status, _ in results), results)
        self.assertEqual(len({p['decision']['response']['run'] for _, p in results}), 1)
        row = results[0][1]['decision']
        self.assertEqual(row['response']['label'], 'Keep it')
        run = row['response']['run']
        prompt = self.app.manager.prompt_of(self.app.store.load(run))
        for needle in ('Which design?', 'Keep it', 'TASK-001', 'not merge'): self.assertIn(needle, prompt)
        self.assertEqual(self.answer_report()[1]['decision']['response']['run'], run)
        self.assertEqual(len(self.app.store.all()), 1)
        self.assertEqual(self.response(self.make())['run'], run, 'a restarted server reads the same answer')
        self.assertEqual(self.question, json.loads((self.studio / 'decisions.json').read_text())['decisions'][0], 'the report is not rewritten')
        self.question['question'] = 'أي تصميم؟'
        self.question['options'][0]['label'] = 'احتفظ به'
        self.write_question()
        self.assertEqual(self.response()['run'], run, 'the same revision in another language is the same question')

    def test_later_plans_fixes_and_the_ideal_planner_receive_the_saved_answer_as_context_only(self):
        from eaos.studio import ideal
        self.answer_report(None, '  Preserve this exact planning choice.  ')
        for verb in ('plan', 'fix'):
            prompt = self.app.manager.prompt_of(self.app.store.load(self.start(verb)))
            self.assertIn('Which design?', prompt)
            self.assertIn('  Preserve this exact planning choice.  ', prompt)
            self.assertIn('context only, never authorization', prompt)
        waiting = ideal.bundle(self.studio.parent, project=self.project)['decisions']['waiting_for_the_person']
        self.assertEqual((waiting[0]['owner_answer']['text'], waiting[0]['state']), ('  Preserve this exact planning choice.  ', 'owner_answer_saved'))

    def test_a_wrong_answer_is_refused_and_a_custom_one_kept_exactly_for_this_project_and_question_only(self):
        self.app.close()
        app = self.make(adapters_={})
        for option, text in (('missing', None), (None, '   '), (None, 'x' * 4001), ('a', 'arbitrary')):
            self.assertEqual(self.answer_report(option, text, app)[0], 400, (option, text))
        self.assertEqual(self.post('/api/decisions/ideal-choice/answer', {'scope': 'wrong', 'option': 'a'}, app)[0], 409)
        self.assertEqual(app.handle('POST', '/api/decisions/ideal-choice/answer', self.headers(app, **{'X-EAOS-CSRF': 'bad'}), {})[0], 403)
        self.assertEqual(app.handle('GET', '/api/decisions', self.headers(app, **{'X-EAOS-Token': 'bad'}))[0], 401)
        text = '  Something entirely different\nPlease explain first.  '
        row = self.answer_report(None, text, app)[1]['decision']
        self.assertEqual(row['response']['text'], text)
        saved = app.store.load(row['response']['run'])
        self.assertIn(text, saved['owner_decision']['answer']['text'])
        self.assertNotIn('person_agreed', saved['inputs'])
        # The trial of 2026-10-12: a review of the owner's answer followed `status` into running the app, was refused the
        # tool (its run reads only) and then asked the owner to edit Claude Code's permission files.
        prompt = app.manager.prompt_of(saved)
        self.assertIn('start nothing', prompt)
        self.assertIn('never ask the person to change permissions', prompt)
        self.assertEqual(app.wait(row['response']['run'], ['waiting_for_person'], timeout=4)['mode'], 'handoff', 'no assistant: handed over')
        self.assertEqual(self.answer_report('b', None, app)[0], 409, 'already answered')
        other_project = self.base / 'another-project'
        other_project.mkdir()
        other = actions.Actions(other_project, port=8765, studio=self.studio, adapters={})
        self.apps.append(other)
        self.assertIsNone(self.response(other))
        self.write_question()
        self.assertEqual(self.response(app)['run'], row['response']['run'], 'a refreshed report keeps the answer')
        self.question['question'] = 'A different question with the same id?'
        self.write_question()
        self.assertIsNone(self.response(app), 'a new question does not inherit')

    def test_a_failed_run_is_retried_with_the_same_choice_and_never_edits(self):
        os.environ['FAKE_MODE'] = 'fail'
        run = self.answer_report()[1]['decision']['response']['run']
        self.assertEqual(self.app.wait(run, ['failed'], 5)['state'], 'failed')
        os.environ.update(FAKE_MODE='slow', FAKE_SECONDS='0.2')
        self.assertEqual(self.post(f'/api/runs/{run}/retry')[0], 200)
        self.assertEqual(self.app.wait(run, ['done'], 5)['state'], 'done')
        self.assertEqual(self.response()['option'], 'a')
        self.assertEqual(len(self.app.store.all()), 1)
        argv = [json.loads(line) for line in (self.base / 'argv.jsonl').read_text().splitlines() if '-p' in json.loads(line)]
        self.assertTrue(all('mcp__eaos__fix_edit' not in call[call.index('--allowedTools') + 1:call.index('--disallowedTools')] for call in argv))


if __name__ == '__main__':
    unittest.main()
