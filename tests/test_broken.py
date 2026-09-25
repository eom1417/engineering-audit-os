"""Broken code fails the first time it runs, or tells a reader to do what cannot be done."""
import json
import tempfile
import unittest
from pathlib import Path

from eaos.facts import broken
from eaos.facts.run import collect


class UndefinedNameTests(unittest.TestCase):
    def test_a_name_imported_in_one_function_and_used_in_another_is_undefined(self):
        text = ('def one():\n    from os import sep as SEP\n    return SEP\n\n'
                'def two():\n    return SEP\n')
        self.assertEqual(broken.undefined_names(text, 'cli.py'), [('SEP', 6)])

    def test_closures_conditional_definitions_builtins_and_star_imports_are_not_reported(self):
        self.assertEqual(broken.undefined_names('try:\n    import json\nexcept ImportError:\n    json = None\n'
                                                'def f(x):\n    y = [i for i in x]\n    def g():\n        return y\n'
                                                '    return g, len(x), json\n', 'a.py'), [])
        self.assertEqual(broken.undefined_names('from os import *\nprint(path)\n', 'b.py'), [])

    def test_a_key_written_twice_with_different_values_loses_the_first(self):
        self.assertEqual(broken.duplicate_keys('X = {"a": 1, "b": 2, "a": 3}\nY = {"c": 1, "c": 1}\n'), [('a', 1, 1)])


class BrokenProjectTests(unittest.TestCase):
    def run_on(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            repo, out = Path(tmp) / 'repo', Path(tmp) / 'out'
            for name, text in files.items():
                (repo / name).parent.mkdir(parents=True, exist_ok=True)
                (repo / name).write_text(text)
            collect(repo, out, ['syntax', 'resolve', 'broken'])
            return {(f['value']['rule'], f['location']['symbol']) for f in json.loads((out / 'facts/broken.json').read_text())['facts']}

    def test_a_missing_import_and_stale_commands_in_docs_are_reported(self):
        found = self.run_on({
            'pyproject.toml': '[project.scripts]\ntool = "tool.cli:main"\n',
            'tool/cli.py': 'import argparse\np = argparse.ArgumentParser()\ns = p.add_subparsers()\n'
                           'for name in ("audit", "map"):\n    s.add_parser(name)\n',
            'package.json': '{"scripts": {"dev": "vite"}}',
            'src/pages/Old.tsx': 'import { api } from "@/lib/historyApi";\n',
            'src/lib/other.ts': 'export {};\n',
            'README.md': 'Run `tool audit`, then `tool next`.\n\n```\nnpm run dev\nnpm run build\npython scripts/gone.py\n```\n'})
        self.assertIn(('missing-import', '@/lib/historyApi'), found)
        self.assertIn(('stale-instruction', 'tool next'), found)
        self.assertIn(('stale-instruction', 'npm run build'), found)
        self.assertIn(('stale-instruction', 'python scripts/gone.py'), found)
        self.assertNotIn(('stale-instruction', 'tool audit'), found)
        self.assertNotIn(('stale-instruction', 'npm run dev'), found)


if __name__ == '__main__':
    unittest.main()
