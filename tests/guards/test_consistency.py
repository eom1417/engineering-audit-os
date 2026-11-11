"""The details that break checks, held once for all: a stop code with no words for the person, a command an action
copies with flags `eaos` does not have, a node missing from the list the AI may run, a stage with no title, a
threshold on the wrong scale."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class Consistency(unittest.TestCase):
    def test_every_stop_code_has_words_and_every_copied_command_and_node_exists(self):
        from eaos.features.check.journey.stages import ORDER
        from eaos.features.ai_review.analysis import NODES
        reasons = json.loads((ROOT / 'eaos/data/errors.json').read_text())['reasons']
        codes = {m for p in (ROOT / 'eaos').rglob('*.py')
                 for m in re.findall(r"SkipStage\([^)]*?code=['\"]([a-z_]+)['\"]", p.read_text(), re.S)}
        self.assertEqual(sorted(c for c in codes if not (reasons.get(c) or {}).get('ar')), [],
                         'a stop code the person cannot read')
        stages = json.loads((ROOT / 'eaos/data/words.json').read_text())['stages']
        self.assertEqual([s for s in ORDER if s not in stages], [], 'a stage with no words')
        self.assertEqual([s for s in stages if s not in ORDER], [], 'words of a stage that is gone')
        contract = json.loads((ROOT / 'docs/studio-actions.json').read_text())
        enum = next(a for a in contract['actions']
                    if a['id'] == 'run_nodes')['inputs']['properties']['nodes']['items']['enum']
        self.assertEqual(set(enum), {n.name for n in NODES}, 'a node the AI cannot run')

    def test_a_projects_state_is_read_and_written_only_through_its_one_module(self):
        """The CLI, MCP and the sandbox read state.json through its one module."""
        readers = sorted(str(p.relative_to(ROOT)) for p in (ROOT / 'eaos').rglob('*.py')
                         if re.search(r"""['"]state\.json['"]""",
                                      p.read_text()) and p != ROOT / 'eaos/kernel/project/state.py')
        self.assertEqual(readers, [], 'state.json named outside eaos/kernel/project/state.py')


if __name__ == '__main__':
    unittest.main()
