"""analysis/experience/scenario.py: the personas, their goals and hand-offs planned once, repaired by rules, ordered."""
import json
import tempfile
import unittest
from pathlib import Path

from eaos.analysis.experience import scenario

ROLES = {'roles': [{'id': 'customer', 'name': {'en': 'Customer', 'ar': 'العميل'}, 'pages': ['/shop']},
                   {'id': 'admin', 'name': 'Administrator', 'pages': ['/admin']}]}
FEATURES = {'features': [{'name': 'orders', 'description': 'place an order', 'surfaces': ['/shop'], 'critical': True},
                         {'name': 'approvals', 'description': 'approve orders', 'surfaces': ['/admin'], 'critical': True},
                         {'name': 'about', 'description': 'the about page', 'surfaces': ['/about'], 'critical': False}]}
GOOD = {'personas': [
    {'id': 'buyer', 'role': 'customer', 'name': 'Sara', 'about': 'Buys things.',
     'goals': [{'id': 'order', 'goal': 'Place an order', 'start': '/shop', 'done_when': 'A thank-you page',
                'waits_for': [], 'makes': 'order-placed'},
               {'id': 'receive', 'goal': 'See the order approved', 'start': '/shop', 'done_when': 'Approved shows',
                'waits_for': ['admin.approve'], 'makes': None}]},
    {'id': 'admin', 'role': 'admin', 'name': 'Omar', 'about': 'Runs the shop.',
     'goals': [{'id': 'approve', 'goal': 'Approve the order', 'start': '/admin', 'done_when': 'Approved',
                'waits_for': [], 'makes': 'order-approved'}]}],
    'handoffs': [{'from': 'buyer.order', 'event': 'order-placed', 'to': 'admin.approve'},
                 {'from': 'admin.approve', 'event': 'order-approved', 'to': 'buyer.receive'}]}


class Assistant:
    """A provider answering every question with `answer`, wrapped as the adapters may return it."""

    def __init__(self, answer):
        self.answer, self.asked = answer, []

    def complete(self, messages, small=False, stage=None, reads=None, deep=False):
        self.asked.append({'stage': stage, 'deep': deep, 'brief': json.loads(messages[-1]['content'])})
        return {'result': self.answer}, {}


class ScenarioTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.report = Path(folder.name)
        (self.report / 'roles.json').write_text(json.dumps(ROLES))
        (self.report / 'features.json').write_text(json.dumps(FEATURES))

    def test_valid_plan_is_asked_once_deep_and_written(self):
        assistant = Assistant(GOOD)
        made = scenario.plan(self.report, assistant)
        self.assertEqual([(a['stage'], a['deep']) for a in assistant.asked], [('experience_scenario', True)])
        self.assertEqual([r['id'] for r in assistant.asked[0]['brief']['roles']], ['customer', 'admin'])
        self.assertEqual((made['source'], made['dropped']), ('assistant', []))
        self.assertEqual(len(made['handoffs']), 2)
        self.assertEqual(json.loads((self.report / 'experience/scenario.json').read_text()), made)

    def test_bad_references_unknown_roles_and_cycles_are_repaired(self):
        unknown = json.loads(json.dumps(GOOD))
        unknown['personas'][0]['role'] = 'wizard'
        self.assertEqual(scenario.checked(unknown, ['customer', 'admin'])['personas'][0]['role'], 'visitor')
        bad = json.loads(json.dumps(GOOD))      # signed in: a visitor's goal would gate nothing, and no circle would close
        bad['personas'][0]['goals'][0]['waits_for'] = ['buyer.receive', 'nobody.nothing', 'buyer.order']
        bad['personas'][1]['goals'].append({'id': 'Approve', 'goal': 'again', 'waits_for': []})
        bad['handoffs'].append({'from': 'ghost.walk', 'to': 'admin.approve', 'event': 'x'})
        made = scenario.checked(bad, ['customer', 'admin'])
        buyer, admin = made['personas']
        self.assertEqual([g['id'] for g in admin['goals']], ['approve', 'approve-2'])
        names = {f"{p['id']}.{g['id']}": g['waits_for'] for p in made['personas'] for g in p['goals']}
        self.assertNotIn('nobody.nothing', names['buyer.order'])
        self.assertNotIn('buyer.order', names['buyer.order'])
        played = scenario.order(made)
        for name, waits in names.items(): self.assertTrue(all(played.index(w) < played.index(name) for w in waits))
        for handoff in made['handoffs']: self.assertIn(handoff['from'], names[handoff['to']])
        self.assertTrue(any('circle' in d['why'] for d in made['dropped']))
        self.assertTrue(any('ghost.walk' in d['what'] for d in made['dropped']))

    def test_a_handoff_makes_its_receiver_wait(self):
        loose = json.loads(json.dumps(GOOD))
        loose['personas'][1]['goals'][0]['waits_for'] = []
        made = scenario.checked(loose, ['customer', 'admin'])
        self.assertEqual(made['personas'][1]['goals'][0]['waits_for'], ['buyer.order'])

    def test_a_signed_in_persona_never_waits_for_a_visitors_sign_up(self):
        # flask-microblog (M10.10): every signed-in goal waited for a newcomer's sign-up; it failed, 9 of 11 were blocked
        plan = {'personas': [{'id': 'newcomer', 'role': 'visitor', 'name': 'Ana', 'about': 'new',
                              'goals': [{'id': 'join', 'goal': 'sign up', 'start': '/', 'done_when': 'in', 'waits_for': [], 'makes': 'joined'}]},
                             {'id': 'buyer', 'role': 'customer', 'name': 'Sara', 'about': 'buys',
                              'goals': [{'id': 'order', 'goal': 'order', 'start': '/shop', 'done_when': 'ok',
                                         'waits_for': ['newcomer.join'], 'makes': None}]}],
                'handoffs': [{'from': 'newcomer.join', 'event': 'joined', 'to': 'buyer.order'}]}
        made = scenario.checked(plan, ['customer'])
        self.assertEqual((made['personas'][1]['goals'][0]['waits_for'], made['handoffs']), ([], []))
        self.assertIn('buyer.order waits for newcomer.join', [d['what'] for d in made['dropped']])

    def test_order_puts_every_goal_after_what_it_waits_for(self):
        made = scenario.checked(GOOD, ['customer', 'admin'])
        self.assertEqual(scenario.order(made), ['buyer.order', 'admin.approve', 'buyer.receive'])

    def test_without_an_assistant_rules_make_one_persona_per_role_and_goals_from_features(self):
        made = scenario.plan(self.report)
        self.assertEqual(made['source'], 'rules')
        goals = {p['id']: [g['id'] for g in p['goals']] for p in made['personas']}
        self.assertEqual(goals, {'customer': ['orders'], 'admin': ['approvals']})
        self.assertTrue((self.report / 'experience/scenario.json').is_file())

    def test_without_roles_rules_plan_one_visitor(self):
        (self.report / 'roles.json').unlink()
        made = scenario.plan(self.report, Assistant({'personas': []}))
        self.assertEqual([(p['id'], p['role']) for p in made['personas']], [('visitor', 'visitor')])


if __name__ == '__main__':
    unittest.main()
