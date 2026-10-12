"""Repeated call-sequence fingerprints (L4): same ordered list of callees."""
import json
from pathlib import Path
import tempfile
import unittest
from eaos.facts.run import collect

IDIOMS = Path(__file__).resolve().parent / 'fixtures/idioms'
CHAIN = "def {name}(p):\n    validate(p)\n    save(p)\n    notify(p)\n    return p\n"


def sequences_of(files):
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / 'repo'; repo.mkdir()
        for name, body in files.items():
            (repo / name).write_text(body)
        collect(repo, Path(tmp) / 'out', ['syntax', 'sequences'])
        return json.loads((Path(tmp) / 'out/facts/sequences.json').read_text())


class SequenceFactTests(unittest.TestCase):
    def test_the_same_call_order_in_three_places_is_one_cluster_within_and_across_files(self):
        for files, paths in [({'a.py': ''.join(CHAIN.format(name=n) for n in ('first', 'second', 'third'))}, ['a.py'] * 3),
                             ({f'{n}.py': CHAIN.format(name='run') for n in 'abc'}, ['a.py', 'b.py', 'c.py'])]:
            with self.subTest(paths=paths):
                clusters = sequences_of(files)['facts']
                self.assertEqual(len(clusters), 1)
                self.assertEqual(clusters[0]['value']['sequence'], ['validate', 'save', 'notify'])
                self.assertEqual(sorted(o['path'] for o in clusters[0]['value']['occurrences']), paths)

    def test_different_orders_two_copies_and_short_sequences_do_not_cluster(self):
        cases = {'unrelated orders': "def first(p):\n    validate(p)\n    notify(p)\n    save(p)\n    return p\n"
                                     "def second(p):\n    save(p)\n    validate(p)\n    notify(p)\n    return p\n"
                                     "def third(p):\n    notify(p)\n    save(p)\n    validate(p)\n    return p\n",
                 'below the minimum': CHAIN.format(name='first') + CHAIN.format(name='second'),
                 'too short': ''.join(f"def {n}(x):\n    helper(x)\n    return x\n" for n in ('first', 'second', 'third'))}
        for case, body in cases.items():
            with self.subTest(case=case):
                self.assertEqual(sequences_of({'a.py': body})['facts'], [])

    def test_idiomatic_patterns_are_excluded_visibly_and_real_duplicates_still_cluster(self):
        for language, ext in [('python', 'py'), ('go', 'go'), ('javascript', 'js')]:
            with self.subTest(language=language):
                idiom = sequences_of({f'idiom_test.{ext}': (IDIOMS / language / f'idiom_test.{ext}').read_text()})
                self.assertEqual(idiom['facts'], [])
                duplicate = sequences_of({f'duplicate_test.{ext}': (IDIOMS / language / f'duplicate_test.{ext}').read_text()})
                self.assertTrue(duplicate['facts'])
        python = sequences_of({'idiom_test.py': (IDIOMS / 'python/idiom_test.py').read_text()})['summary']
        self.assertGreater(python['idiomatic_clusters_excluded'], 0, 'an idiom is reported, never dropped silently')
        self.assertGreater(python['idiomatic_clusters_by_language'].get('python', 0), 0)
