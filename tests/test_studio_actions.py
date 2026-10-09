"""The command centre (docs/STUDIO.md D8, eaos/studio/actions): the contract, the locks, the event log, the adapters on
real recorded streams, and runs end to end with a fake assistant (tests/fixtures/studio/actions/fake_assistant.py)."""
import json
import os
import re
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
    def test_the_packaged_contract_is_the_documented_one_and_names_every_tool(self):
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

    def test_every_endpoint_of_the_contract_is_routed(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, {'EAOS_HOME': folder}):
            project = Path(folder) / 'p'
            project.mkdir()
            app = actions.Actions(project, port=8765, adapters={})
            try:
                run = 'r-none'
                for row in actions.contract()['endpoints']:
                    path = row['path'].replace('<id>/answer', 'r-none-q1/answer').replace('<id>', run if row['path'].startswith('/api/runs') else 'status')
                    headers = {'X-EAOS-Token': app.token, 'X-EAOS-CSRF': app.csrf, 'Origin': 'http://127.0.0.1:8765', 'Host': '127.0.0.1:8765'}
                    status, payload = app.handle(row['method'], path, headers, {})
                    if '<id>' in row['path'] and 'runs' in row['path'] or 'questions/' in path or 'decisions/' in path:
                        self.assertIn(status, (403, 404, 409), (row, payload))      # a run that does not exist, not an unknown route
                        if status == 404: self.assertIn('r-none', payload['error'], row)
                    else:
                        self.assertNotEqual(status, 404, (row, payload))
            finally:
                app.close()


class Locks(Base):
    def test_every_post_needs_the_token_the_csrf_token_and_the_studio_origin(self):
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

    def test_every_refusal_is_logged_with_its_reason_and_never_the_token(self):
        self.app.handle('GET', f'/api/runs?token=wrong-{self.app.token[:5]}', {'Host': '127.0.0.1:8765'}, None)
        self.app.handle('POST', '/api/runs', {**self.headers(), 'X-EAOS-CSRF': 'bad'}, {})
        text = (self.app.store.folder / 'refused.jsonl').read_text()
        rows = [json.loads(line) for line in text.splitlines()]
        self.assertEqual([(r['method'], r['path']) for r in rows], [('GET', '/api/runs'), ('POST', '/api/runs')])
        self.assertIn('CSRF', rows[1]['reason'])
        self.assertNotIn(self.app.token, text)
        self.assertNotIn(self.app.token[:5], text)

    def test_a_get_takes_the_token_from_the_query_but_a_post_does_not(self):
        host = {'Host': 'localhost:8765'}
        self.assertEqual(self.app.handle('GET', f'/api/session?token={self.app.token}', host, None)[0], 200)
        self.assertEqual(self.app.handle('GET', '/api/session?token=nope', host, None)[0], 401)
        self.assertEqual(self.app.handle('POST', f'/api/runs/reorder?token={self.app.token}', {**host, 'X-EAOS-CSRF': self.app.csrf,
                                                                                                  'Origin': 'http://localhost:8765'}, {})[0], 401)

    def test_a_confirm_token_is_single_use_bound_and_expires(self):
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

    def test_a_fix_run_without_its_confirmation_is_refused_and_not_queued(self):
        status, payload = self.post('/api/runs', {'action': 'fix', 'verb': 'fix', 'selection': {'kind': 'card', 'cards': ['TASK-001']}})
        self.assertEqual((status, payload.get('needs')), (403, 'confirm'))
        self.assertEqual(self.app.store.all(), [])
        status, _ = self.post('/api/runs', {'action': 'accept', 'inputs': {'person_agreed': True}})
        self.assertEqual(status, 403)


class EventLog(unittest.TestCase):
    def test_events_are_gapless_hash_chained_and_tampering_shows(self):
        with tempfile.TemporaryDirectory() as folder:
            log = store.Store(Path(folder) / 'runs', store.Scrubber(folder))
            log.save({'id': 'r1', 'state': 'queued'}, new=True)
            for index in range(5): log.append('r1', 'step', f'step {index}', {'n': index})
            events = log.events('r1')
            self.assertEqual([e['seq'] for e in events], [1, 2, 3, 4, 5])
            self.assertEqual(events[0]['prev'], store.ZERO)
            self.assertEqual(log.verify('r1'), [])
            self.assertEqual([e['seq'] for e in log.events('r1', after=3)], [4, 5])
            path = Path(folder) / 'runs/r1/events.jsonl'
            path.write_text(path.read_text().replace('step 2', 'step X'))
            self.assertTrue(log.verify('r1'))

    def test_no_secret_home_or_project_path_is_written(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder) / 'project'
            log = store.Store(Path(folder) / 'runs', store.Scrubber(project, ['launch-token-value']))
            log.save({'id': 'r1'}, new=True)
            words = (f'{project}/src/a.py and {Path.home()}/x with sk-ant-abcdefghijklmnopqrstuv ghp_abcdefghijklmnopqrstuvwxyz0123 '
                     'Bearer abcdefghijklmnopqrstuvwxyz and launch-token-value')
            event = log.append('r1', 'say', words, {'nested': [words]}, words)
            text = json.dumps(event)
            for leaked in ('sk-ant-', 'ghp_', 'abcdefghijklmnopqrstuvwxyz', 'launch-token-value', str(project), str(Path.home()) + '/x'):
                self.assertNotIn(leaked, text)
            self.assertIn('src/a.py', event['text']['en'])

    def test_a_huge_diff_is_cut(self):
        with tempfile.TemporaryDirectory() as folder:
            log = store.Store(Path(folder) / 'runs', store.Scrubber(folder))
            log.save({'id': 'r1'}, new=True)
            event = log.append('r1', 'edit', 'big', {'diff': 'x' * (store.DIFF_LIMIT + 10)})
            self.assertTrue(event['data']['cut'])
            self.assertLess(len(event['data']['diff']), store.DIFF_LIMIT + 100)


