"""The extension guide stays true (M18.2): docs/EXTENDING.md names only files that exist, every engine has what its
recipe asks for, every stage its words, and every Studio action its MCP twin or the reason it has none."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUIDE = ROOT / 'docs' / 'EXTENDING.md'
# A path in backquotes: a folder or a file of a known kind; a placeholder (<name>) or an absolute path is not one.
PATH = re.compile(r'`([\w.-]+(?:/[\w.-]+)*(?:/|\.(?:py|json|md|cjs|mjs|js|yml|sh|toml)))`')


class Extending(unittest.TestCase):
    def test_every_path_the_guide_names_exists(self):
        named = {match for match in PATH.findall(GUIDE.read_text(encoding='utf-8')) if not match.startswith('/')}
        full = {path for path in named if '/' in path.rstrip('/') or (ROOT / path).exists()}
        self.assertGreater(len(full), 40, 'the guide names its files by path')
        self.assertEqual(sorted(path for path in full if not (ROOT / path).exists()), [], 'a path that is gone')
        # a name repeated alone (`loops.py`) was named in full before
        self.assertEqual(sorted(name for name in named - full if not any(path.rstrip('/').endswith('/' + name.rstrip('/')) for path in full)), [])

    def test_every_engine_has_what_its_recipe_asks_for(self):
        from eaos.engines import ADAPTERS
        from tests.engines.test_engine_contracts import UNSAMPLED
        notices = (ROOT / 'THIRD_PARTY_NOTICES.md').read_text(encoding='utf-8')
        for name, adapter in ADAPTERS.items():
            with self.subTest(engine=name):
                self.assertTrue(Path(adapter.__file__).is_relative_to(ROOT / 'eaos' / 'engines'), 'an adapter in eaos/engines/')
                self.assertTrue(name in UNSAMPLED or (ROOT / 'tests' / 'contracts' / f'{name}.json').is_file(), 'a pinned sample')
                self.assertIn(f'| `{name}`', notices, 'a row in THIRD_PARTY_NOTICES.md')

    def test_every_licence_kept_names_a_pinned_tool_or_a_noticed_work(self):
        from eaos.core.toolchain import registry
        names = {tool['name'] for tool in registry()['tools']}
        notices = (ROOT / 'THIRD_PARTY_NOTICES.md').read_text(encoding='utf-8')
        for kept in sorted((ROOT / 'upstreams' / 'licenses').iterdir()):
            work = re.sub(r'-(LICENSE|NOTICE)$', '', kept.name)
            with self.subTest(licence=kept.name):
                self.assertTrue(work in names or f'[{work}]' in notices, 'a licence of a tool no longer pinned')

    def test_every_stage_has_its_words(self):
        from eaos.pipeline.stages import STAGES
        words = json.loads((ROOT / 'eaos' / 'data' / 'words.json').read_text(encoding='utf-8'))['stages']
        for stage in STAGES:
            with self.subTest(stage=stage.name):
                forms = words.get(stage.name) or {}
                self.assertEqual(sorted(forms), ['does', 'doing', 'title'])
                self.assertTrue(all(len(pair) == 2 and all(pair) for pair in forms.values()), 'Arabic and English')

    def test_every_studio_action_has_its_mcp_twin_or_its_reason(self):
        from eaos.core.project.runs import contract
        from eaos.interfaces.mcp_server.studio_parity import NO_TOOL, PARITY
        declared = {f"{row['method']} {row['path']}" for row in contract()['endpoints']}
        self.assertEqual(sorted(declared - set(PARITY) - set(NO_TOOL)), [])


if __name__ == '__main__':
    unittest.main()
