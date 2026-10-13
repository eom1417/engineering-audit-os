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

    def test_logic_is_written_once(self):
        self.assertEqual(code_limits.duplicates(), [], 'keep one copy and call it from the other places')

    def test_no_unused_import_or_variable(self):
        self.assertEqual(code_limits.leftovers(), [])

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
