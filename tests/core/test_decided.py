"""An investigation card is accepted once its observation carries a recorded decision, and not before."""
import json
from pathlib import Path
import subprocess
import sys

from shared_fixture import Workspace

from eaos.core.contracts.decided import status

CLAIM = {'id': 'CLM-001', 'uid': 'OBS-1', 'statement': 'a coupling', 'claim_type': 'structure', 'confidence': 'LIKELY',
         'falsifier': 'f', 'origin': 'source'}


class DecidedTests(Workspace):
    def report(self, claim):
        Path(self.tmp, 'dossier.json').write_text(json.dumps({'claims': [claim]}))
        return self.tmp

    def test_only_a_recorded_decision_or_a_vanished_observation_closes_the_card(self):
        decided = {**CLAIM, 'disposition': {'kind': 'accepted', 'owner': 'lead', 'reason': 'the coupling is intended'}}
        cases = [(CLAIM, 'OBS-1', 'open'), (decided, 'OBS-1', 'retain'),
                 ({**CLAIM, 'confidence': 'REFUTED'}, 'OBS-1', 'retain'), (CLAIM, 'OBS-other', 'gone')]
        for claim, uid, expected in cases:
            with self.subTest(expected=expected, uid=uid):
                self.assertEqual(status(self.report(claim), uid)[0], expected)

    def test_the_card_command_exits_1_while_open(self):
        done = subprocess.run([sys.executable, '-m', 'eaos', 'decided', self.report(CLAIM), 'OBS-1'], capture_output=True,
                              text=True, cwd=Path(__file__).resolve().parents[2])
        self.assertEqual(done.returncode, 1, done.stderr)
