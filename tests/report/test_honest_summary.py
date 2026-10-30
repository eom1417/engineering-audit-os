"""What the first page says of a check is what is so (EAOS on itself, 2026-10-30): "78 problems, all fixed automatically"
held 30 screen notes a person must look at, a red gap for a database the project does not have, a secret in a test's sample."""
import unittest

from eaos.analysis.assessments.data_keeping import unmeasured
from eaos.analysis.target_state.projection import _secrets_item
from eaos.core.contracts.decisions import unattended


def card(kind='remediate', pattern='hotspot', check='command'):
    return {'kind': kind, 'pattern': pattern, 'decision': {'readiness': 'ready', 'checks': [{'kind': check}]}}


class HonestSummary(unittest.TestCase):
    def test_only_what_the_machine_fixes_and_proves_is_called_automatic(self):
        self.assertTrue(unattended(card()))
        for told in (card(check='human'), card(pattern='investigation'), card(kind='build')):
            self.assertFalse(unattended(told))

    def test_an_app_with_no_database_is_no_gap_and_one_that_could_not_be_read_is(self):
        pages = {'writes_before': {'pages': 5}}
        self.assertEqual(unmeasured({**pages, 'database': {'why': 'none', 'none_declared': True}}), [])
        self.assertEqual(unmeasured({**pages, 'database': {'why': 'none'}}), ['none'])

    def test_a_sample_in_a_tests_data_is_no_credential_of_the_project(self):
        fact = lambda path: {'location': {'path': path}, 'value': {'severity': 'high'}}
        self.assertTrue(_secrets_item({'committed_credential': [fact('tests/contracts/semgrep.json')]})[0])
        self.assertFalse(_secrets_item({'committed_credential': [fact('app/settings.py')]})[0])


if __name__ == '__main__':
    unittest.main()
