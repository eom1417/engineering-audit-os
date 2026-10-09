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

The pipeline map (docs/STUDIO.md D9; written by the planner 2026-10-08 with NS46.T12-T13):
    eaos.facts.pipeline.scan(project) -> record      {detected, confidence, kinds, evidence, looked_for, pipelines, stages,
                                                     edges, routers, fans, control, error_lanes, hidden, unresolved}; every
                                                     stage, edge and branch with its evidence {path, line} in the project
    eaos.facts.pipeline.write(report, record)        facts/pipeline.json of a report, as the facts stage writes it
    eaos.studio.pipeline.section(record, cards=(), plan=None, lang='en') -> the body of studio/pipeline.json
    evaluations/pipelines/<name>.json                hand-written truth files: {name, kind, source, commit, pipelines:
                                                     [{anchor, stages, edges, routers: [{table, branches}]}]}; source null
                                                     is this repository; apps.json lists what each app project holds
    tools/pipeline_truth.py checkout(truth) -> Path | None, compare(truth, record) -> {stages|edges|branches: {recall,
                                                     precision}}, verify(project, record) -> [problems], apps() -> [(name, path)]
    human/index.html                                 a section id="pipeline-sheet" when facts/pipeline.json holds a pipeline
The planned ideal (docs/STUDIO.md D10; written by the planner 2026-10-08 with NS46.T14):
    eaos.studio.ideal.VIEWS                          system, change, journeys, paths, data_paths, infra, pipeline, plan_order
    eaos.studio.ideal.known_ids(report, project=None) -> set   every id a citation may resolve to: the report's facts
                                                     (FACT-...), claims (CLM-...), cards (TASK-...) and the rules the
                                                     baseline applied (RULE-<family>-<name>, e.g. RULE-disposition-modify)
    eaos.studio.ideal.check(ideal, known) -> (kept, dropped)   the evidence check: an element none of whose `cites`
                                                     resolves is dropped ([{view, id, why}]); unresolved cites are removed
    eaos.studio.ideal.plan(report, launcher=None, project=None, lang='en', adapters=None) -> {'state', 'message', ...}
        the planning pass, the critique pass and the evidence check, kept in <report>/ideal/plan.json. `launcher(pass,
        prompt, schema) -> dict` asks the assistant (pass 'plan' -> an ideal; pass 'critique' -> {critique, ideal});
        `launcher.assistant` and `launcher.model` name it, read after each call. Without a launcher, the first available
        adapter of `adapters` (eaos.studio.actions.adapters.installed() by default) runs headless; with none, nothing
        is planned. A failure or timeout leaves the rules' target in place.
        An ideal: {views: {<view>: {summary, confidence, elements: [{id, kind, title, operation, subject, detail,
        cites: [ids]}]}}, departures: [{view, element, rule_says, plan_chose, because, cites}],
        open_questions: [{id, view, question, options, recommendation, why}], confidence}
    eaos.studio.ideal.section(report, lang) -> dict  the body of studio/ideal.json (contract studio-ideal): state
                                                     (planned, not_planned, stale, failed), message, views{<view>:
                                                     {provenance, rules, planned}}, evidence, questions
    eaos.studio.ideal.decisions(report, lang) -> [rows of studio/decisions.json]   the open questions, for the inbox
    $EAOS_MEASURE/ideal/FleetManageWeb/run.json      a real run: {project, assistant, model, at, real, passes,
                                                     share_with_evidence, elements, dropped, departures, open_questions}

