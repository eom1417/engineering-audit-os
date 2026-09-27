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

    def test_an_import_only_the_removed_code_used_goes_with_it_and_the_rest_stay(self):
        import subprocess
        from eaos.codemods import TRANSFORM
        if not which('jscodeshift'): self.skipTest('jscodeshift is not installed')
        root = self.project({'src/a.tsx': "import 'side-effect'\nimport { createContext, useContext } from 'react'\n"
                                           "import { already } from 'x'\n"
                                           "export const Ctx = createContext(1)\nexport const useCtx = () => useContext(Ctx)\n"})
        subprocess.run([which('jscodeshift'), '-t', str(TRANSFORM), '--parser=tsx', '--name=useCtx', 'src/a.tsx'],
                       cwd=root, capture_output=True, check=True)
        text = (root / 'src/a.tsx').read_text()
        self.assertNotIn('useContext', text)
        self.assertIn("import { createContext } from 'react'", text)
        self.assertIn("import 'side-effect'", text, 'a side-effect import is kept for its effect')
        self.assertIn("import { already } from 'x'", text, 'an import unused before the change is not the change\'s to remove')

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


class CopyLifetimeTests(Workspace):
    """A large project dry-runs hundreds of cards: one copy, restored between cards, and gone afterwards."""

    def project(self, files):
        root = Path(self.tmp) / 'project'
        for name, text in files.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text)
        return root

    def leftovers(self):
        import glob, tempfile
        return set(glob.glob(str(Path(tempfile.gettempdir()) / 'eaos-codemod-*')))

    def test_no_copy_outlives_a_dry_run(self):
        root = self.project({'old.txt': 'x\n'})
        before = self.leftovers()
        result, _ = dry_run({'kind': 'delete-file', 'path': 'old.txt'}, root)
        self.assertEqual(result, {'exit': 0, 'files_changed': 1})
        self.assertEqual(self.leftovers(), before)
        self.assertTrue((root / 'old.txt').exists())

    def test_every_card_starts_from_the_untouched_project_on_the_shared_copy(self):
        from eaos.codemods import attach
        root = self.project({'a.py': 'def gone():\n    return 1\n\n\ndef kept():\n    return 2\n', 'old.txt': 'x\n'})
        out = Path(self.tmp) / 'out'
        (out / 'facts').mkdir(parents=True)
        (out / 'facts/deadcode.json').write_text(json.dumps({'facts': [
            {'id': 'F1', 'kind': 'dead', 'value': {'rule': 'unreferenced-symbol'}, 'location': {'path': 'a.py', 'symbol': 'gone'}},
            {'id': 'F2', 'kind': 'leftover', 'value': {}, 'location': {'path': 'old.txt'}}]}))
        tasks = [{'pattern': 'leftover', 'evidence': {'fact_ids': ['F2']}},
                 {'pattern': 'leftover', 'evidence': {'fact_ids': ['F2']}}]
        before = self.leftovers()
        self.assertEqual(attach(tasks, out, root), 2)
        # the second card deletes the same file again: it was restored after the first, so it changes one file too
        self.assertEqual([t['codemod']['dry_run'] for t in tasks], [{'exit': 0, 'files_changed': 1}] * 2)
        self.assertEqual(self.leftovers(), before)
        self.assertTrue((root / 'old.txt').exists())


class AppFolderTests(Workspace):
    def test_an_upgrade_runs_in_the_folder_of_the_lock_file_the_scanner_read(self):
        import tempfile
        from eaos.codemods import _commands, card_for
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'app').mkdir()
            (Path(tmp) / 'app/package.json').write_text('{"dependencies": {"sharp": "^0.35.3"}}')
            (Path(tmp) / 'app/package-lock.json').write_text('{}')
            fact = {'id': 'F', 'location': {'path': 'app/package-lock.json', 'symbol': 'npm:sharp@0.35.3'},
                    'value': {'measurements': [{'name': 'fixed_in', 'value': '0.35.4'}]}}
            card = card_for({'pattern': 'upgrade_dependency', 'evidence': {'fact_ids': ['F']}}, {'F': fact}, tmp)
            self.assertEqual((card['folder'], card['direct']), ('app', True))
            argv = _commands(card, Path(tmp))[0][0]
            self.assertEqual(argv[1:3], ['install', 'sharp@0.35.4'])
            self.assertEqual(argv[-2:], ['--prefix', 'app'])
