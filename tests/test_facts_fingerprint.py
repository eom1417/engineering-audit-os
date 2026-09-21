"""Structural fingerprints: the L3 detector that finds shape-duplicates ignoring names."""
import json
from pathlib import Path
import tempfile
import unittest
from eaos.facts import fingerprint
from eaos.facts.run import collect


def _make(tmp, body, name='app.py'):
    repo = Path(tmp) / 'repo'; repo.mkdir()
    (repo / name).write_text(body)
    collect(repo, Path(tmp) / 'out', ['syntax', 'fingerprint'])
    return json.loads((Path(tmp) / 'out/facts/fingerprint.json').read_text())


class FingerprintFactTests(unittest.TestCase):
    def test_two_functions_with_same_shape_under_different_names_cluster(self):
        body1 = (
            "def alpha(price, rate):\n"
            "    return round(price * (1 + rate), 2)\n"
        )
        body2 = (
            "def beta(cost, tax):\n"
            "    return round(cost * (1 + tax), 2)\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'a.py').write_text(body1); (repo / 'b.py').write_text(body2)
            collect(repo, Path(tmp) / 'out', ['syntax', 'fingerprint'])
            data = json.loads((Path(tmp) / 'out/facts/fingerprint.json').read_text())
        clusters = [f for f in data['facts'] if f['kind'] == 'duplicate_cluster']
        self.assertEqual(len(clusters), 1)
        occ = clusters[0]['value']['occurrences']
        names = sorted(o['name'] for o in occ)
        self.assertEqual(names, ['alpha', 'beta'])

    def test_three_implementations_of_pricing_rule_form_one_cluster(self):
        """The doctrine's reference example: compute_total in three places."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'canonical.py').write_text(
                "def compute_total(amount, tier):\n"
                "    if tier == 'premium':\n"
                "        amount = amount * 0.9\n"
                "    tax = amount * 0.15\n"
                "    return round(amount + tax, 2)\n"
            )
            (repo / 'orders.py').write_text(
                "def order_total(amount, tier):\n"
                "    if tier == 'premium':\n"
                "        amount = amount * 0.9\n"
                "    tax = amount * 0.15\n"
                "    return round(amount + tax, 2)\n"
            )
            (repo / 'billing.py').write_text(
                "def invoice_amount(amount, tier):\n"
                "    if tier == 'premium':\n"
                "        amount = amount * 0.9\n"
                "    tax = amount * 0.15\n"
                "    return round(amount + tax, 2)\n"
            )
            collect(repo, Path(tmp) / 'out', ['syntax', 'fingerprint'])
            data = json.loads((Path(tmp) / 'out/facts/fingerprint.json').read_text())
        clusters = [f for f in data['facts'] if f['kind'] == 'duplicate_cluster']
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0]['value']['occurrences']), 3)

    def test_structurally_different_functions_do_not_cluster(self):
        body1 = ("def one(x):\n    return x + 1\n")
        body2 = ("def two(x):\n    return x * 2\n")
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'a.py').write_text(body1); (repo / 'b.py').write_text(body2)
            collect(repo, Path(tmp) / 'out', ['syntax', 'fingerprint'])
            data = json.loads((Path(tmp) / 'out/facts/fingerprint.json').read_text())
        clusters = [f for f in data['facts'] if f['kind'] == 'duplicate_cluster']
        self.assertEqual(clusters, [])

    def test_trivial_one_line_functions_are_below_threshold(self):
        body1 = ("def one(x):\n    return x\n")
        body2 = ("def two(y):\n    return y\n")
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'a.py').write_text(body1); (repo / 'b.py').write_text(body2)
            collect(repo, Path(tmp) / 'out', ['syntax', 'fingerprint'])
            data = json.loads((Path(tmp) / 'out/facts/fingerprint.json').read_text())
        clusters = [f for f in data['facts'] if f['kind'] == 'duplicate_cluster']
        self.assertEqual(clusters, [])

    def test_clusters_report_path_and_line_for_each_member(self):
        body1 = ("def calc(x, y, z):\n    if x > 0:\n        return y + z\n    return y - z\n")
        body2 = ("def run(a, b, c):\n    if a > 0:\n        return b + c\n    return b - c\n")
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'first.py').write_text(body1); (repo / 'second.py').write_text(body2)
            collect(repo, Path(tmp) / 'out', ['syntax', 'fingerprint'])
            data = json.loads((Path(tmp) / 'out/facts/fingerprint.json').read_text())
        clusters = [f for f in data['facts'] if f['kind'] == 'duplicate_cluster']
        self.assertEqual(len(clusters), 1)
        paths = sorted(o['path'] for o in clusters[0]['value']['occurrences'])
        self.assertEqual(paths, ['first.py', 'second.py'])

    def test_unparsable_file_is_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'broken.py').write_text('def oops(:\n')
            (repo / 'good.py').write_text("def calc(x, y, z):\n    if x > 0:\n        return y + z\n    return y - z\n")
            (repo / 'good2.py').write_text("def run(a, b, c):\n    if a > 0:\n        return b + c\n    return b - c\n")
            collect(repo, Path(tmp) / 'out', ['syntax', 'fingerprint'])
            data = json.loads((Path(tmp) / 'out/facts/fingerprint.json').read_text())
        self.assertEqual(data['summary']['files_blocked'], 1)
        self.assertGreater(data['summary']['clusters'], 0)


class FingerprintLimitationsTests(unittest.TestCase):
    def test_fingerprints_are_observations_not_defects(self):
        self.assertIn('syntactic observation', ' '.join(fingerprint.LIMITATIONS))
