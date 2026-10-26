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

from eaos.core.contracts import artifacts as contract
from eaos.core.contracts.document_rules import BUDGETS, validate
from eaos.pipeline.stages import BY_NAME as STAGE_BY_NAME, STAGES


class DeclarationTests(unittest.TestCase):
    def test_every_artifact_has_one_owner_one_purpose_and_one_budget(self):
        self.assertEqual(contract.errors(), [])
        produced_by = {product: stage.name for stage in STAGES for product in stage.produces}
        for artifact in contract.ARTIFACTS:
            self.assertIn(artifact.owner, STAGE_BY_NAME, artifact.name)
        for product, stage_name in produced_by.items():
            if product.startswith(('facts/', 'PLAN/', 'bundles/')) and product not in contract.BY_NAME:
                continue
            self.assertIn(product, contract.BY_NAME, f'{stage_name} produces undeclared {product}')
            self.assertEqual(contract.BY_NAME[product].owner, stage_name, product)
        self.assertEqual(BUDGETS, contract.BUDGETS)
        for artifact in contract.DOCUMENTS:
            self.assertTrue(artifact.purpose.strip(), artifact.name)
            self.assertGreater(artifact.budget_lines, 0, artifact.name)
        order = contract.reading_order()
        self.assertEqual((len(order), order), (len(contract.DOCUMENTS), contract.reading_order()))


class RuleThirteenTests(unittest.TestCase):
    """R13: no document nobody declared, and no declared artifact missing without a reason."""

    def _report(self, directory, statuses=None, extra=None):
        out = Path(directory)
        (out / 'README.md').write_text('# index\n\n[start](START-HERE.md)\n', encoding='utf-8')
        if statuses:
            (out / 'run-manifest.json').write_text(json.dumps(
                {'stages': {stage.name: {'status': statuses} for stage in STAGES}}), encoding='utf-8')
        for name, text in (extra or {}).items():
            (out / name).write_text(text, encoding='utf-8')
        return validate(out, {'claims': []})

    def test_undeclared_and_unexplained_missing_artifacts_are_violations(self):
        cases = [('ok', {'SURPRISE.md': '# surprise\n'}, 'R13 SURPRISE.md'), (None, {'STRAY.md': '# stray\n'}, 'R13 STRAY.md'),
                 ('ok', None, 'R13 CURRENT-STATE.md')]
        for statuses, extra, expected in cases:
            with self.subTest(expected), tempfile.TemporaryDirectory() as directory:
                self.assertTrue(any(p.startswith(expected) for p in self._report(directory, statuses, extra)))
        # A stage that did not run explains its missing artifact; a single command is not a pipeline run.
        for statuses in ('unavailable', None):
            with self.subTest(statuses=statuses), tempfile.TemporaryDirectory() as directory:
                self.assertFalse([p for p in self._report(directory, statuses) if p.startswith('R13')])
        self.assertFalse(contract.BY_NAME['run-manifest.json'].checked)


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

    def test_the_writer_scan_resolves_directories_and_keeps_duplicates_visible(self):
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

    def test_one_document_one_writer_and_a_shared_record_declares_who_may_mutate_it(self):
        offenders = {name: sorted(paths) for name, paths in self._writers().items() if len(paths) > 1}
        self.assertEqual(offenders, {}, 'each of these documents is written from more than one module')
        for name, paths in self._writers(contract.RECORD).items():
            if len(paths) <= 1:
                continue
            artifact = contract.BY_NAME[name]
            self.assertTrue(artifact.mutated_by,
                            f'{name} is written from {sorted(paths)} without declaring mutated_by')


class RecordTwinTests(unittest.TestCase):
    """R14: a document a model cannot act on is a dead end, and silence is not an answer."""

    def test_every_declared_document_has_a_record_twin_or_says_why_not(self):
        from eaos.core.contracts.document_rules import documents_without_a_record_twin
        self.assertEqual(documents_without_a_record_twin(), [])
        # The mutation the rule exists to catch: a new document added with neither field set.
        from eaos.core.contracts import document_rules as rules
        from eaos.core.contracts.artifacts import Artifact, DOCUMENT
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
        from eaos.core.contracts.artifacts import ARTIFACTS, BY_NAME, DOCUMENT
        for artifact in ARTIFACTS:
            if artifact.kind != DOCUMENT or not artifact.record:
                continue
            with self.subTest(document=artifact.name):
                self.assertIn(artifact.record, BY_NAME,
                              f'{artifact.name} names {artifact.record}, which no stage declares')
