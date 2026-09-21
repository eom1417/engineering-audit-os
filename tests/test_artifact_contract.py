"""Every artifact has one owner, one purpose and one budget — and the contract checks all of them.

Sixteen of thirty documents were once outside the output contract, unbudgeted and unchecked, and
four were written twice: the second writer replaced 574 lines of measured content with empty
headings and nothing failed. These tests exist so that cannot happen quietly again.
"""
import ast
import json
import tempfile
import unittest
from pathlib import Path

from eaos.compose import artifacts as contract
from eaos.compose.rules import BUDGETS, validate
from eaos.pipeline import BY_NAME as STAGE_BY_NAME, STAGES


class DeclarationTests(unittest.TestCase):
    def test_the_declaration_has_no_structural_problems(self):
        self.assertEqual(contract.errors(), [])

    def test_every_artifact_names_a_stage_that_exists(self):
        for artifact in contract.ARTIFACTS:
            self.assertIn(artifact.owner, STAGE_BY_NAME, artifact.name)

    def test_every_stage_product_is_declared(self):
        for stage in STAGES:
            for product in stage.produces:
                if product.startswith(('facts/', 'PLAN/', 'bundles/')):
                    continue
                self.assertIn(product, contract.BY_NAME, f'{stage.name} produces undeclared {product}')

    def test_the_declared_owner_matches_the_stage_that_produces_it(self):
        produced_by = {product: stage.name for stage in STAGES for product in stage.produces}
        for name, stage_name in produced_by.items():
            artifact = contract.BY_NAME.get(name)
            if artifact is None:
                continue
            self.assertEqual(artifact.owner, stage_name, name)

    def test_budgets_come_from_the_contract_and_nowhere_else(self):
        self.assertEqual(BUDGETS, contract.BUDGETS)

    def test_every_document_states_why_a_reader_would_open_it(self):
        for artifact in contract.DOCUMENTS:
            self.assertTrue(artifact.purpose.strip(), artifact.name)
            self.assertGreater(artifact.budget_lines, 0, artifact.name)

    def test_the_reading_order_is_stable_and_total(self):
        order = contract.reading_order()
        self.assertEqual(len(order), len(contract.DOCUMENTS))
        self.assertEqual(order, contract.reading_order())


class RuleThirteenTests(unittest.TestCase):
    def _report(self, directory, extra=None):
        out = Path(directory)
        (out / 'README.md').write_text('# index\n\n[brief](DECISION-BRIEF.md)\n', encoding='utf-8')
        (out / 'run-manifest.json').write_text(json.dumps(
            {'stages': {stage.name: {'status': 'ok'} for stage in STAGES}}), encoding='utf-8')
        for name, text in (extra or {}).items():
            (out / name).write_text(text, encoding='utf-8')
        return out

    def test_a_document_nobody_declared_is_a_violation(self):
        with tempfile.TemporaryDirectory() as directory:
            out = self._report(directory, {'SURPRISE.md': '# surprise\n'})
            problems = validate(out, {'claims': []})
        self.assertTrue(any(p.startswith('R13 SURPRISE.md') for p in problems), problems)

    def test_a_required_artifact_absent_with_no_reason_is_a_violation(self):
        with tempfile.TemporaryDirectory() as directory:
            out = self._report(directory)
            problems = validate(out, {'claims': []})
        self.assertTrue(any('R13 SYSTEM-MAP.md' in p for p in problems), problems)

    def test_a_stage_that_did_not_run_explains_its_missing_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / 'README.md').write_text('# index\n\n[brief](DECISION-BRIEF.md)\n', encoding='utf-8')
            (out / 'run-manifest.json').write_text(json.dumps(
                {'stages': {stage.name: {'status': 'unavailable'} for stage in STAGES}}), encoding='utf-8')
            problems = validate(out, {'claims': []})
        self.assertFalse([p for p in problems if p.startswith('R13')], problems)

    def test_an_artifact_written_after_the_check_is_not_demanded_by_it(self):
        self.assertFalse(contract.BY_NAME['run-manifest.json'].checked)
        self.assertFalse(contract.BY_NAME['product-review.json'].checked)


class SingleWriterTests(unittest.TestCase):
    """One artifact, one module. Two writers is how the system map was silently emptied."""

    def _writers(self):
        """Modules that actually call write_text on a path naming a declared document."""
        writers = {}
        for path in sorted(Path('eaos').rglob('*.py')):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == 'write_text'):
                    continue
                for inner in ast.walk(node.func.value):
                    if (isinstance(inner, ast.Constant) and isinstance(inner.value, str)
                            and inner.value in contract.BY_NAME
                            and contract.BY_NAME[inner.value].kind == contract.DOCUMENT):
                        writers.setdefault(inner.value, set()).add(path.as_posix())
        return writers

    def test_no_document_is_named_for_writing_by_two_unrelated_modules(self):
        offenders = {name: sorted(paths) for name, paths in self._writers().items() if len(paths) > 1}
        self.assertEqual(offenders, {}, 'each of these documents is written from more than one module')


class PartialRunTests(unittest.TestCase):
    """A single command is not a pipeline run; R13 must not invent missing artifacts for it."""

    def test_without_a_manifest_no_artifact_is_declared_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / 'README.md').write_text('# index\n\n[brief](DECISION-BRIEF.md)\n', encoding='utf-8')
            problems = validate(out, {'claims': []})
        self.assertFalse([p for p in problems if p.startswith('R13')], problems)

    def test_an_undeclared_document_is_still_caught_without_a_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / 'README.md').write_text('# index\n\n[brief](DECISION-BRIEF.md)\n', encoding='utf-8')
            (out / 'STRAY.md').write_text('# stray\n', encoding='utf-8')
            problems = validate(out, {'claims': []})
        self.assertTrue(any(p.startswith('R13 STRAY.md') for p in problems), problems)
