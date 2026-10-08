"""The owner's trial (2026-09-29): a merged batch left its branch behind, the report did not move, and after a new check
the progress said 3 done and the same 339 left. The ledger (eaos/ledger.py), reconcile and merge (eaos/guided.py), and
the handover between assistants (eaos/handover.py)."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos import agent_tools, guided, handover, ledger
from eaos.waves import commit as eaos_commit, plan as read_plan
from tests.test_mcp import git_project


def git(project, *argv):
    return subprocess.run(['git', '-C', str(project), *argv], check=True, capture_output=True, text=True).stdout.strip()


def card(number, pattern, path, title):
    return {'id': f'TASK-{number:03d}', 'pattern': pattern, 'paths': [path], 'title': title, 'kind': 'remediate',
            'decision': {'readiness': 'ready'}}


FIRST = [card(1, 'remove_dead', 'src/a.js', 'unused function `a.old` (line 3)'),
         card(2, 'remove_dead', 'src/a.js', 'unused function `a.older` (line 9)'),
         card(3, 'import_cycle', 'src/b.js', 'Import cycle between: src/b.js, src/c.js'),
         card(4, 'duplicated_rule', 'src/c.js', '2 copies of the same rule'),
         card(5, 'remove_dead', 'src/d.js', 'unused file src/d.js')]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(self.tmp.name) / 'home'), 'EAOS_ASSISTANT': 'Codex'})
        env.start()
        self.addCleanup(env.stop)
        self.project = git_project(Path(self.tmp.name) / 'shop')
        self.state = agent_tools.project_state(str(self.project))
        self.check(FIRST)

    def check(self, cards):
        """A check of the project as it is now: its plan, as the audit would leave it."""
        report = guided.report_of(self.state)
        guided.save(self.state)
        report.mkdir(parents=True, exist_ok=True)
        (report / 'plan.json').write_text(json.dumps({'tasks': cards, 'milestones': [{'id': 'M01', 'name': 'stabilize', 'tasks': [c['id'] for c in cards]}]}))
        (report / 'run-manifest.json').write_text('{"status": "COMPLETE"}')
        (report / 'START-HERE.md').write_text('# Start here\n')
        self.state = guided.load(self.project)
        self.state.update(scanned=f'2026-09-29T{len(self.state.get("waves") or []):02d}:{len(cards):02d}:00+00:00',
                          scanned_commit=git(self.project, 'rev-parse', 'HEAD'), scanned_with=agent_tools.tool_digest())
        guided.save(self.state)
        return ledger.sync(self.state)

    def batch(self, number, fixed, failed=None):
        """What fix_finish leaves: the batch's branch in the project with one EAOS commit per kept card, and its record."""
        cards = {c['id']: c for c in read_plan(guided.report_of(self.state))['tasks']}
        here = git(self.project, 'rev-parse', '--abbrev-ref', 'HEAD')
        git(self.project, 'checkout', '-q', '-b', f'eaos/wave-{number}')
        for card_id in fixed:
            target = self.project / 'src' / f'fix-{card_id}.js'
            target.write_text(f'// {card_id}\n')
            eaos_commit(self.project, cards[card_id], 'assistant')
        tip = git(self.project, 'rev-parse', 'HEAD')
        git(self.project, 'checkout', '-q', here)
        state = guided.load(self.project)
        state.setdefault('waves', []).append({'number': number, 'base': state['scanned_commit'], 'cards': fixed + list(failed or {}),
                                              'kept': fixed, 'failed': failed or {}, 'branch': f'eaos/wave-{number}', 'status': 'applied',
                                              'tip': tip, 'keys': {c: cards[c]['key'] for c in fixed + list(failed or {})}})
        guided.save(state)
        self.state = state

    def branches(self):
        return git(self.project, 'branch', '--list', 'eaos/*').split()


