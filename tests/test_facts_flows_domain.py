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


def collect_files(tmp, files):
    repo = Path(tmp) / 'repo'
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)
    collect(repo, Path(tmp) / 'out', SETS)
    return Path(tmp) / 'out'


class PolyglotFlowAndDomainTests(TemporaryWorkspace):
    @classmethod
    def setUpClass(cls):
        out = Path(cls.workspace().name) / 'out'
        collect(FIXTURE, out, SETS)
        flows = read_set(out, 'flows')
        cls.flows, cls.summary = [f['value'] for f in flows['facts']], flows['summary']
        cls.domain = read_set(out, 'domain')

    def flow_for(self, route, method=None):
        return next(flow for flow in self.flows
                    if flow['entry']['route'] == route and (method is None or flow['entry']['http_method'] == method))

    def test_routes_and_jobs_are_traced_into_the_modules_that_implement_them(self):
        flow = self.flow_for('/orders', 'POST')
        self.assertEqual(flow['entry']['handler'], 'createOrder')
        self.assertIn('api/lib/pricing.ts', flow['touched_files'])
        step = next(step for step in flow['steps'] if step['callee'] == 'priceFor')
        self.assertEqual((step['resolution'], step['to_path']), ('imported', 'api/lib/pricing.ts'))
        job = self.flow_for('recalculate')
        self.assertIn('core/pricing.py', job['touched_files'])
        self.assertIn('TAX_RATE', job['environment_reads'])
        for flow in self.flows:
            for step in flow['steps']:
                self.assertTrue(step['from_path'])
                self.assertIsInstance(step['line'], int)
        # Library and builtin calls are not counted as gaps.
        self.assertEqual(self.summary['unresolved_steps'], 0)
        self.assertGreater(self.summary['steps_by_resolution']['method_or_external'], 0)

    def test_a_rule_constant_duplicated_across_languages_is_found(self):
        fact = next(f for f in self.domain['facts'] if f['value'].get('name') == 'PREMIUM_DISCOUNT')
        paths = {definition['path'] for definition in fact['value']['definitions']}
        self.assertEqual(paths, {'api/handlers/orders.ts', 'api/lib/pricing.ts', 'core/pricing.py'})
        self.assertTrue(fact['value']['duplicated'])
        self.assertTrue(fact['value']['same_value_everywhere'])