class Adapters(unittest.TestCase):
    labels = {a['id']: a['label'] for a in actions.contract()['actions']}

    def parse(self, adapter, name):
        state, events = adapter.new_state(), []
        for line in (FIXTURES / name).read_text(encoding='utf-8').splitlines(): events += adapter.parse(line, state, self.labels)
        return state, events

    def test_a_real_claude_code_stream_reads_as_plain_events(self):
        state, events = self.parse(adapters.ClaudeCode(), 'claude-stream.jsonl')
        self.assertEqual(state['session'], 'cdf7b362-ed33-4731-9bc7-19ce5cbc4c70')
        self.assertIsNone(state['failed'])
        kinds = [kind for kind, *_ in events]
        self.assertEqual(kinds[0], 'step')
        self.assertIn('read', kinds)
        self.assertEqual(kinds[-1], 'say')
        handed = [data for kind, _, data, _ in events if kind == 'check' and data.get('branch')]
        self.assertEqual(handed[0]['branch'], 'eaos/wave-1')
        self.assertNotIn('ToolSearch', json.dumps([text for _, text, _, _ in events]))
        self.assertIn('eaos/wave-1', state['final'])

    def test_a_real_codex_stream_reads_as_plain_events(self):
        state, events = self.parse(adapters.Codex(), 'codex-stream.jsonl')
        self.assertEqual(state['session'], '01a0ef94-aacd-7503-b6a1-7c0910b2a2b8')
        progress = [data for kind, _, data, _ in events if kind == 'progress']
        self.assertTrue(progress and all(p['total'] == 26 for p in progress))
        steps = [data.get('tool') for kind, _, data, _ in events if kind == 'step']
        self.assertIn('audit', steps)
        self.assertIn('command', steps)
        self.assertTrue(any(tool == 'run_setup' and isinstance(payload, dict) and payload.get('status') == 'needs_agreement'
                            for tool, payload in state['eaos_results']))

    def test_real_explain_runs_started_by_the_studio_read_as_plain_events(self):
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

    def test_an_edit_carries_its_diff_and_a_check_its_verdict(self):
        events = adapters.tool_events('fix_edit', {'card': 'TASK-1', 'edits': [{'path': 'a.py', 'find': 'x = 1\n', 'replace': 'x = 2\n'},
                                                                               {'path': 'b.py', 'content': 'new\n'}, {'path': 'c.py', 'delete': True}]}, self.labels)
        kind, _, data, _ = events[0]
        self.assertEqual((kind, data['paths']), ('edit', ['a.py', 'b.py', 'c.py']))
        self.assertIn('-x = 1', data['diff'])
        self.assertIn('+new', data['diff'])
        self.assertIn('(deleted)', data['diff'])
        checks = adapters.result_events('wait', {}, {'status': 'done', 'result': {'kept': False, 'card': 'TASK-1', 'why': 'a test broke'}})
        self.assertEqual(checks[0][0], 'check')
        self.assertFalse(checks[0][2]['passed'])

    def test_claude_code_starts_with_eaos_only_and_without_the_person_only_tools(self):
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
        allowed = argv[argv.index('--allowedTools') + 1:argv.index('--disallowedTools')]
        self.assertEqual(allowed, ['mcp__eaos__status', 'mcp__eaos__finding', 'Read', 'Grep', 'Glob'])

    def test_the_runs_mcp_server_is_this_eaos_never_another_on_the_path(self):
        with mock.patch('shutil.which', return_value='/usr/local/bin/eaos'):
            argv, env = adapters.eaos_server('r1', 'Codex')
        self.assertEqual(argv, [sys.executable, '-m', 'eaos', 'mcp'])
        self.assertEqual(Path(env['PYTHONPATH']), ROOT)
        self.assertEqual((env['EAOS_STUDIO_RUN'], env['EAOS_ASSISTANT']), ('r1', 'Codex'))

    def test_codex_starts_read_only_with_the_eaos_server_and_resumes_its_thread(self):
        argv = adapters.Codex(command=['codex']).argv('go on', 'r1', Path('.'), session='t1')
        self.assertEqual(argv[:3], ['codex', 'exec', 'resume'])
        self.assertIn('sandbox_mode="read-only"', argv)
        server = next(a for a in argv if a.startswith('mcp_servers.eaos='))
        self.assertIn('EAOS_STUDIO_RUN="r1"', server)
        self.assertEqual(argv[-2:], ['t1', 'go on'])
        self.assertIn('disabled_tools=["accept", "undo", "choose_branch"]', server)
        limited = next(a for a in adapters.Codex(command=['codex']).argv('x', 'r1', Path('.'), tools=['status']) if a.startswith('mcp_servers.eaos='))
        self.assertIn('enabled_tools=["status"]', limited)
        self.assertNotIn('disabled_tools', limited)

    def test_detection_says_installed_and_logged_in(self):
        with mock.patch.dict(os.environ, {'FAKE_LOGGED_IN': '0'}):
            found = adapters.ClaudeCode(command=[sys.executable, str(FAKE)]).detect(fresh=True)
        self.assertEqual((found['installed'], found['logged_in']), (True, False))
        self.assertTrue(adapters.ClaudeCode(command=[sys.executable, str(FAKE)]).available())
        self.assertFalse(adapters.ClaudeCode(command=['/nonexistent/claude']).detect()['installed'])

    def test_a_probe_that_times_out_keeps_the_last_detection(self):
        ready = adapters.ClaudeCode(command=[sys.executable, str(FAKE)])
        self.assertTrue(ready.detect(fresh=True)['logged_in'])
        with mock.patch.object(adapters.ClaudeCode, '_run', return_value=None):
            self.assertEqual((ready.detect(fresh=True)['installed'], ready.detect(fresh=True)['logged_in']), (True, True))
            self.assertFalse(adapters.ClaudeCode(command=[sys.executable, str(FAKE)]).detect(fresh=True)['installed'])


