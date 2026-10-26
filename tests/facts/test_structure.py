"""Structure facts: the substrate every redundancy detector below stands on."""
import json
from pathlib import Path
import tempfile
import unittest
from eaos.facts.run import collect


def structure_of(files, sets=('syntax', 'structure')):
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / 'repo'; repo.mkdir()
        for name, body in files.items():
            (repo / name).write_text(body)
        collect(repo, Path(tmp) / 'out', list(sets))
        return json.loads((Path(tmp) / 'out/facts/structure.json').read_text())


class StructureFactTests(unittest.TestCase):
    def test_loops_branches_and_call_sites_with_their_enclosing_symbol(self):
        data = structure_of({'app.py': (
            "def loop(items):\n    total = 0\n    for item in items:\n        if item > 0:\n"
            "            helper(item)\n            helper(item)\n    while total > 100:\n        total = total - 1\n"
            "    return total\n"
            "def outer():\n    def nested():\n        return other(1)\n    return nested()\n"
            "class Container:\n    def run(self):\n        return self.method()\n")})
        self.assertEqual((data['summary']['loops'], data['summary']['branches']), (2, 1))
        self.assertTrue({'loop', 'branch', 'scope'} <= {f['kind'] for f in data['facts']})
        sites = [f for f in data['facts'] if f['kind'] == 'call_site']
        self.assertEqual({s['location']['symbol'] for s in sites if s['value']['callee'] == 'helper'}, {'<module>.loop'})
        self.assertEqual(len([s for s in sites if s['value']['callee'] == 'helper']), 2)
        for site in sites:
            self.assertTrue(site['location']['symbol'].startswith('<module>.'))
        method = next(s for s in sites if s['value']['callee'] == 'method')
        self.assertTrue(method['value']['attribute'])

    def test_an_unparsable_file_is_recorded_as_such(self):
        data = structure_of({'broken.py': 'def oops(:\n'}, sets=('structure',))
        self.assertEqual(data['summary']['files_blocked'], 1)
        self.assertEqual(data['summary']['parse_coverage'], 0.0)
