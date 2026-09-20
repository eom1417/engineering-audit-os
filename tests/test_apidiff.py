"""What changing the public surface would break for a consumer."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from eaos import cli
from eaos.apidiff import compare, run, surface
from eaos.facts.run import collect
from eaos.facts.store import read_set


def snapshot(root, name, body):
    repo = Path(root) / name
    repo.mkdir(parents=True)
    (repo / 'api.py').write_text(body)
    out = Path(root) / (name + '-out')
    collect(repo, out, ['syntax'])
    return out


BEFORE = 'def charge(amount, currency):\n    return amount\n\n\ndef refund(amount):\n    return -amount\n'


class ApiDiffTests(unittest.TestCase):
    def test_a_removed_function_is_breaking(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = snapshot(tmp, 'before', BEFORE)
            after = snapshot(tmp, 'after', 'def charge(amount, currency):\n    return amount\n')
            result = run(before, after)
            self.assertEqual(result['status'], 'BREAKING')
            self.assertEqual(result['counts']['removed'], 1)
            self.assertIn('api.py::refund', result['breaking'])

    def test_a_removed_parameter_is_breaking(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = snapshot(tmp, 'before', BEFORE)
            after = snapshot(tmp, 'after', BEFORE.replace('charge(amount, currency)', 'charge(amount)'))
            result = run(before, after)
            self.assertEqual(result['status'], 'BREAKING')
            detail = json.loads((Path(after) / 'api-diff.json').read_text())
            self.assertEqual(detail['changed'][0]['removed_parameters'], ['currency'])

    def test_an_added_function_is_not_breaking(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = snapshot(tmp, 'before', BEFORE)
            after = snapshot(tmp, 'after', BEFORE + '\n\ndef quote(amount):\n    return amount\n')
            result = run(before, after)
            self.assertEqual(result['status'], 'COMPATIBLE')
            self.assertEqual(result['counts']['added'], 1)

    def test_an_optional_parameter_added_at_the_end_is_not_breaking(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = snapshot(tmp, 'before', BEFORE)
            after = snapshot(tmp, 'after', BEFORE.replace('charge(amount, currency)', 'charge(amount, currency, note=None)'))
            result = run(before, after)
            self.assertEqual(result['status'], 'COMPATIBLE')
            self.assertEqual(result['counts']['changed'], 1)

    def test_private_and_test_symbols_are_outside_the_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; (repo / 'tests').mkdir(parents=True)
            (repo / 'api.py').write_text('def _hidden():\n    return 1\n\n\ndef shown():\n    return 2\n')
            (repo / 'tests/test_api.py').write_text('def test_shown():\n    assert True\n')
            out = Path(tmp) / 'out'
            collect(repo, out, ['syntax'])
            names = {row['name'] for row in surface({'syntax': read_set(out, 'syntax')}).values()}
            self.assertEqual(names, {'shown'})

    def test_the_gate_can_fail_the_build_on_a_break(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = snapshot(tmp, 'before', BEFORE)
            after = snapshot(tmp, 'after', 'def charge(amount, currency):\n    return amount\n')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(['api-diff', str(before), str(after), '--fail-on-breaking']), 2)
                self.assertEqual(cli.main(['api-diff', str(before), str(after)]), 0)

    def test_comparison_is_pure_and_symmetric_in_reporting(self):
        before = {'a.py::f': {'path': 'a.py', 'name': 'f', 'kind': 'function', 'signature': ['x'], 'required': 1, 'line': 1}}
        self.assertEqual(compare(before, before)['counts'], {'removed': 0, 'changed': 0, 'added': 0, 'breaking': 0})
