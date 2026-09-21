"""Tests for invariants the code asserts in prose and nothing else was checking.

docs/invariants.json maps every asserting sentence in the package to the test that fails when it
is broken. These are the ones written because no such test existed: a sentence with no test is an
intention, and this product exists to tell the two apart.
"""
import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DeclaredInvariantTests(unittest.TestCase):

    def test_a_claim_about_test_code_is_marked_as_such(self):
        """eaos/dossier.py:origin_of — a reader must not confuse product code with test code."""
        from eaos.dossier import origin_of
        index = {'F1': 'tests/test_thing.py', 'F2': 'eaos/claims.py'}
        self.assertEqual(origin_of({'fact_ids': ['F1']}, index), 'test')
        self.assertEqual(origin_of({'fact_ids': ['F2']}, index), 'source')
        self.assertEqual(origin_of({'fact_ids': []}, index), 'unknown')
        mixed = origin_of({'fact_ids': ['F1', 'F2']}, index)
        self.assertNotEqual(mixed, 'source', 'a claim spanning both must not read as pure product code')

    def test_running_a_missing_binary_returns_a_code_rather_than_raising(self):
        """eaos/engines/process.py:run — never raises on a bad exit."""
        from eaos.engines.process import run
        code, out, error, seconds = run(['/nonexistent/binary/eaos-test'])
        self.assertNotEqual(code, 0)
        self.assertTrue(error)
        self.assertGreaterEqual(seconds, 0)
        code, out, _, _ = run([sys.executable, '-c', 'import sys; sys.exit(3)'])
        self.assertEqual(code, 3)

    def test_the_executive_page_cites_only_measured_numbers(self):
        """eaos/executive.py — the page never invents metrics."""
        from eaos import executive
        source = (ROOT / 'eaos/executive.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        literals = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.JoinedStr):
                for part in node.values:
                    if isinstance(part, ast.Constant) and isinstance(part.value, str):
                        literals.update(token for token in part.value.split()
                                        if token.replace('.', '').replace('%', '').isdigit())
        self.assertEqual(sorted(literals), [], 'a number hard-coded into the page is not measured')
        with tempfile.TemporaryDirectory() as out:
            self.assertIsNone(executive.render(out, language='en'),
                              'with no facts there is nothing to summarise, and nothing must be invented')
            self.assertFalse((Path(out) / 'EXECUTIVE.md').exists())

    def test_a_framework_detector_is_self_contained(self):
        """eaos/facts/frameworks — adding one means adding one module, never touching the core."""
        core = ROOT / 'eaos/facts/entrypoints.py'
        text = core.read_text(encoding='utf-8')
        for module in sorted((ROOT / 'eaos/facts/frameworks').glob('*.py')):
            if module.stem == '__init__':
                continue
            self.assertNotIn(module.stem, text,
                             f'{core.name} names the detector {module.stem}; detectors must register themselves')
        registry = (ROOT / 'eaos/facts/frameworks/__init__.py').read_text(encoding='utf-8')
        self.assertIn('MODULES', registry, 'detectors register through one list in the package')

    def test_history_of_a_subdirectory_is_scoped_to_it(self):
        """eaos/facts/history.py:prefix_of — history must be scoped to the analysed subtree."""
        from eaos.facts.history import prefix_of
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'sub').mkdir()
            (root / 'sub/a.py').write_text('x = 1\n', encoding='utf-8')
            for command in (['git', 'init', '-q'], ['git', 'add', '-A'],
                            ['git', '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-qm', 'one']):
                subprocess.run(command, cwd=root, capture_output=True)
            self.assertEqual(prefix_of(root / 'sub'), 'sub/')
            self.assertEqual(prefix_of(root), '')

    def test_two_arms_of_one_branch_are_not_a_repetition(self):
        """eaos/facts/redundancy.py:_exclusive_branches — arms that never both execute."""
        from eaos.facts.redundancy import run
        from eaos.facts.source import Source
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'm.py').write_text(
                'def pick(flag):\n'
                '    if flag:\n'
                '        value = compute(1)\n'
                '    else:\n'
                '        value = compute(1)\n'
                '    return value\n'
                'def compute(x):\n'
                '    return x\n', encoding='utf-8')
            facts = run(root, Source(root))['facts']
        repeated = [f for f in facts if f['value']['kind'] == 'repeated_call']
        self.assertEqual(repeated, [], 'the two arms of one branch never both run')

    def test_unparsed_yaml_is_declared_not_guessed(self):
        """eaos/facts/runtime.py:yaml_load — the parser raises rather than guessing."""
        from eaos.facts.runtime import UnsupportedYaml, yaml_load
        self.assertEqual(yaml_load('a: 1\n'), {'a': 1})
        self.assertEqual(yaml_load('services:\n  web:\n    image: x\n'), {'services': {'web': {'image': 'x'}}})
        for unreadable in ('a: [unclosed\n  - ?? : {\n', 'a: 1\n\t b: 2\n', 'a: 1\n*alias\n', 'a: |\n  block\n'):
            with self.assertRaises(UnsupportedYaml, msg=unreadable):
                yaml_load(unreadable)

    def test_the_stage_declaration_imports_nothing_but_the_standard_library(self):
        """eaos/pipeline/run.py:_runners — the declaration is readable without the whole product."""
        tree = ast.parse((ROOT / 'eaos/pipeline/stages.py').read_text(encoding='utf-8'))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported.add(('.' * (node.level or 0)) + (node.module or ''))
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        relative = sorted(name for name in imported if name.startswith('.'))
        self.assertEqual(relative, [], 'the stage declaration must not import the package it describes')

    def test_a_stage_acceptance_command_comes_from_the_project(self):
        """eaos/transform_plan.py:_stage_acceptance — we never invent arbitrary test commands."""
        from eaos.transform_plan import _stage_acceptance
        self.assertIsNone(_stage_acceptance('canonicalize', []))
        acceptance = _stage_acceptance('canonicalize', [{'path': 'a.py', 'line': 1, 'symbol': 's'}])
        self.assertIn('kind', acceptance)
        text = json.dumps(acceptance, ensure_ascii=False)
        for invented in ('pytest', 'npm test', 'make test', 'go test'):
            self.assertNotIn(invented, text, 'a command the project never declared was invented')


class RegisterTests(unittest.TestCase):
    """The register itself must stay honest: current, complete, and pointing at real tests."""

    def test_every_asserting_sentence_is_classified_and_enforced(self):
        from tools.invariants import check, extract, load_register, merge
        register = merge(extract(), load_register())
        self.assertEqual(check(register), [])

    def test_the_register_is_not_stale(self):
        from tools.invariants import extract, load_register
        recorded = {row['id'] for row in load_register()['invariants']}
        current = {row['id'] for row in extract()}
        self.assertEqual(sorted(current - recorded), [],
                         'new invariants were written without registering them; run tools/invariants.py --list')

    def test_a_rationale_exemption_has_to_argue_for_itself(self):
        from tools.invariants import load_register
        for row in load_register()['invariants']:
            if row.get('kind') == 'rationale':
                self.assertTrue((row.get('note') or '').strip(), row['id'])
