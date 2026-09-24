"""NS17.T4 — the fifteen stages as data, and a gate per stage that a command decides.

Interface this task must provide:
    python -m eaos engage status REPORT_DIR --json
      {"stages": [{"id": "S01", "key": "DISCOVER", "contract": "assessment" | "execution" | "mixed",
                   "artifacts": [{"path": ..., "present": bool}], "gate": {"passed": bool, "reasons": [str]}}]}
      ids and keys exactly those of docs/north-star.json -> pipeline, in order.
      contract: S05 and S15 are "mixed" (a static half, then a run); S01-S04, S06, S07 "assessment";
      S08-S14 "execution".
    python -m eaos engage gate SXX REPORT_DIR [--runtime DIR]
      exit 0 when SXX and every earlier stage pass; exit 1 otherwise, printing the first failing stage id;
      exit 3 for an execution stage when DIR/authorization.json (default DIR = REPORT_DIR) is missing,
      expired, or does not grant SXX, printing the word "authorization".
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def eaos(*args):
    return subprocess.run([sys.executable, '-m', 'eaos', *args], cwd=ROOT, capture_output=True, text=True)


class Engage(unittest.TestCase):
    def test_the_stages_are_the_pipeline_of_the_plan(self):
        pipeline = json.loads((ROOT / 'docs/north-star.json').read_text(encoding='utf-8'))['pipeline']
        with tempfile.TemporaryDirectory() as tmp:
            done = eaos('engage', 'status', tmp, '--json')
            self.assertEqual(done.returncode, 0, done.stderr)
            stages = json.loads(done.stdout)['stages']
        self.assertEqual([(s['id'], s['key']) for s in stages], [(s['id'], s['key']) for s in pipeline])
        contract = {s['id']: s['contract'] for s in stages}
        self.assertEqual({k for k, v in contract.items() if v == 'mixed'}, {'S05', 'S15'})
        self.assertEqual({k for k, v in contract.items() if v == 'execution'}, {f'S{i:02d}' for i in range(8, 15)})
        for stage in stages:
            self.assertIsInstance(stage['gate']['passed'], bool)
            self.assertTrue(stage['gate']['passed'] or stage['gate']['reasons'], stage['id'])

    def test_a_gate_fails_on_the_first_earlier_stage_that_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            done = eaos('engage', 'gate', 'S04', tmp)
        self.assertEqual(done.returncode, 1)
        self.assertIn('S01', done.stdout + done.stderr)

    def test_an_execution_stage_without_authorization_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            done = eaos('engage', 'gate', 'S08', tmp)
        self.assertEqual(done.returncode, 3)
        self.assertIn('authorization', (done.stdout + done.stderr).lower())


if __name__ == '__main__':
    unittest.main()
