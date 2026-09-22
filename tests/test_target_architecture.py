"""The target architecture is a judgement about this codebase, with evidence for each verdict."""
import unittest

class ComponentGranularityTests(unittest.TestCase):
    """A component is an architectural unit, and every one carries a verdict with its evidence."""

    def _sets(self, files, packages):
        symbols = [{'kind': 'symbol', 'id': f'FACT-s{index}', 'location': {'path': path},
                    'value': {'name': f'fn{index}', 'kind': 'function'}}
                   for index, path in enumerate(files)]
        nodes = [{'kind': 'graph_node', 'id': f'FACT-n{index}', 'location': {'path': path},
                  'value': {'fan_in': 1, 'fan_out': 1, 'depends_on': []}}
                 for index, path in enumerate(files)]
        return {'syntax': {'facts': symbols}, 'graph': {'facts': nodes}}

    def test_ten_thousand_symbols_do_not_become_ten_thousand_components(self):
        from eaos.target_architecture import components
        files = [f'pkg{index % 40}/module_{index}.py' for index in range(10000)]
        built = components(self._sets(files, 40))
        self.assertEqual(len(built), 40, 'a component must be a package, not a symbol')
        self.assertEqual(sum(row['symbols'] for row in built), 10000)

    def test_a_top_level_file_belongs_to_the_root_component(self):
        from eaos.target_architecture import components, package_of
        self.assertEqual(package_of('main.py'), '')
        built = components(self._sets(['main.py', 'pkg/a.py'], 2))
        self.assertEqual(sorted(row['name'] for row in built), ['(root)', 'pkg'])

    def test_a_component_with_nothing_against_it_is_retained_with_that_as_the_reason(self):
        from eaos.target_architecture import assess, components
        built = components(self._sets(['pkg/a.py'], 1))
        relation, reason, evidence = assess(built[0], {'graph': {'facts': []}}, claims=[])
        self.assertEqual(relation, 'retain')
        self.assertIn('absence', reason)
        self.assertTrue(evidence, 'even a retain decision cites what it looked at')

    def test_a_live_claim_on_a_component_makes_it_modify_and_names_the_claim(self):
        from eaos.target_architecture import assess, components
        built = components(self._sets(['pkg/a.py'], 1))
        claim = {'id': 'CLM-001', 'confidence': 'CONFIRMED',
                 'priority_factors': {'paths': ['pkg/a.py']}}
        relation, reason, evidence = assess(built[0], {'graph': {'facts': []}}, claims=[claim])
        self.assertEqual(relation, 'modify')
        self.assertIn('live claim', reason)
        self.assertIn('CLM-001', evidence)

    def test_a_refuted_claim_does_not_condemn_a_component(self):
        from eaos.target_architecture import assess, components
        built = components(self._sets(['pkg/a.py'], 1))
        claim = {'id': 'CLM-001', 'confidence': 'REFUTED',
                 'priority_factors': {'paths': ['pkg/a.py']}}
        relation, _, _ = assess(built[0], {'graph': {'facts': []}}, claims=[claim])
        self.assertEqual(relation, 'retain')

    def test_a_cycle_through_a_component_makes_it_modify(self):
        from eaos.target_architecture import assess, components
        built = components(self._sets(['pkg/a.py'], 1))
        sets = {'graph': {'facts': [{'kind': 'graph_cycle', 'id': 'FACT-c1',
                                     'location': {'path': 'pkg/a.py'},
                                     'value': {'members': ['pkg/a.py', 'pkg/b.py']}}]}}
        relation, reason, evidence = assess(built[0], sets, claims=[])
        self.assertEqual(relation, 'modify')
        self.assertIn('cycle', reason)
        self.assertIn('FACT-c1', evidence)

    def test_every_component_in_a_real_report_carries_a_relation_and_a_reason(self):
        import json as _json
        import tempfile as _tempfile
        from pathlib import Path as _Path
        from eaos.audit import run as run_audit
        fixture = _Path(__file__).resolve().parent / 'fixtures/sustainability'
        with _tempfile.TemporaryDirectory() as out:
            run_audit(fixture, out, language='en')
            record = _json.loads(_Path(out, 'target-architecture.json').read_text(encoding='utf-8'))
        self.assertTrue(record['components'])
        unassessed = [row for row in record['components'] if row['relation'] == 'unassessed']
        self.assertEqual(unassessed, [], 'a component was left unassessed without a reason')
        for row in record['components']:
            self.assertTrue(row['reason'].strip(), row['id'])
            self.assertTrue(row['evidence_ids'], f"{row['id']} was judged with no evidence")
