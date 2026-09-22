"""Repeated call-sequence fingerprints (L4): same ordered list of callees."""
import json
from pathlib import Path
import tempfile
import unittest
from eaos.facts import sequences
from eaos.facts.run import collect


def _make(tmp, files):
    repo = Path(tmp) / 'repo'; repo.mkdir()
    for name, body in files.items():
        (repo / name).write_text(body)
    collect(repo, Path(tmp) / 'out', ['syntax', 'sequences'])
    return json.loads((Path(tmp) / 'out/facts/sequences.json').read_text())


class SequenceFactTests(unittest.TestCase):
    def test_three_functions_with_the_same_call_order_cluster(self):
        files = {'a.py':
                 "def first(p):\n    validate(p)\n    save(p)\n    notify(p)\n    return p\n"
                 "def second(p):\n    validate(p)\n    save(p)\n    notify(p)\n    return p\n"
                 "def third(p):\n    validate(p)\n    save(p)\n    notify(p)\n    return p\n"}
        with tempfile.TemporaryDirectory() as tmp:
            data = _make(tmp, files)
        clusters = data['facts']
        self.assertEqual(len(clusters), 1)
        seq = clusters[0]['value']['sequence']
        self.assertEqual(seq, ['validate', 'save', 'notify'])
        self.assertEqual(len(clusters[0]['value']['occurrences']), 3)

    def test_unrelated_orderings_do_not_cluster(self):
        files = {'a.py':
                 "def first(p):\n    validate(p)\n    notify(p)\n    save(p)\n    return p\n"
                 "def second(p):\n    save(p)\n    validate(p)\n    notify(p)\n    return p\n"
                 "def third(p):\n    notify(p)\n    save(p)\n    validate(p)\n    return p\n"}
        with tempfile.TemporaryDirectory() as tmp:
            data = _make(tmp, files)
        self.assertEqual(data['facts'], [])

    def test_two_functions_are_below_cluster_minimum(self):
        files = {'a.py':
                 "def first(p):\n    validate(p)\n    save(p)\n    notify(p)\n    return p\n"
                 "def second(p):\n    validate(p)\n    save(p)\n    notify(p)\n    return p\n"}
        with tempfile.TemporaryDirectory() as tmp:
            data = _make(tmp, files)
        self.assertEqual(data['facts'], [])

    def test_sequence_clusters_across_files(self):
        files = {'a.py': "def run(p):\n    validate(p)\n    save(p)\n    notify(p)\n    return p\n",
                 'b.py': "def run(p):\n    validate(p)\n    save(p)\n    notify(p)\n    return p\n",
                 'c.py': "def run(p):\n    validate(p)\n    save(p)\n    notify(p)\n    return p\n"}
        with tempfile.TemporaryDirectory() as tmp:
            data = _make(tmp, files)
        clusters = data['facts']
        self.assertEqual(len(clusters), 1)
        paths = sorted(occ['path'] for occ in clusters[0]['value']['occurrences'])
        self.assertEqual(paths, ['a.py', 'b.py', 'c.py'])

    def test_short_sequences_are_excluded(self):
        files = {'a.py':
                 "def first(x):\n    helper(x)\n    return x\n"
                 "def second(x):\n    helper(x)\n    return x\n"
                 "def third(x):\n    helper(x)\n    return x\n"}
        with tempfile.TemporaryDirectory() as tmp:
            data = _make(tmp, files)
        self.assertEqual(data['facts'], [])





class IdiomaticSequenceTests(unittest.TestCase):
    """Idiomatic call patterns are not duplicates. The detector must say so, not drop them."""

    FIXTURE = Path(__file__).resolve().parent / 'fixtures/idioms'

    def _collect_one(self, language, filename):
        # Copy only the file under test into a clean fixture so the duplicate file does
        # not pollute the idiom-only fixture (and vice versa).
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'src'; target.mkdir()
            (target / filename).write_text((self.FIXTURE / language / filename).read_text())
            out = Path(tmp) / 'out'
            collect(target, out, ['syntax', 'sequences'])
            return json.loads((out / 'facts/sequences.json').read_text())

    def test_python_idiom_test_does_not_cluster(self):
        data = self._collect_one('python', 'idiom_test.py')
        # Only one file is the idiom; no real duplicate cluster should appear.
        facts = data['facts']
        self.assertEqual(facts, [])
        # But the summary must report idiomatic exclusions.
        self.assertGreater(data['summary']['idiomatic_clusters_excluded'], 0)

    def test_python_duplicate_test_does_cloy(self):
        data = self._collect_one('python', 'duplicate_test.py')
        self.assertGreater(len(data['facts']), 0)
        seq = data['facts'][0]['value']['sequence']
        self.assertEqual(seq, ['validate', 'save', 'notify'])

    def test_go_idiom_test_does_not_cluster(self):
        data = self._collect_one('go', 'idiom_test.go')
        facts = data['facts']
        self.assertEqual(facts, [])

    def test_go_duplicate_test_does_cloy(self):
        data = self._collect_one('go', 'duplicate_test.go')
        self.assertGreater(len(data['facts']), 0)

    def test_javascript_idiom_test_does_not_cluster(self):
        data = self._collect_one('javascript', 'idiom_test.js')
        facts = data['facts']
        self.assertEqual(facts, [])

    def test_javascript_duplicate_test_does_cloy(self):
        data = self._collect_one('javascript', 'duplicate_test.js')
        self.assertGreater(len(data['facts']), 0)

    def test_idiom_set_is_exposed(self):
        self.assertIn('go', sequences.IDIOMS)
        self.assertIn('python', sequences.IDIOMS)
        self.assertIn('javascript', sequences.IDIOMS)
        self.assertIn('typescript', sequences.IDIOMS)

    def test_idiomatic_exclusion_is_recorded_not_silent(self):
        """Every idiomatic exclusion is logged in the summary; none are dropped silently."""
        data = self._collect_one("python", "idiom_test.py")
        self.assertIn('idiomatic_clusters_excluded', data['summary'])
        self.assertIn('idiomatic_clusters_by_language', data['summary'])
        self.assertGreater(data['summary']['idiomatic_clusters_excluded'], 0)
        self.assertGreater(data['summary']['idiomatic_clusters_by_language'].get('python', 0), 0)



class SequenceLimitationsTests(unittest.TestCase):
    def test_source_order_not_runtime_path(self):
        self.assertIn('source-order', ' '.join(sequences.LIMITATIONS))
