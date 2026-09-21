"""Multi-language syntax facts: parsed languages, honest status for the rest."""
import json
from pathlib import Path
import tempfile
import unittest
from shared_fixture import TemporaryWorkspace
from eaos.facts import syntax
from eaos.facts.run import collect

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'


class SyntaxFactTests(TemporaryWorkspace):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        collect(FIXTURE, Path(cls.tmp.name) / 'out', ['syntax'])
        cls.data = json.loads((Path(cls.tmp.name) / 'out/facts/syntax.json').read_text())


    def kind(self, kind): return [f for f in self.data['facts'] if f['kind'] == kind]

    def test_python_symbols_carry_qualified_names_and_ranges(self):
        symbol = next(f for f in self.kind('symbol') if f['location']['symbol'] == 'price_for')
        self.assertEqual(symbol['value']['kind'], 'function')
        self.assertEqual(symbol['location']['path'], 'core/pricing.py')
        self.assertGreater(symbol['location']['end_line'], symbol['location']['start_line'])

    def test_typescript_and_go_are_parsed_not_guessed(self):
        languages = {f['value']['language'] for f in self.kind('source_file') if f['value']['parse_status'] == 'OBSERVED'}
        self.assertLessEqual({'python', 'typescript', 'go'}, languages)
        self.assertIn('createOrder', {f['value']['name'] for f in self.kind('symbol')})
        self.assertIn('healthHandler', {f['value']['name'] for f in self.kind('symbol')})

    def test_imports_record_style_and_stay_unresolved_until_the_resolver_runs(self):
        modules = {(f['location']['path'], f['value']['module']): f for f in self.kind('import_edge')}
        relative = modules[('api/handlers/orders.ts', '../lib/pricing')]
        self.assertEqual(relative['value']['style'], 'relative')
        self.assertEqual(relative['resolution'], 'UNRESOLVED')
        self.assertEqual(modules[('cli.py', 'core.pricing')]['value']['style'], 'absolute')

    def test_manifests_are_not_counted_as_unparsed_source(self):
        summary = self.data['summary']
        self.assertEqual(summary['parse_coverage'], 1.0)
        self.assertEqual(summary['by_status'].get('NOT_SOURCE'), 2)

    def test_unparsable_file_is_blocked_not_silently_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'broken.py').write_text('def oops(:\n')
            collect(repo, Path(tmp) / 'out', ['syntax'])
            data = json.loads((Path(tmp) / 'out/facts/syntax.json').read_text())
            self.assertEqual(data['summary']['by_status'], {'BLOCKED': 1})
            self.assertEqual(data['summary']['parse_coverage'], 0.0)

    def test_extraction_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            collect(FIXTURE, Path(tmp) / 'a', ['syntax']); collect(FIXTURE, Path(tmp) / 'b', ['syntax'])
            self.assertEqual((Path(tmp) / 'a/facts/syntax.json').read_bytes(), (Path(tmp) / 'b/facts/syntax.json').read_bytes())

    def test_parser_absence_is_declared_rather_than_approximated(self):
        self.assertIn('Dynamic imports', ' '.join(syntax.LIMITATIONS))
        self.assertTrue(self.data['summary']['tree_sitter_available'] in (True, False))
