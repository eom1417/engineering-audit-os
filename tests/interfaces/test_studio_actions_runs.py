"""The run engine (eaos/journeys/runs): runs end to end with a fake assistant
(tests/fixtures/studio/actions/fake_assistant.py)."""
import json
import os
import time
import unittest
from pathlib import Path
from unittest import mock
from eaos.ai.assistant import headless as adapters, prompts
from eaos.journeys.runs import resume
from eaos.core.project import runs as store
from eaos.core.project import state as project_state
from tests.interfaces._studio_actions_fixture import Base, alive, until


class Runs(Base):
    def test_a_question_waits_in_the_inbox_and_the_answer_resumes_the_session(self):
        run = self.start('explain')
        self.assertEqual(self.app.wait(run, ('waiting_for_person', 'failed'), 30)['state'], 'waiting_for_person')
        question = self.get('/api/questions')[1]['questions'][0]
        self.assertEqual((question['run'], question['recommendation'], question['text']['ar']), (run, 'yes', 'أكمل؟'))
        self.assertEqual(self.post(f"/api/questions/{question['id']}/answer", {'option': 'maybe'})[0], 400)
        self.assertEqual(self.post(f"/api/questions/{question['id']}/answer", {'option': 'yes'})[0], 200)
        self.assertEqual(self.post(f"/api/questions/{question['id']}/answer", {'option': 'yes'})[0], 200)
        self.assertEqual(self.post(f"/api/questions/{question['id']}/answer", {'option': 'no'})[0], 409)
        done = self.app.wait(run, ('done', 'failed'), 30)
        self.assertEqual(done['state'], 'done', self.app.store.events(run))
        self.assertEqual(done['result']['answer'], 'All done.')
        argvs = [json.loads(line) for line in Path(os.environ['FAKE_ARGV']).read_text().splitlines() if '-p' in line]
        self.assertEqual(argvs[-1][-2:], ['--resume', 'fake-session'])
        self.assertIn('option "yes"', argvs[-1][argvs[-1].index('-p') + 1])
        starts = [e['text']['en'] for e in self.app.store.events(run) if e['kind'] == 'step'
                  and e['data'].get('assistant')]
        self.assertEqual(starts, ['Claude Code started', 'Claude Code went on'])
        edits = [e for e in self.app.store.events(run) if e['kind'] == 'edit']
        self.assertIn('+x = 2', edits[0]['data']['diff'])
        self.assertIn('check', self.kinds(run))
        self.assertEqual(self.app.store.verify(run), [])

    def test_an_answer_in_the_persons_own_words_is_their_answer_and_the_session_goes_on_from_it(self):
        # an answer in the person's own words is not taken for a clarification: the same question must not come back
        # until they pick one of its options
        run = self.start('explain')
        self.assertEqual(self.app.wait(run, ('waiting_for_person', 'failed'), 30)['state'], 'waiting_for_person')
        question = self.get('/api/questions')[1]['questions'][0]
        said = 'Only the screens of the pharmacy, and leave the reports for later'
        self.assertEqual(self.post(f"/api/questions/{question['id']}/answer", {'text': said})[0], 200)
        done = self.app.wait(run, ('done', 'failed', 'waiting_for_person'), 30)
        self.assertEqual(done['state'], 'done', 'never asked the same question again')
        argvs = [json.loads(line) for line in Path(os.environ['FAKE_ARGV']).read_text().splitlines() if '-p' in line]
        self.assertEqual(argvs[-1][-2:], ['--resume', 'fake-session'], 'its own session goes on')
        resumed = argvs[-1][argvs[-1].index('-p') + 1]
        self.assertIn(said, resumed)
        self.assertIn('This is their answer', resumed)

    def test_an_answer_that_closes_the_stuck_batch_closes_it_and_a_direct_step_runs_while_a_question_waits(self):
        """Answering "yes, close the batch" closes it through fix_abandon, and fix_abandon pressed from the palette is
        not queued behind the run that waits for that same answer."""
        calls = []
        def tool(name):
            def call(**arguments):
                calls.append(name)
                return json.dumps({'status': 'abandoned'} if name == 'fix_abandon' else {'ok': True})
            return call
        self.app.manager.tools = lambda: {a['id']: tool(a['id']) for a in store.contract()['actions']}
        run = self.start('explain')
        self.assertEqual(self.app.wait(run, ('waiting_for_person', 'failed'), 30)['state'], 'waiting_for_person')
        direct = self.post('/api/runs', {'action': 'audit'})[1]['run']['id']
        self.assertEqual(self.app.wait(direct, ('done', 'failed'), 10)['state'], 'done',
                         'a direct step is not blocked by a waiting question')
        asked = prompts.question_in('```eaos-question\n{"text": "Close the stuck batch?", "options": '
                                    '[{"id": "close", "label": "Yes", "action": "fix_abandon"}, '
                                    '{"id": "keep", "label": "No", "action": "accept"}]}\n```')
        self.assertEqual([o.get('action') for o in asked['options']], ['fix_abandon', None],
                         'only the allowed action is kept')
        record = self.app.store.load(run)
        self.app.store.update(run, question={**record['question'], 'options': asked['options']})
        self.assertEqual(self.post(f"/api/questions/{record['question']['id']}/answer", {'option': 'close'})[0], 200)
        self.assertEqual(self.app.wait(run, ('done', 'failed'), 30)['state'], 'done')
        self.assertEqual(calls, ['audit', 'fix_abandon'])
        argvs = [json.loads(line) for line in Path(os.environ['FAKE_ARGV']).read_text().splitlines() if '-p' in line]
        self.assertIn('already ran fix_abandon', argvs[-1][argvs[-1].index('-p') + 1])

    def test_a_fix_run_that_kept_nothing_says_so_and_its_progress_is_its_batch(self):
        """A fix run that fixed nothing does not end as done, and its bar does not show status's count of cards."""
        self.assertEqual(adapters.result_events('status', {}, {'progress': {'done': 0, 'total': 898}}), [])
        run = self.start('fix', cards=('TASK-001', 'TASK-002'))
        question = self.app.wait(run, ('waiting_for_person', 'failed'), 30)['question']
        self.assertEqual(self.post(f"/api/questions/{question['id']}/answer", {'option': 'yes'})[0], 200)
        ended = self.app.wait(run, ('done', 'failed', 'unchanged'), 30)
        # neither done nor failed: nothing reached the project, nothing broke, and it may be tried again
        self.assertEqual((ended['state'], ended['result']['nothing_changed']), ('unchanged', True),
                         self.app.store.events(run))
        self.assertEqual(self.post(f'/api/runs/{run}/retry')[1]['run']['state'], 'queued')
        events = self.app.store.events(run)
        self.assertEqual([(e['data']['done'], e['data']['total']) for e in events if e['kind'] == 'progress'], [(1, 2)])
        self.assertTrue(next(e for e in events if e['kind'] == 'result')['data']['nothing_changed'])
        self.assertNotIn('تم', ' '.join(e['text']['ar'] for e in events if e['kind'] == 'result'))

    def test_a_fix_run_whose_assistant_stopped_goes_on_by_itself_and_counts_on_from_the_cards_already_tried(self):
        """When an assistant's sign-in expires partway through a batch the run stops as "failed", and after Retry its
        bar counts the cards already done."""
        os.environ['FAKE_MODE'] = 'crash_once'
        wave = {'open_wave': {'number': 1, 'cards': ['TASK-001', 'TASK-002'], 'kept': {'TASK-001': 'abc'},
                              'failed': {}}}
        with mock.patch('eaos.core.project.state.load', return_value=wave):
            run = self.start('fix', cards=('TASK-001', 'TASK-002'))
            self.app.wait(run, ('done', 'failed'), 30)
        events = self.app.store.events(run)
        launches = [line for line in Path(os.environ['FAKE_ARGV']).read_text().splitlines()
                    if '"--allowedTools"' in line]
        self.assertEqual(len(launches), 2, 'it went on by itself once its assistant crashed')
        self.assertIn('stopped before the end', json.loads(launches[1])[json.loads(launches[1]).index('-p') + 1][:300])
        self.assertEqual([e['data'].get('resume') for e in events if e['kind'] == 'step' and e['data'].get('resume')],
                         [1])
        self.assertEqual({(e['data']['done'], e['data']['total']) for e in events if e['kind'] == 'progress'}, {(1, 2)})
        self.assertNotIn('something broke',
                         ' '.join(str(e['data'].get('reason')) for e in events if e['kind'] == 'error'))

    def test_a_fix_in_speed_mode_starts_an_assistant_per_lane_beside_its_own_and_gets_back_what_one_left(self):
        from eaos.journeys import agent_tools, guided
        from eaos.journeys.runs import lane_assistants as helpers
        state = agent_tools.state_of(str(self.project))
        state['open_wave'] = {'number': 1, 'cards': ['TASK-001', 'TASK-002', 'TASK-004'], 'kept': {}, 'failed': {},
                              'lanes': [['TASK-001'], ['TASK-002'], ['TASK-004']], 'claims': {}, 'helpers': {},
                              'later': [], 'released': []}
        guided.save(state)
        # no dispatcher saying a run without its process stopped
        manager = self.make(dispatch=False).manager
        manager.store.save({'id': 'rfirst', 'verb': 'fix', 'action': 'fix', 'label': {'en': 'Fix', 'ar': 'أصلح'},
                            'assistant': 'claude',
                            'cards': ['TASK-001', 'TASK-002', 'TASK-004'],
                            'cards_detail': [{'id': 'TASK-002', 'title': 'Problem TASK-002'}],
                            'mode': 'assistant', 'state': 'running', 'created': store.now()}, new=True)
        answered = {'eaos_results': [('wait', {'batch': 1, 'helpers': [['TASK-002'], ['TASK-004']]})]}
        with mock.patch.object(manager, '_start') as started:
            helpers.after(manager, 'rfirst', answered)
            helpers.after(manager, 'rfirst',
                          {'eaos_results': answered['eaos_results']})     # another turn reading it: once
        self.assertEqual(sorted(call.args[0] for call in started.call_args_list), ['rfirst-1', 'rfirst-2'])
        second = manager.store.load('rfirst-1')
        self.assertEqual((second['lane'], second['parent'], second['cards'], second['state']),
                         (1, 'rfirst', ['TASK-002'], 'running'))
        prompt = manager.prompt_of(second)
        self.assertIn('one of several assistants', prompt)
        self.assertNotIn('fix_start with', prompt, 'it never opens a batch of its own')
        self.assertEqual(project_state.load(self.project)['open_wave']['helpers'], {'rfirst-1': 1, 'rfirst-2': 2})
        manager.set_state('rfirst-1', 'failed', 'its assistant stopped for good')
        self.assertEqual(project_state.load(self.project)['open_wave']['later'], ['TASK-002'],
                         'its card goes to the first assistant')
        manager.set_state('rfirst', 'stopped', 'you stopped it')
        self.assertEqual(manager.store.load('rfirst-2')['state'], 'stopped', 'stopping the first one stops the others')

    def test_a_run_goes_on_with_another_signed_in_assistant_when_its_own_hit_its_limit(self):
        ready = lambda adapter: adapter != 'signed-out'
        three = {'claude': 'claude', 'codex': 'codex', 'third': 'signed-out'}
        self.assertEqual(resume.next_assistant(three, 'claude', 'limit', ready), 'codex', 'another one first')
        self.assertEqual(resume.next_assistant(three, 'claude', 'failed', ready), 'claude',
                         'a crash: the same one again')
        self.assertIsNone(resume.next_assistant({'claude': 'signed-out'}, 'claude', 'not_signed_in', ready))

    def test_a_run_waiting_for_an_answer_lets_the_next_start_and_its_answer_goes_on_when_the_slot_is_free(self):
        """A run that waits on "build it?" does not keep the next run queued."""
        waiting = self.start('explain')
        self.assertEqual(self.app.wait(waiting, ('waiting_for_person', 'failed'), 30)['state'], 'waiting_for_person')
        os.environ.update(FAKE_MODE='slow', FAKE_SECONDS='2')
        second, third = (self.start('explain', cards=(c,)) for c in ('TASK-002', 'TASK-004'))
        self.assertEqual(self.app.wait(second, ('running', 'done'), 10)['state'], 'running',
                         'the waiting run holds no slot')
        question = self.app.store.load(waiting)['question']
        self.assertEqual(self.post(f"/api/questions/{question['id']}/answer", {'option': 'yes'})[0], 200)
        kept = self.app.store.load(waiting)
        self.assertEqual((kept['state'], bool(kept['answer_waiting'])), ('waiting_for_person', True),
                         'never two runs at once')
        self.assertEqual(self.app.wait(waiting, ('running', 'done', 'failed'), 20)['state'], 'running')
        self.assertEqual(self.app.store.load(second)['state'], 'done')
        self.assertEqual(self.app.store.load(third)['state'], 'queued', 'the answered run goes on before the queue')
        self.assertEqual(self.app.wait(waiting, ('done', 'failed'), 20)['state'], 'done')
        self.assertEqual(self.app.wait(third, ('done', 'failed'), 20)['state'], 'done')

    def test_one_run_at_a_time_and_the_queue_is_reordered(self):
        os.environ.update(FAKE_MODE='slow', FAKE_SECONDS='2')
        first, second, third = (self.start('explain', cards=(c,)) for c in ('TASK-001', 'TASK-002', 'TASK-004'))
        self.assertEqual(self.app.wait(first, ('running',), 10)['state'], 'running')
        self.assertEqual(self.get('/api/runs')[1]['queue'], [second, third])
        self.assertEqual(self.post('/api/runs/reorder', {'order': [third]})[1]['queue'], [third, second])
        self.assertEqual(self.post('/api/runs/reorder', {'order': [first]})[0], 409)
        self.assertEqual(self.get(f'/api/runs/{third}')[1]['run']['position'], 1)
        self.assertEqual(self.app.wait(first, ('done',), 20)['state'], 'done')
        self.assertIn(self.app.wait(third, ('running', 'done'), 20)['state'], ('running', 'done'))
        self.assertEqual(self.get(f'/api/runs/{second}')[1]['run']['state'], 'queued')

    def test_pause_resume_stop_and_retry(self):
        os.environ.update(FAKE_MODE='slow', FAKE_SECONDS='6')
        run = self.start('explain')
        running = self.app.wait(run, ('running',), 10)
        until(lambda: self.app.store.load(run).get('pid')
              and any(e['kind'] != 'state' for e in self.app.store.events(run)), 10)  # it has written
        self.assertEqual(self.post(f'/api/runs/{run}/pause')[1]['run']['state'], 'paused')
        time.sleep(0.5)                             # what the assistant wrote before it was paused is still read
        count = len(self.app.store.events(run))
        time.sleep(0.8)
        self.assertEqual(len(self.app.store.events(run)), count)
        resumed = self.post(f'/api/runs/{run}/resume')[1]['run']
        # the run's clocks must not count through a pause: the pause is kept as a span they leave out
        self.assertEqual((resumed['state'], len(resumed['paused']), resumed.get('paused_at')), ('running', 1, None))
        self.assertEqual(self.post(f'/api/runs/{run}/stop')[1]['run']['state'], 'stopped')
        pid = self.app.store.load(run).get('pid') or running.get('pid')
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and pid and alive(pid): time.sleep(0.2)
        self.assertFalse(pid and alive(pid))
        self.assertEqual(self.post(f'/api/runs/{run}/stop')[0], 409)
        os.environ['FAKE_MODE'] = 'question'
        self.app.store.update(run, usage={'cost_usd': 0.2})        # what Actions.usage keeps of an ended run
        self.assertEqual(self.post(f'/api/runs/{run}/retry')[1]['run']['state'], 'queued')
        self.assertIsNone(self.app.store.load(run).get('usage'), "a run tried again is counted again, every turn of it")
        again = self.app.wait(run, ('waiting_for_person', 'failed'), 30)
        self.assertEqual((again['state'], again['attempt']), ('waiting_for_person', 2))
        self.assertEqual(self.app.store.verify(run), [])

    def test_a_run_ends_with_its_result_or_its_reason_and_its_events_replay(self):
        for mode, words in (('fail', 'the model is not available'), ('crash', 'code 3')):
            os.environ['FAKE_MODE'] = mode
            run = self.start('explain')
            self.assertEqual(self.app.wait(run, ('failed', 'done'), 30)['state'], 'failed')
            errors = [e for e in self.app.store.events(run) if e['kind'] == 'error']
            self.assertIn(words, errors[-1]['data']['reason'])
        os.environ['FAKE_MODE'] = 'replay'
        run = self.start('explain')
        done = self.app.wait(run, ('done', 'failed'), 30)
        self.assertEqual(done['state'], 'done', self.app.store.events(run)[-3:])
        self.assertIn('eaos/wave-1', done['result']['answer'])
        self.assertLessEqual({'step', 'read', 'check', 'say', 'result'}, set(self.kinds(run)))
        ids = [event['seq'] for event in self.app.store.events(run)]
        self.assertEqual(ids, list(range(1, len(ids) + 1)))
        status, payload = self.get(f'/api/runs/{run}/events?after={ids[-2]}')
        self.assertEqual([e['seq'] for e in payload['events']], [ids[-1]])

    def test_two_servers_never_start_the_same_run(self):
        deadline = time.monotonic() + 5
        while self.app.manager._lockfile is None and time.monotonic() < deadline: time.sleep(0.05)
        other = self.make()
        self.assertFalse(other.manager._hold())
        run = self.start('explain', app=other)
        self.assertEqual(self.app.wait(run, ('waiting_for_person', 'failed'), 30)['state'], 'waiting_for_person')
        time.sleep(1)
        launches = [line for line in Path(os.environ['FAKE_ARGV']).read_text().splitlines()
                    if '"--allowedTools"' in line]
        self.assertEqual(len(launches), 1)
        self.assertNotIn(run, other.manager.watched)

    def test_a_restart_follows_a_live_assistant_and_fails_a_dead_one_plainly(self):
        os.environ.update(FAKE_MODE='slow', FAKE_SECONDS='3')
        live = self.start('explain')
        self.app.wait(live, ('running',), 10)
        until(lambda: self.app.store.load(live).get('pid')
              and any(e['kind'] != 'state' for e in self.app.store.events(live)), 10)
        self.app.close()
        self.app.manager.children.clear()
        dead = 'r-dead'
        self.app.store.save({'id': dead, 'action': 'explain', 'verb': 'explain', 'mode': 'assistant',
                             'assistant': 'claude', 'state': 'running',
                             'pid': 999999, 'label': {'en': 'x', 'ar': 'x'}, 'created': '0'}, new=True)
        again = self.make()
        self.assertEqual(again.wait(dead, ('failed',), 10)['state'], 'failed')
        self.assertIn('server', again.store.events(dead)[-2]['text']['en'])
        finished = again.wait(live, ('done', 'failed'), 20)
        self.assertEqual(finished['state'], 'done', again.store.events(live)[-3:])
        self.assertEqual(finished['result']['answer'], 'finished slowly')


if __name__ == '__main__':
    unittest.main()
