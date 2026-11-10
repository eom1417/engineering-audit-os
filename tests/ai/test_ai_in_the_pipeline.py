"""The person's assistant inside the check (docs/AI-IN-THE-PIPELINE.md): asked about once, passed to the check so the
cards are triaged and the plan ordered right after the check, invented citations dropped, and the rules standing alone
without an assistant or on a failure."""
import json
import os
import subprocess
import tempfile
import sys
import unittest
from pathlib import Path
from unittest import mock

from eaos.journeys import agent_tools, guided
from eaos.pipeline.runners import by_rules as runners
from eaos.pipeline.run import Context
from eaos.pipeline.stage_run import _one
from eaos.pipeline.stages import BY_NAME
from eaos.core.progress.log import _small
from eaos.ai.nodes import framework as core
from ai.test_ai_nodes import Answer, _nodes_report, decision
from eaos.core.project import state as project_state


def answers(name, schema):
    """The fake assistant of the triage and the order: one verdict per card, one with an invented citation, and an order
    that keeps the prerequisite of TASK-003."""
    if 'plan' in str(schema):
        steps = [{'id': 's1', 'title': 'Dead code first', 'tasks': ['TASK-001', 'TASK-002'], 'why': 'small and safe'},
                 {'id': 's2', 'title': 'Then', 'tasks': ['TASK-003'], 'why': 'needs TASK-001'}]
        return {'summary': '', 'decisions': [decision('plan', 'reorder', ['TASK-001', 'TASK-003'], detail={'steps': steps})]}
    return {'summary': '', 'decisions': [decision('TASK-001', 'confirm', ['TASK-001', 'FACT-0001'], detail={'falsifier': 'a caller', 'harmed': 'the app users'}),
                                         decision('TASK-002', 'reject', ['TASK-002'], detail={'falsifier': 'no caller'}),
                                         decision('TASK-003', 'doubt', ['FACT-invented'], detail={'falsifier': '?'})]}

