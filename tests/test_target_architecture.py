"""The target architecture is a judgement about this codebase, with evidence for each verdict."""
import unittest


class ArchitecturalDecisionTests(unittest.TestCase):
    def component(self, relation='modify'):
        return {'id': 'T-app', 'relation': relation, 'reason': 'FACT-c1 shows a cycle',
                'evidence_ids': ['FACT-c1'], 'paths': ['app/a.py'],
                'assessment': {'dependency_cycles': 1, 'live_claims': 0,
                               'policy_violations': 0, 'load_blockers': 0}}

    def test_every_changed_component_gets_a_complete_adr(self):
        from eaos.target_architecture import decisions
        records = decisions([self.component('modify'), self.component('introduce'),
                             self.component('retire'), self.component('retain')])
        self.assertEqual(len(records), 3)
        for record in records:
            self.assertGreaterEqual(len(record['options']), 2)
            self.assertTrue(any('do nothing' in option.lower() for option in record['options']))
            self.assertIn(record['chosen'], record['options'])
            self.assertTrue(record['tradeoffs'])
            self.assertEqual(record['evidence'], ['FACT-c1'])

    def test_an_adr_with_one_option_is_rejected(self):
        from eaos.target_architecture import validate_decision
        record = {'id': 'ADR-001', 'problem': 'problem', 'evidence': ['FACT-c1'],
                  'options': ['Do nothing.'], 'chosen': 'Do nothing.', 'tradeoffs': 'cost',
                  'consequences': ['persists'], 'migration': ['stop']}
        with self.assertRaisesRegex(ValueError, 'at least two'):
            validate_decision(record)

    def test_an_adr_without_tradeoffs_is_rejected(self):
        from eaos.target_architecture import validate_decision
        record = {'id': 'ADR-001', 'problem': 'problem', 'evidence': ['FACT-c1'],
                  'options': ['Do nothing.', 'Change it.'], 'chosen': 'Change it.',
                  'tradeoffs': '', 'consequences': ['changes'], 'migration': ['change']}
        with self.assertRaisesRegex(ValueError, 'tradeoffs'):
            validate_decision(record)

    def test_render_writes_one_numbered_file_per_decision(self):
        import tempfile
        from pathlib import Path
        from eaos.target_architecture import decisions, render_decisions
        records = decisions([self.component()])
        with tempfile.TemporaryDirectory() as out:
            render_decisions(out, records)
            text = Path(out, 'docs/adr/ADR-001.md').read_text(encoding='utf-8')
        self.assertIn('Do nothing', text)
        self.assertIn('FACT-c1', text)

    def test_options_follow_the_evidence_instead_of_repeating_one_template(self):
        from eaos.target_architecture import decisions
        cycle = self.component()
        load = dict(self.component(), id='T-api', reason='load blockers', paths=['api/handler.py'],
                    assessment={'dependency_cycles': 0, 'live_claims': 1,
                                'policy_violations': 0, 'load_blockers': 2})
        records = decisions([cycle, load])
        self.assertNotEqual(records[0]['options'], records[1]['options'])
        self.assertIn('cycle', ' '.join(records[0]['options']).lower())
        self.assertRegex(' '.join(records[1]['options']).lower(), 'rate|cache|paginat')
        self.assertIn('app/a.py', ' '.join(records[0]['migration']))

    def test_evidence_is_capped_with_a_remainder_counter(self):
        from eaos.target_architecture import decisions
        component = self.component()
        component['evidence_ids'] = [f'FACT-{index}' for index in range(10)]
        evidence = decisions([component])[0]['evidence']
        self.assertEqual(len(evidence), 6)
        self.assertIn('+5 more evidence IDs', evidence)

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


class GapMatrixTests(unittest.TestCase):
    def component(self, relation='modify'):
        return {'id': 'T-api', 'origin': 'api', 'relation': relation, 'reason': 'one claim',
                'paths': ['api/handler.py'], 'evidence_ids': ['FACT-1']}

    def test_retain_without_an_open_claim_is_covered(self):
        from eaos.target_architecture import gap_matrix
        row = gap_matrix([self.component('retain')], [])[0]
        self.assertEqual(row['gap'], 'covered')
        self.assertEqual(row['blocking_tasks'], [])

    def test_claim_with_a_task_is_partial_and_names_the_card(self):
        from eaos.target_architecture import gap_matrix
        claim = {'id': 'CLM-1', 'confidence': 'CONFIRMED',
                 'priority_factors': {'paths': ['api/handler.py']}}
        task = {'id': 'TASK-1', 'claim_id': 'CLM-1'}
        row = gap_matrix([self.component()], [], [claim], [task])[0]
        self.assertEqual(row['gap'], 'partial')
        self.assertEqual(row['blocking_tasks'], ['TASK-1'])
        self.assertIn('CLM-1', row['evidence'])

    def test_claim_without_a_task_is_missing(self):
        from eaos.target_architecture import gap_matrix
        claim = {'id': 'CLM-1', 'confidence': 'LIKELY',
                 'priority_factors': {'paths': ['api/handler.py']}}
        row = gap_matrix([self.component()], [], [claim], [])[0]
        self.assertEqual(row['gap'], 'missing')

    def test_introduced_component_needs_a_transform_stage(self):
        from eaos.target_architecture import gap_matrix
        target = {'id': 'T-new', 'relation': 'introduce', 'paths': ['new/service.py'],
                  'evidence_ids': ['FACT-2']}
        missing = gap_matrix([], [target], stages=[])[0]
        partial = gap_matrix([], [target], stages=[{'stage': 2, 'sites': [{'path': 'new/service.py'}]}])[0]
        self.assertEqual(missing['gap'], 'missing')
        self.assertEqual(partial['gap'], 'partial')
        self.assertEqual(partial['blocking_tasks'], ['TRANSFORM-002'])
