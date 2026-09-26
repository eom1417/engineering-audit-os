"""An investigation card is accepted once its observation carries a recorded decision, and not before."""
import json
from pathlib import Path

from shared_fixture import Workspace

from eaos.decided import status

CLAIM = {'id': 'CLM-001', 'uid': 'OBS-1', 'statement': 'a coupling', 'claim_type': 'structure', 'confidence': 'LIKELY',
         'falsifier': 'f', 'origin': 'source'}


class DecidedTests(Workspace):
    def report(self, claim):
        Path(self.tmp, 'dossier.json').write_text(json.dumps({'claims': [claim]}))
        return self.tmp

    def test_an_open_investigation_is_not_accepted(self):
        self.assertEqual(status(self.report(CLAIM), 'OBS-1')[0], 'open')

    def test_a_recorded_retain_with_owner_and_reason_closes_it(self):
        decided = {**CLAIM, 'disposition': {'kind': 'accepted', 'owner': 'lead', 'reason': 'the coupling is intended'}}
        self.assertEqual(status(self.report(decided), 'OBS-1')[0], 'retain')

    def test_a_refuted_or_vanished_observation_closes_it(self):
        self.assertEqual(status(self.report({**CLAIM, 'confidence': 'REFUTED'}), 'OBS-1')[0], 'retain')
        self.assertEqual(status(self.report(CLAIM), 'OBS-other')[0], 'gone')

    def test_the_card_command_exits_1_while_open(self):
        import subprocess, sys
        done = subprocess.run([sys.executable, '-m', 'eaos', 'decided', self.report(CLAIM), 'OBS-1'], capture_output=True, text=True,
                              cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(done.returncode, 1, done.stderr)
