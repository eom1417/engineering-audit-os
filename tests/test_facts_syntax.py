"""Multi-language syntax facts: parsed languages, honest status for the rest."""
import json
from pathlib import Path
import tempfile
import unittest
from eaos.facts import syntax
from eaos.facts.run import collect

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'


def syntax_of(repo):
    with tempfile.TemporaryDirectory() as tmp:
        collect(repo, Path(tmp) / 'out', ['syntax'])
        return json.loads((Path(tmp) / 'out/facts/syntax.json').read_text())


class SyntaxFactTests(unittest.TestCase):
    def test_python_typescript_and_go_are_parsed_into_symbols_and_imports(self):
        data = syntax_of(FIXTURE)
        kind = lambda name: [f for f in data['facts'] if f['kind'] == name]
        symbol = next(f for f in kind('symbol') if f['location']['symbol'] == 'price_for')
        self.assertEqual((symbol['value']['kind'], symbol['location']['path']), ('function', 'core/pricing.py'))
        self.assertGreater(symbol['location']['end_line'], symbol['location']['start_line'])
        observed = {f['value']['language'] for f in kind('source_file') if f['value']['parse_status'] == 'OBSERVED'}
        self.assertLessEqual({'python', 'typescript', 'go'}, observed)
        self.assertTrue({'createOrder', 'healthHandler'} <= {f['value']['name'] for f in kind('symbol')})
        modules = {(f['location']['path'], f['value']['module']): f for f in kind('import_edge')}
        relative = modules[('api/handlers/orders.ts', '../lib/pricing')]
        self.assertEqual((relative['value']['style'], relative['resolution']), ('relative', 'UNRESOLVED'))
        self.assertEqual(modules[('cli.py', 'core.pricing')]['value']['style'], 'absolute')
        # Manifests are not counted as unparsed source.
        self.assertEqual(data['summary']['parse_coverage'], 1.0)
        self.assertEqual(data['summary']['by_status'].get('NOT_SOURCE'), 2)

    def test_a_dynamic_import_is_an_edge_only_when_its_specifier_is_a_literal(self):
        units = syntax.parse_text('server/index.mjs', (
            'const R = [["/h", () => import("./routes/health.ts")], { load: () => import(`./routes/up.ts`) }];\n'
            'await import(new URL(spec, new URL("../server/", import.meta.url)).href);\n'
            'await import(`./pages/${name}.ts`);\nconst c = require("./c.cjs");\n'))[0]
        if units is None: self.skipTest('tree-sitter is not installed')
        self.assertEqual([entry['module'] for entry in units[1]], ['./routes/health.ts', './routes/up.ts', './c.cjs'])

    def test_an_unparsable_file_is_blocked_not_silently_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'broken.py').write_text('def oops(:\n')
            data = syntax_of(repo)
        self.assertEqual(data['summary']['by_status'], {'BLOCKED': 1})
        self.assertEqual(data['summary']['parse_coverage'], 0.0)
