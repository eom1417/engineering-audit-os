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


if __name__ == '__main__':
    unittest.main()
