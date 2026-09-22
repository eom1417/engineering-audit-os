"""The handoff cannot point at nonexistent prerequisites or hide dependency cycles."""
import copy
import importlib.util
import json
import tempfile
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


class RunnableStageAcceptanceTests(unittest.TestCase):
    def test_every_real_stage_has_a_valid_behavioral_command(self):
        import tempfile
        from eaos.audit import run
        from eaos.decisions import check_errors
        with tempfile.TemporaryDirectory() as out:
            run(ROOT, out, language='en')
            plan = json.loads(Path(out, 'transform-plan.json').read_text(encoding='utf-8'))
        self.assertTrue(plan['stages'])
        for stage in plan['stages']:
            check = stage['acceptance']
            self.assertEqual(check_errors(check), [], stage['stage'])
            self.assertIsInstance(check['argv'], list)
            self.assertEqual(check['cwd'], '.')
            self.assertIs(type(check['expected_exit']), int)

    def test_a_repository_without_tests_gets_a_declared_fallback(self):
        import tempfile
        from eaos.transform_plan import _stage_acceptance
        with tempfile.TemporaryDirectory() as out:
            facts = Path(out, 'facts'); facts.mkdir()
            target = Path(out, 'candidate'); target.mkdir()
            Path(facts, 'run.json').write_text(json.dumps({'target': str(target)}), encoding='utf-8')
            check = _stage_acceptance('canonicalize', [{'path': 'app.py'}], out, 1)
        self.assertEqual(check['origin'], 'generated_equivalence_fallback')
        self.assertEqual(check['argv'][1:4], ['-m', 'compileall', '-q'])

    def test_report_regeneration_is_never_an_acceptance_command(self):
        from eaos.decisions import check_errors
        check = {'id': 'x', 'kind': 'command', 'invariant': 'behavior', 'expected': 'passes',
                 'source_revision': 'candidate', 'argv': ['eaos', 'facts', '.'],
                 'cwd': '.', 'expected_exit': 0}
        self.assertIn('report regeneration is not behavioral acceptance', check_errors(check))


class StageCommandStringTests(unittest.TestCase):
    """Every real stage's acceptance must carry a `command` string the runner can paste."""

    def test_every_real_stage_has_a_command_string(self):
        """Read a real transform-plan.json and assert every stage has a non-empty command."""
        from pathlib import Path
        import json
        plan_path = Path(__file__).resolve().parents[1] / 'docs' / 'transform-plan.json'
        if not plan_path.is_file():
            self.skipTest('no recorded transform-plan.json yet')
        plan = json.loads(plan_path.read_text(encoding='utf-8'))
        stages = plan.get('stages', [])
        self.assertGreater(len(stages), 0)
        for stage in stages:
            acceptance = stage.get('acceptance') or {}
            command = acceptance.get('command')
            argv = acceptance.get('argv')
            self.assertIsInstance(command, str,
                                    f'stage {stage["stage"]} missing acceptance.command')
            self.assertTrue(command.strip(),
                             f'stage {stage["stage"]} has an empty acceptance.command')
            # argv is the list form the automated runner uses; command is the joined paste form.
            self.assertIsInstance(argv, list,
                                    f'stage {stage["stage"]} missing acceptance.argv')
            self.assertGreater(len(argv), 0,
                                f'stage {stage["stage"]} has empty acceptance.argv')
            self.assertEqual(command, ' '.join(argv),
                              f'stage {stage["stage"]} command disagrees with argv: '
                              f'{command!r} vs {" ".join(argv)!r}')

    def test_a_synthetic_stage_command_equals_joined_argv(self):
        """A stage built in-memory gets the command string for free."""
        from eaos.transform_plan import _stage_acceptance
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'app.py').write_text('VALUE = 1\n')
            sites = [{'path': 'app.py', 'line': 1, 'symbol': 'VALUE'}]
            # When there are no tests, the fallback is the compileall invocation.
            acceptance = _stage_acceptance('canonicalize', sites, out=Path(tmp), stage=7)
            self.assertIsInstance(acceptance, dict)
            self.assertEqual(acceptance['kind'], 'command')
            self.assertIsInstance(acceptance['command'], str)
            self.assertEqual(acceptance['command'], ' '.join(acceptance['argv']))
            self.assertIn('compileall', acceptance['command'])
