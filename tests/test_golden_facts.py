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
SETS = ['syntax', 'resolve', 'structure', 'fingerprint', 'sequences', 'redundancy', 'runtime', 'entrypoints', 'config', 'metrics', 'domain', 'graph', 'flows', 'leftovers', 'deadcode', 'broken', 'secrets', 'pipeline']


class GoldenFactTests(TemporaryWorkspace):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        collect(FIXTURE, Path(cls.tmp.name) / 'out', SETS)
        cls.produced = {name: read_set(Path(cls.tmp.name) / 'out', name) for name in SETS}


    def test_every_shipped_extractor_matches_its_golden_snapshot(self):
        from eaos.facts.run import EXTRACTORS
        self.assertEqual(set(SETS) | {'history'}, set(EXTRACTORS),
                         'A new extractor needs a golden snapshot or an explicit reason to be excluded')
        for name in SETS:
            expected = json.loads((GOLDEN / f'{name}.json').read_text())
            with self.subTest(extractor=name):
                self.assertEqual(self.produced[name], expected,
                                 f'{name} output drifted; review the diff and regenerate the golden file deliberately')


class IncrementalCacheTests(unittest.TestCase):
    """A cached run must be cheaper but not different."""

    def test_a_cached_run_is_identical_and_only_a_changed_file_is_reparsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            shutil.copytree(FIXTURE, repo)
            out = Path(tmp) / 'out'
            collect(repo, out, SETS)
            first = (out / 'facts/syntax.json').read_bytes()
            warm = collect(repo, out, SETS)['reused_from_cache']['syntax']
            self.assertEqual((out / 'facts/syntax.json').read_bytes(), first)
            self.assertGreater(warm, 0)
            (repo / 'core/pricing.py').write_text('PREMIUM_DISCOUNT = 0.2\n')
            after_edit = collect(repo, out, SETS)['reused_from_cache']['syntax']
            self.assertEqual(after_edit, warm - 1, 'exactly one changed file should fall out of the cache')
            self.assertEqual(len(json.loads((out / 'facts/syntax-cache.json').read_text())), warm, 'the edited file\'s old entry is gone')
