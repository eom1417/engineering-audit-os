"""Support and tickets (M10.6): a stuck persona writes a ticket, support answers or escalates, an answered persona tries
once more; tickets are kept per run and the friction log gathers every journey's friction by kind."""
import contextlib
import json
import tempfile
import unittest
from pathlib import Path

from eaos.core.contracts.untrusted import CLAUSE, UNTRUSTED
from eaos.live.experience import support

PERSONA = {'id': 'buyer', 'role': 'user', 'name': 'Sara', 'about': 'a first-time buyer'}
GOAL = {'name': 'buyer.order', 'goal': 'Order a lamp', 'start': '/', 'done_when': 'the page says Ordered'}
STUCK = {'goal': 'buyer.order', 'persona': 'buyer', 'wanted': 'Order a lamp', 'start': '/', 'reached': False,
         'stuck': 'I cannot find the basket', 'steps': [{'action': 'click', 'at': '/', 'landed': '/shop'}],
         'friction': [{'step': 1, 'kind': 'find', 'note': 'no basket anywhere'}]}


class Scripted:
    """An assistant answering, by stage, what it is given; it keeps what it was asked."""
    def __init__(self, support_reply, *steps):
        self.reply, self.steps, self.asked = support_reply, list(steps), []

    def complete(self, messages, **options):
        self.asked.append({'brief': messages[-1]['content'], 'system': messages[0]['content'], **options})
        if options.get('stage') == 'experience_support': return {'result': self.reply}, {}
        return {'result': self.steps.pop(0) if self.steps else {'action': 'stuck', 'why': 'nothing more'}}, {}


class Still:
    out = Path('.')

    def do(self, command): return {'ok': True, 'path': '/', 'text': 'Home', 'controls': []}


def browsers(opened):
    @contextlib.contextmanager
    def browser_for(persona, goal):
        opened.append(goal['name'])
        yield Still()
    return browser_for


class SupportTests(unittest.TestCase):
    def test_an_answered_ticket_earns_one_more_try_that_reaches(self):
        assistant, opened = Scripted({'answer': '1. Open Shop  2. Press Add', 'escalate': False, 'why': 'it exists'},
                                     {'action': 'done'}), []
        desk = support.Desk(assistant, '/project', browsers(opened))
        again = desk(STUCK, PERSONA, GOAL)
        self.assertEqual((again['reached'], again['ticket'], opened), (True, 'T1', ['buyer.order']))
        asked = assistant.asked[0]
        self.assertEqual({k: asked.get(k) for k in ('stage', 'small', 'deep', 'reads', 'system')} | {'system': CLAUSE in asked['system']},
                         {'stage': 'experience_support', 'small': None, 'deep': None, 'reads': '/project', 'system': True})
        ticket = json.loads(asked['brief'])['ticket']
        self.assertEqual(ticket['trust'], UNTRUSTED, 'the ticket (the app\'s pages, the persona\'s words) is marked as data')
        self.assertIn('no basket anywhere', ticket['content']['asked'])
        told = json.loads(assistant.asked[1]['brief'])['support_told_you']
        self.assertEqual((told['trust'], told['content'][:12]), (UNTRUSTED, '1. Open Shop'))
        self.assertEqual((desk.tickets[0]['after'], desk.calls), ('reached', 2), 'its answer and the retry\'s step are counted')
        with tempfile.TemporaryDirectory() as tmp:
            saved = json.loads(desk.save(tmp).read_text())
        self.assertEqual((saved['version'], [t['id'] for t in saved['tickets']]), (1, ['T1']))

    def test_an_escalated_ticket_is_not_retried_and_a_goal_gets_one_ticket(self):
        assistant, opened = Scripted({'answer': None, 'escalate': True, 'why': 'there is no basket: a missing feature'}), []
        desk = support.Desk(assistant, '/project', browsers(opened))
        self.assertIsNone(desk(STUCK, PERSONA, GOAL))
        self.assertIsNone(desk(STUCK, PERSONA, GOAL))
        self.assertEqual((opened, len(desk.tickets), len(assistant.asked)), ([], 1, 1))
        self.assertEqual({k: desk.tickets[0][k] for k in ('escalated', 'answer', 'after')},
                         {'escalated': True, 'answer': None, 'after': 'stuck'})

    def test_the_friction_log_orders_by_kind_then_goal_and_step(self):
        journeys = [{'goal': 'b.two', 'persona': 'b', 'friction': [{'step': 3, 'kind': 'error', 'note': 'e'},
                                                                   {'step': 1, 'kind': 'find', 'note': 'f2'}]},
                    {'goal': 'a.one', 'persona': 'a', 'friction': [{'step': 2, 'kind': 'understand', 'note': 'u'},
                                                                   {'step': 4, 'kind': 'find', 'note': 'f1'}]}]
        self.assertEqual([r['note'] for r in support.friction_log(journeys)], ['f1', 'f2', 'u', 'e'])


if __name__ == '__main__':
    unittest.main()
