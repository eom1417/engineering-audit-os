"""Blast radius from facts, and an ordering that can be argued with."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from eaos import cli
from eaos.dossier import assemble
from eaos.impact import assess, load
from eaos.ranking import rank

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'


class ImpactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / 'out'
        assemble(FIXTURE, cls.out)

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def test_a_shared_module_reports_its_real_dependents(self):
        result = assess(self.out, 'core/pricing.py')
        self.assertEqual(sorted(result['direct_dependents']), ['cli.py', 'core/audit.py', 'worker/tasks.py'])
        self.assertEqual(result['blast_radius'], 3)

    def test_flows_and_entry_points_touching_the_target_are_listed(self):
        result = assess(self.out, 'api/handlers/orders.ts')
        self.assertTrue(any(flow['route'] == '/orders' for flow in result['flows']))

    def test_a_symbol_resolves_to_the_files_that_define_it(self):
        result = assess(self.out, 'price_for')
        self.assertEqual(result['resolved_paths'], ['core/pricing.py'])
        self.assertTrue(any(symbol['symbol'] == 'price_for' for symbol in result['symbols']))

    def test_an_unknown_target_fails_loudly(self):
        with self.assertRaisesRegex(ValueError, 'Unknown path or symbol'):
            assess(self.out, 'does/not/exist.py')

    def test_missing_facts_are_reported_rather_than_assumed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'No graph facts'):
                load(Path(tmp))

    def test_cli_exposes_the_report(self):
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            self.assertEqual(cli.main(['impact-of', 'core/pricing.py', '--out', str(self.out)]), 0)
        self.assertEqual(json.loads(printed.getvalue())['blast_radius'], 3)


class RankingTests(unittest.TestCase):
    def sets_for(self, dependents_count):
        nodes = [{'kind': 'graph_node', 'location': {'path': 'core.py'}, 'value': {'depends_on': []}}]
        for index in range(dependents_count):
            nodes.append({'kind': 'graph_node', 'location': {'path': f'user{index}.py'}, 'value': {'depends_on': ['core.py']}})
        return {'graph': {'facts': nodes},
                'metrics': {'facts': [{'kind': 'metric', 'location': {'path': 'core.py'},
                                       'value': {'scope': 'file', 'lines': 50}}]},
                'flows': {'facts': []}, 'entrypoints': {'facts': []}}

    def claim(self, identifier, **overrides):
        row = {'id': identifier, 'statement': 'x' * 30, 'claim_type': 'structure', 'confidence': 'CONFIRMED',
               'method': ['static_fact'], 'evidence_ids': [], 'fact_ids': ['F1'], 'falsifier': 'y',
               'status': 'open', 'created_at': 'now', 'origin': 'source'}
        row.update(overrides)
        return row

    def test_wider_reach_outranks_a_longer_sentence(self):
        sets = self.sets_for(5)
        index = {'F1': 'core.py', 'F2': 'leaf.py'}
        sets['graph']['facts'].append({'kind': 'graph_node', 'location': {'path': 'leaf.py'}, 'value': {'depends_on': []}})
        wide = self.claim('CLM-001')
        narrow = self.claim('CLM-002', fact_ids=['F2'],
                            impact={'scenario': 'a very long consequence sentence ' * 10})
        ordered = rank([narrow, wide], sets, index)
        self.assertEqual(ordered[0]['id'], 'CLM-001')
        self.assertGreater(ordered[0]['priority'], ordered[1]['priority'])

    def test_test_origin_is_discounted_against_product_code(self):
        sets = self.sets_for(3)
        index = {'F1': 'core.py'}
        product = self.claim('CLM-001')
        fixture = self.claim('CLM-002', origin='test')
        ordered = rank([fixture, product], sets, index)
        self.assertEqual(ordered[0]['id'], 'CLM-001')

    def test_every_claim_exposes_the_inputs_of_its_priority(self):
        sets = self.sets_for(2)
        ordered = rank([self.claim('CLM-001')], sets, {'F1': 'core.py'})
        factors = ordered[0]['priority_factors']
        self.assertEqual(set(factors), {'reach', 'reach_normalised', 'confidence', 'origin', 'cost', 'paths', 'formula'})
        self.assertEqual(factors['cost']['bucket'], 'small')

    def test_the_register_orders_product_findings_above_fixtures(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            assemble(FIXTURE, out)
            register = (out / 'RISK-REGISTER.md').read_text()
            self.assertIn('priority =', register)
            claims = json.loads((out / 'dossier.json').read_text())['claims']
            self.assertTrue(all('priority' in claim for claim in claims))