class Prompts(unittest.TestCase):
    def test_a_question_block_is_read_and_normalised(self):
        found = prompts.question_in('Words.\n```eaos-question\n{"text": "Which?", "options": ["A", {"id": "b", "label": "B"}], "recommendation": "b"}\n```')
        self.assertEqual(found['text'], {'en': 'Which?', 'ar': 'Which?'})
        self.assertEqual([o['id'] for o in found['options']], ['o1', 'b'])
        self.assertEqual(found['recommendation'], 'b')
        self.assertIsNone(prompts.question_in('```eaos-question\n{not json}\n```'))
        self.assertIsNone(prompts.question_in('no block'))
        self.assertIsNone(prompts.question_in('```eaos-question\n{"text": "x", "options": [], "recommendation": "zz"}\n```')['recommendation'])

    def test_a_fix_prompt_keeps_the_eaos_way_and_the_persons_decisions(self):
        text = prompts.build('fix', [{'id': 'TASK-1', 'title': 'T', 'paths': ['a.py']}], Path('/p/shop'), 'ar')
        for needle in ('fix_start', 'fix_edit', 'fix_finish', 'TASK-1', 'eaos-question', 'Do not call accept, undo or choose_branch', 'Arabic'):
            self.assertIn(needle, text)
        self.assertNotIn('/p/shop', text)


class Selection(Base):
    def test_every_kind_of_selection_resolves_to_open_cards(self):
        (self.studio / 'gaps.json').write_text(json.dumps({'gaps': [{'id': 'g1', 'component': 'orders', 'cards': ['TASK-002', 'TASK-003']}]}))
        (self.studio / 'operations.json').write_text(json.dumps({'operations': [{'id': 'op1', 'cards': ['TASK-004']}]}))
        ids = lambda s: [c['id'] for c in selection.resolve(s, self.studio)[0]]
        self.assertEqual(ids({'kind': 'group', 'group': {'by': 'severity', 'value': 'high'}}), ['TASK-001', 'TASK-004'])
        self.assertEqual(ids({'kind': 'group', 'group': {'by': 'area', 'value': 'security'}}), ['TASK-002'])
        self.assertEqual(ids({'kind': 'group', 'group': {'by': 'component', 'value': 'orders'}}), ['TASK-002'])
        self.assertEqual(ids({'kind': 'group', 'group': {'by': 'gap', 'value': 'g1'}}), ['TASK-002'])
        self.assertEqual(ids({'kind': 'group', 'group': {'by': 'operation', 'value': 'op1'}}), ['TASK-004'])
        self.assertEqual(ids({'kind': 'step', 'step': 'M2'}), ['TASK-004'])
        self.assertEqual(ids({'kind': 'card', 'cards': ['TASK-002', 'TASK-001']}), ['TASK-002'])
        _, left = selection.resolve({'kind': 'cards', 'cards': ['TASK-001', 'TASK-003']}, self.studio)
        self.assertEqual(left, [{'id': 'TASK-003', 'why': 'already done'}])

    def test_a_selection_that_cannot_run_is_refused_with_its_reason(self):
        for bad, why in (({'kind': 'cards', 'cards': ['NOPE']}, 'no card named'), ({'kind': 'cards', 'cards': ['TASK-003']}, 'already handled'),
                         ({'kind': 'group', 'group': {'by': 'gap', 'value': 'g'}}, 'gap register'), ({'kind': 'x'}, 'kind'),
                         ({'kind': 'step', 'step': 'M9'}, 'names no card')):
            with self.assertRaisesRegex(selection.SelectionError, why): selection.resolve(bad, self.studio)
        status, payload = self.post('/api/actions/fix/preview', {'verb': 'fix', 'selection': {'kind': 'cards', 'cards': ['NOPE']}})
        self.assertEqual(status, 400)

    def test_a_fix_preview_names_files_batches_time_risk_and_the_assistant(self):
        many = [card(f'TASK-{n:03d}') for n in range(10, 32)]
        (self.studio / 'cards.json').write_text(json.dumps({'cards': many}))
        status, preview = self.post('/api/actions/fix/preview', {'verb': 'fix', 'selection': {'kind': 'group', 'group': {'by': 'severity', 'value': 'high'}}})
        self.assertEqual(status, 200, preview)
        self.assertEqual([len(b['cards']) for b in preview['batches']], [10, 10, 2])
        self.assertEqual(len(preview['files']), 22)
        self.assertEqual(preview['risk']['level'], 'high')
        self.assertLess(preview['estimate']['minutes_low'], preview['estimate']['minutes_high'])
        self.assertEqual(preview['assistant']['name'], 'Claude Code')
        self.assertTrue(preview['confirm']['token'] and preview['on_failure']['ar'])
        status, preview = self.post('/api/actions/explain/preview', {'verb': 'explain', 'selection': {'kind': 'card', 'cards': ['TASK-010']}})
        self.assertEqual((preview['risk']['level'], preview['confirm'], preview['batches']), ('low', None, []))


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

    def test_one_run_at_a_time_and_the_queue_is_reordered(self):
        os.environ.update(FAKE_MODE='slow', FAKE_SECONDS='2')
        first, second, third = (self.start('explain', cards=(c,)) for c in ('TASK-001', 'TASK-002', 'TASK-004'))
        self.assertEqual(self.app.wait(first, ('running',), 10)['state'], 'running')
        self.assertEqual(self.get('/api/runs')[1]['queue'], [second, third])
        self.assertEqual(self.post('/api/runs/reorder', {'order': [third]})[1]['queue'], [third, second])
        self.assertEqual(self.post('/api/runs/reorder', {'order': [first]})[0], 409)
        self.assertEqual(self.get(f'/api/runs/{third}')[1]['run']['position'], 1)
        self.assertEqual(self.app.wait(first, ('done',), 20)['state'], 'done')
        self.assertEqual(self.app.wait(third, ('running', 'done'), 20)['state'] in ('running', 'done'), True)
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
        while time.monotonic() < deadline and pid and adapters_alive(pid): time.sleep(0.2)
        self.assertFalse(pid and adapters_alive(pid))
        self.assertEqual(self.post(f'/api/runs/{run}/stop')[0], 409)
        os.environ['FAKE_MODE'] = 'question'
        self.assertEqual(self.post(f'/api/runs/{run}/retry')[1]['run']['state'], 'queued')
        again = self.app.wait(run, ('waiting_for_person', 'failed'), 30)
        self.assertEqual((again['state'], again['attempt']), ('waiting_for_person', 2))
        self.assertEqual(self.app.store.verify(run), [])

    def test_a_failing_assistant_fails_the_run_with_its_reason(self):
        for mode, words in (('fail', 'the model is not available'), ('crash', 'code 3')):
            os.environ['FAKE_MODE'] = mode
            run = self.start('explain')
            self.assertEqual(self.app.wait(run, ('failed', 'done'), 30)['state'], 'failed')
            errors = [e for e in self.app.store.events(run) if e['kind'] == 'error']
            self.assertIn(words, errors[-1]['data']['reason'])

    def test_a_real_recorded_stream_runs_to_a_result(self):
        os.environ['FAKE_MODE'] = 'replay'
        run = self.start('explain')
        done = self.app.wait(run, ('done', 'failed', 'waiting_for_person'), 30)
        self.assertEqual(done['state'], 'done', self.app.store.events(run)[-3:])
        self.assertIn('eaos/wave-1', done['result']['answer'])
        self.assertLessEqual({'step', 'read', 'check', 'say', 'result'}, set(self.kinds(run)))

    def test_events_stream_as_sse_and_replay_from_last_event_id(self):
        os.environ['FAKE_MODE'] = 'replay'
        run = self.start('explain')
        frames = []
        reader = threading.Thread(target=lambda: frames.extend(self.app.sse(run, follow=True, heartbeat=0.5)), daemon=True)
        reader.start()
        reader.join(30)
        self.assertFalse(reader.is_alive())
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


