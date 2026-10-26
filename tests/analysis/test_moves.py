"""The move tool (M8.5): files moved, every import and path that names them written again, the program unchanged; and
what the move gate reads to prove it."""
import os
import subprocess
import sys
from pathlib import Path

from shared_fixture import Workspace

from eaos.analysis.repair import move_gate, moves
from eaos.analysis.repair.move_python import Unmovable

SHOP = {
    'shop/__init__.py': '"""Shop."""\nfrom .pipeline_run import go\n',
    'shop/pipeline_run.py': 'from .core import money\nfrom shop.core.money import cents\n\n\ndef go(x):\n    return money.total(x) + cents(1)\n',
    'shop/pipeline_load.py': 'import shop.pipeline_run\n\n\ndef load():\n    return shop.pipeline_run.go(2)\n',
    'shop/core/__init__.py': '',
    'shop/core/money.py': 'def total(x):\n    return x * 2\n\n\ndef cents(x):\n    return x\n',
    'tests/test_shop.py': ('import unittest\nfrom unittest import mock\nfrom shop import pipeline_run, pipeline_load\n'
                           'from shop.pipeline_run import go\n\n\nclass T(unittest.TestCase):\n    def test_go(self):\n'
                           '        self.assertEqual(go(1), 3)\n\n    def test_load(self):\n        self.assertEqual(pipeline_load.load(), 5)\n\n'
                           "    def test_patch(self):\n        with mock.patch('shop.pipeline_run.cents', return_value=0):\n"
                           '            self.assertEqual(pipeline_run.go(1), 2)\n'),
    'docs/README.md': 'See `shop/pipeline_run.py`, and [the loader](../shop/pipeline_load.py).\n',
}
FAMILY = [{'from': 'shop/pipeline_run.py', 'to': 'shop/pipeline/run.py'}, {'from': 'shop/pipeline_load.py', 'to': 'shop/pipeline/load.py'}]


