"""Redundant-work facts (L5): the four structural hypotheses the engine can flag."""
from pathlib import Path
import tempfile
import unittest
from eaos.facts.run import collect
from eaos.facts.store import read_set

# (body, hypothesis kind, callees expected for that kind)
CASES = [
    ("def run():\n    x = lookup('a')\n    y = lookup('a')\n    return x + y\n", 'repeated_call', ['lookup']),
    ("def run():\n    x = lookup('a')\n    y = lookup('b')\n    return x + y\n", 'repeated_call', []),
    # Regression: two different no-argument calls were reported as one repeated call.
    ('def setup():\n    return 1\n\n\ndef teardown():\n    return 2\n\n\n'
     'def run():\n    setup()\n    teardown()\n    return 3\n', 'repeated_call', []),
    ("def run(items):\n    for item in items:\n        value = constant()\n        process(item, value)\n"
     "    return items\n", 'hoistable_call', ['constant']),
    ("def run(items):\n    for item in items:\n        process(item)\n    return items\n", 'hoistable_call', []),
    ("def run(orders):\n    for order in orders:\n        rows = order.items.filter_by(active=True)\n"
     "    return orders\n", 'n_plus_one', ['filter_by']),
    ("def run(items):\n    for x in items:\n        v = fetch(x)\n    return items\n", 'n_plus_one', ['fetch']),
    # A method call is not a query; treating every one as N+1 produced a thousand false claims.
    ("def run(orders):\n    for order in orders:\n        total = order.get_total()\n    return orders\n", 'n_plus_one', []),
    ("def wrapper(payload):\n    return inner(payload)\n", 'pass_through', ['inner']),
    ("def wrapper(payload):\n    cleaned = clean(payload)\n    return inner(cleaned)\n", 'pass_through', []),
]


class RedundancyFactTests(unittest.TestCase):
    def test_each_hypothesis_fires_on_its_shape_and_only_there(self):
        for body, kind, expected in CASES:
            with self.subTest(kind=kind, body=body), tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp) / 'repo'; repo.mkdir()
                (repo / 'app.py').write_text(body)
                collect(repo, Path(tmp) / 'out', ['syntax', 'structure', 'redundancy'])
                facts = read_set(Path(tmp) / 'out', 'redundancy')['facts']
                self.assertEqual([f['value']['callee'] for f in facts if f['value']['kind'] == kind], expected)
