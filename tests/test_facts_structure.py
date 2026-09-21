"""Structure facts: the substrate every redundancy detector below stands on."""
import json
from pathlib import Path
import tempfile
import unittest
from eaos.facts import structure
from eaos.facts.run import collect


def _collect(tmp, body, name='app.py'):
    repo = Path(tmp) / 'repo'; repo.mkdir()
    (repo / name).write_text(body)
    collect(repo, Path(tmp) / 'out', ['syntax', 'structure'])
    return json.loads((Path(tmp) / 'out/facts/structure.json').read_text())


class StructureFactTests(unittest.TestCase):
    def test_loop_and_branch_are_each_separately_recorded(self):
        body = (
            "def loop(items):\n"
            "    total = 0\n"
            "    for item in items:\n"
            "        if item > 0:\n"
            "            total = total + item\n"
            "    while total > 100:\n"
            "        total = total - 1\n"
            "    return total\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body)
        kinds = [f['kind'] for f in data['facts']]
        self.assertEqual(data['summary']['loops'], 2)
        self.assertEqual(data['summary']['branches'], 1)
        self.assertIn('loop', kinds); self.assertIn('branch', kinds); self.assertIn('scope', kinds)

    def test_call_site_carries_its_enclosing_symbol(self):
        body = (
            "def outer():\n"
            "    def nested():\n"
            "        return helper(1)\n"
            "    return nested()\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body)
        sites = [f for f in data['facts'] if f['kind'] == 'call_site']
        self.assertEqual(len(sites), 2)
        for site in sites: self.assertTrue(site['location']['symbol'].startswith('<module>.'))

    def test_attribute_calls_are_marked(self):
        body = (
            "class Container:\n"
            "    def run(self):\n"
            "        return self.helper()\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body)
        site = next(f for f in data['facts'] if f['kind'] == 'call_site')
        self.assertEqual(site['value']['callee'], 'helper')
        self.assertTrue(site['value']['attribute'])

    def test_unparsable_file_is_recorded_as_such(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'broken.py').write_text('def oops(:\n')
            collect(repo, Path(tmp) / 'out', ['structure'])
            data = json.loads((Path(tmp) / 'out/facts/structure.json').read_text())
            self.assertEqual(data['summary']['files_blocked'], 1)
            self.assertEqual(data['summary']['parse_coverage'], 0.0)

    def test_extraction_is_deterministic(self):
        body = ("def loop(items):\n"
                 "    for item in items:\n"
                 "        if item:\n"
                 "            helper(item)\n"
                 "    return items\n")
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'app.py').write_text(body)
            collect(repo, Path(tmp) / 'a', ['syntax', 'structure'])
            collect(repo, Path(tmp) / 'b', ['syntax', 'structure'])
            self.assertEqual((Path(tmp) / 'a/facts/structure.json').read_bytes(),
                             (Path(tmp) / 'b/facts/structure.json').read_bytes())

    def test_two_calls_in_the_same_loop_have_the_same_enclosing_symbol(self):
        body = (
            "def loop(items):\n"
            "    for item in items:\n"
            "        helper(item)\n"
            "        helper(item)\n"
            "    return items\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body)
        sites = [f for f in data['facts'] if f['kind'] == 'call_site' and f['value']['callee'] == 'helper']
        self.assertEqual(len(sites), 2)
        self.assertEqual({s['location']['symbol'] for s in sites}, {'<module>.loop'})


class StructureLimitationsTests(unittest.TestCase):
    def test_static_observations_are_not_runtime_traces(self):
        self.assertIn('syntactic observation', ' '.join(structure.LIMITATIONS))
