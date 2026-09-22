import tempfile
import unittest
from pathlib import Path
import json
import re
import shlex

from eaos.execution_guide import FORBIDDEN_TOKENS, _transform_for, document


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
        plan = json.loads((out / 'plan.json').read_text(encoding='utf-8'))
        body = (out / 'EXECUTION-GUIDE.md').read_text(encoding='utf-8')
        self.assertLessEqual(len(body.splitlines()), 300)
        for task in plan['tasks']:
            self.assertEqual(body.count(f"**{task['id']} /"), 1)
            for path in task.get('paths', []):
                self.assertIn(f'`{path}`', body)

    def test_real_cards_are_mechanically_executable(self):
        out = Path('/tmp/eg')
        if not (out / 'EXECUTION-GUIDE.md').is_file():
            self.skipTest('acceptance audit has not populated /tmp/eg')
        plan = json.loads((out / 'plan.json').read_text(encoding='utf-8'))
        transform = json.loads((out / 'transform-plan.json').read_text(encoding='utf-8'))
        run = json.loads((out / 'facts/run.json').read_text(encoding='utf-8'))
        target = Path(run['target'])
        order = {}
        for wave in plan['waves']:
            for position, task_id in enumerate(wave['tasks']):
                order[task_id] = (wave['wave'], position)

        for task in plan['tasks']:
            with self.subTest(task=task['id']):
                self.assertTrue(task.get('paths'))
                for path in task['paths']:
                    self.assertTrue((target / path).exists(), f'{task["id"]}: missing {path}')

                checks = task.get('acceptance') or []
                self.assertTrue(checks, f'{task["id"]}: no acceptance command')
                for check in checks:
                    argv = shlex.split(check.get('command', ''))
                    self.assertTrue(argv, f'{task["id"]}: acceptance is not argv')
                    self._assert_concrete(check['command'], task['id'])

                stage = _transform_for(task, transform.get('stages', []))
                steps = [task.get('change'), *(stage or {}).get('steps', [])]
                self.assertTrue(all(steps), f'{task["id"]}: empty step')
                for step in steps:
                    self.assertNotIn('\n', step, f'{task["id"]}: step spans sentences')
                    self.assertLessEqual(len(re.findall(r'[.!?؟](?:\s|$)', step)), 1,
                                         f'{task["id"]}: step is not one sentence')
                    self._assert_concrete(step, task['id'])

                self.assertTrue(str(task.get('rollback', '')).strip(), f'{task["id"]}: empty rollback')
                for dependency in task.get('prerequisites', []):
                    dependency_id = dependency['task_id'] if isinstance(dependency, dict) else dependency
                    self.assertIn(dependency_id, order, f'{task["id"]}: unknown dependency')
                    self.assertLess(order[dependency_id], order[task['id']],
                                    f'{task["id"]}: dependency follows task')

    def _assert_concrete(self, text, task_id):
        folded = text.casefold()
        found = [token for token in FORBIDDEN_TOKENS if token.casefold() in folded]
        self.assertEqual(found, [], f'{task_id}: ambiguous token(s) {found}')

    def test_forbidden_tokens_cover_omission_approximation_and_placeholders(self):
        for token in ('...', '…', 'approximately', 'maybe', 'as needed', 'TBD', '<placeholder>', 'ربما'):
            self.assertIn(token, FORBIDDEN_TOKENS)


if __name__ == '__main__':
    unittest.main()
