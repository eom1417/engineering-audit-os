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

    def _writers(self, kind=contract.DOCUMENT, source=Path('eaos')):
        """Compare report-relative paths, including local directory aliases, rather than basenames."""
        writers = {}

        def relative_path(node, aliases, seen=frozenset()):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                return node.value
            if isinstance(node, ast.Name):
                if node.id in aliases and node.id not in seen:
                    return relative_path(aliases[node.id], aliases, seen | {node.id})
                return ''  # The report root is supplied by the caller.
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                left = relative_path(node.left, aliases, seen)
                right = relative_path(node.right, aliases, seen)
                return '/'.join(part.strip('/') for part in (left, right) if part)
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == 'Path' and node.args:
                    return relative_path(node.args[0], aliases, seen)
                # The node API owns this directory, never the report root (core.folder_of).
                if (isinstance(node.func, ast.Attribute) and node.func.attr == 'folder_of'
                        and isinstance(node.func.value, ast.Name) and node.func.value.id == 'core'):
                    return 'nodes/<node>'
            return '<dynamic>'

        def scan(scope, inherited):
            aliases = dict(inherited)
            nodes = []
            def visit(node):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    return
                nodes.append(node)
                for child in ast.iter_child_nodes(node):
                    visit(child)
            for statement in scope.body:
                visit(statement)
            for node in sorted(nodes, key=lambda item: getattr(item, 'lineno', 0)):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            aliases[target.id] = node.value
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == 'write_text'):
                    # Keep the contract's explicit artifact-name write sites; resolve their directory.
                    if not any(isinstance(part, ast.Constant) and isinstance(part.value, str)
                               and part.value in contract.BY_NAME for part in ast.walk(node.func.value)):
                        continue
                    name = relative_path(node.func.value, aliases)
                    if name in contract.BY_NAME and contract.BY_NAME[name].kind == kind:
                        writers.setdefault(name, set()).add(path.as_posix())
            for statement in scope.body:
                if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    local = dict(aliases)
                    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        for arg in (*statement.args.posonlyargs, *statement.args.args, *statement.args.kwonlyargs):
                            local.pop(arg.arg, None)
                    scan(statement, local)

        for path in sorted(source.rglob('*.py')):
            scan(ast.parse(path.read_text(encoding='utf-8')), {})
        return writers

    def test_nested_plans_do_not_become_root_writers(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            for name, code in {
                'root': "(report / 'plan.json').write_text('root')",
                'behavior': "folder = report / 'behavior-lock'\n(folder / 'plan.json').write_text('nested')",
                'ideal': "folder = Path(report) / 'ideal'\nalias = folder\n(alias / 'plan.json').write_text('nested')",
                'node': "folder = core.folder_of(report, record['node'])\n(folder / 'plan.json').write_text('nested')",
                'direct': "(report / 'nodes' / 'planner' / 'plan.json').write_text('nested')",
                'joined': "(report / 'ideal/plan.json').write_text('nested')",
            }.items():
                (source / (name + '.py')).write_text(code, encoding='utf-8')
            self.assertEqual(self._writers(contract.RECORD, source),
                             {'plan.json': {(source / 'root.py').as_posix()},
                              'behavior-lock/plan.json': {(source / 'behavior.py').as_posix()},
                              'ideal/plan.json': {(source / 'ideal.py').as_posix(), (source / 'joined.py').as_posix()}})

    def test_duplicate_root_writers_remain_visible_without_permission(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / 'first.py').write_text("(report / 'plan.json').write_text('one')", encoding='utf-8')
            (source / 'second.py').write_text(
                "def write(report):\n    root = Path(report)\n    (root / 'plan.json').write_text('two')\n"
                "    root = report / 'ideal'\n    (root / 'plan.json').write_text('nested')", encoding='utf-8')
            writers = self._writers(contract.RECORD, source)
            self.assertEqual(writers['plan.json'],
                             {(source / 'first.py').as_posix(), (source / 'second.py').as_posix()})
            self.assertFalse(contract.BY_NAME['plan.json'].mutated_by)

    def test_no_document_is_named_for_writing_by_two_unrelated_modules(self):
        offenders = {name: sorted(paths) for name, paths in self._writers().items() if len(paths) > 1}
        self.assertEqual(offenders, {}, 'each of these documents is written from more than one module')

    def test_a_record_with_several_writers_declares_who_may_mutate_it(self):
        for name, paths in self._writers(contract.RECORD).items():
            if len(paths) <= 1:
                continue
            artifact = contract.BY_NAME[name]
            self.assertTrue(artifact.mutated_by,
                            f'{name} is written from {sorted(paths)} without declaring mutated_by')


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


class RecordTwinTests(unittest.TestCase):
    """R14: a document a model cannot act on is a dead end, and silence is not an answer."""

    def test_every_declared_document_has_a_record_twin_or_says_why_not(self):
        from eaos.compose.rules import documents_without_a_record_twin
        self.assertEqual(documents_without_a_record_twin(), [])

    def test_a_document_declared_without_either_is_caught(self):
        # The mutation the rule exists to catch: a new document added with neither field set.
        from eaos.compose import rules
        from eaos.compose.artifacts import Artifact, DOCUMENT
        silent = Artifact('NEW-THING.md', 'compose', DOCUMENT, 'a document nobody can act on', 99, 120)
        original = dict(rules.BY_NAME)
        try:
            rules.BY_NAME['NEW-THING.md'] = silent
            problems = rules.documents_without_a_record_twin()
        finally:
            rules.BY_NAME.clear(); rules.BY_NAME.update(original)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn('R14 NEW-THING.md', problems[0])
        # And the rule is satisfied by either field, not only by a record.
        for field in ({'record': 'thing.json'}, {'record_absent_because': 'it renders facts/ directly'}):
            with self.subTest(field=sorted(field)[0]):
                try:
                    rules.BY_NAME['NEW-THING.md'] = Artifact(
                        'NEW-THING.md', 'compose', DOCUMENT, 'a document nobody can act on', 99, 120, **field)
                    self.assertEqual(rules.documents_without_a_record_twin(), [])
                finally:
                    rules.BY_NAME.clear(); rules.BY_NAME.update(original)

    def test_a_named_record_twin_is_itself_a_declared_artifact(self):
        # Pointing at a file nobody writes would satisfy the letter of R14 and none of its point.
        from eaos.compose.artifacts import ARTIFACTS, BY_NAME, DOCUMENT
        for artifact in ARTIFACTS:
            if artifact.kind != DOCUMENT or not artifact.record:
                continue
            with self.subTest(document=artifact.name):
                self.assertIn(artifact.record, BY_NAME,
                              f'{artifact.name} names {artifact.record}, which no stage declares')
