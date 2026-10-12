"""Task cards and waves: the difference between a report and work that can be handed over."""
import json
from pathlib import Path
import tempfile
import unittest
from shared_fixture import TemporaryWorkspace
from eaos import claims as ledger
from eaos import plan as plan_module
from eaos.compose import Document
from eaos.compose.rules import validate
from eaos.dossier import assemble
from eaos.plan import build, waves, waves_document
from eaos.remediation_patterns import PATTERNS, _ENGINE_CLUSTER_KINDS, classify, cost_of_inaction, pattern_for

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'
NOTHING = 'لا نفعل شيئًا'


class TaskCardTests(TemporaryWorkspace):
    @classmethod
    def setUpClass(cls):
        cls.out = Path(cls.workspace().name) / 'out'
        assemble(FIXTURE, cls.out)
        build(FIXTURE, cls.out)
        cls.plan = json.loads((cls.out / 'plan.json').read_text())
        cls.dossier = json.loads((cls.out / 'dossier.json').read_text())

    def test_every_actionable_claim_gets_one_complete_card(self):
        actionable = [c for c in self.dossier['claims'] if c['confidence'] in {'CONFIRMED', 'LIKELY'}]
        self.assertEqual(len(self.plan['tasks']), len(actionable))
        self.assertEqual([t['id'] for t in self.plan['tasks'] if t['pattern'] == 'generic'], [])
        for task in self.plan['tasks']:
            with self.subTest(task=task['id']):
                self.assertTrue((self.out / 'PLAN' / (task['id'] + '.md')).is_file())
                nothing = next(o for o in task['options'] if o['option'] == NOTHING)
                self.assertTrue(nothing['verdict'])
                self.assertIn(task['effort'], {'S', 'M', 'L'})
                self.assertEqual(set(task['effort_basis']), {'files', 'dependents'})
                self.assertTrue(task['effort_confidence'])
        text = (self.out / 'PLAN/TASK-001.md').read_text()
        for heading in ['المشكلة', 'الدليل', 'نطاق الأثر', 'الخيارات', 'التغيير المقترح', 'معيار القبول', 'التراجع', 'التقدير']:
            self.assertIn(heading, text)
        cards = ' '.join(path.read_text() for path in (self.out / 'PLAN').glob('TASK-*.md'))
        self.assertIn('مسارين يختلفان', cards)
        self.assertNotIn('makes two paths disagree', cards)
        self.assertEqual([p for p in validate(self.out, self.dossier) if p.startswith('R7')], [])

    def test_a_design_decision_card_asks_for_a_recorded_decision_not_a_fake_check(self):
        # PREMIUM_DISCOUNT is repeated across TypeScript and Python: where its one home lives is a design decision
        task = next(task for task in self.plan['tasks'] if task['pattern'] == 'duplicated_rule')
        self.assertIn('-m eaos decided', ' '.join(step['command'] for step in task['acceptance']))
        self.assertIn(task['claim_id'], ' '.join(step['expect'] for step in task['acceptance']))
        self.assertEqual((task['verify_command'], task['kind']), ([], 'investigate'))

    def test_blast_radius_comes_from_facts_not_prose(self):
        task = next(task for task in self.plan['tasks'] if 'core/pricing.py' in task['paths'])
        self.assertIn('cli.py', task['blast_radius']['direct_dependents'])
        self.assertGreater(task['blast_radius']['total'], 0)

    def test_planning_without_a_dossier_fails_clearly(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, 'Build a dossier'):
            build(FIXTURE, Path(tmp))


