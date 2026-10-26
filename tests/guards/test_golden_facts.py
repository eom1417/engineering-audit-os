"""Golden fact snapshots: any change in extractor output must be seen and accepted deliberately.

Regenerate a snapshot by writing read_set(out, name) of a collect() of tests/fixtures/polyglot, as setUpClass makes it.
"""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from shared_fixture import TemporaryWorkspace
from eaos.facts.run import collect
from eaos.facts.store import read_set

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'fixtures/polyglot'
GOLDEN = ROOT / 'fixtures/golden'
SETS = ['syntax', 'resolve', 'structure', 'fingerprint', 'sequences', 'redundancy', 'runtime', 'entrypoints', 'config', 'metrics', 'domain', 'graph', 'flows', 'leftovers', 'deadcode', 'broken', 'secrets', 'pipeline', 'repository']


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
            out, cache = Path(tmp) / 'out', Path(tmp) / 'runtime/syntax-cache.json'    # its folder not made yet
            collect(repo, out, SETS, cache=cache)
            first = (out / 'facts/syntax.json').read_bytes()
            warm = collect(repo, out, SETS, cache=cache)['reused_from_cache']['syntax']
            self.assertEqual((out / 'facts/syntax.json').read_bytes(), first)
            self.assertGreater(warm, 0)
            self.assertFalse((out / 'facts/syntax-cache.json').exists(), 'a cache never sits in the report')
            (repo / 'core/pricing.py').write_text('PREMIUM_DISCOUNT = 0.2\n')
            after_edit = collect(repo, out, SETS, cache=cache)['reused_from_cache']['syntax']
            self.assertEqual(after_edit, warm - 1, 'exactly one changed file should fall out of the cache')
            self.assertEqual(len(json.loads(cache.read_text())), warm, 'the edited file\'s old entry is gone')


class StoreTests(unittest.TestCase):
    def test_a_set_reads_back_as_made_and_a_kind_is_read_from_the_sets_holding_it_only(self):
        # EAOS, 2026-10-23: the fields every fact repeated were half of each set, and every reader read all 280 MB
        from eaos.facts import make, store
        with tempfile.TemporaryDirectory() as out:
            rows = [make('symbol', 'syntax', '3', 'sha', {'path': f'a{i}.py'}, {'n': i}, limitations=['syntax only'])
                    for i in range(3)]
            entries = [store.write_set(out, 'syntax', 'syntax', '3', rows, 'sha', ['syntax only']),
                       store.write_set(out, 'graph', 'graph', '1', [], 'sha', [])]
            store.write_index(out, out, entries)
            self.assertNotIn('limitations', json.loads((Path(out) / 'facts/syntax.json').read_text())['facts'][0])
            self.assertEqual(read_set(out, 'syntax')['facts'], rows)
            (Path(out) / 'facts/graph.json').write_text('not json')     # never read: the index says it holds no symbol
            self.assertEqual(store.facts(out, 'symbol'), rows)
            self.assertEqual(store.by_id(out, [rows[1]['id']]), {rows[1]['id']: rows[1]})
