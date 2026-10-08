"""NS46 — Studio first (docs/STUDIO.md D7): the acceptance of each task of the phase, one class per task.

Written by the planner with the plan (2026-10-08, docs/north-star.json NS46), before the pages; most fail today.
Run one task's class: python tools/acceptance.py test ns46_studio.<Class>.

Interface the phase must provide:
    schemas/artifacts/studio-<section>.schema.json   for functions, screens, gaps, operations, history, quality and
                                                     coverage: "x-revision": 2, "contract" const 1, "revision" const 2,
                                                     a byte-identical packaged copy, and listed in the manifest's x-sections
    tests/fixtures/studio/v2/<section>.json          a small fixture per v2 section, valid
    tools/studio_synthetic.py build(cards, components) -> {section: data}; write(folder, sections) -> [problems]
    <report>/studio/coverage.json                    in every corpus report, valid
    docs/studio-routes.json                          the routes, each with the task that builds it (`task`)
    tools/north_star_studio.py route_status(reports, routes) -> {route id: (ok, why)}
    $EAOS_MEASURE/studio-gates/budgets.json          {"studio_source_sha256", "filter_5000_ms", "home_interactive_ms"}
    docs/STUDIO-REVIEW.md                            the self-review: every project of docs/studio-routes.json, and a line
                                                     "Owner verdict (YYYY-MM-DD): ..." the owner gave

The command centre (docs/STUDIO.md D8, docs/studio-actions.json; written by the planner 2026-10-08 with NS46.T9-T11):
    eaos/data/studio-actions.json                    byte-identical to docs/studio-actions.json
    eaos.studio.actions.contract() -> dict           the packaged contract
    eaos.studio.actions.Actions(project, home=None, port=8765, adapters=None, studio=None)
        .token, .csrf                                the launch token and the CSRF token
        .handle(method, path, headers, body) -> (status, dict)   every endpoint of the contract but the SSE stream
        .sse(run, last_event_id=None, follow=False) -> iterator of SSE frames ("id: N\ndata: {...}\n\n")
        .wait(run, states, timeout) -> the run dict once its state is in `states`
    eaos.studio.actions.adapters.ClaudeCode(command=[...])   the Claude Code adapter; `command` replaces `claude`
    eaos.studio.actions.handoff.pending(project) -> [requests]   what the next `status` call picks up
    A question reaches the run when the assistant ends its turn with a fenced block ```eaos-question {json}```.
    tools/studio_trial.py -> $EAOS_MEASURE/studio/<project>/trial.json: {project, assistant, audited, selection{kind,
        cards}, cards_fixed, questions_answered_in_inbox, accepted, typed_to_assistant, time_to_first_action_s,
        steps_per_task, failures[], understood{state: bool}, screenshots[], video}
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

from eaos import artifact_contracts

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
V2 = ('functions', 'screens', 'gaps', 'operations', 'history', 'quality', 'coverage')


def reports():
    import dev_paths
    return dev_paths.MEASURE


def routes_of(task):
    import north_star_studio
    routes = [route for route in north_star_studio.registry()['routes'] if route['task'] == task]
    return routes, north_star_studio.route_status(reports(), routes)


class RoutesOfTask:
    task = None

    def test_every_route_of_the_task_is_shown_and_passes_its_gates(self):
        routes, status = routes_of(self.task)
        self.assertTrue(routes, f'docs/studio-routes.json names no route for {self.task}')
        failing = {name: why for name, (ok, why) in status.items() if not ok}
        self.assertEqual(failing, {}, f'{self.task}: routes not shown with real data or a coverage state')


class ContractV2(unittest.TestCase):
    def test_every_v2_section_has_its_schema_and_packaged_copy(self):
        manifest = json.loads((ROOT / 'schemas/artifacts/studio-manifest.schema.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['properties']['contract'], {'const': 1})
        for name in V2:
            self.assertIn(name, manifest['x-sections'])
            source = (ROOT / f'schemas/artifacts/studio-{name}.schema.json').read_bytes()
            self.assertEqual(source, (ROOT / f'eaos/data/schemas/artifacts/studio-{name}.schema.json').read_bytes(), name)
            schema = json.loads(source)
            self.assertEqual((schema['x-revision'], schema['properties']['contract'], schema['properties']['revision']),
                             (2, {'const': 1}, {'const': 2}), name)

    def test_every_v2_section_has_a_valid_small_fixture(self):
        contracts = artifact_contracts.contracts()
        for name in V2:
            data = json.loads((ROOT / f'tests/fixtures/studio/v2/{name}.json').read_text(encoding='utf-8'))
            self.assertEqual(artifact_contracts.validate(data, contracts[f'studio-{name}']), [], name)

    def test_the_synthetic_project_holds_5000_cards_and_1000_components(self):
        import studio_synthetic
        sections = studio_synthetic.build(cards=5000, components=1000)
        self.assertEqual(len(sections['cards']['cards']), 5000)
        self.assertEqual(len(sections['story']['current']['components']), 1000)
        self.assertTrue(set(V2) <= set(sections))
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(studio_synthetic.write(folder, sections), [])

    def test_every_corpus_report_says_what_it_has_not_measured(self):
        contracts = artifact_contracts.contracts()
        record = json.loads((ROOT / 'docs/north-star.json').read_text(encoding='utf-8'))
        for spec in record['corpus']:
            path = reports() / spec['name'] / 'studio/coverage.json'
            self.assertTrue(path.is_file(), f'{spec["name"]}: no studio/coverage.json')
            data = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(artifact_contracts.validate(data, contracts['studio-coverage']), [], spec['name'])
            for row in data['sections']:
                if row['state'] in ('not_measured', 'failed'): self.assertTrue(row['step'] and row['detail'], row['section'])


class Problems(RoutesOfTask, unittest.TestCase):
    task = 'NS46.T2'

    def test_5000_cards_filter_within_100_ms_on_the_shipped_build(self):
        import north_star_studio
        budgets = json.loads((reports() / 'studio-gates/budgets.json').read_text(encoding='utf-8'))
        self.assertEqual(budgets.get('studio_source_sha256'), north_star_studio.shipped())
        self.assertLessEqual(budgets['filter_5000_ms'], 100)


class Change(RoutesOfTask, unittest.TestCase):
    task = 'NS46.T3'


class LibraryHistoryQuality(RoutesOfTask, unittest.TestCase):
    task = 'NS46.T4'


class FunctionsScreens(RoutesOfTask, unittest.TestCase):
    task = 'NS46.T5'


class Maps(RoutesOfTask, unittest.TestCase):
    task = 'NS46.T6'


class SelfReview(unittest.TestCase):
    def test_the_review_covers_every_project_and_records_the_owner_verdict(self):
        import north_star_studio
        text = (ROOT / 'docs/STUDIO-REVIEW.md').read_text(encoding='utf-8')
        for project in north_star_studio.registry()['projects']:
            self.assertIn(project['name'].split(' (')[0], text)
        self.assertRegex(text, re.compile(r'(?m)^Owner verdict \(\d{4}-\d{2}-\d{2}\): \S'))


FAKE_CLAUDE = r'''import json, sys
argv = sys.argv[1:]
resumed = '--resume' in argv
def say(event): print(json.dumps(event), flush=True)
say({'type': 'system', 'subtype': 'init', 'session_id': 'fake-session', 'tools': ['mcp__eaos__status']})
if not resumed:
    say({'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 't1', 'name': 'mcp__eaos__finding', 'input': {'id': 'TASK-001'}}]}})
    say({'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 't1', 'content': [{'type': 'text', 'text': '{"id": "TASK-001"}'}]}]}})
    text = 'I need your choice.\n```eaos-question\n{"text": {"en": "Run the app?", "ar": "أشغّل التطبيق؟"}, "options": [{"id": "yes", "label": {"en": "Yes", "ar": "نعم"}}, {"id": "no", "label": {"en": "No", "ar": "لا"}}], "recommendation": "yes"}\n```'
    say({'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': text}]}})
    say({'type': 'result', 'subtype': 'success', 'is_error': False, 'result': text, 'session_id': 'fake-session'})
else:
    say({'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 't2', 'name': 'mcp__eaos__fix_read', 'input': {'path': 'src/a.py'}}]}})
    say({'type': 'result', 'subtype': 'success', 'is_error': False, 'result': 'Done: the card is explained.', 'session_id': 'fake-session'})
'''


class CommandCentreActions(unittest.TestCase):
    """NS46.T9: the action API and the assistant launcher, through the interface above, with a fake Claude Code."""

    def setUp(self):
        import os
        import subprocess
        self.folder = tempfile.TemporaryDirectory()
        base = Path(self.folder.name)
        self.addCleanup(self.folder.cleanup)
        self.env = {key: os.environ.get(key) for key in ('EAOS_HOME', 'EAOS_OUTPUT')}
        os.environ['EAOS_HOME'], os.environ['EAOS_OUTPUT'] = str(base / 'home'), str(base / 'out')
        self.addCleanup(lambda: [os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v) for k, v in self.env.items()])
        self.project = base / 'project'
        (self.project / 'src').mkdir(parents=True)
        (self.project / 'src/a.py').write_text('x = 1\n', encoding='utf-8')
        subprocess.run(['git', 'init', '-q', str(self.project)], check=True)
        self.studio = base / 'studio'
        self.studio.mkdir()
        card = {'id': 'TASK-001', 'key': 'k1', 'title': 'A problem', 'kind': 'duplication', 'category': 'structure', 'severity': 'high',
                'fixable': True, 'scope': 'place', 'place': 'src/a.py', 'paths': ['src/a.py'], 'evidence': [], 'state': 'open', 'milestone': 'M1'}
        (self.studio / 'cards.json').write_text(json.dumps({'schema_version': 1, 'contract': 1, 'cards': [card]}), encoding='utf-8')
        fake = base / 'fake_claude.py'
        fake.write_text(FAKE_CLAUDE, encoding='utf-8')
        from eaos.studio import actions
        from eaos.studio.actions import adapters
        self.actions = actions
        self.app = actions.Actions(self.project, port=8765, adapters={'claude': adapters.ClaudeCode(command=[sys.executable, str(fake)])},
                                   studio=self.studio)

    def headers(self, **extra):
        return {'X-EAOS-Token': self.app.token, 'X-EAOS-CSRF': self.app.csrf, 'Origin': 'http://127.0.0.1:8765',
                'Host': '127.0.0.1:8765', **extra}

    def test_the_contract_names_every_mcp_tool_and_is_packaged(self):
        from eaos import mcp_server
        contract = self.actions.contract()
        self.assertEqual((ROOT / 'docs/studio-actions.json').read_bytes(), (ROOT / 'eaos/data/studio-actions.json').read_bytes())
        server = mcp_server.build()
        tools = {tool.name for tool in server._tool_manager.list_tools()} if hasattr(server, '_tool_manager') else set()
        if not tools:
            import asyncio
            tools = {tool.name for tool in asyncio.run(server.list_tools())}
        actions = {action['id']: action for action in contract['actions']}
        self.assertEqual(tools - set(actions), set())
        for action in actions.values():
            self.assertTrue(action['label']['en'] and action['label']['ar'] and isinstance(action['inputs'], dict), action['id'])
            self.assertIsInstance(action['needs_assistant'], bool)
        self.assertTrue(actions['accept']['irreversible'] and actions['undo']['irreversible'])
        self.assertEqual({verb['id'] for verb in contract['verbs']}, {'fix', 'verify', 'explain', 'plan'})
        self.assertEqual(set(contract['lifecycle']['states']), {'queued', 'running', 'paused', 'waiting_for_person', 'done', 'failed', 'stopped'})
        kinds = set(contract['events']['envelope']['properties']['kind']['enum'])
        self.assertLessEqual({'step', 'read', 'edit', 'check', 'screenshot', 'progress', 'question', 'answer', 'result', 'error'}, kinds)
        paths = {(row['method'], row['path']) for row in contract['endpoints']}
        for row in [('POST', '/api/actions/<id>/preview'), ('POST', '/api/runs'), ('GET', '/api/runs'), ('GET', '/api/runs/<id>'),
                    ('GET', '/api/runs/<id>/events'), ('POST', '/api/runs/<id>/pause'), ('POST', '/api/runs/<id>/resume'),
                    ('POST', '/api/runs/<id>/stop'), ('POST', '/api/runs/<id>/retry'), ('POST', '/api/runs/reorder'),
                    ('POST', '/api/questions/<id>/answer'), ('POST', '/api/runs/<id>/accept'), ('POST', '/api/runs/<id>/undo')]:
            self.assertIn(row, paths)

    def test_a_call_without_the_token_csrf_or_local_origin_is_refused(self):
        body = {'action': 'status'}
        for headers in ({}, self.headers(**{'X-EAOS-Token': 'wrong'}), self.headers(**{'X-EAOS-CSRF': 'wrong'}),
                        self.headers(Origin='http://evil.example'), self.headers(Host='evil.example:8765')):
            status, _ = self.app.handle('POST', '/api/runs', headers, body)
            self.assertIn(status, (401, 403), headers)
        self.assertEqual(self.app.runs_count() if hasattr(self.app, 'runs_count') else len(self.app.handle('GET', '/api/runs', self.headers(), None)[1]['runs']), 0)

    def test_a_run_streams_events_asks_the_person_resumes_and_needs_confirm_to_accept(self):
        status, preview = self.app.handle('POST', '/api/actions/explain/preview', self.headers(),
                                          {'verb': 'explain', 'selection': {'kind': 'cards', 'cards': ['TASK-001']}, 'assistant': 'claude'})
        self.assertEqual(status, 200, preview)
        self.assertEqual([card['id'] for card in preview['cards']], ['TASK-001'])
        status, created = self.app.handle('POST', '/api/runs', self.headers(),
                                          {'action': 'explain', 'verb': 'explain', 'selection': {'kind': 'cards', 'cards': ['TASK-001']},
                                           'assistant': 'claude', 'confirm': (preview.get('confirm') or {}).get('token')})
        self.assertEqual(status, 200, created)
        run = created['run']['id']
        waiting = self.app.wait(run, ('waiting_for_person', 'failed', 'done'), 60)
        self.assertEqual(waiting['state'], 'waiting_for_person', waiting)
        status, inbox = self.app.handle('GET', '/api/questions', self.headers(), None)
        question = inbox['questions'][0]
        self.assertEqual(question['recommendation'], 'yes')
        status, _ = self.app.handle('POST', f"/api/questions/{question['id']}/answer", self.headers(), {'option': 'yes'})
        self.assertEqual(status, 200)
        finished = self.app.wait(run, ('done', 'failed', 'stopped'), 60)
        self.assertEqual(finished['state'], 'done', finished)
        frames = list(self.app.sse(run))
        seqs = [int(re.search(r'^id: (\d+)$', frame, re.M).group(1)) for frame in frames if frame.startswith('id:')]
        self.assertEqual(seqs, list(range(1, len(seqs) + 1)))
        kinds = [json.loads(re.search(r'^data: (.*)$', frame, re.M).group(1))['kind'] for frame in frames if frame.startswith('id:')]
        for kind in ('action', 'step', 'question', 'answer', 'result'): self.assertIn(kind, kinds)
        later = list(self.app.sse(run, last_event_id=seqs[-2]))
        self.assertEqual(len([f for f in later if f.startswith('id:')]), 1)
        status, refused = self.app.handle('POST', f'/api/runs/{run}/accept', self.headers(), {})
        self.assertIn(status, (400, 403), refused)

    def test_stop_retry_and_the_queue_survive_a_restart(self):
        body = {'action': 'explain', 'verb': 'explain', 'selection': {'kind': 'card', 'cards': ['TASK-001']}, 'assistant': 'claude'}
        first = self.app.handle('POST', '/api/runs', self.headers(), body)[1]['run']['id']
        self.app.wait(first, ('waiting_for_person',), 60)
        second = self.app.handle('POST', '/api/runs', self.headers(), body)[1]['run']['id']
        self.assertEqual(self.app.handle('GET', f'/api/runs/{second}', self.headers(), None)[1]['run']['state'], 'queued')
        from eaos.studio.actions import adapters
        again = self.actions.Actions(self.project, port=8765, adapters={'claude': adapters.ClaudeCode(command=['false'])}, studio=self.studio)
        runs = {run['id']: run for run in again.handle('GET', '/api/runs', {'X-EAOS-Token': again.token, 'Host': '127.0.0.1:8765'}, None)[1]['runs']}
        self.assertEqual((runs[first]['state'], runs[second]['state']), ('waiting_for_person', 'queued'))
        headers = {'X-EAOS-Token': again.token, 'X-EAOS-CSRF': again.csrf, 'Origin': 'http://127.0.0.1:8765', 'Host': '127.0.0.1:8765'}
        self.assertEqual(again.handle('POST', f'/api/runs/{first}/stop', headers, {})[0], 200)
        self.assertEqual(again.wait(first, ('stopped',), 30)['state'], 'stopped')
        self.assertEqual(again.handle('POST', f'/api/runs/{first}/retry', headers, {})[0], 200)

    def test_with_no_assistant_the_request_is_handed_to_the_next_status_call(self):
        from eaos.studio.actions import handoff
        app = self.actions.Actions(self.project, port=8765, adapters={}, studio=self.studio)
        headers = {'X-EAOS-Token': app.token, 'X-EAOS-CSRF': app.csrf, 'Origin': 'http://127.0.0.1:8765', 'Host': '127.0.0.1:8765'}
        status, preview = app.handle('POST', '/api/actions/fix/preview', headers, {'verb': 'fix', 'selection': {'kind': 'card', 'cards': ['TASK-001']}})
        self.assertEqual(status, 200)
        self.assertTrue(preview['handoff']['available'] and preview['handoff']['request']['ar'])
        status, created = app.handle('POST', '/api/runs', headers, {'action': 'fix', 'verb': 'fix', 'selection': {'kind': 'card', 'cards': ['TASK-001']},
                                                                   'confirm': (preview.get('confirm') or {}).get('token')})
        self.assertEqual(status, 200, created)
        self.assertEqual(app.wait(created['run']['id'], ('waiting_for_person',), 30)['state'], 'waiting_for_person')
        self.assertTrue(handoff.pending(self.project))


class CommandCentrePages(RoutesOfTask, unittest.TestCase):
    task = 'NS46.T10'

    def test_the_studio_runs_actions_through_the_contract(self):
        source = '\n'.join(path.read_text(encoding='utf-8') for path in (ROOT / 'studio/src').rglob('*.ts*'))
        for needle in ('/api/runs', '/preview', '/api/questions', 'Last-Event-ID', 'eaos studio'):
            self.assertIn(needle, source)


class CommandCentreTrial(unittest.TestCase):
    """NS46.T11: the real trial from the Studio on the owner's FleetManageWeb (tools/studio_trial.py)."""

    def test_fleetmanageweb_was_run_end_to_end_from_the_studio_by_a_real_assistant(self):
        trials = sorted((reports() / 'studio').glob('FleetManageWeb*/trial.json'))
        self.assertTrue(trials, 'no tools/studio_trial.py run on FleetManageWeb')
        trial = json.loads(trials[-1].read_text(encoding='utf-8'))
        self.assertIn(trial['assistant'], ('Claude Code', 'Codex'))
        self.assertTrue(trial['audited'])
        self.assertIn(trial['selection']['kind'], ('group', 'cards', 'step'))
        self.assertGreaterEqual(len(trial['selection']['cards']), 2)
        self.assertGreaterEqual(len(trial['cards_fixed']), 1)
        self.assertGreaterEqual(trial['questions_answered_in_inbox'], 1)
        self.assertTrue(trial['accepted'])
        self.assertEqual(trial['typed_to_assistant'], 0)
        self.assertIsInstance(trial['failures'], list)
        self.assertTrue(trial['understood'] and all(trial['understood'].values()), trial['understood'])
        self.assertIsInstance(trial['time_to_first_action_s'], (int, float))
        self.assertIsInstance(trial['steps_per_task'], (int, float))
        self.assertTrue(trial['screenshots'] and all(Path(p).is_file() for p in trial['screenshots']))
        self.assertTrue(Path(trial['video']).is_file())


if __name__ == '__main__':
    unittest.main()
