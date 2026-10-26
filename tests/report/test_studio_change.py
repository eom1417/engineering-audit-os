"""studio/gaps.json and studio/operations.json (eaos/report/studio/change.py): every gap and operation read from the
check's records, closure only where cards measure it, and an order that never puts an operation before what it waits for."""
import unittest

from eaos.core.contracts import artifact_rules as artifact_contracts
from eaos.report.studio import change

CURRENT = [
    {'id': 'T-a', 'name': 'src/a', 'relation': 'rebuild', 'files': 4, 'target_component': 'features', 'reason': 'Most of it must move.'},
    {'id': 'T-b', 'name': 'src/b', 'relation': 'modify', 'files': 2, 'target_component': 'features', 'reason': 'It stays, with changes.'},
    {'id': 'T-c', 'name': 'src/c', 'relation': 'retain', 'files': 1, 'target_component': 'lib'},
    {'id': 'T-d', 'name': 'old', 'relation': 'delete', 'files': 3, 'target_component': 'lib'},
    {'id': 'T-e', 'name': 'src/e', 'relation': 'rebuild', 'files': 5, 'target_component': 'pages'},
]
TARGETS = [{'name': 'features', 'responsibility': 'One module per domain'}, {'name': 'lib', 'responsibility': 'Shared code'},
           {'name': 'pages', 'responsibility': 'Routes'}, {'name': 'home', 'responsibility': 'The landing screen'}]
ROWS = [{'current_id': 'T-a', 'blocking_tasks': ['TASK-1', 'TASK-2'], 'gap': 'partial'},
        {'current_id': 'T-b', 'blocking_tasks': ['TASK-3'], 'gap': 'partial'},
        {'current_id': 'T-c', 'blocking_tasks': [], 'gap': 'covered'},
        {'current_id': 'T-d', 'blocking_tasks': ['TASK-4'], 'gap': 'partial'},
        {'current_id': 'T-e', 'blocking_tasks': [], 'gap': 'missing'}]
PLAN = {'milestones': [{'id': 'M01', 'name': 'stabilize', 'tasks': ['TASK-3', 'TASK-4']},
                       {'id': 'M02', 'name': 'build:features', 'tasks': ['TASK-1', 'TASK-2']},
                       {'id': 'M03', 'name': 'build:pages', 'tasks': []}],
        # TASK-4 (old) touches a file TASK-1 (src/a) also changes, a wave earlier: deleting old waits for it.
        'waves': [{'wave': 1, 'tasks': ['TASK-1', 'TASK-3']}, {'wave': 2, 'tasks': ['TASK-2', 'TASK-4']}],
        'tasks': [{'id': 'TASK-1', 'paths': ['src/a/x.ts', 'old/y.ts']}, {'id': 'TASK-2', 'paths': ['src/a/z.ts']},
                  {'id': 'TASK-3', 'paths': ['src/b/w.ts']}, {'id': 'TASK-4', 'paths': ['old/y.ts']}]}
CARDS = [{'id': 'TASK-1', 'state': 'done'}, {'id': 'TASK-2', 'state': 'open'}, {'id': 'TASK-3', 'state': 'in_batch'},
         {'id': 'TASK-4', 'state': 'open'}]


def records(**over):
    target = {'current_components': CURRENT, 'target_components': TARGETS,
              'decisions': [{'id': 'ADR-001', 'component_id': 'T-a'}]}
    return {'target': target, 'plan': PLAN, 'gap_matrix': {'rows': ROWS}, **over}


class Change(unittest.TestCase):
    def setUp(self):
        gaps, ops = change.change(records(), CARDS, 'en')
        self.gaps = {g['id']: g for g in gaps['gaps']}
        self.ops = {o['id']: o for o in ops['operations']}
        self.order = [o['id'] for o in ops['operations']]
        self.bodies = gaps, ops

    def test_every_component_has_a_gap_with_its_operation_target_decision_and_closure_measured_only_from_cards(self):
        contracts = artifact_contracts.contracts()
        for name, body in zip(('gaps', 'operations'), self.bodies):
            self.assertEqual(artifact_contracts.validate({'schema_version': 1, 'contract': 1, 'revision': 2, **body},
                                                         contracts[f'studio-{name}']), [], name)
        a = self.gaps['src/a']
        self.assertEqual((a['operation'], a['to'], a['responsibility'], a['decision'], a['files']),
                         ('rebuild', 'features', 'One module per domain', 'ADR-001', 4))
        self.assertEqual(self.gaps['src/b']['operation'], 'refactor')
        self.assertEqual(self.gaps['old']['operation'], 'delete')
        self.assertEqual(self.gaps['src/c']['operations'], [], 'a retained component needs no operation')
        self.assertEqual((self.gaps['src/a']['cards_closed'], self.gaps['src/a']['closed']['value']), (1, 0.5))
        self.assertIsNone(self.gaps['src/e']['closed']['value'], 'no card closes it: not measured, never 0')
        self.assertIn('no card', self.gaps['src/e']['closed']['src'])
        self.assertEqual(self.gaps['src/e']['cover'], 'missing')

    def test_operations_come_from_the_target_wait_for_the_cards_follow_the_ledger_and_nothing_without_a_target(self):
        merge, new = self.ops['merge:features'], self.ops['new:home']
        self.assertEqual(merge['sources'], ['src/a', 'src/b'])
        self.assertEqual(self.gaps['target:features']['files'], 6)
        self.assertEqual(new['sources'], [])
        self.assertNotIn('merge:pages', self.ops, 'one source is not a merge')
        self.assertEqual(self.ops['rebuild:src/e']['step'], 'M03')
        self.assertEqual(self.ops['rebuild:src/a']['step'], 'M02')
        self.assertEqual(self.ops['merge:features']['step'], 'M02')
        self.assertIsNone(self.ops['new:home']['step'], 'the plan has no step for it: not planned, not invented')
        self.assertEqual(self.ops['delete:old']['after'], ['rebuild:src/a'])
        self.assertLess(self.order.index('rebuild:src/a'), self.order.index('delete:old'))
        self.assertEqual(self.ops['refactor:src/b']['after'], [])
        self.assertEqual([self.ops[i]['order'] for i in self.order], list(range(1, len(self.order) + 1)))
        self.assertEqual(self.ops['rebuild:src/a']['state'], 'active')
        self.assertEqual(self.ops['refactor:src/b']['state'], 'active')
        self.assertEqual(self.ops['rebuild:src/e']['state'], 'todo')
        self.assertEqual(change.change(records(target={}), CARDS, 'en'), (None, None))


if __name__ == '__main__':
    unittest.main()
