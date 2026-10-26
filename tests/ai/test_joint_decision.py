"""The check decides with the person's assistant before it writes its reports (docs/AI-IN-THE-PIPELINE.md): the triage's
rejected cards leave the plan and the gaps, the ideal planner's answers become the final target with who decided each
component, the order becomes the plan's steps; without an assistant the same path gives the rules' result."""
import json
import shutil
import unittest
from pathlib import Path
from unittest import mock

from shared_fixture import TemporaryWorkspace

from eaos.pipeline.run import execute
from eaos.pipeline.stages import BY_NAME, ORDER
from eaos.ai.nodes import framework as core

ROOT = Path(__file__).resolve().parents[2]


def project(base):
    """Seven components and nine cards: the polyglot fixture with the redundant one beside it; the policy places the
    worker in a layer, so the owner protects it."""
    target = Path(base) / 'shop'
    shutil.copytree(ROOT / 'tests/fixtures/polyglot', target)
    shutil.copytree(ROOT / 'tests/fixtures/sustainability/redundant', target / 'redundant')
    (target / 'eaos.policy.json').write_text(json.dumps({'schema_version': 1, 'layers': {'jobs': ['worker/**']}}), encoding='utf-8')
    return target


def bundle(prompt):
    return json.loads(prompt[prompt.rindex('The bundle:\n') + len('The bundle:\n'):])


def element(id_, operation, subject=None):
    return {'id': id_, 'kind': 'component', 'title': id_, 'operation': operation, 'subject': subject, 'detail': f'{operation} it',
            'cites': ['RULE-plan-order']}


class Assistant:
    """Answers the triage, the ideal and the order the way a person's assistant would, with evidence."""
    assistant, model, cost_usd = 'Claude Code', 'test-model', None
    rejected = set()

    def __call__(self, name, prompt, schema):
        text = json.dumps(schema)
        if 'changes' in schema['properties']:          # the ideal's critique answers only its changes: none here
            return {'critique': {'missed': [], 'risks': [], 'order': []},
                    'changes': {'put': [], 'remove': [], 'summaries': [], 'aspects': [], 'departures': [], 'open_questions': [],
                                'drop_questions': [], 'confidence': None}}
        if '"views"' in text:
            ideal = {'views': {view: {'summary': '', 'confidence': 0.8, 'elements': []} for view in
                               ('system', 'change', 'journeys', 'paths', 'data_paths', 'infra', 'pipeline', 'plan_order')},
                     'departures': [{'view': 'system', 'element': 'T-api', 'rule_says': 'retain', 'plan_chose': 'rebuild',
                                     'because': 'its handlers mix transport and rules', 'cites': ['RULE-plan-order']}],
                     'open_questions': [], 'confidence': 0.8}
            ideal['views']['system']['elements'] = [element('T-api', 'rebuild'), element('T-svc', 'retain'),
                                                    element('T-worker', 'delete'), element('TC-domain', 'delete'),
                                                    element('TC-events', 'new'),
                                                    dict(element('T-core', 'rebuild'), cites=sorted(Assistant.rejected))]
            mine = set(schema['properties']['views']['properties'])          # one part of the plan pass: its views
            return {**ideal, 'views': {k: v for k, v in ideal['views'].items() if k in mine},
                    'departures': [d for d in ideal['departures'] if d['view'] in mine]}
        subjects = schema['properties']['decisions']['items']['properties']['subject']['enum']
        if subjects == ['plan']:
            tasks = [t['id'] for t in bundle(prompt)['tasks']]
            steps = [{'id': 's1', 'title': 'The last card first', 'tasks': tasks[-1:], 'why': 'it unblocks the rest'},
                     {'id': 's2', 'title': 'The rest', 'tasks': tasks[:-1], 'why': 'same file'}]
            return {'summary': '', 'decisions': [decision('plan', 'reorder', tasks[:1], {'steps': steps})]}
        if all(s.startswith('TASK-') for s in subjects):
            on_core = {c['id'] for c in bundle(prompt)['cards'] if 'core/audit.py' in c['paths']}
            verdict = lambda card: 'reject' if card in on_core else 'doubt' if card == 'TASK-002' else 'confirm'
            Assistant.rejected |= on_core
            return {'summary': '', 'decisions': [decision(s, verdict(s), [s], {'falsifier': 'a caller', 'harmed': 'the app users'}) for s in subjects]}
        return {'summary': '', 'decisions': []}


def decision(subject, choice, evidence, detail):
    return {'subject': subject, 'decision': choice, 'options': [], 'evidence': evidence, 'confidence': 0.8, 'why': f'{choice}: because',
            'open_questions': [], 'detail': detail}