def adapters_alive(pid):
    from eaos.studio.actions.runs import alive
    return alive(pid)


class Direct(Base):
    def fake_tools(self, answers):
        calls = []
        def tool(name):
            def call(**arguments):
                calls.append((name, arguments))
                answer = answers.get(name, {'ok': True})
                return json.dumps(answer(arguments) if callable(answer) else answer)
            return call
        return (lambda: {name: tool(name) for name in actions.contract() and {a['id'] for a in actions.contract()['actions']}}), calls

    def test_a_reading_action_answers_at_once_and_stays_out_of_the_history(self):
        self.app.manager.tools, calls = self.fake_tools({'status': {'next': 'audit'}})
        status, payload = self.post('/api/runs', {'action': 'status'})
        self.assertEqual((status, payload['run']['state']), (200, 'done'))
        self.assertEqual(payload['run']['result']['answer'], {'next': 'audit'})
        self.assertEqual(calls, [('status', {'project': str(self.project.resolve())})])
        self.assertEqual(self.get('/api/runs')[1]['runs'], [])
        self.assertEqual(len(self.get('/api/runs?all=1')[1]['runs']), 1)
        self.assertEqual(self.post('/api/runs', {'action': 'findings', 'inputs': {'limit': 'many'}})[0], 400)

    def test_a_job_action_is_followed_with_its_progress(self):
        from eaos import jobs
        state = {'n': 0}
        def read(job):
            state['n'] += 1
            if state['n'] < 3: return {'id': job, 'kind': 'audit', 'status': 'running', 'progress': {'done': state['n'], 'total': 3, 'stage': 'engines'}}
            return {'id': job, 'kind': 'audit', 'status': 'done', 'result': {'overview': 'fine'}}
        self.app.manager.tools, _ = self.fake_tools({'audit': {'job': 'audit-1', 'status': 'running'}})
        with mock.patch.object(jobs, 'read', side_effect=read):
            run = self.post('/api/runs', {'action': 'audit'})[1]['run']['id']
            done = self.app.wait(run, ('done', 'failed'), 20)
        self.assertEqual(done['state'], 'done')
        self.assertEqual([e['data']['done'] for e in self.app.store.events(run) if e['kind'] == 'progress'], [1, 2])

    def test_a_direct_step_that_needs_consent_asks_in_the_inbox(self):
        self.app.manager.tools, calls = self.fake_tools({'run_setup': lambda a: {'job': 'j', 'status': 'done'} if a.get('person_agreed')
                                                         else {'status': 'needs_agreement', 'ask_the_person': 'May EAOS run your app?'}})
        run = self.post('/api/runs', {'action': 'run_setup'})[1]['run']['id']
        self.assertEqual(self.app.wait(run, ('waiting_for_person',), 10)['state'], 'waiting_for_person')
        question = self.get('/api/questions')[1]['questions'][0]
        self.assertEqual(question['why'], 'run consent')
        self.post(f"/api/questions/{question['id']}/answer", {'option': 'yes'})
        self.assertEqual(self.app.wait(run, ('done', 'failed'), 10)['state'], 'done')
        self.assertEqual(calls[-1][1].get('person_agreed'), True)

    def test_custom_setup_answer_clarifies_then_still_requires_explicit_consent(self):
        os.environ.update(FAKE_MODE='slow', FAKE_SECONDS='0.2')
        self.app.manager.tools, calls = self.fake_tools({'run_setup': lambda a: {'status': 'done'} if a.get('person_agreed')
                                                         else {'status': 'needs_agreement', 'ask_the_person': 'May EAOS run your app?'}})
        run = self.post('/api/runs', {'action': 'run_setup'})[1]['run']['id']
        self.app.wait(run, ('waiting_for_person',), 5)
        question = self.get('/api/questions')[1]['questions'][0]
        path = f"/api/questions/{question['id']}/answer"
        text = '  Yes is a word, but explain first.\nAn unrelated request.  '
        self.assertEqual(self.post(path, {'option': 'yes', 'text': text})[0], 400)
        self.assertEqual(self.post(path, {'option': ['yes']})[0], 400)
        self.assertEqual(self.post(path, {'text': '   '})[0], 400)
        self.assertEqual(self.post(path, {'text': 'x' * 4001})[0], 400)
        self.assertEqual(self.post(path, {'text': text})[0], 200)
        self.assertEqual(self.post(path, {'text': text})[0], 200)
        record = self.app.wait(run, ('waiting_for_person',), 5)
        self.assertEqual(record['mode'], 'direct')
        self.assertNotEqual(record['question']['id'], question['id'])
        self.assertEqual(record['answered'][0]['text'], text)
        self.assertEqual(record['question']['why'], 'run consent')
        self.assertFalse(any(args.get('person_agreed') for _, args in calls))
        again = self.make()
        reread = again.store.load(run)
        self.assertEqual(reread['answered'][0]['text'], text)
        self.assertEqual(reread['question']['options'], question['options'])
        self.assertEqual(self.post(f"/api/questions/{reread['question']['id']}/answer", {'option': 'yes'})[0], 200)
        self.assertEqual(self.app.wait(run, ('done', 'failed'), 5)['state'], 'done')
        self.assertTrue(calls[-1][1]['person_agreed'])

    def test_the_checks_branch_question_is_asked_in_the_studio_and_the_choice_runs_it_again(self):
        branches = [{'name': 'main', 'main': True}, {'name': 'work', 'ahead_of_main': 3}]
        asked = {'status': 'needs_branch', 'branches': branches, 'recommended': 'work'}
        chosen = []
        self.app.manager._choose_branch = lambda branch, said: chosen.append((branch, said))
        self.app.manager.tools, calls = self.fake_tools({'audit': lambda arguments: asked if not chosen else {'status': 'started', 'checked': True}})
        run = self.post('/api/runs', {'action': 'audit'})[1]['run']['id']
        question = self.app.wait(run, ('waiting_for_person', 'done'), 5)['question']
        self.assertEqual((question['why'], question['recommendation']), ('branch', 'work'))
        self.assertEqual([o['id'] for o in question['options']], ['main', 'work'])
        self.assertEqual(self.post(f"/api/questions/{question['id']}/answer", {'option': 'main'})[0], 200)
        self.assertEqual(self.app.wait(run, ('done', 'failed'), 5)['state'], 'done')
        self.assertEqual(chosen, [('main', 'main (main)')])
        self.assertEqual([name for name, _ in calls], ['audit', 'audit'])

    def test_failed_custom_clarification_preserves_the_original_question(self):
        os.environ['FAKE_MODE'] = 'fail'
        self.app.manager.tools, calls = self.fake_tools({'run_setup': {'status': 'needs_agreement', 'ask_the_person': 'May EAOS run?'}})
        run = self.post('/api/runs', {'action': 'run_setup'})[1]['run']['id']
        original = self.app.wait(run, ('waiting_for_person',), 5)['question']
        self.assertEqual(self.post(f"/api/questions/{original['id']}/answer", {'text': 'Explain first'})[0], 200)
        record = self.app.wait(run, ('waiting_for_person',), 5)
        self.assertEqual(record['question']['why'], 'run consent')
        self.assertEqual(record['answered'][0]['text'], 'Explain first')
        self.assertFalse(any(args.get('person_agreed') for _, args in calls))
        self.assertIn('error', self.kinds(run))

    def test_accept_and_undo_need_their_confirmation_and_a_branch(self):
        self.app.manager.tools, calls = self.fake_tools({'accept': {'status': 'accepted', 'branch': 'eaos/wave-1'}})
        record = {'id': 'r-fix', 'action': 'fix', 'verb': 'fix', 'mode': 'assistant', 'state': 'done', 'label': {'en': 'x', 'ar': 'x'},
                  'created': '0', 'result': {'branch': 'eaos/wave-1'}}
        self.app.store.save(record, new=True)
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

    def test_undo_after_accept_and_a_decision_on_another_runs_branch_are_refused(self):
        self.app.manager.tools, calls = self.fake_tools({'undo': {'status': 'nothing_to_undo'}, 'accept': {'status': 'accepted'}})
        for run, branch, outcome in (('r-old', 'eaos/wave-1', 'accepted'), ('r-two', 'eaos/wave-2', None), ('r-three', 'eaos/wave-3', None)):
            self.app.store.save({'id': run, 'action': 'fix', 'verb': 'fix', 'mode': 'assistant', 'state': 'done', 'label': {'en': 'x', 'ar': 'x'},
                                 'created': '0', 'result': {'branch': branch}, **({'outcome': outcome} if outcome else {})}, new=True)
        self.app.manager.newest_waiting = lambda: 'eaos/wave-3'
        undo = lambda run: self.post(f'/api/runs/{run}/undo', {'confirm': self.post('/api/actions/undo/preview')[1]['confirm']['token']})
        self.assertEqual(undo('r-old')[0], 409)
        self.assertEqual(undo('r-two')[0], 409)
        self.assertEqual(calls, [])
        self.app.manager.newest_waiting = lambda: None
        self.assertEqual(undo('r-three')[0], 409)
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
        from eaos import mcp_server
        with mock.patch('eaos.build_tools.status_of', side_effect=lambda project: {'next': 'audit'}), mock.patch.dict(os.environ, {'EAOS_ASSISTANT': 'Codex'}):
            answer = mcp_server._status(str(self.project))
            self.assertEqual(mcp_server._status(str(self.project)), {'next': 'audit'})
        self.assertEqual(answer['studio_request']['id'], run)
        self.assertIn('TASK-001', answer['studio_request']['request'])
        self.assertEqual(app.wait(run, ('running',), 10)['state'], 'running')
        self.assertIsNone(handoff.close(self.project, 'studio-request other done'))
        self.assertEqual(handoff.close(self.project, f'studio-request {run} done: fixed TASK-001'), run)
        done = app.wait(run, ('done',), 10)
        self.assertEqual(done['result']['answer'], 'fixed TASK-001')
        self.assertEqual(handoff.pending(self.project), [])

    def test_the_request_waits_in_the_eaos_workspace_never_in_the_project(self):
        handoff.add(self.project, 'r1', 'do it', {'en': 'x', 'ar': 'x'})
        self.assertEqual(list(self.project.rglob('studio-requests.json')), [])
        written = list((self.base / 'home').rglob('studio-requests.json'))
        self.assertEqual(len(written), 1)
        self.assertIn('studio-request r1 done', json.loads(written[0].read_text())[0]['request']['en'])

    def test_the_studios_own_status_call_does_not_take_the_request(self):
        handoff.add(self.project, 'r1', 'do it', {'en': 'x', 'ar': 'x'})
        from eaos import mcp_server
        with mock.patch('eaos.build_tools.status_of', return_value={}), mock.patch.dict(os.environ, {'EAOS_ASSISTANT': mcp_server.STUDIO}):
            self.assertEqual(mcp_server._status(str(self.project)), {})
        self.assertEqual(len(handoff.pending(self.project)), 1)

    def test_in_a_studio_run_the_person_only_tools_refuse(self):
        from eaos import mcp_server
        with mock.patch.dict(os.environ, {'EAOS_STUDIO_RUN': 'r1'}):
            for tool in mcp_server.PERSON_ONLY:
                answer = json.loads(mcp_server.functions()[tool](project=str(self.project), **({'branch': 'x'} if tool == 'choose_branch' else {})))
                self.assertIn('the person', answer['error'])


