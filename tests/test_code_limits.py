"""EAOS's own code stays within its limits: no new complex function or long module and none of today's grows, logic
written once, no unused import or variable."""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import code_limits  # noqa: E402


class CodeLimits(unittest.TestCase):
    def test_no_function_or_module_grows_past_its_limit(self):
        current, baseline = code_limits.measure(), code_limits.load()
        self.assertEqual(code_limits.breaches(current, baseline), [],
                         'split the function or module; the limits only move down')
        stale = {kind: sorted(set(baseline[kind]) - set(current[kind])) for kind in baseline}
        self.assertEqual(stale, {'functions': [], 'modules': []},
                         'now under the limit: run python tools/code_limits.py --tighten')

    def test_a_listed_function_moved_by_a_split_keeps_its_allowance_and_may_not_grow(self):
        # EAOS, 2026-10-15: its five largest modules could not be split, every moved complex function counted as new
        baseline = {'functions': {'eaos/runs.py::Manager._answer': 41}, 'modules': {}}
        moved = {'functions': {'eaos/runs_answer.py::_answer': 41}, 'modules': {}}
        self.assertEqual(code_limits.breaches(moved, baseline), [])
        grown = {'functions': {'eaos/runs_answer.py::_answer': 42}, 'modules': {}}
        self.assertEqual(code_limits.breaches(grown, baseline), ['eaos/runs_answer.py::_answer: 42 (allowed 41)'])

    def test_logic_is_written_once(self):
        self.assertEqual(code_limits.duplicates(), [], 'keep one copy and call it from the other places')

    def test_no_unused_import_or_variable(self):
        self.assertEqual(code_limits.leftovers(), [])

    def test_a_temporary_folder_is_removed_by_what_made_it(self):
        # A folder from mkdtemp stays for ever unless its maker removes it: 24,000 had piled up (2026-10-17). A
        # TemporaryDirectory removes its own; each of these removes its folders as said.
        owners = {'eaos/sandbox.py': 'the next run sweeps what no live run holds', 'eaos/codemods.py': 'removed in finally',
                  'tests/shared_fixture.py': 'scratch() and Workspace: removed when the run or the test ends'}
        root = Path(__file__).resolve().parents[1]
        code = [path for folder in ('eaos', 'tests', 'tools') for path in (root / folder).rglob('*.py') if 'fixtures' not in path.parts]
        makers = sorted(path.relative_to(root).as_posix() for path in code
                        if any(isinstance(node, ast.Attribute) and node.attr == 'mkdtemp' for node in ast.walk(ast.parse(path.read_bytes()))))
        self.assertEqual(sorted(set(makers) - set(owners)), [], 'use tempfile.TemporaryDirectory, or scratch() in a test')

    def test_every_assistant_works_to_the_code_laws(self):
        from eaos import mcp_server, semantic
        from eaos.code_laws import LAWS
        from eaos.studio import ideal_prompts
        from eaos.studio.nodes import core
        data = {'lang': 'en', 'project': {'language': 'English'}}
        carried = {'semantic reading': semantic.SYSTEM, 'fixing (MCP)': mcp_server.INSTRUCTIONS,
                   'every node': core.prompt('task', data), 'node critique': core.critique_prompt('task', data, {}, 'en'),
                   'ideal plan': ideal_prompts.prompt_plan(data), 'ideal critique': ideal_prompts.prompt_critique(data, {})}
        self.assertEqual([name for name, text in carried.items() if LAWS not in text], [])

    def test_complexity_counts_decisions_and_skips_nested_functions(self):
        source = ('def f(a, b):\n'
                  '    if a and b: return [x for x in a if x]\n'
                  '    def inner():\n        if b: return 1\n'
                  '    return 0 if a else 1\n')
        self.assertEqual(code_limits.complexity(ast.parse(source).body[0]), 6)


if __name__ == '__main__':
    unittest.main()
