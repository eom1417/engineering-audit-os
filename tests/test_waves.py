"""Fixes in waves: the expensive gates once per batch (eaos/waves.py finish_batch, behind the MCP fix_finish), the card
at fault found by halving, and the result handed over as a branch that leaves the person's branch and files alone."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos import waves
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
        from eaos.behavior_lock import _declared
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
        with mock.patch.object(waves, 'failing_output', return_value=said), mock.patch.object(waves, 'gates', return_value='') as gates:
            self.assertEqual(list(waves._named(batch, commits)), [commits[0]])
        self.assertEqual(gates.call_count, 1, 'one run of the checks, not a halving')
        self.assertEqual(waves._sizes_before(root, ['b.py', 'c.py']), {'b.py': 2}, 'counted as facts/metrics counts lines')

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
                mock.patch('eaos.probes.decide_probe', return_value=('REFUTED', 'gone')):
            exits = waves.batch_acceptance(scratch(), [dead_card, gone_card, probe_card], scratch())
        self.assertEqual(collect.call_count, 1)
        self.assertEqual(exits, {'D': 0, 'G': 1, 'P': 0})

class RebuildTests(unittest.TestCase):
    def test_a_module_is_split_only_after_its_complex_functions_and_a_split_tried_too_early_comes_back(self):
        # EAOS, 2026-10-15: five module splits went into batches before their simplifications, failed, never came back
        from eaos import ledger
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

    def test_the_branch_is_the_base_plus_exactly_the_kept_commits_and_the_card_at_fault_is_found_by_halving(self):
        root = repository()
        base = git(root, 'rev-parse', 'HEAD')
        one, two, three = (commit_file(root, f'{n}.txt', n) for n in ('one', 'two', 'three'))
        self.assertEqual(waves.rebuild(root, base, [one, three]), [])
        self.assertEqual(sorted(p.name for p in root.glob('*.txt')), ['a.txt', 'one.txt', 'three.txt'])
        commits = [f'c{n}' for n in range(8)]
        applied, regenerated = [], []
        batch = {'root': 'root', 'base': 'base', 'name': 'wave-1', 'say': lambda *a: None, 'regenerate': regenerated.append}
        with mock.patch.object(waves, 'rebuild', side_effect=lambda root, base, part: applied.append(list(part)) or []), \
                mock.patch.object(waves, 'gates', side_effect=lambda *a, **k: f'broken by {len(applied[-1])}' if 'c5' in applied[-1] else ''):
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

    def test_a_closed_batchs_copy_goes_at_the_next_save_and_one_still_opening_stays(self):
        with tempfile.TemporaryDirectory() as runtime:
            copies = Path(runtime) / 'candidates'
            for name in ('WAVE-1', 'BUILD-2', 'WAVE-3'): (copies / name).mkdir(parents=True)
            logs = Path(runtime) / 'runtime'
            logs.mkdir()
            for name in ('wave-1', 'wave-1-bisect-ab12cd34-2', 'wave-3-bisect-ab12cd34-2'): (logs / f'checks-{name}-log.json').write_text('{}')
            waves.saved({'waves': [{'number': 1}, {'number': 2, 'via': 'build'}]}, runtime)
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
        with mock.patch.object(waves, 'batch_acceptance', side_effect=lambda report, cards, root: {c['id']: 0 for c in cards}
                               | {'T4': 1}), \
                mock.patch.object(waves, 'original_checks', return_value=['test']), mock.patch.object(waves, 'gates', side_effect=broken), \
                mock.patch.object(waves, '_against_control', return_value=False):
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
        with mock.patch.object(waves, 'batch_acceptance', side_effect=lambda report, cards, root: {c['id']: 0 for c in cards}), \
                mock.patch.object(waves, 'original_checks', return_value=['test']), mock.patch.object(waves, 'gates', side_effect=together), \
                mock.patch.object(waves, '_against_control', return_value=False):
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
        with mock.patch.object(waves, 'batch_acceptance', side_effect=lambda report, cards, root: {c['id']: 0 for c in cards}), \
                mock.patch.object(waves, 'original_checks', return_value=[]), mock.patch.object(waves, 'gates', side_effect=live_page), \
                mock.patch('eaos.behavior_lock.verify_lock') as control, \
                mock.patch('eaos.behavior_lock.failing_tests', return_value={'problems'}):
            summary = waves.finish_batch(report, project, runtime, wave(root, base, kept), lock=True)
        self.assertEqual((summary['kept'], summary['failed']), (['T1', 'T2'], {}))
        self.assertEqual(control.call_args.kwargs['name'], 'wave-1-control', 'checked once on the base alone')
        self.assertEqual(sorted(p.name for p in root.glob('*.txt')), ['1.txt', '2.txt', 'a.txt'], 'and the batch back whole after it')


class RegenerateTests(unittest.TestCase):
    def test_what_the_build_makes_from_the_batchs_source_comes_back_as_one_commit_and_nothing_ignored(self):
        # EAOS on itself (2026-10-13): Studio fixes changed studio/src, the shipped build in eaos/data/studio no longer
        # matched it, and four sound fixes were about to be left out of the batch for it.
        from eaos import regenerate
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
        from eaos.gates import debt, words
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
        from eaos import gates

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
        from eaos import execute
        typecheck = {'argv': ['npm', 'run', 'typecheck'], 'exit': 0, 'failing': []}
        with mock.patch('eaos.live_run.load_profile', return_value={'app': 'studio'}), \
                mock.patch.object(execute, 'original_checks', return_value=[typecheck]), \
                mock.patch.object(execute, 'project_checks', return_value=[{**typecheck, 'exit': 2}]) as ran:
            self.assertEqual(execute.app_breakage('project', 'runtime', 'copy', ['eaos/plan.py']), [])
            self.assertEqual(execute.app_breakage('project', 'runtime', 'copy', ['studio/src/x.tsx']),
                             ["the app's own check failed: npm run typecheck"])
        self.assertEqual(ran.call_args.kwargs, {'python': False}, 'the whole Python suite stays for the batch')

    def test_a_python_suite_beside_the_app_is_a_gate_and_only_its_new_failures_count(self):
        from eaos.execute import failing, regressions
        from eaos.verify import python_tests
        root = Path(scratch())
        self.assertEqual(python_tests(root), [], 'no tests/ folder, no command')
        (root / 'tests').mkdir()
        (root / 'tests' / 'test_a.py').write_text('')
        self.assertEqual(python_tests(root)[0][-3:], ['discover', '-s', 'tests'])
        (root / 'conftest.py').write_text('')
        self.assertEqual(python_tests(root)[0][-2:], ['pytest', '-q'])
        argv = ['python', '-m', 'unittest']
        before = [{'argv': argv, 'exit': 1, 'failing': failing('FAIL: test_old (tests.test_a.A.test_old)\n')}]
        after = [{'argv': argv, 'exit': 1, 'failing': failing('FAIL: test_old (tests.test_a.A.test_old)\nERROR: test_new (tests.test_a.A.test_new)\n')}]
        self.assertEqual(regressions(before, after), ['python -m unittest (1 new failing: test_new (tests.test_a.A.test_new))'])


if __name__ == '__main__':
    unittest.main()