class Serving(Base):
    def test_the_stdlib_server_serves_the_api_and_the_stream_on_loopback_only(self):
        from eaos.studio.actions import serve
        os.environ['FAKE_MODE'] = 'replay'
        server = serve.serve(self.app, 0)
        port = server.server_address[1]
        self.assertEqual(server.server_address[0], '127.0.0.1')
        app = self.make()
        app.locks.port = port
        server.RequestHandlerClass.actions = app
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        base = f'http://127.0.0.1:{port}'
        def call(method, path, body=None, headers=None):
            request = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                             headers={'X-EAOS-Token': app.token, **(headers or {})})
            try:
                with urllib.request.urlopen(request, timeout=30) as response: return response.status, response.read().decode()
            except urllib.error.HTTPError as problem: return problem.code, problem.read().decode()
        status, text = call('GET', '/api/session')
        self.assertEqual((status, json.loads(text)['csrf']), (200, app.csrf))
        self.assertEqual(call('POST', '/api/runs', {'action': 'status'})[0], 403)
        posting = {'X-EAOS-CSRF': app.csrf, 'Origin': f'http://127.0.0.1:{port}', 'Content-Type': 'application/json'}
        preview = json.loads(call('POST', '/api/actions/explain/preview', {'verb': 'explain', 'selection': {'kind': 'card', 'cards': ['TASK-001']}}, posting)[1])
        status, text = call('POST', '/api/runs', {'action': 'explain', 'verb': 'explain', 'selection': {'kind': 'card', 'cards': ['TASK-001']}}, posting)
        self.assertEqual(status, 200, text)
        run = json.loads(text)['run']['id']
        status, stream = call('GET', f'/api/runs/{run}/events', headers={'Last-Event-ID': '0'})
        self.assertEqual(status, 200)
        self.assertIn('event: result', stream)
        self.assertIsNone(preview['confirm'])


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


