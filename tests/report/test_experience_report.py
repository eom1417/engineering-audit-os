"""The experience report (M10.8): one story from the records, told in EXPERIENCE.md in both languages and by the MCP tool."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.report.experience.document import write
from eaos.report.experience.story import story, summary


def _put(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body), encoding='utf-8')


def _journey(persona, goal, reached, steps):
    return {'version': 1, 'persona': persona, 'goal': f'{persona}.{goal}', 'wanted': f'{goal} done', 'reached': reached,
            'stuck': None if reached else 'no button to pay', 'steps': steps, 'friction': [] if reached else
            [{'step': 2, 'kind': 'find', 'note': 'the pay button is hidden'}], 'seconds': 30.5, 'calls': 4}


def _records(report):
    folder = report / 'experience'
    _put(folder / 'scenario.json', {'version': 1, 'personas': [{'id': 'buyer', 'role': 'visitor', 'name': 'Sara', 'goals': []},
                                                               {'id': 'admin', 'role': 'admin', 'name': 'Omar', 'goals': []}]})
    step = {'action': 'click', 'target': {'role': 'button', 'name': 'Cart'}, 'value': None, 'why': 'to see the cart',
            'landed': '/cart', 'picture': 'step-1.jpg'}
    _put(folder / 'journeys/buyer--order.json', _journey('buyer', 'order', False, [step]))
    _put(folder / 'journeys/admin--approve.json', _journey('admin', 'approve', True, [{**step, 'picture': ''}]))
    _put(folder / 'run.json', {'version': 1, 'goals': [{'name': 'admin.approve', 'persona': 'admin', 'status': 'reached', 'seconds': 12, 'calls': 3},
                                                       {'name': 'buyer.order', 'persona': 'buyer', 'status': 'stuck', 'seconds': 40, 'calls': 6}],
                               'seconds': 52, 'calls': 9})
    _put(folder / 'replays.json', {'version': 1, 'replays': [{'goal': 'admin.approve', 'status': 'red', 'error': 'the button moved'}],
                                   'summary': {'green': 0, 'red': 1, 'skipped': 1}})
    _put(folder / 'tickets.json', {'version': 1, 'tickets': [{'id': 'T1', 'goal': 'buyer.order', 'persona': 'buyer', 'asked': 'how do I pay?',
                                                              'answer': 'from the cart', 'escalated': False, 'after': 'stuck'}]})
    base = {'goal': 'buyer.order', 'persona': 'buyer', 'kind': 'find', 'note': 'n', 'why': 'w', 'title': 'Pay is hidden', 'title_ar': 'الدفع مخفي'}
    _put(folder / 'difficulties.json', {'version': 1, 'difficulties': [
        {**base, 'id': 'D1', 'verdict': 'doubt', 'severity': 'high'},
        {**base, 'id': 'D2', 'verdict': 'confirm', 'severity': 'low'},
        {**base, 'id': 'D3', 'verdict': 'confirm', 'severity': 'high', 'pictures': ['experience/journeys/buyer--order/step-1.jpg'],
         'repro': ['open the cart'], 'fix': 'show the pay button', 'fix_ar': 'أظهر زر الدفع'},
        {**base, 'id': 'D4', 'verdict': 'reject', 'severity': 'high'}]})


class ExperienceReport(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.report = Path(tmp.name)
        _records(self.report)

    def test_the_story_ranks_the_difficulties_and_times_each_task(self):
        told = story(self.report)
        self.assertEqual([d['id'] for d in told['difficulties']['ranked']], ['D3', 'D2', 'D1'])
        self.assertEqual([d['id'] for d in told['difficulties']['rejected']], ['D4'])
        self.assertEqual([(t['name'], t['status'], t['seconds']) for t in told['time']], [('admin.approve', 'reached', 12), ('buyer.order', 'stuck', 40)])
        buyer = told['personas'][0]
        self.assertEqual((buyer['name'], buyer['goals'][0]['why'], buyer['goals'][0]['steps'][0]['target']), ('Sara', 'no button to pay', 'Cart'))
        self.assertEqual(buyer['goals'][0]['steps'][0]['picture'], 'experience/journeys/buyer--order/step-1.jpg')
        self.assertIsNone(told['personas'][1]['goals'][0]['steps'][0]['picture'])
        self.assertEqual((told['replays']['summary']['red'], told['missing']), (1, ['data.json']))

    def test_a_confirmed_difficulty_carries_its_fix_card_once_the_plan_made_it(self):
        # story.json had no card, so the Studio's experience part never linked a difficulty to its fix (M10.10)
        self.assertIsNone(story(self.report)['difficulties']['ranked'][0]['card'])
        _put(self.report / 'facts/experience.json', {'facts': [{'id': 'F-9', 'kind': 'experience_difficulty', 'value': {'id': 'D3'}}]})
        _put(self.report / 'plan.json', {'tasks': [{'id': 'TASK-001', 'evidence': {'fact_ids': ['F-1']}},
                                                   {'id': 'TASK-007', 'evidence': {'fact_ids': ['F-9']}}]})
        ranked = story(self.report)['difficulties']['ranked']
        self.assertEqual([(d['id'], d['card']) for d in ranked], [('D3', 'TASK-007'), ('D2', None), ('D1', None)])
        self.assertIn('Its fix card: `TASK-007`', write(self.report, 'en')[0].read_text(encoding='utf-8'))

    def test_a_retry_after_support_is_the_goals_journey_with_its_own_pictures(self):
        folder = self.report / 'experience/journeys'
        step = {'action': 'click', 'target': {'name': 'Pay'}, 'landed': '/paid', 'picture': 'step-1.jpg'}
        _put(folder / 'buyer--order--again.json', {**_journey('buyer', 'order', True, [step]), 'attempt': 'again',
                                                   'pictures_dir': 'buyer--order--again'})
        _put(folder / 'buyer--order--second.json', {**_journey('buyer', 'order', False, []), 'attempt': 'second'})
        goal = story(self.report)['personas'][0]['goals'][0]
        self.assertEqual((goal['wanted'], goal['steps'][0]['target']), ('order done', 'Pay'))
        self.assertEqual(goal['steps'][0]['picture'], 'experience/journeys/buyer--order--again/step-1.jpg')

    def test_both_languages_are_written_with_relative_pictures_and_the_missing_said(self):
        page, data = write(self.report, 'en')
        english = page.read_text(encoding='utf-8')
        self.assertIn('![Step 1](experience/journeys/buyer--order/step-1.jpg)', english)
        self.assertLess(english.index('D3: Pay is hidden'), english.index('D2: Pay is hidden'))
        self.assertIn('T1 (buyer.order)', english)
        self.assertIn('experience/data.json', english)
        self.assertEqual(json.loads(data.read_text(encoding='utf-8'))['seconds'], 52)
        arabic = write(self.report, 'ar')[0].read_text(encoding='utf-8')
        self.assertIn('الدفع مخفي', arabic)
        self.assertIn('أظهر زر الدفع', arabic)
        self.assertIn('سجلات ناقصة', arabic)

    def test_a_report_without_an_experience_run_says_so(self):
        with tempfile.TemporaryDirectory() as empty:
            told = story(empty)
            self.assertFalse(told['ran'])
            self.assertIn('journeys/', told['missing'])
            self.assertIn('was not tried', write(empty, 'en')[0].read_text(encoding='utf-8'))

    def test_the_summary_counts_the_steps_and_keeps_the_ranking(self):
        told = summary(story(self.report))
        self.assertEqual(told['personas'][0]['goals'][0]['steps'], 1)
        self.assertEqual(told['difficulties']['ranked'][0]['id'], 'D3')


    def test_the_mcp_tool_answers_the_summary(self):
        from eaos.interfaces.mcp_server.server import build
        from eaos.journeys import guided
        with mock.patch.object(guided, 'report_of', return_value=self.report), \
             mock.patch('eaos.journeys.agent_tools.state_of', return_value={}), \
             mock.patch.dict('os.environ', {'EAOS_HOME': str(self.report / 'home')}):
            answer = asyncio.run(build().call_tool('experience', {'project': str(self.report)}))
        self.assertEqual(json.loads(answer.content[0].text)['difficulties']['ranked'][0]['id'], 'D3')

if __name__ == '__main__':
    unittest.main()
