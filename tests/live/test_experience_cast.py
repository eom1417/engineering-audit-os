"""Several simulated users (M10.5): each goal runs in its order in a browser of its own; a goal waits for the goals it
needs and is told their events, is blocked when one was not reached, and the run's budget blocks what is left."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.live.experience import cast

SCENARIO = {'version': 1, 'personas': [
    {'id': 'buyer', 'role': 'user', 'name': 'Sara', 'goals': [
        {'id': 'order', 'goal': 'Order a lamp', 'start': '/', 'done_when': 'Ordered', 'waits_for': [], 'makes': 'order-placed'},
        {'id': 'track', 'goal': 'See my order approved', 'start': '/orders', 'done_when': 'Approved',
         'waits_for': ['admin.approve'], 'makes': None}]},
    {'id': 'admin', 'role': 'admin', 'name': 'Omar', 'goals': [
        {'id': 'approve', 'goal': 'Approve the new order', 'start': '/admin', 'done_when': 'Approved',
         'waits_for': ['buyer.order'], 'makes': 'order-approved'}]}],
    'handoffs': [{'from': 'buyer.order', 'event': 'order-placed', 'to': 'admin.approve'},
                 {'from': 'admin.approve', 'event': 'order-approved', 'to': 'buyer.track'}]}
ORDER = ['buyer.order', 'admin.approve', 'buyer.track']
DONE, STUCK = {'action': 'done'}, {'action': 'stuck', 'why': 'no approve button'}


class Fake:
    """A browser whose page never changes; it keeps where it was opened and as whom."""
    opened = []

    def __init__(self, base, out, storage_state=None):
        self.out = Path(out)
        Fake.opened.append((self.out.name, storage_state))

    def __enter__(self): return self

    def __exit__(self, *_): pass

    def do(self, command): return {'ok': True, 'path': '/', 'text': 'Home', 'controls': []}


class Scripted:
    """The assistant: the next step it is given; it keeps the briefs."""
    def __init__(self, *steps):
        self.steps, self.briefs = list(steps), []

    def complete(self, messages, **options):
        self.briefs.append(json.loads(messages[-1]['content']))
        return {'result': self.steps.pop(0)}, {}


class CastTests(unittest.TestCase):
    def setUp(self):
        Fake.opened = []
        patcher = mock.patch.object(cast, 'Browser', Fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = {'base': 'http://app', 'sessions': {'admin': 'admin.json', 'user': None}}

    def run_cast(self, assistant, **plan):
        return cast.run(self.app, SCENARIO, {'order': ORDER, **plan}, assistant, self.tmp.name)

    def test_a_goal_runs_after_the_one_it_waits_for_and_is_told_its_event(self):
        assistant = Scripted(DONE, DONE, DONE)
        data = {'through_ui': [{'goal': 'buyer.order', 'values': {'Email': 'sara@example.com'}}]}
        run = self.run_cast(assistant, data=data)
        self.assertEqual([(g['name'], g['status']) for g in run['goals']],
                         [('buyer.order', 'reached'), ('admin.approve', 'reached'), ('buyer.track', 'reached')])
        self.assertEqual([(e['event'], e['by']) for e in run['events']],
                         [('order-placed', 'buyer.order'), ('order-approved', 'admin.approve')])
        self.assertEqual(assistant.briefs[0]['values_to_use'], {'Email': 'sara@example.com'})
        self.assertEqual([e['event'] for e in assistant.briefs[1]['happened_before_you']], ['order-placed'])
        self.assertEqual(Fake.opened, [('buyer--order', None), ('admin--approve', 'admin.json'), ('buyer--track', None)])
        experience = Path(self.tmp.name) / 'experience'
        self.assertEqual(json.loads((experience / 'run.json').read_text())['calls'], 3)
        self.assertTrue(all((experience / 'journeys' / f'{n}.json').is_file() for n in ('buyer--order', 'admin--approve', 'buyer--track')))

    def test_a_goal_waiting_on_a_goal_not_reached_is_blocked(self):
        run = self.run_cast(Scripted(DONE, STUCK))
        self.assertEqual(run['goals'][1]['why'], 'no approve button')
        self.assertEqual((run['goals'][2]['status'], run['goals'][2]['waited_for']), ('blocked', ['admin.approve']))
        self.assertEqual(len(Fake.opened), 2, 'a blocked goal opens no browser')

    def test_the_journey_on_stuck_answers_replaces_the_stuck_one(self):
        helped = []

        def on_stuck(journey, persona, goal):
            helped.append((journey['stuck'], persona['id'], goal['name']))
            return {**journey, 'reached': True, 'stuck': None, 'calls': 2, 'friction': [{'step': 1, 'kind': 'find', 'note': 'asked support'}]}
        run = self.run_cast(Scripted(DONE, STUCK, DONE), on_stuck=on_stuck)
        self.assertEqual(helped, [('no approve button', 'admin', 'admin.approve')])
        self.assertEqual([g['status'] for g in run['goals']], ['reached', 'reached', 'reached'])
        self.assertEqual((run['goals'][1]['calls'], run['goals'][1]['friction']), (3, 1))
        journeys = Path(self.tmp.name) / 'experience/journeys'
        first, again = (json.loads((journeys / f'admin--approve{s}.json').read_text()) for s in ('', '--again'))
        self.assertEqual((first['reached'], first['pictures_dir'], 'attempt' in first), (False, 'admin--approve', False),
                         'the first try is kept, not overwritten by the retry')
        self.assertEqual((again['reached'], again['attempt']), (True, 'again'))

    def test_the_runs_budget_blocks_the_goals_left(self):
        with mock.patch.dict(cast.BUDGET, calls=1):
            run = self.run_cast(Scripted(DONE))
        self.assertEqual([g['status'] for g in run['goals']], ['reached', 'blocked', 'blocked'])
        self.assertEqual(run['goals'][1]['why'], "the run's budget ran out")


if __name__ == '__main__':
    unittest.main()
