"""Dead code is what no production path reaches and no text names; tests are not users."""
import json
import tempfile
import unittest
from pathlib import Path

from eaos.facts.run import collect

SETS = ['syntax', 'resolve', 'entrypoints', 'deadcode']


def dead_facts(files):
    with tempfile.TemporaryDirectory() as tmp:
        repo, out = Path(tmp) / 'repo', Path(tmp) / 'out'
        for name, text in files.items():
            (repo / name).parent.mkdir(parents=True, exist_ok=True)
            (repo / name).write_text(text)
        collect(repo, out, SETS)
        return json.loads((out / 'facts/deadcode.json').read_text())


def run(files):
    return {(f['value']['rule'], f['location']['symbol']): f['value']['message'] for f in dead_facts(files)['facts']}


APP = {
    'pkg/__main__.py': 'from pkg import app\napp.main()\n',
    'pkg/app.py': ('from pkg import helpers\nREGISTRY = {"format": "pretty"}\nLIMIT = 3\nUNUSED_LIMIT = 9\n\n'
                   'def main():\n    return helpers.used(LIMIT) + len(REGISTRY)\n\n'
                   'def _loop(n):\n    return _loop(n - 1) if n else 0\n\n'
                   'def only_tested():\n    return 1\n\n'
                   'def pretty():\n    return "named in a registry string"\n'),
    'pkg/helpers.py': 'def used(x):\n    return x\n',
    'pkg/orphan.py': 'def lonely():\n    return 0\n',
    'pkg/loaded.py': 'X = 1\n',
    'pkg/loader.py': '',
    'tests/test_app.py': 'from pkg import app, orphan\nassert app.only_tested() == 1\n',
    'examples/demo.py': 'def shown():\n    pass\n',
}
APP['pkg/app.py'] += 'import importlib\nmod = importlib.import_module("pkg.loaded")\n'


