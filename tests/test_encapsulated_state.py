"""Module state private to its module has an owner: a decision for a person, not a ready repair."""
import unittest

from eaos.claims import from_facts
from eaos.facts.domain import encapsulated


class EncapsulationTests(unittest.TestCase):
    def claim(self, private):
        sets = {'domain': {'facts': [{'id': 'F1', 'kind': 'mutable_global', 'location': {'path': 'server/h.ts', 'start_line': 1},
                                      'value': {'name': 'draining', 'shape': 'let', 'mutated_by': 'assignment', 'mutated_at_line': 8,
                                                'mutation_scope': 'function', 'encapsulated': private}}]}}
        return next(c for c in from_facts(sets) if (c.get('render') or {}).get('key') == 'mutable_global')

    def test_state_other_modules_cannot_reach_is_a_likely_claim_and_exposed_state_is_confirmed(self):
        for name, text, language, private in [
                ('draining', 'let draining = false;\nexport function markDraining() { draining = true; }', 'typescript', True),
                ('x', 'export let x = 1;', 'typescript', False), ('x', 'let x = 1;\nexport { x };', 'typescript', False),
                ('x', 'let x = 1;\nmodule.exports.x = x;', 'javascript', False), ('_cache', '_cache = {}', 'python', True),
                ('_cache', "__all__ = ['_cache']\n_cache = {}", 'python', False), ('CACHE', 'CACHE = {}', 'python', False),
                ('cache', 'var cache = map[string]int{}', 'go', True)]:
            self.assertIs(encapsulated(name, text, language), private, (text, language))
        self.assertEqual(self.claim(True)['confidence'], 'LIKELY')
        self.assertIn('private to its module', self.claim(True)['statement'])
        self.assertEqual(self.claim(False)['confidence'], 'CONFIRMED')
