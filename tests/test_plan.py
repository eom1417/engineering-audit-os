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


class CardLanguageTests(unittest.TestCase):
    """A card is read by the same person who read the brief; it speaks the same language."""

    def test_cards_and_waves_render_in_the_reader_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            assemble(FIXTURE, out)
            build(FIXTURE, out, language='ar')
            waves_text = (out / 'PLAN/WAVES.md').read_text()
            self.assertIn('معرّف في', waves_text + (out / 'PLAN/TASK-001.md').read_text())

    def test_english_rendering_stays_english(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            assemble(FIXTURE, out, language='en')
            build(FIXTURE, out, language='en')
            text = (out / 'PLAN/TASK-001.md').read_text()
            self.assertIn('is defined in', text)
            self.assertNotIn('معرّف في', text)


class PatternCoverageTests(unittest.TestCase):
    """Every claim class the tool can detect must have a remediation pattern, or cards say nothing useful."""

    def test_each_detectable_class_maps_to_a_named_pattern(self):
        queries = {'cycle_present': 'import_cycle', 'flow_has_unresolved_steps': 'trace_gap',
                   'no_code_dependency': 'hidden_coupling', 'metric_threshold': 'hotspot',
                   'mutable_global_present': 'mutable_state', 'external_write_present': 'external_write',
                   'policy_violation_present': 'policy_violation'}
        for query, expected in queries.items():
            claim = {'probe_spec': {'probe_type': 'graph_query', 'specification': {'query': query}}}
            self.assertEqual(classify(claim), expected, query)
            pattern = pattern_for(claim)
            self.assertNotEqual(pattern['name'], 'generic')
            self.assertTrue(pattern['change'] and pattern['rollback'])
            self.assertIn('لا نفعل شيئًا', [option['option'] for option in pattern['options']])

    def test_no_generated_card_falls_back_to_the_generic_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            assemble(FIXTURE, out)
            plan = build(FIXTURE, out)
            tasks = json.loads((out / 'plan.json').read_text())['tasks']
            self.assertTrue(tasks)
            self.assertEqual([task['id'] for task in tasks if task['pattern'] == 'generic'], [])

    def test_the_consequence_line_is_translated_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            assemble(FIXTURE, out)
            build(FIXTURE, out, language='ar')
            text = ' '.join(path.read_text() for path in (out / 'PLAN').glob('TASK-*.md'))
            self.assertIn('مسارين يختلفان', text)
            self.assertNotIn('makes two paths disagree', text)


class HypothesisTaskTests(unittest.TestCase):
    """An unproven claim is work too: prove it or drop it, never change code on it."""

    def test_a_hypothesis_becomes_an_investigation_not_a_change(self):
        from eaos import claims as ledger
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            assemble(FIXTURE, out)
            dossier = json.loads((out / 'dossier.json').read_text())
            guess = ledger.make(901, 'The pricing module probably owns the tax rule as well', 'responsibility',
                                'HYPOTHESIS', ['model_inference'], [], 'A second module applying tax without importing it',
                                fact_ids=dossier['claims'][0]['fact_ids'], origin='source')
            dossier['claims'].append(guess)
            (out / 'dossier.json').write_text(json.dumps(dossier, ensure_ascii=False))
            build(FIXTURE, out)
            tasks = json.loads((out / 'plan.json').read_text())['tasks']
            investigation = next(task for task in tasks if task['claim_id'] == guess['id'])
            self.assertEqual(investigation['kind'], 'investigate')
            self.assertEqual(investigation['pattern'], 'investigation')
            self.assertIn('أثبت هذا الادعاء أو انقضه', investigation['change'])
            self.assertIn('CONFIRMED or REFUTED', ' '.join(step['expect'] for step in investigation['acceptance']))
            self.assertIn('لا تغيير في الكود', investigation['rollback'])