class DeadCodeTests(unittest.TestCase):
    def test_each_engine_way_of_naming_a_candidate_is_read_and_a_module_is_judged_by_eaos_reachability(self):
        from eaos.facts.deadcode import _candidate_name, _verdict
        named = lambda path, symbol, message='': _candidate_name({'message': message}, {'path': path, 'symbol': symbol})
        # As vulture, knip and enola write them (every vulture finding on EAOS was read as `py:act`, 2026-10-24).
        self.assertEqual(named('eaos/interfaces/terminal.py', 'eaos/interfaces/terminal.py:act'), 'act')
        self.assertEqual(named('src/routes.js', 'src/routes.js:routes'), 'routes')
        self.assertEqual(named('src/app/[slug]/page.tsx', 'src/app/[slug].generateMetadata'), 'generateMetadata')
        self.assertEqual(named('src/hero-post.tsx', 'src/hero-post.tsx', 'unused file `src/hero-post.tsx`'), 'src/hero-post.tsx')
        module = lambda ours: _verdict({}, {'path': 'src/hero-post.tsx'}, 'src/hero-post.tsx', ours, None)['verdict']
        self.assertEqual((module({('src/hero-post.tsx', 'src/hero-post.tsx')}), module(set())), ('confirmed', 'unconfirmed'))

    def test_what_only_tests_or_itself_use_is_dead_and_what_text_names_is_reached(self):
        data = dead_facts(APP)
        found = {(f['value']['rule'], f['location']['symbol']): f['value']['message'] for f in data['facts']}
        verdicts = {f['location']['symbol']: f['value']['adjudication']['verdict'] for f in data['facts']}
        self.assertIn('imported only by tests', found[('unreachable-module', 'pkg/orphan.py')])
        self.assertNotIn(('unreachable-module', 'pkg/loaded.py'), found, 'a module named in text is reached')
        self.assertIn('referenced only by tests', found[('unused-symbol', 'only_tested')])
        self.assertIn(('unused-symbol', '_loop'), found)
        # A name held in a registry string is referenced.
        self.assertNotIn(('unused-symbol', 'pretty'), found)
        self.assertNotIn(('unused-symbol', 'used'), found)
        self.assertIn('never read', found[('unread-constant', 'UNUSED_LIMIT')])
        self.assertNotIn(('unread-constant', 'LIMIT'), found)
        self.assertFalse([key for key in found if 'shown' in key or 'examples/demo.py' in key], 'examples are never candidates')
        # A name only tests read is a review candidate, not an asserted defect.
        self.assertEqual((verdicts['only_tested'], verdicts['_loop'], verdicts['pkg/orphan.py']),
                         ('test_only', 'confirmed', 'test_only'))

    def test_globals_lookup_keys_and_barrel_files_are_not_dead(self):
        cases = {
            'replacing a platform global': {
                'package.json': '{"name": "web", "main": "src/main.js"}',
                'src/main.js': 'import "./host.js";\nalert("hi");\n',
                'src/host.js': 'window.alert = (m) => console.log(m);\nwindow.confirm = () => true;\n'
                               'export function forgotten() { return 1; }\n'},
            'a function under a quoted key': {
                'package.json': '{"name": "web", "main": "src/main.js"}',
                'src/main.js': ('const SAY = {\n  \'past-empty\': (m) => `${m} passed`,\n  empty: (m) => `${m} empty`,\n};\n'
                                'export const say = (state, m) => SAY[state](m);\n')},
            'a module behind a barrel file': {
                'index.html': '<script type="module" src="/src/main.tsx"></script>',
                'src/main.tsx': 'import { Dialog } from "./components";\nDialog();\n',
                'src/components/index.ts': 'export { Dialog } from "./Dialog";\nexport * from "./types";\n',
                'src/components/Dialog.tsx': 'export function Dialog() { return 1; }\n',
                'src/components/types.ts': 'export const KIND = 1;\n',
                'src/global.d.ts': 'declare global {\n  interface Window { app: number }\n}\n'}}
        for case, files in cases.items():
            with self.subTest(case=case):
                found = run(files)
                self.assertFalse([key for key in found if key[0] == 'unreachable-module'], found)
                self.assertFalse([key for key in found if key[1] and (key[1].startswith('window.') or key[1] == "'past-empty'")], found)

    def test_built_start_scripts_dynamic_imports_and_tool_configs_reach_their_modules(self):
        found = run({'app/package.json': '{"type": "module", "scripts": {"start": "node dist-server/main.mjs"}}',
                     'app/server/main.mjs': 'import { handle } from "./index.mjs";\nhandle();\n',
                     'app/server/index.mjs': ('import { claimAttempt } from "./security/rate-limit.ts";\n'
                                              'const ROUTES = [\n  ["/api/health", () => import("./routes/health.ts")],\n'
                                              '  { path: "/api/up", load: async () => await import(`./routes/up.ts`) },\n];\n'
                                              'export function handle() { return claimAttempt(ROUTES); }\n'),
                     'app/server/security/rate-limit.ts': 'export function claimAttempt(r) { return r; }\n',
                     'app/server/routes/health.ts': 'export function GET() { return 1; }\n',
                     'app/server/routes/up.ts': 'export function GET() { return 1; }\n',
                     'app/server/routes/gone.ts': 'export function GET() { return 1; }\n',
                     'app/tests/rate.test.mjs': 'import { claimAttempt } from "../server/security/rate-limit.ts";\n'})
        self.assertEqual({key for key in found if key[0] == 'unreachable-module'}, {('unreachable-module', 'app/server/routes/gone.ts')})
        # A module a tool config loads by a path relative to itself is reached.
        found = run({'app/package.json': '{"scripts": {"dev": "vite"}}',
                     'app/index.html': '<script type="module" src="/src/main.ts"></script>',
                     'app/src/main.ts': 'document.title = "x";\n',
                     'app/vite.config.ts': ('const entry = new URL("./server/index.mjs", import.meta.url).href;\n'
                                            'export default { plugins: [{ configureServer: async () => (await import(entry)).handle }] };\n'),
                     'app/server/index.mjs': 'import { guard } from "./guard.ts";\nexport function handle() { return guard(); }\n',
                     'app/server/guard.ts': 'export function guard() { return 1; }\n'})
        self.assertFalse([key for key in found if key[0] == 'unreachable-module'], found)

    def test_what_a_build_script_hands_its_bundler_or_loads_is_reached(self):
        # EAOS's own Studio (2026-10-24): esbuild's entry points and the words the build imports are computed paths,
        # and 96 of its modules were said to be dead
        build = ("import path from 'node:path';\nimport { fileURLToPath, pathToFileURL } from 'node:url';\nimport * as esbuild from 'esbuild';\n"
                 "const HERE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');\nconst SRC = path.join(HERE, 'src');\n"
                 "await esbuild.build({ entryPoints: [path.join(SRC, 'core/main.js')], outfile: path.join(HERE, 'out/main.js') });\n"
                 "for (const place of ['a']) await esbuild.build({ entryPoints: [path.join(SRC, 'places', place, 'index.js')] });\n"
                 "for (const file of ['ar.js']) await import(pathToFileURL(path.join(SRC, 'words', file)).href);\n")
        found = run({'pkg/__main__.py': 'print(1)\n', 'console/package.json': '{"scripts": {"build": "node scripts/build.mjs"}}',
                     'console/scripts/build.mjs': build, 'console/src/core/main.js': 'import { go } from "./go.js";\ngo();\n',
                     'console/src/core/go.js': 'export function go() {}\n', 'console/src/places/a/index.js': 'document.title = "a";\n',
                     'console/src/words/ar.js': 'export default {};\n', 'console/src/places/a/deep/gone.js': 'export const x = 1;\n'})
        self.assertEqual({key[1] for key in found if key[0] == 'unreachable-module'}, {'console/src/places/a/deep/gone.js'})

    def test_without_an_entry_point_only_private_names_are_judged(self):
        found = run({'lib/api.py': 'def public():\n    return 1\n\ndef _private():\n    return 2\n'})
        self.assertEqual(set(found), {('unused-symbol', '_private')})

    def test_a_module_nothing_imports_is_confirmed_and_a_program_nothing_runs_is_a_review_candidate(self):
        data = dead_facts({'package.json': '{"main": "src/main.js", "scripts": {"audit": "node scripts/audit.mjs"}}',
                           'src/main.js': 'export const x = 1;\n', 'src/lost.js': 'export const y = 1;\n',
                           'scripts/audit.mjs': 'console.log(1);\n', 'scripts/by-hand.mjs': 'console.log(2);\n',
                           'scripts/in-ci.mjs': 'console.log(3);\n', 'scripts/documented.mjs': 'console.log(4);\n',
                           '.github/workflows/ci.yml': 'jobs:\n  a:\n    steps:\n      - run: node scripts/in-ci.mjs\n',
                           'README.md': 'Run `node --import tsx scripts/documented.mjs --write` after a change.\n'})
        verdicts = {f['location']['symbol']: f['value']['adjudication']['verdict'] for f in data['facts'] if f['value']['rule'] == 'unreachable-module'}
        self.assertEqual(verdicts, {'src/lost.js': 'confirmed', 'scripts/by-hand.mjs': 'review'})
        from eaos.analysis import claims
        rendered = {row['render']['params']['subject']: (row['render']['key'], row['confidence']) for row in claims.from_facts({'deadcode': data})}
        self.assertEqual(rendered['scripts/by-hand.mjs'], ('dead_code_review', 'LIKELY'))
        self.assertEqual(rendered['src/lost.js'], ('dead_code', 'CONFIRMED'))

    def test_files_loaded_by_path_package_data_rule_fixtures_and_types_are_not_dead_classes_or_modules(self):
        # The self-audit: `Path(__file__).parent / 'templates/screens/stream-reporter.mjs'` loads a file no import
        # names; a k6 template ships as declared package data; a semgrep rule test carries `# ruleid:` lines; and
        # an unused TypeScript type was called an "unused class".
        found = run({'pyproject.toml': '[tool.setuptools.package-data]\npkg = ["templates/**/*", "rules/*.json"]\n',
                     'pkg/__init__.py': '', 'pkg/__main__.py': 'from pkg import lock\nlock.run()\n',
                     'pkg/lock.py': ('from pathlib import Path\n'
                                     "REPORTER = Path(__file__).resolve().parent / 'screens/stream-reporter.mjs'\n"
                                     'def run():\n    return REPORTER\n'),
                     'pkg/screens/stream-reporter.mjs': 'export default class StreamReporter {}\n',
                     'pkg/templates/k6/load.js': 'export default function () {}\nexport const OPTIONS = {};\n',
                     'pkg/checks/dynamic.py': 'def f(x):\n    # ruleid: pkg.dynamic-code\n    return eval(x)\n',
                     'index.html': '<script type="module" src="/web/main.ts"></script>',
                     'web/main.ts': 'import { words } from "./words";\nwords();\n',
                     'web/words.ts': 'export type BranchWord = string;\nexport function words() { return 1; }\n'})
        self.assertFalse([key for key in found if key[1] != 'BranchWord'], found)
        self.assertIn('unused type', found[('unused-symbol', 'BranchWord')])
