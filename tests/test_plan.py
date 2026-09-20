"""Task cards and waves: the difference between a report and work that can be handed over."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from eaos import cli
from eaos.dossier import assemble
from eaos.plan import build, waves
from eaos.remediation_patterns import classify, pattern_for

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'


class TaskCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / 'out'
        assemble(FIXTURE, cls.out)
        cls.result = build(FIXTURE, cls.out)
        cls.plan = json.loads((cls.out / 'plan.json').read_text())

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def test_a_card_exists_for_every_actionable_claim(self):
        dossier = json.loads((self.out / 'dossier.json').read_text())
        actionable = [claim for claim in dossier['claims'] if claim['confidence'] in {'CONFIRMED', 'LIKELY'}]
        self.assertEqual(len(self.plan['tasks']), len(actionable))
        for task in self.plan['tasks']:
            self.assertTrue((self.out / 'PLAN' / (task['id'] + '.md')).is_file())

    def test_every_card_carries_the_mandatory_fields(self):
        text = (self.out / 'PLAN/TASK-001.md').read_text()
        for heading in ['المشكلة', 'الدليل', 'نطاق الأثر', 'الخيارات', 'التغيير المقترح',
                        'معيار القبول', 'التراجع', 'التقدير']:
            self.assertIn(heading, text, heading)

    def test_every_option_set_includes_doing_nothing_and_its_cost(self):
        for task in self.plan['tasks']:
            options = [option['option'] for option in task['options']]
            self.assertIn('لا نفعل شيئًا', options)
            nothing = next(option for option in task['options'] if option['option'] == 'لا نفعل شيئًا')
            self.assertTrue(nothing['verdict'])

    def test_acceptance_is_runnable_and_derived_from_the_probe(self):
        task = next(task for task in self.plan['tasks'] if task['pattern'] == 'duplicated_rule')
        commands = ' '.join(step['command'] for step in task['acceptance'])
        self.assertIn('eaos probe', commands)
        self.assertIn(task['claim_id'], ' '.join(step['expect'] for step in task['acceptance']))
        self.assertTrue(task['verify_command'])

    def test_blast_radius_comes_from_facts_not_prose(self):
        task = next(task for task in self.plan['tasks'] if 'core/pricing.py' in task['paths'])
        self.assertIn('cli.py', task['blast_radius']['direct_dependents'])
        self.assertGreater(task['blast_radius']['total'], 0)

    def test_effort_states_its_own_confidence(self):
        for task in self.plan['tasks']:
            self.assertIn(task['effort'], {'صغير', 'متوسط', 'كبير'})
            self.assertTrue(task['effort_confidence'])

    def test_the_output_contract_accepts_the_generated_plan(self):
        from eaos.compose.rules import validate
        dossier = json.loads((self.out / 'dossier.json').read_text())
        self.assertEqual([problem for problem in validate(self.out, dossier) if problem.startswith('R7')], [])

    def test_cli_exposes_the_generator(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as printed:
            out = Path(tmp) / 'out'
            assemble(FIXTURE, out)
            self.assertEqual(cli.main(['tasks', str(FIXTURE), '--out', str(out)]), 0)
        self.assertGreater(json.loads(printed.getvalue())['tasks'], 0)

    def test_planning_without_a_dossier_fails_clearly(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'Build a dossier'):
                build(FIXTURE, Path(tmp))


class PatternTests(unittest.TestCase):
    def test_each_claim_class_maps_to_its_own_pattern(self):
        cases = [
            ({'probe_spec': {'probe_type': 'graph_query', 'specification': {'query': 'cycle_present'}}}, 'import_cycle'),
            ({'probe_spec': {'probe_type': 'absence_search', 'specification': {}}}, 'duplicated_rule'),
            ({'probe_spec': {'probe_type': 'graph_query', 'specification': {'query': 'no_code_dependency'}}}, 'hidden_coupling'),
            ({'claim_type': 'risk', 'statement': '3 files were never executed by the test command'}, 'untested_path'),
        ]
        for claim, expected in cases:
            self.assertEqual(classify(claim), expected)

    def test_an_unknown_class_says_so_instead_of_inventing_a_fix(self):
        pattern = pattern_for({'claim_type': 'cost', 'statement': 'something unusual'})
        self.assertEqual(pattern['name'], 'generic')
        self.assertIn('⧗', pattern['change'])


class WaveTests(unittest.TestCase):
    def task(self, identifier, paths, priority=1.0, kind='remediate'):
        return {'id': identifier, 'paths': paths, 'priority': priority, 'kind': kind}

    def test_tasks_touching_the_same_file_never_share_a_wave(self):
        plan = waves([self.task('TASK-001', ['a.py']), self.task('TASK-002', ['a.py', 'b.py']),
                      self.task('TASK-003', ['c.py'])])
        placement = {identifier: wave['wave'] for wave in plan for identifier in wave['tasks']}
        self.assertNotEqual(placement['TASK-001'], placement['TASK-002'])
        self.assertEqual(placement['TASK-003'], 1)

    def test_investigations_come_before_the_changes_they_inform(self):
        plan = waves([self.task('TASK-001', ['a.py'], priority=0.9),
                      self.task('TASK-002', ['a.py'], priority=0.1, kind='investigate')])
        self.assertEqual(plan[0]['tasks'], ['TASK-002'])

    def test_each_wave_declares_entry_and_exit_conditions(self):
        plan = waves([self.task('TASK-001', ['a.py'])])
        self.assertTrue(plan[0]['entry_condition'] and plan[0]['exit_condition'])
