"""Fixes in waves: the card at fault found by halving, and the batch rebuilt from what is left."""
import json
import unittest
from pathlib import Path
from unittest import mock
from needs import need
from eaos.journeys.fix import waves
from eaos.journeys.fix.waves import batch as wave_batch
from shared_fixture import scratch
from tests.journeys._waves_fixture import commit_file, git, repository


class RebuildTests(unittest.TestCase):
    def test_a_module_is_split_only_after_its_complex_functions_and_a_split_tried_too_early_comes_back(self):
        # a split tried before its simplifications fails and must come back after them
        from eaos.core.project import ledger
        report = Path(scratch())
        card = lambda i, needs=(): {'id': i, 'kind': 'remediate', 'decision': {'readiness': 'ready'},
                                    'prerequisites': [{'task_id': n} for n in needs]}
        (report / 'plan.json').write_text(json.dumps({'tasks': [card('SPLIT', ['SIMPLIFY']), card('SIMPLIFY')],
                                                      'milestones': []}))
        keys = {c['id']: c['key'] for c in waves.plan(report)['tasks']}
        book = {keys['SPLIT']: {'id': 'SPLIT', 'state': 'skipped', 'batch': 1},
                keys['SIMPLIFY']: {'id': 'SIMPLIFY', 'state': 'open'}}
        state = {'project': 'p', 'tried': [keys['SPLIT']]}
        with mock.patch.object(ledger, 'load', return_value={'cards': book}):
            self.assertEqual(waves.next_batch(report, state), ['SIMPLIFY'], 'the split waits for the simplification')
            self.assertEqual(waves.too_early(state, [card('SPLIT', ['SIMPLIFY'])])['waits'], {'SPLIT': ['SIMPLIFY']})
            book[keys['SIMPLIFY']].update(state='done', batch=2)
            ledger._reopen_waited({c['id']: c for c in book.values()}, [card('SPLIT', ['SIMPLIFY'])])
            self.assertEqual(book[keys['SPLIT']]['state'], 'open', 'set aside by the order, not by its own change')
            self.assertEqual(waves.next_batch(report, state), ['SPLIT'], 'tried, but opened again by the ledger')
        # a split whose simplifications are open goes in the same batch, after them, not left for the next batch
        book[keys['SIMPLIFY']].update(state='open', batch=None)
        with mock.patch.object(ledger, 'load', return_value={'cards': book}):
            self.assertEqual(waves.next_batch(report, state), ['SIMPLIFY', 'SPLIT'],
                             'listed first, the split comes after what it waits for')
            self.assertEqual(waves.with_prerequisites(report, state, ['SPLIT']), ['SIMPLIFY', 'SPLIT'],
                             'asked alone, it brings it')
            self.assertIsNone(waves.too_early(state, [card('SIMPLIFY'), card('SPLIT', ['SIMPLIFY'])]))

    def test_a_commit_says_what_changed_in_the_projects_language_cut_at_a_word(self):
        # a commit subject is cut at a word, not mid-word at 72 characters, is in the project's language, and has no
        # "Executed by EAOS" body
        root = repository()
        card = {'id': 'TASK-V001', 'title': 'زر القائمة الجانبية صغير جدًا على الجوال', 'pattern': 'design_review',
                'key': '0123456789ab'}
        said = lambda what: git(root, 'log', '-1', f'--format={what}')
        commit_file(root, 'a.txt', 'b\n')      # the change comes back below, as EAOS's commit
        git(root, 'reset', '-q', '--soft', 'HEAD~1')
        wave_batch.commit(root, card, 'Enlarge the sidebar toggle on phones\n\nIt is the only way to the menu there.')
        self.assertEqual(said('%s'), 'Enlarge the sidebar toggle on phones')
        self.assertIn('It is the only way to the menu there.', said('%b'))
        self.assertIn('EAOS-Card: 0123456789ab', said('%b'))
        self.assertIn('TASK-V001', said('%b'))
        self.assertNotIn('Executed by', said('%B'))
        title = 'Simplify the parser of the configuration files so that every assistant and engineer reads it at once'
        for name, text in (('b.txt', 'b'), ('c.txt', 'c')):
            (root / name).write_text(text)
            wave_batch.commit(root, {**card, 'title': title if name == 'b.txt' else card['title']})
            subject = said('%s')
            self.assertLessEqual(len(subject), 72)
            self.assertNotRegex(subject, '[\u0600-\u06ff]')
        self.assertTrue(title.startswith(git(root, 'log', '-1', '--skip=1', '--format=%s') + ' '))
        for subject in ('إصلاح صفحة الدخول', 'صفحة الطلبات'):
            git(root, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-q', '--allow-empty', '-m', subject)
        (root / 'd.txt').write_text('d')
        wave_batch.commit(root, card)
        self.assertEqual(said('%s'), card['title'], 'a repository whose own commits are Arabic')

    def test_the_branch_is_the_base_plus_exactly_the_kept_commits_and_the_card_at_fault_is_found_by_halving(self):
        root = repository()
        base = git(root, 'rev-parse', 'HEAD')
        one, two, three = (commit_file(root, f'{n}.txt', n) for n in ('one', 'two', 'three'))
        self.assertEqual(waves.rebuild(root, base, [one, three]), [])
        self.assertEqual(sorted(p.name for p in root.glob('*.txt')), ['a.txt', 'one.txt', 'three.txt'])
        commits = [f'c{n}' for n in range(8)]
        applied, regenerated = [], []
        batch = {'root': 'root', 'base': 'base', 'name': 'wave-1', 'say': lambda *a: None,
                 'regenerate': regenerated.append}
        with mock.patch.object(wave_batch, 'rebuild', side_effect=lambda root, base, part: applied.append(list(part))
                               or []), \
                mock.patch.object(wave_batch, 'gates', side_effect=lambda *a, **k: f'broken by {len(applied[-1])}'
                                  if 'c5' in applied[-1] else ''):
            found = waves.culprits(batch, commits)
        self.assertEqual(found, {'c5': 'broken by 1'}, "the culprit's own reason, not the batch's")
        self.assertLessEqual(len(applied), 6, 'halving, not trying every card alone')
        # a half is checked with the files its build makes, so a stale generated build does not fail every half alike
        self.assertEqual(len(regenerated), len(applied), 'each half is checked with the files its build makes')

    def test_skipping_a_kept_card_gives_the_others_their_new_commits_and_fails_one_that_no_longer_applies(self):
        root = repository()
        base = git(root, 'rev-parse', 'HEAD')
        one, two = commit_file(root, 'one.txt', 'one'), commit_file(root, 'b.txt', 'two\n')
        three = commit_file(root, 'b.txt', 'two\nthree\n')                  # stands on two's change
        wave = {'root': str(root), 'base': base, 'kept': {'T1': one, 'T2': two, 'T3': three}, 'failed': {}}
        waves.without(wave, 'T2')
        self.assertEqual((wave['kept'], wave['failed']),
                         ({'T1': git(root, 'rev-parse', 'HEAD')},
                          {'T3': 'its change no longer applies once T2 was skipped'}))


    def test_a_lock_that_installs_only_unfrozen_fails_the_gate(self):
        # A fallback to an unfrozen npm install must not pass the gate: a lock that npm ci refuses must fail it.
        from eaos.journeys.fix.execute import project_checks, regressions

        class Run:
            def __init__(self, *_, **__):
                self.profile, self.log = {'checks': [['npm', 'test']]}, []
                self.sandbox, self.commit = mock.Mock(copy=Path('copy')), 'HEAD'
            def setup(self):
                self.log += [{'argv': ['npm', 'ci', '--no-audit', '--no-fund'], 'exit': 1},
                             {'argv': ['npm', 'install', '--no-audit', '--no-fund'], 'exit': 0}]
            def run(self, argv, **_): return 0, '', ''
            def stop(self): pass
            def record(self, name): pass
        with mock.patch('eaos.live.app.run.LiveRun', Run):
            after = project_checks('copy', 'runtime', 'S09', 'edit', python=False)
        before = [{'argv': ['npm', 'ci', '--no-audit', '--no-fund'], 'exit': 0, 'failing': []},
                  {'argv': ['npm', 'test'], 'exit': 0, 'failing': []}]
        self.assertEqual(regressions(before, after), ['npm ci --no-audit --no-fund'])

    def test_a_check_runs_once_as_on_ci_not_watching(self):
        # `vitest` watches unless CI is set: a check runs once, as on CI, so the suite ends.
        from eaos.journeys.fix.execute import project_checks
        root = repository()

        class Run:
            def __init__(self, *_, **__):
                self.profile, self.log, self.commit = {'checks': [['yarn', 'test']]}, [], git(root, 'rev-parse', 'HEAD')
                self.sandbox = mock.Mock(copy=Path(scratch()))
            def setup(self): pass
            def run(self, argv, env=None, **_):
                return (0, '', '') if (env or {}).get('CI') else (1, '', 'stopped after 1800s')
            def stop(self): pass
            def record(self, name): pass
        with mock.patch('eaos.live.app.run.LiveRun', Run):
            self.assertEqual([row['exit'] for row in project_checks(root, 'runtime', 'S09', 'edit', python=False)], [0])

    def test_a_check_that_rewrites_the_files_is_named_and_is_no_gate(self):
        # A project's lint may reach `biome --write` and pass by fixing the files it checked; such a check rewrites
        # files and is no gate.
        from eaos.journeys.fix.execute import project_checks, regressions, rewrites
        root = repository()
        copy = Path(scratch()) / 'copy'
        copy.mkdir()
        (copy / 'a.txt').write_text('a\n')

        class Run:
            def __init__(self, *_, **__):
                self.profile, self.log, self.commit = {'checks': [['npm', 'run', 'lint'],
                                                                  ['npm', 'test']]}, [], git(root, 'rev-parse', 'HEAD')
                self.sandbox = mock.Mock(copy=copy)
            def setup(self): pass
            def run(self, argv, **_):
                if 'lint' in argv: (copy / 'a.txt').write_text('fixed\n')
                return 0, '', ''
            def stop(self): pass
            def record(self, name): pass
        with mock.patch('eaos.live.app.run.LiveRun', Run):
            after = project_checks(root, 'runtime', 'S09', 'edit', python=False)
        self.assertEqual([row.get('writes') for row in after], [['a.txt'], None])
        self.assertEqual((copy / 'a.txt').read_text(), 'a\n', 'the files it rewrote are restored for the next check')
        self.assertEqual(rewrites(after), ['npm run lint'])
        before = [{'argv': ['npm', 'run', 'lint'], 'exit': 0, 'failing': []}]
        self.assertEqual(regressions(before, [{**after[0], 'exit': 1}]), [], 'its exit is no gate')
        from eaos.journeys.fix import finish
        runtime = Path(scratch())
        (runtime / 'runtime').mkdir()
        (runtime / 'runtime/checks-original.json').write_text(json.dumps({'checks': after}))
        with mock.patch.object(finish.project_state, 'runtime_of', return_value=runtime):
            keys, words = finish._said_too({}, {})
        self.assertEqual(keys['checks_rewriting'], ['npm run lint'])
        self.assertIn('rewrite the files instead of checking them, so no fix was held to them: npm run lint.', words)

    def test_the_cards_put_off_are_counted_at_the_hand_over_and_said_in_the_persons_language(self):
        # The cards put off are said in the person's language, not in English.
        from eaos.ai.assistant import prompts
        from eaos.journeys.fix import finish
        wave = {'failed': {'T1': 'skipped: a large split', 'T2': 'skipped: an import loop', 'T3': 'it broke something'}}
        with mock.patch.object(finish.project_state, 'runtime_of', return_value=Path(scratch())):
            keys, words = finish._said_too({}, wave)
        self.assertEqual(keys['put_off'], 2)
        self.assertIn('2 cards were left out, grouped by why, in their language', words)
        self.assertIn("fix_skip's reason", prompts._written_in('ar'))

    def test_a_fix_that_raises_the_go_line_of_go_mod_says_so_in_its_commit_and_at_the_hand_over(self):
        # A Go module upgrade may raise go.mod's `go` line, so everyone building the project needs a newer Go: the
        # commit and the hand-over say it.
        from eaos.journeys.fix import finish
        root = repository()
        (root / 'svc').mkdir()
        base = commit_file(root, 'svc/go.mod',
                           'module example.com/svc\n\ngo 1.21\n\nrequire golang.org/x/net v0.10.0\n')
        (root / 'svc/go.mod').write_text('module example.com/svc\n\ngo 1.26\n\ntoolchain go1.26.1\n\n'
                                         'require golang.org/x/net v0.40.0\n')
        wave_batch.commit(root, {'id': 'TASK-007', 'title': 'Upgrade golang.org/x/net', 'key': 'k'},
                          'Upgrade golang.org/x/net to v0.40.0')
        body = git(root, 'log', '-1', '--format=%b')
        self.assertIn('svc/go.mod now needs Go 1.26 (was 1.21)', body)
        self.assertIn('svc/go.mod now needs the toolchain go1.26.1', body)
        runtime = Path(scratch())
        with mock.patch.object(finish.project_state, 'runtime_of', return_value=runtime):
            keys, words = finish._said_too({'project': str(root)}, {'base': base}, 'HEAD')
        self.assertEqual(keys['go_raised'],
                         ['svc/go.mod now needs Go 1.26 (was 1.21)', 'svc/go.mod now needs the toolchain go1.26.1'])
        self.assertIn('svc/go.mod now needs Go 1.26 (was 1.21)', words)
        (root / 'a.txt').write_text('c\n')
        wave_batch.commit(root, {'id': 'TASK-008', 'title': 'Change a', 'key': 'k2'})
        self.assertNotIn('go.mod', git(root, 'log', '-1', '--format=%b'),
                         'a change that leaves go.mod alone says nothing of it')

    def test_a_codemod_that_fails_says_why_in_its_own_words(self):
        # a failed upgrade records the command's own output, not only its command line
        import sys
        from eaos.journeys.fix.execute import run_codemod
        step = [sys.executable, '-c',
                "import sys; sys.stderr.write('npm error ERESOLVE could not resolve'); sys.exit(1)"]
        with mock.patch('eaos.analysis.repair.codemods.card_for', return_value={'kind': 'x'}), \
                mock.patch('eaos.analysis.repair.codemods._commands',
                           return_value=[(step, None)]), mock.patch('eaos.facts.store.by_id'):
            with self.assertRaisesRegex(RuntimeError, 'exited 1: npm error ERESOLVE could not resolve'):
                run_codemod({'id': 'T1'}, scratch(), scratch())

    def test_a_dependency_change_that_breaks_a_consumers_range_is_refused_at_its_commit(self):
        # an upgrade that puts a package out of the range a consumer asks for breaks the install; the dependency gate
        # must see it, not only the card's own gate
        from eaos.engines.process import which
        from eaos.journeys.fix.execute import _dependencies_broken
        need(self, '' if which('npm') else 'npm is not installed')
        lock = lambda b: json.dumps({'name': 'shop', 'version': '1.0.0', 'lockfileVersion': 3, 'requires': True,
                                     'packages': {
            '': {'name': 'shop', 'version': '1.0.0', 'dependencies': {'a': '1.0.0'}},
            'node_modules/a': {'version': '1.0.0', 'dependencies': {'b': '^1.0.0'}}, 'node_modules/b': {'version': b}}})
        root = repository()
        commit_file(root, 'package.json', '{"name": "shop", "version": "1.0.0", "dependencies": {"a": "1.0.0"}}')
        commit_file(root, 'package-lock.json', lock('1.0.0'))
        self.assertEqual(_dependencies_broken(root), [])
        commit_file(root, 'package-lock.json', lock('2.0.0'))
        self.assertEqual(_dependencies_broken(root),
                         ['the dependency tree is no longer valid: invalid: b@2.0.0 node_modules/b'])
        commit_file(root, 'b.txt', 'b')
        self.assertEqual(_dependencies_broken(root), [], 'a commit that changes no dependency is not read again')

    def test_a_lock_file_card_that_fails_whole_keeps_the_packages_that_pass_one_by_one(self):
        # a lock file card that fails whole may leave the dependency tree invalid through one package; the sound
        # upgrades are kept one by one
        self._lock_card_in_part({'files_changed': 1})

    def test_a_lock_file_card_whose_dry_run_failed_whole_is_tried_one_by_one(self):
        # a lock file card whose dry run failed whole (one package needing a newer Python) is tried package by package
        # instead of going to the assistant
        self._lock_card_in_part({'exit': 1, 'files_changed': 0})

    def _lock_card_in_part(self, dry_run):
        from eaos.engines.process import which
        from eaos.journeys.fix.automatic import automatic_fixes
        from eaos.journeys.fix.execute import _dependencies_broken
        need(self, '' if which('npm') else 'npm is not installed')
        root = repository()
        commit_file(root, 'package.json', '{"name": "shop", "version": "1.0.0", "dependencies": {"a": "1.0.0"}}')
        commit_file(root, 'package-lock.json',
                    json.dumps({'name': 'shop', 'version': '1.0.0', 'lockfileVersion': 3, 'requires': True,
                                'packages': {
            '': {'name': 'shop', 'version': '1.0.0', 'dependencies': {'a': '1.0.0'}},
            'node_modules/a': {'version': '1.0.0', 'dependencies': {'b': '^1.0.0', 'c': '^1.0.0'}},
            'node_modules/b': {'version': '1.0.0'}, 'node_modules/c': {'version': '1.0.0'}}}))

        def bump(member):
            def step():
                lock = json.loads((root / 'package-lock.json').read_text())
                lock['packages'][f"node_modules/{member['package']}"]['version'] = member['fixed']
                (root / 'package-lock.json').write_text(json.dumps(lock))
            return step, f"bump {member['package']}"
        members = [{'kind': 'npm', 'package': 'b', 'version': '1.0.0', 'fixed': '2.0.0'},
                   {'kind': 'npm', 'package': 'c', 'version': '1.0.0', 'fixed': '1.0.1'}]
        facts = {f'F-{m["package"]}': {'id': f'F-{m["package"]}', 'location': {'symbol': f'npm:{m["package"]}@1.0.0'},
                                       'value': {'measurements': [{'name': 'advisory_ids',
                                                                   'value': [f'GHSA-{m["package"]}']}]}}
                 for m in members}
        card = {'id': 'TASK-1', 'title': 'Upgrade the lock file', 'key': 'k1', 'evidence': {'fact_ids': list(facts)},
                'codemod': {'command': 'npm install', 'dry_run': dry_run}}
        wave = {'kept': {}, 'failed': {}, 'tools': {}}
        with mock.patch('eaos.analysis.repair.codemods.card_for', return_value={'kind': 'npm', 'group': members}), \
                mock.patch('eaos.analysis.repair.codemods._commands',
                           lambda detail, copy: [bump(m) for m in detail.get('group') or [detail]]), \
                mock.patch('eaos.facts.store.by_id', return_value=facts), \
                mock.patch('eaos.journeys.fix.automatic.new_breakage',
                           lambda report, where: _dependencies_broken(where)):
            automatic_fixes(wave, [card], root, scratch(), lambda *_: None)
        self.assertEqual((list(wave['kept']), wave['failed']), (['TASK-1'], {}))
        partial = wave['partial']['TASK-1']
        self.assertEqual(partial['left'],
                         {'b@1.0.0': 'the dependency tree is no longer valid: invalid: b@2.0.0 node_modules/b'})
        check = partial['verify_command'][-1]
        self.assertIn("'npm:c@': ['GHSA-c']", check)
        self.assertNotIn('npm:b@', check, 'the card claims only the package it moved')
        lock = json.loads(git(root, 'show', 'HEAD:package-lock.json'))['packages']
        self.assertEqual((lock['node_modules/b']['version'], lock['node_modules/c']['version']), ('1.0.0', '1.0.1'))
        self.assertEqual(git(root, 'rev-list', '--count', 'HEAD'), '4', 'one commit for the card')
        report = Path(scratch())
        (report / 'plan.json').write_text(json.dumps({'tasks': [{**card, 'verify_command': ['whole card check']}]}))
        held = waves.cards.wave_cards(report, {**wave, 'cards': ['TASK-1']})['TASK-1']['verify_command']
        self.assertEqual(held, partial['verify_command'], 'its acceptance is the packages it moved')


if __name__ == '__main__':
    unittest.main()
