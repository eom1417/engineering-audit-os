"""Graph queries over an evidence-backed architecture model: cycles, change impact and declared policy."""
import json
from pathlib import Path
import unittest
from eaos.facts.code import graph_queries as arch

MODEL = Path(__file__).resolve().parents[1] / 'fixtures/architecture-model.json'


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.model = json.loads(MODEL.read_text())

    def test_change_impact_walks_proven_edges_up_to_an_explicit_depth(self):
        result = arch.impact(self.model, 'store')
        self.assertEqual(result['potential_dependents'], ['entry', 'service'])
        self.assertEqual(result['distances'], {'store': 0, 'service': 1, 'entry': 2})
        limited = arch.impact(self.model, 'store', 1)
        self.assertEqual((limited['potential_dependents'], limited['unexpanded_frontier']), (['service'], ['entry']))
        self.model['edges'][0]['status'] = 'HYPOTHESIS'
        guessed = arch.impact(self.model, 'store')
        self.assertEqual((guessed['potential_dependents'], guessed['hypothesis_edges']), (['service'], ['EDGE-1']))

    def test_cycles_are_found_typed_and_safe_on_long_chains(self):
        graph = {str(i): {str(i + 1)} for i in range(5000)}
        graph['5000'] = set()
        self.assertEqual(arch.cycles(graph), [])
        self.assertEqual(arch.cycles({'a': {'a'}}), [['a']])
        self.model['edges'].append(dict(id='BACK', **{'from': 'store', 'to': 'entry'}, relation='imports',
                                        status='CONFIRMED', reason='fixture', evidence_ids=['E-1']))
        self.assertEqual(arch.summary(self.model)['static_dependency_cycles'], [])
        self.model['edges'][1]['relation'] = 'imports'
        self.assertEqual(arch.summary(self.model)['static_dependency_cycles'], [['entry', 'service', 'store']])

    def test_only_a_declared_policy_makes_a_violation(self):
        self.assertEqual(arch.summary(self.model)['declared_policy_violations'], [])
        self.model['dependency_policies'] = [dict(id='P-1', **{'from': 'entry', 'to': 'service'}, relation='uses_contract',
                                                  rule='forbid', reason='fixture', evidence_ids=['E-1'])]
        self.assertEqual(arch.summary(self.model)['declared_policy_violations'][0]['edge_id'], 'EDGE-1')
