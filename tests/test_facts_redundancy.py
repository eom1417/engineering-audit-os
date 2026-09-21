"""Redundant-work facts (L5): the four structural hypotheses the engine can flag."""
import json
from pathlib import Path
import tempfile
import unittest
from eaos.facts import redundancy
from eaos.facts.run import collect


def _collect(tmp, body, name='app.py'):
    repo = Path(tmp) / 'repo'; repo.mkdir()
    (repo / name).write_text(body)
    collect(repo, Path(tmp) / 'out', ['syntax', 'redundancy'])
    return json.loads((Path(tmp) / 'out/facts/redundancy.json').read_text())


class RedundancyFactTests(unittest.TestCase):
    def test_same_call_twice_in_a_function_is_a_repeated_call(self):
        body = ("def run():\n    x = lookup('a')\n    y = lookup('a')\n    return x + y\n")
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body)
        repeated = [f for f in data['facts'] if f['value']['kind'] == 'repeated_call']
        self.assertEqual(len(repeated), 1)
        self.assertEqual(repeated[0]['value']['callee'], 'lookup')

    def test_call_with_different_args_is_not_a_repeated_call(self):
        body = ("def run():\n    x = lookup('a')\n    y = lookup('b')\n    return x + y\n")
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body)
        self.assertEqual([f for f in data['facts'] if f['value']['kind'] == 'repeated_call'], [])

    def test_call_independent_of_loop_variable_is_hoistable(self):
        body = ("def run(items):\n    for item in items:\n        value = constant()\n        process(item, value)\n"
                "    return items\n")
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body)
        hoist = [f for f in data['facts'] if f['value']['kind'] == 'hoistable_call']
        self.assertEqual([h['value']['callee'] for h in hoist], ['constant'])

    def test_call_depending_on_loop_variable_is_not_hoistable(self):
        body = ("def run(items):\n    for item in items:\n        process(item)\n    return items\n")
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body)
        self.assertEqual([f for f in data['facts'] if f['value']['kind'] == 'hoistable_call'], [])

    def test_a_store_access_on_the_loop_value_is_n_plus_one(self):
        body = ("def run(orders):\n    for order in orders:\n        rows = order.items.filter_by(active=True)\n"
                "    return orders\n")
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body)
        np1 = [f for f in data['facts'] if f['value']['kind'] == 'n_plus_one']
        self.assertEqual([f['value']['callee'] for f in np1], ['filter_by'])

    def test_a_plain_method_call_on_the_loop_value_is_not_an_n_plus_one(self):
        """A method call is not a query; treating every one as N+1 produced a thousand false claims."""
        body = ("def run(orders):\n    for order in orders:\n        total = order.get_total()\n    return orders\n")
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body)
        self.assertEqual([f for f in data['facts'] if f['value']['kind'] == 'n_plus_one'], [])

    def test_named_data_access_call_in_a_loop_is_n_plus_one(self):
        body = ("def run(items):\n    for x in items:\n        v = fetch(x)\n    return items\n")
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body)
        np1 = [f for f in data['facts'] if f['value']['kind'] == 'n_plus_one']
        self.assertEqual(len(np1), 1)
        self.assertEqual(np1[0]['value']['callee'], 'fetch')

    def test_pass_through_forwards_the_parameter(self):
        body = ("def wrapper(payload):\n    return inner(payload)\n")
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body)
        passthrough = [f for f in data['facts'] if f['value']['kind'] == 'pass_through']
        self.assertEqual(len(passthrough), 1)
        self.assertEqual(passthrough[0]['value']['callee'], 'inner')

    def test_function_with_extra_work_is_not_a_pass_through(self):
        body = ("def wrapper(payload):\n    cleaned = clean(payload)\n    return inner(cleaned)\n")
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body)
        self.assertEqual([f for f in data['facts'] if f['value']['kind'] == 'pass_through'], [])


class RedundancyLimitationsTests(unittest.TestCase):
    def test_redundancy_is_observational(self):
        self.assertIn('structural hypothesis', ' '.join(redundancy.LIMITATIONS))


class SignatureIdentityTests(unittest.TestCase):
    """Regression: two different no-argument calls were reported as one repeated call."""

    def analyse(self, tmp, body):
        from eaos.facts.run import collect
        from eaos.facts.store import read_set
        repo = Path(tmp) / 'repo'; repo.mkdir(exist_ok=True)
        (repo / 'x.py').write_text(body)
        collect(repo, Path(tmp) / 'out', ['syntax', 'structure', 'redundancy'])
        return read_set(Path(tmp) / 'out', 'redundancy')

    def test_two_different_calls_are_not_a_repetition(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = self.analyse(tmp, 'def setup():\n    return 1\n\n\ndef teardown():\n    return 2\n\n\n'
                                     'def run():\n    setup()\n    teardown()\n    return 3\n')
            self.assertEqual([f for f in data['facts'] if f['value']['kind'] == 'repeated_call'], [])

    def test_the_same_call_twice_is_still_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = self.analyse(tmp, 'def fetch(user):\n    return user\n\n\n'
                                     'def run(user):\n    fetch(user)\n    fetch(user)\n    return 1\n')
            repeated = [f for f in data['facts'] if f['value']['kind'] == 'repeated_call']
            self.assertEqual(len(repeated), 1)
            self.assertEqual(repeated[0]['value']['callee'], 'fetch')

    def test_the_same_callee_with_different_arguments_is_not_a_repetition(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = self.analyse(tmp, 'def fetch(user):\n    return user\n\n\n'
                                     'def run(a, b):\n    fetch(a)\n    fetch(b)\n    return 1\n')
            self.assertEqual([f for f in data['facts'] if f['value']['kind'] == 'repeated_call'], [])