class AddedClaimTests(unittest.TestCase):
    def test_a_hypothesis_becomes_an_investigation_a_fileless_card_says_so_and_english_stays_english(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            assemble(FIXTURE, out)
            dossier = json.loads((out / 'dossier.json').read_text())
            guess = ledger.make(901, 'The pricing module probably owns the tax rule as well', 'responsibility',
                                'HYPOTHESIS', ['model_inference'], [], 'A second module applying tax without importing it',
                                fact_ids=dossier['claims'][0]['fact_ids'], origin='source')
            wide = ledger.make(902, 'Two products share one command line and the docs cover only one',
                               'structure', 'HYPOTHESIS', ['model_inference'], ['SRC-1'],
                               'A document stating which path serves which need', origin='source')
            dossier['claims'] += [guess, wide]
            (out / 'dossier.json').write_text(json.dumps(dossier, ensure_ascii=False))
            build(FIXTURE, out)
            tasks = json.loads((out / 'plan.json').read_text())['tasks']
            card = next(p.read_text() for p in (out / 'PLAN').glob('TASK-*.md')
                        if 'Two products share one command line' in p.read_text())
        investigation = next(task for task in tasks if task['claim_id'] == guess['id'])
        self.assertEqual((investigation['kind'], investigation['pattern']), ('investigate', 'investigation'))
        self.assertIn('أثبت هذا الادعاء أو انقضه', investigation['change'])
        self.assertIn('a recorded decision', ' '.join(step['expect'] for step in investigation['acceptance']))
        self.assertIn('لا تغيير في الكود', investigation['rollback'])
        self.assertIn('لا يشير إلى ملف بعينه', card)
        # English cards stay English.
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            assemble(FIXTURE, out, language='en')
            build(FIXTURE, out, language='en')
            text = (out / 'PLAN/TASK-001.md').read_text()
        self.assertIn('is defined in', text)
        self.assertNotIn('معرّف في', text)


def graph_claim(query, **specification):
    return {'probe_spec': {'probe_type': 'graph_query', 'specification': {'query': query, **specification}}}


class PatternTests(unittest.TestCase):
    """Every claim class the tool can detect has a real remediation pattern, or cards say nothing useful."""

    def test_each_detectable_class_maps_to_a_complete_pattern_and_an_unknown_one_says_so(self):
        cases = [(graph_claim(query), expected) for query, expected in {
            'cycle_present': 'import_cycle', 'flow_has_unresolved_steps': 'trace_gap',
            'no_code_dependency': 'hidden_coupling', 'metric_threshold': 'hotspot',
            'mutable_global_present': 'mutable_state', 'external_write_present': 'external_write',
            'policy_violation_present': 'policy_violation'}.items()]
        cases += [(graph_claim('engine_cluster_present', kind=kind), expected) for kind, expected in {
            'complexity': 'hotspot', 'coupling': 'hidden_coupling', 'literal_duplication': 'canonicalize',
            'dead_code': 'dead_code'}.items()]
        cases += [({'probe_spec': {'probe_type': 'absence_search', 'specification': {}}}, 'duplicated_rule'),
                  ({'claim_type': 'risk', 'statement': '3 files were never executed by the test command'}, 'untested_path')]
        for claim, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(classify(claim), expected)
                pattern = pattern_for(claim)
                self.assertTrue(pattern['change'] and pattern['rollback'])
                self.assertIn(NOTHING, [option['option'] for option in pattern['options']])
        for kind, name in _ENGINE_CLUSTER_KINDS.items():
            self.assertIn(name, PATTERNS, kind)
        dead = pattern_for(graph_claim('engine_cluster_present', kind='dead_code'))
        self.assertGreaterEqual(len(dead['options']), 3)
        self.assertLessEqual({'منخفضة', 'متوسطة'}, {option.get('cost') for option in dead['options']})
        self.assertIn('الكود الميت', cost_of_inaction('dead_code'))
        # An unknown class says so instead of inventing a fix.
        self.assertIn('⧗', pattern_for({'claim_type': 'cost', 'statement': 'something unusual'})['change'])
        for claim, reason in [(graph_claim('engine_cluster_present', kind='unknown_kind_xyz'), 'unknown_kind_xyz'),
                              (graph_claim('engine_cluster_present'), 'absent')]:
            with self.subTest(reason=reason):
                self.assertEqual(classify(claim), 'generic')
                self.assertIn(reason, pattern_for(claim)['fallback_reason'])


def tasks_of(count, priority=1):
    return [{'id': f'TASK-{index:03d}', 'title': f'task {index}', 'kind': 'repair', 'priority': priority,
             'paths': [f'module_{index}.py'], 'claim_id': f'CLM-{index:03d}'} for index in range(count)]


class WaveTests(unittest.TestCase):
    def task(self, identifier, paths, priority=1.0, kind='remediate'):
        return {'id': identifier, 'paths': paths, 'priority': priority, 'kind': kind}

    def test_waves_never_share_a_file_put_investigations_first_and_read_well_at_any_size(self):
        plan = waves([self.task('TASK-001', ['a.py']), self.task('TASK-002', ['a.py', 'b.py']),
                      self.task('TASK-003', ['c.py'])])
        placement = {identifier: wave['wave'] for wave in plan for identifier in wave['tasks']}
        self.assertNotEqual(placement['TASK-001'], placement['TASK-002'])
        self.assertEqual(placement['TASK-003'], 1)
        self.assertTrue(all(wave['entry_condition'] and wave['exit_condition'] for wave in plan))
        plan = waves([self.task('TASK-001', ['a.py'], priority=0.9),
                      self.task('TASK-002', ['a.py'], priority=0.1, kind='investigate')])
        self.assertEqual(plan[0]['tasks'], ['TASK-002'])
        # The wave document stays readable at any size.
        small = tasks_of(4)
        self.assertIn('## Wave 1', waves_document(waves(small), small, 'en').render())
        for count in (83, 120):
            tasks = tasks_of(count, priority=3)
            text = waves_document(waves(tasks), tasks, 'en').render()
            self.assertLessEqual(text.count('\n'), 140, count)
            self.assertTrue(all(task['id'] in text for task in tasks), count)
        tasks = tasks_of(8)
        self.assertEqual(waves_document(waves(tasks), tasks, 'en').render().count('entry: '), 1)
        tasks = tasks_of(3)
        plan = waves(tasks)
        plan[0] = dict(plan[0], entry_condition='a different entry')
        text = waves_document(plan, tasks, 'en').render()
        self.assertEqual(text.count('entry: '), len(plan))
        self.assertIn('a different entry', text)

    def test_a_document_keeps_its_budget_and_a_failed_render_publishes_nothing(self):
        document = Document('Waves', 'en', budget_lines=40)
        document.table(['#', 'task'], [[str(index), f'task {index}'] for index in range(200)])
        text = document.render()
        self.assertLessEqual(text.count('\n'), 40)
        self.assertIn('of 200', text)
        document = Document('Small', 'en', budget_lines=100)
        document.table(['#'], [[str(index)] for index in range(5)])
        text = document.render()
        self.assertTrue(all(f'| {value} |' in text for value in range(5)))
        self.assertNotIn('Showing', text)
        prose = Document('Prose', 'en', budget_lines=4)
        prose.bullets([f'line {index}' for index in range(50)])
        with self.assertRaises(ValueError):
            prose.render()
        # Publishing writes nothing when a card fails to render.
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'PLAN'
            target.mkdir()
            (target / 'TASK-000.md').write_text('stale', encoding='utf-8')
            with self.assertRaises(Exception):
                plan_module.publish(target, [{'id': 'TASK-001'}], [], 'en')
            self.assertEqual([path.name for path in target.iterdir()], ['TASK-000.md'])
