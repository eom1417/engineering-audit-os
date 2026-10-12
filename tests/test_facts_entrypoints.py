"""Entry-point detection: matched surfaces only, and undetectable ones declared as gaps."""
import json
from pathlib import Path
import tempfile
import unittest
from eaos.facts.run import collect

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'


def load(root, repo, sets=('syntax', 'entrypoints')):
    collect(repo, Path(root) / 'out', list(sets))
    return json.loads((Path(root) / 'out/facts/entrypoints.json').read_text())


def load_files(files):
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / 'repo'
        for name, text in files.items():
            (repo / name).parent.mkdir(parents=True, exist_ok=True)
            (repo / name).write_text(text)
        return load(tmp, repo)


class EntryPointTests(unittest.TestCase):
    def test_routes_cli_jobs_and_manifest_surfaces_are_found_across_languages(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = load(tmp, FIXTURE)
        rows = [f['value'] | {'resolution': f['resolution']} for f in data['facts']]
        http = {(r['http_method'], r['route']) for r in rows if r['surface'] == 'http'}
        self.assertTrue({('GET', '/orders'), ('POST', '/orders'), ('DELETE', '/orders/:id'), ('ANY', '/health')} <= http)
        handler = next(r for r in rows if r['route'] == '/orders' and r['http_method'] == 'POST')
        self.assertEqual((handler['handler'], handler['resolution']), ('createOrder', 'RESOLVED'))
        pairs = {(r['route'], r['framework']) for r in rows}
        self.assertTrue({('polyglot', 'argparse'), ('recalculate', 'celery')} <= pairs)
        self.assertIn('npm run start', {r['route'] for r in rows})

    def test_nothing_is_invented_for_a_library_without_entry_points(self):
        data = load_files({'lib.py': 'VALUE = 1\n\n\ndef helper():\n    return VALUE\n'})
        self.assertEqual(data['facts'], [])
        self.assertEqual(data['summary']['entry_points'], 0)

    def test_runtime_registered_commands_are_declared_as_gaps_not_hidden(self):
        data = load_files({'tool.py': 'import argparse\n\n\ndef main():\n    parser = argparse.ArgumentParser(prog="tool")\n'
                                      '    sub = parser.add_subparsers()\n    for command in ["a", "b"]:\n'
                                      '        sub.add_parser(command)\n'})
        dynamic = [f for f in data['facts'] if f['value']['framework'] == 'argparse_dynamic']
        self.assertEqual(len(dynamic), 1)
        self.assertIsNone(dynamic[0]['value']['route'])
        self.assertEqual(dynamic[0]['resolution'], 'UNRESOLVED')

    def test_dockerfile_makefile_and_main_guarded_scripts_are_surfaces(self):
        rows = [f['value'] for f in load_files({
            'Dockerfile': 'FROM python:3.12\nCMD ["python", "-m", "app"]\n',
            'Makefile': '.PHONY: test\ntest:\n\tpytest\n',
            'render.py': 'def render():\n    return 1\n\n\nif __name__ == "__main__":\n    raise SystemExit(render())\n'})['facts']]
        self.assertIn('container', {r['surface'] for r in rows})
        self.assertIn('make test', {r['route'] for r in rows})
        script = next(row for row in rows if row['framework'] == 'python_script')
        self.assertEqual((script['route'], script['handler'], script['surface']), ('render', 'render', 'cli'))

    def test_go_main_needs_package_main_and_func_main_and_receiver_handlers_are_routes(self):
        data = load_files({
            'cmd/x/main.go': 'package main\n\nimport "fmt"\n\nfunc main() {\n    fmt.Println("hi")\n}\n',
            'helpers/helpers.go': 'package main\n\nfunc helper() {}\n',
            'lib/lib.go': 'package lib\n\nfunc main() {}\n',
            'server/server.go': 'package main\n\nimport "net/http"\n\ntype Server struct{}\n\n'
                                'func (s *Server) handleIndex(w http.ResponseWriter, r *http.Request) {}\n\n'
                                'func main() {\n    s := &Server{}\n    http.HandleFunc("/", s.handleIndex)\n}\n'})
        mains = {f['location']['path']: f['value'] for f in data['facts'] if f['value']['framework'] == 'go_main'}
        self.assertEqual(set(mains), {'cmd/x/main.go', 'server/server.go'})
        self.assertEqual((mains['cmd/x/main.go']['surface'], mains['cmd/x/main.go']['handler']), ('cli', 'main'))
        route = next(f['value'] for f in data['facts'] if f['value']['surface'] == 'http')
        self.assertEqual((route['handler'], route['framework']), ('s.handleIndex', 'go_http'))


class TaskRunnerScriptTests(unittest.TestCase):
    """A package.json script or a Makefile target is an entry point when it runs a file of the repository;
    when it only runs an external tool it is a tool command, never an entry point without a handler."""

    def facts(self, files):
        data = load_files(files)
        return {f['value']['route']: f for f in data['facts']}, data['summary']

    def test_npm_scripts_are_traced_to_the_program_they_run(self):
        scripts = {'start': 'node server.js', 'dev': 'vite', 'typecheck': 'tsc --noEmit', 'test': 'vitest run',
                   'lint': 'eslint src/app.ts', 'ship': 'NODE_ENV=production npx tsx scripts/ship.ts --fast',
                   'build': 'npm run lint && vite build && node scripts/pack.mjs', 'check': 'pnpm typecheck',
                   'gates': '../.venv/bin/python ../tools/gates.py --strict', 'outside': 'node ../../elsewhere.js'}
        facts, summary = self.facts({'web/package.json': json.dumps({'scripts': scripts}),
                                     'loop/package.json': json.dumps({'scripts': {'a': 'npm run b', 'b': 'npm run a'}})})
        handlers = {route[len('npm run '):]: fact['value']['handler'] for route, fact in facts.items()
                    if fact['kind'] == 'entry_point'}
        self.assertEqual(handlers, {'start': 'web/server.js', 'ship': 'web/scripts/ship.ts',
                                    'build': 'web/scripts/pack.mjs', 'gates': 'tools/gates.py'})
        tools = {route[len('npm run '):]: fact['value']['tools'] for route, fact in facts.items()
                 if fact['kind'] == 'tool_command' and route not in ('npm run a', 'npm run b')}
        # A file handed to a linter is read, not run; a path outside the repository is no handler of it.
        self.assertEqual(tools, {'dev': ['vite'], 'typecheck': ['tsc'], 'test': ['vitest'], 'lint': ['eslint'],
                                 'check': ['tsc'], 'outside': ['node']})
        # Scripts that call each other in a cycle end, as tool commands.
        self.assertEqual({facts['npm run a']['kind'], facts['npm run b']['kind']}, {'tool_command'})
        self.assertEqual(facts['npm run start']['resolution'], 'RESOLVED')
        self.assertEqual(summary['production_entry_points'], 4)
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
