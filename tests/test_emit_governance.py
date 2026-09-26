"""The governance kit: CI pinned by commit, fast hooks, grouped updates, and the target's boundaries as rules."""
import json
import re
import unittest
from pathlib import Path

from shared_fixture import Workspace
import kit_fixture

from eaos.emit.engines_check import installed
from eaos.emit import emit
from eaos.emit import governance
from eaos.emit.yamltext import dump
from eaos.reference_architecture import by_id


class BoundaryRuleTests(unittest.TestCase):
    def test_the_most_specific_glob_wins_as_in_placement(self):
        ref = by_id('react-vite-spa-rest')
        lib = next(layer for layer in ref['layers'] if layer['name'] == 'lib')
        # src/lib/*Api.ts is the api-client's, although it shares the src/lib/ prefix with lib
        self.assertIn('src/lib/*Api.ts', governance.narrower(lib, ref))
        self.assertIn('src/lib/Api.ts', governance.narrower(lib, ref))

    def test_a_glob_becomes_an_anchored_path_expression(self):
        self.assertRegex('src/lib/fuelApi.ts', governance.glob_regex('src/lib/*Api.ts'))
        self.assertNotRegex('src/lib/api/fuelApi.ts', governance.glob_regex('src/lib/*Api.ts'))
        self.assertRegex('src/pages/a/b.tsx', governance.glob_regex('src/pages/**'))

    def test_every_pair_the_reference_does_not_allow_is_a_rule_and_no_allowed_pair_is(self):
        ref = by_id('react-vite-spa-rest')
        pairs = {(a['name'], b['name']) for a, b in governance.forbidden_pairs(ref)}
        self.assertIn(('pages', 'api-client'), pairs)
        self.assertNotIn(('features', 'api-client'), pairs)

    def test_python_modules_are_matched_by_the_layer_globs(self):
        self.assertEqual(governance.module_regex(['core/**', 'core/database.py']), [r'core(\.|$)', r'core\.database$'])


class YamlTests(unittest.TestCase):
    def test_words_yaml_would_misread_are_quoted_and_scripts_are_literal_blocks(self):
        text = dump({'on': {'push': {}}, 'run': 'a\nb\n', 'x': 'yes', 'k': 'a: b', 'count': 3, 'y': 1})
        self.assertIn('"on":', text)
        self.assertIn('run: |\n  a\n  b', text)
        self.assertIn('x: "yes"', text)
        self.assertIn('k: "a: b"', text)
        self.assertIn('count: 3', text)
        self.assertIn('"y": 1', text)   # YAML 1.1 reads a bare y as true


class KitTests(Workspace):
    def test_every_action_is_pinned_to_a_full_commit(self):
        _, report = kit_fixture.build(self.tmp)
        governance.write(report)
        text = (report / 'handover/.github/workflows/eaos.yml').read_text()
        pins = re.findall(r'uses: ([\w./-]+)@(\S+)', text)
        self.assertTrue(pins)
        self.assertTrue(all(re.fullmatch(r'[0-9a-f]{40}', sha) for _, sha in pins), pins)

    def test_steps_follow_the_project(self):
        _, report = kit_fixture.build(self.tmp)
        governance.write(report)
        text = (report / 'handover/.github/workflows/eaos.yml').read_text()
        self.assertIn('bun install --frozen-lockfile', text)
        self.assertIn('bun run test', text)
        self.assertIn('--ignore-known .dependency-cruiser-known-violations.json', text)
        self.assertNotIn('checkov', text)   # no CI and no IaC in the project
        self.assertIn('sha256sum -c', text)  # downloaded tools are checked against the toolchain's hash

    def test_the_eaos_gate_reads_its_package_from_the_environment_not_the_script(self):
        _, report = kit_fixture.build(self.tmp)
        governance.write(report)
        text = (report / 'handover/.github/workflows/eaos.yml').read_text()
        self.assertIn('pip install "$EAOS_PACKAGE"', text)
        self.assertNotIn('pip install "${{', text)

    def test_python_projects_get_boundary_rules_as_imports(self):
        _, report = kit_fixture.build(self.tmp, 'python')
        governance.write(report)
        text = (report / 'handover/semgrep/boundaries.yml').read_text()
        self.assertIn('eaos.boundary.domain-not-services', text)
        self.assertFalse((report / 'handover/.dependency-cruiser.cjs').exists())

    @unittest.skipUnless(installed('actionlint', 'pre-commit', 'renovate-config-validator', 'depcruise', 'semgrep'),
                         'the governance validators are not installed: python -m eaos tools install')
    def test_every_file_is_accepted_by_its_own_tool(self):
        _, report = kit_fixture.build(self.tmp)
        written, rows = emit(report, only=['governance'], validate=True)
        self.assertTrue(rows)
        self.assertEqual([r['path'] for r in rows if not r['ok']], [], rows)

    @unittest.skipUnless(installed('depcruise'), 'dependency-cruiser is not installed')
    def test_the_boundary_rules_catch_a_page_calling_the_api_directly(self):
        import subprocess
        from eaos.engines.process import which
        project, report = kit_fixture.build(self.tmp)
        governance.write(report)
        done = subprocess.run([which('depcruise'), '--config', str(report / 'handover/.dependency-cruiser.cjs'),
                               '--output-type', 'json', 'src'], cwd=project, capture_output=True, text=True)
        rules = {v['rule']['name'] for v in json.loads(done.stdout)['summary']['violations']}
        self.assertIn('eaos-pages-not-api-client', rules)   # src/pages/Home.tsx -> src/lib/Api.ts
        self.assertIn('eaos-lib-not-api-client', rules)     # src/lib/format.ts -> src/lib/Api.ts
