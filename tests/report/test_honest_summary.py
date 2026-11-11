"""What the first page says of a check is what is so: "78 problems, all fixed automatically" must not hide 30 screen
notes a person must look at, or a secret in a test's sample."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.features.layers.analysis.target_state.projection import _secrets_item
from eaos.kernel.contracts.decisions import unattended


def card(kind='remediate', pattern='hotspot', check='command'):
    return {'kind': kind, 'pattern': pattern, 'decision': {'readiness': 'ready', 'checks': [{'kind': check}]}}


class HonestSummary(unittest.TestCase):
    def test_only_what_the_machine_fixes_and_proves_is_called_automatic(self):
        self.assertTrue(unattended(card()))
        for told in (card(check='human'), card(pattern='investigation'), card(kind='build')):
            self.assertFalse(unattended(told))

    def test_a_card_from_a_detector_not_measured_is_said_as_such(self):
        from eaos.features.report.interface.documents import start_here
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'dossier.json').write_text(json.dumps({'claims': [
                {'id': 'C1', 'render': {'key': 'hotspot'}}, {'id': 'C2', 'render': {'key': 'never_judged'}}]}))
            with mock.patch.object(start_here, 'measured_detectors', return_value={'hotspot'}):
                self.assertEqual(start_here._unmeasured(folder, [{'claim_id': 'C1'}, {'claim_id': 'C2'}]), 1)

    def test_a_sample_in_a_tests_data_is_no_credential_of_the_project(self):
        fact = lambda path: {'location': {'path': path}, 'value': {'severity': 'high'}}
        self.assertTrue(_secrets_item({'committed_credential': [fact('tests/contracts/semgrep.json')]})[0])
        self.assertFalse(_secrets_item({'committed_credential': [fact('app/settings.py')]})[0])


if __name__ == '__main__':
    unittest.main()
