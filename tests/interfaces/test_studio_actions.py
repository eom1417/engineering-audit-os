"""The run engine (eaos/features/studio/journey/runs, wired by eaos/doors/runs.py): the contract, the event log, and the
adapters on real recorded streams."""
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from eaos.doors import runs as actions  # noqa: E402
from eaos.features.assistant.adapters import headless as adapters, prompts
from eaos.kernel.project import runs as store
from tests.interfaces._studio_actions_fixture import FAKE, FIXTURES, ROOT


class Contract(unittest.TestCase):
    def test_the_packaged_contract_is_the_documented_one_names_every_tool_and_every_endpoint_is_routed(self):
        self.assertEqual((ROOT / 'docs/studio-actions.json').read_bytes(),
                         (ROOT / 'eaos/data/studio-actions.json').read_bytes())
        from eaos.doors.mcp_server import server as mcp_server
        data = store.contract()
        names = {action['id'] for action in data['actions'] if action['tool']}
        self.assertEqual(set(mcp_server.functions()), names)
        self.assertEqual([a['id'] for a in data['actions'] if not a['tool']], [])
        self.assertLessEqual(mcp_server.reading(), names)
        for action in data['actions']:
            self.assertEqual(action['inputs']['type'], 'object', action['id'])
            self.assertTrue(action['label']['ar'] and action['label']['en'])
            self.assertEqual(action['needs_assistant'], action['mode'] == 'assistant')
        self.assertEqual({a['id'] for a in data['actions'] if a['irreversible']}, {'accept', 'undo'})
        self.assertEqual(set(data['lifecycle']['states']), {'queued', *store.ACTIVE, *store.TERMINAL})
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, {'EAOS_HOME': folder}):
            project = Path(folder) / 'p'
            project.mkdir()
            app = actions.Actions(project, port=8765, adapters={})
            try:
                for row in data['endpoints']:
                    path = row['path'].replace('<id>/answer', 'r-none-q1/answer').replace(
                        '<id>', 'r-none' if row['path'].startswith('/api/runs') else 'status')
                    headers = {'X-EAOS-Token': app.token, 'X-EAOS-CSRF': app.csrf, 'Origin': 'http://127.0.0.1:8765',
                               'Host': '127.0.0.1:8765'}
                    status, payload = app.handle(row['method'], path, headers, {})
                    if '<id>' in row['path'] and 'runs' in row['path'] or 'questions/' in path or 'decisions/' in path:
                        self.assertIn(status, (403, 404, 409),
                                      (row, payload))      # a run that does not exist, not an unknown route
                        if status == 404: self.assertIn('r-none', payload['error'], row)
                    else:
                        self.assertNotEqual(status, 404, (row, payload))
            finally:
                app.close()

    def test_every_tool_status_can_name_next_is_allowed_to_the_fix_verb(self):
        """status offers fix_abandon, so a fix run is allowed it and a stuck batch can be closed."""
        import inspect
        from eaos.features.guided.interface.agent_tools import where
        source = ''.join(inspect.getsource(f)
                         for f in (where.status, where._next_step, where._batch_step, where._setup_step))
        named = set()
        for step in re.findall(r"return \('([^']+)'", source) + re.findall(r"'next': \{'tool': '([^']+)'", source):
            named.update(word for word in re.split(r',? then | or ', step) if word != 'none')
        verbs = {verb['id']: set(verb['tools']) for verb in store.contract()['verbs']}
        self.assertIn('fix_abandon', named)
        self.assertEqual(named - set(adapters.PERSON_ONLY) - verbs['fix'], set())
        for verb in ('verify', 'explain', 'plan'):
            self.assertLessEqual({'wait', 'overview', 'findings', 'plan'}, verbs[verb], verb)


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
            words = (f'{project}/src/a.py and {Path.home()}/x with sk-ant-abcdefghijklmnopqrstuv '
                     'ghp_abcdefghijklmnopqrstuvwxyz0123 '
                     'Bearer abcdefghijklmnopqrstuvwxyz and launch-token-value')
            text = json.dumps(log.append('r1', 'say', words, {'nested': [words]}, words))
            for leaked in ('sk-ant-', 'ghp_', 'abcdefghijklmnopqrstuvwxyz', 'launch-token-value', str(project),
                           str(Path.home()) + '/x'):
                self.assertNotIn(leaked, text)
            self.assertIn('src/a.py', text)
            big = log.append('r1', 'edit', 'big', {'diff': 'x' * (store.DIFF_LIMIT + 10)})
            self.assertTrue(big['data']['cut'])
            self.assertLess(len(big['data']['diff']), store.DIFF_LIMIT + 100)
            self.assertEqual(log.verify('r1'), [])
            path = Path(folder) / 'runs/r1/events.jsonl'
            path.write_text(path.read_text().replace('step 2', 'step X'))
            self.assertTrue(log.verify('r1'), 'tampering shows')

    def test_an_ended_run_past_the_newest_ten_keeps_its_record_with_what_it_used_and_nothing_else(self):
        result = json.dumps({'type': 'result', 'usage': {'input_tokens': 7, 'output_tokens': 3}, 'total_cost_usd': 0.5})
        with tempfile.TemporaryDirectory() as folder:
            log, runs = store.Store(Path(folder) / 'runs', store.Scrubber(Path(folder), [])), Path(folder) / 'runs'
            for n in range(store.KEEP + 2):        # r00 still runs, r01 to r11 ended: r01 is past the newest ten
                log.save({'id': f'r{n:02}', 'state': 'done' if n else 'running', 'created': f'2026-10-17T00:00:{n:02}'},
                         new=True)
                (runs / f'r{n:02}/stream.jsonl').write_text(result + '\n')
                log.append(f'r{n:02}', 'step', 'one step')
            log.save({'id': 'r12', 'state': 'queued', 'created': '2026-10-17T00:00:12'}, new=True)
            self.assertEqual(sorted(p.name for p in (runs / 'r01').iterdir()), ['run.json'])
            self.assertEqual((log.load('r01')['usage']['output'], log.load('r01')['usage']['cost_usd']), (3, 0.5))
            self.assertTrue(log.load('r01')['trimmed'])
            self.assertTrue(all((runs / f'r{n:02}/stream.jsonl').is_file() for n in range(12) if n != 1),
                            'live and newest kept')
            for n in range(store.KEEP):              # quick answers (read) never push a run's details out
                log.save({'id': f'q{n:02}', 'state': 'done', 'read': True, 'created': f'2026-10-17T00:01:{n:02}'},
                         new=True)
            self.assertTrue((runs / 'r02/stream.jsonl').is_file())


