"""The dossier as one readable unit: an index, cross-links, one language, and grounded answers."""
import json
from pathlib import Path
import tempfile
import unittest
from eaos.ask import answer
from eaos.compose.labels import detail_artifact, statement_of
from eaos.compose.rules import validate
from eaos.dossier import assemble

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'


class IndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / 'out'
        assemble(FIXTURE, cls.out)

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def test_the_dossier_opens_with_an_index_and_a_reading_order(self):
        text = (self.out / 'README.md').read_text()
        self.assertIn('DECISION-BRIEF.md', text)
        self.assertIn('ONBOARDING.md', text)
        self.assertIn('eaos impact-of', text)

    def test_every_section_declares_how_well_it_is_sourced(self):
        text = (self.out / 'README.md').read_text()
        for section in ['SYSTEM-MAP.md', 'FLOWS.md', 'VERIFICATION-MAP.md']:
            self.assertIn(section, text)
        self.assertIn('not assessed: needs the model path', text)

    def test_a_missing_index_fails_the_output_contract(self):
        dossier = json.loads((self.out / 'dossier.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            bare = Path(tmp)
            (bare / 'DECISION-BRIEF.md').write_text('# brief\n\nالتغطية: 1\n\n⬤ x\n\n## ما لم يُفحص\n\n- none\n')
            self.assertTrue(any(problem.startswith('R12') for problem in validate(bare, dossier)))

    def test_the_brief_links_to_the_artifact_holding_the_detail(self):
        text = (self.out / 'DECISION-BRIEF.md').read_text()
        self.assertIn('](DOMAIN-AND-DATA.md)', text)
        self.assertEqual([problem for problem in validate(self.out, json.loads((self.out / 'dossier.json').read_text()))
                          if problem.startswith('R12')], [])

    def test_claims_render_in_the_reader_language(self):
        claim = {'statement': 'Import cycle between: a.py, b.py', 'render': {'key': 'cycle', 'params': {'members': 'a.py, b.py'}}}
        self.assertEqual(statement_of(claim, 'ar'), 'دورة استيراد بين: a.py, b.py')
        self.assertEqual(statement_of(claim, 'en'), 'Import cycle between: a.py, b.py')

    def test_a_claim_without_a_template_keeps_its_own_words(self):
        claim = {'statement': 'something specific', 'render': {}}
        self.assertEqual(statement_of(claim, 'ar'), 'something specific')
        self.assertIsNone(detail_artifact(claim))

    def test_the_arabic_dossier_reads_in_arabic(self):
        text = (self.out / 'DECISION-BRIEF.md').read_text()
        self.assertIn('معرّف في', text)
        self.assertNotIn('is defined in', text)

    def test_the_onboarding_runbook_answers_day_one_questions(self):
        text = (self.out / 'ONBOARDING.md').read_text()
        for heading in ['ابنِ وشغّل', 'اختبر', 'نقاط الدخول لتجربتها', 'أول عشرة ملفات تقرؤها', 'مصائد معروفة']:
            self.assertIn(heading, text)


class AskRankingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / 'out'
        assemble(FIXTURE, cls.out)

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def test_a_question_about_a_route_returns_the_entry_point_first(self):
        result = answer(self.out, 'what handles POST /orders')
        self.assertEqual(result['answers'][0]['kind'], 'entry point')

    def test_every_answer_comes_with_a_next_step(self):
        result = answer(self.out, 'orders')
        self.assertTrue(result['next_questions'])
        self.assertTrue(any('impact-of' in suggestion for suggestion in result['next_questions']))

    def test_an_unanswerable_question_suggests_nothing_and_says_why(self):
        result = answer(self.out, 'zzzqxv nonexistent subsystem')
        self.assertEqual(result['next_questions'], [])
        self.assertIn('No record answers', result['note'])


class AskRobustnessTests(unittest.TestCase):
    """Every record kind must survive being indexed, whatever shape its value has."""

    def test_domain_facts_without_a_name_field_do_not_break_the_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'settings.py').write_text('LIMIT = 10\n')
            (repo / 'main.py').write_text('import argparse\nimport settings\n\n\ndef main():\n'
                                          '    argparse.ArgumentParser(prog="x").parse_args()\n    settings.LIMIT = 1\n')
            out = Path(tmp) / 'out'
            assemble(repo, out)
            result = answer(out, 'settings LIMIT')
            self.assertEqual(result['status'], 'ANSWERED')
            self.assertTrue(any('settings' in row['text'] for row in result['answers']))


class ViewFreshnessTests(unittest.TestCase):
    """Regression: the index said tasks 0 while ten cards sat next to it."""

    def test_the_index_reflects_the_plan_once_it_exists(self):
        from eaos.plan import build
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            assemble(FIXTURE, out)
            self.assertIn('tasks 0', (out / 'README.md').read_text())
            build(FIXTURE, out)
            text = (out / 'README.md').read_text()
            self.assertNotIn('tasks 0', text)
            self.assertIn('waves', text)

    def test_a_probe_verdict_reaches_the_brief(self):
        from eaos import probes
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            assemble(FIXTURE, out)
            probes.run_all(FIXTURE, out)
            dossier = json.loads((out / 'dossier.json').read_text())
            counts = {}
            for claim in dossier['claims']: counts[claim['confidence']] = counts.get(claim['confidence'], 0) + 1
            self.assertEqual(dossier['claim_counts'], counts)

    def test_refreshing_without_a_dossier_fails_clearly(self):
        from eaos.dossier import refresh_views
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'No dossier to refresh'):
                refresh_views(Path(tmp))

    def test_the_index_stops_claiming_no_semantic_review_once_one_ran(self):
        from eaos import claims as ledger
        from eaos.dossier import refresh_views
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            assemble(FIXTURE, out)
            self.assertIn('semantic review: not performed', (out / 'README.md').read_text())
            dossier = json.loads((out / 'dossier.json').read_text())
            dossier['claims'].append(ledger.make(
                900, 'The pricing module owns the discount rule', 'responsibility', 'HYPOTHESIS',
                ['model_inference'], [], 'A second module applying it without importing',
                fact_ids=dossier['claims'][0]['fact_ids'], origin='source'))
            (out / 'dossier.json').write_text(json.dumps(dossier, ensure_ascii=False))
            refresh_views(out)
            text = (out / 'README.md').read_text()
            self.assertNotIn('semantic review: not performed', text)
            self.assertIn('model inference over facts', text)
            updated = json.loads((out / 'dossier.json').read_text())
            self.assertFalse(any(question['question'].startswith('No semantic review was run')
                                 for question in updated['questions']),
                             'a question answered by a later pass must not stay open')


