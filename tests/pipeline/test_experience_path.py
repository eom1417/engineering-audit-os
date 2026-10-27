"""The experience in the check (M10.9): its own path (the whole simulation on the check's running app), its short option
beside the complete check with its time and cost said before it starts, and the saved journeys replayed with the
behaviour lock in every full check, each a row of it, without the assistant."""
import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.analysis.experience import simulation
from eaos.core.contracts.artifact_rules import validate
from eaos.core.contracts.check_paths import PATHS
from eaos.core.language.words import catalog
from eaos.interfaces import cli
from eaos.journeys import check_choices
from eaos.live.experience import replay
from eaos.pipeline.loops import switched_off
from eaos.pipeline.path_choice import resolve
from eaos.pipeline.runners import experience as runner
from eaos.pipeline.runners.by_rules import RUNNERS
from eaos.pipeline.runners.live_app import PAGE_STAGES
from eaos.pipeline.stage_run import Context
from eaos.pipeline.stages import BY_NAME, ORDER, WAITS, SkipStage

ACTIONS = Path(__file__).parents[2] / 'eaos/data/studio-actions.json'


class Declared(unittest.TestCase):
    def test_the_path_runs_the_app_signed_in_and_the_option_is_off_unless_chosen(self):
        alone = resolve(['experience'])['stages']
        self.assertTrue({'roles', 'setup', 'session', 'experience'} <= set(alone))
        self.assertNotIn('screens', alone, 'the path does not picture every page first')
        self.assertIn('experience', switched_off(['complete']), 'off by default in the complete check')
        self.assertNotIn('experience', switched_off(['complete', 'experience']))
        self.assertEqual(resolve(['complete', 'experience'])['paths'], ['complete', 'experience'])
        stage = BY_NAME['experience']
        self.assertEqual((stage.requires, stage.uses), (('setup',), ('app',)))
        self.assertLess(ORDER.index('screens'), ORDER.index('experience'))
        self.assertIn('experience', WAITS['claims'], 'its confirmed difficulties reach the claims, so the cards')
        self.assertIn('experience', PAGE_STAGES, 'the shared app stays up for it')
        self.assertIs(RUNNERS['experience'], runner.experience)

    def test_the_cli_the_mcp_tool_and_the_studio_accept_the_path(self):
        parsed = []
        original = argparse.ArgumentParser.parse_args

        def spy(self, argv=None, namespace=None):
            parsed.append(self)
            raise SystemExit(0)
        with mock.patch.object(argparse.ArgumentParser, 'parse_args', spy), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.suppress(SystemExit):
            cli.main(['--version'])
        commands = [a for a in parsed[0]._actions if isinstance(a, argparse._SubParsersAction)][0].choices
        for name in ('check', 'start'):
            with self.subTest(name):
                args, _ = commands[name].parse_known_args(['--path', 'experience'])
                self.assertEqual(args.path, ['experience'])
        audit = next(a for a in json.loads(ACTIONS.read_text(encoding='utf-8'))['actions'] if a['id'] == 'audit')['inputs']
        self.assertEqual(validate({'paths': ['complete', 'experience']}, audit), [], 'the MCP audit tool and the Studio queue it')
        state = {'workspace': '.'}
        self.assertEqual(check_choices.options(state, None, [], None, None, paths=['experience'])['paths'], ['experience'])
        self.assertIn('experience', [p['id'] for p in check_choices.offered(state)['paths']], 'the Studio lists it from data')