class Continuity(Base):
    def test_a_card_keeps_its_key_when_a_new_check_numbers_it_again(self):
        again = [dict(c, id=f'TASK-{100 - i:03d}', title=c['title'].replace('line 3', 'line 7')) for i, c in enumerate(reversed(FIRST))]
        self.assertEqual(sorted(ledger.keys(FIRST).values()), sorted(ledger.keys(again).values()))
        self.assertEqual(len(set(ledger.keys(FIRST).values())), 5, 'alike cards stay apart')

    def test_accept_merges_deletes_the_branch_and_updates_the_report_at_once(self):
        self.batch(1, ['TASK-001', 'TASK-003'], {'TASK-004': 'skipped: needs a product decision'})
        before = ledger.sync(self.state)['totals']
        self.assertEqual((before['closed'], before['on_branch'], before['skipped']), (0, 2, 1), 'a waiting branch is not done yet')
        self.assertEqual(agent_tools.accept(str(self.project))['status'], 'needs_agreement')
        answer = agent_tools.accept(str(self.project), person_agreed=True)
        self.assertEqual(answer['status'], 'accepted')
        self.assertTrue(answer['branch_deleted'])
        self.assertEqual(self.branches(), [], 'the branch is deleted with the merge, without being asked')
        self.assertEqual((answer['progress']['closed'], answer['progress']['total'], answer['progress']['percent']), (2, 5, 40.0))
        page = guided.outputs(guided.load(self.project)) / 'REPORT.html'
        self.assertTrue(page.is_file(), 'the report is rebuilt in the same call')
        self.assertEqual(agent_tools.status(str(self.project))['next']['tool'], 'run_setup',
                         'no new check is needed after EAOS merged its own fixes')

    def test_a_merge_made_with_git_by_hand_is_recorded_and_its_branch_deleted(self):
        self.batch(1, ['TASK-001', 'TASK-002'])
        git(self.project, 'merge', '-q', '--ff-only', 'eaos/wave-1')          # what the other assistant did
        status = agent_tools.status(str(self.project))
        self.assertEqual(self.branches(), [])
        self.assertEqual(guided.load(self.project)['waves'][0]['status'], 'accepted')
        self.assertEqual((status['progress']['done'], status['progress']['total']), (2, 5))
        history = ledger.load(guided.load(self.project))['history']
        self.assertEqual((history[0]['event'], history[-1]['event'], history[-1]['closed']), ('baseline', 'merged', 2))

    def test_a_branch_an_older_eaos_left_after_its_merge_is_deleted(self):
        self.batch(1, ['TASK-005'])
        git(self.project, 'merge', '-q', '--ff-only', 'eaos/wave-1')
        state = guided.load(self.project)
        state['waves'][0]['status'] = 'accepted'
        guided.save(state)
        agent_tools.status(str(self.project))
        self.assertEqual(self.branches(), [])

    def test_a_new_check_after_the_merge_keeps_the_count_right(self):
        """The trial's numbers: 339 before, then '3 done, 339 left'. Here: 5 before; 2 merged; the new check finds 3 of
        the old (numbered again) and 1 new: 2 closed of 6, 4 open, not 2 done and 5 left."""
        self.batch(1, ['TASK-001', 'TASK-003'])
        agent_tools.accept(str(self.project), person_agreed=True)
        old = {c['id']: c for c in FIRST}
        again = [dict(old['TASK-005'], id='TASK-001'), dict(old['TASK-002'], id='TASK-002', title='unused function `a.older` (line 4)'),
                 dict(old['TASK-004'], id='TASK-003'), card(4, 'access_gap', 'src/e.js', 'an endpoint with no sign-in check')]
        totals = self.check(again)['totals']
        self.assertEqual((totals['closed'], totals['done'], totals['total'], totals['open'], totals['new']), (2, 2, 6, 4, 1))
        cards = ledger.load(guided.load(self.project))['cards'].values()
        self.assertEqual({c['id'] for c in cards if c['state'] == 'done'}, {None}, 'the fixed cards are no longer in the plan')
        self.assertEqual(ledger.load(guided.load(self.project))['history'][-1]['event'], 'recheck')

    def test_a_card_a_new_check_no_longer_finds_is_closed_as_resolved(self):
        totals = self.check(FIRST[1:])['totals']
        self.assertEqual((totals['resolved'], totals['closed'], totals['total']), (1, 1, 5))

    def test_fixes_merged_before_the_ledger_existed_are_read_from_git(self):
        """The owner's project: the batch merged by hand, then a new check numbered everything again."""
        cards = {c['id']: c for c in read_plan(guided.report_of(self.state))['tasks']}
        (self.project / 'src/x.js').write_text('// fixed\n')
        subprocess.run(['git', '-C', str(self.project), 'add', '-A'], check=True)
        subprocess.run(['git', '-C', str(self.project), '-c', 'user.name=EAOS', '-c', 'user.email=eaos@localhost', 'commit', '-qm',
                        f"TASK-001: {cards['TASK-001']['title']}\n\nExecuted by EAOS (assistant)."], check=True)
        ledger.path(self.state).unlink()
        totals = self.check([dict(c, id=f'TASK-{i:03d}') for i, c in enumerate(FIRST[1:], 1)])['totals']
        self.assertEqual((totals['done'], totals['total']), (1, 5))

    def test_a_batch_from_before_keys_follows_its_card_when_a_new_check_numbers_it_again(self):
        self.batch(1, ['TASK-001'])
        state = guided.load(self.project)
        del state['waves'][0]['keys']
        guided.save(state)
        again = [dict(c, id=f'TASK-{6 - i:03d}') for i, c in enumerate(FIRST, 1)]    # the same problems, numbered backwards
        cards = self.check(again)['cards'].values()
        self.assertEqual([c['title'] for c in cards if c['state'] == 'on_branch'], [FIRST[0]['title']])

    def test_a_merge_that_is_not_a_fast_forward_still_merges_and_a_conflict_changes_nothing(self):
        self.batch(1, ['TASK-001'])
        (self.project / 'README.md').write_text('mine\n')
        git(self.project, 'add', '-A')
        git(self.project, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'the person works on')
        self.assertEqual(agent_tools.accept(str(self.project), person_agreed=True)['status'], 'accepted')
        self.assertEqual(self.branches(), [])
        self.batch(2, ['TASK-002'])
        (self.project / 'src/fix-TASK-002.js').write_text('// the person wrote this file too\n')
        git(self.project, 'add', '-A')
        git(self.project, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'same file')
        head = git(self.project, 'rev-parse', 'HEAD')
        self.assertEqual(agent_tools.accept(str(self.project), person_agreed=True)['status'], 'conflict')
        self.assertEqual((git(self.project, 'rev-parse', 'HEAD'), git(self.project, 'status', '--porcelain')), (head, ''))
        self.assertEqual(self.branches(), ['eaos/wave-2'], 'a branch that is not merged stays')

    def test_a_new_batch_waits_for_the_decision_on_the_last(self):
        self.batch(1, ['TASK-001'])
        state = guided.load(self.project)
        state['consent'] = {'run_and_fix': True}
        state['setup'] = {'commit': state['scanned_commit'], 'ok': True}
        guided.save(state)
        self.assertEqual(agent_tools.fix_start(str(self.project))['status'], 'waiting_decision')


