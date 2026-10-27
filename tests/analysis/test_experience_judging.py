"""The judging of the simulated users' difficulties (M10.7): a difficulty met again by a fresh actor and confirmed with
who it harms becomes a fact and a card with its steps to reproduce; one not met again, or confirmed without who it
harms, is at most a doubt; verdicts for unknown difficulties are ignored."""
import json
import tempfile
import unittest
from pathlib import Path

from eaos.analysis.assessments.debt_register import _layered
from eaos.analysis.claims.from_experience import experience, present
from eaos.analysis.repair.remediation import pattern_for
from eaos.core.language.words import FALSIFIERS, IMPACTS, TEMPLATES
from eaos.analysis.experience import judging
from eaos.facts.store import read_set

CART = {'action': 'click', 'target': {'role': 'link', 'name': 'Cart'}, 'value': None, 'at': '/', 'landed': '/cart', 'picture': 'step-1.jpg'}
PAY = {'action': 'click', 'target': {'role': 'button', 'name': 'Pay'}, 'value': None, 'at': '/cart', 'landed': '/cart',
       'picture': 'step-2.jpg', 'error': 'Server error'}
ORDER = {'version': 1, 'persona': 'buyer', 'role': 'user', 'goal': 'buyer.order', 'wanted': 'Order a book', 'start': '/',
         'reached': False, 'stuck': 'I cannot pay', 'stopped': None, 'steps': [CART, PAY],
         'friction': [{'step': 1, 'kind': 'find', 'note': 'the cart has no label'}, {'step': 1, 'kind': 'find', 'note': 'again'},
                      {'step': 2, 'kind': 'error', 'note': 'Server error'}]}
PROFILE = {'version': 1, 'persona': 'buyer', 'role': 'user', 'goal': 'buyer.profile', 'wanted': 'Save my profile', 'start': '/',
           'reached': True, 'steps': [dict(CART, landed='/profile')], 'friction': [{'step': 1, 'kind': 'understand', 'note': 'what is OK?'}]}
AGAIN = {'goal': 'buyer.order', 'reached': False, 'stuck': 'no checkout', 'steps': [CART], 'friction': [{'step': 1, 'kind': 'find', 'note': 'hidden cart'}]}


class Judge:
    """A fake deep judge: the verdicts it is given; it records what it was asked."""
    def __init__(self, verdicts): self.verdicts, self.asked = verdicts, []

    def complete(self, messages, small=False, stage=None, reads=None, deep=False):
        self.asked.append({'stage': stage, 'deep': deep, 'reads': reads, 'brief': json.loads(messages[1]['content'])})
        return {'result': {'verdicts': self.verdicts}}, {}


def verdict(id, kind='confirm', harmed='buyers who cannot find the cart, and leave'):
    return {'id': id, 'verdict': kind, 'why': 'step 1 shows an unlabelled icon', 'harmed': harmed, 'severity': 'high',
            'title': f'{id}: the cart is hard to find', 'title_ar': 'السلة صعبة الإيجاد', 'fix': 'Label the cart.', 'fix_ar': 'سمّ السلة.'}


def attempt(goal):
    if goal == 'admin.approve': raise RuntimeError('no browser')
    return {'reached': goal != 'buyer.order', 'same': None, 'journey': AGAIN if goal == 'buyer.order' else dict(PROFILE, friction=[])}


