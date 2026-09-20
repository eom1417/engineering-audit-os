"""Traced flows and the source-of-truth view: the two artifacts that answer real questions."""
import json
from pathlib import Path
import tempfile
import unittest
from eaos.facts.run import collect
from eaos.facts.store import read_set

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'
SETS = ['syntax', 'resolve', 'entrypoints', 'config', 'metrics', 'domain', 'graph', 'flows']


class FlowTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        collect(FIXTURE, Path(cls.tmp.name) / 'out', SETS)
        cls.flows = {f['value']['flow_id']: f['value'] for f in read_set(Path(cls.tmp.name) / 'out', 'flows')['facts']}
        cls.summary = read_set(Path(cls.tmp.name) / 'out', 'flows')['summary']

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def flow_for(self, route, method=None):
        return next(flow for flow in self.flows.values()
                    if flow['entry']['route'] == route and (method is None or flow['entry']['http_method'] == method))

    def test_a_route_is_traced_into_the_module_that_implements_it(self):
        flow = self.flow_for('/orders', 'POST')
        self.assertEqual(flow['entry']['handler'], 'createOrder')
        self.assertIn('api/lib/pricing.ts', flow['touched_files'])
        step = next(step for step in flow['steps'] if step['callee'] == 'priceFor')
        self.assertEqual(step['resolution'], 'imported')
        self.assertEqual(step['to_path'], 'api/lib/pricing.ts')

    def test_every_step_carries_a_real_location(self):
        for flow in self.flows.values():
            for step in flow['steps']:
                self.assertTrue(step['from_path'])
                self.assertIsInstance(step['line'], int)

    def test_cross_file_python_flow_reaches_the_shared_rule(self):
        flow = self.flow_for('recalculate')
        self.assertIn('core/pricing.py', flow['touched_files'])
        self.assertIn('TAX_RATE', flow['environment_reads'])

    def test_library_and_builtin_calls_are_not_counted_as_gaps(self):
        self.assertEqual(self.summary['unresolved_steps'], 0)
        self.assertGreater(self.summary['steps_by_resolution']['method_or_external'], 0)

    def test_an_unresolvable_call_is_recorded_not_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'app.py').write_text(
                'import argparse\n\n\ndef handler():\n    return mystery_function()\n\n\n'
                'def main():\n    parser = argparse.ArgumentParser(prog="app")\n    handler()\n')
            collect(repo, Path(tmp) / 'out', SETS)
            flows = [f['value'] for f in read_set(Path(tmp) / 'out', 'flows')['facts']]
            steps = [step for flow in flows for step in flow['steps']]
            self.assertIn('mystery_function', [step['callee'] for step in steps])
            self.assertEqual(next(step for step in steps if step['callee'] == 'mystery_function')['resolution'], 'unresolved')


class DomainFactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        collect(FIXTURE, Path(cls.tmp.name) / 'out', SETS)
        cls.data = read_set(Path(cls.tmp.name) / 'out', 'domain')

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def test_a_rule_constant_duplicated_across_languages_is_found(self):
        fact = next(f for f in self.data['facts'] if f['value'].get('name') == 'PREMIUM_DISCOUNT')
        paths = {definition['path'] for definition in fact['value']['definitions']}
        self.assertEqual(paths, {'api/handlers/orders.ts', 'api/lib/pricing.ts', 'core/pricing.py'})
        self.assertTrue(fact['value']['duplicated'])
        self.assertTrue(fact['value']['same_value_everywhere'])

    def test_differing_values_for_the_same_rule_are_separated_from_matching_ones(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'checkout.py').write_text('DISCOUNT = 0.1\n')
            (repo / 'export.py').write_text('DISCOUNT = 0.15\n')
            collect(repo, Path(tmp) / 'out', SETS)
            summary = read_set(Path(tmp) / 'out', 'domain')['summary']
            self.assertEqual(summary['duplicated_with_different_values'], ['DISCOUNT'])
            self.assertEqual(summary['duplicated_with_same_value'], [])

    def test_data_models_and_tables_are_located(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'models.py').write_text('class Order(Model):\n    pass\n')
            (repo / 'schema.sql').write_text('CREATE TABLE orders (id int);\n')
            collect(repo, Path(tmp) / 'out', SETS)
            facts = read_set(Path(tmp) / 'out', 'domain')['facts']
            self.assertIn('Order', [f['value']['name'] for f in facts if f['kind'] == 'data_model'])
            self.assertIn('orders', [f['value']['name'] for f in facts if f['kind'] == 'data_table'])

    def test_duplication_is_framed_as_a_question_not_a_verdict(self):
        self.assertIn('not yet a defect', self.data['summary']['interpretation'])