class Estimate(unittest.TestCase):
    def test_the_short_option_says_its_time_and_calls_before_the_check_and_the_plain_check_adds_nothing(self):
        last = {name: 30.0 for name in ORDER if name != 'experience'}
        with mock.patch.object(check_choices, 'previous_seconds', return_value=last):
            plain, short = check_choices.estimate('report'), check_choices.estimate('report', ['complete', 'experience'])
            alone = check_choices.estimate('report', ['experience'])
        self.assertNotIn('experience', plain)
        self.assertEqual(short['experience'], {'simulation': 'short', 'minutes': simulation.SHORT['seconds'] // 60,
                                               'calls': {'light': simulation.SHORT['steps'], 'deep': 1}})
        self.assertGreaterEqual(short['minutes_high'] - plain['minutes_high'], simulation.SHORT['seconds'] // 60 - 1)
        self.assertEqual(alone['experience']['simulation'], 'whole')
        self.assertEqual(check_choices.adds(['complete', 'experience']), {'experience': short['experience']}, 'a first check says it too')
        self.assertEqual(check_choices.adds(None), {})
        said = catalog()['paths']['experience']['looks_at'][1]
        for number in (f"{simulation.SHORT['seconds'] // 60} minutes", f"{simulation.SHORT['steps']} light"):
            self.assertIn(number, said, "the words say the option's own numbers")
        self.assertIn('experience', PATHS)


class Stage(unittest.TestCase):
    def _run(self, paths, provider=object()):
        app = {'base': 'http://127.0.0.1:1', 'sessions': {}, 'runtime': Path('.')}
        ran = {'goals': [{'status': 'reached'}, {'status': 'stuck'}], 'calls': 7}
        with tempfile.TemporaryDirectory() as out, mock.patch.object(runner, 'app_of', return_value=app), \
                mock.patch.multiple(simulation, short=mock.DEFAULT, prepare=mock.DEFAULT, simulate=mock.DEFAULT, judged=mock.DEFAULT) as calls, \
                mock.patch('eaos.report.experience.document.write') as write:
            calls['short'].return_value = {**ran, 'judged': {'confirm': 1}}
            calls['simulate'].return_value = dict(ran)
            calls['judged'].return_value = {'confirm': 2}
            said = runner.experience(Context(out=Path(out), target='.', provider=provider, language='en', paths=paths))
            return said, {name: call.called for name, call in calls.items()}, write.called

    def test_alone_the_whole_simulation_beside_complete_the_short_one_and_the_report_either_way(self):
        said, called, written = self._run(['experience'])
        self.assertEqual((said['simulation'], said['confirmed']), ('whole', 2))
        self.assertEqual(called, {'short': False, 'prepare': True, 'simulate': True, 'judged': True})
        self.assertTrue(written)
        said, called, written = self._run(['complete', 'experience'])
        self.assertEqual((said['simulation'], said['goals'], said['reached']), ('short', 2, 1))
        self.assertEqual(called, {'short': True, 'prepare': False, 'simulate': False, 'judged': False})
        with self.assertRaises(SkipStage): self._run(['experience'], provider=None)

    def test_the_short_simulation_is_one_persona_on_its_first_goal_within_its_steps(self):
        given = {'features': [{'name': f, 'description': f, 'surfaces': ['/' + f], 'critical': True} for f in ('a', 'b')],
                 'roles': [{'id': 'admin', 'name': 'Admin', 'pages': ['/a']}, {'id': 'user', 'name': 'User', 'pages': []}],
                 'pages': [], 'sign_in': {}}
        with mock.patch.object(simulation.scenarios, 'brief', return_value=given), \
                mock.patch.object(simulation.cast, 'run', return_value={'goals': []}) as run, \
                mock.patch.object(simulation.judging, 'judge', return_value={'confirm': 0}):
            simulation.short('report', '.', {}, 'provider')
        played = run.call_args.args[1]
        self.assertEqual([len(p['goals']) for p in played['personas']], [1])
        self.assertEqual(played['personas'][0]['goals'][0]['steps'], simulation.SHORT['steps'])


class Replays(unittest.TestCase):
    def _journey(self, folder, name, reached=True):
        steps = [{'action': 'click', 'landed': '/done'}]
        (folder / f'{name}.json').write_text(json.dumps({'goal': name, 'role': None, 'start': '/', 'reached': reached, 'steps': steps}))

    def test_saved_journeys_replay_as_rows_of_the_lock_without_the_assistant(self):
        answers = {'buyer--order': {'screens': ['/', '/done']}, 'admin--approve': {'screens': ['/'], 'broken_at': 1, 'error': 'no button'}}

        @contextlib.contextmanager
        def browser(base, out, state=None): yield Path(out).name

        lock = {'results': [{'path': 'pages/home.spec.ts', 'status': 'passed'},
                            {'path': 'experience/journeys/gone.json', 'status': 'passed'}], 'limitations': []}
        with tempfile.TemporaryDirectory() as out, tempfile.TemporaryDirectory() as runtime:
            journeys = Path(out) / 'experience' / 'journeys'
            journeys.mkdir(parents=True)
            for name in answers: self._journey(journeys, name)
            self._journey(journeys, 'visitor--look', reached=False)
            context = Context(out=Path(out), runtime=runtime, provider=mock.Mock(side_effect=AssertionError('no AI')))
            app = {'base': 'http://127.0.0.1:1', 'sessions': {}, 'runtime': runtime}
            with mock.patch.object(runner, 'app_of', return_value=app), mock.patch.object(replay, 'Browser', browser), \
                    mock.patch.object(replay, 'replay', lambda opened, journey: answers[opened]):
                record = runner.replayed(context, lock)
            written = json.loads((Path(runtime) / 'behavior-lock/results.json').read_text(encoding='utf-8'))
        self.assertEqual(written, record)
        rows = {row['path']: row for row in record['results']}
        self.assertEqual(rows['pages/home.spec.ts']['status'], 'passed')
        self.assertNotIn('experience/journeys/gone.json', rows, "an earlier check's replay is replaced")
        self.assertEqual(rows['experience/journeys/buyer--order.json']['status'], 'passed')
        self.assertEqual(rows['experience/journeys/admin--approve.json']['status'], 'failed', 'red shows as a broken screen')
        self.assertIn('step 1: no button', rows['experience/journeys/admin--approve.json']['reason'])
        self.assertEqual(rows['experience/journeys/visitor--look.json']['status'], 'quarantined')
        context.provider.assert_not_called()

    def test_nothing_saved_nothing_replayed(self):
        lock = {'results': [], 'limitations': ['x']}
        with tempfile.TemporaryDirectory() as out, tempfile.TemporaryDirectory() as runtime, \
                mock.patch.object(runner, 'app_of', side_effect=AssertionError('no app needed')):
            self.assertIs(runner.replayed(Context(out=Path(out), runtime=runtime), lock), lock)
            self.assertFalse((Path(runtime) / 'behavior-lock').exists())


if __name__ == '__main__':
    unittest.main()