class JudgingTests(unittest.TestCase):
    def setUp(self):
        self.report = Path(self.enterContext(tempfile.TemporaryDirectory()))
        journeys = self.report / judging.JOURNEYS
        journeys.mkdir(parents=True)
        for name, journey in (('buyer--order', ORDER), ('buyer--profile', PROFILE)): (journeys / f'{name}.json').write_text(json.dumps(journey))
        (self.report / 'experience/run.json').write_text(json.dumps({'goals': [
            {'name': 'buyer.order', 'status': 'stuck'}, {'name': 'admin.approve', 'persona': 'admin', 'status': 'stuck', 'why': 'no list'}]}))
        (self.report / 'experience/tickets.json').write_text(json.dumps({'tickets': [{'goal': 'buyer.order', 'asked': 'Where is the cart?'}]}))

    def test_difficulties_are_merged_per_goal_kind_and_screen_with_their_steps_and_pictures(self):
        found = {(d['goal'], d['kind']): d for d in judging.difficulties(self.report)}
        self.assertEqual(list(found), [('buyer.order', 'find'), ('buyer.order', 'error'), ('buyer.order', 'stuck'),
                                       ('buyer.profile', 'understand'), ('admin.approve', 'stuck')])
        find = found[('buyer.order', 'find')]
        self.assertEqual((find['id'], find['screen'], find['steps'], find['note']), ('D1', '/', [1], 'the cart has no label'))
        self.assertEqual(find['pictures'], ['experience/journeys/buyer--order/step-1.jpg'])
        self.assertEqual(found[('buyer.order', 'error')]['screen'], '/cart')
        self.assertEqual(found[('buyer.order', 'stuck')]['repro'], ['As a user, open /', "Click 'Cart'", "Click 'Pay'", 'Met: I cannot pay'])

    def test_a_retry_after_support_points_at_its_own_pictures_and_the_judges_attempt_is_not_a_difficulty(self):
        journeys = self.report / judging.JOURNEYS
        retry = dict(PROFILE, goal='buyer.retry', attempt='again', pictures_dir='buyer--retry--again')
        (journeys / 'buyer--retry--again.json').write_text(json.dumps(retry))
        (journeys / 'buyer--retry.json').write_text(json.dumps(dict(PROFILE, goal='buyer.retry', pictures_dir='buyer--retry',
                                                                    friction=[{'step': 1, 'kind': 'find', 'note': 'first'}])))
        (journeys / 'buyer--order--second.json').write_text(json.dumps(dict(AGAIN, attempt='second', friction=[{'step': 1, 'kind': 'finish', 'note': 'x'}])))
        found = [(d['goal'], d['kind'], d['pictures']) for d in judging.difficulties(self.report)]
        self.assertIn(('buyer.retry', 'find', ['experience/journeys/buyer--retry/step-1.jpg']), found)
        self.assertIn(('buyer.retry', 'understand', ['experience/journeys/buyer--retry--again/step-1.jpg']), found)
        self.assertNotIn('finish', [kind for _, kind, _ in found])

    def test_only_a_difficulty_met_again_and_confirmed_with_who_it_harms_becomes_a_fact_and_a_card(self):
        rows = {r['id']: r['second'] for r in judging.confirm(self.report, attempt)}
        self.assertEqual([rows[i]['same'] for i in ('D1', 'D2', 'D3', 'D4', 'D5')], [True, False, True, False, False])
        judge = Judge([verdict('D1'), verdict('D2'), verdict('D3', harmed=None), verdict('D4', 'reject'), verdict('D9')])
        summary = judging.judge(self.report, judge)
        self.assertEqual(summary, {'confirm': 1, 'doubt': 3, 'reject': 1})
        self.assertEqual((judge.asked[0]['stage'], judge.asked[0]['deep'], judge.asked[0]['reads']), ('experience_judge', True, str(self.report)))
        self.assertEqual(judge.asked[0]['brief']['difficulties'][0]['asked'], ['Where is the cart?'])
        ruled = {d['id']: d for d in json.loads((self.report / judging.RECORD).read_text())['difficulties']}
        self.assertEqual([ruled[i]['verdict'] for i in ('D1', 'D2', 'D3', 'D4', 'D5')], ['confirm', 'doubt', 'doubt', 'reject', 'doubt'])
        self.assertIn('did not meet it again', ruled['D2']['why'])
        self.assertIn('no one named as harmed', ruled['D3']['why'])
        sets = {'experience': read_set(self.report, 'experience')}
        self.assertEqual([f['value']['id'] for f in sets['experience']['facts']], ['D1'])
        claims = []
        experience(sets, lambda *args, **extra: claims.append((args, extra)), None)
        (statement, kind, confidence, method, _), extra = claims[0]
        self.assertEqual((statement, kind, confidence, method), ('D1: the cart is hard to find', 'risk', 'LIKELY', ['model_inference']))
        self.assertIn("Steps to reproduce: 1. As a user, open / 2. Click 'Cart' 3. Met: the cart has no label", extra['impact']['scenario'])
        self.assertEqual(present(extra['probe_spec']['specification'], sets)[0], 'CONFIRMED')
        render = extra['render']
        self.assertEqual((render['key'], render['params']['severity']), ('experience_difficulty', 'high'),
                         'a difficulty is its own kind of card, not a layer finding')
        for words in (*TEMPLATES.values(), *IMPACTS.values(), *FALSIFIERS.values()): self.assertIn('experience_difficulty', words)
        self.assertEqual(_layered(render, 'architecture', 'low'), ('reliability', 'high'))
        self.assertEqual(pattern_for({'statement': statement, 'render': render})['change'], 'سمّ السلة.')

    def test_without_a_second_attempt_or_a_judge_nothing_is_confirmed(self):
        summary = judging.judge(self.report, Judge([verdict(f'D{n}') for n in range(1, 6)]))
        self.assertEqual(summary['confirm'], 0)
        self.assertEqual(judging.judge(self.report, None)['doubt'], 5)


if __name__ == '__main__':
    unittest.main()
