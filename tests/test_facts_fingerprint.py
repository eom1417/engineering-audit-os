"""Structural fingerprints: the L3 detector that finds shape-duplicates ignoring names."""
import json
from pathlib import Path
import tempfile
import unittest
from eaos.facts.run import collect


def fingerprints(files):
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / 'repo'; repo.mkdir()
        for name, text in files.items():
            (repo / name).write_text(text)
        collect(repo, Path(tmp) / 'out', ['syntax', 'fingerprint'])
        return json.loads((Path(tmp) / 'out/facts/fingerprint.json').read_text())


def clusters(data):
    return [f for f in data['facts'] if f['kind'] == 'duplicate_cluster']


RULE = ("def {name}(amount, tier):\n"
        "    if tier == 'premium':\n"
        "        amount = amount * 0.9\n"
        "    tax = amount * 0.15\n"
        "    return round(amount + tax, 2)\n")


class FingerprintFactTests(unittest.TestCase):
    def test_one_rule_written_three_times_under_different_names_is_one_cluster(self):
        data = fingerprints({'canonical.py': RULE.format(name='compute_total'),
                             'orders.py': RULE.format(name='order_total'),
                             'billing.py': RULE.format(name='invoice_amount'),
                             'broken.py': 'def oops(:\n'})
        found = clusters(data)
        self.assertEqual(len(found), 1)
        occurrences = found[0]['value']['occurrences']
        self.assertEqual(sorted(o['name'] for o in occurrences), ['compute_total', 'invoice_amount', 'order_total'])
        self.assertEqual(sorted(o['path'] for o in occurrences), ['billing.py', 'canonical.py', 'orders.py'])
        self.assertEqual(data['summary']['files_blocked'], 1, 'an unparsable file is excluded, not fatal')

    def test_different_shapes_trivial_bodies_and_body_less_declarations_do_not_cluster(self):
        signatures = ''.join(f'export function f{i}(a: string, b: number, c: boolean, d: string[]): Promise<void>;\n'
                             for i in range(4))
        members = 'interface Api {\n' + ''.join(
            f'  m{i}(a: string, b: number, c: boolean, d: string[]): Promise<void>;\n' for i in range(4)) + '}\n'
        data = fingerprints({'a.py': 'def one(x):\n    return x + 1\n', 'b.py': 'def two(x):\n    return x * 2\n',
                             'c.py': 'def three(x):\n    return x\n', 'd.py': 'def four(y):\n    return y\n',
                             'core.d.ts': signatures, 'api.ts': members + signatures})
        self.assertEqual(clusters(data), [])
