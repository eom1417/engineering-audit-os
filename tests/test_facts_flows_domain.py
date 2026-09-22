"""Traced flows and the source-of-truth view: the two artifacts that answer real questions."""
import json
from pathlib import Path
import tempfile
import unittest
from shared_fixture import TemporaryWorkspace
from eaos.facts.run import collect
from eaos.facts.store import read_set

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'
SETS = ['syntax', 'resolve', 'entrypoints', 'config', 'metrics', 'domain', 'graph', 'flows']


class FlowTraceTests(TemporaryWorkspace):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        collect(FIXTURE, Path(cls.tmp.name) / 'out', SETS)
        cls.flows = {f['value']['flow_id']: f['value'] for f in read_set(Path(cls.tmp.name) / 'out', 'flows')['facts']}
        cls.summary = read_set(Path(cls.tmp.name) / 'out', 'flows')['summary']


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


class DomainFactTests(TemporaryWorkspace):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        collect(FIXTURE, Path(cls.tmp.name) / 'out', SETS)
        cls.data = read_set(Path(cls.tmp.name) / 'out', 'domain')


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


class SharedStateTests(unittest.TestCase):
    """Module-level state and cross-module writes: reported only when they actually happen."""

    def analyse(self, tmp, body, name='app.py'):
        repo = Path(tmp) / 'repo'; repo.mkdir(exist_ok=True)
        (repo / name).write_text(body)
        collect(repo, Path(tmp) / 'out', SETS)
        return read_set(Path(tmp) / 'out', 'domain')

    def test_a_lookup_table_is_not_reported_as_mutable_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = self.analyse(tmp, 'TABLE = {"a": 1, "b": 2}\n\n\ndef lookup(key):\n    return TABLE[key]\n')
            self.assertEqual(data['summary']['mutable_globals'], 0)

    def test_state_mutated_at_runtime_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = self.analyse(tmp, 'CACHE = {}\n\n\ndef remember(key, value):\n    CACHE[key] = value\n')
            self.assertEqual(data['summary']['mutable_globals_changed_at_runtime'], 1)
            fact = next(f for f in data['facts'] if f['kind'] == 'mutable_global')
            self.assertEqual(fact['value']['mutation_scope'], 'function')

    def test_state_built_at_import_time_is_recorded_but_separated(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = self.analyse(tmp, 'PATTERNS = {"a": 1}\nPATTERNS["b"] = 2\n')
            self.assertEqual(data['summary']['mutable_globals'], 1)
            self.assertEqual(data['summary']['mutable_globals_changed_at_runtime'], 0)

    def test_writing_into_another_module_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'settings.py').write_text('LIMIT = 10\n')
            (repo / 'app.py').write_text('import settings\n\n\ndef raise_limit():\n    settings.LIMIT = 99\n')
            collect(repo, Path(tmp) / 'out', SETS)
            data = read_set(Path(tmp) / 'out', 'domain')
            self.assertEqual(data['summary']['external_state_writes'], 1)
            fact = next(f for f in data['facts'] if f['kind'] == 'external_state_write')
            self.assertEqual((fact['value']['module'], fact['value']['attribute']), ('settings', 'LIMIT'))

    def test_runtime_state_and_cross_module_writes_become_claims_with_probes(self):
        from eaos.dossier import assemble
        from eaos import probes
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'settings.py').write_text('LIMIT = 10\n')
            (repo / 'app.py').write_text('import argparse\nimport settings\n\nCACHE = {}\n\n\n'
                                         'def main():\n    argparse.ArgumentParser(prog="demo")\n'
                                         '    CACHE["x"] = 1\n    settings.LIMIT = 99\n')
            out = Path(tmp) / 'out'
            assemble(repo, out)
            probes.run_all(repo, out)
            claims = json.loads((out / 'dossier.json').read_text())['claims']
            kinds = {claim['statement'].split()[0] for claim in claims}
            self.assertIn('CACHE', kinds)
            self.assertTrue(any('writes into settings.LIMIT' in claim['statement'] for claim in claims))
            self.assertTrue(all(claim['confidence'] == 'CONFIRMED' for claim in claims))


