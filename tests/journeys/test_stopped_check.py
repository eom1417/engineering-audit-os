"""A check that stopped before its plan says the step it stopped at and why, not that the project was never checked."""
import json
import tempfile
import unittest
from pathlib import Path
from eaos.journeys.agent_tools.project import _stopped


class StoppedCheckTests(unittest.TestCase):
    def test_the_failed_step_and_its_reason_are_said(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp)
            self.assertEqual(_stopped(report), '')
            (report / 'run-manifest.json').write_text(json.dumps({'stages': {
                'facts': {'status': 'ok'},
                'claims': {'status': 'failed', 'reason': 'ValueError: Claim ledger rejected'},
                'plan': {'status': 'not_reached'}}}), encoding='utf-8')
            said = _stopped(report)
            self.assertIn('`claims`', said)
            self.assertIn('Claim ledger rejected', said)


if __name__ == '__main__':
    unittest.main()