@unittest.skipUnless(__import__('importlib').util.find_spec('starlette'), 'starlette not installed')
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


class Measure(unittest.TestCase):
    def test_f15_counts_only_complete_real_trials_and_needs_fleetmanageweb(self):
        sys.path.insert(0, str(ROOT / 'tools'))
        import north_star_studio
        good = {'assistant': 'Claude Code', 'audited': True, 'selection': {'kind': 'group', 'cards': ['A', 'B']}, 'cards_fixed': ['A'],
                'questions_answered_in_inbox': 1, 'accepted': True, 'typed_to_assistant': 0, 'understood': {'run': True}}
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(north_star_studio.command_value(folder)[0])
            def write(name, trial):
                (Path(folder) / 'studio' / name).mkdir(parents=True, exist_ok=True)
                (Path(folder) / 'studio' / name / 'trial.json').write_text(json.dumps(trial))
            write('chief-ops', good)
            self.assertEqual(north_star_studio.command_value(folder)[0], 0.0)
            write('FleetManageWeb', {**good, 'assistant': 'fake'})
            value, why = north_star_studio.command_value(folder)
            self.assertEqual(value, 0.0)
            self.assertIn('a real assistant', why)
            write('FleetManageWeb', good)
            self.assertEqual(north_star_studio.command_value(folder)[0], 0.0)
            for name in ('EAOS', 'FleetManageWeb'):
                path = Path(folder) / 'owner-controls' / name
                path.mkdir(parents=True)
                proof = {'assistant': 'Codex', 'mocked': False, 'studio_source_sha256': north_star_studio.shipped(), 'completed_at': 'now',
                         'cases': [{'id': case, 'pass': True, 'evidence': 'live observation', 'kind': 'live'} for case in north_star_studio.OWNER_CONTROL_CASES],
                         'views': [{'viewport': v, 'lang': l, 'theme': t, 'pass': True, 'screenshot': 'shot.png'} for v, l, t in north_star_studio.OWNER_CONTROL_VIEWS]}
                (path / 'trial.json').write_text(json.dumps(proof))
            self.assertEqual(north_star_studio.command_value(folder)[0], 0.0, 'branch control and scan freshness are not proven yet')
            sys.path.insert(0, str(ROOT / 'acceptance'))
            import test_branch_control, test_scan_freshness
            shot = Path(folder) / 'shot.png'
            shot.write_bytes(b'png')
            for name, module in (('branch-control', test_branch_control), ('scan-freshness', test_scan_freshness)):
                live = {'kind': 'live', 'mocked': False, 'studio_source_sha256': north_star_studio.shipped(), 'completed_at': '2026-10-09T12:00:00+00:00',
                        'cases': [{'id': case, 'pass': True, 'kind': 'live', 'evidence': 'observed'} for case in module.CASES],
                        'views': [{'viewport': v, 'lang': l, 'theme': t, 'pass': True, 'width_equals_viewport': True, 'initial_scroll_zero': True,
                                   'axe_violations': 0, 'small_targets': 0, 'screenshot': str(shot)} for v, l, t in test_branch_control.VIEWS]}
                (Path(folder) / name).mkdir()
                (Path(folder) / name / 'trial.json').write_text(json.dumps(live))
            self.assertEqual(north_star_studio.command_value(folder)[0], 1.0)
            proof['mocked'] = True
            (path / 'trial.json').write_text(json.dumps(proof))
            self.assertEqual(north_star_studio.command_value(folder)[0], 0.5)

    def test_f13_and_f14_measure_without_any_run(self):
        sys.path.insert(0, str(ROOT / 'tools'))
        import north_star_studio
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(north_star_studio.projects_value(folder)[0])
            self.assertIsNone(north_star_studio.budgets_value(folder)[0])