class MoveTests(Workspace):
    def project(self, files, git=True):
        root = Path(self.tmp) / 'project'
        for name, text in files.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text, encoding='utf-8')
        if git:
            for argv in (['init', '-q'], ['add', '-A'], ['-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-qm', 'one']):
                subprocess.run(['git', '-C', str(root), *argv], check=True, capture_output=True)
        return root

    def suite_of(self, root):
        done = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], cwd=root, capture_output=True,
                              text=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        return [{'argv': ['unittest'], 'exit': done.returncode, 'output': done.stdout + done.stderr}]

    def test_a_python_family_moves_into_its_folder_and_every_test_comes_back_with_its_name_and_result(self):
        root = self.project(SHOP)
        before, exposed = self.suite_of(root), move_gate.exports(root, moves.files(root))
        mapping = moves.plan(root, FAMILY)['mapping']
        made = moves.apply(root, FAMILY)
        self.assertEqual(made['created'], ['shop/pipeline/__init__.py'], 'the new folder stays a package')
        self.assertEqual((root / 'shop/__init__.py').read_text(), '"""Shop."""\nfrom .pipeline.run import go\n')
        self.assertIn('from ..core import money\nfrom shop.core.money import cents', (root / 'shop/pipeline/run.py').read_text(),
                      'a moved file\'s relative import is written from its new place, its absolute one kept')
        self.assertIn('import shop.pipeline.run\n', (root / 'shop/pipeline/load.py').read_text())
        self.assertIn('return shop.pipeline.run.go(2)', (root / 'shop/pipeline/load.py').read_text())
        test = (root / 'tests/test_shop.py').read_text()
        self.assertIn('from shop.pipeline import run as pipeline_run, load as pipeline_load', test, 'the names it binds unchanged')
        self.assertIn("mock.patch('shop.pipeline.run.cents'", test)
        self.assertEqual((root / 'docs/README.md').read_text(), 'See `shop/pipeline/run.py`, and [the loader](../shop/pipeline/load.py).\n')
        self.assertFalse((root / 'shop/pipeline_run.py').exists())
        self.assertEqual(move_gate.test_differences(before, self.suite_of(root), mapping), [])
        after = {'entries': [], 'commands': {}, 'exports': move_gate.exports(root, moves.files(root))}
        self.assertEqual(move_gate.surface_differences({'entries': [], 'commands': {}, 'exports': exposed}, after, mapping), [])

    def test_javascript_and_typescript_specifiers_keep_the_form_they_were_written_in(self):
        root = self.project({
            'tsconfig.json': '{ "compilerOptions": { "baseUrl": ".", "paths": { "@/*": ["src/*"] } } }',
            'package.json': '{"name":"x","main":"src/index.ts","scripts":{"lint":"eslint src/lib/utils_date.ts"}}',
            'src/index.ts': "import { fmt } from './lib/utils_date';\nimport Button from './components/Button';\nexport * from \"./lib/utils_money.js\";\n",
            'src/lib/utils_date.ts': 'export const fmt = (d: Date) => d.toISOString();\n',
            'src/lib/utils_money.ts': "import { fmt } from '@/lib/utils_date';\nexport const cents = (x: number) => fmt(new Date(x));\n",
            'src/components/Button/index.tsx': "import { cents } from '../../lib/utils_money';\nexport default function Button() { return cents(1); }\n",
            'test/a.test.ts': ("import { fmt } from '../src/lib/utils_date';\nvi.mock('../src/lib/utils_money', () => ({}));\n"
                               "const lazy = () => import('@/components/Button');\nconst r = require('../src/lib/utils_date.ts');\n"
                               "import React from 'react';\n")}, git=False)
        moves.apply(root, [{'from': 'src/lib/utils_date.ts', 'to': 'src/lib/utils/date.ts'},
                           {'from': 'src/lib/utils_money.ts', 'to': 'src/lib/utils/money.ts'}, {'from': 'src/components/Button', 'to': 'src/ui/Button'}])
        self.assertEqual((root / 'src/index.ts').read_text(),
                         "import { fmt } from './lib/utils/date';\nimport Button from './ui/Button';\nexport * from \"./lib/utils/money.js\";\n")
        self.assertIn("from '@/lib/utils/date'", (root / 'src/lib/utils/money.ts').read_text(), 'an alias stays an alias')
        self.assertIn("from '../../lib/utils/money'", (root / 'src/ui/Button/index.tsx').read_text())
        self.assertEqual((root / 'test/a.test.ts').read_text(),
                         "import { fmt } from '../src/lib/utils/date';\nvi.mock('../src/lib/utils/money', () => ({}));\n"
                         "const lazy = () => import('@/ui/Button');\nconst r = require('../src/lib/utils/date.ts');\nimport React from 'react';\n")
        self.assertIn('eslint src/lib/utils/date.ts', (root / 'package.json').read_text())
        self.assertFalse((root / 'src/components').exists(), 'the folder the moves emptied is gone')

    def test_a_move_that_would_change_what_the_code_means_is_refused_whole_and_nothing_is_written(self):
        root = self.project({**SHOP, 'shop/paths.py': 'from pathlib import Path\nHERE = Path(__file__).parent\n',
                             'shop/pipeline.py': 'X = 1\n'})
        cases = {'shop/paths.py finds other files from its own place': [{'from': 'shop/paths.py', 'to': 'shop/core/paths.py'}],
                 'shop/core/money.py is already there': [{'from': 'shop/pipeline_run.py', 'to': 'shop/core/money.py'}],
                 'beside the module shop/pipeline.py': FAMILY}
        for why, asked in cases.items():
            with self.assertRaises(Unmovable) as refused: moves.apply(root, asked)
            self.assertIn(why, str(refused.exception))
            self.assertEqual(subprocess.run(['git', '-C', str(root), 'status', '--porcelain'], capture_output=True, text=True).stdout, '')

    def test_the_gate_reads_each_test_by_its_name_and_says_when_none_can_be_read(self):
        unittest_output = 'test_go (test_shop.T.test_go) ... ok\ntest_x (test_shop.T.test_x)\nA docstring. ... FAIL\n'
        pytest_output = 'PASSED tests/test_a.py::test_one\nFAILED tests/test_a.py::test_two - assert 1\n'
        tap = 'ok 1 - adds\nnot ok 2 - subtracts\nok 3 - later # SKIP not yet\n'
        vitest = ' ✓ src/a.test.ts > adds 3ms\n × src/a.test.ts > subtracts\n'
        self.assertEqual(set(move_gate.test_results(unittest_output)), {('test_shop.T.test_go', 'passed'), ('test_shop.T.test_x', 'failed')})
        self.assertEqual(set(move_gate.test_results(pytest_output)), {('tests/test_a.py::test_one', 'passed'), ('tests/test_a.py::test_two', 'failed')})
        self.assertEqual(set(move_gate.test_results(tap)), {('adds', 'passed'), ('subtracts', 'failed'), ('later', 'skipped')})
        self.assertEqual(set(move_gate.test_results(vitest)), {('src/a.test.ts > adds', 'passed'), ('src/a.test.ts > subtracts', 'failed')})
        self.assertEqual(move_gate.test_results('Tests  12 passed (12)\n'), {('(counts)', 'passed'): 12})
        self.assertEqual(move_gate.unproven([]), 'the project has no check or test EAOS can run')
        self.assertIn('could not read', move_gate.unproven([{'argv': ['npm', 'test'], 'exit': 0, 'output': 'done\n'}]))

    def test_a_test_moved_with_its_module_is_the_same_test_and_a_lost_name_is_a_difference(self):
        mapping = {'tests/test_shop.py': 'tests/shop/test_shop.py', 'src/a.test.ts': 'src/lib/a.test.ts'}
        before = [{'argv': ['t'], 'exit': 0, 'output': 'test_go (test_shop.T.test_go) ... ok\n ✓ src/a.test.ts > adds\n'}]
        after = [{'argv': ['t'], 'exit': 0, 'output': 'test_go (shop.test_shop.T.test_go) ... ok\n ✓ src/lib/a.test.ts > adds\n'}]
        self.assertEqual(move_gate.test_differences(before, after, mapping), [])
        lost = [{'argv': ['t'], 'exit': 0, 'output': 'test_go (shop.test_shop.T.test_go) ... ok\n'}]
        self.assertEqual(move_gate.test_differences(before, lost, mapping), ['src/lib/a.test.ts > adds: passed before, not after'])
        exposed = {'entries': [('http', 'GET', '/a')], 'commands': {'script:shop': 'shop/cli.py'}, 'exports': {'a.py': ['f', 'g']}}
        now = {'entries': [], 'commands': {'script:shop': 'shop/cli/main.py'}, 'exports': {'b.py': ['f']}}
        self.assertEqual(move_gate.surface_differences(exposed, now, {'a.py': 'b.py'}),
                         ['the entry point http GET /a is gone', 'the command script:shop ran shop/cli.py and now runs shop/cli/main.py',
                          'b.py no longer exposes what a.py did: g'])