class JointDecision(TemporaryWorkspace):
    @classmethod
    def setUpClass(cls):
        cls.workspace()
        base = Path(cls.tmp.name)
        target = project(base)
        cls.rules = execute(target, base / 'rules', language='en')
        with mock.patch.object(core, 'pick', return_value=object()), mock.patch.object(core, 'AdapterLauncher', return_value=Assistant()):
            cls.joint = execute(target, base / 'joint', language='en', provider=object())
        cls.base = base

    def read(self, run, name):
        return json.loads((self.base / run / name).read_text(encoding='utf-8'))

    def test_without_an_assistant_the_same_path_completes_and_the_rules_decide_everything(self):
        self.assertEqual(self.rules['status'], 'COMPLETE')
        for name in ('semantic', 'proposals', 'triage', 'ideal', 'pipeline_gaps', 'order'):
            self.assertEqual((self.rules['stages'][name]['status'], self.rules['stages'][name]['reason_code']), ('unavailable', 'no_provider'))
        target, proposal = self.read('rules', 'target-architecture.json'), self.read('rules', 'target-proposal.json')
        self.assertEqual({c['decided_by']['label'] for c in target['current_components']}, {'rule_only'})
        self.assertEqual([c['relation'] for c in target['current_components']], [c['relation'] for c in proposal['current_components']])
        self.assertEqual([(r['gap'], r['blocking_tasks']) for r in target['gap_matrix']],
                         [(r['gap'], r['blocking_tasks']) for r in proposal['gap_matrix']])
        self.assertEqual((self.read('rules', 'cards.json')['decided_by'], self.read('rules', 'plan.json')['order']['source']), ('rules', 'rules'))

    def test_a_card_the_triage_rejected_leaves_the_plan_and_the_gaps(self):
        plan, cards = self.read('joint', 'plan.json'), self.read('joint', 'cards.json')
        core = {t['id']: t['claim_id'] for t in self.read('rules', 'plan.json')['tasks'] if t['paths'] == ['core/audit.py']}
        self.assertTrue(core)
        self.assertFalse(core.keys() & {t['id'] for t in plan['tasks']})
        self.assertEqual({row['card']: row['claim_id'] for row in cards['set_aside']}, core)
        # Self-audit: the verdicts reached only the plan; the claims the assistant rejected stayed open and ranked among
        # the top risks, and a doubted card stayed "ready". Applied once, every later reader sees them.
        claims = {c['id']: c for c in self.read('joint', 'dossier.json')['claims']}
        self.assertEqual({(claims[c]['confidence'], claims[c]['triage']['decision'], claims[c]['priority']) for c in core.values()},
                         {('REFUTED', 'reject', 0.0)})
        self.assertFalse(set(core.values()) & {i['claim_id'] for i in self.read('joint', 'debt-register.json')['items']})
        self.assertEqual({d['kind'] for d in self.read('joint', 'plan.json')['decisions']
                          if d['observation_uid'] in {claims[c]['uid'] for c in core.values()}}, {'retain'})
        # A doubted card is neither fixed blind nor handed to the person: it closes as not proven, judged again next check.
        doubted = next(row for row in cards['closed'] if row['card'] == 'TASK-002')
        self.assertTrue(doubted['why'].startswith('Not proven by its evidence'), doubted)
        self.assertNotIn(doubted['claim_id'], {t['claim_id'] for t in plan['tasks']})
        gap = lambda run: {r['component']: r for r in self.read(run, 'target-architecture.json')['gap_matrix']}['T-core']
        self.assertTrue(core.keys() <= set(gap('rules')['blocking_tasks']))
        self.assertFalse(core.keys() & set(gap('joint')['blocking_tasks']))

    def test_the_assistants_answers_become_the_final_target_and_its_gaps_with_who_decided(self):
        target = self.read('joint', 'target-architecture.json')
        by_id = {c['id']: c for c in target['current_components']}
        self.assertEqual((by_id['T-api']['relation'], by_id['T-api']['decided_by']['label'], by_id['T-api']['decided_by']['rule']),
                         ('rebuild', 'ai_modified', 'retain'))
        self.assertEqual(by_id['T-api']['decided_by']['why'], 'its handlers mix transport and rules')
        # Its one file moves into its feature: the rules say modify (one file is no rebuild), the assistant keeps it.
        self.assertEqual((by_id['T-svc']['decided_by']['rule'], by_id['T-svc']['decided_by']['label']), ('modify', 'ai_modified'))
        self.assertEqual((by_id['T-worker']['relation'], by_id['T-worker']['decided_by']['label']), ('retain', 'disagreement'))
        self.assertEqual(by_id['T-root']['decided_by']['label'], 'rule_only')
        gaps = {r['component']: r for r in target['gap_matrix']}
        # its routes write with no sign-in check (M6): cards now close part of its gap
        self.assertEqual((gaps['T-api']['gap'], gaps['T-api']['decided_by']), ('partial', 'ai_modified'))
        names = {t['name']: t['decided_by']['label'] for t in target['target_components']}
        self.assertEqual((names['domain'], names['TC-events']), ('disagreement', 'ai_added'))
        # Self-audit: the ideal planner cited a claim the triage had rejected; standing only on it, the rule stays.
        self.assertEqual((by_id['T-core']['relation'], by_id['T-core']['decided_by']['label']), ('retain', 'disagreement'))
        self.assertEqual({d['element'] for d in target['disagreements']}, {'T-api', 'T-svc', 'T-worker', 'TC-domain', 'T-core'})
        self.assertEqual({k: target['decided'][k] for k in ('ai_modified', 'disagreement', 'ai_added')},
                         {'ai_modified': 2, 'disagreement': 3, 'ai_added': 1})
        self.assertIn('Rebuild `api` as `interface`', (self.base / 'joint/TARGET-ARCHITECTURE.md').read_text(encoding='utf-8'))

    def test_the_assistant_saying_what_the_rules_say_is_never_a_disagreement(self):
        # it was asked of the owner as "the rules say delete and your assistant said delete", on protected files
        from eaos.report.target_architecture.picture import _decide_current
        component = {'relation': 'delete', 'paths': ['console/src/core/main.js']}
        self.assertEqual(_decide_current(component, {'operation': 'delete', 'cites': []}, 'both', lambda path: True)[0], 'agreed')

    def test_the_order_becomes_the_plans_steps_before_the_reports_are_written(self):
        order = self.read('joint', 'plan.json')['order']
        self.assertEqual((order['source'], [s['id'] for s in order['steps']]), ('assistant', ['s1', 's2']))
        self.assertIn('The last card first', (self.base / 'joint/PLAN/STEPS.md').read_text(encoding='utf-8'))
        # The reports are written after every decision.
        decided = ('triage', 'cards', 'ideal', 'pipeline_gaps', 'reconcile', 'order', 'steps')
        self.assertGreater(ORDER.index('reports'), max(ORDER.index(name) for name in decided))
        self.assertEqual(BY_NAME['reports'].requires, ('reconcile', 'steps'))
        self.assertEqual(self.joint['status'], 'COMPLETE')

    def test_a_decision_an_earlier_check_left_on_disk_is_never_read_as_this_ones(self):
        out = self.base / 'stale'
        shutil.copytree(self.base / 'rules', out)
        shutil.copytree(self.base / 'joint/nodes', out / 'nodes')
        shutil.copytree(self.base / 'joint/ideal', out / 'ideal')
        again = execute(self.base / 'shop', out, language='en')
        self.assertEqual((again['stages']['triage']['status'], self.read('stale', 'cards.json')['set_aside']), ('unavailable', []))
        self.assertEqual(len(self.read('stale', 'plan.json')['tasks']), len(self.read('rules', 'plan.json')['tasks']))
        self.assertEqual(self.read('stale', 'target-architecture.json')['decided']['by'], 'rules')
        self.assertEqual(self.read('stale', 'plan.json')['order']['source'], 'rules')


