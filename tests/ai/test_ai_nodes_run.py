"""The AI nodes of EAOS's pipeline (docs/AI-IN-THE-PIPELINE.md): the planners, a stuck node, and the run engine's
`run_nodes`."""
import json
import os
import unittest
from pathlib import Path
from unittest import mock
from eaos.ai import nodes
from eaos.ai.nodes import framework as core
ROOT = Path(__file__).resolve().parents[2]
from eaos.core.system import process as provider
from tests.ai._ai_nodes_fixture import Answer, decision
from tests.ai.test_ai_nodes import Base


class Planners(Base):
    """The plan orderer keeps every prerequisite and sets rejected cards aside; the fix reviewer never accepts what the
    gates failed."""

    def test_the_orderer_keeps_prerequisites_and_the_gates_stay_the_judge_of_a_fix(self):
        bad = {'steps': [{'id': 's1', 'title': 'first', 'tasks': ['TASK-003'], 'why': ''},
                         {'id': 's2', 'title': '', 'tasks': ['TASK-001'], 'why': ''}]}
        launcher = Answer(lambda n, s: {'summary': '',
                                        'decisions': [decision('plan', 'reorder', ['TASK-001'], detail=bad)]})
        record = nodes.run(self.report, names=['plan_orderer'], launcher=launcher)['plan_orderer']
        self.assertIn('before its prerequisite TASK-001', record['dropped'][0]['why'])
        self.assertEqual([c[0] for c in launcher.calls], ['plan', 'critique'])
        good = {'steps': [{'id': 's1', 'title': 'first', 'tasks': ['TASK-002'], 'why': 'small'}]}
        (self.report / 'nodes/card_triage').mkdir(parents=True)
        (self.report / 'nodes/card_triage/verdicts.json').write_text(json.dumps({'verdicts': [{'card': 'TASK-003',
                                                                                               'decision': 'reject'}]}),
                                                                     encoding='utf-8')
        nodes.run(self.report, names=['plan_orderer'], launcher=Answer(lambda n, s: {'summary': '', 'decisions': [
            decision('plan', 'reorder', ['TASK-002'], detail=good)]}), fresh=True)
        order = json.loads((self.report / 'nodes/plan_orderer/order.json').read_text(encoding='utf-8'))
        self.assertEqual([s['tasks'] for s in order['steps']], [['TASK-002'], ['TASK-001']],
                         'the cards it left out follow')
        self.assertEqual(order['set_aside'], ['TASK-003'])
        self.assertEqual(json.loads((self.report / 'plan.json').read_text(encoding='utf-8'))['waves'],
                         [['TASK-001', 'TASK-002'], ['TASK-003']])

        launcher = Answer(lambda n, s: {'summary': '', 'decisions': [decision('TASK-001', 'accept', ['TASK-001']),
                                                                    decision('TASK-002', 'accept', ['TASK-002'])]})
        record = nodes.run(self.report, names=['fix_reviewer'], launcher=launcher, wave=self.wave)['fix_reviewer']
        self.assertEqual(record['dropped'][0]['why'], 'the gates failed this fix, so it cannot be accepted')
        review = json.loads((self.report / 'nodes/fix_reviewer/review.json').read_text(encoding='utf-8'))
        self.assertEqual([(c['card'], c['decision']) for c in review['cards']],
                         [('TASK-001', 'accept'), ('TASK-002', 'rules only')])
        self.assertNotIn('fix_reviewer', nodes.run(self.report, names=['fix_reviewer'], launcher=launcher),
                         'nothing to read without a batch')


class Stuck(Base):
    def test_with_a_stuck_assistant_the_rules_decide(self):
        def stuck(name, schema): raise provider.Stuck('silent')
        record = self.triage(Answer(stuck))
        self.assertEqual((record['state'], record['why']), ('rules_only', core.WORDS['stuck']))


class RunFromTheEngine(Base):
    """The run engine's `run_nodes`: a run of the manager, the nodes' steps as events, the summary as its result."""

    def setUp(self):
        super().setUp()
        self.env = mock.patch.dict(os.environ,
                                   {'EAOS_HOME': str(self.base / 'home'), 'EAOS_OUTPUT': str(self.base / 'out')})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.project = self.base / 'project'
        self.project.mkdir()

    def test_the_nodes_run_and_end_with_their_summary(self):
        from eaos.interfaces import runs as actions
        from eaos.journeys.fix import selection
        patch = mock.patch.object(selection, 'studio_folder', return_value=self.report / 'studio')
        patch.start()
        self.addCleanup(patch.stop)
        app = actions.Actions(self.project, port=8765, adapters={}, studio=self.report / 'studio', lang='en')
        self.addCleanup(app.close)
        headers = {'X-EAOS-Token': app.token, 'X-EAOS-CSRF': app.csrf, 'Origin': 'http://127.0.0.1:8765',
                   'Host': '127.0.0.1:8765'}
        contract = json.loads((ROOT / 'docs/studio-actions.json').read_text(encoding='utf-8'))
        action = next(a for a in contract['actions'] if a['id'] == 'run_nodes')
        self.assertTrue(action['needs_assistant'] and not action['changes_code'] and action['tool'] == 'run_nodes')
        with mock.patch('eaos.journeys.guided.publish'), mock.patch('eaos.core.project.state.load', return_value={}):
            status, body = app.handle('POST', '/api/runs', headers,
                                      {'action': 'run_nodes', 'inputs': {'nodes': ['card_triage', 'plan_orderer']}})
            self.assertEqual(status, 200, body)
            run = app.wait(body['run']['id'], ('done', 'failed'), timeout=30)
        self.assertEqual(run['state'], 'done', run)
        self.assertEqual(set(run['result']['nodes']), {'card_triage', 'plan_orderer'})
        self.assertEqual(run['result']['nodes']['card_triage']['routes']['rules only'], 3)
        self.assertIn('step', [e['kind'] for e in app.store.events(run['id'])])


class AnyNodeAnyTime(unittest.TestCase):
    def test_any_node_runs_as_a_job_an_assistant_starts_and_the_contract_lists_every_node(self):
        # Every node can be re-run at any time, also by an assistant, so every node is in the list.
        import json
        from pathlib import Path
        from eaos.interfaces.mcp_server import node_jobs
        from eaos.ai import nodes
        contract = json.loads((Path(__file__).resolve().parents[2] / 'docs/studio-actions.json').read_text())
        action = next(a for a in contract['actions'] if a['id'] == 'run_nodes')
        self.assertEqual(set(action['inputs']['properties']['nodes']['items']['enum']), {n.name for n in nodes.NODES})
        with mock.patch('eaos.journeys.agent_tools._start',
                        return_value={'job': 'j1', 'status': 'started'}) as started, \
                mock.patch('eaos.journeys.agent_tools.state_of', return_value={'project': '/p'}):
            self.assertEqual(node_jobs.start('/p', ['plan_orderer'])['job'], 'j1')
        self.assertEqual(started.call_args.kwargs['runner'], 'eaos.interfaces.mcp_server.node_jobs')
        self.assertIn('run_nodes', node_jobs.JOBS)


if __name__ == '__main__':
    unittest.main()