if __name__ == '__main__':
    unittest.main()

class ReportDecisions(Base):
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

    def test_save_queue_exact_input_restart_and_idempotency(self):
        status, payload = self.answer_report()
        self.assertEqual(status, 200, payload)
        row = payload['decision']
        self.assertEqual(row['response']['label'], 'Keep it')
        run = row['response']['run']
        prompt = self.app.manager.prompt_of(self.app.store.load(run))
        self.assertIn('Which design?', prompt)
        self.assertIn('Keep it', prompt)
        self.assertIn('TASK-001', prompt)
        self.assertIn('not merge', prompt)
        self.assertEqual(self.answer_report()[1]['decision']['response']['run'], run)
        self.assertEqual(len(self.app.store.all()), 1)
        other = self.make()
        reread = self.get('/api/decisions', other)[1]['decisions'][0]
        self.assertEqual(reread['response']['run'], run)
        self.assertEqual(self.question, json.loads((self.studio / 'decisions.json').read_text())['decisions'][0])

    def test_future_plan_fix_and_ideal_planner_receive_saved_owner_context(self):
        from eaos.studio import ideal
        self.answer_report(None, '  Preserve this exact planning choice.  ')
        for verb in ('plan', 'fix'):
            run = self.start(verb)
            prompt = self.app.manager.prompt_of(self.app.store.load(run))
            self.assertIn('Which design?', prompt)
            self.assertIn('  Preserve this exact planning choice.  ', prompt)
            self.assertIn('context only, never authorization', prompt)
        grounded = ideal.bundle(self.studio.parent, project=self.project)
        waiting = grounded['decisions']['waiting_for_the_person']
        self.assertEqual(waiting[0]['owner_answer']['text'], '  Preserve this exact planning choice.  ')
        self.assertEqual(waiting[0]['state'], 'owner_answer_saved')

    def test_invalid_option_scope_conflict_and_csrf(self):
        self.assertEqual(self.answer_report('missing')[0], 400)
        self.assertEqual(self.post('/api/decisions/ideal-choice/answer', {'scope': 'wrong', 'option': 'a'})[0], 409)
        self.assertEqual(self.app.handle('POST', '/api/decisions/ideal-choice/answer', self.headers(**{'X-EAOS-CSRF': 'bad'}), {})[0], 403)
        self.assertEqual(self.app.handle('GET', '/api/decisions', self.headers(**{'X-EAOS-Token': 'bad'}))[0], 401)
        self.assertEqual(self.answer_report()[0], 200)
        self.assertEqual(self.answer_report('b')[0], 409)

    def test_custom_exact_text_even_binary_and_empty_refused(self):
        self.assertEqual(self.answer_report(None, '   ')[0], 400)
        self.assertEqual(self.answer_report(None, 'x' * 4001)[0], 400)
        self.assertEqual(self.answer_report('a', 'arbitrary')[0], 400)
        text = '  Something entirely different\nPlease explain first.  '
        row = self.answer_report(None, text)[1]['decision']
        self.assertEqual(row['response']['text'], text)
        self.assertIn(text, self.app.store.load(row['response']['run'])['owner_decision']['answer']['text'])
        self.assertNotIn('person_agreed', self.app.store.load(row['response']['run'])['inputs'])

    def test_refresh_reconciles_and_new_question_does_not_inherit(self):
        old = self.answer_report()[1]['decision']
        self.write_question()
        self.assertEqual(self.get('/api/decisions')[1]['decisions'][0]['response']['run'], old['response']['run'])
        self.question['question'] = 'A different question with the same id?'
        self.write_question()
        self.assertIsNone(self.get('/api/decisions')[1]['decisions'][0]['response'])

    def test_concurrent_answer_has_one_run(self):
        results = []
        threads = [threading.Thread(target=lambda: results.append(self.answer_report())) for _ in range(5)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertTrue(all(status == 200 for status, _ in results), results)
        self.assertEqual(len({p['decision']['response']['run'] for _, p in results}), 1)
        self.assertEqual(len(self.app.store.all()), 1)

    def test_cross_project_isolation(self):
        self.answer_report()
        other_project = self.base / 'another-project'
        other_project.mkdir()
        other = actions.Actions(other_project, port=8765, studio=self.studio, adapters={})
        self.apps.append(other)
        self.assertIsNone(self.get('/api/decisions', other)[1]['decisions'][0]['response'])

    def test_missing_assistant_retains_answer_and_handoff(self):
        self.app.close()
        app = self.make(adapters_={})
        status, result = self.answer_report(app=app)
        self.assertEqual(status, 200)
        row = result['decision']
        run = app.wait(row['response']['run'], ['waiting_for_person'], timeout=4)
        self.assertEqual(run['mode'], 'handoff')
        self.assertEqual(self.get('/api/decisions', app)[1]['decisions'][0]['response']['label'], 'Keep it')

    def test_failure_retry_preserves_choice_and_single_run(self):
        os.environ['FAKE_MODE'] = 'fail'
        row = self.answer_report()[1]['decision']
        run = row['response']['run']
        self.assertEqual(self.app.wait(run, ['failed'], 5)['state'], 'failed')
        os.environ['FAKE_MODE'] = 'slow'
        os.environ['FAKE_SECONDS'] = '0.2'
        self.assertEqual(self.post(f'/api/runs/{run}/retry')[0], 200)
        self.assertEqual(self.app.wait(run, ['done'], 5)['state'], 'done')
        self.assertEqual(self.get('/api/decisions')[1]['decisions'][0]['response']['option'], 'a')
        self.assertEqual(len(self.app.store.all()), 1)
        argv = [json.loads(line) for line in (self.base / 'argv.jsonl').read_text().splitlines() if '-p' in json.loads(line)]
        self.assertTrue(all('mcp__eaos__fix_edit' not in call[call.index('--allowedTools') + 1:call.index('--disallowedTools')] for call in argv))

    def test_revision_is_independent_of_presentation_language(self):
        self.question['revision'] = 'source-question-v1'
        self.write_question()
        run = self.answer_report()[1]['decision']['response']['run']
        self.question['question'] = 'أي تصميم؟'
        self.question['options'][0]['label'] = 'احتفظ به'
        self.write_question()
        self.assertEqual(self.get('/api/decisions')[1]['decisions'][0]['response']['run'], run)


class RemoteLocks(unittest.TestCase):
    def test_exact_remote_host_with_tokens_csrf_and_origin(self):
        origin = 'https://engineering-audit-os--8095.dev.remote.e-m.sa'
        locks = security.Locks(8095, remote_origin=origin)
        headers = {'Host': origin[8:], 'Origin': origin, 'X-EAOS-Token': locks.token, 'X-EAOS-CSRF': locks.csrf}
        self.assertIsNone(locks.check('POST', '/api/decisions/d/answer', headers))
        for changed in ({'Host': 'other--8095.dev.remote.e-m.sa'}, {'Origin': 'https://evil.example'}, {'X-EAOS-CSRF': 'bad'}, {'X-EAOS-Token': 'bad'}):
            self.assertIsNotNone(locks.check('POST', '/api/decisions/d/answer', {**headers, **changed}))
        for value in ('https://*.dev.remote.e-m.sa', 'http://engineering-audit-os--8095.dev.remote.e-m.sa', 'https://evil.example'):
            with self.assertRaises(ValueError): security.Locks(8095, remote_origin=value)
