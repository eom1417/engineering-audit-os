"""Fixes in waves: the expensive gates once per batch (eaos/features/fix/journey/waves/ finish_batch, behind the MCP
fix_finish): the code laws and the Python suite."""
import json
import unittest
from pathlib import Path
from unittest import mock
from shared_fixture import scratch


class CodeLawsGateTests(unittest.TestCase):
    def test_a_change_that_copies_leaves_dead_code_or_adds_complexity_is_refused_and_a_partial_split_is_kept(self):
        from eaos.features.fix.analysis.gates import debt, words
        new_debt = lambda before, after, paths: words(debt(before, after, paths))

        def facts(folder, functions, clones=(), dead=()):
            (Path(folder) / 'facts').mkdir(parents=True)
            metrics = [{'kind': 'metric', 'location': {'path': path, 'symbol': name},
                        'value': {'scope': scope, 'branches': n}}
                       for path, name, n, scope in (row + ('function',) * (4 - len(row)) for row in functions)]
            metrics += [{'kind': 'clone_cluster', 'input_sha': key,
                         'value': {'occurrences': [{'path': 'a.py'}, {'path': 'b.py'}]}}
                        for key in clones]
            dead_facts = [{'location': {'path': 'a.py', 'symbol': name}, 'value': {'rule': 'unused-function'}}
                          for name in dead]
            for name, rows in (('metrics', metrics), ('deadcode', dead_facts)):
                (Path(folder) / 'facts' / f'{name}.json').write_text(json.dumps({'facts': rows}))
            return folder

        before = facts(scratch(), [('a.py', 'big', 60)])
        split = facts(scratch(), [('a.py', 'one', 20), ('a.py', 'two', 20), ('a.py', 'three', 20)])
        self.assertEqual(new_debt(before, split, ['a.py']), [], 'sixty split into three of twenty is less complexity')
        worse = facts(scratch(), [('a.py', 'big', 60), ('a.py', 'new', 20)], clones=['k'], dead=['old'])
        found = new_debt(before, worse, ['a.py'])
        self.assertEqual(len(found), 3, found)
        self.assertEqual(new_debt(before, worse, ['c.py']), [], 'only the files the change touched')
        moved = facts(scratch(), [('b.py', 'big', 60), ('b.py', 'Owner', 60, 'class')])
        self.assertEqual(new_debt(before, moved, ['a.py', 'b.py']), [],
                         'a split that moves a complex function into a new module adds nothing, nor does its class')


    def test_a_module_past_the_line_limit_or_outside_the_declared_layers_is_refused_on_the_card(self):
        # A new module in no declared layer, or a module grown past its limit, is refused on the card, not found only
        # when all the changes meet in the project's own suite.
        from eaos.features.fix.analysis import gates

        def lines(folder, sizes):
            (Path(folder) / 'facts').mkdir(parents=True, exist_ok=True)
            rows = [{'kind': 'metric', 'location': {'path': path}, 'value': {'scope': 'file', 'lines': n}}
                    for path, n in sizes.items()]
            (Path(folder) / 'facts/metrics.json').write_text(json.dumps({'facts': rows}))
            return folder

        before, after = lines(scratch(), {'big.py': 700, 'a.py': 100}), lines(scratch(), {'big.py': 650, 'a.py': 640})
        self.assertEqual(gates.words(gates.debt(before, after, ['big.py', 'a.py'])),
                         ['a.py grew to 640 lines, past the limit of 600: split it'])
        for folder, files in ((before, ['eaos/a.py', 'old.py']), (after, ['eaos/a.py', 'old.py', 'eaos/new.py'])):
            nodes = [{'kind': 'graph_node', 'location': {'path': path}} for path in files]
            (Path(folder) / 'facts/graph.json').write_text(json.dumps({'facts': nodes}))
            (Path(folder) / 'facts/resolve.json').write_text(json.dumps({'facts': []}))
        policy = {'layers': {'core': ['eaos/a.py']}, 'rules': []}
        self.assertEqual([p['where'] for p in gates.structure(before, after, policy)], ['eaos/new.py'],
                         'only the file the change added')