class FieldEdges(Base):
    """The edges of the field-report scenarios (acceptance/test_field_report.py) that the acceptance does not walk."""

    def test_a_fix_whose_revert_was_reverted_is_done_again(self):
        self.batch(1, ['TASK-001'])
        git(self.project, 'merge', '-q', '--ff-only', 'eaos/wave-1')
        agent_tools.status(str(self.project))
        for _ in range(2): git(self.project, '-c', 'user.name=t', '-c', 'user.email=t@t', 'revert', '--no-edit', 'HEAD')
        self.assertEqual(ledger.sync(guided.load(self.project))['totals']['done'], 1)

    def test_a_folder_with_a_project_file_is_the_project_even_with_one_repository_under_it(self):
        inner = git_project(self.project / 'vendor' / 'lib').parent.parent
        self.assertEqual(agent_tools.locate(inner), self.project)
        plain = Path(self.tmp.name) / 'plain'
        plain.mkdir()
        self.assertEqual(agent_tools.locate(plain), plain, 'nothing under it: the folder stays, and project_state says why')

    def test_the_folder_above_means_its_one_repository_and_several_are_never_guessed(self):
        above = Path(self.tmp.name)
        self.assertEqual(agent_tools.locate(above), self.project)
        git_project(above / 'other')
        with self.assertRaises(agent_tools.SeveralProjects) as several:
            agent_tools.locate(above)
        self.assertEqual([p.name for p in several.exception.projects], ['other', 'shop'])
        self.assertEqual(agent_tools.status(str(above))['status'], 'needs_project')

    def test_a_ready_card_still_opens_its_batch_past_the_decision_check(self):
        state = guided.load(self.project)
        state['setup'] = {'commit': state['scanned_commit'], 'ok': True}
        state['consent'] = {'run_and_fix': True}
        guided.save(state)
        with mock.patch.object(agent_tools, '_start', return_value={'status': 'started'}) as started:
            self.assertEqual(agent_tools.fix_start(str(self.project), cards=['TASK-001'])['status'], 'started')
        self.assertEqual(started.call_args[0][2], {'cards': ['TASK-001']})


