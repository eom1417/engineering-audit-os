"""Fixes in waves: the expensive gates once per batch (eaos/journeys/fix/waves/ finish_batch, behind the MCP fix_finish), the card
at fault found by halving, and the result handed over as a branch that leaves the person's branch and files alone."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.journeys.fix import waves
from eaos.journeys.fix.waves import batch as wave_batch
from shared_fixture import scratch


def git(where, *args):
    return subprocess.run(['git', '-C', str(where), *args], capture_output=True, text=True, check=True).stdout.strip()


def repository():
    root = Path(scratch()) / 'shop'
    root.mkdir()
    (root / 'a.txt').write_text('a\n')
    git(root, 'init', '-q'); git(root, 'add', '-A')
    git(root, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'first')
    return root


def commit_file(root, name, text):
    (root / name).write_text(text)
    git(root, 'add', '-A'); git(root, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', name)
    return git(root, 'rev-parse', 'HEAD')


class OrderTests(unittest.TestCase):
    def test_a_batch_with_a_design_card_may_change_any_screens_look_but_not_its_errors(self):
        # EAOS, 2026-10-15: a design card's shared change showed on pages its finding never named; each run found one more
        from eaos.live.behavior.lock import _declared
        self.assertEqual(waves.declared_screens([{'design': {'findings': [{'page': '/library'}]}}, {}]), {'*'})
        self.assertEqual(waves.declared_screens([{'id': 'TASK-1'}]), set(), 'a batch of code changes keeps every screen locked')
        shot = 'expect(page).toHaveScreenshot(expected) failed\n  Snapshot: change-ideal.png'
        self.assertEqual(_declared('failed', shot, {'*'}), 'passed')
        self.assertEqual(_declared('failed', 'console: TypeError: x is undefined', {'*'}), 'failed', 'a page error still breaks it')
        self.assertEqual(_declared('failed', shot, set()), 'failed')

    def test_a_failure_that_names_a_file_finds_its_culprit_in_one_run_and_a_change_is_sized_against_the_copy(self):
        # EAOS, 2026-10-15: halving 68 changes ran the whole suite for hours though the failure named the one file; a
        # repair was refused for growing an 876-line file that the check on record knew at 861
        root = Path(scratch())
        run = lambda *a: subprocess.run(['git', '-C', str(root), '-c', 'user.name=t', '-c', 'user.email=t@t', *a], check=True,
                                        capture_output=True, text=True).stdout.strip()
        run('init', '-q')
        (root / 'a.py').write_text('x = 1\n'); (root / 'b.py').write_text('y = 1\n')
        run('add', '-A'); run('commit', '-qm', 'base'); base = run('rev-parse', 'HEAD')
        commits = []
        for name in ('a.py', 'b.py'):
            (root / name).write_text('z = 2\n'); run('commit', '-qam', name); commits.append(run('rev-parse', 'HEAD'))
        batch = {'name': 'w', 'runtime': root, 'root': root, 'base': base, 'say': lambda *_: None, 'regenerate': lambda r: None}
        said = [{'command': 'tests', 'output': 'FAIL: test_x ... a.py::f: 16 (allowed 15)'}]
        with mock.patch.object(wave_batch, 'failing_output', return_value=said), mock.patch.object(wave_batch, 'gates', return_value='') as gates:
            self.assertEqual(list(wave_batch._named(batch, commits)), [commits[0]])
        self.assertEqual(gates.call_count, 1, 'one run of the checks, not a halving')
        self.assertEqual(wave_batch._sizes_before(root, ['b.py', 'c.py']), {'b.py': 2}, 'counted as facts/metrics counts lines')

    def test_a_card_whose_change_brings_a_finding_of_the_slower_security_engine_is_left_out_of_the_batch(self):
        # M7.5: bandit and gitleaks read every change; semgrep (the browser's innerHTML, a shell built from strings) only
        # read the batch's commit once it was merged, by the next check
        root = repository()
        base = git(root, 'rev-parse', 'HEAD')
        sound, unsafe = commit_file(root, 'b.txt', 'b\n'), commit_file(root, 'page.js', 'el.innerHTML = name\n')
        batch = {'root': root, 'base': base, 'report': root, 'say': lambda *_: None, 'regenerate': lambda r: None}
        failed = {}
        found = [('semgrep', 'insecure-innerhtml', 'page.js')]
        with mock.patch('eaos.facts.run.collect'), mock.patch('eaos.analysis.assessments.weaknesses.new', return_value=found):
            kept = wave_batch._secure(batch, {'T1': sound, 'T2': unsafe}, failed, [])
        self.assertEqual(list(kept), ['T1'])
        self.assertIn('insecure-innerhtml (semgrep) in page.js', failed['T2'])
        self.assertEqual(batch['security']['engines'], ['semgrep'], "the batch's record says what read it")
        self.assertFalse((root / 'page.js').exists(), 'the copy is rebuilt without it')

    def test_a_batch_is_the_next_ready_cards_in_milestone_order_and_judged_from_one_collection_of_facts(self):
        report = Path(scratch())
        ready = lambda i: {'id': i, 'kind': 'remediate', 'decision': {'readiness': 'ready'}}
        (report / 'plan.json').write_text(json.dumps({'tasks': [ready('T1'), ready('T2'), ready('T3'),
                                                                {'id': 'T4', 'kind': 'investigate', 'decision': {'readiness': 'blocked'}}],
                                                      'milestones': [{'tasks': ['T3', 'T4']}, {'tasks': ['T1', 'T2']}]}))
        self.assertEqual(waves.next_batch(report, {}, size=2), ['T3', 'T1'])
        tried = [c['key'] for c in waves.plan(report)['tasks'] if c['id'] == 'T3']     # `tried` holds keys, not ids
        self.assertEqual(waves.next_batch(report, {'tried': tried}, size=5), ['T1', 'T2'])
        dead_card = {'id': 'D', 'verify_command': ['python', '-c', "left = [f for f in facts if (f['location']['path'], "
                                                   "f['location']['symbol'], f['value']['rule']) == ('src/a.ts', 'gone', 'unused-symbol')]"]}
        gone_card = {'id': 'G', 'verify_command': ['python', '-c', "x == ('src/a.ts', 'still', 'unused-symbol')"]}
        probe_card = {'id': 'P', 'verify_command': ['eaos', 'recheck', '--spec', json.dumps({'probe_type': 'graph_query', 'specification': {'query': 'q'}}), '.']}
        sets = {'deadcode': {'facts': [{'location': {'path': 'src/a.ts', 'symbol': 'still'}, 'value': {'rule': 'unused-symbol'}}]}}
        with mock.patch('eaos.facts.run.collect') as collect, mock.patch('eaos.facts.run.read_available', return_value=sets), \
                mock.patch('eaos.analysis.claims.probes.decide_probe', return_value=('REFUTED', 'gone')):
            exits = wave_batch.batch_acceptance(scratch(), [dead_card, gone_card, probe_card], scratch())
        self.assertEqual(collect.call_count, 1)
        self.assertEqual(exits, {'D': 0, 'G': 1, 'P': 0})

    def test_repository_craft_never_goes_in_a_fix_batch(self):
        # five real projects: an assistant fixed "no map for extending" inside a fix batch, writing the guide and CLAUDE.md there
        report = Path(scratch())
        card = lambda i, pattern: {'id': i, 'kind': 'remediate', 'pattern': pattern, 'decision': {'readiness': 'ready'}}
        (report / 'plan.json').write_text(json.dumps({'tasks': [card('CRAFT', 'repository_craft'), card('FIX', 'duplication')], 'milestones': []}))
        self.assertEqual(waves.next_batch(report, {}), ['FIX'])
        self.assertEqual(waves.kept_apart([card('CRAFT', 'repository_craft'), card('FIX', 'duplication')])['own_batch'], ['CRAFT'])
        self.assertIsNone(waves.kept_apart([card('FIX', 'duplication')]))

    def test_a_layer_card_is_judged_by_the_layers_read_again_on_the_copy(self):
        # Trial on real projects (2026-11-02): every layer card of a batch exited 2, "the boundaries facts are not present"
        spec = {'probe_type': 'graph_query', 'specification': {'query': 'boundary_finding_present', 'rule': 'ui-database',
                                                               'path': 'web/Orders.jsx', 'params': {}}}
        card = {'id': 'L', 'verify_command': ['eaos', 'recheck', '--spec', json.dumps(spec), '.']}
        shown = {'location': {'path': 'web/Orders.jsx'}, 'value': {'rule': 'ui-database', 'params': {}}}
        for facts, exit in (([], 0), ([shown], 1)):
            with mock.patch('eaos.facts.run.collect'), mock.patch('eaos.facts.run.read_available', return_value={}), \
                    mock.patch('eaos.analysis.layers.check'), mock.patch('eaos.analysis.layers.facts_of', return_value=facts):
                self.assertEqual(wave_batch.batch_acceptance(scratch(), [card], scratch()), {'L': exit})

    def test_a_failing_tests_card_passes_only_when_its_command_passes_on_the_copy(self):
        # Trial on real projects (2026-11-02): a failing-tests card's recheck read the code alone and would call it gone
        spec = {'probe_type': 'graph_query', 'specification': {'query': 'boundary_finding_present', 'rule': 'tests-failing',
                                                               'path': '*', 'params': {'failed': 3, 'total': 40, 'command': 'npm run test'}}}
        card = {'id': 'T', 'verify_command': ['eaos', 'recheck', '--spec', json.dumps(spec), '.']}
        for code, runtime, exit in ((0, 'runtime', 0), (1, 'runtime', 1), (127, 'runtime', 2), (0, None, 2)):
            rows = [{'argv': ['npm', 'run', 'lint'], 'exit': 0, 'failing': []}, {'argv': ['npm', 'run', 'test'], 'exit': code, 'failing': []}]
            with mock.patch('eaos.facts.run.collect'), mock.patch('eaos.facts.run.read_available', return_value={}), \
                    mock.patch('eaos.journeys.fix.execute.project_checks', return_value=rows):
                self.assertEqual(wave_batch.batch_acceptance(scratch(), [card], scratch(), runtime=runtime), {'T': exit}, (code, runtime))

class RebuildTests(unittest.TestCase):
    def test_a_module_is_split_only_after_its_complex_functions_and_a_split_tried_too_early_comes_back(self):
        # EAOS, 2026-10-15: five module splits went into batches before their simplifications, failed, never came back
        from eaos.core.project import ledger
        report = Path(scratch())
        card = lambda i, needs=(): {'id': i, 'kind': 'remediate', 'decision': {'readiness': 'ready'},
                                    'prerequisites': [{'task_id': n} for n in needs]}
        (report / 'plan.json').write_text(json.dumps({'tasks': [card('SPLIT', ['SIMPLIFY']), card('SIMPLIFY')], 'milestones': []}))
        keys = {c['id']: c['key'] for c in waves.plan(report)['tasks']}
        book = {keys['SPLIT']: {'id': 'SPLIT', 'state': 'skipped', 'batch': 1}, keys['SIMPLIFY']: {'id': 'SIMPLIFY', 'state': 'open'}}
        state = {'project': 'p', 'tried': [keys['SPLIT']]}
        with mock.patch.object(ledger, 'load', return_value={'cards': book}):
            self.assertEqual(waves.next_batch(report, state), ['SIMPLIFY'], 'the split waits for the simplification')
            self.assertEqual(waves.too_early(state, [card('SPLIT', ['SIMPLIFY'])])['waits'], {'SPLIT': ['SIMPLIFY']})
            book[keys['SIMPLIFY']].update(state='done', batch=2)
            ledger._reopen_waited({c['id']: c for c in book.values()}, [card('SPLIT', ['SIMPLIFY'])])
            self.assertEqual(book[keys['SPLIT']]['state'], 'open', 'set aside by the order, not by its own change')
            self.assertEqual(waves.next_batch(report, state), ['SPLIT'], 'tried, but opened again by the ledger')
        # a full-stack app: ten splits left for "the next batch" while their simplifications were open: now in the same batch, after
        book[keys['SIMPLIFY']].update(state='open', batch=None)
        with mock.patch.object(ledger, 'load', return_value={'cards': book}):
            self.assertEqual(waves.next_batch(report, state), ['SIMPLIFY', 'SPLIT'], 'listed first, the split comes after what it waits for')
            self.assertEqual(waves.with_prerequisites(report, state, ['SPLIT']), ['SIMPLIFY', 'SPLIT'], 'asked alone, it brings it')
            self.assertIsNone(waves.too_early(state, [card('SIMPLIFY'), card('SPLIT', ['SIMPLIFY'])]))

    def test_a_commit_says_what_changed_in_the_projects_language_cut_at_a_word(self):
        # five real projects: subjects cut mid-word at 72, Arabic subjects in English repositories, "Executed by EAOS" bodies
        root = repository()
        card = {'id': 'TASK-V001', 'title': 'زر القائمة الجانبية صغير جدًا على الجوال', 'pattern': 'design_review', 'key': '0123456789ab'}
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
        batch = {'root': 'root', 'base': 'base', 'name': 'wave-1', 'say': lambda *a: None, 'regenerate': regenerated.append}
        with mock.patch.object(wave_batch, 'rebuild', side_effect=lambda root, base, part: applied.append(list(part)) or []), \
                mock.patch.object(wave_batch, 'gates', side_effect=lambda *a, **k: f'broken by {len(applied[-1])}' if 'c5' in applied[-1] else ''):
            found = waves.culprits(batch, commits)
        self.assertEqual(found, {'c5': 'broken by 1'}, "the culprit's own reason, not the batch's")
        self.assertLessEqual(len(applied), 6, 'halving, not trying every card alone')
        # Wave 4 on EAOS (2026-10-13): without the Studio rebuilt, every half failed alike, 56 runs over three hours
        self.assertEqual(len(regenerated), len(applied), 'each half is checked with the files its build makes')

    def test_skipping_a_kept_card_gives_the_others_their_new_commits_and_fails_one_that_no_longer_applies(self):
        root = repository()
        base = git(root, 'rev-parse', 'HEAD')
        one, two = commit_file(root, 'one.txt', 'one'), commit_file(root, 'b.txt', 'two\n')
        three = commit_file(root, 'b.txt', 'two\nthree\n')                  # stands on two's change
        wave = {'root': str(root), 'base': base, 'kept': {'T1': one, 'T2': two, 'T3': three}, 'failed': {}}
        waves.without(wave, 'T2')
        self.assertEqual((wave['kept'], wave['failed']),
                         ({'T1': git(root, 'rev-parse', 'HEAD')}, {'T3': 'its change no longer applies once T2 was skipped'}))


    def test_a_lock_that_installs_only_unfrozen_fails_the_gate(self):
        # Trial on real projects (2026-11-02): a dependency card left a lock npm ci refused; the gate's npm install fallback
        # passed, the checks ran green, and the broken lock went into the delivered branch
        from eaos.journeys.fix.execute import project_checks, regressions

        class Run:
            def __init__(self, *_, **__):
                self.profile, self.log = {'checks': [['npm', 'test']]}, []
                self.sandbox, self.commit = mock.Mock(copy=Path('copy')), 'HEAD'
            def setup(self):
                self.log += [{'argv': ['npm', 'ci', '--no-audit', '--no-fund'], 'exit': 1}, {'argv': ['npm', 'install', '--no-audit', '--no-fund'], 'exit': 0}]
            def run(self, argv, **_): return 0, '', ''
            def stop(self): pass
            def record(self, name): pass
        with mock.patch('eaos.live.app.run.LiveRun', Run):
            after = project_checks('copy', 'runtime', 'S09', 'edit', python=False)
        before = [{'argv': ['npm', 'ci', '--no-audit', '--no-fund'], 'exit': 0, 'failing': []}, {'argv': ['npm', 'test'], 'exit': 0, 'failing': []}]
        self.assertEqual(regressions(before, after), ['npm ci --no-audit --no-fund'])

    def test_a_check_that_rewrites_the_files_is_named_and_is_no_gate(self):
        # Trial on real projects: a project's lint reached `biome --write` and always passed by fixing the files it checked
        from eaos.journeys.fix.execute import project_checks, regressions, rewrites
        root = repository()
        copy = Path(scratch()) / 'copy'
        copy.mkdir()
        (copy / 'a.txt').write_text('a\n')

        class Run:
            def __init__(self, *_, **__):
                self.profile, self.log, self.commit = {'checks': [['npm', 'run', 'lint'], ['npm', 'test']]}, [], git(root, 'rev-parse', 'HEAD')
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

    def test_a_fix_that_raises_the_go_line_of_go_mod_says_so_in_its_commit_and_at_the_hand_over(self):
        # Second trial on real projects: a Go module upgrade raised go.mod's `go` line, so everyone building the
        # project needs a newer Go, and neither the commit nor the hand-over said it.
        from eaos.journeys.fix import finish
        root = repository()
        (root / 'svc').mkdir()
        base = commit_file(root, 'svc/go.mod', 'module example.com/svc\n\ngo 1.21\n\nrequire golang.org/x/net v0.10.0\n')
        (root / 'svc/go.mod').write_text('module example.com/svc\n\ngo 1.26\n\ntoolchain go1.26.1\n\nrequire golang.org/x/net v0.40.0\n')
        wave_batch.commit(root, {'id': 'TASK-007', 'title': 'Upgrade golang.org/x/net', 'key': 'k'}, 'Upgrade golang.org/x/net to v0.40.0')
        body = git(root, 'log', '-1', '--format=%b')
        self.assertIn('svc/go.mod now needs Go 1.26 (was 1.21)', body)
        self.assertIn('svc/go.mod now needs the toolchain go1.26.1', body)
        runtime = Path(scratch())
        with mock.patch.object(finish.project_state, 'runtime_of', return_value=runtime):
            keys, words = finish._said_too({'project': str(root)}, {'base': base}, 'HEAD')
        self.assertEqual(keys['go_raised'], ['svc/go.mod now needs Go 1.26 (was 1.21)', 'svc/go.mod now needs the toolchain go1.26.1'])
        self.assertIn('svc/go.mod now needs Go 1.26 (was 1.21)', words)
        (root / 'a.txt').write_text('c\n')
        wave_batch.commit(root, {'id': 'TASK-008', 'title': 'Change a', 'key': 'k2'})
        self.assertNotIn('go.mod', git(root, 'log', '-1', '--format=%b'), 'a change that leaves go.mod alone says nothing of it')

    def test_a_codemod_that_fails_says_why_in_its_own_words(self):
        # Trial on real projects (2026-11-02): eight dependency upgrades failed, each recorded as its command line only
        import sys
        from eaos.journeys.fix.execute import run_codemod
        step = [sys.executable, '-c', "import sys; sys.stderr.write('npm error ERESOLVE could not resolve'); sys.exit(1)"]
        with mock.patch('eaos.analysis.repair.codemods.card_for', return_value={'kind': 'x'}), \
                mock.patch('eaos.analysis.repair.codemods._commands', return_value=[(step, None)]), mock.patch('eaos.facts.store.by_id'):
            with self.assertRaisesRegex(RuntimeError, 'exited 1: npm error ERESOLVE could not resolve'):
                run_codemod({'id': 'T1'}, scratch(), scratch())

    def test_a_dependency_change_that_breaks_a_consumers_range_is_refused_at_its_commit(self):
        # Trial on real projects (2026-11-02): an upgrade put esbuild out of the range a build plugin asks; its own gate saw
        # nothing, the install broke, and eight later upgrades failed on it
        from eaos.engines.process import which
        from eaos.journeys.fix.execute import _dependencies_broken
        if not which('npm'): self.skipTest('npm is not installed')
        lock = lambda b: json.dumps({'name': 'shop', 'version': '1.0.0', 'lockfileVersion': 3, 'requires': True, 'packages': {
            '': {'name': 'shop', 'version': '1.0.0', 'dependencies': {'a': '1.0.0'}},
            'node_modules/a': {'version': '1.0.0', 'dependencies': {'b': '^1.0.0'}}, 'node_modules/b': {'version': b}}})
        root = repository()
        commit_file(root, 'package.json', '{"name": "shop", "version": "1.0.0", "dependencies": {"a": "1.0.0"}}')
        commit_file(root, 'package-lock.json', lock('1.0.0'))
        self.assertEqual(_dependencies_broken(root), [])
        commit_file(root, 'package-lock.json', lock('2.0.0'))
        self.assertEqual(_dependencies_broken(root), ['the dependency tree is no longer valid: invalid: b@2.0.0 node_modules/b'])
        commit_file(root, 'b.txt', 'b')
        self.assertEqual(_dependencies_broken(root), [], 'a commit that changes no dependency is not read again')

    def test_a_lock_file_card_that_fails_whole_keeps_the_packages_that_pass_one_by_one(self):
        # Second trial on real projects: a lock file card of 32 packages left the dependency tree invalid through one of
        # them, and the 31 sound upgrades were lost with it
        from eaos.engines.process import which
        from eaos.journeys.fix.automatic import automatic_fixes
        from eaos.journeys.fix.execute import _dependencies_broken
        if not which('npm'): self.skipTest('npm is not installed')
        root = repository()
        commit_file(root, 'package.json', '{"name": "shop", "version": "1.0.0", "dependencies": {"a": "1.0.0"}}')
        commit_file(root, 'package-lock.json', json.dumps({'name': 'shop', 'version': '1.0.0', 'lockfileVersion': 3, 'requires': True, 'packages': {
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
                                       'value': {'measurements': [{'name': 'advisory_ids', 'value': [f'GHSA-{m["package"]}']}]}}
                 for m in members}
        card = {'id': 'TASK-1', 'title': 'Upgrade the lock file', 'key': 'k1', 'evidence': {'fact_ids': list(facts)},
                'codemod': {'command': 'npm install', 'dry_run': {'files_changed': 1}}}
        wave = {'kept': {}, 'failed': {}, 'tools': {}}
        with mock.patch('eaos.analysis.repair.codemods.card_for', return_value={'kind': 'npm', 'group': members}), \
                mock.patch('eaos.analysis.repair.codemods._commands', lambda detail, copy: [bump(m) for m in detail.get('group') or [detail]]), \
                mock.patch('eaos.facts.store.by_id', return_value=facts), \
                mock.patch('eaos.journeys.fix.automatic.new_breakage', lambda report, where: _dependencies_broken(where)):
            automatic_fixes(wave, [card], root, scratch(), lambda *_: None)
        self.assertEqual((list(wave['kept']), wave['failed']), (['TASK-1'], {}))
        partial = wave['partial']['TASK-1']
        self.assertEqual(partial['left'], {'b@1.0.0': 'the dependency tree is no longer valid: invalid: b@2.0.0 node_modules/b'})
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

class HandOverTests(unittest.TestCase):
    def test_the_branch_arrives_without_touching_the_current_branch_or_unsaved_edits(self):
        project = repository()
        clone = Path(scratch()) / 'candidate'
        subprocess.run(['git', 'clone', '-q', str(project), str(clone)], check=True)
        git(clone, 'checkout', '-q', '-b', 'eaos/wave-1')
        commit_file(clone, 'fixed.txt', 'fixed')
        (project / 'a.txt').write_text('an unsaved edit\n')
        branch = waves.apply(project, {'kept': ['T1'], 'branch': 'eaos/wave-1', 'root': str(clone)})
        self.assertEqual(branch, 'eaos/wave-1')
        self.assertEqual(git(project, 'branch', '--show-current'), git(project, 'rev-parse', '--abbrev-ref', 'HEAD'))
        self.assertNotEqual(git(project, 'branch', '--show-current'), 'eaos/wave-1')
        self.assertEqual((project / 'a.txt').read_text(), 'an unsaved edit\n')
        self.assertFalse((project / 'fixed.txt').exists())
        self.assertEqual(waves.undo(project, 'eaos/wave-1'), 'deleted')
        self.assertEqual(waves.undo(project, 'eaos/wave-1'), 'absent')
        git(project, 'branch', 'eaos/wave-1')
        self.assertEqual(waves.undo(project, 'eaos/wave-1'), 'merged', 'a merged wave is not undone behind the person\'s back')
        with self.assertRaises(ValueError, msg='a wave that kept nothing hands nothing over'):
            waves.apply(project, {'kept': [], 'branch': 'eaos/wave-1', 'root': '/nowhere'})

    def test_a_closing_save_removes_the_closed_batchs_copy_and_one_still_opening_stays(self):
        with tempfile.TemporaryDirectory() as runtime:
            copies = Path(runtime) / 'candidates'
            for name in ('WAVE-1', 'BUILD-2', 'WAVE-3'): (copies / name).mkdir(parents=True)
            logs = Path(runtime) / 'runtime'
            logs.mkdir()
            for name in ('wave-1', 'wave-1-bisect-ab12cd34-2', 'wave-3-bisect-ab12cd34-2'): (logs / f'checks-{name}-log.json').write_text('{}')
            waves.saved({'waves': [{'number': 1}, {'number': 2, 'via': 'build'}]}, runtime, {'waves': [], 'open_wave': {'number': 1}, 'open_build': {'number': 2}})
            self.assertEqual([p.name for p in copies.iterdir()], ['WAVE-3'])
            self.assertEqual(sorted(p.name for p in logs.iterdir()), ['checks-wave-1-log.json', 'checks-wave-3-bisect-ab12cd34-2-log.json'],
                             "a closed batch keeps its gates' summary, not its bisection's logs")


def wave(root, base, kept):
    """The open batch as batch_finish keeps it: number 1, every kept card, none failed."""
    return {'number': 1, 'root': root, 'base': base, 'cards': list(kept), 'kept': kept, 'failed': {}, 'tools': {}}


class FinishTests(unittest.TestCase):
    def test_a_card_that_breaks_the_gates_is_taken_back_and_the_others_stay(self):
        project, runtime, report = repository(), Path(scratch()), Path(scratch())
        cards = [{'id': f'T{n}', 'title': f't{n}', 'kind': 'remediate', 'decision': {'readiness': 'ready'}, 'paths': [f'{n}.txt'],
                  'verify_command': ['true']} for n in (1, 2, 3, 4)]
        (report / 'plan.json').write_text(json.dumps({'tasks': cards}))
        root = Path(scratch()) / 'candidate'
        subprocess.run(['git', 'clone', '-q', str(project), str(root)], check=True)
        base = git(root, 'rev-parse', 'HEAD')
        kept = {card['id']: commit_file(root, card['paths'][0], card['id']) for card in cards}
        broken = lambda batch, name: 'the project\'s own check failed: test' if (Path(batch['root']) / '2.txt').exists() else ''
        with mock.patch.object(wave_batch, 'batch_acceptance', side_effect=lambda report, cards, root, **_: {c['id']: 0 for c in cards}
                               | {'T4': 1}), \
                mock.patch.object(wave_batch, 'original_checks', return_value=['test']), mock.patch.object(wave_batch, 'gates', side_effect=broken), \
                mock.patch.object(wave_batch, '_against_control', return_value=False):
            summary = waves.finish_batch(report, project, runtime, wave(root, base, kept), lock=False)
        self.assertEqual(summary['kept'], ['T1', 'T3'])
        self.assertIn("own check failed", summary['failed']['T2'])
        self.assertIn('acceptance exited 1', summary['failed']['T4'])
        self.assertEqual(sorted(p.name for p in root.glob('*.txt')), ['1.txt', '3.txt', 'a.txt'])
        rows = {r['id']: (r['status'], r['tool']) for r in json.loads((runtime / 'runtime/execution.json').read_text())['tasks']}
        self.assertEqual(rows, {'T1': ('VERIFIED_IN_ISOLATED_COPY', 'assistant'), 'T2': ('FAILED', 'assistant'),
                                'T3': ('VERIFIED_IN_ISOLATED_COPY', 'assistant'), 'T4': ('FAILED', 'assistant')},
                         'a card the assistant fixed is recorded like any other')
        self.assertEqual(len(list((runtime / 'waves/wave-1').glob('*.patch'))), 2)
        self.assertEqual(json.loads((runtime / 'waves/wave-1/wave.json').read_text())['branch'], 'eaos/wave-1')

    def test_changes_that_fail_only_together_are_repaired_on_top_and_no_sound_card_is_left_out(self):
        # Wave 2 on EAOS (2026-10-13): 45 cards passed one by one; together, a split module's parts imported each other.
        # Halving would have left about 20 sound cards out; a repair on top kept all of them.
        project, runtime, report = repository(), Path(scratch()), Path(scratch())
        cards = [{'id': f'T{n}', 'title': f't{n}', 'kind': 'remediate', 'decision': {'readiness': 'ready'}, 'paths': [f'{n}.txt'],
                  'verify_command': ['true']} for n in (1, 2)]
        (report / 'plan.json').write_text(json.dumps({'tasks': cards}))
        root = Path(scratch()) / 'candidate'
        subprocess.run(['git', 'clone', '-q', str(project), str(root)], check=True)
        base = git(root, 'rev-parse', 'HEAD')
        kept = {card['id']: commit_file(root, card['paths'][0], card['id']) for card in cards}
        together = lambda batch, name: ('' if (Path(batch['root']) / 'repair.txt').exists() or not (Path(batch['root']) / '2.txt').exists()
                                                else "the project's own check failed: a cycle")
        finish = lambda repairs, bisect: waves.finish_batch(report, project, runtime, wave(root, base, kept),
                                                           lock=False, repairs=repairs, bisect=bisect)
        with mock.patch.object(wave_batch, 'batch_acceptance', side_effect=lambda report, cards, root, **_: {c['id']: 0 for c in cards}), \
                mock.patch.object(wave_batch, 'original_checks', return_value=['test']), mock.patch.object(wave_batch, 'gates', side_effect=together), \
                mock.patch.object(wave_batch, '_against_control', return_value=False):
            with self.assertRaises(waves.GatesFailed) as asked:
                finish([], bisect=False)
            self.assertIn('a cycle', asked.exception.why)
            repair = commit_file(root, 'repair.txt', 'repair')
            summary = finish([repair], bisect=False)
        self.assertEqual((summary['kept'], summary['failed']), (['T1', 'T2'], {}))
        self.assertEqual(sorted(p.name for p in root.glob('*.txt')), ['1.txt', '2.txt', 'a.txt', 'repair.txt'])

    def test_what_fails_on_the_base_too_is_set_aside_and_the_batch_is_kept_whole(self):
        # Wave 4 on EAOS (2026-10-14): the Studio page of the problems read live data the batch itself rewrote, so it
        # differed with every card alone and with none; all 31 sound fixes were left out for it.
        project, runtime, report = repository(), Path(scratch()), Path(scratch())
        cards = [{'id': f'T{n}', 'title': f't{n}', 'kind': 'remediate', 'decision': {'readiness': 'ready'}, 'paths': [f'{n}.txt'],
                  'verify_command': ['true']} for n in (1, 2)]
        (report / 'plan.json').write_text(json.dumps({'tasks': cards}))
        root = Path(scratch()) / 'candidate'
        subprocess.run(['git', 'clone', '-q', str(project), str(root)], check=True)
        base = git(root, 'rev-parse', 'HEAD')
        kept = {card['id']: commit_file(root, card['paths'][0], card['id']) for card in cards}
        live_page = lambda batch, name: '' if 'problems' in (batch.get('known') or ()) else 'the behaviour lock broke on 1 of 2 specs'
        with mock.patch.object(wave_batch, 'batch_acceptance', side_effect=lambda report, cards, root, **_: {c['id']: 0 for c in cards}), \
                mock.patch.object(wave_batch, 'original_checks', return_value=[]), mock.patch.object(wave_batch, 'gates', side_effect=live_page), \
                mock.patch('eaos.live.behavior.lock.verify_lock') as control, \
                mock.patch('eaos.live.behavior.lock.failing_tests', return_value={'problems'}):
            summary = waves.finish_batch(report, project, runtime, wave(root, base, kept), lock=True)
        self.assertEqual((summary['kept'], summary['failed']), (['T1', 'T2'], {}))
        self.assertEqual(control.call_args.args[3].name, 'wave-1-control', 'checked once on the base alone')
        self.assertEqual(sorted(p.name for p in root.glob('*.txt')), ['1.txt', '2.txt', 'a.txt'], 'and the batch back whole after it')


class RegenerateTests(unittest.TestCase):
    def test_what_the_build_makes_from_the_batchs_source_comes_back_as_one_commit_and_nothing_ignored(self):
        # EAOS on itself (2026-10-13): Studio fixes changed studio/src, the shipped build in eaos/data/studio no longer
        # matched it, and four sound fixes were about to be left out of the batch for it.
        from eaos.journeys.fix import regenerate
        root, runtime = repository(), Path(scratch())
        (root / 'app').mkdir(); (root / 'shipped').mkdir()
        commit_file(root, 'app/src.ts', 'one')
        commit_file(root, 'shipped/old.js', 'old')
        base = git(root, 'rev-parse', 'HEAD')
        (root / '.gitignore').write_text('app/dist/\n')
        commit_file(root, 'app/src.ts', 'two')
        copy = Path(scratch()) / 'project'
        subprocess.run(['git', '-C', str(root), 'worktree', 'add', '-q', '--detach', str(copy)], check=True)

        class Built:                                       # the build: one shipped file made, one gone, one ignored
            sandbox = mock.Mock(copy=copy)
            def __init__(self, *args, **kwargs): pass
            def setup(self):
                (copy / 'shipped/old.js').unlink()
                (copy / 'shipped/new.js').write_text('built from two')
                (copy / 'app/dist').mkdir(parents=True)
                (copy / 'app/dist/out.js').write_text('local only')
            def stop(self): pass
            def record(self, name): pass
        profile = {'app': 'app', 'build': [['npm', 'run', 'build']]}
        with mock.patch.object(regenerate, 'LiveRun', Built), mock.patch.object(regenerate, 'load_profile', return_value=profile):
            sha = regenerate.regenerate(root, runtime, base, 3)
        self.assertEqual(sorted(git(root, 'show', '--name-only', '--format=', sha).split()), ['shipped/new.js', 'shipped/old.js'])
        self.assertEqual(((root / 'shipped/new.js').read_text(), (root / 'shipped/old.js').exists()), ('built from two', False))
        with mock.patch.object(regenerate, 'load_profile', return_value=profile):
            self.assertIsNone(regenerate.regenerate(root, runtime, git(root, 'rev-parse', 'HEAD'), 4), 'the app did not change')


class CodeLawsGateTests(unittest.TestCase):
    def test_a_change_that_copies_leaves_dead_code_or_adds_complexity_is_refused_and_a_partial_split_is_kept(self):
        from eaos.analysis.repair.gates import debt, words
        new_debt = lambda before, after, paths: words(debt(before, after, paths))

        def facts(folder, functions, clones=(), dead=()):
            (Path(folder) / 'facts').mkdir(parents=True)
            metrics = [{'kind': 'metric', 'location': {'path': path, 'symbol': name}, 'value': {'scope': scope, 'branches': n}}
                       for path, name, n, scope in (row + ('function',) * (4 - len(row)) for row in functions)]
            metrics += [{'kind': 'clone_cluster', 'input_sha': key, 'value': {'occurrences': [{'path': 'a.py'}, {'path': 'b.py'}]}}
                        for key in clones]
            dead_facts = [{'location': {'path': 'a.py', 'symbol': name}, 'value': {'rule': 'unused-function'}} for name in dead]
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
        # EAOS, batch 5 (2026-10-14): a new module in no layer of eaos.policy.json and modules grown past their limit were
        # found only when the 51 changes met, by the project's own suite
        from eaos.analysis.repair import gates

        def lines(folder, sizes):
            (Path(folder) / 'facts').mkdir(parents=True, exist_ok=True)
            rows = [{'kind': 'metric', 'location': {'path': path}, 'value': {'scope': 'file', 'lines': n}} for path, n in sizes.items()]
            (Path(folder) / 'facts/metrics.json').write_text(json.dumps({'facts': rows}))
            return folder

        before, after = lines(scratch(), {'big.py': 700, 'a.py': 100}), lines(scratch(), {'big.py': 650, 'a.py': 640})
        self.assertEqual(gates.words(gates.debt(before, after, ['big.py', 'a.py'])), ['a.py grew to 640 lines, past the limit of 600: split it'])
        for folder, files in ((before, ['eaos/a.py', 'old.py']), (after, ['eaos/a.py', 'old.py', 'eaos/new.py'])):
            nodes = [{'kind': 'graph_node', 'location': {'path': path}} for path in files]
            (Path(folder) / 'facts/graph.json').write_text(json.dumps({'facts': nodes}))
            (Path(folder) / 'facts/resolve.json').write_text(json.dumps({'facts': []}))
        policy = {'layers': {'core': ['eaos/a.py']}, 'rules': []}
        self.assertEqual([p['where'] for p in gates.structure(before, after, policy)], ['eaos/new.py'], 'only the file the change added')


class PythonSuiteGateTests(unittest.TestCase):
    def test_a_change_to_the_apps_files_runs_the_apps_checks_on_the_card_itself(self):
        # EAOS, batch 5 (2026-10-14): an unused import in studio/ broke its type check and its build; no card's gate ran
        # them, and it was found only when the 51 changes met
        from eaos.journeys.fix import execute
        typecheck = {'argv': ['npm', 'run', 'typecheck'], 'exit': 0, 'failing': []}
        with mock.patch('eaos.live.app.run.load_profile', return_value={'app': 'studio'}), \
                mock.patch.object(execute, 'original_checks', return_value=[typecheck]), \
                mock.patch.object(execute, 'project_checks', return_value=[{**typecheck, 'exit': 2}]) as ran:
            self.assertEqual(execute.app_breakage('project', 'runtime', 'copy', ['eaos/analysis/planning/cards.py']), [])
            self.assertEqual(execute.app_breakage('project', 'runtime', 'copy', ['studio/src/x.tsx']),
                             ["the app's own check failed: npm run typecheck"])
        self.assertEqual(ran.call_args.kwargs, {'python': False}, 'the whole Python suite stays for the batch')

    def test_a_python_suite_beside_the_app_is_a_gate_and_only_its_new_failures_count(self):
        from eaos.journeys.fix.execute import failing, regressions
        from eaos.live.testing.verify import python_tests
        root = Path(scratch())
        self.assertEqual(python_tests(root), [], 'no tests/ folder, no command')
        small = Path(scratch())
        (small / 'tests.py').write_text('')        # flask-microblog of the corpus keeps its tests at its root (M9.5)
        (small / 'app').mkdir()
        (small / 'app' / 'testing.py').write_text('raise SystemExit')   # never imported to find the tests
        self.assertEqual(python_tests(small)[0][-3:], ['-m', 'unittest', 'tests'])
        layered = Path(scratch())
        (layered / 'tests' / 'e2e' / 'node_modules' / 'gyp').mkdir(parents=True)
        (layered / 'tests' / 'e2e' / 'node_modules' / 'gyp' / 'test_gyp.py').write_text('')   # a dependency's
        (layered / 'tests' / 'unit').mkdir()
        (layered / 'tests' / 'unit' / 'test_a.py').write_text('')    # a folder unittest cannot enter
        self.assertEqual(python_tests(layered), [])
        (layered / 'tests' / 'unit' / '__init__.py').write_text('')  # EAOS's own since M8: its check found no suite
        self.assertEqual(python_tests(layered)[0][-3:], ['discover', '-s', 'tests'])
        (root / 'tests').mkdir()
        (root / 'tests' / 'test_a.py').write_text('')
        self.assertEqual(python_tests(root)[0][-3:], ['discover', '-s', 'tests'])
        (root / 'conftest.py').write_text('')
        self.assertEqual(python_tests(root)[0][-2:], ['pytest', '-q'])
        argv = ['python', '-m', 'unittest']
        before = [{'argv': argv, 'exit': 1, 'failing': failing('FAIL: test_old (tests.test_a.A.test_old)\n')}]
        after = [{'argv': argv, 'exit': 1, 'failing': failing('FAIL: test_old (tests.test_a.A.test_old)\nERROR: test_new (tests.test_a.A.test_new)\n')}]
        self.assertEqual(regressions(before, after), ['python -m unittest (1 new failing: test_new (tests.test_a.A.test_new))'])

    def test_a_jest_suite_already_failing_counts_its_new_failures(self):
        # Trial on real projects (2026-11-02): the delivered branch had one more failing jest test than the original; no
        # gate saw it, the test gate read only TAP, unittest and pytest
        from eaos.journeys.fix.execute import failing, regressions
        old = ('FAIL api src/tests/services/auth.service.test.ts\n  \u25cf AuthService \u203a login \u203a should throw an error\n\n'
               '    expect(received).rejects.toThrow()\n\n  \u25cf Console\n\n    console.log\nTests:       1 failed, 26 passed, 27 total\n')
        new = old.replace('FAIL api src/tests/services/auth.service.test.ts\n',
                          'FAIL api src/tests/services/auth.service.test.ts\n  \u25cf AuthService \u203a createUser \u203a should create new user \n')
        argv = ['npm', 'run', 'test']
        self.assertEqual(regressions([{'argv': argv, 'exit': 1, 'failing': failing(old)}], [{'argv': argv, 'exit': 1, 'failing': failing(new)}]),
                         ['npm run test (1 new failing: AuthService \u203a createUser \u203a should create new user)'])
        self.assertEqual(failing(' FAIL  src/a.test.ts > cart > adds one\n'), ['cart > adds one'], 'vitest says it on one line')

    def test_a_check_that_cannot_run_here_is_named_never_silent(self):
        # Trial on real projects (2026-11-02): both checks of a project exited 127 (their program not found) on the original
        # and every gate; a check already failing with no names is no gate, so the lint gate was off and nobody was told
        from eaos.journeys.fix.execute import not_run
        rows = [{'argv': ['bun', 'run', 'lint'], 'exit': 127, 'failing': []}, {'argv': ['bun', 'run', 'test'], 'exit': 127, 'failing': []},
                {'argv': ['npm', 'test'], 'exit': 1, 'failing': []}]
        self.assertEqual(not_run(rows), ['bun run lint', 'bun run test'])

    def test_the_files_a_card_changed_beyond_its_own_are_named(self):
        # Trial on real projects (2026-11-02): a card about one dialog's complexity was kept with 13 files changed, the
        # other 12 never named to the person
        from eaos.journeys.fix.finish import beyond
        own = 'frontend/src/components/Admin/AddUser.tsx'
        others = [f'frontend/src/components/{name}.tsx' for name in (
            'Admin/DeleteUser', 'Admin/EditUser', 'Admin/UserFormFields', 'Common/DeleteDialog', 'Common/FormDialog', 'Common/FormFields',
            'Items/AddItem', 'Items/DeleteItem', 'Items/EditItem', 'Items/ItemActionsMenu', 'Items/ItemDialog')] + ['frontend/src/routes/_layout/items.tsx']
        self.assertEqual(beyond({'paths': [own]}, [own, *others]), others)
        self.assertEqual(beyond({'paths': ['frontend/src/components']}, [own, *others]), ['frontend/src/routes/_layout/items.tsx'])
        self.assertEqual(beyond({'paths': ['*']}, [own, *others]), [])


if __name__ == '__main__':
    unittest.main()
