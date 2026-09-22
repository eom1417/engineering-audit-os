import tempfile
import unittest
from pathlib import Path

from eaos.execution_guide import document


class ExecutionGuideTests(unittest.TestCase):
    def test_every_task_keeps_literal_execution_fields_in_wave_order(self):
        plan = {
            'tasks': [
                {'id': 'TASK-002', 'title': 'second', 'impact': 'second goal.',
                 'paths': ['src/b.py'], 'change': 'Edit src/b.py.',
                 'acceptance': [{'command': 'python check_b.py', 'expect': 'exit 0'}],
                 'rollback': 'git revert B', 'prerequisites': ['TASK-001']},
                {'id': 'TASK-001', 'title': 'first', 'impact': 'first goal.',
                 'paths': ['src/a.py'], 'change': 'Edit src/a.py.',
                 'acceptance': [{'command': 'python check_a.py', 'expect': 'exit 0'}],
                 'rollback': 'git revert A', 'prerequisites': []},
            ],
            'waves': [{'wave': 1, 'tasks': ['TASK-001']}, {'wave': 2, 'tasks': ['TASK-002']}],
        }
        transform = {'stages': [{'stage': 1, 'sites': [{'path': 'src/a.py'}],
                                 'steps': ['Preserve Symbol.literal.']} ]}
        load = {'entry_points': [{'path': 'src/a.py',
                                  'projection': {'bottlenecks': ['no_rate_limit']}}]}

        body = document(plan, transform, load)

        self.assertIn('## اقرأ هذا أولًا', body)
        self.assertLess(body.index('TASK-001'), body.index('TASK-002'))
        for literal in ('`src/a.py`', '1. Edit src/a.py.', '2. Preserve Symbol.literal.',
                        '`python check_a.py`', 'git revert A', '`TASK-001`', 'no_rate_limit'):
            self.assertIn(literal, body)

        english = document(plan, transform, load, language='en')
        self.assertIn('## Read this first', english)
        self.assertNotIn('اقرأ', english)

    def test_a_real_audit_guide_contains_every_plan_task_within_budget(self):
        out = Path('/tmp/eg')
        if not (out / 'EXECUTION-GUIDE.md').is_file():
            self.skipTest('acceptance audit has not populated /tmp/eg')
        import json
        plan = json.loads((out / 'plan.json').read_text(encoding='utf-8'))
        body = (out / 'EXECUTION-GUIDE.md').read_text(encoding='utf-8')
        self.assertLessEqual(len(body.splitlines()), 300)
        for task in plan['tasks']:
            self.assertEqual(body.count(f"**{task['id']} /"), 1)
            for path in task.get('paths', []):
                self.assertIn(f'`{path}`', body)


if __name__ == '__main__':
    unittest.main()
