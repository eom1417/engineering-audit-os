"""Dead code is what no production path reaches and no text names; tests are not users."""
import json
import tempfile
import unittest
from pathlib import Path

from eaos.facts.run import collect

SETS = ['syntax', 'resolve', 'entrypoints', 'deadcode']


def run(files):
    with tempfile.TemporaryDirectory() as tmp:
        repo, out = Path(tmp) / 'repo', Path(tmp) / 'out'
        for name, text in files.items():
            (repo / name).parent.mkdir(parents=True, exist_ok=True)
            (repo / name).write_text(text)
        collect(repo, out, SETS)
        return {(f['value']['rule'], f['location']['symbol']): f['value']['message']
                for f in json.loads((out / 'facts/deadcode.json').read_text())['facts']}


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
    def test_a_module_only_tests_import_is_unreachable(self):
        found = run(APP)
        self.assertIn(('unreachable-module', 'pkg/orphan.py'), found)
        self.assertIn('imported only by tests', found[('unreachable-module', 'pkg/orphan.py')])

    def test_a_module_named_in_text_is_reached(self):
        self.assertNotIn(('unreachable-module', 'pkg/loaded.py'), run(APP))

    def test_a_function_only_tests_or_itself_call_is_unused(self):
        found = run(APP)
        self.assertIn(('unused-symbol', 'only_tested'), found)
        self.assertIn('referenced only by tests', found[('unused-symbol', 'only_tested')])
        self.assertIn(('unused-symbol', '_loop'), found)

    def test_replacing_a_platform_global_is_not_dead_code(self):
        found = run({'package.json': '{"name": "web", "main": "src/main.js"}',
                     'src/main.js': 'import "./host.js";\nalert("hi");\n',
                     'src/host.js': 'window.alert = (m) => console.log(m);\nwindow.confirm = () => true;\n'
                                    'export function forgotten() { return 1; }\n'})
        self.assertFalse([key for key in found if key[1] and key[1].startswith('window.')], found)

    def test_a_name_held_in_a_registry_string_is_referenced(self):
        found = run(APP)
        self.assertNotIn(('unused-symbol', 'pretty'), found)
        self.assertNotIn(('unused-symbol', 'used'), found)

    def test_a_constant_nothing_reads_is_reported_and_one_read_is_not(self):
        found = run(APP)
        self.assertIn(('unread-constant', 'UNUSED_LIMIT'), found)
        self.assertIn('never read', found[('unread-constant', 'UNUSED_LIMIT')])
        self.assertNotIn(('unread-constant', 'LIMIT'), found)

    def test_examples_and_tests_are_never_candidates(self):
        found = run(APP)
        self.assertFalse([key for key in found if 'shown' in key or 'examples/demo.py' in key])

    def test_a_module_behind_a_barrel_file_is_reached(self):
        found = run({'index.html': '<script type="module" src="/src/main.tsx"></script>',
                     'src/main.tsx': 'import { Dialog } from "./components";\nDialog();\n',
                     'src/components/index.ts': 'export { Dialog } from "./Dialog";\nexport * from "./types";\n',
                     'src/components/Dialog.tsx': 'export function Dialog() { return 1; }\n',
                     'src/components/types.ts': 'export const KIND = 1;\n',
                     'src/global.d.ts': 'declare global {\n  interface Window { app: number }\n}\n'})
        self.assertFalse([key for key in found if key[0] == 'unreachable-module'], found)

    def test_the_source_of_a_built_start_script_is_an_entry_and_its_ts_and_dynamic_imports_are_reached(self):
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

    def test_a_module_a_tool_config_loads_by_a_path_relative_to_itself_is_reached(self):
        found = run({'app/package.json': '{"scripts": {"dev": "vite"}}',
                     'app/index.html': '<script type="module" src="/src/main.ts"></script>',
                     'app/src/main.ts': 'document.title = "x";\n',
                     'app/vite.config.ts': ('const entry = new URL("./server/index.mjs", import.meta.url).href;\n'
                                            'export default { plugins: [{ configureServer: async () => (await import(entry)).handle }] };\n'),
                     'app/server/index.mjs': 'import { guard } from "./guard.ts";\nexport function handle() { return guard(); }\n',
                     'app/server/guard.ts': 'export function guard() { return 1; }\n'})
        self.assertFalse([key for key in found if key[0] == 'unreachable-module'], found)

    def test_without_an_entry_point_only_private_names_are_judged(self):
        found = run({'lib/api.py': 'def public():\n    return 1\n\ndef _private():\n    return 2\n'})
        self.assertEqual(set(found), {('unused-symbol', '_private')})


if __name__ == '__main__':
    unittest.main()


class VerdictTests(unittest.TestCase):
    def test_a_name_only_tests_read_is_a_review_candidate_not_an_asserted_defect(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, out = Path(tmp) / 'repo', Path(tmp) / 'out'
            for name, text in APP.items():
                (repo / name).parent.mkdir(parents=True, exist_ok=True)
                (repo / name).write_text(text)
            collect(repo, out, SETS)
            verdicts = {f['location']['symbol']: f['value']['adjudication']['verdict']
                        for f in json.loads((out / 'facts/deadcode.json').read_text())['facts']}
        self.assertEqual(verdicts['only_tested'], 'test_only')
        self.assertEqual(verdicts['_loop'], 'confirmed')
        self.assertEqual(verdicts['pkg/orphan.py'], 'confirmed')
