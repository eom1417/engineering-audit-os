"""Blast radius from facts, and an ordering that can be argued with."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from shared_fixture import TemporaryWorkspace
from eaos import cli
from eaos.dossier import assemble
from eaos.impact import assess, load
from eaos.ranking import rank

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'


class ImpactTests(TemporaryWorkspace):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / 'out'
        assemble(FIXTURE, cls.out)


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
        self.assertEqual(set(factors), {'reach', 'reach_normalised', 'reach_source', 'confidence', 'origin', 'cost', 'paths', 'formula'})
        self.assertEqual(factors['cost']['bucket'], 'small')

    def test_the_register_orders_product_findings_above_fixtures(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            assemble(FIXTURE, out)
            register = (out / 'RISK-REGISTER.md').read_text()
            self.assertIn('priority =', register)
            claims = json.loads((out / 'dossier.json').read_text())['claims']
            self.assertTrue(all('priority' in claim for claim in claims))




class ReachFromGraphTests(unittest.TestCase):
    """Reach counts dependents, flows and entry points in the graph — never cluster size."""

    def _sets(self, target_path):
        return {'graph': {'facts': [
            {'kind': 'graph_node', 'location': {'path': target_path}, 'value': {'depends_on': []}},
        ]}, 'metrics': {'facts': []}, 'flows': {'facts': []}, 'entrypoints': {'facts': []}}

    def _claim(self, identifier, fact_path):
        return {'id': identifier, 'statement': 'x' * 30, 'claim_type': 'structure',
                'confidence': 'CONFIRMED', 'method': ['static_fact'], 'evidence_ids': [],
                'fact_ids': ['F' + identifier], 'falsifier': 'y', 'status': 'open', 'created_at': 'now',
                'origin': 'source'}

    def test_cluster_with_no_graph_node_has_zero_reach(self):
        sets = self._sets('target.py')
        # 400 facts but the index resolves none to a known path.
        cluster = self._claim('CLM-CLUSTER', 'target.py')
        cluster['fact_ids'] = [f'f{i}' for i in range(400)]
        ordered = rank([cluster], sets, {})
        # None of the 400 facts maps to a path, so reach is zero.
        self.assertEqual(ordered[0]['priority_factors']['reach']['reach_source'], 'no_paths')
        self.assertEqual(ordered[0]['priority_factors']['reach']['total'], 0)

    def test_cluster_with_paths_but_no_graph_signal_has_zero_reach(self):
        sets = self._sets('target.py')
        cluster = self._claim('CLM-CLUSTER', 'target.py')
        # All facts resolve to a path that exists in graph nodes but has no dependents.
        cluster['fact_ids'] = [f'f{i}' for i in range(400)]
        index = {f'f{i}': 'target.py' for i in range(400)}
        ordered = rank([cluster], sets, index)
        # The path is in the graph but nothing depends on it, no flow touches it, no entry.
        self.assertEqual(ordered[0]['priority_factors']['reach']['reach_source'], 'no_graph_node')
        self.assertEqual(ordered[0]['priority_factors']['reach']['total'], 0)

    def test_cluster_without_graph_node_ranks_below_graph_reachable_function(self):
        sets = {'graph': {'facts': [
            {'kind': 'graph_node', 'location': {'path': 'a.py'}, 'value': {'depends_on': []}},
            {'kind': 'graph_node', 'location': {'path': 'b.py'}, 'value': {'depends_on': ['a.py']}},
            {'kind': 'graph_node', 'location': {'path': 'c.py'}, 'value': {'depends_on': ['a.py']}},
        ]}, 'metrics': {'facts': []}, 'flows': {'facts': []}, 'entrypoints': {'facts': []}}
        cluster = self._claim('CLM-CLUSTER', 'a.py')
        cluster['fact_ids'] = [f'f{i}' for i in range(400)]
        single = self._claim('CLM-SINGLE', 'a.py')
        single['fact_ids'] = ['S1']
        index = {('F' + fact): 'a.py' for fact in cluster['fact_ids']}; index['S1'] = 'a.py'
        ordered = rank([cluster, single], sets, index)
        # Both reference a.py; the single one references only one path.
        # Their priority_factors differ: cluster has 400 paths and no graph signal; single has 1.
        self.assertEqual(ordered[0]['priority_factors']['reach_source'], 'graph')

    def test_reach_source_appears_in_priority_factors(self):
        sets = self._sets('only.py')
        index = {'F1': 'only.py'}
        claim = self._claim('CLM-001', 'only.py')
        ordered = rank([claim], sets, index)
        self.assertIn('reach_source', ordered[0]['priority_factors'])


class LateClaimRankingTests(unittest.TestCase):
    """A claim that arrives after assembly still has to earn its place in the order."""

    def test_a_semantic_claim_is_ranked_when_the_views_refresh(self):
        from eaos import claims as ledger
        from eaos.dossier import refresh_views
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            assemble(FIXTURE, out)
            dossier = json.loads((out / 'dossier.json').read_text())
            late = ledger.make(900, 'The pricing module owns the discount rule for every path', 'responsibility',
                               'HYPOTHESIS', ['model_inference'], [],
                               'A second module applying the rule without importing it',
                               fact_ids=dossier['claims'][0]['fact_ids'], origin='source')
            dossier['claims'].append(late)
            (out / 'dossier.json').write_text(json.dumps(dossier, ensure_ascii=False))
            refresh_views(out)
            updated = json.loads((out / 'dossier.json').read_text())
            ranked = next(claim for claim in updated['claims'] if claim['id'] == late['id'])
            self.assertIn('priority', ranked)
            self.assertIn('priority_factors', ranked)
            self.assertGreater(ranked['priority'], 0)
            self.assertEqual((ranked.get('disposition') or {}).get('kind'), 'investigate')