AI nodes in the EAOS pipeline (docs/STUDIO.md D11; written by the planner 2026-10-08 with NS46.T15):
    eaos.studio.nodes.NODES                          the AI nodes, in order, as declared data: Node(name, title, kind='ai',
                                                     passes, requires, consumes, produces, routes, budget); `routes` is a
                                                     tuple of Route(decision, to, when): `to` is another node or one of
                                                     eaos.studio.nodes.SINKS; each node has exactly one 'rules only' route
    eaos.studio.nodes.Budget(seconds, usd)           the time and cost budget of one node's run
    eaos.studio.nodes.run(report, names=None, launcher=None, adapters=None, project=None, lang='en', budget=None,
                          fresh=False, **inputs) -> {name: record}
        runs the named nodes (all by default) whose inputs exist; `launcher(pass, prompt, schema) -> dict` is the
        assistant (its optional `cost_usd` read after each call); without one, the first available adapter of
        `adapters`; with none, every node takes its rules-only route. `inputs`: wave=<folder of a fix batch>.
        A schema asks for {summary, decisions: [decision]}; a decision's `subject` is held to an enum of the subjects.
    record (contract ai-node)                        {node, state: decided|rules_only|failed, method: model|rules, assistant,
                                                     model, at, inputs (digest), prompt (digest), cached, seconds, cost_usd,
                                                     budget, why, decisions, dropped, routes: [{decision, to, when,
                                                     subjects}]}
    eaos.studio.nodes.core.DECISION                  the shared decision: {subject, decision, options, evidence (ids, at
                                                     least one), confidence, why, open_questions, source: model|rules}
    eaos.studio.nodes.core.log(report) -> [entries]  the run log: {node, at, prompt, model, inputs, output, cached, ...}
    evaluations/pipelines/eaos.json                  a pipeline anchored at eaos/studio/nodes/__init__.py with
                                                     `ai_stages` and one router per node (table = the node's name)
    $EAOS_MEASURE/nodes/FleetManageWeb/card_triage.json   a real triage run: {project, assistant, model, at, real,
                                                     decisions, share_with_evidence, routes{decision: count}}
Re-planning every target already built (docs/STUDIO.md D10; written by the planner 2026-10-09 with NS46.T16):
    $EAOS_MEASURE/replan/<project>/run.json          for FleetManageWeb, chief-ops, finance-os-a0192b7b and EAOS: a real
                                                     planning run (tools/replan_trial.py) on a fresh check: the fields of
                                                     the ideal run, with views{<view>: {method, rules, planned, summary,
                                                     why_empty, differences{same, changed, added, rules_only}}} and
                                                     differences [{view, element, kind, subject, rules, planned}]
    docs/roadmap-proposals.json                      the planning and critique pass over EAOS's own roadmap
                                                     (tools/roadmap_review.py): {run{assistant, model, at, real, passes,
                                                     share_with_evidence}, proposals [{id, kind, title, detail, cites,
                                                     recommendation, decision{state, options, owner_verdict}, applied}],
                                                     dropped}; every cite is an id of docs/north-star.json
    docs/roadmap-proposals.md                        the same for people, every proposal id in it
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


RECALL, PRECISION = 0.8, 0.9


def pipeline_truth():
    import pipeline_truth as truth
    return truth


class PipelineEngine(unittest.TestCase):
    """NS46.T12: the engine finds the pipelines as the hand-written truth files say, and invents none."""

    def judge(self, name, scores):
        for part in ('stages', 'edges', 'branches'):
            self.assertGreaterEqual(scores[part]['recall'], RECALL, f'{name}: {part} recall {scores[part]}')
            self.assertGreaterEqual(scores[part]['precision'], PRECISION, f'{name}: {part} precision {scores[part]}')

    def test_eaos_itself_matches_its_hand_written_truth(self):
        from eaos.facts import pipeline
        truth = pipeline_truth()
        record = pipeline.scan(ROOT)
        self.assertTrue(record['detected'])
        self.judge('eaos', truth.compare(truth.load('eaos'), record))
        self.assertEqual(truth.verify(ROOT, record), [])

    def test_two_public_pipelines_of_different_kinds_match_their_truth(self):
        from eaos.facts import pipeline
        truth = pipeline_truth()
        public = [truth.load(path.stem) for path in sorted((ROOT / 'evaluations/pipelines').glob('*.json'))
                  if path.stem not in ('eaos', 'apps')]
        self.assertGreaterEqual(len({t['kind'] for t in public}), 2, 'two public pipelines of different kinds')
        for spec in public:
            self.assertTrue(spec['source'] and spec['commit'], spec['name'])
            where = truth.checkout(spec)
            self.assertIsNotNone(where, f"{spec['name']}: not cloned at {spec['commit']} (python tools/pipeline_truth.py fetch)")
            record = pipeline.scan(where)
            self.judge(spec['name'], truth.compare(spec, record))
            self.assertEqual(truth.verify(where, record), [], spec['name'])

    def test_no_pipeline_is_invented_on_the_app_projects(self):
        from eaos.facts import pipeline
        truth = pipeline_truth()
        expected = truth.load('apps')['projects']
        apps = truth.apps()
        self.assertGreaterEqual(len(apps), 4)
        for name, where in apps:
            record = pipeline.scan(where)
            found = sorted(p['title'] for p in record['pipelines'] if p['role'] == 'product')
            self.assertEqual(found, sorted(expected.get(name, {}).get('product', [])), f'{name}: a product pipeline not in the truth')
            self.assertEqual(truth.verify(where, record), [], name)

    def test_the_section_meets_its_contract_with_its_fixture(self):
        from eaos.facts import pipeline
        from eaos.studio import pipeline as section
        contracts = artifact_contracts.contracts()
        manifest = json.loads((ROOT / 'schemas/artifacts/studio-manifest.schema.json').read_text(encoding='utf-8'))
        self.assertIn('pipeline', manifest['x-sections'])
        source = (ROOT / 'schemas/artifacts/studio-pipeline.schema.json').read_bytes()
        self.assertEqual(source, (ROOT / 'eaos/data/schemas/artifacts/studio-pipeline.schema.json').read_bytes())
        fixture = json.loads((ROOT / 'tests/fixtures/studio/v2/pipeline.json').read_text(encoding='utf-8'))
        self.assertEqual(artifact_contracts.validate(fixture, contracts['studio-pipeline']), [])
        self.assertTrue(fixture['detected'] and fixture['routers'] and fixture['views']['gap'])
        body = {'schema_version': 1, 'contract': 1, 'revision': 2, **section.section(pipeline.scan(ROOT))}
        self.assertEqual(artifact_contracts.validate(body, contracts['studio-pipeline']), [])
        self.assertEqual({r['id'] for r in body['rules']} >= {f'P{n}' for n in range(1, 10)}, True)
        for entry in body['views']['gap']:
            self.assertTrue(entry['evidence']['path'], entry['id'])

    def test_a_1000_stage_synthetic_pipeline_builds_within_its_budget(self):
        import time
        from eaos.facts import pipeline
        from eaos.studio import pipeline as section
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            body = ['def stage_%d(value):\n    return value + %d\n' % (n, n) for n in range(1000)]
            calls = ['    v0 = stage_0(seed)'] + ['    v%d = stage_%d(v%d)' % (n, n, n - 1) for n in range(1, 1000)]
            (project / 'flow.py').write_text('\n'.join(body) + '\n\ndef run_pipeline(seed):\n' + '\n'.join(calls) + '\n    return v999\n',
                                             encoding='utf-8')
            began = time.monotonic()
            record = pipeline.scan(project)
            data = {'schema_version': 1, 'contract': 1, 'revision': 2, **section.section(record)}
            spent = time.monotonic() - began
        self.assertGreaterEqual(len(data['stages']), 1000)
        self.assertGreaterEqual(len(data['edges']), 999)
        self.assertEqual(artifact_contracts.validate(data, artifact_contracts.contracts()['studio-pipeline']), [])
        self.assertLess(spent, 20.0, f'{spent:.1f} s for 1,000 stages')


class PipelinePage(RoutesOfTask, unittest.TestCase):
    """NS46.T13: System -> Pipeline in the Studio, and the pipeline sheet in the report."""
    task = 'NS46.T13'

    def test_the_report_has_the_pipeline_sheet(self):
        sys.path.insert(0, str(ROOT))
        from eaos import human_report
        from eaos.facts import pipeline
        from tests.test_human_report import report
        with tempfile.TemporaryDirectory() as folder:
            out = report(Path(folder))
            pipeline.write(out, pipeline.scan(ROOT))
            page = Path(human_report.write(out, 'en', 'eaos')).read_text(encoding='utf-8')
        self.assertIn('id="pipeline-sheet"', page)
        for stage in ('facts', 'claims', 'compose'):
            self.assertIn(stage, page)


def _ideal_report(base):
    """The smallest report the planner reads: the rules' target, one fact, one card, a plan."""
    report = base / 'report'
    (report / 'facts').mkdir(parents=True)
    (report / 'studio').mkdir()
    (report / 'target-architecture.json').write_text(json.dumps({
        'reference': 'react-vite-spa-rest', 'gap_matrix': [], 'decisions': [], 'target_edges': [],
        'current_components': [{'id': 'T-src', 'name': 'src', 'relation': 'modify', 'reason': 'Everything else.', 'files': 2,
                                'paths': ['src/a.ts', 'src/b.ts']}],
        'target_components': [{'name': 'api-client', 'layer': 'api-client', 'responsibility': 'The only code that knows endpoints',
                               'files': 1, 'paths': ['src/a.ts']}],
        'infrastructure': [{'area': 'ci', 'present': False, 'decision': 'Introduce CI', 'tool': 'GitHub Actions', 'evidence': 'no workflow'}]}),
        encoding='utf-8')
    (report / 'facts/graph.json').write_text(json.dumps({'facts': [{'id': 'FACT-0001', 'kind': 'graph_node', 'location': {'path': 'src/a.ts'},
                                                                    'value': {'fan_in': 1, 'fan_out': 0, 'depends_on': []}}]}), encoding='utf-8')
    (report / 'studio/cards.json').write_text(json.dumps({'cards': [{'id': 'TASK-001', 'title': 'Two writers of one table', 'severity': 'high',
                                                                     'kind': 'ownership', 'paths': ['src/a.ts'], 'state': 'open'}]}), encoding='utf-8')
    (report / 'plan.json').write_text(json.dumps({'milestones': [{'id': 'M1', 'goal': 'Stabilise', 'tasks': ['TASK-001']}]}), encoding='utf-8')
    return report


def _ideal(extra=()):
    element = lambda i, cites, op='refactor': {'id': i, 'kind': 'component', 'title': f'Element {i}', 'operation': op,
                                               'subject': 'T-src', 'detail': 'why', 'cites': list(cites)}
    views = {'system': {'summary': 'One client for the backend.', 'confidence': 0.7,
                        'elements': [element('s1', ['FACT-0001', 'RULE-disposition-modify']), element('s2', ['FACT-nope', 'TASK-001']), *extra]},
             'plan_order': {'summary': 'Client first.', 'confidence': 0.6,
                            'elements': [{'id': 'p1', 'kind': 'step', 'title': 'Make the client', 'operation': 'new', 'subject': 'M1',
                                          'detail': 'first', 'cites': ['TASK-001']}]}}
    return {'views': views, 'confidence': 0.65,
            'departures': [{'view': 'system', 'element': 's1', 'rule_says': 'modify src', 'plan_chose': 'split src',
                            'because': 'two writers of one table', 'cites': ['TASK-001']}],
            'open_questions': [{'id': 'q1', 'view': 'system', 'question': 'Keep the old client during the move?',
                                'options': ['yes', 'no'], 'recommendation': 'yes', 'why': 'nothing in the facts decides it'}]}


class _Launcher:
    assistant, model = 'Claude Code', 'test-model'

    def __init__(self, fail=None):
        self.fail, self.passes = fail, []

    def __call__(self, name, prompt, schema):
        self.passes.append(name)
        if self.fail: raise self.fail
        uncited = {'id': 's9', 'kind': 'component', 'title': 'Invented', 'operation': 'new', 'subject': None, 'detail': 'no evidence',
                   'cites': ['FACT-invented']}
        if name == 'plan': return _ideal()
        return {'critique': {'missed': [], 'risks': [{'view': 'system', 'risk': 'order', 'cites': ['TASK-001']}], 'order': []},
                'ideal': _ideal([uncited])}


class IdealPlanned(unittest.TestCase):
    """NS46.T14: every Target/Ideal view is planned by the person's assistant on top of the rules, every element with
    its evidence, each view with its provenance; without an assistant the rules' target says it is not planned yet."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.report = _ideal_report(Path(self.folder.name))
        from eaos.studio import ideal
        self.ideal = ideal

    def test_every_planned_element_cites_evidence_that_exists_and_an_uncited_one_is_dropped(self):
        known = self.ideal.known_ids(self.report)
        self.assertLessEqual({'FACT-0001', 'TASK-001', 'RULE-disposition-modify'}, known)
        kept, dropped = self.ideal.check(_ideal([{'id': 's9', 'kind': 'component', 'title': 'Invented', 'operation': 'new',
                                                  'subject': None, 'detail': '', 'cites': ['FACT-invented']}]), known)
        ids = {e['id'] for view in kept['views'].values() for e in view['elements']}
        self.assertEqual(ids, {'s1', 's2', 'p1'})
        self.assertEqual([(row['view'], row['id']) for row in dropped], [('system', 's9')])
        for view in kept['views'].values():
            for element in view['elements']:
                self.assertTrue(element['cites'] and set(element['cites']) <= known, element)
        launcher = _Launcher()
        result = self.ideal.plan(self.report, launcher=launcher, lang='en')
        self.assertEqual(result['state'], 'planned', result)
        self.assertEqual(launcher.passes, ['plan', 'critique'])
        body = self.ideal.section(self.report, 'en')
        self.assertEqual(body['evidence']['share']['value'], 1.0)
        self.assertIn('s9', {row['id'] for row in body['evidence']['dropped']})
        planned = [e for view in body['views'].values() if view['planned'] for e in view['planned']['elements']]
        self.assertTrue(planned)
        for element in planned:
            self.assertTrue(element['cites'] and set(element['cites']) <= known, element)

    def test_each_ideal_view_carries_its_provenance(self):
        self.ideal.plan(self.report, launcher=_Launcher(), lang='en')
        body = self.ideal.section(self.report, 'en')
        self.assertEqual(artifact_contracts.validate({'schema_version': 1, 'contract': 1, 'revision': 2, **body},
                                                     artifact_contracts.contracts()['studio-ideal']), [])
        self.assertEqual(set(body['views']), set(self.ideal.VIEWS))
        for name, view in body['views'].items():
            provenance = view['provenance']
            self.assertLessEqual({'method', 'assistant', 'model', 'at', 'confidence', 'departures', 'open_questions'}, set(provenance), name)
            self.assertIn(provenance['method'], ('rules', 'planned'))
        system = body['views']['system']['provenance']
        self.assertEqual((system['method'], system['assistant'], system['model']), ('planned', 'Claude Code', 'test-model'))
        self.assertTrue(system['at'] and 0 <= system['confidence'] <= 1)
        self.assertEqual(system['departures'][0]['because'], 'two writers of one table')
        self.assertLessEqual({'rule_says', 'plan_chose', 'because'}, set(system['departures'][0]))
        self.assertTrue(system['open_questions'])
        inbox = self.ideal.decisions(self.report, 'en')
        self.assertTrue(inbox and all(row['state'] == 'waiting' and row['question'] for row in inbox))

    def test_without_an_assistant_the_studio_shows_the_rules_target_not_planned_yet(self):
        from eaos.studio import export
        self.assertIn('ideal', export.SECTIONS_V2)
        result = self.ideal.plan(self.report, launcher=None, adapters={}, lang='en')
        self.assertEqual(result['state'], 'not_planned')
        self.assertTrue(result['message'])
        body = self.ideal.section(self.report, 'en')
        self.assertEqual(body['state'], 'not_planned')
        self.assertTrue(body['message']['en'] and body['message']['ar'])
        for view in body['views'].values():
            self.assertEqual(view['provenance']['method'], 'rules')
            self.assertIsNone(view['planned'])
        self.assertTrue(body['views']['system']['rules']['elements'])
        failed = self.ideal.plan(self.report, launcher=_Launcher(fail=TimeoutError('took too long')), lang='en')
        self.assertEqual(failed['state'], 'failed')
        self.assertTrue(failed['message'])
        self.assertEqual({v['provenance']['method'] for v in self.ideal.section(self.report, 'en')['views'].values()}, {'rules'})
        contract = json.loads((ROOT / 'docs/studio-actions.json').read_text(encoding='utf-8'))
        self.assertEqual((ROOT / 'docs/studio-actions.json').read_bytes(), (ROOT / 'eaos/data/studio-actions.json').read_bytes())
        action = next(a for a in contract['actions'] if a['id'] == 'replan_ideal')
        self.assertTrue(action['needs_assistant'] and not action['changes_code'] and not action['irreversible'])

    def test_a_real_planning_run_on_fleetmanageweb_has_every_element_with_evidence(self):
        path = reports() / 'ideal/FleetManageWeb/run.json'
        self.assertTrue(path.is_file(), 'no recorded planning run on FleetManageWeb')
        run = json.loads(path.read_text(encoding='utf-8'))
        self.assertTrue(run['real'])
        self.assertIn(run['assistant'], ('Claude Code', 'Codex'))
        self.assertTrue(run['model'] and run['at'])
        self.assertEqual(run['passes'], ['plan', 'critique'])
        self.assertGreater(run['elements'], 0)
        self.assertEqual(run['share_with_evidence'], 1.0)
        self.assertIsInstance(run['dropped'], list)
        self.assertIsInstance(run['departures'], list)
        self.assertIsInstance(run['open_questions'], list)


def _nodes_report(base):
    """The smallest report every AI node reads: three cards with their facts, a plan, a pipeline gap, a fix batch."""
    report = _ideal_report(base)
    facts = [{'id': f'FACT-000{i}', 'kind': 'graph_node', 'location': {'path': f'src/{n}.ts', 'start_line': 1},
              'value': {'fan_in': i, 'fan_out': 0, 'depends_on': []}} for i, n in ((1, 'a'), (2, 'b'), (3, 'c'))]
    (report / 'facts/graph.json').write_text(json.dumps({'facts': facts}), encoding='utf-8')
    cards = [{'id': f'TASK-00{i}', 'title': f'Card {i}', 'severity': 'high', 'kind': 'remove_dead', 'paths': [f'src/{n}.ts'],
              'state': 'open', 'evidence': [f'FACT-000{i}'], 'confidence': 0.9, 'milestone': 'M1'} for i, n in ((1, 'a'), (2, 'b'), (3, 'c'))]
    (report / 'studio/cards.json').write_text(json.dumps({'cards': cards}), encoding='utf-8')
    tasks = [{'id': c['id'], 'title': c['title'], 'kind': 'remove_dead', 'paths': c['paths'], 'prerequisites': [],
              'evidence': {'fact_ids': c['evidence']}} for c in cards]
    tasks[2]['prerequisites'] = ['TASK-001']
    (report / 'plan.json').write_text(json.dumps({'tasks': tasks, 'waves': [['TASK-001', 'TASK-002'], ['TASK-003']],
                                                  'milestones': [{'id': 'M1', 'goal': 'Stabilise', 'tasks': [c['id'] for c in cards]}]}),
                                      encoding='utf-8')
    site = {'path': 'src/a.ts', 'line': 1, 'fact': None, 'text': None}
    gap = [{'id': f'gap:P{n}:x', 'rule': f'P{n}', 'pipeline': 'p', 'subject': 'p/a', 'subject_kind': 'stage', 'operation': 'refactor',
            'detail': f'rule P{n} broken', 'evidence': site, 'card': None, 'step': None} for n in (2, 7)]
    (report / 'studio/pipeline.json').write_text(json.dumps({'detected': True, 'views': {'gap': gap}, 'stages': [], 'routers': []}),
                                                 encoding='utf-8')
    wave = base / 'runtime/waves/wave-1'
    wave.mkdir(parents=True)
    (wave / 'wave.json').write_text(json.dumps({'wave': 1, 'branch': 'eaos/wave-1', 'kept': ['TASK-001'],
                                                'failed': {'TASK-002': 'the project\'s checks failed'}, 'stat': '1 file changed'}),
                                    encoding='utf-8')
    (wave / '0001-TASK-001.patch').write_text('--- a/src/a.ts\n+++ b/src/a.ts\n@@ -1 +1 @@\n-dead()\n+\n', encoding='utf-8')
    return report, wave


def _fill(schema):
    """A value of `schema`: each decision list holds one decision per subject the schema allows, citing the subject,
    after one decision that cites an id that does not exist."""
    kind = schema.get('type')
    kind = next((k for k in kind if k != 'null'), 'null') if isinstance(kind, list) else kind
    if 'enum' in schema: return schema['enum'][0]
    if 'oneOf' in schema: return _fill(next(s for s in schema['oneOf'] if s.get('type') != 'null'))
    if kind == 'object': return {name: _fill(sub) for name, sub in (schema.get('properties') or {}).items()}
    if kind == 'array':
        items = schema.get('items') or {}
        subject = (items.get('properties') or {}).get('subject') or {}
        if subject.get('enum'):
            rows = []
            for i, value in enumerate(subject['enum']):
                row = _fill(items)
                row.update(subject=value, evidence=[value], confidence=0.8, why='the evidence says so')
                if i == 0: rows.append(dict(row, evidence=['FACT-invented'], why='invented'))
                rows.append(row)
            return rows
        return []
    return {'string': '', 'number': 0.5, 'integer': 1, 'boolean': False}.get(kind)


class _NodeLauncher:
    assistant, model = 'Claude Code', 'test-model'

    def __init__(self, sleep=0, cost=None):
        self.sleep, self.cost_usd, self.calls = sleep, cost, []

    def __call__(self, name, prompt, schema):
        import time
        self.calls.append(name)
        if self.sleep: time.sleep(self.sleep)
        return _fill(schema)


class AINodes(unittest.TestCase):
    """NS46.T15: AI nodes are first-class stages of EAOS's pipeline: a shared decision schema, a router of declared
    branches after each node with a rules-only fallback, guards (evidence, budget, run log, cache), and the nodes drawn
    on EAOS's own pipeline map and in its truth file."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.report, self.wave = _nodes_report(Path(self.folder.name))
        from eaos.studio import nodes
        self.nodes = nodes

    def test_every_nodes_output_meets_the_shared_decision_schema_and_uncited_output_is_dropped(self):
        contracts = artifact_contracts.contracts()
        decision = {'type': 'object', '$defs': contracts['ai-node'].get('$defs', {}), **self.nodes.core.DECISION}
        records = self.nodes.run(self.report, launcher=_NodeLauncher(), wave=self.wave)
        self.assertEqual(set(records), {node.name for node in self.nodes.NODES})
        for name, record in records.items():
            self.assertEqual(artifact_contracts.validate(record, contracts['ai-node']), [], name)
            self.assertEqual(record['method'], 'model', name)
            self.assertTrue(record['decisions'], name)
            for row in record['decisions']:
                self.assertEqual(artifact_contracts.validate(row, decision), [], (name, row))
                self.assertTrue(row['evidence'], (name, row))
                self.assertNotIn('FACT-invented', row['evidence'], name)
        for name in ('card_triage', 'plan_orderer', 'fix_reviewer', 'pipeline_gap_planner'):
            self.assertTrue(any('FACT-invented' in (row.get('evidence') or []) for row in records[name]['dropped']), name)

    def test_every_node_routes_by_declared_branches_and_falls_back_to_rules_only(self):
        names = {node.name for node in self.nodes.NODES}
        self.assertGreaterEqual(names, {'ideal_planner', 'plan_orderer', 'card_triage', 'fix_reviewer', 'pipeline_gap_planner'})
        for node in self.nodes.NODES:
            self.assertEqual(node.kind, 'ai')
            self.assertTrue(node.routes, node.name)
            self.assertEqual([r.decision for r in node.routes].count('rules only'), 1, node.name)
            for route in node.routes:
                self.assertIn(route.to, names | set(self.nodes.SINKS), (node.name, route))
                self.assertTrue(route.when, (node.name, route))
        triage = {r.decision: r.to for r in self.nodes.node('card_triage').routes}
        self.assertEqual((triage['confirm'], triage['doubt'], triage['reject']), ('plan_orderer', 'probe', 'library_feedback'))
        reviewer = {r.decision for r in self.nodes.node('fix_reviewer').routes}
        self.assertLessEqual({'accept', 'retry', 'ask'}, reviewer)
        records = self.nodes.run(self.report, adapters={}, wave=self.wave)
        for name, record in records.items():
            self.assertEqual((record['state'], record['method']), ('rules_only', 'rules'), name)
            self.assertTrue(record['why'], name)
            self.assertEqual([r['decision'] for r in record['routes'] if r['subjects']], ['rules only'], name)
            self.assertTrue(record['decisions'] and all(row['source'] == 'rules' for row in record['decisions']), name)

    def test_budget_run_log_and_cache_hold_with_a_fake_launcher(self):
        import time
        Budget = self.nodes.Budget
        began = time.monotonic()
        slow = self.nodes.run(self.report, names=['card_triage'], launcher=_NodeLauncher(sleep=5), budget=Budget(seconds=1, usd=1.0))
        self.assertLess(time.monotonic() - began, 4.5)
        self.assertEqual(slow['card_triage']['state'], 'rules_only')
        self.assertIn('time', slow['card_triage']['why'])
        costly = self.nodes.run(self.report, names=['card_triage'], launcher=_NodeLauncher(cost=5.0), budget=Budget(seconds=60, usd=1.0),
                                fresh=True)
        self.assertEqual(costly['card_triage']['state'], 'rules_only')
        self.assertIn('budget', costly['card_triage']['why'])
        launcher = _NodeLauncher()
        first = self.nodes.run(self.report, names=['card_triage'], launcher=launcher, fresh=True)['card_triage']
        entry = self.nodes.core.log(self.report)[-1]
        self.assertEqual(entry['node'], 'card_triage')
        for field in ('prompt', 'model', 'inputs', 'output', 'cached', 'at'):
            self.assertIn(field, entry)
        self.assertTrue(entry['prompt'] and entry['inputs'] and entry['model'] == 'test-model')
        self.assertEqual(entry['output'], first['decisions'])
        calls = len(launcher.calls)
        again = self.nodes.run(self.report, names=['card_triage'], launcher=launcher)['card_triage']
        self.assertEqual(len(launcher.calls), calls, 'the same inputs were asked again')
        self.assertTrue(again['cached'])
        self.assertEqual(again['decisions'], first['decisions'])
        cards = json.loads((self.report / 'studio/cards.json').read_text(encoding='utf-8'))
        cards['cards'][0]['title'] = 'Card 1, changed'
        (self.report / 'studio/cards.json').write_text(json.dumps(cards), encoding='utf-8')
        changed = self.nodes.run(self.report, names=['card_triage'], launcher=launcher)['card_triage']
        self.assertGreater(len(launcher.calls), calls)
        self.assertFalse(changed['cached'])

    def test_eaos_own_pipeline_map_and_truth_show_the_ai_nodes_and_their_branches(self):
        from eaos.facts import pipeline
        from eaos.studio import pipeline as section
        anchor = 'eaos/studio/nodes/__init__.py'
        truth = json.loads((ROOT / 'evaluations/pipelines/eaos.json').read_text(encoding='utf-8'))
        mine = next(p for p in truth['pipelines'] if p['anchor'] == anchor)
        declared = {node.name: node for node in self.nodes.NODES}
        self.assertEqual(set(mine['ai_stages']), set(declared))
        for name, node in declared.items():
            router = next(r for r in mine['routers'] if r['table'] == name)
            self.assertEqual(sorted(router['branches']), sorted(r.decision for r in node.routes), name)
        body = section.section(pipeline.scan(ROOT))
        found = next(p for p in body['pipelines'] if p['entry']['path'] == anchor or any(e['path'] == anchor for e in p['evidence']))
        stages = {s['id']: s for s in body['stages'] if s['pipeline'] == found['id']}
        ai = {s['label'] for s in stages.values() if s['kind'] == 'ai'}
        self.assertEqual(ai, set(declared))
        for name, node in declared.items():
            router = next(r for r in body['routers'] if r['pipeline'] == found['id'] and r.get('table') == name)
            self.assertEqual(sorted(b['condition'] for b in router['branches']), sorted(r.decision for r in node.routes), name)
            for branch, route in zip(sorted(router['branches'], key=lambda b: b['condition']), sorted(node.routes, key=lambda r: r.decision)):
                self.assertIn(branch['to'], stages, (name, branch))
                self.assertEqual(stages[branch['to']]['label'], route.to, (name, branch))
        self.assertEqual(artifact_contracts.validate({'schema_version': 1, 'contract': 1, 'revision': 2, **body},
                                                     artifact_contracts.contracts()['studio-pipeline']), [])

    def test_a_real_card_triage_run_on_fleetmanageweb_has_every_decision_with_evidence(self):
        path = reports() / 'nodes/FleetManageWeb/card_triage.json'
        self.assertTrue(path.is_file(), 'no recorded card triage run on FleetManageWeb')
        run = json.loads(path.read_text(encoding='utf-8'))
        self.assertTrue(run['real'])
        self.assertIn(run['assistant'], ('Claude Code', 'Codex'))
        self.assertTrue(run['model'] and run['at'])
        self.assertGreater(run['decisions'], 0)
        self.assertEqual(run['share_with_evidence'], 1.0)
        self.assertLessEqual(set(run['routes']), {'confirm', 'doubt', 'reject', 'rules only'})


REPLANNED = ('FleetManageWeb', 'chief-ops', 'finance-os-a0192b7b', 'EAOS')


def _roadmap_ids():
    record = json.loads((ROOT / 'docs/north-star.json').read_text(encoding='utf-8'))
    ids = {m['id'] for m in record['milestones']} | {t['id'] for m in record['milestones'] for t in m['tasks']}
    ids |= {c['id'] for c in record['capabilities']} | {i['id'] for c in record['capabilities'] for i in c.get('indicators') or []}
    return ids | {r['id'] for r in record.get('roadmap') or []}


class ReplanTargets(unittest.TestCase):
    """NS46.T16: every target already built is planned again by the ideal planner: the four projects (EAOS itself
    among them) view by view, each with its differences from the rules' target, and EAOS's own roadmap, whose
    proposals are decisions for the owner and are never applied without the owner."""

    def test_each_project_was_replanned_by_a_real_assistant_on_every_view(self):
        from eaos.studio import ideal
        for project in REPLANNED:
            with self.subTest(project=project):
                path = reports() / 'replan' / project / 'run.json'
                self.assertTrue(path.is_file(), f'no recorded re-planning run for {project}')
                run = json.loads(path.read_text(encoding='utf-8'))
                self.assertTrue(run['real'])
                self.assertEqual(run['state'], 'planned')
                self.assertIn(run['assistant'], ('Claude Code', 'Codex'))
                self.assertTrue(run['model'] and run['at'])
                self.assertEqual(run['passes'], ['plan', 'critique'])
                self.assertGreater(run['elements'], 0)
                self.assertEqual(run['share_with_evidence'], 1.0)
                self.assertEqual(set(run['views']), set(ideal.VIEWS))
                for name, view in run['views'].items():
                    if view['method'] != 'planned':
                        # Only a view with nothing in it on either side may stay on the rules, and it says why.
                        self.assertEqual((view['rules'], view['planned'] or 0), (0, 0), (project, name))
                        self.assertTrue(view.get('why_empty'), (project, name))
                    self.assertLessEqual({'same', 'changed', 'added', 'rules_only'}, set(view['differences']), (project, name))
                planned = [name for name, view in run['views'].items() if view['method'] == 'planned']
                self.assertGreaterEqual(len(planned), 6, (project, planned))
                self.assertIsInstance(run['differences'], list)
                self.assertTrue(run['differences'])
                for row in run['differences']:
                    self.assertIn(row['view'], ideal.VIEWS)
                    self.assertIn(row['kind'], ('same', 'changed', 'added'))
                self.assertIsInstance(run['departures'], list)
                self.assertIsInstance(run['open_questions'], list)
        eaos = json.loads((reports() / 'replan/EAOS/run.json').read_text(encoding='utf-8'))
        self.assertEqual(eaos['views']['pipeline']['method'], 'planned', 'EAOS is a pipeline: its pipeline view must be planned')

    def test_the_roadmap_proposals_are_decisions_for_the_owner_never_applied(self):
        data = json.loads((ROOT / 'docs/roadmap-proposals.json').read_text(encoding='utf-8'))
        run = data['run']
        self.assertTrue(run['real'])
        self.assertIn(run['assistant'], ('Claude Code', 'Codex'))
        self.assertTrue(run['model'] and run['at'])
        self.assertEqual(run['passes'], ['plan', 'critique'])
        self.assertEqual(run['share_with_evidence'], 1.0)
        proposals = data['proposals']
        self.assertTrue(proposals)
        known = _roadmap_ids()
        text = (ROOT / 'docs/roadmap-proposals.md').read_text(encoding='utf-8')
        for row in proposals:
            with self.subTest(proposal=row['id']):
                self.assertTrue(row['title'] and row['detail'] and row['recommendation'])
                self.assertTrue(row['cites'] and set(row['cites']) <= known, row['cites'])
                decision = row['decision']
                self.assertEqual(decision['options'], ['approve', 'reject'])
                self.assertIn(decision['state'], ('waiting', 'approved', 'rejected'))
                if decision['state'] != 'waiting':
                    self.assertRegex((decision.get('owner_verdict') or {}).get('date') or '', r'^\d{4}-\d{2}-\d{2}$')
                self.assertTrue(row['applied'] is False or decision['state'] == 'approved', row['id'])
                self.assertIn(row['id'], text)


if __name__ == '__main__':
    unittest.main()