class FlowTests(unittest.TestCase):
    def test_unresolvable_calls_are_recorded_and_go_receiver_handlers_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = collect_files(tmp, {
                'app.py': 'import argparse\n\n\ndef handler():\n    return mystery_function()\n\n\n'
                          'def main():\n    parser = argparse.ArgumentParser(prog="app")\n    handler()\n',
                'server.go': 'package main\n\nimport "net/http"\n\ntype Server struct{}\n\n'
                             'func (s *Server) handleIndex(w http.ResponseWriter, r *http.Request) {}\n\n'
                             'func main() {\n    s := &Server{}\n    http.HandleFunc("/", s.handleIndex)\n}\n'})
            flows = [f['value'] for f in read_set(out, 'flows')['facts']]
        steps = [step for flow in flows for step in flow['steps']]
        self.assertEqual(next(step for step in steps if step['callee'] == 'mystery_function')['resolution'], 'unresolved')
        go = next(flow for flow in flows if flow['entry']['handler'] == 's.handleIndex')
        self.assertTrue(go['handler_found'], 'receiver-method handler did not link')

    def test_task_runner_scripts_and_console_scripts_are_traced_to_their_handlers(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = collect_files(tmp, {
                'web/package.json': json.dumps({'scripts': {
                    'build': 'tsc && node scripts/ship.mjs', 'gates': 'python ../tools/gates.py', 'dev': 'vite',
                    'missing': 'node scripts/absent.mjs'}}),
                'web/scripts/ship.mjs': "import fs from 'node:fs'\n\nfunction pack(dir) {\n  return fs.readdirSync(dir)\n}\n\n"
                                        "console.log(pack('dist'))\n",
                'tools/gates.py': 'def check():\n    return 0\n\n\nraise SystemExit(check())\n',
                'pyproject.toml': '[project]\nname = "pkg"\n\n[project.scripts]\npkg = "pkg.cli:main"\n',
                'pkg/__init__.py': '',
                'pkg/cli.py': 'def run():\n    return 1\n\n\ndef main():\n    return run()\n'})
            flows = {f['value']['entry']['route']: f['value'] for f in read_set(out, 'flows')['facts']}
            summary = read_set(out, 'flows')['summary']
        ship = flows['npm run build']
        self.assertTrue(ship['handler_found'])
        self.assertIn('pack', [step['callee'] for step in ship['steps']])
        self.assertIn('web/scripts/ship.mjs', ship['touched_files'])
        self.assertIn('check', [step['callee'] for step in flows['npm run gates']['steps']])
        self.assertEqual((flows['pkg']['steps'][0]['from_path'], flows['pkg']['steps'][0]['callee']), ('pkg/cli.py', 'run'))
        # A script naming a missing file stays visible as a gap; one running only an external tool is no entry point.
        self.assertNotIn('npm run missing', flows)
        self.assertNotIn('npm run dev', flows)
        self.assertEqual(summary['entry_points_considered'], 4)
        self.assertEqual(summary['entry_points_without_traceable_handler'], 1)

    def test_a_repeated_callee_is_recorded_once_and_the_trace_reaches_the_call_behind_it(self):
        from eaos.facts import flows
        page = {'path': 'src/Page.tsx', 'symbol': 'Page', 'name': 'Page', 'start': 1, 'end': 90, 'kind': 'function'}
        load = {'path': 'src/api.ts', 'symbol': 'load', 'name': 'load', 'start': 1, 'end': 5, 'kind': 'function'}
        by_file, by_name = {'src/Page.tsx': [page], 'src/api.ts': [load]}, {'Page': [page], 'load': [load]}
        calls = {('src/Page.tsx', 'Page'): [{'callee': 'useState', 'line': n, 'attribute': False} for n in range(2, 60)]
                 + [{'callee': 'String', 'line': 61, 'attribute': False}, {'callee': 'load', 'line': 62, 'attribute': False}]}
        entry = {'value': {'handler': 'Page', 'surface': 'page', 'route': '/', 'http_method': None, 'framework': 'react_router'},
                 'location': {'path': 'src/Page.tsx', 'start_line': 1}}
        traced = flows.trace(entry, by_file, by_name, calls, {'src/Page.tsx': {'src/api.ts'}}, {}, {'src/Page.tsx': {'useState'}})
        callees = [step['callee'] for step in traced['steps']]
        self.assertEqual(callees.count('useState'), 1)
        self.assertEqual(next(s for s in traced['steps'] if s['callee'] == 'load')['resolution'], 'imported')
        self.assertEqual(next(s for s in traced['steps'] if s['callee'] == 'String')['resolution'], 'builtin')
        self.assertEqual(traced['unresolved_steps'], 0)


class DomainTests(unittest.TestCase):
    def test_differing_rule_values_models_and_tables_are_located(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = collect_files(tmp, {'checkout.py': 'DISCOUNT = 0.1\n', 'export.py': 'DISCOUNT = 0.15\n',
                                      'models.py': 'class Order(Model):\n    pass\n',
                                      'schema.sql': 'CREATE TABLE orders (id int);\n'})
            data = read_set(out, 'domain')
        self.assertEqual(data['summary']['duplicated_with_different_values'], ['DISCOUNT'])
        self.assertEqual(data['summary']['duplicated_with_same_value'], [])
        self.assertIn('Order', [f['value']['name'] for f in data['facts'] if f['kind'] == 'data_model'])
        self.assertIn('orders', [f['value']['name'] for f in data['facts'] if f['kind'] == 'data_table'])

    def test_shared_state_is_reported_only_when_it_actually_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = collect_files(tmp, {
                'tables.py': 'TABLE = {"a": 1, "b": 2}\n\n\ndef lookup(key):\n    return TABLE[key]\n',
                'cache.py': 'CACHE = {}\n\n\ndef remember(key, value):\n    CACHE[key] = value\n',
                'patterns.py': 'PATTERNS = {"a": 1}\nPATTERNS["b"] = 2\n',
                'settings.py': 'LIMIT = 10\n',
                'app.py': 'import settings\n\n\ndef raise_limit():\n    settings.LIMIT = 99\n'})
            data = read_set(out, 'domain')
        summary = data['summary']
        # A lookup table is not mutable state; state built at import time is recorded but kept apart.
        self.assertEqual(summary['mutable_globals'], 2)
        self.assertEqual(summary['mutable_globals_changed_at_runtime'], 1)
        changed = [f for f in data['facts'] if f['kind'] == 'mutable_global' and f['value']['mutation_scope'] == 'function']
        self.assertEqual([f['value'].get('name') for f in changed], ['CACHE'])
        self.assertEqual(summary['external_state_writes'], 1)
        fact = next(f for f in data['facts'] if f['kind'] == 'external_state_write')
        self.assertEqual((fact['value']['module'], fact['value']['attribute']), ('settings', 'LIMIT'))


class DossierClaimTests(unittest.TestCase):
    def test_runtime_state_and_cross_module_writes_become_claims_with_probes(self):
        from eaos.analysis.dossier import assemble
        from eaos.analysis import probes
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
        self.assertIn('CACHE', {claim['statement'].split()[0] for claim in claims})
        self.assertTrue(any('writes into settings.LIMIT' in claim['statement'] for claim in claims))
        self.assertTrue(all(claim['confidence'] == 'CONFIRMED' for claim in claims))

    def test_the_most_complex_function_is_a_hotspot_even_when_its_file_is_not_top_ranked(self):
        from eaos.analysis.dossier import assemble
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            branches = '\n'.join(f'    if value == {n}:\n        return {n}' for n in range(80))
            (repo / 'buried.py').write_text(f'def decide(value):\n{branches}\n    return 0\n')
            (repo / 'simple.py').write_text('def add(a, b):\n    return a + b\n')
            # Fifteen small, central modules outrank the complex one on attention.
            for index in range(15):
                (repo / f'mod{index}.py').write_text('import buried\n\n\ndef use():\n    return buried.decide(1)\n')
            (repo / 'main.py').write_text('import argparse\n' + ''.join(f'import mod{i}\n' for i in range(15))
                                          + '\n\ndef main():\n    argparse.ArgumentParser(prog="x").parse_args()\n'
                                          + '    return mod0.use()\n')
            out = Path(tmp) / 'out'
            assemble(repo, out)
            claims = json.loads((out / 'dossier.json').read_text())['claims']
        hotspots = [claim for claim in claims if 'has complexity' in claim['statement']]
        self.assertEqual(len(hotspots), 1, 'only the dense function is a hotspot, whatever its file rank')
        self.assertIn('decide', hotspots[0]['statement'])
        self.assertEqual(hotspots[0]['confidence'], 'CONFIRMED')
        self.assertEqual(hotspots[0]['probe_spec']['specification']['query'], 'metric_threshold')