class PythonSuiteGateTests(unittest.TestCase):
    def test_a_change_to_the_apps_files_runs_the_apps_checks_on_the_card_itself(self):
        # An unused import in an app's folder breaks its type check and build: the app's checks run on the card itself,
        # not only when the changes meet.
        from eaos.features.fix.journey import execute
        typecheck = {'argv': ['npm', 'run', 'typecheck'], 'exit': 0, 'failing': []}
        with mock.patch('eaos.features.app_run.adapters.app.run.load_profile', return_value={'app': 'studio'}), \
                mock.patch.object(execute, 'original_checks', return_value=[typecheck]), \
                mock.patch.object(execute, 'project_checks', return_value=[{**typecheck, 'exit': 2}]) as ran:
            self.assertEqual(execute.app_breakage('project', 'runtime', 'copy', ['eaos/features/plan/analysis/cards.py']),
                             [])
            self.assertEqual(execute.app_breakage('project', 'runtime', 'copy', ['studio/src/x.tsx']),
                             ["the app's own check failed: npm run typecheck"])
        self.assertEqual(ran.call_args.kwargs, {'python': False}, 'the whole Python suite stays for the batch')

    def test_a_python_suite_beside_the_app_is_a_gate_and_only_its_new_failures_count(self):
        from eaos.features.fix.journey.execute import failing, regressions
        from eaos.features.app_run.adapters.testing.verify import python_tests
        root = Path(scratch())
        self.assertEqual(python_tests(root), [], 'no tests/ folder, no command')
        small = Path(scratch())
        (small / 'tests.py').write_text('')  # a project that keeps its tests at its root
        (small / 'app').mkdir()
        (small / 'app' / 'testing.py').write_text('raise SystemExit')   # never imported to find the tests
        self.assertEqual(python_tests(small)[0][-3:], ['-m', 'unittest', 'tests'])
        layered = Path(scratch())
        (layered / 'tests' / 'e2e' / 'node_modules' / 'gyp').mkdir(parents=True)
        (layered / 'tests' / 'e2e' / 'node_modules' / 'gyp' / 'test_gyp.py').write_text('')   # a dependency's
        (layered / 'tests' / 'unit').mkdir()
        (layered / 'tests' / 'unit' / 'test_a.py').write_text('')    # a folder unittest cannot enter
        self.assertEqual(python_tests(layered), [])
        # a package of tests with an __init__.py is found by discovery
        (layered / 'tests' / 'unit' / '__init__.py').write_text('')
        self.assertEqual(python_tests(layered)[0][-3:], ['discover', '-s', 'tests'])
        (root / 'tests').mkdir()
        (root / 'tests' / 'test_a.py').write_text('')
        self.assertEqual(python_tests(root)[0][-3:], ['discover', '-s', 'tests'])
        (root / 'conftest.py').write_text('')
        self.assertEqual(python_tests(root)[0][-2:], ['pytest', '-q'])
        argv = ['python', '-m', 'unittest']
        before = [{'argv': argv, 'exit': 1, 'failing': failing('FAIL: test_old (tests.test_a.A.test_old)\n')}]
        after = [{'argv': argv, 'exit': 1,
                  'failing': failing('FAIL: test_old (tests.test_a.A.test_old)\n'
                                     'ERROR: test_new (tests.test_a.A.test_new)\n')}]
        self.assertEqual(regressions(before, after),
                         ['python -m unittest (1 new failing: test_new (tests.test_a.A.test_new))'])

    def test_a_jest_suite_already_failing_counts_its_new_failures(self):
        # the test gate must read jest output, not only TAP, unittest and pytest, so a new jest failure is counted
        from eaos.features.fix.journey.execute import failing, regressions
        old = ('FAIL api src/tests/services/auth.service.test.ts\n'
               '  \u25cf AuthService \u203a login \u203a should throw an error\n\n'
               '    expect(received).rejects.toThrow()\n\n  \u25cf Console\n\n    console.log\n'
               'Tests:       1 failed, 26 passed, 27 total\n')
        new = old.replace('FAIL api src/tests/services/auth.service.test.ts\n',
                          'FAIL api src/tests/services/auth.service.test.ts\n'
                          '  \u25cf AuthService \u203a createUser \u203a should create new user \n')
        argv = ['npm', 'run', 'test']
        self.assertEqual(regressions([{'argv': argv, 'exit': 1, 'failing': failing(old)}],
                                     [{'argv': argv, 'exit': 1, 'failing': failing(new)}]),
                         ['npm run test (1 new failing: AuthService \u203a createUser \u203a should create new user)'])
        self.assertEqual(failing(' FAIL  src/a.test.ts > cart > adds one\n'), ['cart > adds one'],
                         'vitest says it on one line')

    def test_a_check_that_cannot_run_here_is_named_never_silent(self):
        # a check that exits 127 (program not found) on the original and on every gate is no gate; it is named, not
        # silent
        from eaos.features.fix.journey.execute import not_run
        rows = [{'argv': ['bun', 'run', 'lint'], 'exit': 127, 'failing': []},
                {'argv': ['bun', 'run', 'test'], 'exit': 127, 'failing': []},
                {'argv': ['npm', 'test'], 'exit': 1, 'failing': []}]
        self.assertEqual(not_run(rows), ['bun run lint', 'bun run test'])

    def test_the_files_a_card_changed_beyond_its_own_are_named(self):
        # a card kept with changes to files beyond its own must name them to the person
        from eaos.features.fix.journey.finish import beyond
        own = 'frontend/src/components/Admin/AddUser.tsx'
        others = [f'frontend/src/components/{name}.tsx' for name in (
            'Admin/DeleteUser', 'Admin/EditUser', 'Admin/UserFormFields', 'Common/DeleteDialog', 'Common/FormDialog',
            'Common/FormFields',
            'Items/AddItem', 'Items/DeleteItem', 'Items/EditItem', 'Items/ItemActionsMenu',
            'Items/ItemDialog')] + ['frontend/src/routes/_layout/items.tsx']
        self.assertEqual(beyond({'paths': [own]}, [own, *others]), others)
        self.assertEqual(beyond({'paths': ['frontend/src/components']}, [own, *others]),
                         ['frontend/src/routes/_layout/items.tsx'])
        self.assertEqual(beyond({'paths': ['*']}, [own, *others]), [])


if __name__ == '__main__':
    unittest.main()