class TriageAndOrderStages(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.report, _ = _nodes_report(Path(self.tmp.name))
        self.context = Context(target=Path(self.tmp.name), out=self.report, provider=object(), language='en')

    def stage(self, name, launcher):
        with mock.patch.object(core, 'pick', return_value=object()), mock.patch.object(core, 'AdapterLauncher', return_value=launcher):
            return _one(BY_NAME[name], self.context, runners.RUNNERS, {})

    def read(self, path):
        return json.loads((self.report / path).read_text(encoding='utf-8'))

    def test_the_triage_judges_every_card_the_order_reads_it_and_without_an_assistant_the_check_goes_on(self):
        failing = Answer(lambda name, schema: {'decisions': 'not a list'})
        for name in ('triage', 'order'):
            self.assertEqual(self.stage(name, failing)['reason_code'], 'ai_failed')
            row = _one(BY_NAME[name], Context(self.context, provider=None), runners.RUNNERS, {})
            self.assertEqual((row['status'], row['reason_code']), ('unavailable', 'no_provider'))
        row = self.stage('triage', Answer(answers))
        self.assertEqual(row['status'], 'ok')
        self.assertEqual(_small(row['detail']), row['detail'], 'the live map shows all the stage reported')
        self.assertEqual({k: row['detail'][k] for k in ('confirm', 'reject', 'rules only', 'dropped', 'calls', 'model')},
                         {'confirm': 1, 'reject': 1, 'rules only': 1, 'dropped': 1, 'calls': 1, 'model': 'test-model'})
        self.assertEqual(self.read('nodes/card_triage/library-feedback.json')['rejected'][0]['card'], 'TASK-002')
        plan = (self.report / 'plan.json').read_bytes()
        self.stage('triage', Answer(answers))
        launcher = Answer(answers)
        row = self.stage('order', launcher)
        self.assertEqual((row['status'], row['detail']['decision'], row['detail']['calls']), ('ok', 'reorder', 2))
        self.assertIn('"triage": "reject"', launcher.calls[0][1])
        order = self.read('nodes/plan_orderer/order.json')
        self.assertEqual(([s['tasks'] for s in order['steps']], order['set_aside']), ([['TASK-001', 'TASK-002'], ['TASK-003']], ['TASK-002']))
        self.assertEqual((self.report / 'plan.json').read_bytes(), plan)
        (self.report / 'plan.json').write_text('{}', encoding='utf-8')
        self.assertEqual(self.stage('order', Answer(answers))['reason_code'], 'not_applicable')

class Consent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        home = mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(self.tmp.name) / 'home'), 'EAOS_ASSISTANT': 'claude'})
        home.start(); self.addCleanup(home.stop)
        installed = mock.patch('eaos.ai.shutil.which', return_value='/bin/claude')
        installed.start(); self.addCleanup(installed.stop)
        self.project = Path(self.tmp.name) / 'shop'
        self.project.mkdir()
        subprocess.run(['git', 'init', '-q', '-b', 'main'], cwd=self.project, check=True)
        (self.project / 'package.json').write_text('{}', encoding='utf-8')
        subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'one', '--allow-empty'], cwd=self.project,
                       check=True)

    def probe(self, ready, code=None):
        row = {'id': 'claude', 'name': 'Claude Code', 'ready': ready, 'installed': True, 'code': code or 'claude_ready',
               'reason': {'en': 'Claude Code is not signed in. Run `claude` once', 'ar': 'غير مسجّل'}}
        return mock.patch('eaos.ai.assistant.readiness.probe', return_value=row)

    def test_the_persons_yes_reaches_the_check_from_eaos_start_and_from_the_mcp_audit(self):
        state = {'lang': 'en', 'project': str(self.project), 'workspace': str(Path(self.tmp.name) / 'ws'), 'questions': []}
        with mock.patch.object(sys.stdin, 'isatty', return_value=False), self.assertRaises(guided.NeedsAnswer):
            guided.agree_to_assistant(state, yes=False)
        with self.probe(True):
            self.assertEqual(guided.check_provider(state).config['assistant'], 'claude', 'on unless the person says no')
        with self.probe(True):
            self.assertTrue(guided.agree_to_assistant(state, yes=True))
            provider = guided.check_provider(state)
        self.assertIn('claude_adapter', provider.identity()['argv'][-1])
        self.assertEqual(provider.config['assistant'], 'claude')
        state['questions'][-1]['answer'] = False
        self.assertEqual(guided.check_provider(state).code, 'ai_declined')
        with mock.patch.object(agent_tools.checking, '_start', return_value={'status': 'started'}), self.probe(True):
            agent_tools.audit(str(self.project), use_assistant=True)
        with mock.patch('eaos.journeys.check.check', side_effect=RuntimeError('stop here')) as check, self.assertRaises(RuntimeError), \
                mock.patch.object(guided, 'tools_for_check', return_value={}), self.probe(True):
            agent_tools._audit_job(str(self.project), {}, None)
        self.assertTrue(check.call_args.kwargs['provider'])
        with mock.patch.object(agent_tools.checking, '_start', return_value={'status': 'started'}):
            agent_tools.audit(str(self.project), use_assistant=False)
        self.assertEqual(guided.check_provider(project_state.load(self.project)).code, 'ai_declined')

    def test_the_views_and_the_sign_in_read_the_code_themselves_and_every_other_call_is_as_it_was(self):
        # The assistant of the views and the sign-in sees excerpts only, with every tool off.
        from eaos.ai.assistant import claude_adapter, codex_adapter
        seen = []
        with mock.patch.object(claude_adapter, 'stream', side_effect=lambda argv, text, env: seen.append((argv, env)) or {'result': '{}'}):
            claude_adapter.call([{'role': 'user', 'content': 'hi'}])
            claude_adapter.call([{'role': 'user', 'content': 'hi'}], reads='/copy', deep=True)
        (plain, plain_env), (reading, reading_env) = seen
        self.assertEqual(plain[plain.index('--tools') + 1], '', 'a call as before: no tool')
        self.assertIsNone(plain_env)
        self.assertEqual(reading[reading.index('--tools'):reading.index('--tools') + 6],
                         ['--tools', 'Read,Grep,Glob', '--add-dir', '/copy', '--permission-mode', 'dontAsk'])
        self.assertEqual(reading_env['MAX_THINKING_TOKENS'], '31999')
        with mock.patch.object(codex_adapter.subprocess, 'run', return_value=mock.Mock(returncode=1)) as run, self.assertRaises(RuntimeError):
            codex_adapter.call([{'role': 'user', 'content': 'hi'}], reads='/copy', deep=True)
        argv = run.call_args.args[0]
        self.assertEqual((argv[argv.index('-C') + 1], argv[argv.index('-s') + 1]), ('/copy', 'read-only'))
        self.assertIn('model_reasoning_effort="high"', argv)

    def test_an_answer_with_braces_in_its_prose_is_read_and_a_failed_adapter_says_its_own_reason(self):
        # A reply with prose and braces after the object is still read, and a failed adapter step says its own reason,
        # not only that the adapter exited unsuccessfully; the use of the assistant is recorded.
        from eaos.ai.assistant import claude_adapter
        from eaos.ai.assistant.command import Provider
        reply = 'Here is the answer:\n{"users": [{"role": "admin"}]}\nEach row has a {role} field, as {asked}.'
        self.assertEqual(claude_adapter.parse(reply), {'users': [{'role': 'admin'}]})
        quoted = 'package.json says {"name": "app", "scripts": {"test": "jest"}}; my answer: {"ok": true}'
        self.assertEqual(claude_adapter.parse(quoted), {'ok': True}, 'the review of M10: never a larger object it quoted')
        failing = ('import sys; sys.stdin.read(); sys.stderr.write(\'{"type": "stream_event", "secret": "raw"}\\n\'); '
                   'sys.stderr.write("claude adapter: the model returned no JSON object\\n"); sys.exit(1)')
        with self.assertRaises(ValueError) as failed:
            Provider({'argv': [sys.executable, '-c', failing]}).complete([{'role': 'user', 'content': 'hi'}])
        self.assertIn('the model returned no JSON object', str(failed.exception))
        self.assertNotIn('raw', str(failed.exception), 'never the rest of its stderr')

    def test_the_choice_is_kept_per_project_and_one_not_ready_is_never_used_silently(self):
        state = {'lang': 'en', 'project': str(self.project), 'workspace': str(guided.workspace(self.project)), 'questions': []}
        guided.choose_assistant(state, True, 'codex', via='studio')
        kept = project_state.load(self.project)
        self.assertEqual((kept['assistant'], guided.answered(kept, 'use_assistant')), ('codex', True))
        with mock.patch('eaos.ai.shutil.which', return_value='/bin/x'):
            self.assertEqual(guided.chosen_assistant(kept), 'codex', 'the project\'s choice wins over $EAOS_ASSISTANT')
        guided.choose_assistant(kept, False)
        kept = project_state.load(self.project)
        self.assertEqual((kept['assistant'], guided.answered(kept, 'use_assistant')), ('codex', False))
        self.assertEqual([q['id'] for q in kept['questions']].count('use_assistant'), 1)
        with self.assertRaises(ValueError): guided.choose_assistant(kept, True, 'gemini')
        state = {'lang': 'en', 'project': str(self.project), 'workspace': str(Path(self.tmp.name) / 'ws'), 'questions': []}
        guided.choose_assistant(state, True, 'claude')
        with self.probe(False, 'claude_not_signed_in'):
            found = guided.check_provider(state)
            self.assertFalse(found)
            self.assertEqual(found.code, 'claude_not_signed_in')
            with mock.patch.object(sys.stdin, 'isatty', return_value=True), mock.patch('builtins.input', return_value='no'), \
                    mock.patch.object(guided.checking, 'say') as said, mock.patch.object(guided.checking, 'box') as box:
                self.assertFalse(guided.agree_to_assistant(state, yes=False))
            self.assertIn('Run `claude` once', said.call_args_list[0].args[0])
            self.assertIn('did not start', box.call_args.args[1])
            with mock.patch.object(guided.checking, 'say'):
                self.assertTrue(guided.agree_to_assistant(state, yes=True), '--yes: the check starts without AI, and says why')

    def test_the_mcp_audit_never_starts_with_an_assistant_that_is_not_ready_but_may_go_without_ai(self):
        with mock.patch.object(agent_tools.checking, '_start', return_value={'status': 'started'}) as start, self.probe(False, 'claude_sign_in_expired'):
            self.assertEqual(agent_tools.audit(str(self.project))['status'], 'assistant_not_ready', 'on by default, so never silently off')
            start.assert_not_called()
            self.assertEqual(agent_tools.audit(str(self.project), without_ai=True)['status'], 'started')
        self.assertEqual(start.call_args.args[2], {'without_ai': True})
        self.assertIsNone(guided.answered(project_state.load(self.project), 'use_assistant'), 'one check without AI changes no choice')
        with mock.patch('eaos.journeys.check.check', side_effect=RuntimeError('stop here')) as check, self.assertRaises(RuntimeError), \
                mock.patch.object(guided, 'tools_for_check', return_value={}):
            agent_tools._audit_job(str(self.project), {'without_ai': True}, None)
        self.assertEqual(check.call_args.kwargs['provider'].code, 'ai_skipped')
        from eaos.ai.assistant.readiness import words
        self.assertTrue(words('ai_skipped'))
        with mock.patch.object(agent_tools.checking, '_start', return_value={'status': 'started'}) as start, self.probe(False, 'claude_not_signed_in'):
            answer = agent_tools.audit(str(self.project), use_assistant=True, assistant='claude')
        start.assert_not_called()
        self.assertEqual((answer['status'], answer['assistant']['code']), ('assistant_not_ready', 'claude_not_signed_in'))
        self.assertIn('Run `claude` once', answer['what_now'])
        self.assertIn('use_assistant=false', answer['what_now'])
        with mock.patch.object(agent_tools.checking, '_start', return_value={'status': 'started'}) as start, self.probe(False, 'claude_not_signed_in'):
            self.assertEqual(agent_tools.audit(str(self.project), use_assistant=False)['status'], 'started')

    def test_the_studio_the_assistant_check_and_the_doctor_show_each_assistant_and_ask_instead_of_saying_done(self):
        from eaos.ai.assistant import prompts
        question = prompts.assistant_question({'status': 'assistant_not_ready', 'assistant': {
            'name': 'Claude Code', 'code': 'claude_sign_in_expired', 'reason': {'en': 'Sign in again.', 'ar': 'سجّل دخولك من جديد.'}}})
        self.assertEqual((question['why'], [o['id'] for o in question['options']], question['recommendation']),
                         ('assistant', ['retry', 'without_ai'], 'retry'))
        self.assertIn('سجّل دخولك من جديد', question['text']['ar'])
        rows = [{'id': 'claude', 'ready': True}, {'id': 'codex', 'ready': False, 'code': 'codex_sign_in_expired'}]
        with mock.patch('eaos.ai.assistant.readiness.probe_all', return_value=rows) as probed:
            answer = agent_tools.assistant_check(str(self.project), fresh=True)
        probed.assert_called_once_with(fresh=True, names=None)
        self.assertEqual(answer['assistants'], rows)
        self.assertEqual(answer['choice'], {'use_assistant': None, 'assistant': 'claude', 'kept': False})
        self.assertIn('changes no file', answer['permission']['en'])
        self.assertTrue(answer['permission']['ar'])
        rows = [{'id': 'claude', 'name': 'Claude Code', 'ready': False, 'installed': False, 'code': 'claude_not_installed', 'reason': {'en': 'no claude'}},
                {'id': 'codex', 'name': 'Codex', 'ready': False, 'installed': True, 'code': 'codex_sign_in_expired', 'reason': {'en': 'run codex login'}}]
        with mock.patch('eaos.ai.assistant.readiness.probe_all', return_value=rows):
            row = guided.assistant_row(probe=True)
        self.assertFalse(row['ok'])
        self.assertIn('Codex: sign-in expired', row['en'])
        self.assertEqual(row['fix'], 'run codex login')
        with mock.patch('eaos.ai.assistant.readiness.probe_all', side_effect=AssertionError('no probe without asking')):
            self.assertTrue(guided.assistant_row(probe=False)['ok'])

if __name__ == '__main__':
    unittest.main()
