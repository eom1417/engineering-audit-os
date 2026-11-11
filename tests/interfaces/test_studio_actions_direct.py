"""The run engine (eaos/journeys/runs): direct runs with a fake assistant
(tests/fixtures/studio/actions/fake_assistant.py)."""
import json
import os
import unittest
from unittest import mock
from eaos.ai.assistant import headless as adapters
from eaos.core.project import runs as store
from tests.interfaces._studio_actions_fixture import Base


class Direct(Base):
    def fake_tools(self, answers):
        calls = []
        def tool(name):
            def call(**arguments):
                calls.append((name, arguments))
                answer = answers.get(name, {'ok': True})
                return json.dumps(answer(arguments) if callable(answer) else answer)
            return call
        return (lambda: {name: tool(name) for name in {a['id'] for a in store.contract()['actions']}}), calls

    def test_opening_the_report_is_work_it_waits_its_turn_and_stays_in_the_history_and_it_still_runs(self):
        self.app.manager.tools, calls = self.fake_tools({'open_report': {'report_for_people': 'REPORT.html',
                                                                         'opened_in_browser': False}})
        created = self.post('/api/runs', {'action': 'open_report', 'inputs': {'show': False}})[1]['run']
        self.assertNotIn('answer', created.get('result') or {}, 'not answered at once, as a reading action is')
        self.assertEqual(self.app.wait(created['id'], ('done', 'failed'), 20)['state'], 'done')
        self.assertEqual([name for name, _ in calls], ['open_report'])
        self.assertIn(created['id'], [run['id'] for run in self.get('/api/runs')[1]['runs']])

    def test_a_reading_action_answers_at_once_and_a_job_is_followed_with_its_progress(self):
        from eaos.core.project import jobs
        self.app.manager.tools, calls = self.fake_tools({'status': {'next': 'audit'},
                                                         'audit': {'job': 'audit-1', 'status': 'running'}})
        applied = {'branch': 'main', 'waves': [{'status': 'applied', 'branch': 'eaos/main/wave-1', 'kept': ['TASK-1']}]}
        with mock.patch('eaos.core.project.state.load',
                        return_value=applied):     # a batch handed over earlier is not this read's
            status, payload = self.post('/api/runs', {'action': 'status'})
        self.assertEqual((status, payload['run']['state'], payload['run']['result']['answer']),
                         (200, 'done', {'next': 'audit'}))
        self.assertEqual((payload['run']['result']['branch'], payload['run']['result']['cards_closed']), (None, []))
        self.assertEqual(calls, [('status', {'project': str(self.project.resolve())})])
        self.assertEqual(self.get('/api/runs')[1]['runs'], [], 'a reading action stays out of the history')
        self.assertEqual(len(self.get('/api/runs?all=1')[1]['runs']), 1)
        self.assertEqual(self.post('/api/runs', {'action': 'findings', 'inputs': {'limit': 'many'}})[0], 400)
        state = {'n': 0}
        def read(job, project):
            state['n'] += 1
            if state['n'] < 3: return {'id': job, 'kind': 'audit', 'status': 'running',
                                       'progress': {'done': state['n'], 'total': 3, 'stage': 'engines'}}
            return {'id': job, 'kind': 'audit', 'status': 'done', 'result': {'overview': 'fine'}}
        with mock.patch.object(jobs, 'read', side_effect=read), mock.patch('eaos.core.project.state.load',
                                                                           return_value=applied):
            run = self.post('/api/runs', {'action': 'audit'})[1]['run']['id']
            done = self.app.wait(run, ('done', 'failed'), 20)
        self.assertEqual(done['state'], 'done')
        self.assertIsNone(done['result']['branch'],
                          'a check run while a batch waits does not hand that batch over again')
        self.assertEqual([e['data']['done'] for e in self.app.store.events(run) if e['kind'] == 'progress'], [1, 2])

    def test_a_step_that_needs_consent_asks_in_the_inbox_and_only_an_explicit_yes_gives_it(self):
        os.environ['FAKE_MODE'] = 'fail'
        self.app.manager.tools, calls = self.fake_tools({'run_setup': lambda a: {'status': 'done'}
                                                         if a.get('person_agreed')
                                                         else {'status': 'needs_agreement',
                                                               'ask_the_person': 'May EAOS run your app?'}})
        run = self.post('/api/runs', {'action': 'run_setup'})[1]['run']['id']
        question = self.app.wait(run, ('waiting_for_person',), 5)['question']
        self.assertEqual(question['why'], 'run consent')
        path = f"/api/questions/{question['id']}/answer"
        self.assertEqual(self.post(path, {'text': 'Explain first'})[0], 200)
        record = self.app.wait(run, ('waiting_for_person',), 5)
        self.assertEqual((record['question']['why'], record['answered'][0]['text']), ('run consent', 'Explain first'),
                         'a clarification that failed keeps the question')
        self.assertIn('error', self.kinds(run))
        os.environ.update(FAKE_MODE='slow', FAKE_SECONDS='0.2')
        question = record['question']
        path = f"/api/questions/{question['id']}/answer"
        text = '  Yes is a word, but explain first.\nAn unrelated request.  '
        for body in ({'option': 'yes', 'text': text}, {'option': ['yes']}, {'text': '   '}, {'text': 'x' * 4001}):
            self.assertEqual(self.post(path, body)[0], 400, body)
        self.assertEqual(self.post(path, {'text': text})[0], 200)
        self.assertEqual(self.post(path, {'text': text})[0], 200)
        record = self.app.wait(run, ('waiting_for_person',), 5)
        self.assertEqual(record['mode'], 'direct')
        self.assertNotEqual(record['question']['id'], question['id'])
        self.assertEqual((record['answered'][-1]['text'], record['question']['why']), (text, 'run consent'))
        self.assertFalse(any(args.get('person_agreed') for _, args in calls), 'words are never consent')
        reread = self.make().store.load(run)
        self.assertEqual(reread['answered'][-1]['text'], text)
        self.assertEqual(reread['question']['options'], question['options'])
        self.assertEqual(self.post(f"/api/questions/{reread['question']['id']}/answer", {'option': 'yes'})[0], 200)
        self.assertEqual(self.app.wait(run, ('done', 'failed'), 5)['state'], 'done')
        self.assertTrue(calls[-1][1]['person_agreed'])

    def test_the_branch_a_check_or_an_assistant_needs_is_asked_in_the_studio_and_the_choice_is_applied(self):
        chosen, manager = [], self.app.manager
        manager._choose_branch = lambda branch, said: chosen.append((branch, said))
        asked = {'status': 'needs_branch',
                 'branches': [{'name': 'main', 'main': True}, {'name': 'work', 'ahead_of_main': 3}],
                 'recommended': 'work'}
        manager.tools, calls = self.fake_tools({'audit': lambda arguments: asked if not chosen
                                                else {'status': 'started', 'checked': True}})
        run = self.post('/api/runs', {'action': 'audit'})[1]['run']['id']
        question = self.app.wait(run, ('waiting_for_person', 'done'), 5)['question']
        self.assertEqual((question['why'], question['recommendation'], [o['id'] for o in question['options']]),
                         ('branch', 'work', ['main', 'work']))
        self.assertEqual(self.post(f"/api/questions/{question['id']}/answer", {'option': 'main'})[0], 200)
        self.assertEqual(self.app.wait(run, ('done', 'failed'), 5)['state'], 'done')
        self.assertEqual(chosen, [('main', 'main (main)')])
        self.assertEqual([name for name, _ in calls], ['audit', 'audit'], 'the check runs again on the chosen branch')
        chosen.clear()
        run = self.start('explain')
        self.app.wait(run, ('waiting_for_person', 'done', 'failed'), 30)
        manager._launch = lambda *args: None
        asked = {'status': 'needs_branch', 'recommended': 'develop',
                 'branches': [{'name': 'main', 'main': True}, {'name': 'develop', 'ahead_of_main': 9}]}
        manager._end_turn(run, {'eaos_results': [('status', asked)], 'texts': ['EAOS needs the branch first.']}, 0)
        question = self.app.store.load(run)['question']
        self.assertEqual((question['why'], question['recommendation']), ('branch', 'develop'))
        self.assertEqual(self.post(f"/api/questions/{question['id']}/answer", {'option': 'develop'})[0], 200)
        self.assertEqual([branch for branch, _ in chosen], ['develop'],
                         'answered in the Studio, the choice reaches EAOS')

    def test_accept_and_undo_need_their_confirmation_and_the_newest_waiting_branch(self):
        self.app.manager.tools, calls = self.fake_tools({'accept': {'status': 'accepted', 'branch': 'eaos/wave-1'},
                                                         'undo': {'status': 'nothing_to_undo'}})
        for run, branch in (('r-fix', 'eaos/wave-1'), ('r-two', 'eaos/wave-2'), ('r-three', 'eaos/wave-3')):
            self.app.store.save({'id': run, 'action': 'fix', 'verb': 'fix', 'mode': 'assistant', 'state': 'done',
                                 'label': {'en': 'x', 'ar': 'x'},
                                 'created': '0', 'result': {'branch': branch}}, new=True)
        self.app.manager.newest_waiting = lambda: 'eaos/wave-1'
        self.assertEqual(self.post('/api/runs/r-fix/accept', {})[0], 403)
        wrong = self.post('/api/actions/undo/preview')[1]['confirm']['token']
        self.assertEqual(self.post('/api/runs/r-fix/accept', {'confirm': wrong})[0], 403)
        token = self.post('/api/actions/accept/preview')[1]['confirm']['token']
        status, payload = self.post('/api/runs/r-fix/accept', {'confirm': token})
        self.assertEqual(status, 200, payload)
        self.assertEqual(calls, [('accept', {'person_agreed': True, 'project': str(self.project.resolve())})])
        self.assertEqual(self.app.store.load('r-fix')['outcome'], 'accepted')
        self.assertEqual(self.post('/api/runs/r-fix/accept', {'confirm': token})[0], 403)
        undo = lambda run: self.post(f'/api/runs/{run}/undo',
                                     {'confirm': self.post('/api/actions/undo/preview')[1]['confirm']['token']})
        self.app.manager.newest_waiting = lambda: 'eaos/wave-3'
        self.assertEqual(undo('r-fix')[0], 409, 'accepted work is not undone here')
        self.assertEqual(undo('r-two')[0], 409, "another run's branch")
        self.app.manager.newest_waiting = lambda: None
        self.assertEqual(undo('r-three')[0], 409)
        self.assertEqual(len(calls), 1)
        self.app.manager.newest_waiting = lambda: 'eaos/wave-3'
        status, payload = undo('r-three')
        self.assertEqual(status, 200, payload)
        self.assertNotIn('outcome', self.app.store.load('r-three'))
        self.assertEqual(self.kinds('r-three')[-1], 'error')


    def test_a_branch_decided_outside_the_studio_waits_no_more(self):
        """When EAOS merges a batch outside a run, its question does not stay waiting: accept answers "not waiting
        any more". Whether a branch waits is read from EAOS's state, the one truth."""
        self.app.store.save({'id': 'r-fix', 'action': 'fix', 'verb': 'fix', 'mode': 'assistant', 'state': 'done',
                             'label': {'en': 'x', 'ar': 'x'},
                             'created': '0', 'result': {'branch': 'eaos/develop/wave-10'}}, new=True)
        listed = lambda waves: mock.patch('eaos.core.project.state.load', return_value={'waves': waves})
        with listed([{'number': 10, 'status': 'applied', 'branch': 'eaos/develop/wave-10'}]):
            self.assertIsNone(self.get('/api/runs')[1]['runs'][0].get('outcome'), 'handed over, it waits')
        with listed([{'number': 10, 'status': 'accepted', 'branch': 'eaos/develop/wave-10'},
                     {'number': 11, 'status': 'accepted', 'branch': 'eaos/develop/wave-10'}]):
            self.assertEqual(self.get('/api/runs')[1]['runs'][0]['outcome'], 'accepted')
        with listed([{'number': 10, 'status': 'undone', 'branch': 'eaos/develop/wave-10'}]):
            self.assertEqual(self.get('/api/runs')[1]['runs'][0]['outcome'], 'undone')

    def test_a_fix_accepts_its_own_batch_only_when_the_person_chose_it_in_its_preview(self):
        """"Accept automatically when the checks pass" is the person's choice in that Fix preview, for that run only;
        without it, or into a protected branch, or with nothing kept, the branch waits for the person."""
        selection = {'kind': 'cards', 'cards': ['TASK-001']}
        preview = lambda auto: self.post('/api/actions/fix/preview',
                                         {'verb': 'fix', 'selection': selection, 'inputs': {'auto_accept': auto}})[1]
        self.assertTrue(preview(True)['auto_accept'])
        for shown, sent in ((True, False), (False, True)):          # the token carries the choice the person saw
            status, payload = self.post('/api/runs',
                                        {'action': 'fix', 'verb': 'fix', 'selection': selection,
                                         'inputs': {'auto_accept': sent},
                                         'confirm': preview(shown)['confirm']['token']})
            self.assertEqual((status, payload.get('needs')), (403, 'confirm'), payload)
        self.assertEqual(self.app.store.all(), [])
        self.app.manager.tools, calls = self.fake_tools({'accept': {'status': 'accepted', 'branch': 'eaos/wave-1'}})
        self.app.manager.newest_waiting = lambda: 'eaos/wave-1'
        self.app.branches.policy = lambda: {'protected': {'main': {'en': 'main', 'ar': 'main', 'code': 'main_name'}}}
        def end(run, auto, target='dev', kept=('TASK-001',)):
            self.app.store.save({'id': run, 'action': 'fix', 'verb': 'fix', 'mode': 'assistant', 'state': 'running',
                                 'label': {'en': 'x', 'ar': 'x'},
                                 'created': '0', 'cards': ['TASK-001'], 'where': {'merge_into': target},
                                 **({'auto_accept': True} if auto else {})}, new=True)
            with mock.patch.object(self.app.manager, '_outcome',
                                   return_value={'branch': 'eaos/wave-1', 'cards_closed': list(kept),
                                                 'target': target}):
                self.app.manager._end_turn(run, {'eaos_results': [], 'final': 'done'}, 0)
            return self.app.store.load(run)
        for run, auto, target, kept in (('r-not-chosen', False, 'dev', ('TASK-001',)),
                                        ('r-protected', True, 'main', ('TASK-001',))):
            self.assertNotIn('outcome', end(run, auto, target, kept), run)
        self.assertEqual(calls, [], 'nothing is accepted that the person did not choose, nor into a protected branch')
        self.assertEqual(end('r-chosen', True)['outcome'], 'accepted')
        self.assertEqual(calls, [('accept', {'person_agreed': True, 'project': str(self.project.resolve())})])
        self.assertTrue(next(e for e in reversed(self.app.store.events('r-chosen'))
                             if e['kind'] == 'result')['data']['auto_accept'])

    def test_closing_words_mostly_not_in_arabic_are_asked_once_again_and_kept_and_said_when_still_not(self):
        # under --lang ar a closing summary that is mostly English is asked for once again; one Arabic word must not let
        # it through
        self.app.store.save({'id': 'r-lang', 'action': 'fix', 'verb': 'fix', 'mode': 'assistant', 'state': 'running',
                             'assistant': 'claude',
                             'label': {'en': 'x', 'ar': 'x'}, 'created': '0'}, new=True)
        words = ('تم. Fixed the AddUser dialog: split it into two components and moved the shared fields '
                 'into `FormFields.tsx`.')
        arabic = 'تم: قسّمت نافذة إضافة المستخدم إلى مكوّنين ونقلت الحقول المشتركة إلى `FormFields.tsx`.'
        with mock.patch.object(adapters, 'ask', return_value={'answer': {'text': arabic}}):
            self.assertEqual(self.app.manager._readable('r-lang', words), arabic)
            self.assertEqual(self.app.manager._readable('r-lang', arabic), arabic)
        with mock.patch.object(adapters, 'ask', return_value={'answer': {'text': words}}) as asked:
            self.assertEqual(self.app.manager._readable('r-lang', words), words)
        self.assertEqual(asked.call_count, 1, 'asked once, never again')
        said = [e for e in self.app.store.events('r-lang') if e['kind'] == 'check']
        self.assertEqual([(e['data']['name'], e['data']['passed']) for e in said], [('language', False)])


if __name__ == '__main__':
    unittest.main()
