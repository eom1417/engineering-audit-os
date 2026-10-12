"""The target architecture is a judgement about this codebase, with evidence for each verdict."""
import json
from pathlib import Path
import tempfile
import unittest
from eaos.pipeline import execute
from eaos.target_architecture import (assess, components, decisions, gap_matrix, package_of, render_decisions,
                                      validate_decision)


def changed(relation='modify', **extra):
    return {'id': 'T-app', 'relation': relation, 'reason': 'FACT-c1 shows a cycle', 'evidence_ids': ['FACT-c1'],
            'paths': ['app/a.py'], 'assessment': {'dependency_cycles': 1, 'live_claims': 0, 'policy_violations': 0,
                                                  'load_blockers': 0}, **extra}


def fact_sets(files):
    return {'syntax': {'facts': [{'kind': 'symbol', 'id': f'FACT-s{i}', 'location': {'path': path},
                                  'value': {'name': f'fn{i}', 'kind': 'function'}} for i, path in enumerate(files)]},
            'graph': {'facts': [{'kind': 'graph_node', 'id': f'FACT-n{i}', 'location': {'path': path},
                                 'value': {'fan_in': 1, 'fan_out': 1, 'depends_on': []}} for i, path in enumerate(files)]}}


class ArchitecturalDecisionTests(unittest.TestCase):
    def test_every_changed_component_gets_a_complete_decision_that_follows_its_evidence(self):
        records = decisions([changed('modify'), changed('introduce'), changed('retire'), changed('retain')])
        self.assertEqual(len(records), 3)
        for record in records:
            self.assertGreaterEqual(len(record['options']), 2)
            self.assertTrue(any('do nothing' in option.lower() for option in record['options']))
            self.assertIn(record['chosen'], record['options'])
            self.assertTrue(record['tradeoffs'])
            self.assertEqual(record['evidence'], ['FACT-c1'])
        load = changed(id='T-api', reason='load blockers', paths=['api/handler.py'],
                       assessment={'dependency_cycles': 0, 'live_claims': 1, 'policy_violations': 0, 'load_blockers': 2})
        cycle, api = decisions([changed(), load])
        self.assertNotEqual(cycle['options'], api['options'])
        self.assertIn('cycle', ' '.join(cycle['options']).lower())
        self.assertRegex(' '.join(api['options']).lower(), 'rate|cache|paginat')
        self.assertIn('app/a.py', ' '.join(cycle['migration']))
        evidence = decisions([changed(evidence_ids=[f'FACT-{index}' for index in range(10)])])[0]['evidence']
        self.assertEqual(len(evidence), 6)
        self.assertIn('+5 more evidence IDs', evidence)
        with tempfile.TemporaryDirectory() as out:
            render_decisions(out, decisions([changed()]))
            text = Path(out, 'adr/ADR-001.md').read_text(encoding='utf-8')
        self.assertIn('Do nothing', text)
        self.assertIn('FACT-c1', text)

    def test_a_decision_without_a_real_choice_is_rejected(self):
        base = {'id': 'ADR-001', 'problem': 'problem', 'evidence': ['FACT-c1'], 'consequences': ['x'], 'migration': ['y']}
        cases = [({'options': ['Do nothing.'], 'chosen': 'Do nothing.', 'tradeoffs': 'cost'}, 'at least two'),
                 ({'options': ['Do nothing.', 'Change it.'], 'chosen': 'Change it.', 'tradeoffs': ''}, 'tradeoffs')]
        for record, message in cases:
            with self.subTest(message), self.assertRaisesRegex(ValueError, message):
                validate_decision({**base, **record})


class ComponentTests(unittest.TestCase):
    """A component is an architectural unit, and every one carries a verdict with its evidence."""

    def test_a_component_is_a_package_not_a_symbol(self):
        files = [f'pkg{index % 40}/module_{index}.py' for index in range(10000)]
        built = components(fact_sets(files))
        self.assertEqual(len(built), 40)
        self.assertEqual(sum(row['symbols'] for row in built), 10000)
        self.assertEqual(package_of('main.py'), '')
        self.assertEqual(sorted(row['name'] for row in components(fact_sets(['main.py', 'pkg/a.py']))), ['(root)', 'pkg'])

    def test_each_verdict_names_what_it_looked_at(self):
        component = components(fact_sets(['pkg/a.py']))[0]
        claim = lambda confidence: {'id': 'CLM-001', 'confidence': confidence, 'priority_factors': {'paths': ['pkg/a.py']}}
        cycle = {'graph': {'facts': [{'kind': 'graph_cycle', 'id': 'FACT-c1', 'location': {'path': 'pkg/a.py'},
                                      'value': {'members': ['pkg/a.py', 'pkg/b.py']}}]}}
        empty = {'graph': {'facts': []}}
        cases = [(empty, [], 'retain', 'absence', None), (empty, [claim('CONFIRMED')], 'modify', 'live claim', 'CLM-001'),
                 (empty, [claim('REFUTED')], 'retain', None, None), (cycle, [], 'modify', 'cycle', 'FACT-c1')]
        for sets, claims, expected, why, cited in cases:
            with self.subTest(expected=expected, why=why):
                relation, reason, evidence = assess(component, sets, claims=claims)
                self.assertEqual(relation, expected)
                self.assertTrue(evidence, 'even a retain decision cites what it looked at')
                if why: self.assertIn(why, reason)
                if cited: self.assertIn(cited, evidence)

    def test_every_component_in_a_real_report_carries_a_relation_and_a_reason(self):
        fixture = Path(__file__).resolve().parent / 'fixtures/sustainability'
        with tempfile.TemporaryDirectory() as out:
            execute(fixture, out, skip=('engines',), language='en')
            record = json.loads(Path(out, 'target-architecture.json').read_text(encoding='utf-8'))
        self.assertTrue(record['components'])
        for row in record['components']:
            self.assertNotEqual(row['relation'], 'unassessed', row['id'])
            self.assertTrue(row['reason'].strip(), row['id'])
            self.assertTrue(row['evidence_ids'], f"{row['id']} was judged with no evidence")


class GapMatrixTests(unittest.TestCase):
    def test_each_gap_names_the_card_or_stage_that_closes_it(self):
        component = lambda relation='modify': {'id': 'T-api', 'origin': 'api', 'relation': relation, 'reason': 'one claim',
                                               'paths': ['api/handler.py'], 'evidence_ids': ['FACT-1']}
        claim = lambda confidence: {'id': 'CLM-1', 'confidence': confidence, 'priority_factors': {'paths': ['api/handler.py']}}
        covered = gap_matrix([component('retain')], [])[0]
        self.assertEqual((covered['gap'], covered['blocking_tasks']), ('covered', []))
        partial = gap_matrix([component()], [], [claim('CONFIRMED')], [{'id': 'TASK-1', 'claim_id': 'CLM-1'}])[0]
        self.assertEqual((partial['gap'], partial['blocking_tasks']), ('partial', ['TASK-1']))
        self.assertIn('CLM-1', partial['evidence'])
        self.assertEqual(gap_matrix([component()], [], [claim('LIKELY')], [])[0]['gap'], 'missing')
        target = {'id': 'T-new', 'relation': 'introduce', 'paths': ['new/service.py'], 'evidence_ids': ['FACT-2']}
        self.assertEqual(gap_matrix([], [target], stages=[])[0]['gap'], 'missing')
        staged = gap_matrix([], [target], stages=[{'stage': 2, 'sites': [{'path': 'new/service.py'}]}])[0]
        self.assertEqual((staged['gap'], staged['blocking_tasks']), ('partial', ['TRANSFORM-002']))
