"""The evaluation harness: numbers on planted cases, and a baseline to compare against."""
import json
from pathlib import Path
import tempfile
import unittest
from shared_fixture import TemporaryWorkspace
from eaos.evaluate import baseline, run, score

CORPUS = Path(__file__).resolve().parent / 'fixtures/benchmarks'


class EvaluationTests(TemporaryWorkspace):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.result = run(CORPUS, Path(cls.tmp.name) / 'out')
        cls.details = json.loads((Path(cls.tmp.name) / 'out/eval.json').read_text())


    def test_every_planted_defect_is_detected(self):
        self.assertEqual(self.result['totals']['detected'], self.result['totals']['planted'])
        self.assertEqual(self.result['totals']['recall'], 1.0)

    def test_the_clean_project_produces_no_false_positive(self):
        clean = next(row for row in self.details['cases'] if row['case'] == 'clean-project')
        self.assertEqual(clean['framework']['false_positives'], [])
        self.assertEqual(clean['claims'], 0)

    def test_the_framework_beats_the_grep_baseline(self):
        self.assertGreater(self.result['totals']['detected'], self.result['totals']['baseline_detected'])

    def test_the_untested_path_case_needs_real_execution(self):
        row = next(row for row in self.details['cases'] if row['case'] == 'untested-path')
        self.assertEqual(row['framework']['detected'], 1)
        self.assertGreaterEqual(row['runtime_confirmed'], 1)

    def test_what_was_not_measured_is_stated(self):
        joined = ' '.join(self.details['not_measured'])
        self.assertIn('Live-model', joined)
        self.assertIn('blind human rating', joined)

    def test_scoring_counts_forbidden_claims_as_false_positives(self):
        outcome = score(['X is defined in 2 places'], {'planted': [], 'must_not_claim': ['defined in']})
        self.assertEqual(len(outcome['false_positives']), 1)
        self.assertIsNone(outcome['precision'])
        self.assertEqual(outcome['not_adjudicated'], 1)

    def test_baseline_only_sees_repeated_constants(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'a.py').write_text('RATE = 1\n')
            (repo / 'b.py').write_text('RATE = 2\n')
            (repo / 'c.py').write_text('import a\n')
            found = baseline(repo)
            self.assertEqual(len(found), 1)
            self.assertIn('RATE', found[0])


class EvaluationV2Tests(TemporaryWorkspace):
    """Measurement across every claim class the tool claims to detect, plus the plan it produces."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.result = run(CORPUS, Path(cls.tmp.name) / 'out')
        cls.details = json.loads((Path(cls.tmp.name) / 'out/eval.json').read_text())


    def case(self, name): return next(row for row in self.details['cases'] if row['case'] == name)

    def test_every_new_claim_class_has_a_measured_case(self):
        names = {row['case'] for row in self.details['cases']}
        self.assertLessEqual({'policy-violation', 'hotspot', 'mutable-state', 'external-write', 'api-break'}, names)

    def test_all_planted_defects_are_detected_with_no_false_positive(self):
        self.assertEqual(self.result['totals']['recall'], 1.0)
        self.assertEqual(self.result['totals']['false_positives'], 0)

    def test_the_framework_still_beats_the_grep_baseline_by_a_wide_margin(self):
        self.assertGreaterEqual(self.result['totals']['detected'], 8)
        self.assertLessEqual(self.result['totals']['baseline_detected'], 2)

    def test_a_declared_policy_is_enforced_inside_the_dossier(self):
        row = self.case('policy-violation')
        self.assertEqual(row['framework']['detected'], 1)
        self.assertGreaterEqual(row['plan']['cards'], 1)

    def test_a_breaking_api_change_is_measured_on_two_snapshots(self):
        row = self.case('api-break')
        self.assertEqual(row['mode'], 'api_break')
        self.assertEqual(row['framework']['detected'], 1)

    def test_investigations_are_complete_but_not_counted_as_executable_repairs(self):
        totals = self.result['totals']
        self.assertEqual(totals['complete_cards'], totals['cards'])
        self.assertEqual(totals['runnable_acceptance'], 0)
        self.assertGreater(totals['cards'], 0)

    def test_the_clean_project_still_produces_nothing(self):
        row = self.case('clean-project')
        self.assertEqual(row['claims'], 0)
        self.assertEqual(row['plan']['cards'], 0)

    def test_the_report_states_that_card_usefulness_is_not_measured(self):
        self.assertTrue(any('blind human rating' in note for note in self.details['not_measured']))
