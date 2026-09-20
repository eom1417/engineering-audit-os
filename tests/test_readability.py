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