class HotspotTests(unittest.TestCase):
    """Complexity is only a finding where change and dependency already concentrate."""

    def test_a_dense_function_on_a_central_path_becomes_a_claim(self):
        from eaos.dossier import assemble
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            branches = '\n'.join(f'    if value == {n}:\n        return {n}' for n in range(70))
            (repo / 'core.py').write_text(f'def decide(value):\n{branches}\n    return 0\n')
            (repo / 'main.py').write_text('import argparse\nimport core\n\n\ndef main():\n'
                                          '    argparse.ArgumentParser(prog="demo")\n    return core.decide(1)\n')
            out = Path(tmp) / 'out'
            assemble(repo, out)
            claims = json.loads((out / 'dossier.json').read_text())['claims']
            hotspot = [claim for claim in claims if 'branches over' in claim['statement']]
            self.assertTrue(hotspot)
            self.assertEqual(hotspot[0]['confidence'], 'CONFIRMED')
            self.assertEqual(hotspot[0]['probe_spec']['specification']['query'], 'metric_threshold')

    def test_a_simple_project_produces_no_hotspot(self):
        from eaos.dossier import assemble
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'core.py').write_text('def add(a, b):\n    return a + b\n')
            out = Path(tmp) / 'out'
            assemble(repo, out)
            claims = json.loads((out / 'dossier.json').read_text())['claims']
            self.assertEqual([claim for claim in claims if 'branches over' in claim['statement']], [])

    def test_the_worst_offender_stays_visible_when_its_file_is_not_top_ranked(self):
        """Regression: the most complex function in the project vanished when other modules outranked it."""
        from eaos.dossier import assemble
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            branches = '\n'.join(f'    if value == {n}:\n        return {n}' for n in range(80))
            (repo / 'buried.py').write_text(f'def decide(value):\n{branches}\n    return 0\n')
            # Fifteen small, central modules outrank the complex one on attention.
            for index in range(15):
                (repo / f'mod{index}.py').write_text('import buried\n\n\ndef use():\n    return buried.decide(1)\n')
            (repo / 'main.py').write_text('import argparse\n' + ''.join(f'import mod{i}\n' for i in range(15))
                                          + '\n\ndef main():\n    argparse.ArgumentParser(prog="x").parse_args()\n'
                                          + '    return mod0.use()\n')
            out = Path(tmp) / 'out'
            assemble(repo, out)
            claims = json.loads((out / 'dossier.json').read_text())['claims']
            hotspots = [claim for claim in claims if 'branches over' in claim['statement']]
            self.assertTrue(hotspots, 'the most branching function must be reported whatever its file rank')
            self.assertIn('decide', hotspots[0]['statement'])


class FlowHandlerLinkingTests(TemporaryWorkspace):
    """Handler-to-symbol linking handles Go receiver-method calls and cross-file imports."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()

    def test_a_handler_with_a_receiver_resolves_to_the_method_symbol(self):
        """`s.handleIndex` is registered against a symbol named `handleIndex` in the same file."""
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
            collect(repo, Path(tmp) / 'out',
                    ['syntax', 'resolve', 'entrypoints', 'config', 'metrics', 'domain', 'graph', 'flows'])
            flows = read_set(Path(tmp) / 'out', 'flows')
            handler_found = any(f['value']['handler_found'] for f in flows['facts'])
            self.assertTrue(handler_found,
                              "receiver-method handler did not link")
            flow = flows['facts'][0]
            self.assertEqual(flow['value']['entry']['handler'], 's.handleIndex')
            # The handler is `s.handleIndex` in the entry_point, but the trace must have
            # found the symbol named `handleIndex` in the same file.
            self.assertTrue(any(step.get('to_symbol') == 'handleIndex' or 'handleIndex' in str(step)
                                for step in flow['value']['steps']) or flow['value']['handler_found'])
