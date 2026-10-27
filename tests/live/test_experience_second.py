"""The second attempt (M10.7): a fresh actor runs the same goal on a fresh browser, told nothing of the first attempt;
it says whether it met the same difficulty again (stuck again, or the same kind of friction on the same screen)."""
import json
import unittest
from pathlib import Path

from eaos.live.experience.second import met, second_attempt

PERSONA = {'id': 'buyer', 'role': 'user', 'name': 'Sara', 'about': 'a first-time buyer'}
GOAL = {'name': 'buyer.order', 'goal': 'Order a book', 'start': '/', 'done_when': 'the page says Ordered',
        'first_attempt': 'stuck on /cart: no checkout button'}       # never shown to the fresh actor
CLICK = {'action': 'click', 'target': {'role': 'button', 'name': 'Cart', 'nth': 0},
         'friction': {'kind': 'find', 'note': 'the checkout is hidden'}}


class Pages:
    """A fresh browser: home, then the cart."""
    out = Path('.')

    def __init__(self): self.commands = []

    def do(self, command):
        self.commands.append(command)
        return {'ok': True, 'path': '/' if command.get('op') == 'open' else '/cart', 'text': 'Shop', 'controls': []}


class Scripted:
    def __init__(self, *steps): self.steps, self.asked = list(steps), []

    def complete(self, messages, **options):
        self.asked.append(json.dumps(messages))
        return {'result': self.steps.pop(0)}, {}


class SecondAttemptTests(unittest.TestCase):
    def test_a_fresh_actor_not_told_the_first_attempt_meets_the_same_friction_again(self):
        assistant = Scripted(CLICK, {'action': 'stuck', 'why': 'no checkout'})
        result = second_attempt(Pages(), PERSONA, GOAL, assistant, {'kind': 'find', 'screen': '/'})
        self.assertEqual((result['reached'], result['same']), (False, True))
        self.assertTrue(all('first_attempt' not in asked and 'no checkout button' not in asked for asked in assistant.asked))
        stuck = second_attempt(Pages(), PERSONA, GOAL, Scripted({'action': 'stuck', 'why': 'lost'}), {'kind': 'stuck', 'screen': '/'})
        self.assertTrue(stuck['same'])

    def test_a_goal_reached_without_the_difficulty_did_not_meet_it(self):
        result = second_attempt(Pages(), PERSONA, GOAL, Scripted({'action': 'done'}), {'kind': 'find', 'screen': '/'})
        self.assertEqual((result['reached'], result['same']), (True, False))
        result = second_attempt(Pages(), PERSONA, GOAL, Scripted({'action': 'done'}), {'kind': 'stuck', 'screen': '/'})
        self.assertFalse(result['same'])

    def test_a_journey_a_budget_or_the_assistant_ended_did_not_give_up_again(self):
        for ended in ('assistant', 'time', 'calls'):
            journey = {'reached': False, 'stopped': ended, 'stuck': f'the {ended} budget ran out', 'steps': []}
            self.assertFalse(met(journey, {'kind': 'stuck', 'screen': '/'}), ended)
        self.assertTrue(met({'reached': False, 'stopped': None, 'stuck': 'lost', 'steps': []}, {'kind': 'stuck', 'screen': '/'}))

    def test_the_second_attempt_types_the_goals_own_values(self):
        assistant = Scripted({'action': 'done'})
        second_attempt(Pages(), PERSONA, GOAL, assistant, values={'Email': 'sara@example.com'})
        self.assertIn('sara@example.com', assistant.asked[0])


if __name__ == '__main__':
    unittest.main()
