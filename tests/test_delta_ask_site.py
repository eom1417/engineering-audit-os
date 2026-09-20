"""Living-record features: delta as a drift gate, grounded answers, and a rendered site."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from eaos import cli
from eaos.ask import answer
from eaos.delta import run as run_delta
from eaos.dossier import assemble
from eaos.site import build as build_site

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'


def small_repo(root, discount_sites=1):
    repo = Path(root) / 'repo'; repo.mkdir()
    (repo / 'pricing.py').write_text('PREMIUM_DISCOUNT = 0.1\n\n\ndef price(total):\n    return total * (1 - PREMIUM_DISCOUNT)\n')
    if discount_sites > 1:
        (repo / 'checkout.py').write_text('PREMIUM_DISCOUNT = 0.1\n\n\ndef total(x):\n    return x * (1 - PREMIUM_DISCOUNT)\n')
    return repo


class DeltaTests(unittest.TestCase):
    def test_a_new_duplicated_rule_trips_the_drift_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = small_repo(tmp)
            assemble(repo, Path(tmp) / 'before')
            (repo / 'checkout.py').write_text('PREMIUM_DISCOUNT = 0.1\n\n\ndef total(x):\n    return x * (1 - PREMIUM_DISCOUNT)\n')
            assemble(repo, Path(tmp) / 'after')
            result = run_delta(Path(tmp) / 'before', Path(tmp) / 'after', fail_on_new_severe=True)
            self.assertEqual(result['status'], 'DRIFT')
            self.assertEqual(result['counts']['new'], 1)
            self.assertTrue((Path(tmp) / 'after/DELTA.md').is_file())

    def test_an_unchanged_project_reports_no_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = small_repo(tmp)
            assemble(repo, Path(tmp) / 'before')
            assemble(repo, Path(tmp) / 'after')
            result = run_delta(Path(tmp) / 'before', Path(tmp) / 'after', fail_on_new_severe=True)
            self.assertEqual(result['status'], 'OK')
            self.assertEqual(result['counts'], {'new': 0, 'resolved': 0, 'changed': 0, 'new_severe': 0})

    def test_a_resolved_problem_shows_as_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = small_repo(tmp, discount_sites=2)
            assemble(repo, Path(tmp) / 'before')
            (repo / 'checkout.py').write_text('from pricing import PREMIUM_DISCOUNT\n\n\ndef total(x):\n    return x * (1 - PREMIUM_DISCOUNT)\n')
            assemble(repo, Path(tmp) / 'after')
            result = run_delta(Path(tmp) / 'before', Path(tmp) / 'after')
            self.assertEqual(result['counts']['resolved'], 1)
            self.assertEqual(result['counts']['new'], 0)

    def test_cli_exits_nonzero_on_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = small_repo(tmp)
            assemble(repo, Path(tmp) / 'before')
            (repo / 'checkout.py').write_text('PREMIUM_DISCOUNT = 0.1\n')
            assemble(repo, Path(tmp) / 'after')
            with contextlib.redirect_stdout(io.StringIO()):
                code = cli.main(['delta', str(Path(tmp) / 'before'), str(Path(tmp) / 'after'), '--fail-on-new-severe'])
            self.assertEqual(code, 2)


class AskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / 'out'
        assemble(FIXTURE, cls.out)

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def test_a_real_question_is_answered_with_locations(self):
        result = answer(self.out, 'where is the premium discount defined')
        self.assertEqual(result['status'], 'ANSWERED')
        self.assertTrue(any('core/pricing.py' in row['text'] or 'core/pricing.py' in row['citation'] for row in result['answers']))

    def test_route_questions_reach_the_entry_point_records(self):
        result = answer(self.out, 'what handles POST /orders')
        self.assertTrue(any(row['kind'] == 'entry point' for row in result['answers']))

    def test_an_arabic_question_reaches_the_arabic_artifacts(self):
        result = answer(self.out, 'أين قاعدة الخصم المكررة')
        self.assertEqual(result['status'], 'ANSWERED')
        self.assertTrue(any(row['kind'] == 'artifact section' for row in result['answers']))
        self.assertFalse(any(set(row['text'].replace(' · ', '')) <= {'-', ':'} for row in result['answers']))

    def test_an_unanswerable_question_says_so_instead_of_guessing(self):
        result = answer(self.out, 'zzzqxv nonexistent subsystem')
        self.assertEqual(result['status'], 'NOT_IN_RECORDS')
        self.assertEqual(result['answers'], [])
        self.assertIn('No record answers this question', result['note'])

    def test_answers_never_come_from_outside_the_records(self):
        result = answer(self.out, 'pricing')
        for row in result['answers']:
            self.assertIn(row['kind'], {'claim', 'open question', 'entry point', 'flow', 'rule constant',
                                        'symbol', 'configuration', 'data_model', 'data_table', 'artifact section'})


class SiteTests(unittest.TestCase):
    def test_site_renders_every_artifact_into_one_searchable_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            assemble(FIXTURE, out)
            result = build_site(out)
            page = (out / 'index.html').read_text()
            self.assertIn('<nav>', page)
            self.assertIn('DECISION-BRIEF', page)
            self.assertEqual(page.count('<section'), len(result['documents']))
            self.assertNotIn('http://', page.replace('http://www.w3.org', ''))

    def test_site_requires_a_built_dossier(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'No rendered artifacts'):
                build_site(Path(tmp))
