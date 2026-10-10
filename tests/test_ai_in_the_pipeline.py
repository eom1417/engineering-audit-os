"""The person's assistant inside the check (docs/AI-IN-THE-PIPELINE.md): asked about once, passed to the check so the
semantic stage runs, the ideal planned right after the check, invented citations dropped, and the rules standing alone
without an assistant or on a failure."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos import agent_tools, guided
from eaos.dossier import assemble
from eaos.pipeline import runners
from eaos.pipeline.run import Context, _one
from eaos.pipeline.stages import BY_NAME, STAGES, SkipStage
from eaos.progress import stage_rows
from eaos.studio import ideal
from eaos.studio.nodes import core
from test_ideal_planner import Launcher, make_report
from test_semantic import FIXTURE, ScriptedSemanticProvider, grounded


def invented(digest, call):
    return {'claims': [{'statement': 'Something is wrong somewhere in the system', 'claim_type': 'cause',
                        'fact_ids': ['FACT-doesnotexist'], 'falsifier': 'evidence to the contrary', 'basis': 'inferred'}],
            'questions': []}


def slow(digest, call):
    raise ValueError('Model adapter timed out; no raw stderr exposed')


class SemanticStage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / 'out'
        assemble(FIXTURE, self.out)

    def context(self, provider):
        return Context(target=FIXTURE, out=self.out, provider=provider, language='en')

    def test_an_invented_citation_is_sent_back_and_only_grounded_claims_are_kept(self):
        answers = iter([invented, grounded])
        provider = ScriptedSemanticProvider(lambda digest, call: next(answers)(digest, call))
        detail = runners.semantic(self.context(provider))
        self.assertEqual((detail['hypotheses'], detail['calls']), (1, 2))
        self.assertNotIn('FACT-doesnotexist', (self.out / 'semantic.json').read_text(encoding='utf-8'))

    def test_without_an_assistant_or_on_a_failure_the_stage_is_unavailable_and_the_check_goes_on(self):
        for provider, code in ((None, 'no_provider'), (ScriptedSemanticProvider(invented), 'ai_failed'),
                               (ScriptedSemanticProvider(slow), 'ai_failed')):
            row = _one(BY_NAME['semantic'], self.context(provider), runners.RUNNERS, {})
            self.assertEqual((row['status'], row['reason_code']), ('unavailable', code))
        self.assertFalse((self.out / 'SEMANTIC.md').exists())


class IdealStage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.report = make_report(self.tmp.name)
        self.context = Context(target=Path(self.tmp.name), out=self.report, provider=object(), language='en')

    def planned_with(self, launcher):
        with mock.patch.object(core, 'pick', return_value=object()), mock.patch.object(core, 'AdapterLauncher', return_value=launcher):
            return runners.ideal(self.context)

    def test_after_the_check_the_ideal_is_planned_and_an_element_with_an_invented_citation_is_dropped(self):
        detail = self.planned_with(Launcher())
        self.assertEqual((detail['dropped'], detail['calls'], detail['model']), (1, 2, 'fake-model'))
        record, state = ideal.current(self.report)
        self.assertEqual(state, 'planned')
        self.assertEqual([row['id'] for row in record['dropped']], ['s9'])
        self.assertEqual(ideal.section(self.report, 'en')['views']['system']['provenance']['method'], 'planned')

    def test_a_failed_plan_or_no_assistant_leaves_the_rules_target(self):
        with self.assertRaises(SkipStage) as failed:
            self.planned_with(Launcher('critique', TimeoutError('slow')))
        self.assertEqual(failed.exception.code, 'ai_failed')
        with self.assertRaises(SkipStage) as absent:
            runners.ideal(Context(self.context, provider=None))
        self.assertEqual(absent.exception.code, 'no_provider')
        self.assertEqual(ideal.current(self.report), (None, 'failed'))

    def test_the_live_map_marks_the_ai_stages_from_their_declaration(self):
        self.assertEqual([row['name'] for row in stage_rows(STAGES) if row['ai']], ['semantic', 'ideal'])
        self.assertEqual(BY_NAME['ideal'].requires, ('compose',))


class Consent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        home = mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(self.tmp.name) / 'home'), 'EAOS_ASSISTANT': 'claude'})
        home.start(); self.addCleanup(home.stop)
        installed = mock.patch('eaos.runtime.assistants.shutil.which', return_value='/bin/claude')
        installed.start(); self.addCleanup(installed.stop)
        self.project = Path(self.tmp.name) / 'shop'
        self.project.mkdir()
        subprocess.run(['git', 'init', '-q', '-b', 'main'], cwd=self.project, check=True)
        (self.project / 'package.json').write_text('{}', encoding='utf-8')
        subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'one', '--allow-empty'], cwd=self.project,
                       check=True)

    def test_eaos_start_asks_once_and_yes_answers_it(self):
        state = {'lang': 'en', 'project': str(self.project), 'workspace': str(Path(self.tmp.name) / 'ws'), 'questions': []}
        with mock.patch.object(guided.sys.stdin, 'isatty', return_value=False), self.assertRaises(guided.NeedsAnswer):
            guided.agree_to_assistant(state, yes=False)
        self.assertIsNone(guided.check_provider(state))
        guided.agree_to_assistant(state, yes=True)
        self.assertIn('claude_adapter', guided.check_provider(state).identity()['argv'][-1])
        state['questions'][-1]['answer'] = False
        self.assertIsNone(guided.check_provider(state))

    def test_the_mcp_audit_keeps_the_persons_answer_and_passes_the_assistant_to_the_check(self):
        with mock.patch.object(agent_tools, '_start', return_value={'status': 'started'}):
            agent_tools.audit(str(self.project), use_assistant=True)
        with mock.patch('eaos.pipeline.check', side_effect=RuntimeError('stop here')) as check, self.assertRaises(RuntimeError):
            agent_tools._audit_job(str(self.project), {}, None)
        self.assertIsNotNone(check.call_args.kwargs['provider'])
        with mock.patch.object(agent_tools, '_start', return_value={'status': 'started'}):
            agent_tools.audit(str(self.project), use_assistant=False)
        self.assertIsNone(guided.check_provider(guided.load(self.project)))


if __name__ == '__main__':
    unittest.main()
