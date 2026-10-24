"""The details that broke real checks this week, held once for all (the owner, 2026-10-22: "it must never miss these
stupid details"): a stop code with no words for the person, a command the Studio copies with flags `eaos` does not
have, a node missing from the list the AI may run, a stage with no title, a threshold on the wrong scale."""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Consistency(unittest.TestCase):
    def test_every_stop_code_has_words_and_every_copied_command_and_node_exists(self):
        from eaos.pipeline.stages import ORDER
        from eaos.ai.nodes import NODES
        reasons = json.loads((ROOT / 'eaos/data/errors.json').read_text())['reasons']
        codes = {m for p in (ROOT / 'eaos').rglob('*.py') for m in re.findall(r"SkipStage\([^)]*?code=['\"]([a-z_]+)['\"]", p.read_text(), re.S)}
        self.assertEqual(sorted(c for c in codes if not (reasons.get(c) or {}).get('ar')), [], 'a stop code the person cannot read')
        console = ''.join(p.read_text() for p in (ROOT / 'console/src').rglob('*.js'))
        for command, flags in set(re.findall(r'eaos (check|start|fix)((?: --[a-z-]+(?: \$\{[^}]+\}| [a-z]+)?)+)', console)):
            known = subprocess.run([sys.executable, '-m', 'eaos', command, '--help'], capture_output=True, text=True).stdout
            for flag in re.findall(r'--[a-z-]+', flags): self.assertIn(flag, known, f'the Studio copies eaos {command} {flag}')
        stages = json.loads((ROOT / 'eaos/data/words.json').read_text())['stages']
        self.assertEqual([s for s in ORDER if s not in stages], [], 'a stage with no words')
        self.assertEqual([s for s in stages if s not in ORDER], [], 'words of a stage that is gone')
        contract = json.loads((ROOT / 'docs/studio-actions.json').read_text())
        enum = next(a for a in contract['actions'] if a['id'] == 'run_nodes')['inputs']['properties']['nodes']['items']['enum']
        self.assertEqual(set(enum), {n.name for n in NODES}, 'a node the AI cannot run')
        self.assertNotRegex((ROOT / 'eaos/journeys/build_look.py').read_text(), r'scores\[name\] < 0\.\d', 'Lighthouse scores are out of 100')


    def test_a_projects_state_is_read_and_written_only_through_its_one_module(self):
        """M3.2: the CLI, MCP, the Studio and the sandbox each read state.json their own way; one module holds it now."""
        readers = sorted(str(p.relative_to(ROOT)) for p in (ROOT / 'eaos').rglob('*.py')
                         if re.search(r"""['"]state\.json['"]""", p.read_text()) and p.name != 'project_state.py')
        self.assertEqual(readers, [], 'state.json named outside eaos/core/project_state.py')


if __name__ == '__main__':
    unittest.main()