class OwnerShareTests(unittest.TestCase):
    def test_every_source_shares_one_owner_cap_and_a_doubted_card_is_kept_not_proven(self):
        # The self-check asked the owner 20 questions for 123 cards (14 from the planner) and left 16 doubted cards to them.
        from eaos.analysis.repair.review import resolutions
        from eaos.core.contracts.owner_share import capped as _capped
        rows = [{'id': 'target-architecture', 'state': 'waiting', 'recommended_option': 'review'},
                {'id': 'ideal-OQ-a', 'state': 'waiting', 'recommended_option': 'o1'},
                {'id': 'ideal-OQ-b', 'state': 'waiting', 'recommended_option': None},
                {'id': 'node-x:Q', 'state': 'waiting', 'recommended_option': 'o2'}]
        capped = {r['id']: (r['state'], r.get('answer')) for r in _capped(rows, 20)}
        self.assertEqual(capped, {'target-architecture': ('waiting', None), 'ideal-OQ-a': ('answered', 'o1'),
                                  'ideal-OQ-b': ('waiting', None), 'node-x:Q': ('answered', 'o2')})
        doubted = resolutions([{'id': 'TASK-001'}], {'TASK-001': {'decision': 'doubt', 'why': 'only a line count'}}, [])
        self.assertEqual(doubted['TASK-001']['resolution'], 'keep')


if __name__ == '__main__':
    unittest.main()
