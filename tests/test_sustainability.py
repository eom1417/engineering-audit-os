"""The six sustainability indicators, the transform plan built on them and the canonical home of a repeated definition
(eaos/sustainability.py, eaos/transform_plan.py, eaos/canonical_home.py), restored from the archive in 0.0.9."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import shared_fixture  # noqa: F401  (runs without measured detector verdicts)
from eaos import sustainability, transform_plan
from eaos.canonical_home import suggest
from eaos.facts.run import collect
from shared_fixture import scratch

SETS = ['syntax', 'structure', 'fingerprint', 'sequences', 'redundancy', 'domain', 'graph', 'metrics', 'flows', 'resolve']
FIXTURE = Path(__file__).resolve().parent / 'fixtures/sustainability'


def _collect(tmp, files=None, source=FIXTURE):
    repo = Path(tmp) / 'src'
    repo.mkdir()
    if files:
        for name, text in files.items(): (repo / name).write_text(text)
    else:
        for child in source.rglob('*'):
            if child.is_file():
                (repo / child.relative_to(source)).parent.mkdir(parents=True, exist_ok=True)
                (repo / child.relative_to(source)).write_bytes(child.read_bytes())
    collect(repo, Path(tmp) / 'out', SETS)
    return Path(tmp) / 'out'


class SustainabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = scratch()
        cls.out = _collect(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_six_indicators_against_their_target_and_a_move_with_a_falsifier_for_each_gap(self):
        result = sustainability.write(self.out)
        self.assertEqual({row['indicator'] for row in result['rows']}, set(sustainability.INDICATORS))
        single = next(row for row in result['rows'] if row['indicator'] == 'single_source')
        self.assertGreater(single['gap'], 0)
        self.assertTrue(result['moves'])
        self.assertTrue(all(move['falsifier'] and move['indicator'] for move in result['moves']))
        record = json.loads((self.out / 'sustainability.json').read_text())
        self.assertEqual(record['rows'], result['rows'])

    def test_a_detector_that_saw_too_little_of_the_snapshot_reports_unmeasured_not_a_clean_zero(self):
        row = sustainability._too_little_coverage('redundancy detection', {'files_observed': 1, 'files_blocked': 1020})
        self.assertEqual((row['value'], row['measured']), (None, False))
        self.assertIsNone(sustainability._too_little_coverage('redundancy detection', {'files_observed': 5, 'files_blocked': 5}))

    def test_each_repeated_definition_gets_a_canonical_home_and_an_acceptance(self):
        plan = transform_plan.build(self.out)
        homes = [s for s in plan['stages'] if s['move'] == 'canonicalize']
        self.assertTrue(homes)
        for stage in homes:
            self.assertIsNotNone(stage['canonical_home'])
            self.assertEqual(stage['acceptance']['expected_exit'], 0)
            self.assertTrue(stage['falsifier'] and stage['rollback'])
        transform_plan.write(self.out, plan)
        self.assertEqual(len(json.loads((self.out / 'transform-plan.json').read_text())['stages']), len(plan['stages']))

    def test_a_canonical_home_never_closes_an_import_cycle(self):
        body = 'def run(x, y, z):\n    if x > 0:\n        return y + z\n    return y - z\n'
        with tempfile.TemporaryDirectory() as tmp:
            out = _collect(tmp, {'a.py': 'from b import x\n\n' + body, 'b.py': 'from a import x\n\n' + body})
            clusters = [f for f in json.loads((out / 'facts/fingerprint.json').read_text())['facts'] if f['kind'] == 'duplicate_cluster']
            self.assertTrue(clusters)
            paths = {c['path'] for c in suggest(out, clusters[0])['candidates']}
        self.assertIn('', paths)
        self.assertFalse({'a.py', 'b.py'} & paths)


if __name__ == '__main__':
    unittest.main()
