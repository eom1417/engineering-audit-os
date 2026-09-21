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


class SequenceLimitationsTests(unittest.TestCase):
    def test_source_order_not_runtime_path(self):
        self.assertIn('source-order', ' '.join(sequences.LIMITATIONS))