class LayeringTests(unittest.TestCase):
    """The refresh layer must sit above what it rebuilds, or nothing can be changed alone."""

    def test_the_ledger_does_not_depend_on_the_plan_or_the_report(self):
        import ast
        root = Path(__file__).resolve().parents[1] / 'eaos'
        tree = ast.parse((root / 'dossier.py').read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.lstrip('.'))
        self.assertFalse(imported & {'plan', 'product_review', 'site', 'views'},
                         f'dossier must not import the layers that render from it: {imported}')

    def test_refreshing_through_the_top_layer_rebuilds_everything_downstream(self):
        from eaos.plan import build
        from eaos.views import refresh
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            assemble(FIXTURE, out)
            build(FIXTURE, out)
            summary = refresh(out)
            self.assertIn('PLAN/', summary['refreshed'])
            self.assertGreater(summary['tasks'], 0)

    def test_the_package_has_no_import_cycle(self):
        """A cycle means two modules can no longer be changed, tested or replaced alone."""
        import tempfile as tf
        from eaos.facts.run import collect
        from eaos.facts.store import read_set
        root = Path(__file__).resolve().parents[1]
        with tf.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            collect(root, out, ['syntax', 'resolve', 'entrypoints', 'config', 'metrics', 'domain', 'graph'],
                    exclude=['tests/fixtures'])
            cycles = [fact['value']['members'] for fact in read_set(out, 'graph')['facts']
                      if fact['kind'] == 'graph_cycle']
            self.assertEqual(cycles, [], 'the package must stay acyclic')

    def test_the_description_stops_denying_a_semantic_pass_that_ran(self):
        from eaos import claims as ledger
        from eaos.dossier import refresh_views
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            assemble(FIXTURE, out)
            dossier = json.loads((out / 'dossier.json').read_text())
            self.assertIn('not assessed in a facts-only run', dossier['description'])
            dossier['claims'].append(ledger.make(
                903, 'The pricing module owns the discount rule', 'responsibility', 'HYPOTHESIS',
                ['model_inference'], [], 'A second module applying it without importing',
                fact_ids=dossier['claims'][0]['fact_ids'], origin='source'))
            (out / 'dossier.json').write_text(json.dumps(dossier, ensure_ascii=False))
            refresh_views(out)
            updated = json.loads((out / 'dossier.json').read_text())
            self.assertNotIn('not assessed in a facts-only run', updated['description'])
            self.assertIn('model inference', updated['description'])
