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
        self.assertEqual(renderer.ready_tasks(self.plan)[0]['id'], 'M12.T1')

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
