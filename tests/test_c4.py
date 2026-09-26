"""C4 models written from the records, and judged by the Structurizr CLI itself."""
import json
import re
from pathlib import Path

from shared_fixture import Workspace

from eaos.c4 import quote, workspace, write


class C4Tests(Workspace):
    def test_names_are_quoted_and_escaped_and_identifiers_are_plain(self):
        dsl, mermaid = workspace('p', 'stack', [('a "quoted" name', 'd'), ('feature:x', 'e')], [('feature:x', 'a "quoted" name', 'uses')], [])
        self.assertIn(quote('a "quoted" name'), dsl)
        self.assertIn('\\"quoted\\"', dsl)
        self.assertEqual(dsl.count('{'), dsl.count('}'))
        for identifier in re.findall(r'^\s*(\w+) = ', dsl, re.M): self.assertRegex(identifier, r'^[A-Za-z0-9_]+$')
        self.assertIn('c2 -> c1 "uses"', dsl)
        self.assertTrue(mermaid.startswith('flowchart LR'))

    def report(self):
        out = Path(self.tmp)
        (out / 'facts').mkdir()
        (out / 'target-architecture.json').write_text(json.dumps({
            'reference': 'react-vite-spa-rest',
            'current_components': [{'id': 'T-src', 'name': 'src', 'origin': 'src', 'depends_on': ['src/lib'], 'relation': 'modify', 'reason': 'r'},
                                   {'id': 'T-lib', 'name': 'src/lib', 'origin': 'src/lib', 'depends_on': [], 'relation': 'retain', 'reason': 'r'}],
            'target_components': [{'name': 'feature:fleet', 'responsibility': 'fleet'}, {'name': 'api-client', 'responsibility': 'http'}],
            'target_edges': [{'from': 'feature:fleet', 'to': 'api-client', 'imports': 3}]}))
        return out

    def test_every_current_and_target_component_is_in_its_model_with_its_dependencies(self):
        out = self.report()
        written = write(out)
        self.assertEqual([e.path for e in written], ['architecture/current/workspace.dsl', 'architecture/target/workspace.dsl'])
        current = (out / 'architecture/current/workspace.dsl').read_text()
        target = (out / 'architecture/target/workspace.dsl').read_text()
        self.assertIn('component "src"', current)
        self.assertIn('c1 -> c2 "depends on"', current)
        self.assertIn('component "feature:fleet"', target)
        self.assertIn('c1 -> c2 "3 import(s)"', target)
        self.assertTrue((out / 'architecture/target/diagram.mmd').is_file())

    def test_the_structurizr_cli_accepts_both_models(self):
        from eaos.emit import emit
        from eaos.engines.process import which
        if not which('structurizr'): self.skipTest('structurizr-cli is not installed: python -m eaos tools install')
        out = self.report()
        _, rows = emit(out, only=['c4'], validate=True)
        self.assertEqual([r['ok'] for r in rows], [True, True], rows)

    def test_the_cli_rejects_a_broken_model(self):
        import subprocess
        from eaos.engines.process import which
        from eaos.toolchain import home
        if not which('structurizr'): self.skipTest('structurizr-cli is not installed')
        bad = Path(self.tmp) / 'bad.dsl'
        bad.write_text('workspace "x" {\n  model {\n    a = person "A"\n    a -> nothing "uses"\n  }\n}\n')
        import os
        env = {**os.environ, 'PATH': str(home() / 'bin') + os.pathsep + os.environ['PATH']}
        self.assertNotEqual(subprocess.run([which('structurizr'), 'validate', '-workspace', str(bad)], env=env,
                                           capture_output=True).returncode, 0)
