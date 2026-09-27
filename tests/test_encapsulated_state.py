"""Module state private to its module has an owner: a decision for a person, not a ready repair."""
import unittest

from eaos.claims import from_facts
from eaos.facts.domain import encapsulated


class EncapsulationTests(unittest.TestCase):
    def test_what_other_modules_cannot_reach_is_encapsulated(self):
        self.assertTrue(encapsulated('draining', 'let draining = false;\nexport function markDraining() { draining = true; }', 'typescript'))
        self.assertFalse(encapsulated('x', 'export let x = 1;', 'typescript'))
        self.assertFalse(encapsulated('x', 'let x = 1;\nexport { x };', 'typescript'))
        self.assertFalse(encapsulated('x', 'let x = 1;\nmodule.exports.x = x;', 'javascript'))
        self.assertTrue(encapsulated('_cache', '_cache = {}', 'python'))
        self.assertFalse(encapsulated('_cache', "__all__ = ['_cache']\n_cache = {}", 'python'))
        self.assertFalse(encapsulated('CACHE', 'CACHE = {}', 'python'))
        self.assertTrue(encapsulated('cache', 'var cache = map[string]int{}', 'go'))

    def claim(self, private):
        sets = {'domain': {'facts': [{'id': 'F1', 'kind': 'mutable_global', 'location': {'path': 'server/h.ts', 'start_line': 1},
                                      'value': {'name': 'draining', 'shape': 'let', 'mutated_by': 'assignment', 'mutated_at_line': 8,
                                                'mutation_scope': 'function', 'encapsulated': private}}]}}
        return next(c for c in from_facts(sets) if (c.get('render') or {}).get('key') == 'mutable_global')

    def test_encapsulated_state_is_likely_and_exposed_state_is_confirmed(self):
        self.assertEqual(self.claim(True)['confidence'], 'LIKELY')
        self.assertIn('private to its module', self.claim(True)['statement'])
        self.assertEqual(self.claim(False)['confidence'], 'CONFIRMED')


if __name__ == '__main__':
    unittest.main()
