"""A batch handed over as branches a reviewer can merge one by one (eaos/journeys/fix/split.py): beside the whole
branch, one branch per kind of card, made from the base with only that kind's commits; a kind that does not stand alone
is named, not made; undo removes them with the batch's branch."""
import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from eaos.journeys.fix import split
from shared_fixture import scratch


def git(where, *args):
    return subprocess.run(['git', '-C', str(where), *args], capture_output=True, text=True, check=True).stdout.strip()


def commit_file(root, name, text):
    (Path(root) / name).write_text(text)
    git(root, 'add', '-A'); git(root, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', name)
    return git(root, 'rev-parse', 'HEAD')


def batch(changes):
    """(project, report, runtime, wave, summary): a project, and its batch's copy with one commit per card of
    `changes` [(card id, pattern, file, text)], handed over as eaos/wave-1 as fix_finish leaves it."""
    project, report, runtime = Path(scratch()) / 'shop', Path(scratch()), Path(scratch())
    project.mkdir()
    git(project, 'init', '-q')
    commit_file(project, 'a.txt', 'a\n')
    cards = [{'id': card_id, 'title': card_id, 'pattern': pattern, 'paths': [name]} for card_id, pattern, name, _ in changes]
    (report / 'plan.json').write_text(json.dumps({'tasks': cards}))
    root = Path(scratch()) / 'candidate'
    subprocess.run(['git', 'clone', '-q', str(project), str(root)], check=True)
    base = git(root, 'rev-parse', 'HEAD')
    kept = {card_id: commit_file(root, name, text) for card_id, _, name, text in changes}
    summary = {'kept': list(kept), 'branch': 'eaos/wave-1', 'root': str(root)}
    git(project, 'fetch', '-q', str(root), '+HEAD:refs/heads/eaos/wave-1')
    return project, report, runtime, {'number': 1, 'root': str(root), 'base': base, 'kept': kept}, summary


def files(project, branch):
    return sorted(git(project, 'ls-tree', '--name-only', branch).split())


PASSING = mock.patch('eaos.journeys.fix.split.batch_acceptance', side_effect=lambda report, cards, root, **_: {c['id']: 0 for c in cards})


class SplitTests(unittest.TestCase):
    def test_a_batch_of_a_dependency_and_a_refactor_is_handed_over_whole_and_as_one_branch_of_each(self):
        # without the split, one branch mixes upgrades, refactors and looks in many files, none mergeable in pieces
        project, report, runtime, wave, summary = batch([('T1', 'upgrade_dependency', 'requirements.txt', 'fastapi==1\n'),
                                                         ('T2', 'split_module', 'code.py', 'x = 1\n')])
        tip = git(wave['root'], 'rev-parse', 'HEAD')
        with PASSING:
            made = split.split((report, runtime, project), wave, summary)
        self.assertEqual(made['split'], [{'kind': 'deps', 'cards': ['T1'], 'branch': 'eaos/wave-1-deps'},
                                         {'kind': 'refactor', 'cards': ['T2'], 'branch': 'eaos/wave-1-refactor'}])
        self.assertEqual(files(project, 'eaos/wave-1-deps'), ['a.txt', 'requirements.txt'])
        self.assertEqual(files(project, 'eaos/wave-1-refactor'), ['a.txt', 'code.py'])
        self.assertEqual(files(project, 'eaos/wave-1'), ['a.txt', 'code.py', 'requirements.txt'], 'the whole branch stays')
        self.assertEqual(git(wave['root'], 'rev-parse', 'HEAD'), tip, "the batch's copy is back at its tip")

    def test_a_kind_whose_changes_do_not_apply_alone_is_named_not_made(self):
        project, report, runtime, wave, summary = batch([('T1', 'upgrade_dependency', 'requirements.txt', 'fastapi==1\n'),
                                                         ('T2', 'split_module', 'requirements.txt', 'fastapi==1\nx\n')])
        with PASSING:
            made = split.split((report, runtime, project), wave, summary)
        self.assertEqual([each['branch'] for each in made['split']], ['eaos/wave-1-deps'])
        self.assertEqual([(each['kind'], each['cards']) for each in made['not_split']], [('refactor', ['T2'])])
        self.assertIn('do not apply', made['not_split'][0]['why'])
        self.assertNotIn('eaos/wave-1-refactor', git(project, 'branch', '--list', 'eaos/wave-1-refactor'))

    def test_a_batch_of_one_kind_is_not_split(self):
        project, report, runtime, wave, summary = batch([('T1', 'split_module', 'one.py', '1\n'), ('T2', 'hotspot', 'two.py', '2\n')])
        self.assertEqual(split.split((report, runtime, project), wave, summary), {})

    def test_undo_removes_the_branches_the_batch_was_split_into(self):
        from eaos.journeys import agent_tools, guided
        project, report, runtime, wave, summary = batch([('T1', 'upgrade_dependency', 'requirements.txt', 'fastapi==1\n'),
                                                         ('T2', 'design_review', 'site.css', 'a {}\n')])
        with mock.patch.dict(os.environ, {'EAOS_HOME': scratch()}):
            with PASSING:
                made = split.split((report, runtime, project), wave, summary)
            state = agent_tools.state_of(str(project))
            state['waves'] = [{'number': 1, 'branch': 'eaos/wave-1', 'status': 'applied', **made}]
            guided.save(state)
            self.assertEqual(agent_tools.undo(str(project), person_agreed=True)['status'], 'undone')
        self.assertEqual(git(project, 'branch', '--list', 'eaos/wave-1*'), '', 'nothing EAOS made is left behind')


if __name__ == '__main__':
    unittest.main()
