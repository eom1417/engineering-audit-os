"""NS30.T2 — the five places the field report (2026-10-07, Chief Operations) tripped, each as it must behave.

Interface this task must provide:
    agent_tools.status(folder)        a folder with no .git and exactly one git repository directly under it is that
                                      project; with several, {"status": "needs_project", "projects": [...]} (never an
                                      exception, never a guess)
    guided.report_stamp(state)        carries "scanned_commit": the project commit the check read
    agent_tools.open_report(...)      returns "stale": {"checked": <sha>, "now": <sha>} once the branch moved past the
                                      checked commit with code of its own, else "stale": null
    agent_tools.fix_start(cards=[x])  refuses a card that needs a person's decision (not ready): the reason names the
                                      decision, and no batch is opened; so fix_finish never meets a card it cannot check
    ledger.sync                       a card whose EAOS commit was reverted on the person's branch is not done
    branches.choice                   branches merged into the main branch (nothing of their own) and archive/* branches
                                      are no choice: with only those beside main, status asks nothing
"""
import subprocess
import tempfile
import unittest
from pathlib import Path

from eaos import agent_tools, branches, guided, ledger
from tests.test_continuity import Base, card, git
from tests.test_mcp import git_project


class FolderAbove(unittest.TestCase):
    def test_status_from_the_folder_above_finds_the_one_project_and_asks_when_there_are_two(self):
        import os
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(tmp) / 'home')}):
            work = Path(tmp) / 'workspace'
            project = git_project(work / 'shop')
            answer = agent_tools.status(str(work))
            self.assertEqual(answer['project'], str(project.resolve()))
            git_project(work / 'other')
            answer = agent_tools.status(str(work))
            self.assertEqual(answer['status'], 'needs_project')
            self.assertEqual(sorted(Path(p).name for p in answer['projects']), ['other', 'shop'])


class FieldReport(Base):
    def test_the_report_says_which_commit_it_checked_and_warns_when_the_branch_moved(self):
        checked = git(self.project, 'rev-parse', 'HEAD')
        guided.publish(self.state)
        self.assertEqual(guided.report_stamp(self.state)['scanned_commit'], checked)
        self.assertIsNone(agent_tools.open_report(str(self.project), show=False)['stale'])
        (self.project / 'src/new.js').write_text('export const n = 1;\n')
        git(self.project, 'add', '-A')
        git(self.project, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'the team went on')
        now = git(self.project, 'rev-parse', 'HEAD')
        self.assertEqual(agent_tools.open_report(str(self.project), show=False)['stale'], {'checked': checked, 'now': now})

    def test_a_card_that_needs_a_decision_never_enters_a_batch(self):
        undecided = dict(card(6, 'hidden_coupling', 'src/e.js', 'hidden link between src/e.js and src/f.js'),
                         decision={'readiness': 'decide', 'kind': 'investigate'})
        self.check([*[card(n, 'remove_dead', f'src/{n}.js', f'unused file src/{n}.js') for n in (1, 2)], undecided])
        state = guided.load(self.project)
        state['setup'] = {'commit': state['scanned_commit'], 'ok': True}
        state['safety'] = {'commit': state['scanned_commit']}
        state['consent'] = {'run_and_fix': True}
        guided.save(state)
        answer = agent_tools.fix_start(str(self.project), cards=['TASK-006'])
        self.assertIn('error', answer)
        self.assertIn('decision', answer['error'])
        self.assertIsNone(guided.load(self.project).get('open_wave'), 'no batch is opened')

    def test_a_card_reverted_by_hand_is_no_longer_done(self):
        self.batch(1, ['TASK-001'])
        git(self.project, 'merge', '-q', '--ff-only', 'eaos/wave-1')
        self.assertEqual(agent_tools.status(str(self.project))['progress']['done'], 1)
        git(self.project, '-c', 'user.name=t', '-c', 'user.email=t@t', 'revert', '--no-edit', 'HEAD')
        totals = ledger.sync(guided.load(self.project))['totals']
        self.assertEqual(totals['done'], 0, 'the fix is no longer in the branch: it is not done')

    def test_no_branch_question_when_the_other_branches_are_merged_or_archived(self):
        main = git(self.project, 'rev-parse', '--abbrev-ref', 'HEAD')
        git(self.project, 'branch', 'feature-done')                       # merged: nothing of its own
        (self.project / 'src/later.js').write_text('export const l = 1;\n')
        git(self.project, 'add', '-A')
        git(self.project, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'main went on')
        git(self.project, 'checkout', '-q', '-b', 'archive/old-work', 'feature-done')
        (self.project / 'src/old.js').write_text('export const o = 1;\n')
        git(self.project, 'add', '-A')
        git(self.project, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'kept for the record')
        git(self.project, 'checkout', '-q', main)
        self.assertIsNone(branches.choice(str(self.project)))
        self.assertNotEqual(agent_tools.status(str(self.project)).get('status'), 'needs_branch')


if __name__ == '__main__':
    unittest.main()
