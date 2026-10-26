"""Broken code fails the first time it runs, or tells a reader to do what cannot be done."""
import json
import tempfile
import unittest
from pathlib import Path

from eaos.facts.defects import broken
from eaos.facts.run import collect


class BrokenCodeTests(unittest.TestCase):
    def test_undefined_names_and_overwritten_keys_are_found_without_false_alarms(self):
        text = ('def one():\n    from os import sep as SEP\n    return SEP\n\n'
                'def two():\n    return SEP\n')
        self.assertEqual(broken.undefined_names(text, 'cli.py'), [('SEP', 6)])
        # Closures, conditional definitions, builtins and star imports are not reported.
        self.assertEqual(broken.undefined_names('try:\n    import json\nexcept ImportError:\n    json = None\n'
                                                'def f(x):\n    y = [i for i in x]\n    def g():\n        return y\n'
                                                '    return g, len(x), json\n', 'a.py'), [])
        self.assertEqual(broken.undefined_names('from os import *\nprint(path)\n', 'b.py'), [])
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
            'README.md': 'Run `tool audit`, then `tool next`.\n\n```\nnpm run dev\nnpm run build\npython scripts/gone.py\n```\n',
            'posts/empty.md': 'An empty block (SvelteKit blog starter):\n```\n```\n'})
        self.assertIn(('missing-import', '@/lib/historyApi'), found)
        for symbol in ('tool next', 'npm run build', 'python scripts/gone.py'):
            self.assertIn(('stale-instruction', symbol), found)
        self.assertNotIn(('stale-instruction', 'tool audit'), found)
        self.assertNotIn(('stale-instruction', 'npm run dev'), found)

    def test_script_families_placeholders_and_app_folder_commands_are_not_stale(self):
        found = self.run_on({
            'app/package.json': '{"scripts": {"deploy:staging": "x", "deploy:production": "y"}}',
            'app/scripts/baseline.mjs': 'export {};\n',
            'README.md': '`npm run deploy:*` refuses; run `node scripts/baseline.mjs`, not `npm run release:*`.\n',
            'CLAUDE.md': ('`npm run deploy:<target>` refuses; so do `npm run deploy:{env}`, `npm run deploy:$ENV`, '
                          '`npm run deploy:[name]` and `npm run deploy:…`; `npm run release:<target>` is gone.\n')})
        stale = {symbol for rule, symbol in found if rule == 'stale-instruction'}
        self.assertEqual(stale, {'npm run release:*', 'npm run release:<target>'})
