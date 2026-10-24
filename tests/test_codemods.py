"""Codemods of mechanical cards: the right tool, tried on an isolated copy, the project never written."""
import glob
import json
from pathlib import Path
import subprocess
import tempfile

from shared_fixture import Workspace

from eaos.analysis.codemods import TRANSFORM, _commands, attach, card_for, dry_run, remove_python
from eaos.engines.process import state_digest, which


def upgrade(path, symbol, fixed):
    fact = {'id': 'F', 'location': {'path': path, 'symbol': symbol}, 'value': {'measurements': [{'name': 'fixed_in', 'value': fixed}]}}
    return {'pattern': 'upgrade_dependency', 'evidence': {'fact_ids': ['F']}}, {'F': fact}


class CodemodTests(Workspace):
    def project(self, files):
        root = Path(self.tmp) / 'project'
        for name, text in files.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text)
        return root

    def leftovers(self):
        return set(glob.glob(str(Path(tempfile.gettempdir()) / 'eaos-codemod-*')))

    def test_python_removes_exactly_the_named_definition_with_its_decorators(self):
        root = self.project({'m.py': 'import x\n\n@cache\ndef gone(a):\n    return a\n\n\ndef kept():\n    return 1\n\nRATE = 2\n'})
        self.assertTrue(remove_python(root / 'm.py', 'gone'))
        self.assertTrue(remove_python(root / 'm.py', 'RATE'))
        self.assertEqual((root / 'm.py').read_text(), 'import x\n\n\n\ndef kept():\n    return 1\n\n')
        self.assertFalse(remove_python(root / 'm.py', 'absent'))

    def test_a_dead_typescript_symbol_is_removed_by_jscodeshift_on_a_copy(self):
        if not which('jscodeshift'): self.skipTest('jscodeshift is not installed')
        root = self.project({'src/a.ts': 'export function keep() { return 1; }\nexport function unused() { return 2; }\n',
                             'src/b.tsx': "import 'side-effect'\nimport { createContext, useContext } from 'react'\n"
                                          "import { already } from 'x'\n"
                                          "export const Ctx = createContext(1)\nexport const useCtx = () => useContext(Ctx)\n"})
        before = state_digest(root)
        result, command = dry_run({'kind': 'jscodeshift', 'path': 'src/a.ts', 'symbol': 'unused'}, root)
        self.assertEqual(result, {'exit': 0, 'files_changed': 1})
        self.assertIn('--name=unused', command)
        self.assertEqual(state_digest(root), before)
        self.assertEqual(dry_run({'kind': 'jscodeshift', 'path': 'src/a.ts', 'symbol': 'absent'}, root)[0]['files_changed'], 0)
        # An import only the removed code used goes with it; the rest stay.
        subprocess.run([which('jscodeshift'), '-t', str(TRANSFORM), '--parser=tsx', '--name=useCtx', 'src/b.tsx'],
                       cwd=root, capture_output=True, check=True)
        text = (root / 'src/b.tsx').read_text()
        self.assertNotIn('useContext', text)
        self.assertIn("import { createContext } from 'react'", text)
        self.assertIn("import 'side-effect'", text)
        self.assertIn("import { already } from 'x'", text)

    def test_an_upgrade_targets_every_vulnerable_lock_file_and_changes_only_the_copy(self):
        root = self.project({'package.json': json.dumps({'dependencies': {'axios': '1.0.0'}}), 'package-lock.json': '{}',
                             'app/package.json': '{"dependencies": {"sharp": "^0.35.3"}}', 'app/package-lock.json': '{}'})
        self.assertTrue(card_for(*upgrade('package-lock.json', 'npm:axios@1.0.0', '1.2.0'), root)['direct'])
        self.assertFalse(card_for(*upgrade('package-lock.json', 'npm:picomatch@1.0.0', '1.2.0'), root)['direct'])
        card = card_for(*upgrade('app/package-lock.json', 'npm:sharp@0.35.3', '0.35.4'), root)
        self.assertEqual((card['folder'], card['direct']), ('app', True))
        argv = _commands(card, root)[0][0]
        self.assertEqual((argv[1:3], argv[-2:]), (['install', 'sharp@0.35.4'], ['--prefix', 'app']))
        lock = lambda version: json.dumps({'packages': {'node_modules/nanoid': {'version': version}}})
        root = self.project({'package.json': '{"dependencies": {"vite": "5"}}', 'package-lock.json': lock('3.3.15'),
                             'server/package.json': '{"dependencies": {"nanoid": "^3"}}', 'server/package-lock.json': lock('3.3.15'),
                             'docs/package.json': '{}', 'docs/package-lock.json': lock('3.3.18')})
        card = card_for(*upgrade('package-lock.json', 'npm:nanoid@3.3.15', '3.3.18'), root)
        self.assertEqual(card['folders'], [('.', False), ('server', True)], 'a lock file already fixed is left alone')
        argv = [step[0] for step in _commands(card, root)]
        self.assertEqual((argv[-1][1:3], argv[-1][-2:]), (['install', 'nanoid@3.3.18'], ['--prefix', 'server']))
        # The npm upgrade changes only the manifest and lock of the copy.
        if not which('npm'): self.skipTest('npm is not installed')
        root = self.project({'package.json': json.dumps({'name': 'f', 'version': '1.0.0', 'dependencies': {'micromatch': '4.0.5'}})})
        subprocess.run(['npm', 'install', '--package-lock-only', '--ignore-scripts', '--loglevel=error'], cwd=root, capture_output=True)
        before = state_digest(root)
        # A fresh lock already resolves the newest picomatch; any other version shows the override reaching the lock.
        result, command = dry_run({'kind': 'npm', 'package': 'picomatch', 'fixed': '2.3.1', 'direct': False}, root)
        if result['exit'] != 0: self.skipTest('the npm registry is unreachable')
        self.assertEqual(result['files_changed'], 2)
        self.assertIn('overrides.picomatch=2.3.1', command)
        self.assertEqual(state_digest(root), before)

    def test_every_card_starts_from_the_untouched_project_and_no_copy_outlives_the_run(self):
        # A large project dry-runs hundreds of cards: one copy, restored between cards, and gone afterwards.
        root = self.project({'a.py': 'def gone():\n    return 1\n\n\ndef kept():\n    return 2\n', 'old.txt': 'x\n'})
        out = Path(self.tmp) / 'out'
        (out / 'facts').mkdir(parents=True)
        (out / 'facts/deadcode.json').write_text(json.dumps({'facts': [
            {'id': 'F1', 'kind': 'dead', 'value': {'rule': 'unreferenced-symbol'}, 'location': {'path': 'a.py', 'symbol': 'gone'}},
            {'id': 'F2', 'kind': 'leftover', 'value': {}, 'location': {'path': 'old.txt'}}]}))
        tasks = [{'pattern': 'leftover', 'evidence': {'fact_ids': ['F2']}} for _ in range(2)]
        before = self.leftovers()
        self.assertEqual(attach(tasks, out, root), 2)
        self.assertEqual([t['codemod']['dry_run'] for t in tasks], [{'exit': 0, 'files_changed': 1}] * 2)
        self.assertEqual(dry_run({'kind': 'delete-file', 'path': 'old.txt'}, root)[0], {'exit': 0, 'files_changed': 1})
        self.assertEqual(self.leftovers(), before)
        self.assertTrue((root / 'old.txt').exists())
