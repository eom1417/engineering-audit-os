"""The handoff cannot point at nonexistent prerequisites or hide dependency cycles."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('handoff_renderer', ROOT / 'tools/render_transformation.py')
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((ROOT / 'docs/transformation.json').read_text())

    def test_real_plan_has_valid_references_and_acyclic_dependencies(self):
        self.assertEqual(renderer.validate(self.plan), [])

    def test_the_next_ready_task_is_a_real_task_whose_prerequisites_are_done(self):
        """Naming the expected id here made the test fail every time work was finished."""
        ready = renderer.ready_tasks(self.plan)
        known = {task['id']: task for task in renderer.tasks(self.plan)}
        for task in ready:
            self.assertIn(task['id'], known)
            self.assertEqual(task['status'], 'todo')
            for prerequisite in task.get('depends_on', []):
                self.assertEqual(known[prerequisite]['status'], 'done',
                                 f"{task['id']} is offered while {prerequisite} is unfinished")

    def test_when_every_task_is_done_nothing_is_offered(self):
        finished = copy.deepcopy(self.plan)
        for task in renderer.tasks(finished):
            task['status'] = 'done'
        self.assertEqual(renderer.ready_tasks(finished), [])

    def test_self_dependency_is_rejected(self):
        task = renderer.tasks(self.plan)[-1]
        task['depends_on'].append(task['id'])
        self.assertTrue(any('cycle' in error for error in renderer.validate(self.plan)))

    def test_missing_existing_reference_is_rejected(self):
        renderer.tasks(self.plan)[0]['reference_details'][0]['path'] = 'missing-reference-should-not-exist'
        self.assertTrue(any('missing reference' in error for error in renderer.validate(self.plan)))

    def test_future_reference_requires_its_producing_task(self):
        task = next(t for t in renderer.tasks(self.plan) if t['id'] == 'M4.T4')
        task['depends_on'].remove('M4.T1')
        self.assertTrue(any('unbound future reference' in error for error in renderer.validate(self.plan)))