class Adapters(unittest.TestCase):
    labels = {a['id']: a['label'] for a in store.contract()['actions']}

    def parse(self, adapter, name):
        state, events = adapter.new_state(), []
        for line in (FIXTURES / name).read_text(encoding='utf-8').splitlines():
            events += adapter.parse(line, state, self.labels)
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
        self.assertTrue(any(tool == 'run_setup' and isinstance(payload, dict)
                            and payload.get('status') == 'needs_agreement'
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
        events = adapters.tool_events('fix_edit', {'card': 'TASK-1', 'edits': [
            {'path': 'a.py', 'find': 'x = 1\n', 'replace': 'x = 2\n'}, {'path': 'b.py', 'content': 'new\n'},
            {'path': 'c.py', 'delete': True}]}, self.labels)
        kind, _, data, _ = events[0]
        self.assertEqual((kind, data['paths']), ('edit', ['a.py', 'b.py', 'c.py']))
        for needle in ('-x = 1', '+new', '(deleted)'): self.assertIn(needle, data['diff'])
        checks = adapters.result_events('wait', {},
                                        {'status': 'done',
                                         'result': {'kept': False, 'card': 'TASK-1', 'why': 'a test broke'}})
        self.assertEqual((checks[0][0], checks[0][2]['passed']), ('check', False))
        why = "the problem is still there: the card's own check still finds it (exit 1)"
        _, words, _, detail = adapters.result_events('wait', {},
                                                     {'status': 'done',
                                                      'result': {'kept': False, 'card': 'TASK-1', 'why': why}})[0]
        self.assertIsNone(re.search(r'[A-Za-z]{3,} [A-Za-z]{3,} [A-Za-z]{3,}', words['ar']),
                          'no English sentence inside an Arabic line')
        self.assertIn('exit 1', detail)

    def test_an_assistant_starts_with_this_eaos_only_without_the_person_only_tools_and_is_told_the_eaos_way(self):
        with tempfile.TemporaryDirectory() as folder:
            argv = adapters.ClaudeCode(command=['claude']).argv('do it', 'r1', Path(folder), session='s1')
            config = json.loads((Path(folder) / 'mcp.json').read_text())
        refused = argv[argv.index('--disallowedTools') + 1:]
        for tool in ('Bash', 'Edit', 'Write', 'mcp__eaos__accept', 'mcp__eaos__undo',
                     'mcp__eaos__choose_branch'): self.assertIn(tool, refused)
        self.assertIn('--strict-mcp-config', argv)
        # a fixing run gets no built-in tool beyond reading, so it cannot launch a subagent
        self.assertEqual(argv[argv.index('--tools') + 1], 'Read,Grep,Glob', 'no built-in tool beyond reading')
        self.assertEqual(argv[-2:], ['--resume', 's1'])
        self.assertEqual(config['mcpServers']['eaos']['env']['EAOS_STUDIO_RUN'], 'r1')
        self.assertEqual(config['mcpServers']['eaos']['args'][-1], 'mcp')
        with tempfile.TemporaryDirectory() as folder:
            argv = adapters.ClaudeCode(command=['claude']).argv('explain', 'r1', Path(folder),
                                                                tools=['status', 'finding'])
        self.assertEqual(argv[argv.index('--allowedTools') + 1:argv.index('--disallowedTools')],
                         ['mcp__eaos__status', 'mcp__eaos__finding', 'Read', 'Grep', 'Glob'])
        argv = adapters.Codex(command=['codex']).argv('go on', 'r1', Path('.'), session='t1')
        self.assertEqual((argv[:3], argv[-2:]), (['codex', 'exec', 'resume'], ['t1', 'go on']))
        self.assertIn('sandbox_mode="read-only"', argv)
        server = next(a for a in argv if a.startswith('mcp_servers.eaos='))
        self.assertIn('EAOS_STUDIO_RUN="r1"', server)
        self.assertIn('disabled_tools=["accept", "undo", "choose_branch"]', server)
        limited = next(a for a in adapters.Codex(command=['codex']).argv('x', 'r1', Path('.'), tools=['status'])
                       if a.startswith('mcp_servers.eaos='))
        self.assertIn('enabled_tools=["status"]', limited)
        self.assertNotIn('disabled_tools', limited)
        with mock.patch('shutil.which', return_value='/usr/local/bin/eaos'):
            argv, env = adapters.eaos_server('r1', 'Codex')
        self.assertEqual(argv, [sys.executable, '-m', 'eaos', 'mcp'], 'never another eaos on the path')
        self.assertEqual(Path(env['PYTHONPATH']), ROOT)
        self.assertEqual((env['EAOS_STUDIO_RUN'], env['EAOS_ASSISTANT']), ('r1', 'Codex'))
        with mock.patch.dict(os.environ, {'EAOS_HEADLESS': '1'}):
            self.assertEqual(adapters.eaos_server('r1', 'Codex')[1].get('EAOS_HEADLESS'), '1',
                             "a headless host's run opens no Studio")
        text = prompts.build('fix', [{'id': 'TASK-1', 'title': 'T', 'paths': ['a.py']}], Path('/p/shop'), 'ar')
        for needle in ('fix_start', 'fix_edit', 'fix_finish', 'TASK-1', 'eaos-question',
                       'Do not call accept, undo or choose_branch', 'Arabic'):
            self.assertIn(needle, text)
        self.assertNotIn('/p/shop', text)
        found = prompts.question_in('Words.\n```eaos-question\n{"text": "Which?", "options": ["A", '
                                    '{"id": "b", "label": "B"}], "recommendation": "b"}\n```')
        self.assertEqual((found['text'], [o['id'] for o in found['options']], found['recommendation']),
                         ({'en': 'Which?', 'ar': 'Which?'}, ['o1', 'b'], 'b'))
        self.assertIsNone(prompts.question_in('```eaos-question\n{not json}\n```'))
        self.assertIsNone(prompts.question_in('no block'))
        self.assertIsNone(prompts.question_in('```eaos-question\n{"text": "x", "options": [], '
                                              '"recommendation": "zz"}\n```')['recommendation'])

    def test_detection_says_installed_and_logged_in_and_a_probe_that_times_out_keeps_the_last(self):
        with mock.patch.dict(os.environ, {'FAKE_LOGGED_IN': '0'}):
            found = adapters.ClaudeCode(command=[sys.executable, str(FAKE)]).detect(fresh=True)
        self.assertEqual((found['installed'], found['logged_in']), (True, False))
        self.assertFalse(adapters.ClaudeCode(command=['/nonexistent/claude']).detect()['installed'])
        ready = adapters.ClaudeCode(command=[sys.executable, str(FAKE)])
        self.assertTrue(ready.available())
        self.assertTrue(ready.detect(fresh=True)['logged_in'])
        with mock.patch.object(adapters.ClaudeCode, '_run', return_value=None):
            self.assertEqual((ready.detect(fresh=True)['installed'], ready.detect(fresh=True)['logged_in']),
                             (True, True))
            self.assertFalse(adapters.ClaudeCode(command=[sys.executable, str(FAKE)]).detect(fresh=True)['installed'])


if __name__ == '__main__':
    unittest.main()
