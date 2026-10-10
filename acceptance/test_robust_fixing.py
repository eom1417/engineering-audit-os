"""NS46.T22 owner-request acceptance (owner, 2026-10-10: fixing must hold, not stop midway), planned 2026-10-10.

The evidence is $EAOS_MEASURE/robust-fixing/trial.json, written by the real Studio fix trial on EAOS itself with the
person's assistant: {"assistant", "branch", "kept", "rechecks", "stuck_batches", "manual_steps"}. A fake provider or
a unit test never counts.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import north_star_measure as measure


class RobustFixing(unittest.TestCase):
    def test_a_real_fix_run_reaches_its_branch_without_a_stall(self):
        path = measure.REPORTS / 'robust-fixing/trial.json'
        self.assertTrue(path.is_file(), f'no evidence at {path}')
        trial = json.loads(path.read_text(encoding='utf-8'))
        self.assertTrue(trial.get('assistant'), 'a real assistant ran it')
        self.assertRegex(trial.get('branch') or '', r'^eaos/wave-\d+$')
        self.assertGreaterEqual(len(trial.get('kept') or []), 1)
        self.assertEqual((trial.get('rechecks'), trial.get('stuck_batches'), trial.get('manual_steps')), (0, 0, 0))


if __name__ == '__main__':
    unittest.main()
