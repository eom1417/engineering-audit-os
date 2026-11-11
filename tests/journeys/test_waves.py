"""Fixes in waves: the order of the waves, the result handed over as a branch that leaves the person's branch and files
alone, finishing a batch, and regenerating."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from eaos.journeys.fix import waves
from eaos.journeys.fix.waves import batch as wave_batch
from shared_fixture import scratch
from tests.journeys._waves_fixture import commit_file, git, repository


class OrderTests(unittest.TestCase):
    def test_a_batch_with_a_design_card_may_change_any_screens_look_but_not_its_errors(self):
        # A design card's shared change shows on pages its finding never named; only an error on them fails it.
        from eaos.live.behavior.lock import _declared
        self.assertEqual(waves.declared_screens([{'design': {'findings': [{'page': '/library'}]}}, {}]), {'*'})
        self.assertEqual(waves.declared_screens([{'id': 'TASK-1'}]), set(),
                         'a batch of code changes keeps every screen locked')
        shot = 'expect(page).toHaveScreenshot(expected) failed\n  Snapshot: change-ideal.png'
        self.assertEqual(_declared('failed', shot, {'*'}), 'passed')
        self.assertEqual(_declared('failed', 'console: TypeError: x is undefined', {'*'}), 'failed',
                         'a page error still breaks it')
        self.assertEqual(_declared('failed', shot, set()), 'failed')

    def test_a_failure_that_names_a_file_finds_its_culprit_in_one_run_and_a_change_is_sized_against_the_copy(self):
        # When a failure names a file, its culprit is found in one run instead of halving the batch; a repair is sized
        # against the copy, not against the size the check on record knew.
        root = Path(scratch())
        run = lambda *a: subprocess.run(['git', '-C', str(root), '-c', 'user.name=t', '-c', 'user.email=t@t', *a],
                                        check=True,
                                        capture_output=True, text=True).stdout.strip()
        run('init', '-q')
        (root / 'a.py').write_text('x = 1\n'); (root / 'b.py').write_text('y = 1\n')
        run('add', '-A'); run('commit', '-qm', 'base'); base = run('rev-parse', 'HEAD')
        commits = []
        for name in ('a.py', 'b.py'):
            (root / name).write_text('z = 2\n'); run('commit', '-qam', name); commits.append(run('rev-parse', 'HEAD'))
        batch = {'name': 'w', 'runtime': root, 'root': root, 'base': base, 'say': lambda *_: None,
                 'regenerate': lambda r: None}
        said = [{'command': 'tests', 'output': 'FAIL: test_x ... a.py::f: 16 (allowed 15)'}]
        with mock.patch.object(wave_batch, 'failing_output',
                               return_value=said), mock.patch.object(wave_batch, 'gates', return_value='') as gates:
            self.assertEqual(list(wave_batch._named(batch, commits)), [commits[0]])
        self.assertEqual(gates.call_count, 1, 'one run of the checks, not a halving')
        self.assertEqual(wave_batch._sizes_before(root, ['b.py', 'c.py']), {'b.py': 2},
                         'counted as facts/metrics counts lines')

    def test_a_card_whose_change_brings_a_finding_of_the_slower_security_engine_is_left_out_of_the_batch(self):
        # bandit and gitleaks read every change; semgrep (the browser's innerHTML, a shell built from strings) reads the
        # batch's commit, so its finding leaves the card out of the batch.
        root = repository()
        base = git(root, 'rev-parse', 'HEAD')
        sound, unsafe = commit_file(root, 'b.txt', 'b\n'), commit_file(root, 'page.js', 'el.innerHTML = name\n')
        batch = {'root': root, 'base': base, 'report': root, 'say': lambda *_: None, 'regenerate': lambda r: None}
        failed = {}
        found = [('semgrep', 'insecure-innerhtml', 'page.js')]
        with mock.patch('eaos.facts.run.collect'), mock.patch('eaos.analysis.assessments.weaknesses.new',
                                                              return_value=found):
            kept = wave_batch._secure(batch, {'T1': sound, 'T2': unsafe}, failed, [])
        self.assertEqual(list(kept), ['T1'])
        self.assertIn('insecure-innerhtml (semgrep) in page.js', failed['T2'])
        self.assertEqual(batch['security']['engines'], ['semgrep'], "the batch's record says what read it")
        self.assertFalse((root / 'page.js').exists(), 'the copy is rebuilt without it')

    def test_a_batch_is_the_next_ready_cards_in_milestone_order_and_judged_from_one_collection_of_facts(self):
        report = Path(scratch())
        ready = lambda i: {'id': i, 'kind': 'remediate', 'decision': {'readiness': 'ready'}}
        (report / 'plan.json').write_text(json.dumps({'tasks': [ready('T1'), ready('T2'), ready('T3'),
                                                                {'id': 'T4', 'kind': 'investigate',
                                                                 'decision': {'readiness': 'blocked'}}],
                                                      'milestones': [{'tasks': ['T3', 'T4']},
                                                                     {'tasks': ['T1', 'T2']}]}))
        self.assertEqual(waves.next_batch(report, {}, size=2), ['T3', 'T1'])
        tried = [c['key'] for c in waves.plan(report)['tasks'] if c['id'] == 'T3']     # `tried` holds keys, not ids
        self.assertEqual(waves.next_batch(report, {'tried': tried}, size=5), ['T1', 'T2'])
        dead_card = {'id': 'D',
                     'verify_command': ['python', '-c', "left = [f for f in facts if (f['location']['path'], "
                                        "f['location']['symbol'], f['value']['rule']) == "
                                        "('src/a.ts', 'gone', 'unused-symbol')]"]}
        gone_card = {'id': 'G', 'verify_command': ['python', '-c', "x == ('src/a.ts', 'still', 'unused-symbol')"]}
        probe_card = {'id': 'P',
                      'verify_command': ['eaos', 'recheck', '--spec',
                                         json.dumps({'probe_type': 'graph_query', 'specification': {'query': 'q'}}),
                                         '.']}
        sets = {'deadcode': {'facts': [{'location': {'path': 'src/a.ts', 'symbol': 'still'},
                                        'value': {'rule': 'unused-symbol'}}]}}
        with mock.patch('eaos.facts.run.collect') as collect, mock.patch('eaos.facts.run.read_available',
                                                                         return_value=sets), \
                mock.patch('eaos.analysis.claims.probes.decide_probe', return_value=('REFUTED', 'gone')):
            exits = wave_batch.batch_acceptance(scratch(), [dead_card, gone_card, probe_card], scratch())
        self.assertEqual(collect.call_count, 1)
        self.assertEqual(exits, {'D': 0, 'G': 1, 'P': 0})

    def test_repository_craft_never_goes_in_a_fix_batch(self):
        # repository_craft cards (the guide, CLAUDE.md) belong to their own batch, never to a fix batch
        report = Path(scratch())
        card = lambda i, pattern: {'id': i, 'kind': 'remediate', 'pattern': pattern, 'decision': {'readiness': 'ready'}}
        (report / 'plan.json').write_text(json.dumps({'tasks': [card('CRAFT', 'repository_craft'),
                                                                card('FIX', 'duplication')], 'milestones': []}))
        self.assertEqual(waves.next_batch(report, {}), ['FIX'])
        self.assertEqual(waves.kept_apart([card('CRAFT', 'repository_craft'), card('FIX', 'duplication')])['own_batch'],
                         ['CRAFT'])
        self.assertIsNone(waves.kept_apart([card('FIX', 'duplication')]))

    def test_a_layer_card_is_judged_by_the_layers_read_again_on_the_copy(self):
        # a layer card is judged by the boundaries facts read again on the copy, which must be present
        spec = {'probe_type': 'graph_query',
                'specification': {'query': 'boundary_finding_present', 'rule': 'ui-database',
                                  'path': 'web/Orders.jsx', 'params': {}}}
        card = {'id': 'L', 'verify_command': ['eaos', 'recheck', '--spec', json.dumps(spec), '.']}
        shown = {'location': {'path': 'web/Orders.jsx'}, 'value': {'rule': 'ui-database', 'params': {}}}
        for facts, exit in (([], 0), ([shown], 1)):
            with mock.patch('eaos.facts.run.collect'), mock.patch('eaos.facts.run.read_available', return_value={}), \
                    mock.patch('eaos.analysis.layers.check'), mock.patch('eaos.analysis.layers.facts_of',
                                                                         return_value=facts):
                self.assertEqual(wave_batch.batch_acceptance(scratch(), [card], scratch()), {'L': exit})

    def test_a_failing_tests_card_passes_only_when_its_command_passes_on_the_copy(self):
        # a failing-tests card's recheck must run its command, not read the code alone, which would call it gone
        spec = {'probe_type': 'graph_query',
                'specification': {'query': 'boundary_finding_present', 'rule': 'tests-failing',
                                  'path': '*', 'params': {'failed': 3, 'total': 40, 'command': 'npm run test'}}}
        card = {'id': 'T', 'verify_command': ['eaos', 'recheck', '--spec', json.dumps(spec), '.']}
        for code, runtime, exit in ((0, 'runtime', 0), (1, 'runtime', 1), (127, 'runtime', 2), (0, None, 2)):
            rows = [{'argv': ['npm', 'run', 'lint'], 'exit': 0, 'failing': []},
                    {'argv': ['npm', 'run', 'test'], 'exit': code, 'failing': []}]
            with mock.patch('eaos.facts.run.collect'), mock.patch('eaos.facts.run.read_available', return_value={}), \
                    mock.patch('eaos.journeys.fix.execute.project_checks', return_value=rows):
                self.assertEqual(wave_batch.batch_acceptance(scratch(), [card], scratch(), runtime=runtime),
                                 {'T': exit}, (code, runtime))


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
        self.assertEqual(waves.undo(project, 'eaos/wave-1'), 'merged',
                         'a merged wave is not undone behind the person\'s back')
        with self.assertRaises(ValueError, msg='a wave that kept nothing hands nothing over'):
            waves.apply(project, {'kept': [], 'branch': 'eaos/wave-1', 'root': '/nowhere'})

    def test_a_closing_save_removes_the_closed_batchs_copy_and_one_still_opening_stays(self):
        with tempfile.TemporaryDirectory() as runtime:
            copies = Path(runtime) / 'candidates'
            for name in ('WAVE-1', 'BUILD-2', 'WAVE-3'): (copies / name).mkdir(parents=True)
            logs = Path(runtime) / 'runtime'
            logs.mkdir()
            for name in ('wave-1', 'wave-1-bisect-ab12cd34-2',
                         'wave-3-bisect-ab12cd34-2'): (logs / f'checks-{name}-log.json').write_text('{}')
            waves.saved({'waves': [{'number': 1}, {'number': 2, 'via': 'build'}]}, runtime,
                        {'waves': [], 'open_wave': {'number': 1}, 'open_build': {'number': 2}})
            self.assertEqual([p.name for p in copies.iterdir()], ['WAVE-3'])
            self.assertEqual(sorted(p.name for p in logs.iterdir()),
                             ['checks-wave-1-log.json', 'checks-wave-3-bisect-ab12cd34-2-log.json'],
                             "a closed batch keeps its gates' summary, not its bisection's logs")


def wave(root, base, kept):
    """The open batch as batch_finish keeps it: number 1, every kept card, none failed."""
    return {'number': 1, 'root': root, 'base': base, 'cards': list(kept), 'kept': kept, 'failed': {}, 'tools': {}}


class FinishTests(unittest.TestCase):
    def test_a_card_that_breaks_the_gates_is_taken_back_and_the_others_stay(self):
        project, runtime, report = repository(), Path(scratch()), Path(scratch())
        cards = [{'id': f'T{n}', 'title': f't{n}', 'kind': 'remediate', 'decision': {'readiness': 'ready'},
                  'paths': [f'{n}.txt'],
                  'verify_command': ['true']} for n in (1, 2, 3, 4)]
        (report / 'plan.json').write_text(json.dumps({'tasks': cards}))
        root = Path(scratch()) / 'candidate'
        subprocess.run(['git', 'clone', '-q', str(project), str(root)], check=True)
        base = git(root, 'rev-parse', 'HEAD')
        kept = {card['id']: commit_file(root, card['paths'][0], card['id']) for card in cards}
        broken = lambda batch, name: ('the project\'s own check failed: test'
                                      if (Path(batch['root']) / '2.txt').exists() else '')
        with mock.patch.object(wave_batch, 'batch_acceptance',
                               side_effect=lambda report, cards, root, **_: {c['id']: 0 for c in cards}
                               | {'T4': 1}), \
                mock.patch.object(wave_batch, 'original_checks',
                                  return_value=['test']), mock.patch.object(wave_batch, 'gates', side_effect=broken), \
                mock.patch.object(wave_batch, '_against_control', return_value=False):
            summary = waves.finish_batch(report, project, runtime, wave(root, base, kept), lock=False)
        self.assertEqual(summary['kept'], ['T1', 'T3'])
        self.assertIn("own check failed", summary['failed']['T2'])
        self.assertIn('acceptance exited 1', summary['failed']['T4'])
        self.assertEqual(sorted(p.name for p in root.glob('*.txt')), ['1.txt', '3.txt', 'a.txt'])
        rows = {r['id']: (r['status'], r['tool'])
                for r in json.loads((runtime / 'runtime/execution.json').read_text())['tasks']}
        self.assertEqual(rows, {'T1': ('VERIFIED_IN_ISOLATED_COPY', 'assistant'), 'T2': ('FAILED', 'assistant'),
                                'T3': ('VERIFIED_IN_ISOLATED_COPY', 'assistant'), 'T4': ('FAILED', 'assistant')},
                         'a card the assistant fixed is recorded like any other')
        self.assertEqual(len(list((runtime / 'waves/wave-1').glob('*.patch'))), 2)
        self.assertEqual(json.loads((runtime / 'waves/wave-1/wave.json').read_text())['branch'], 'eaos/wave-1')

    def test_changes_that_fail_only_together_are_repaired_on_top_and_no_sound_card_is_left_out(self):
        # Cards that pass one by one can fail together (a split module's parts importing each other); a repair on top
        # keeps all of them, where halving would leave sound cards out.
        project, runtime, report = repository(), Path(scratch()), Path(scratch())
        cards = [{'id': f'T{n}', 'title': f't{n}', 'kind': 'remediate', 'decision': {'readiness': 'ready'},
                  'paths': [f'{n}.txt'],
                  'verify_command': ['true']} for n in (1, 2)]
        (report / 'plan.json').write_text(json.dumps({'tasks': cards}))
        root = Path(scratch()) / 'candidate'
        subprocess.run(['git', 'clone', '-q', str(project), str(root)], check=True)
        base = git(root, 'rev-parse', 'HEAD')
        kept = {card['id']: commit_file(root, card['paths'][0], card['id']) for card in cards}
        together = lambda batch, name: ('' if (Path(batch['root']) / 'repair.txt').exists()
                                        or not (Path(batch['root']) / '2.txt').exists()
                                                else "the project's own check failed: a cycle")
        finish = lambda repairs, bisect: waves.finish_batch(report, project, runtime, wave(root, base, kept),
                                                           lock=False, repairs=repairs, bisect=bisect)
        with mock.patch.object(wave_batch, 'batch_acceptance',
                               side_effect=lambda report, cards, root, **_: {c['id']: 0 for c in cards}), \
                mock.patch.object(wave_batch, 'original_checks',
                                  return_value=['test']), mock.patch.object(wave_batch, 'gates',
                                                                            side_effect=together), \
                mock.patch.object(wave_batch, '_against_control', return_value=False):
            with self.assertRaises(waves.GatesFailed) as asked:
                finish([], bisect=False)
            self.assertIn('a cycle', asked.exception.why)
            repair = commit_file(root, 'repair.txt', 'repair')
            summary = finish([repair], bisect=False)
        self.assertEqual((summary['kept'], summary['failed']), (['T1', 'T2'], {}))
        self.assertEqual(sorted(p.name for p in root.glob('*.txt')), ['1.txt', '2.txt', 'a.txt', 'repair.txt'])

    def test_what_fails_on_the_base_too_is_set_aside_and_the_batch_is_kept_whole(self):
        # What fails on the base too is set aside: a page reading live data that the batch itself rewrites differs with
        # every card alone and with none, and must not leave sound fixes out.
        project, runtime, report = repository(), Path(scratch()), Path(scratch())
        cards = [{'id': f'T{n}', 'title': f't{n}', 'kind': 'remediate', 'decision': {'readiness': 'ready'},
                  'paths': [f'{n}.txt'],
                  'verify_command': ['true']} for n in (1, 2)]
        (report / 'plan.json').write_text(json.dumps({'tasks': cards}))
        root = Path(scratch()) / 'candidate'
        subprocess.run(['git', 'clone', '-q', str(project), str(root)], check=True)
        base = git(root, 'rev-parse', 'HEAD')
        kept = {card['id']: commit_file(root, card['paths'][0], card['id']) for card in cards}
        live_page = lambda batch, name: '' if 'problems' in (batch.get('known')
                                                             or ()) else 'the behaviour lock broke on 1 of 2 specs'
        with mock.patch.object(wave_batch, 'batch_acceptance',
                               side_effect=lambda report, cards, root, **_: {c['id']: 0 for c in cards}), \
                mock.patch.object(wave_batch, 'original_checks',
                                  return_value=[]), mock.patch.object(wave_batch, 'gates', side_effect=live_page), \
                mock.patch('eaos.live.behavior.lock.verify_lock') as control, \
                mock.patch('eaos.live.behavior.lock.failing_tests', return_value={'problems'}):
            summary = waves.finish_batch(report, project, runtime, wave(root, base, kept), lock=True)
        self.assertEqual((summary['kept'], summary['failed']), (['T1', 'T2'], {}))
        self.assertEqual(control.call_args.args[3].name, 'wave-1-control', 'checked once on the base alone')
        self.assertEqual(sorted(p.name for p in root.glob('*.txt')), ['1.txt', '2.txt', 'a.txt'],
                         'and the batch back whole after it')


class RegenerateTests(unittest.TestCase):
    def test_what_the_build_makes_from_the_batchs_source_comes_back_as_one_commit_and_nothing_ignored(self):
        # A fix that changes the build's source makes the shipped build differ from it; the rebuilt build is committed,
        # so sound fixes are not left out of the batch for it.
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
        with mock.patch.object(regenerate, 'LiveRun', Built), mock.patch.object(regenerate, 'load_profile',
                                                                                return_value=profile):
            sha = regenerate.regenerate(root, runtime, base, 3)
        self.assertEqual(sorted(git(root, 'show', '--name-only', '--format=', sha).split()),
                         ['shipped/new.js', 'shipped/old.js'])
        self.assertEqual(((root / 'shipped/new.js').read_text(), (root / 'shipped/old.js').exists()),
                         ('built from two', False))
        with mock.patch.object(regenerate, 'load_profile', return_value=profile):
            self.assertIsNone(regenerate.regenerate(root, runtime, git(root, 'rev-parse', 'HEAD'), 4),
                              'the app did not change')


if __name__ == '__main__':
    unittest.main()
