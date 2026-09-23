"""Engine-cluster findings must be classified to a real remediation pattern, not generic."""
import unittest

from eaos.remediation_patterns import (
    PATTERNS,
    _ENGINE_CLUSTER_KINDS,
    classify,
    cost_of_inaction,
    pattern_for,
)


def engine_cluster_claim(kind):
    return {'probe_spec': {'probe_type': 'graph_query',
                           'specification': {'query': 'engine_cluster_present', 'kind': kind}}}


class EngineClusterClassificationTests(unittest.TestCase):
    """Each engine-cluster kind the tools produce must map to its real prescription."""

    def test_complexity_maps_to_hotspot(self):
        self.assertEqual(classify(engine_cluster_claim('complexity')), 'hotspot')

    def test_coupling_maps_to_hidden_coupling(self):
        self.assertEqual(classify(engine_cluster_claim('coupling')), 'hidden_coupling')

    def test_literal_duplication_maps_to_canonicalize(self):
        self.assertEqual(classify(engine_cluster_claim('literal_duplication')), 'canonicalize')

    def test_dead_code_maps_to_the_new_pattern(self):
        self.assertEqual(classify(engine_cluster_claim('dead_code')), 'dead_code')

    def test_unknown_kind_stays_generic_with_a_stated_reason(self):
        claim = engine_cluster_claim('unknown_kind_xyz')
        self.assertEqual(classify(claim), 'generic')
        pattern = pattern_for(claim)
        self.assertEqual(pattern['name'], 'generic')
        self.assertIn('unknown engine-cluster kind', pattern['fallback_reason'])
        self.assertIn('unknown_kind_xyz', pattern['fallback_reason'])

    def test_missing_kind_falls_through_with_a_reason(self):
        claim = {'probe_spec': {'probe_type': 'graph_query',
                                'specification': {'query': 'engine_cluster_present'}}}
        self.assertEqual(classify(claim), 'generic')
        pattern = pattern_for(claim)
        self.assertIn('absent', pattern['fallback_reason'])


class DeadCodePatternTests(unittest.TestCase):
    """Deleting code is a decision, not a note; it needs options and a rollback."""

    def test_dead_code_pattern_has_real_options_and_cost(self):
        pattern = pattern_for(engine_cluster_claim('dead_code'))
        self.assertEqual(pattern['name'], 'dead_code')
        self.assertTrue(pattern['change'].strip())
        self.assertGreaterEqual(len(pattern['options']), 3,
                               'dead_code needs delete / add-test / documented-accept + DO_NOTHING')
        costs = {option.get('cost') for option in pattern['options']}
        self.assertIn('\u0645\u0646\u062e\u0641\u0636\u0629', costs)  # low
        self.assertIn('\u0645\u062a\u0648\u0633\u0637\u0629', costs)  # medium
        self.assertTrue(pattern['rollback'].strip())

    def test_cost_of_inaction_mentions_dead_code_specifically(self):
        self.assertIn('\u0627\u0644\u0643\u0648\u062f \u0627\u0644\u0645\u064a\u062a',
                      cost_of_inaction('dead_code'))


class ConsistencyTests(unittest.TestCase):
    """Every pattern that classify() can return must exist in PATTERNS and cost_of_inaction."""

    def test_engine_cluster_kinds_all_resolve(self):
        for kind in _ENGINE_CLUSTER_KINDS:
            self.assertIn(_ENGINE_CLUSTER_KINDS[kind], PATTERNS,
                          kind + ' maps to a pattern that must exist in PATTERNS')

    def test_classify_returns_known_patterns(self):
        for kind in _ENGINE_CLUSTER_KINDS:
            self.assertIn(classify(engine_cluster_claim(kind)), PATTERNS)
