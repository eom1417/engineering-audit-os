"""Broken code fails the first time it runs, or tells a reader to do what cannot be done."""
import json
import tempfile
import unittest
from pathlib import Path

from eaos.features.defects.facts import broken
from eaos.kernel.facts.run import collect


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
            return {(f['value']['rule'],
                     f['location']['symbol']) for f in json.loads((out / 'facts/broken.json').read_text())['facts']}

    def test_an_import_into_a_submodule_not_checked_out_is_not_missing(self):
        # An Angular app's playwright config imports from a git submodule; the folder is empty until
        # `git submodule update --init`, so the import is not missing.
        found = self.run_on({'.gitmodules': '[submodule "realworld"]\n\tpath = realworld\n\turl = '
                             'https://example.org/realworld.git\n',
                             'playwright.config.ts': "import { baseConfig } from "
                                 "'./realworld/specs/e2e/playwright.base';\n",
                             'src/a.ts': 'import { x } from "./gone";\n'})
        self.assertNotIn(('missing-import', './realworld/specs/e2e/playwright.base'), found)
        self.assertIn(('missing-import', './gone'), found)

    def test_a_command_that_runs_build_output_is_not_stale(self):
        # An Nx API's README runs `node dist/api/main.js`, which its build makes: no dist/ is committed, and the command
        # is not stale. Without a build script, the same command still is.
        files = {'package.json': '{"scripts": {"build": "tsc"}}', 'src/main.ts': 'export const x = 1;\n',
                 'README.md': '```\nnode dist/api/main.js\npython tools/gone.py\n```\n'}
        found = self.run_on(files)
        self.assertNotIn(('stale-instruction', 'node dist/api/main.js'), found)
        self.assertIn(('stale-instruction', 'python tools/gone.py'), found)
        self.assertIn(('stale-instruction', 'node dist/api/main.js'), self.run_on({**files,
            'package.json': '{"scripts": {"start": "node x.js"}}'}))

    def test_a_command_run_from_a_folder_the_document_names_is_not_stale(self):
        # A full-stack template's docs say `bash scripts/prestart.sh` "from the `backend` directory" (or after a `cd
        # backend`); the file is backend/scripts/prestart.sh, and the command must not be called broken.
        files = {'backend/scripts/prestart.sh': 'alembic upgrade head\n', 'backend/app/main.py': 'x = 1\n',
                 'development.md': 'From the `backend` directory:\n```bash\nuv run bash scripts/prestart.sh\n```\n',
                 'frontend/README.md': '```\ncd ../backend\nbash scripts/prestart.sh\nbash scripts/gone.sh\n```\n'}
        stale = {symbol for rule, symbol in self.run_on(files) if rule == 'stale-instruction'}
        self.assertEqual(stale, {'bash scripts/gone.sh'})

    def test_a_missing_import_and_stale_commands_in_docs_are_reported(self):
        found = self.run_on({
            'pyproject.toml': '[project.scripts]\ntool = "tool.cli:main"\n',
            'tool/cli.py': 'import argparse\np = argparse.ArgumentParser()\ns = p.add_subparsers()\n'
                           'for name in ("audit", "map"):\n    s.add_parser(name)\n',
            'package.json': '{"scripts": {"dev": "vite"}}',
            'src/pages/Old.tsx': 'import { api } from "@/lib/historyApi";\n',
            'src/lib/other.ts': 'export {};\n',
            'README.md': 'Run `tool audit`, then `tool next`.\n\n```\nnpm run dev\nnpm run build\npython '
                'scripts/gone.py\n```\n',
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
