"""Rendering stays within its declared budget at any project size, and publishes all-or-nothing."""
import unittest


class BudgetTrimmingTests(unittest.TestCase):
    """A document that outgrows its budget must trim its longest table, not crash the command."""

    def test_a_large_table_is_trimmed_to_the_budget_with_the_real_total_reported(self):
        from eaos.compose import Document
        document = Document('Waves', 'en', budget_lines=40)
        document.table(['#', 'task'], [[str(index), f'task {index}'] for index in range(200)])
        text = document.render()
        self.assertLessEqual(text.count('\n'), 40)
        self.assertIn('of 200', text)

    def test_trimming_stops_at_one_row_and_reports_the_overflow_as_a_renderer_bug(self):
        from eaos.compose import Document
        document = Document('Prose', 'en', budget_lines=4)
        document.bullets([f'line {index}' for index in range(50)])
        with self.assertRaises(ValueError):
            document.render()

    def test_a_table_within_budget_keeps_every_row_and_adds_no_note(self):
        from eaos.compose import Document
        document = Document('Small', 'en', budget_lines=100)
        document.table(['#'], [[str(index)] for index in range(5)])
        text = document.render()
        for value in range(5):
            self.assertIn(f'| {value} |', text)
        self.assertNotIn('Showing', text)

    def test_the_wave_document_survives_a_project_with_many_tasks(self):
        from eaos.plan import waves_document, waves
        tasks = [{'id': f'TASK-{index:03d}', 'title': f'task {index}', 'kind': 'repair', 'priority': 3,
                  'paths': [f'module_{index}.py'], 'claim_id': f'CLM-{index:03d}'} for index in range(120)]
        text = waves_document(waves(tasks), tasks, 'en').render()
        self.assertLessEqual(text.count('\n'), 140)


class PlanPublishingTests(unittest.TestCase):
    """A failed render must not leave task cards on disk without the wave document that orders them."""

    def test_publish_writes_nothing_when_a_card_fails_to_render(self):
        import tempfile
        from pathlib import Path
        from eaos import plan as plan_module
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'PLAN'
            target.mkdir()
            (target / 'TASK-000.md').write_text('stale', encoding='utf-8')
            broken = [{'id': 'TASK-001'}]
            with self.assertRaises(Exception):
                plan_module.publish(target, broken, [], 'en')
            self.assertEqual([path.name for path in target.iterdir()], ['TASK-000.md'])


class WaveDocumentTests(unittest.TestCase):
    """Wave conditions identical across every wave are stated once, not once per wave."""

    def _plan(self, waves_count):
        tasks = [{'id': f'TASK-{index:03d}', 'title': f'task {index}', 'kind': 'repair', 'priority': 1,
                  'paths': [f'module_{index}.py'], 'claim_id': f'CLM-{index:03d}'} for index in range(waves_count)]
        from eaos.plan import waves
        return waves(tasks), tasks

    def test_identical_conditions_appear_once(self):
        from eaos.plan import waves_document
        plan, tasks = self._plan(8)
        text = waves_document(plan, tasks, 'en').render()
        self.assertEqual(text.count('entry: '), 1)

    def test_conditions_that_differ_are_printed_on_their_own_wave(self):
        from eaos.plan import waves_document
        plan, tasks = self._plan(3)
        plan[0] = dict(plan[0], entry_condition='a different entry')
        text = waves_document(plan, tasks, 'en').render()
        self.assertEqual(text.count('entry: '), len(plan))
        self.assertIn('a different entry', text)
