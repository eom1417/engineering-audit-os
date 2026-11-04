"""A project with no interface (a library, a command-line tool, a mobile app) is never pictured through a stand-in page:
its own tests and build keep a change safe (a Python library and a Flutter app were judged by a file listing, and a Rust
tool could not be fixed at all, 2026-11-04)."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from eaos.live.app import first_page, own_checks, profile
from eaos.journeys.agent_tools import fixing, where


class NoInterfaceTests(unittest.TestCase):
    def test_a_file_listing_is_no_app(self):
        with self.assertRaises(first_page.NoInterface):
            first_page.listing({'text': 'Directory listing for /\nsrc/\ntests/\nuv.lock'})
        self.assertEqual(first_page.listing({'text': 'Welcome to the dashboard'}), '')

    def test_the_assistants_answer_that_nothing_opens_is_taken(self):
        with self.assertRaisesRegex(first_page.NoInterface, 'a signing library'):
            first_page.declined({'reason': 'x', 'no_interface': 'a signing library, no server'})
        first_page.declined({'reason': 'keeps the start command', 'start': None})     # null keeps the current value

    def test_a_crate_and_a_module_are_kept_safe_by_their_own_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(own_checks.found(tmp), ([['true']], []))
            (Path(tmp) / 'Cargo.toml').write_text('[package]\nname = "x"\n')
            install, checks = own_checks.found(tmp)
            self.assertEqual(checks, [['cargo', 'test', '--locked', '--offline']])
            self.assertEqual(own_checks.unknown_app(tmp)['profile']['checks'], checks)
        self.assertEqual(profile.safe({'install': install, 'start': ['cargo', 'run']}), [])

    def test_passing_own_checks_open_a_batch_without_screens(self):
        state = {'setup': {'ok': False, 'no_interface': True, 'commit': 'c'},
                 'safety': {'commit': 'c', 'screens': 0, 'passed': 0, 'own_checks': 2}}
        with mock.patch.object(fixing.guided, 'safety_holds', return_value=True), mock.patch.object(fixing, '_head', return_value='c'):
            self.assertIsNone(fixing._no_safety_net(state))
        with mock.patch.object(where.guided, 'set_up', return_value=True), mock.patch.object(where.guided, 'safety_holds', return_value=True):
            self.assertEqual(where._setup_step(state, 'c')[0], 'fix_start')
            state['safety']['own_checks'] = 0
            self.assertEqual(where._setup_step(state, 'c')[0], 'none')

    def test_the_safety_net_of_a_project_with_no_interface_starts_nothing_and_runs_its_own_checks(self):
        from eaos.journeys.guided import running
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'run.json').write_text('{}', encoding='utf-8')
            state = {'setup': {'ok': False, 'no_interface': True, 'commit': 'c'}}
            with mock.patch.object(running, 'runtime_of', return_value=Path(tmp)), mock.patch.object(running, 'report_of', return_value=Path(tmp)), \
                    mock.patch.object(running, 'source', return_value=Path(tmp)), mock.patch.object(running, 'save'), \
                    mock.patch('eaos.live.behavior.specs.build'), mock.patch('eaos.live.behavior.lock.run_lock', side_effect=AssertionError('started')), \
                    mock.patch('eaos.journeys.fix.execute.original_checks', return_value=[{'argv': ['pytest'], 'exit': 0}]):
                outcome = running._safety_run(state, lambda n: None)
        self.assertEqual((outcome['screens'], outcome['own_checks'], state['safety']['own_checks']), (0, 1, 1))
        self.assertIn('no interface', outcome['skipped'][0]['reason'])

    def test_a_batch_of_a_project_with_no_interface_is_held_by_its_checks_not_by_screens(self):
        from eaos.journeys.fix import finish
        state = {'setup': {'no_interface': True}, 'open_wave': {'root': '/x', 'base': 'b'}}
        with mock.patch.object(finish.project_state, 'load', return_value=state), mock.patch.object(finish.project_state, 'runtime_of'), \
                mock.patch.object(finish.guided, 'stale_refusal', return_value=None), mock.patch.object(finish.guided, '_git'), \
                mock.patch.object(finish.guided, 'save'), mock.patch.object(finish.guided, 'report_of'), mock.patch.object(finish.guided, 'source'), \
                mock.patch('eaos.journeys.fix.waves.finish_batch', side_effect=RuntimeError('stop')) as batch:
            with self.assertRaises(RuntimeError): finish.finish_job('/p', {}, lambda *_: None)
        self.assertIs(batch.call_args.kwargs['lock'], False)


if __name__ == '__main__':
    unittest.main()
