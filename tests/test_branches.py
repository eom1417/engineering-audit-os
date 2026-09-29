"""The owner's second finding (2026-09-29): a project whose work went on in a branch far ahead of main was checked on
whatever was checked out, and nothing said which branch. EAOS asks which branch when there is a real choice, and the
check, the fixes, the merges, the progress and the report follow it (eaos/branches.py, guided.choose/source)."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos import agent_tools, branches, guided, ledger
from eaos.waves import commit as eaos_commit, plan as read_plan
from tests.test_continuity import FIRST


def git(project, *argv):
    return subprocess.run(['git', '-C', str(project), '-c', 'user.name=t', '-c', 'user.email=t@t', *argv],
                          check=True, capture_output=True, text=True).stdout.strip()


class Branches(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(self.tmp.name) / 'home'), 'EAOS_ASSISTANT': 'Codex'})
        env.start()
        self.addCleanup(env.stop)
        quick = mock.patch.object(agent_tools, 'ANSWER_SECONDS', 0)
        quick.start()
        self.addCleanup(quick.stop)
        self.project = p = Path(self.tmp.name) / 'shop'
        p.mkdir()
        (p / 'package.json').write_text('{"name": "shop"}\n')
        (p / 'app.js').write_text('export const version = 1;\n')
        git(p, 'init', '-q', '-b', 'main')
        git(p, 'add', '-A')
        git(p, 'commit', '-qm', 'production')
        git(p, 'checkout', '-q', '-b', 'develop')
        for n in range(2, 5):
            (p / 'app.js').write_text(f'export const version = {n};\n')
            git(p, 'commit', '-qam', f'work {n}')
        git(p, 'checkout', '-q', 'main')
        git(p, 'branch', 'dependabot/npm/left-pad-2')             # a bot's branch is never offered
        git(p, 'branch', 'eaos/wave-9')                           # nor one of EAOS's own

    def choose(self, branch, where, said):
        """The person was asked (status) and answered."""
        agent_tools.status(str(where))
        return agent_tools.choose_branch(branch, str(where), person_said=said)

    def check(self, cards=FIRST):
        state = guided.load(self.project)
        report = guided.report_of(state)
        guided.save(state)
        report.mkdir(parents=True, exist_ok=True)
        (report / 'plan.json').write_text(json.dumps({'tasks': cards, 'milestones': [{'id': 'M01', 'name': 'stabilize', 'tasks': [c['id'] for c in cards]}]}))
        (report / 'run-manifest.json').write_text('{"status": "COMPLETE"}')
        (report / 'START-HERE.md').write_text('# Start here\n')
        state = guided.load(self.project)
        state.update(scanned='2026-09-29T10:00:00+00:00', scanned_commit=guided.tip(state), scanned_with=agent_tools.tool_digest())
        guided.save(state)
        guided.publish(state)
        return state

    def test_the_branches_offered_are_the_persons_and_the_one_ahead_is_recommended(self):
        options = branches.choice(self.project)
        self.assertEqual(sorted(r['name'] for r in options['branches']), ['develop', 'main'])
        develop = next(r for r in options['branches'] if r['name'] == 'develop')
        self.assertEqual((develop['ahead_of_main'], develop['behind_main'], develop['checked_out']), (3, 0, False))
        self.assertEqual((options['recommended'], options['main']), ('develop', 'main'))

    def test_one_branch_is_not_a_question(self):
        git(self.project, 'branch', '-D', 'develop')
        self.assertIsNone(branches.choice(self.project))
        status = agent_tools.status(str(self.project))
        self.assertEqual((status['branch'], status['next']['tool']), ('main', 'audit'), 'the branch checked out, without asking')

    def test_status_asks_which_branch_before_anything_and_audit_waits_for_it(self):
        status = agent_tools.status(str(self.project))
        self.assertEqual((status['status'], status['next']['tool'], status['recommended']), ('needs_branch', 'choose_branch', 'develop'))
        self.assertEqual(agent_tools.audit(str(self.project))['status'], 'needs_branch')
        self.assertEqual(agent_tools.choose_branch('develop', str(self.project))['status'], 'needs_the_person', 'never chosen for them')
        with mock.patch.object(agent_tools, 'ANSWER_SECONDS', 30):
            self.assertEqual(agent_tools.choose_branch('develop', str(self.project), person_said='develop')['status'], 'needs_the_person',
                             'an "answer" seconds after the question is nobody\'s')
        self.assertIsNone(guided.load(self.project).get('branch'))
        self.choose('develop', self.project, 'develop please')
        self.assertEqual(agent_tools.status(str(self.project))['branch'], 'develop')

    def test_the_chosen_branch_is_read_from_its_own_copy_and_the_checkout_is_not_switched(self):
        self.choose('develop', self.project, 'develop please')
        source = guided.source(guided.load(self.project))
        self.assertNotEqual(source, self.project)
        self.assertEqual((source / 'app.js').read_text(), 'export const version = 4;\n')
        self.assertEqual((branches.checked_out(self.project), (self.project / 'app.js').read_text()), ('main', 'export const version = 1;\n'))
        git(self.project, 'checkout', '-q', 'develop')
        self.assertEqual(guided.source(guided.load(self.project)), self.project, 'checked out: the project itself')

    def test_a_merge_goes_into_the_chosen_branch_and_main_stays_as_it_is(self):
        self.choose('develop', self.project, 'develop please')
        state = self.check()
        cards = {c['id']: c for c in read_plan(guided.report_of(state))['tasks']}
        copy = Path(self.tmp.name) / 'candidate'
        subprocess.run(['git', 'clone', '-q', '-b', 'develop', str(self.project), str(copy)], check=True)
        git(copy, 'checkout', '-q', '-b', 'eaos/wave-1')
        (copy / 'fix.js').write_text('// a fix\n')
        eaos_commit(copy, cards['TASK-001'], 'assistant')
        git(self.project, 'fetch', '-q', str(copy), 'eaos/wave-1:eaos/wave-1')
        state = guided.load(self.project)
        state['waves'] = [{'number': 1, 'base': state['scanned_commit'], 'cards': ['TASK-001'], 'kept': ['TASK-001'], 'failed': {},
                           'branch': 'eaos/wave-1', 'status': 'applied', 'keys': {'TASK-001': cards['TASK-001']['key']}}]
        guided.save(state)
        main_before = git(self.project, 'rev-parse', 'main')
        answer = agent_tools.accept(str(self.project), person_agreed=True)
        self.assertEqual(answer['status'], 'accepted')
        self.assertEqual(git(self.project, 'rev-parse', 'main'), main_before, 'main is untouched')
        self.assertEqual(git(self.project, 'show', 'develop:fix.js'), '// a fix', 'the fix is in develop')
        self.assertEqual((branches.checked_out(self.project), git(self.project, 'status', '--porcelain')), ('main', ''))
        self.assertNotIn('eaos/wave-1', git(self.project, 'branch', '--list', 'eaos/*'))
        self.assertEqual((answer['progress']['done'], answer['progress']['total']), (1, 5))
        page = (guided.outputs(guided.load(self.project)) / 'REPORT.html').read_text()
        self.assertIn('data-part="branch"', page)
        self.assertIn('develop', page)

    def test_each_branch_keeps_its_own_check_progress_and_report(self):
        self.choose('develop', self.project, 'develop please')
        self.check()
        self.choose('main', self.project, 'main')
        state = guided.load(self.project)
        self.assertFalse(guided.scan_done(state), 'main has not been checked')
        self.assertEqual(guided.report_of(state), guided.outputs(state) / 'branches' / 'main' / 'technical')
        self.assertNotEqual(ledger.path(state).name, 'ledger.json')
        self.check(FIRST[:2])
        main_page = guided.outputs(state) / 'branches' / 'main' / 'REPORT.html'
        self.assertIn('href="../../REPORT.html"', main_page.read_text(), 'a link to the develop report')
        back = self.choose('develop', self.project, 'develop please')
        self.assertTrue(back['checked_before'])
        self.assertEqual(ledger.load(guided.load(self.project))['totals']['total'], 5, "develop's own ledger")

    def test_a_branch_only_on_origin_gets_its_local_branch(self):
        clone = Path(self.tmp.name) / 'clone'
        subprocess.run(['git', 'clone', '-q', str(self.project), str(clone)], check=True)
        self.assertEqual(git(clone, 'branch', '--list', 'develop'), '')
        self.assertIn('develop', [r['name'] for r in branches.inventory(clone)])
        self.choose('develop', clone, 'develop please')
        self.assertEqual(git(clone, 'rev-parse', 'develop'), git(self.project, 'rev-parse', 'develop'))

    def test_work_from_before_branches_stays_with_the_branch_it_was_done_on(self):
        state = agent_tools.project_state(str(self.project))
        state.update(scanned='before', scanned_commit=git(self.project, 'rev-parse', 'main'), setup={'commit': 'x', 'ok': True})
        guided.save(state)
        self.choose('develop', self.project, 'develop please')
        state = guided.load(self.project)
        self.assertEqual((state['home_branch'], state['by_branch']['main']['scanned']), ('main', 'before'))
        self.assertNotIn('setup', state)

    def test_the_branch_cannot_change_in_the_middle_of_a_batch(self):
        self.choose('develop', self.project, 'develop please')
        state = guided.load(self.project)
        state['open_wave'] = {'number': 1, 'cards': [], 'kept': {}, 'failed': {}}
        guided.save(state)
        with self.assertRaises(ValueError): self.choose('main', self.project, 'main')


if __name__ == '__main__':
    unittest.main()
