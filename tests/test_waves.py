"""Fixes in waves: the expensive gates once per batch (eaos/waves.py finish_batch, behind the MCP fix_finish), the card
at fault found by halving, and the result handed over as a branch that leaves the person's branch and files alone."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos import waves


def git(where, *args):
    return subprocess.run(['git', '-C', str(where), *args], capture_output=True, text=True, check=True).stdout.strip()


def repository():
    root = Path(tempfile.mkdtemp()) / 'shop'
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
    def test_a_batch_is_the_next_ready_cards_in_milestone_order_and_judged_from_one_collection_of_facts(self):
        report = Path(tempfile.mkdtemp())
        ready = lambda i: {'id': i, 'kind': 'remediate', 'decision': {'readiness': 'ready'}}
        (report / 'plan.json').write_text(json.dumps({'tasks': [ready('T1'), ready('T2'), ready('T3'),
                                                                {'id': 'T4', 'kind': 'investigate', 'decision': {'readiness': 'blocked'}}],
                                                      'milestones': [{'tasks': ['T3', 'T4']}, {'tasks': ['T1', 'T2']}]}))
        self.assertEqual(waves.next_batch(report, [], size=2), ['T3', 'T1'])
        tried = [c['key'] for c in waves.plan(report)['tasks'] if c['id'] == 'T3']     # `tried` holds keys, not ids
        self.assertEqual(waves.next_batch(report, tried, size=5), ['T1', 'T2'])
        dead_card = {'id': 'D', 'verify_command': ['python', '-c', "left = [f for f in facts if (f['location']['path'], "
                                                   "f['location']['symbol'], f['value']['rule']) == ('src/a.ts', 'gone', 'unused-symbol')]"]}
        gone_card = {'id': 'G', 'verify_command': ['python', '-c', "x == ('src/a.ts', 'still', 'unused-symbol')"]}
        probe_card = {'id': 'P', 'verify_command': ['eaos', 'recheck', '--spec', json.dumps({'probe_type': 'graph_query', 'specification': {'query': 'q'}}), '.']}
        sets = {'deadcode': {'facts': [{'location': {'path': 'src/a.ts', 'symbol': 'still'}, 'value': {'rule': 'unused-symbol'}}]}}
        with mock.patch('eaos.facts.run.collect') as collect, mock.patch('eaos.facts.run.read_available', return_value=sets), \
                mock.patch('eaos.probes.decide_probe', return_value=('REFUTED', 'gone')):
            exits = waves.batch_acceptance(tempfile.mkdtemp(), [dead_card, gone_card, probe_card], tempfile.mkdtemp())
        self.assertEqual(collect.call_count, 1)
        self.assertEqual(exits, {'D': 0, 'G': 1, 'P': 0})

class RebuildTests(unittest.TestCase):
    def test_the_branch_is_the_base_plus_exactly_the_kept_commits_and_the_card_at_fault_is_found_by_halving(self):
        root = repository()
        base = git(root, 'rev-parse', 'HEAD')
        one, two, three = (commit_file(root, f'{n}.txt', n) for n in ('one', 'two', 'three'))
        self.assertEqual(waves.rebuild(root, base, [one, three]), [])
        self.assertEqual(sorted(p.name for p in root.glob('*.txt')), ['a.txt', 'one.txt', 'three.txt'])
        commits = [f'c{n}' for n in range(8)]
        applied = []
        with mock.patch.object(waves, 'rebuild', side_effect=lambda root, base, part: applied.append(list(part)) or []), \
                mock.patch.object(waves, 'gates', side_effect=lambda *a, **k: 'broken' if 'c5' in applied[-1] else ''):
            found = waves.culprits('r', 'root', 'rt', 'base', commits, [], True, 'wave-1', lambda *a: None)
        self.assertEqual(found, ['c5'])
        self.assertLessEqual(len(applied), 6, 'halving, not trying every card alone')


class HandOverTests(unittest.TestCase):
    def test_the_branch_arrives_without_touching_the_current_branch_or_unsaved_edits(self):
        project = repository()
        clone = Path(tempfile.mkdtemp()) / 'candidate'
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


class FinishTests(unittest.TestCase):
    def test_a_card_that_breaks_the_gates_is_taken_back_and_the_others_stay(self):
        project, runtime, report = repository(), Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        cards = [{'id': f'T{n}', 'title': f't{n}', 'kind': 'remediate', 'decision': {'readiness': 'ready'}, 'paths': [f'{n}.txt'],
                  'verify_command': ['true']} for n in (1, 2, 3, 4)]
        (report / 'plan.json').write_text(json.dumps({'tasks': cards}))
        root = Path(tempfile.mkdtemp()) / 'candidate'
        subprocess.run(['git', 'clone', '-q', str(project), str(root)], check=True)
        base = git(root, 'rev-parse', 'HEAD')
        kept = {card['id']: commit_file(root, card['paths'][0], card['id']) for card in cards}
        broken = lambda report, root, *rest: 'the project\'s own check failed: test' if (Path(root) / '2.txt').exists() else ''
        with mock.patch.object(waves, 'batch_acceptance', side_effect=lambda report, cards, root: {c['id']: 0 for c in cards}
                               | {'T4': 1}), \
                mock.patch.object(waves, 'original_checks', return_value=['test']), mock.patch.object(waves, 'gates', side_effect=broken):
            summary = waves.finish_batch(report, project, runtime, 1, root, base, ['T1', 'T2', 'T3', 'T4'], kept, {}, {}, lock=False)
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


if __name__ == '__main__':
    unittest.main()
