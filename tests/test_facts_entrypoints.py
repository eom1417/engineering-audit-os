"""Entry-point detection: matched surfaces only, and undetectable ones declared as gaps."""
import json
from pathlib import Path
import tempfile
import unittest
from shared_fixture import TemporaryWorkspace
from eaos.facts.run import collect

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'


def load(root, repo, sets=('syntax', 'entrypoints')):
    collect(repo, Path(root) / 'out', list(sets))
    return json.loads((Path(root) / 'out/facts/entrypoints.json').read_text())


class EntryPointTests(TemporaryWorkspace):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data = load(cls.tmp.name, FIXTURE)
        cls.rows = [f['value'] | {'path': f['location']['path'], 'resolution': f['resolution']} for f in cls.data['facts']]


    def routes(self, surface): return {(r['http_method'], r['route']) for r in self.rows if r['surface'] == surface}

    def test_http_routes_are_found_across_languages(self):
        self.assertIn(('GET', '/orders'), self.routes('http'))
        self.assertIn(('POST', '/orders'), self.routes('http'))
        self.assertIn(('DELETE', '/orders/:id'), self.routes('http'))
        self.assertIn(('ANY', '/health'), self.routes('http'))

    def test_handlers_are_linked_to_real_symbols(self):
        handler = next(r for r in self.rows if r['route'] == '/orders' and r['http_method'] == 'POST')
        self.assertEqual(handler['handler'], 'createOrder')
        self.assertEqual(handler['resolution'], 'RESOLVED')

    def test_cli_jobs_and_manifest_surfaces_are_covered(self):
        self.assertIn(('polyglot', 'argparse'), {(r['route'], r['framework']) for r in self.rows})
        self.assertIn(('recalculate', 'celery'), {(r['route'], r['framework']) for r in self.rows})
        self.assertIn('npm run start', {r['route'] for r in self.rows})

    def test_nothing_is_invented_for_a_project_without_entry_points(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'lib.py').write_text('VALUE = 1\n\n\ndef helper():\n    return VALUE\n')
            data = load(tmp, repo)
            self.assertEqual(data['facts'], [])
            self.assertEqual(data['summary']['entry_points'], 0)

    def test_runtime_registered_commands_are_declared_as_gaps_not_hidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'tool.py').write_text(
                'import argparse\n\n\ndef main():\n    parser = argparse.ArgumentParser(prog="tool")\n'
                '    sub = parser.add_subparsers()\n    for command in ["a", "b"]:\n        sub.add_parser(command)\n')
            data = load(tmp, repo)
            dynamic = [f for f in data['facts'] if f['value']['framework'] == 'argparse_dynamic']
            self.assertEqual(len(dynamic), 1)
            self.assertIsNone(dynamic[0]['value']['route'])
            self.assertEqual(dynamic[0]['resolution'], 'UNRESOLVED')
            self.assertIn('built at runtime', dynamic[0]['value']['note'])

    def test_dockerfile_and_makefile_surfaces_are_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'Dockerfile').write_text('FROM python:3.12\nCMD ["python", "-m", "app"]\n')
            (repo / 'Makefile').write_text('.PHONY: test\ntest:\n\tpytest\n')
            rows = [f['value'] for f in load(tmp, repo)['facts']]
            self.assertIn('container', {r['surface'] for r in rows})
            self.assertIn('make test', {r['route'] for r in rows})

    def test_detection_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            collect(FIXTURE, Path(tmp) / 'a', ['syntax', 'entrypoints']); collect(FIXTURE, Path(tmp) / 'b', ['syntax', 'entrypoints'])
            self.assertEqual((Path(tmp) / 'a/facts/entrypoints.json').read_bytes(), (Path(tmp) / 'b/facts/entrypoints.json').read_bytes())

    def test_a_script_guarded_by_main_is_an_entry_point(self):
        """A runnable script looked unreachable because its __main__ guard was not a surface."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'render.py').write_text('def render():\n    return 1\n\n\nif __name__ == "__main__":\n'
                                            '    raise SystemExit(render())\n')
            rows = [f['value'] for f in load(tmp, repo)['facts']]
            script = next(row for row in rows if row['framework'] == 'python_script')
            self.assertEqual(script['route'], 'render')
            self.assertEqual(script['handler'], 'render')
            self.assertEqual(script['surface'], 'cli')

    def test_a_module_without_a_main_guard_is_not_an_entry_point(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'lib.py').write_text('def helper():\n    return 1\n')
            self.assertEqual([f for f in load(tmp, repo)['facts']
                              if f['value']['framework'] == 'python_script'], [])


class TaskRunnerScriptTests(unittest.TestCase):
    """A package.json script or a Makefile target is an entry point when it runs a file of the repository;
    when it only runs an external tool it is a tool command, never an entry point without a handler."""

    def facts(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            for name, text in files.items():
                (repo / name).parent.mkdir(parents=True, exist_ok=True)
                (repo / name).write_text(text)
            data = load(tmp, repo)
        return {f['value']['route']: f for f in data['facts']}, data['summary']

    def test_npm_scripts_are_traced_to_the_program_they_run(self):
        scripts = {'start': 'node server.js', 'dev': 'vite', 'typecheck': 'tsc --noEmit', 'test': 'vitest run',
                   'lint': 'eslint src/app.ts', 'ship': 'NODE_ENV=production npx tsx scripts/ship.ts --fast',
                   'build': 'npm run lint && vite build && node scripts/pack.mjs', 'check': 'pnpm typecheck',
                   'gates': '../.venv/bin/python ../tools/gates.py --strict', 'outside': 'node ../../elsewhere.js'}
        facts, summary = self.facts({'web/package.json': json.dumps({'scripts': scripts})})
        handlers = {route[len('npm run '):]: fact['value']['handler'] for route, fact in facts.items()
                    if fact['kind'] == 'entry_point'}
        self.assertEqual(handlers, {'start': 'web/server.js', 'ship': 'web/scripts/ship.ts',
                                    'build': 'web/scripts/pack.mjs', 'gates': 'tools/gates.py'})
        tools = {route[len('npm run '):]: fact['value']['tools'] for route, fact in facts.items()
                 if fact['kind'] == 'tool_command'}
        # A file handed to a linter is read, not run; a path outside the repository is no handler of it.
        self.assertEqual(tools, {'dev': ['vite'], 'typecheck': ['tsc'], 'test': ['vitest'], 'lint': ['eslint'],
                                 'check': ['tsc'], 'outside': ['node']})
        self.assertEqual(facts['npm run start']['resolution'], 'RESOLVED')
        self.assertEqual(summary['production_entry_points'], 4)
        self.assertEqual(summary['tool_commands'], 6)
        self.assertEqual(summary['by_framework'], {'npm_script': 4})

    def test_make_targets_follow_their_recipes_and_prerequisites(self):
        makefile = ('.PHONY: all test run serve\n'
                    'all: run\n'
                    'test:\n\t@pytest -q\n'
                    'run:\n\tpython app.py --port 8000\n'
                    'serve:\n\t$(PYTHON) -m pkg.server\n'
                    'lint: ; ruff check .\n'
                    'out.txt:\n')
        facts, _ = self.facts({'Makefile': makefile})
        self.assertEqual(facts['make all']['value']['handler'], 'app.py')
        self.assertEqual(facts['make run']['value']['handler'], 'app.py')
        self.assertEqual(facts['make serve']['value']['handler'], 'pkg/server.py')
        self.assertEqual((facts['make test']['kind'], facts['make test']['value']['tools']), ('tool_command', ['pytest']))
        self.assertEqual((facts['make lint']['kind'], facts['make lint']['value']['tools']), ('tool_command', ['ruff']))
        # A target with nothing to run is no evidence either way: it stays a declared entry point without a handler.
        self.assertEqual((facts['make out.txt']['kind'], facts['make out.txt']['value']['handler']), ('entry_point', None))
        self.assertEqual(facts['make run']['location']['start_line'], 5)

    def test_scripts_that_call_each_other_in_a_cycle_end(self):
        facts, _ = self.facts({'package.json': json.dumps({'scripts': {'a': 'npm run b', 'b': 'npm run a'}})})
        self.assertEqual({fact['kind'] for fact in facts.values()}, {'tool_command'})


class GoMainPackageTests(TemporaryWorkspace):
    """`package main` + `func main()` is the binary's entry point: surface=cli, framework=go_main.

    The detector only fires when both pieces are present; either alone is not a runtime surface.
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()

    def test_cmd_x_main_go_with_package_main_and_func_main_is_an_entry_point(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'cmd/x').mkdir(parents=True)
            (repo / 'cmd/x/main.go').write_text('package main\n\nimport "fmt"\n\n'
                                                 'func main() {\n    fmt.Println("hi")\n}\n')
            rows = [f['value'] for f in load(tmp, repo)['facts']]
        main_entry = next((r for r in rows if r['framework'] == 'go_main'), None)
        self.assertIsNotNone(main_entry)
        self.assertEqual(main_entry['surface'], 'cli')
        self.assertEqual(main_entry['handler'], 'main')
        self.assertEqual(main_entry['route'], 'main')

    def test_a_package_main_file_without_func_main_does_not_emit_a_go_main_entry_point(self):
        """A library file that happens to start with `package main` is not an entry point."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'helpers.go').write_text('package main\n\nfunc helper() {}\n')
            rows = [f['value'] for f in load(tmp, repo)['facts']]
        self.assertEqual([r for r in rows if r['framework'] == 'go_main'], [])

    def test_a_non_main_package_with_func_main_does_not_emit_a_go_main_entry_point(self):
        """`func main` only counts in a `package main` file; anything else is a collision."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'lib.go').write_text('package lib\n\nfunc main() {}\n')
            rows = [f['value'] for f in load(tmp, repo)['facts']]
        self.assertEqual([r for r in rows if r['framework'] == 'go_main'], [])

    def test_http_handler_with_receiver_is_an_entry_point(self):
        """A receiver-method handler like `s.handleIndex` registers as an http route."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'server.go').write_text(
                'package main\n\n'
                'import "net/http"\n\n'
                'type Server struct{}\n\n'
                'func (s *Server) handleIndex(w http.ResponseWriter, r *http.Request) {}\n\n'
                'func main() {\n'
                '    s := &Server{}\n'
                '    http.HandleFunc("/", s.handleIndex)\n'
                '}\n')
            rows = [f['value'] for f in load(tmp, repo)['facts']]
        http_route = next((r for r in rows if r['surface'] == 'http'), None)
        self.assertIsNotNone(http_route)
        self.assertEqual(http_route['handler'], 's.handleIndex')
        self.assertEqual(http_route['framework'], 'go_http')
