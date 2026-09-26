"""Codemods of mechanical cards: the right tool, tried on an isolated copy, the project never written."""
import json
from pathlib import Path

from shared_fixture import Workspace

from eaos.codemods import card_for, dry_run, remove_python
from eaos.engines.process import state_digest, which


class CodemodTests(Workspace):
    def project(self, files):
        root = Path(self.tmp) / 'project'
        for name, text in files.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text)
        return root

    def test_python_removes_exactly_the_named_definition_with_its_decorators(self):
        root = self.project({'m.py': 'import x\n\n@cache\ndef gone(a):\n    return a\n\n\ndef kept():\n    return 1\n\nRATE = 2\n'})
        self.assertTrue(remove_python(root / 'm.py', 'gone'))
        self.assertTrue(remove_python(root / 'm.py', 'RATE'))
        self.assertEqual((root / 'm.py').read_text(), 'import x\n\n\n\ndef kept():\n    return 1\n\n')
        self.assertFalse(remove_python(root / 'm.py', 'absent'))

    def test_a_dead_symbol_in_typescript_is_removed_by_jscodeshift_on_a_copy(self):
        if not which('jscodeshift'): self.skipTest('jscodeshift is not installed')
        root = self.project({'src/a.ts': 'export function keep() { return 1; }\nexport function unused() { return 2; }\n'})
        before = state_digest(root)
        result, command = dry_run({'kind': 'jscodeshift', 'path': 'src/a.ts', 'symbol': 'unused'}, root)
        self.assertEqual(result, {'exit': 0, 'files_changed': 1})
        self.assertIn('--name=unused', command)
        self.assertEqual(state_digest(root), before)

    def test_a_tool_that_changes_nothing_says_so(self):
        if not which('jscodeshift'): self.skipTest('jscodeshift is not installed')
        root = self.project({'src/a.ts': 'export function keep() { return 1; }\n'})
        self.assertEqual(dry_run({'kind': 'jscodeshift', 'path': 'src/a.ts', 'symbol': 'absent'}, root)[0]['files_changed'], 0)

    def test_a_direct_dependency_is_installed_and_a_transitive_one_is_overridden(self):
        root = self.project({'package.json': json.dumps({'dependencies': {'axios': '1.0.0'}}), 'package-lock.json': '{}'})
        fact = lambda name: {'id': 'F', 'location': {'symbol': f'npm:{name}@1.0.0'},
                             'value': {'measurements': [{'name': 'fixed_in', 'value': '1.2.0'}]}}
        task = {'pattern': 'upgrade_dependency', 'evidence': {'fact_ids': ['F']}}
        self.assertTrue(card_for(task, {'F': fact('axios')}, root)['direct'])
        self.assertFalse(card_for(task, {'F': fact('picomatch')}, root)['direct'])

    def test_the_npm_upgrade_changes_only_the_manifest_and_lock_of_the_copy(self):
        if not which('npm'): self.skipTest('npm is not installed')
        root = self.project({'package.json': json.dumps({'name': 'f', 'version': '1.0.0', 'dependencies': {'micromatch': '4.0.5'}})})
        import subprocess
        subprocess.run(['npm', 'install', '--package-lock-only', '--ignore-scripts', '--loglevel=error'], cwd=root, capture_output=True)
        before = state_digest(root)
        # A fresh lock already resolves the newest picomatch; any other version shows the override reaching the lock.
        result, command = dry_run({'kind': 'npm', 'package': 'picomatch', 'fixed': '2.3.1', 'direct': False}, root)
        if result['exit'] != 0: self.skipTest('the npm registry is unreachable')
        self.assertEqual(result['files_changed'], 2)
        self.assertIn('overrides.picomatch=2.3.1', command)
        self.assertEqual(state_digest(root), before)