class Handover(Base):
    def test_every_call_is_journaled_and_the_next_assistant_knows_where_to_go_on(self):
        from eaos.mcp_server import _answer
        state = guided.load(self.project)
        state['open_wave'] = {'number': 2, 'root': str(self.project), 'base': 'x', 'cards': ['TASK-002', 'TASK-004', 'TASK-005'],
                              'kept': {'TASK-002': 'abc'}, 'failed': {'TASK-004': 'skipped: needs a product decision'}, 'tools': {}}
        state['consent'] = {'run_and_fix': True}
        guided.save(state)
        _answer(agent_tools.fix_skip)(card='TASK-004', reason='needs a product decision', project=str(self.project))
        handover.note('TASK-005: d.js is only read by the old import script; deleting it next.', 'TASK-005', str(self.project))
        with mock.patch.dict(os.environ, {'EAOS_ASSISTANT': 'Claude Code'}):
            brief = agent_tools.status(str(self.project))['handover']
        self.assertEqual(brief['last_assistant'], 'Codex')
        self.assertEqual(brief['open_work']['left'], ['TASK-005'])
        self.assertIn('fix_edit', brief['open_work']['resume'])
        self.assertIn({'question': 'run the app and prepare fixes', 'answer': True}, brief['person_already_answered'])
        self.assertEqual(brief['notes'][-1]['card'], 'TASK-005')
        self.assertEqual([s['tool'] for s in brief['last_steps']], ['fix_skip', 'note'])
        page = (guided.outputs(guided.load(self.project)) / 'HANDOVER.md').read_text()
        for words in ('Continue from here', 'TASK-005', 'do not ask again', 'deleting it next', 'Codex'):
            self.assertIn(words, page)

    def test_a_new_session_is_told_where_the_work_stopped_and_on_which_card(self):
        from eaos.mcp_server import _answer
        state = guided.load(self.project)
        state['open_wave'] = {'number': 2, 'root': str(self.project), 'base': 'x', 'cards': ['TASK-002', 'TASK-005'],
                              'kept': {'TASK-002': 'abc'}, 'failed': {}, 'tools': {}}
        guided.save(state)
        _answer(agent_tools.finding)(id='TASK-005', project=str(self.project))
        _answer(agent_tools.fix_read)(path='src/a.js', project=str(self.project))
        context = handover.hook_context(self.project / 'src')           # opened in a sub-folder of the project
        for words in ('batch 2 is open', 'Codex was on TASK-005', 'src/a.js', 'call the eaos `status` tool'):
            self.assertIn(words, context)
        self.assertEqual(agent_tools.status(str(self.project))['handover']['in_progress']['card'], 'TASK-005')
        self.assertIsNone(handover.hook_context(Path(self.tmp.name)), 'a folder EAOS knows nothing of adds nothing')
        import io, sys
        from eaos import cli
        with mock.patch.object(sys, 'stdin', io.StringIO(json.dumps({'cwd': str(self.project), 'hook_event_name': 'SessionStart'}))), \
                mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            cli.handover_hook(None)
        self.assertEqual(json.loads(out.getvalue())['hookSpecificOutput']['hookEventName'], 'SessionStart')

    def test_a_broken_hook_never_stops_a_session(self):
        import io, sys
        from eaos import cli
        for stdin, failing in (('{not json', False), (json.dumps({'cwd': str(self.project)}), True)):
            with mock.patch.object(sys, 'stdin', io.StringIO(stdin)), mock.patch('sys.stdout', new_callable=io.StringIO) as out, \
                    mock.patch('eaos.handover.brief', side_effect=RuntimeError('broken state')) if failing else mock.patch('os.getcwd', return_value='/'):
                self.assertEqual(cli.handover_hook(None), 0)
            self.assertEqual(out.getvalue(), '', 'nothing printed: the session starts as if EAOS were not there')

    def test_the_person_is_told_where_it_stopped_and_what_to_write(self):
        from tests.test_guided import run
        state = guided.load(self.project)
        state['open_wave'] = {'number': 1, 'root': str(self.project), 'base': 'x', 'cards': ['TASK-001', 'TASK-003'],
                              'kept': {'TASK-001': 'abc'}, 'failed': {}, 'tools': {}}
        guided.save(state)
        handover.note('checking TASK-003 next', 'TASK-003', str(self.project))
        code, printed = run('handover', self.project, lang='ar')
        self.assertEqual(code, 0)
        for words in ('الدفعة 1', 'حُفظ 1، باقي 1', 'كمّل شغل EAOS', 'Codex'):
            self.assertIn(words, printed)

    def test_a_failing_handover_never_costs_the_tool_its_answer(self):
        from eaos.mcp_server import _answer
        with mock.patch('eaos.handover.refresh', side_effect=OSError('disk full')):
            answer = json.loads(_answer(agent_tools.plan)(project=str(self.project)))
        self.assertIn('milestones', answer)
        self.assertEqual(answer['progress']['total'], 5)


if __name__ == '__main__':
    unittest.main()
