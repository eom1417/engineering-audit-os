"""The owner's second finding (2026-09-29): a project whose work went on in a branch far ahead of main was checked on
whatever was checked out, and nothing said which branch. EAOS asks which branch when there is a real choice, and the
check, the fixes, the merges, the progress and the report follow it (eaos/core/project/branches.py, guided.choose/source)."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.journeys import agent_tools, guided
from eaos.journeys.fix import finish as batch_finish
from eaos.core.project import branches, ledger
from eaos.live.app import setup as live_setup
from eaos.journeys.fix.waves import commit as eaos_commit, plan as read_plan
from eaos.core.project import places, state as project_state


def card(number, pattern, path, title):
    return {'id': f'TASK-{number:03d}', 'pattern': pattern, 'paths': [path], 'title': title, 'kind': 'remediate',
            'decision': {'readiness': 'ready'}}


FIRST = [card(1, 'remove_dead', 'src/a.js', 'unused function `a.old` (line 3)'),
         card(2, 'remove_dead', 'src/a.js', 'unused function `a.older` (line 9)'),
         card(3, 'import_cycle', 'src/b.js', 'Import cycle between: src/b.js, src/c.js'),
         card(4, 'duplicated_rule', 'src/c.js', '2 copies of the same rule'),
         card(5, 'remove_dead', 'src/d.js', 'unused file src/d.js')]


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
        quick = mock.patch.object(agent_tools.where, 'ANSWER_SECONDS', 0)
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
        state = project_state.load(self.project)
        report = guided.report_of(state)
        guided.save(state)
        report.mkdir(parents=True, exist_ok=True)
        (report / 'plan.json').write_text(json.dumps({'tasks': cards, 'milestones': [{'id': 'M01', 'name': 'stabilize', 'tasks': [c['id'] for c in cards]}]}))
        (report / 'run-manifest.json').write_text('{"status": "COMPLETE"}')
        (report / 'START-HERE.md').write_text('# Start here\n')
        state = project_state.load(self.project)
        state.update(scanned='2026-09-29T10:00:00+00:00', scanned_commit=guided.tip(state), scanned_with=agent_tools.tool_digest())
        guided.save(state)
        guided.publish(state)
        return state

    def test_the_branches_offered_are_the_persons_and_the_one_ahead_is_recommended_and_one_branch_is_no_question(self):
        git(self.project, 'branch', 'merged-long-ago')
        git(self.project, 'branch', 'archive/develop-copy', 'develop')
        options = branches.choice(self.project)
        self.assertEqual(sorted(r['name'] for r in options['branches']), ['develop', 'main'])
        develop = next(r for r in options['branches'] if r['name'] == 'develop')
        self.assertEqual((develop['ahead_of_main'], develop['behind_main'], develop['checked_out']), (3, 0, False))
        self.assertEqual((options['recommended'], options['main']), ('develop', 'main'))
        for name in ('develop', 'merged-long-ago', 'archive/develop-copy'): git(self.project, 'branch', '-D', name)
        self.assertIsNone(branches.choice(self.project))
        status = agent_tools.status(str(self.project))
        self.assertEqual((status['branch'], status['next']['tool']), ('main', 'audit'), 'the branch checked out, without asking')

    def test_status_asks_which_branch_before_anything_and_audit_waits_for_it(self):
        status = agent_tools.status(str(self.project))
        self.assertEqual((status['status'], status['next']['tool'], status['recommended']), ('needs_branch', 'choose_branch', 'develop'))
        self.assertEqual(agent_tools.audit(str(self.project))['status'], 'needs_branch')
        self.assertEqual(agent_tools.choose_branch('develop', str(self.project))['status'], 'needs_the_person', 'never chosen for them')
        with mock.patch.object(agent_tools.where, 'ANSWER_SECONDS', 30):
            self.assertEqual(agent_tools.choose_branch('develop', str(self.project), person_said='develop')['status'], 'needs_the_person',
                             'an "answer" seconds after the question is nobody\'s')
        self.assertIsNone(project_state.load(self.project).get('branch'))
        self.choose('develop', self.project, 'develop please')
        self.assertEqual(agent_tools.status(str(self.project))['branch'], 'develop')

    def test_the_chosen_branch_is_read_from_its_own_copy_and_the_checkout_is_not_switched(self):
        self.choose('develop', self.project, 'develop please')
        source = guided.source(project_state.load(self.project))
        self.assertNotEqual(source, self.project)
        self.assertEqual((source / 'app.js').read_text(), 'export const version = 4;\n')
        self.assertEqual((branches.checked_out(self.project), (self.project / 'app.js').read_text()), ('main', 'export const version = 1;\n'))
        git(self.project, 'checkout', '-q', 'develop')
        self.assertEqual(guided.source(project_state.load(self.project)), self.project, 'checked out: the project itself')
        clone = Path(self.tmp.name) / 'clone'
        subprocess.run(['git', 'clone', '-q', '-b', 'main', str(self.project), str(clone)], check=True)
        self.assertEqual(git(clone, 'branch', '--list', 'develop'), '')
        self.assertIn('develop', [r['name'] for r in branches.inventory(clone)])
        self.choose('develop', clone, 'develop please')
        self.assertEqual(git(clone, 'rev-parse', 'develop'), git(self.project, 'rev-parse', 'develop'), 'a branch only on origin gets its local branch')

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
        state = project_state.load(self.project)
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
        page = (guided.outputs(project_state.load(self.project)) / 'REPORT.html').read_text()
        self.assertIn('data-part="branch"', page)
        self.assertIn('develop', page)

    def test_the_fix_preview_sets_the_base_the_new_branch_and_where_it_merges_and_a_moved_base_opens_nothing(self):
        """The owner's trial: the batch was built on develop and named eaos/wave-1 on every branch, with no word of either;
        a second branch's batch 1 would overwrite the first's waiting branch."""
        self.choose('develop', self.project, 'develop please')
        state = self.check()
        state.update(consent={'run_and_fix': True}, setup={'commit': state['scanned_commit'], 'ok': True},
                     safety={'commit': state['scanned_commit'], 'screens': 1, 'passed': 1})
        guided.save(state)
        develop = git(self.project, 'rev-parse', 'develop')
        moved = agent_tools.fix_start(str(self.project), base='develop', base_commit=git(self.project, 'rev-parse', 'develop~1'))
        self.assertEqual((moved['status'], moved['now']), ('base_moved', develop))
        with mock.patch.object(agent_tools.fixing, '_start', return_value={'status': 'started'}) as started:
            agent_tools.fix_start(str(self.project), base='develop', base_commit=develop[:7], merge_into='develop')
        self.assertEqual(started.call_args[0][2], {'cards': ['TASK-001', 'TASK-002', 'TASK-003', 'TASK-004', 'TASK-005'],
                                                   'deliver_as': 'eaos/develop/wave-1', 'merge_into': 'develop', 'assistants': 1})
        self.assertEqual(agent_tools.delivery(project_state.load(self.project)), ('eaos/develop/wave-1', 'main'),
                         'by default it merges into the branch open in the project folder')
        # Accept merges into the branch the preview named, here release, a branch neither checked out nor worked on.
        git(self.project, 'branch', 'release', 'develop')
        copy = Path(self.tmp.name) / 'candidate'
        subprocess.run(['git', 'clone', '-q', '-b', 'develop', str(self.project), str(copy)], check=True)
        (copy / 'fix.js').write_text('// a fix\n')
        cards = {c['id']: c for c in read_plan(guided.report_of(state))['tasks']}
        eaos_commit(copy, cards['TASK-001'], 'assistant')
        git(self.project, 'fetch', '-q', str(copy), '+HEAD:refs/heads/eaos/develop/wave-1')
        state = project_state.load(self.project)
        state['waves'] = [{'number': 1, 'base': develop, 'cards': ['TASK-001'], 'kept': ['TASK-001'], 'failed': {}, 'merge_into': 'release',
                           'branch': 'eaos/develop/wave-1', 'status': 'applied', 'keys': {'TASK-001': cards['TASK-001']['key']}}]
        guided.save(state)
        self.assertEqual(agent_tools.accept(str(self.project), person_agreed=True)['status'], 'accepted')
        self.assertEqual((git(self.project, 'show', 'release:fix.js'), git(self.project, 'rev-parse', 'develop')), ('// a fix', develop))

    def ready_to_fix(self):
        """develop chosen and checked, the person agreed, the app runs and its screens are recorded."""
        self.choose('develop', self.project, 'develop please')
        state = self.check()
        state.update(consent={'run_and_fix': True}, setup={'commit': state['scanned_commit'], 'ok': True},
                     safety={'commit': state['scanned_commit'], 'screens': 1, 'passed': 1})
        guided.save(state)
        live_setup.authorize(guided.source(state), project_state.runtime_of(state), 'tester')

    def batch(self, card, **where):
        """One batch of `card` through the real jobs: its change made in the copy as an assistant would, every gate passing."""
        agent_tools._fix_start_job(str(self.project), {'cards': [card], **where}, lambda *_: None)
        state = project_state.load(self.project)
        wave = state['open_wave']
        root = Path(wave['root'])
        (root / f'{card}.js').write_text(f'// {card} fixed\n')
        cards = {c['id']: c for c in read_plan(guided.report_of(state))['tasks']}
        wave['kept'][card] = eaos_commit(root, cards[card], 'assistant')
        guided.save(state)
        with mock.patch('eaos.journeys.fix.waves.batch.gates', return_value=''), mock.patch('eaos.journeys.fix.waves.batch.original_checks', return_value={}), \
                mock.patch('eaos.journeys.fix.waves.batch.batch_acceptance', side_effect=lambda report, chosen, root, collected=None: {c['id']: None for c in chosen}):
            return batch_finish.finish_job(str(self.project), {}, lambda *_: None)

    def work_branches(self):
        return sorted(set(git(self.project, 'for-each-ref', '--format=%(refname:short)', 'refs/heads/eaos/').split()) - {'eaos/wave-9'})

    def test_a_group_continues_on_a_waiting_work_branch_and_one_accept_takes_both(self):
        """The owner (2026-10-12): branches where features are built and never merged must not pile up; a group may go on
        on the EAOS branch still waiting, on top of its commits."""
        self.ready_to_fix()
        first = self.batch('TASK-001')
        self.assertEqual(first['branch'], 'eaos/develop/wave-1')
        with mock.patch.object(agent_tools.fixing, '_start', return_value={'status': 'started'}) as started:
            agent_tools.fix_start(str(self.project), cards=['TASK-002'], deliver_as='eaos/develop/wave-1')
        self.assertEqual(started.call_args[0][2], {'cards': ['TASK-002'], 'deliver_as': 'eaos/develop/wave-1', 'merge_into': 'main', 'assistants': 1},
                         'a waiting work branch is no refusal when the batch goes on it')
        second = self.batch('TASK-002', deliver_as='eaos/develop/wave-1', merge_into='develop')
        self.assertEqual((second['branch'], second['continued_on']), ('eaos/develop/wave-1', 'eaos/develop/wave-1'))
        self.assertEqual(git(self.project, 'rev-parse', 'eaos/develop/wave-1~1'), project_state.load(self.project)['waves'][0]['tip'],
                         'the second batch is on top of the first')
        self.assertEqual(self.work_branches(), ['eaos/develop/wave-1'])
        self.assertEqual(agent_tools.accept(str(self.project), person_agreed=True)['status'], 'accepted')
        self.assertEqual((git(self.project, 'show', 'develop:TASK-001.js'), git(self.project, 'show', 'develop:TASK-002.js')),
                         ('// TASK-001 fixed', '// TASK-002 fixed'))
        self.assertEqual([w['status'] for w in project_state.load(self.project)['waves']], ['accepted', 'accepted'])
        self.assertEqual(self.work_branches(), [])

    def test_a_direct_group_lands_on_the_base_branch_and_leaves_no_branch(self):
        self.ready_to_fix()
        with self.assertRaises(ValueError): agent_tools.delivery({**project_state.load(self.project), 'branch': 'main'}, 'main')
        main = git(self.project, 'rev-parse', 'main')
        done = self.batch('TASK-001', deliver_as='develop', merge_into='develop')
        self.assertEqual((done['branch'], done['landed_on'], done['kept']), (None, 'develop', ['TASK-001']), done)
        self.assertEqual(git(self.project, 'show', 'develop:TASK-001.js'), '// TASK-001 fixed')
        self.assertEqual((self.work_branches(), git(self.project, 'rev-parse', 'main')), ([], main), 'no branch left, main untouched')
        self.assertEqual(project_state.load(self.project)['waves'][-1]['status'], 'accepted')
        self.assertEqual(ledger.load(project_state.load(self.project))['totals']['done'], 1)

    def test_accept_merges_into_the_chosen_branch_and_keeps_the_branch_when_asked(self):
        self.ready_to_fix()
        git(self.project, 'branch', 'release', 'develop')
        self.batch('TASK-001')
        # MCP's accept keeps the Studio's rule (M3.3): never into a branch the project's policy protects
        git(self.project, 'branch', 'stable', 'develop')
        policy = places.workspace(self.project) / 'runs' / 'branch-policy.json'
        policy.parent.mkdir(parents=True, exist_ok=True)
        policy.write_text(json.dumps({'protected': ['stable']}))
        refused = agent_tools.accept(str(self.project), person_agreed=True, merge_into='stable')
        self.assertEqual(refused['status'], 'error', refused)
        self.assertIn('stable is protected', refused['error'])
        answer = agent_tools.accept(str(self.project), person_agreed=True, merge_into='release', delete_after=False)
        self.assertEqual((answer['status'], answer['merged_into'], answer['branch_deleted']), ('accepted', 'release', False), answer)
        self.assertEqual(git(self.project, 'show', 'release:TASK-001.js'), '// TASK-001 fixed')
        agent_tools.status(str(self.project))
        self.assertEqual(self.work_branches(), ['eaos/develop/wave-1'], 'kept, merged, after the next status too')

    def test_each_branch_keeps_its_own_check_progress_and_report(self):
        self.choose('develop', self.project, 'develop please')
        self.check()
        self.choose('main', self.project, 'main')
        state = project_state.load(self.project)
        self.assertFalse(guided.scan_done(state), 'main has not been checked')
        self.assertEqual(guided.report_of(state), guided.outputs(state) / 'branches' / 'main' / 'technical')
        self.assertNotEqual(ledger.path(state).name, 'ledger.json')
        self.check(FIRST[:2])
        main_page = guided.outputs(state) / 'branches' / 'main' / 'REPORT.html'
        self.assertIn('href="../../REPORT.html"', main_page.read_text(), 'a link to the develop report')
        back = self.choose('develop', self.project, 'develop please')
        self.assertTrue(back['checked_before'])
        self.assertEqual(ledger.load(project_state.load(self.project))['totals']['total'], 5, "develop's own ledger")

    def test_work_from_before_branches_stays_with_its_branch_and_the_branch_cannot_change_mid_batch(self):
        state = agent_tools.state_of(str(self.project))
        state.update(scanned='before', scanned_commit=git(self.project, 'rev-parse', 'main'), setup={'commit': 'x', 'ok': True})
        guided.save(state)
        self.choose('develop', self.project, 'develop please')
        state = project_state.load(self.project)
        self.assertEqual((state['home_branch'], state['by_branch']['main']['scanned']), ('main', 'before'))
        self.assertNotIn('setup', state)
        state['open_wave'] = {'number': 1, 'root': '', 'base': git(self.project, 'rev-parse', 'develop'), 'cards': [], 'kept': {}, 'failed': {}}
        guided.save(state)
        with self.assertRaises(ValueError): self.choose('main', self.project, 'main')


if __name__ == '__main__':
    unittest.main()
