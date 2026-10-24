"""The dossier as one readable unit: an index, cross-links, one language, grounded answers and fresh views."""
import ast
import json
from pathlib import Path
import tempfile
import unittest
from shared_fixture import TemporaryWorkspace
from eaos.analysis import claims as ledger
from eaos.analysis import probes
from eaos.ai.ask import answer
from eaos.core.words import statement_of
from eaos.core.document_rules import validate
from eaos.analysis.dossier import assemble, refresh_views
from eaos.facts.run import collect
from eaos.facts.store import read_set
from eaos.analysis.plan import build
from eaos.report.views import refresh

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'


class DossierTests(TemporaryWorkspace):
    @classmethod
    def setUpClass(cls):
        cls.out = Path(cls.workspace().name) / 'out'
        assemble(FIXTURE, cls.out)

    def test_the_dossier_opens_with_an_index_in_reading_order(self):
        text = (self.out / 'README.md').read_text()
        for document in ['START-HERE.md', 'CURRENT-STATE.md', 'EXECUTION-PLAN.md', 'TARGET-ARCHITECTURE.md', 'RUN.md']:
            self.assertIn(f']({document})', text)
        dossier = json.loads((self.out / 'dossier.json').read_text())
        self.assertEqual([p for p in validate(self.out, dossier) if p.startswith('R12')], [])
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(any(problem.startswith('R12') for problem in validate(Path(tmp), dossier)))

    def test_the_dossier_speaks_the_readers_language(self):
        claim = {'statement': 'Import cycle between: a.py, b.py', 'render': {'key': 'cycle', 'params': {'members': 'a.py, b.py'}}}
        self.assertEqual(statement_of(claim, 'ar'), 'دورة استيراد بين: a.py, b.py')
        self.assertEqual(statement_of(claim, 'en'), 'Import cycle between: a.py, b.py')
        plain = {'statement': 'something specific', 'render': {}}
        self.assertEqual(statement_of(plain, 'ar'), 'something specific')
        text = (self.out / 'README.md').read_text()
        self.assertIn('اقرأ بهذا الترتيب', text)
        self.assertNotIn('Read in this order', text)

    def test_a_question_gets_a_grounded_answer_or_says_why_not(self):
        self.assertEqual(answer(self.out, 'what handles POST /orders')['answers'][0]['kind'], 'entry point')
        self.assertTrue(answer(self.out, 'orders')['next_questions'])
        unanswerable = answer(self.out, 'zzzqxv nonexistent subsystem')
        self.assertEqual(unanswerable['next_questions'], [])
        self.assertIn('No record answers', unanswerable['note'])
        # Every record kind survives being indexed, whatever shape its value has.
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

    def test_the_views_follow_the_plan_and_the_probes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            assemble(FIXTURE, out)
            self.assertIn('tasks 0', (out / 'README.md').read_text())
            probes.run_all(FIXTURE, out)
            dossier = json.loads((out / 'dossier.json').read_text())
            counts = {}
            for claim in dossier['claims']: counts[claim['confidence']] = counts.get(claim['confidence'], 0) + 1
            self.assertEqual(dossier['claim_counts'], counts)
            build(FIXTURE, out)
            text = (out / 'README.md').read_text()
            self.assertNotIn('tasks 0', text)
            self.assertIn('waves', text)
            summary = refresh(out)
            self.assertIn('PLAN/', summary['refreshed'])
            self.assertGreater(summary['tasks'], 0)
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, 'No dossier to refresh'):
            refresh_views(Path(tmp))

    def test_the_index_and_description_stop_denying_a_semantic_pass_that_ran(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            assemble(FIXTURE, out)
            self.assertIn('semantic review: not performed', (out / 'README.md').read_text())
            dossier = json.loads((out / 'dossier.json').read_text())
            self.assertIn('not assessed in a facts-only run', dossier['description'])
            dossier['claims'].append(ledger.make(
                900, 'The pricing module owns the discount rule', 'responsibility', 'HYPOTHESIS',
                ['model_inference'], [], 'A second module applying it without importing',
                fact_ids=dossier['claims'][0]['fact_ids'], origin='source'))
            (out / 'dossier.json').write_text(json.dumps(dossier, ensure_ascii=False))
            refresh_views(out)
            text = (out / 'README.md').read_text()
            updated = json.loads((out / 'dossier.json').read_text())
        self.assertNotIn('semantic review: not performed', text)
        self.assertIn('(1 من طبقة دلالية)', text)
        self.assertNotIn('not assessed in a facts-only run', updated['description'])
        self.assertIn('model inference', updated['description'])
        self.assertFalse(any(q['question'].startswith('No semantic review was run') for q in updated['questions']),
                         'a question answered by a later pass must not stay open')


class LayeringTests(unittest.TestCase):
    """The ledger sits below what renders from it, and the package stays acyclic."""

    def test_the_ledger_is_below_its_views_and_the_package_has_no_import_cycle(self):
        root = Path(__file__).resolve().parents[1]
        tree = ast.parse((root / 'eaos/analysis/dossier.py').read_text())
        imported = {node.module.lstrip('.') for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
        self.assertFalse(imported & {'plan', 'views'}, f'dossier must not import the layers that render from it: {imported}')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            collect(root, out, ['syntax', 'resolve', 'entrypoints', 'config', 'metrics', 'domain', 'graph'],
                    exclude=['tests/fixtures'])
            cycles = [fact['value']['members'] for fact in read_set(out, 'graph')['facts'] if fact['kind'] == 'graph_cycle']
        self.assertEqual(cycles, [], 'the package must stay acyclic')
