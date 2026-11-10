"""The run engine (eaos/journeys/runs): the decisions a report carries and the headless assistant."""
import json
import os
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock
from eaos.interfaces import runs as actions  # noqa: E402
from eaos.ai.assistant import prompts
from eaos.journeys.runs import runs
from eaos.core.project import runs as store
from tests.interfaces._studio_actions_fixture import Base


class ReportDecisions(Base):
    """A decision the report asks, answered by the person: saved once, handed to the assistant as context, never as
    consent."""

    def setUp(self):
        super().setUp()
        self.question = {'id': 'ideal-choice', 'question': 'Which design?',
                         'options': [{'id': 'a', 'label': 'Keep it'}, {'id': 'b', 'label': 'Replace it'}],
                         'blocks': ['TASK-001'], 'asked': '2026-10-09', 'tool': 'replan_ideal', 'state': 'waiting'}
        self.write_question()

    def write_question(self):
        (self.studio / 'decisions.json').write_text(json.dumps({'decisions': [self.question]}))

    def answer_report(self, option='a', text=None, app=None):
        _, payload = self.get('/api/decisions', app)
        return self.post('/api/decisions/ideal-choice/answer',
                         {'scope': payload['decisions'][0]['scope'], 'option': option, 'text': text}, app)

    def response(self, app=None):
        return self.get('/api/decisions', app)[1]['decisions'][0]['response']

    def test_an_answer_queues_one_run_with_its_exact_input_once_across_threads_restarts_and_languages(self):
        self.question['revision'] = 'source-question-v1'
        self.write_question()
        results = []
        threads = [threading.Thread(target=lambda: results.append(self.answer_report())) for _ in range(5)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertTrue(all(status == 200 for status, _ in results), results)
        self.assertEqual(len({p['decision']['response']['run'] for _, p in results}), 1)
        row = results[0][1]['decision']
        self.assertEqual(row['response']['label'], 'Keep it')
        run = row['response']['run']
        prompt = self.app.manager.prompt_of(self.app.store.load(run))
        for needle in ('Which design?', 'Keep it', 'TASK-001', 'not merge'): self.assertIn(needle, prompt)
        self.assertEqual(self.answer_report()[1]['decision']['response']['run'], run)
        self.assertEqual(len(self.app.store.all()), 1)
        self.assertEqual(self.response(self.make())['run'], run, 'a restarted server reads the same answer')
        self.assertEqual(self.question, json.loads((self.studio / 'decisions.json').read_text())['decisions'][0],
                         'the report is not rewritten')
        self.question['question'] = 'أي تصميم؟'
        self.question['options'][0]['label'] = 'احتفظ به'
        self.write_question()
        self.assertEqual(self.response()['run'], run, 'the same revision in another language is the same question')

    def test_later_plans_and_fixes_receive_the_saved_answer_as_context_only(self):
        self.answer_report(None, '  Preserve this exact planning choice.  ')
        for verb in ('plan', 'fix'):
            prompt = self.app.manager.prompt_of(self.app.store.load(self.start(verb)))
            self.assertIn('Which design?', prompt)
            self.assertIn('  Preserve this exact planning choice.  ', prompt)
            self.assertIn('context only, never authorization', prompt)

    def test_a_wrong_answer_is_refused_and_a_custom_one_kept_exactly_for_this_project_and_question_only(self):
        self.app.close()
        app = self.make(adapters_={})
        for option, text in (('missing', None), (None, '   '), (None, 'x' * 4001), ('a', 'arbitrary')):
            self.assertEqual(self.answer_report(option, text, app)[0], 400, (option, text))
        self.assertEqual(self.post('/api/decisions/ideal-choice/answer', {'scope': 'wrong', 'option': 'a'}, app)[0],
                         409)
        self.assertEqual(app.handle('POST', '/api/decisions/ideal-choice/answer',
                                    self.headers(app, **{'X-EAOS-CSRF': 'bad'}), {})[0], 403)
        self.assertEqual(app.handle('GET', '/api/decisions', self.headers(app, **{'X-EAOS-Token': 'bad'}))[0], 401)
        text = '  Something entirely different\nPlease explain first.  '
        row = self.answer_report(None, text, app)[1]['decision']
        self.assertEqual(row['response']['text'], text)
        saved = app.store.load(row['response']['run'])
        self.assertIn(text, saved['owner_decision']['answer']['text'])
        self.assertNotIn('person_agreed', saved['inputs'])
        # a review of the person's answer must not follow `status` into running the app, nor ask the person to edit
        # permission files when a tool is refused
        prompt = app.manager.prompt_of(saved)
        self.assertIn('start nothing', prompt)
        self.assertIn('never ask the person to change permissions', prompt)
        self.assertEqual(app.wait(row['response']['run'], ['waiting_for_person'], timeout=4)['mode'], 'handoff',
                         'no assistant: handed over')
        self.assertEqual(self.answer_report('b', None, app)[0], 409, 'already answered')
        other_project = self.base / 'another-project'
        other_project.mkdir()
        other = actions.Actions(other_project, port=8765, studio=self.studio, adapters={})
        self.apps.append(other)
        self.assertIsNone(self.response(other))
        self.write_question()
        self.assertEqual(self.response(app)['run'], row['response']['run'], 'a refreshed report keeps the answer')
        self.question['question'] = 'A different question with the same id?'
        self.write_question()
        self.assertIsNone(self.response(app), 'a new question does not inherit')

    def test_a_failed_run_is_retried_with_the_same_choice_and_never_edits(self):
        os.environ['FAKE_MODE'] = 'fail'
        run = self.answer_report()[1]['decision']['response']['run']
        self.assertEqual(self.app.wait(run, ['failed'], 5)['state'], 'failed')
        os.environ.update(FAKE_MODE='slow', FAKE_SECONDS='0.2')
        self.assertEqual(self.post(f'/api/runs/{run}/retry')[0], 200)
        self.assertEqual(self.app.wait(run, ['done'], 5)['state'], 'done')
        self.assertEqual(self.response()['option'], 'a')
        self.assertEqual(len(self.app.store.all()), 1)
        argv = [json.loads(line) for line in (self.base / 'argv.jsonl').read_text().splitlines()
                if '--allowedTools' in json.loads(line)]
        self.assertTrue(all('mcp__eaos__fix_edit' not in call[call.index('--allowedTools') + 1:
                                                              call.index('--disallowedTools')] for call in argv))


class Headless(unittest.TestCase):
    """Outside the run engine (eaos/interfaces/govern.py): a command queues without starting anything, one host
    starts the runs."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        patcher = mock.patch.dict(os.environ,
                                  {'EAOS_HOME': str(base / 'home'), 'EAOS_OUTPUT': str(base / 'out'),
                                   'EAOS_HOST_IDLE': '1'})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.project = base / 'p'
        self.project.mkdir()
        (self.project / 'package.json').write_text('{}')
        for argv in (['init', '-q'], ['add', '-A'],
                     ['-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'first']):
            subprocess.run(['git', '-C', str(self.project), *argv], check=True, capture_output=True)
        from eaos.interfaces import govern
        self.govern = govern
        govern._core.cache_clear()
        self.addCleanup(govern._core.cache_clear)

    def test_a_command_never_holds_the_dispatch_lock_and_what_it_queues_a_host_finishes_then_leaves(self):
        core = self.govern.core(str(self.project))
        self.addCleanup(core.close)
        self.assertEqual(self.govern.estimate(self.project, {'fresh': True})['estimate']['minutes_high'], 30,
                         'before a first check: the rough rule')
        run = core.create({'action': 'note', 'inputs': {'text': 'from the terminal'}})['id']
        self.assertFalse(self.govern._held(core.store.folder / 'dispatch.lock'),
                         'a command never starts a run it would not live to follow')
        self.assertEqual(core.store.load(run)['state'], 'queued')
        self.assertTrue(self.govern.wake(self.project))
        self.assertEqual(core.wait(run, store.TERMINAL, 60)['state'], 'done', 'no Studio runs: the host started it')
        end = time.monotonic() + 30
        while self.govern._held(core.store.folder / 'host.lock') and time.monotonic() < end: time.sleep(0.2)
        self.assertFalse(self.govern._held(core.store.folder / 'host.lock'),
                         'the host leaves once nothing is queued or active')

    def test_a_host_never_leaves_while_work_is_in_hand_however_late_it_wakes(self):
        asked = []
        def busy(_):
            asked.append(True)
            return len(asked) < 4
        real = time.sleep
        with mock.patch.object(self.govern, '_busy', busy), mock.patch.object(self.govern.time, 'sleep',
                                                                              lambda _: real(0.05)):
            self.govern.host(str(self.project),
                             idle=0.01)      # each sleep outlasts the idle time, as on a loaded computer
        self.assertEqual(len(asked), 4, 'it left with work in hand: the run stays running for ever')

    def test_an_answer_given_in_the_terminal_is_told_as_given_there_never_as_the_studios(self):
        question = {'options': [{'id': 'yes', 'label': {'en': 'Yes, run it', 'ar': 'نعم'}},
                                {'id': 'no', 'label': {'en': 'No', 'ar': 'لا'}}]}
        self.assertIn('answered in the Studio: Yes, run it', prompts.answer(question, 'yes', None, 'en'))
        self.assertIn('answered in the terminal: Yes, run it',
                      prompts.answer(question, 'yes', None, 'en', via='terminal'))
        with mock.patch.object(runs.Manager, 'answer') as answered:
            self.govern.host(str(self.project), ('r1-q1', 'yes', None), idle=0)
        answered.assert_called_once_with('r1-q1', 'yes', None, via='terminal')
        core = self.govern.core(str(self.project))
        self.addCleanup(core.close)
        run = core.create({'action': 'run_setup', 'inputs': {}})['id']
        core.store.update(run, state='waiting_for_person', mode='direct',
                          question={'id': f'{run}-q1', 'run': run, 'why': 'run consent', **question})
        core.manager.answer(f'{run}-q1', 'no',
                            via='terminal')                    # "no": the run ends here, nothing starts
        said = next(e for e in core.store.events(run) if e['kind'] == 'answer')
        self.assertEqual((said['text']['en'], said['text']['ar'], said['data']['via']),
                         ('You answered in the terminal: No', 'جاوبت في الطرفية: لا', 'terminal'))

    def test_a_verb_with_no_card_refuses_and_says_how_to_choose(self):
        import argparse
        import contextlib
        import io
        from eaos.interfaces.terminal import commands
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            code = commands.act(argparse.Namespace(command='fix', project=str(self.project), ids=[], group=None,
                                                   lang='en', yes=True,
                                                   assistant=None, auto_accept=False))
        self.assertEqual(code, 3)
        self.assertIn('eaos problems --fixable', printed.getvalue(),
                      'a fix of nothing named: it says how to choose the cards')

    def test_where_studios_are_services_the_queue_host_is_one_too(self):
        # the queue host is a service too, so the runner does not end it with the session that queued a run
        from eaos.core.system import launch
        with mock.patch.object(launch, 'durable', return_value=True), mock.patch.object(launch, 'as_unit',
                                                                                        return_value=True) as unit, \
                mock.patch.object(launch, 'detach') as detached:
            self.assertTrue(self.govern.wake(self.project))
        self.assertTrue(unit.call_args.args[0].startswith('eaos-govern-'))
        detached.assert_not_called()

    def test_looking_at_the_runs_wakes_the_host_only_when_a_run_is_queued(self):
        import argparse
        import contextlib
        import io
        from eaos.interfaces.terminal import commands
        core = self.govern.core(str(self.project))
        self.addCleanup(core.close)
        asked = lambda: commands.runs(argparse.Namespace(command='runs', project=str(self.project), all=False,
                                                         lang='en'))
        with mock.patch.object(self.govern, 'wake') as woken, contextlib.redirect_stdout(io.StringIO()):
            asked()
            woken.assert_not_called()
            core.create({'action': 'note', 'inputs': {'text': 'queued from a session that ended'}})
            asked()
        woken.assert_called_once()

    def test_time_left_is_paced_from_the_first_card_and_said_from_the_third(self):
        # a fix's first card comes after the app's setup, so the time left is paced from that card
        from datetime import datetime, timedelta, timezone
        core = self.govern.core(str(self.project))
        self.addCleanup(core.close)
        now = datetime.now(timezone.utc)
        record = {'id': 'r1', 'state': 'running', 'started': (now - timedelta(minutes=20)).isoformat()}
        def tried(done, before):
            return {'kind': 'progress', 'at': (now - timedelta(minutes=before)).isoformat(),
                    'data': {'stage': 'cards', 'done': done, 'total': 10}}
        for events, left in (([tried(1, 4), tried(2, 2), tried(3, 0)], 14), ([tried(1, 4), tried(2, 0)], None)):
            with mock.patch.object(core.store, 'events', return_value=events):
                self.assertEqual(self.govern.progress(core, record)['minutes_left'], left)


if __name__ == '__main__':
    unittest.main()
