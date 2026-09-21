"""Golden fact snapshots: any change in extractor output must be seen and accepted deliberately.

Regenerate with: python tests/regenerate_golden.py
"""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from shared_fixture import TemporaryWorkspace
from eaos.facts.run import collect
from eaos.facts.store import read_set

ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / 'fixtures/polyglot'
GOLDEN = ROOT / 'fixtures/golden'
SETS = ['syntax', 'resolve', 'structure', 'fingerprint', 'sequences', 'redundancy', 'runtime', 'entrypoints', 'config', 'metrics', 'domain', 'graph', 'flows']


class GoldenFactTests(TemporaryWorkspace):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        collect(FIXTURE, Path(cls.tmp.name) / 'out', SETS)
        cls.produced = {name: read_set(Path(cls.tmp.name) / 'out', name) for name in SETS}


    def test_every_extractor_matches_its_golden_snapshot(self):
        for name in SETS:
            expected = json.loads((GOLDEN / f'{name}.json').read_text())
            with self.subTest(extractor=name):
                self.assertEqual(self.produced[name], expected,
                                 f'{name} output drifted; review the diff and regenerate the golden file deliberately')

    def test_golden_snapshots_cover_the_extractors_we_ship(self):
        from eaos.facts.run import EXTRACTORS
        self.assertEqual(set(SETS) | {'history'}, set(EXTRACTORS),
                         'A new extractor needs a golden snapshot or an explicit reason to be excluded')


class IncrementalCacheTests(unittest.TestCase):
    """A cached run must be cheaper but not different."""

    def test_cached_run_is_byte_identical_to_a_cold_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            cold = Path(tmp) / 'cold'
            collect(FIXTURE, cold, SETS)
            first = (cold / 'facts/syntax.json').read_bytes()
            second_result = collect(FIXTURE, cold, SETS)
            self.assertEqual((cold / 'facts/syntax.json').read_bytes(), first)
            self.assertGreater(second_result['reused_from_cache'].get('syntax', 0), 0)

    def test_changing_one_file_only_reparses_that_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            shutil.copytree(FIXTURE, repo)
            out = Path(tmp) / 'out'
            collect(repo, out, SETS)
            warm = collect(repo, out, SETS)['reused_from_cache']['syntax']
            (repo / 'core/pricing.py').write_text('PREMIUM_DISCOUNT = 0.2\n')
            after_edit = collect(repo, out, SETS)['reused_from_cache']['syntax']
            self.assertEqual(after_edit, warm - 1, 'exactly one changed file should fall out of the cache')
