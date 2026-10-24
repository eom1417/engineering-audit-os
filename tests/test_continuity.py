"""The owner's trial (2026-09-29): a merged batch left its branch behind, the report did not move, and after a new check
the progress said 3 done and the same 339 left. The ledger (eaos/core/ledger.py), reconcile and merge (eaos/journeys/guided.py), and
the handover between assistants (eaos/journeys/handover.py)."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.journeys import agent_tools, batch_finish, guided, handover
from eaos.core import ledger
from eaos.journeys.waves import commit as eaos_commit, plan as read_plan
from tests.test_mcp import git_project
from eaos.core import project_state


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
        self.state = agent_tools.state_of(str(self.project))
        self.check(FIRST)

    def check(self, cards):
        """A check of the project as it is now: its plan, as the audit would leave it."""
        report = guided.report_of(self.state)
        guided.save(self.state)
        report.mkdir(parents=True, exist_ok=True)
        (report / 'plan.json').write_text(json.dumps({'tasks': cards, 'milestones': [{'id': 'M01', 'name': 'stabilize', 'tasks': [c['id'] for c in cards]}]}))
        (report / 'run-manifest.json').write_text('{"status": "COMPLETE"}')
        (report / 'START-HERE.md').write_text('# Start here\n')
        self.state = project_state.load(self.project)
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
        state = project_state.load(self.project)
        state.setdefault('waves', []).append({'number': number, 'base': state['scanned_commit'], 'cards': fixed + list(failed or {}),
                                              'kept': fixed, 'failed': failed or {}, 'branch': f'eaos/wave-{number}', 'status': 'applied',
                                              'tip': tip, 'keys': {c: cards[c]['key'] for c in fixed + list(failed or {})}})
        guided.save(state)
        self.state = state

    def branches(self):
        return git(self.project, 'branch', '--list', 'eaos/*').split()


class Continuity(Base):
    def test_a_batch_is_drawn_on_the_live_map_from_its_state_card_by_card_to_its_handover(self):
        # owner, 2026-10-15: no batch ever showed on the live map, nothing wrote the flow `fix`, it read "waiting" throughout
        from eaos.core import progress
        state = project_state.load(self.project)
        state['open_wave'] = {'number': 9, 'cards': ['TASK-001', 'TASK-002', 'TASK-003'], 'kept': {'TASK-001': 'a1'},
                              'failed': {'TASK-002': 'skipped: too large'}, 'opened': '2026-10-15T09:00:00+00:00'}
        guided.save(state)
        read = lambda: {s['name']: s for s in progress.fold(progress.read(project_state.runtime_of(state), 'fix'))['stages']}
        drawn = read()
        self.assertEqual((drawn['open']['state'], drawn['change']['state']), ('ok', 'running'))
        self.assertEqual([(c['name'], c['status']) for c in drawn['change']['steps']], [('TASK-001', 'ok'), ('TASK-002', 'skipped')])
        state['open_wave']['phases'] = {'acceptance': '2026-10-15T09:20:00+00:00'}
        guided.save(state)
        self.assertEqual((read()['change']['state'], read()['acceptance']['state']), ('ok', 'running'))
        state['waves'] = (state.get('waves') or []) + [{**state.pop('open_wave'), 'status': 'applied', 'branch': 'eaos/wave-9'}]
        guided.save(state)
        self.assertEqual(progress.fold(progress.read(project_state.runtime_of(state), 'fix'))['status'], 'COMPLETE')

    def test_a_card_keeps_its_key_across_checks_and_one_no_longer_found_leaves_the_ledger(self):
        again = [dict(c, id=f'TASK-{100 - i:03d}', title=c['title'].replace('line 3', 'line 7')) for i, c in enumerate(reversed(FIRST))]
        self.assertEqual(sorted(ledger.keys(FIRST).values()), sorted(ledger.keys(again).values()))
        self.assertEqual(len(set(ledger.keys(FIRST).values())), 5, 'alike cards stay apart')
        # The incident (898 cards, 58.9% with no fix): a hotspot's title names the tools that saw it, so the next check
        # gave it a new key. The observation's uid keys it, whatever the words; a problem no longer found is not progress.
        hotspot = dict(FIRST[3], decision={'readiness': 'ready', 'observation_uid': 'OBS-1'}, title='3 tools (codegraph, complexipy, reforge)')
        self.assertEqual(ledger.key(hotspot), ledger.key(dict(hotspot, title='4 tools (codegraph, complexipy, lizard, reforge)')))
        totals = self.check(FIRST[1:])['totals']
        self.assertEqual((totals['closed'], totals['total'], totals['percent']), (0, 4, 0.0))

    def test_a_batch_left_on_code_that_moved_on_is_retired_and_a_failed_finish_leaves_it_as_it_was(self):
        """The owner's trial (2026-10-10): batch 1 outlived four checks; every fix_finish failed after rewriting its copy,
        status kept sending the assistant back to it, and each run_setup added one more consent question."""
        state = project_state.load(self.project)
        state.update(consent={'run_and_fix': True}, setup={'commit': state['scanned_commit'], 'ok': True},
                     safety={'commit': state['scanned_commit'], 'screens': 1, 'passed': 1})
        copy = project_state.runtime_of(state) / 'candidates/WAVE-1'
        subprocess.run(['git', 'clone', '-q', str(self.project), str(copy)], check=True)
        base = git(copy, 'rev-parse', 'HEAD')
        (copy / 'src/a.js').write_text('// fixed\n')
        cards = {c['id']: c for c in read_plan(guided.report_of(state))['tasks']}
        kept = eaos_commit(copy, cards['TASK-001'], 'assistant')
        state['open_wave'] = {'number': 1, 'root': str(copy), 'base': base, 'cards': ['TASK-001'], 'kept': {'TASK-001': kept},
                              'failed': {}, 'tools': {}, 'keys': {'TASK-001': cards['TASK-001']['key']}}
        guided.save(state)

        def refused(*_, **__):                                   # it rewrites the copy, then the gate refuses it
            git(copy, 'reset', '-q', '--hard', base)
            raise PermissionError('S09: the copy does not descend from the authorised commit')
        def stopped(*_, **__):                                   # the person stops it while it halves the batch
            git(copy, 'reset', '-q', '--hard', base)
            raise KeyboardInterrupt
        with mock.patch('eaos.journeys.waves.finish_batch', side_effect=stopped), self.assertRaises(KeyboardInterrupt):
            batch_finish.finish_job(str(self.project), {}, lambda *_: None)
        wave = project_state.load(self.project)['open_wave']
        self.assertEqual((git(copy, 'rev-parse', 'HEAD'), wave.get('last_error')), (kept, None), 'stopped: whole, and nothing failed')
        with mock.patch('eaos.journeys.waves.finish_batch', side_effect=refused), self.assertRaises(PermissionError):
            batch_finish.finish_job(str(self.project), {}, lambda *_: None)
        wave = project_state.load(self.project)['open_wave']
        self.assertEqual((git(copy, 'rev-parse', 'HEAD'), list(wave['kept'])), (kept, ['TASK-001']), 'the batch as it was')
        self.assertIn('S09', wave['last_error'])
        self.assertEqual(agent_tools.status(str(self.project))['next']['tool'], 'fix_abandon')
        # The person commits: a batch with kept changes goes on (EAOS lost one so, mid hand-over), its merge says the rest;
        # the person closes it, its copy removed.
        (self.project / 'src/e.js').write_text('export const e = 1;\n')
        git(self.project, 'add', '-A')
        git(self.project, '-c', 'user.name=a', '-c', 'user.email=a@b', 'commit', '-qm', 'the person works')
        answer = agent_tools.status(str(self.project))
        self.assertIsNotNone(answer['open_batch'])
        self.assertIsNone(answer.get('retired_batch'))
        agent_tools.fix_abandon(str(self.project))
        state = project_state.load(self.project)
        self.assertEqual((state['waves'][-1]['status'], copy.exists()), ('abandoned', False))
        from eaos.core import ledger
        self.assertEqual({c['state'] for c in ledger.load(state)['cards'].values() if c['id'] == 'TASK-001'}, {'open'},
                         'its cards are free at once, not left "in the batch" for every next one to refuse')
        from eaos.live import setup as live_setup
        with mock.patch('eaos.live.setup.authorize'), mock.patch('eaos.live.setup.detect', return_value=live_setup._unknown_app()), \
                mock.patch('eaos.journeys.agent_tools._start'):
            for _ in range(2): agent_tools.run_setup(str(self.project), person_agreed=True)
        self.assertEqual(sum(q['id'] == 'run_and_fix' for q in project_state.load(self.project)['questions']), 1, 'asked once')

    def test_a_batch_from_before_keys_follows_its_card_when_a_new_check_numbers_it_again(self):
        self.batch(1, ['TASK-001'])
        state = project_state.load(self.project)
        del state['waves'][0]['keys']
        guided.save(state)
        again = [dict(c, id=f'TASK-{6 - i:03d}') for i, c in enumerate(FIRST, 1)]    # the same problems, numbered backwards
        cards = self.check(again)['cards'].values()
        self.assertEqual([c['title'] for c in cards if c['state'] == 'on_branch'], [FIRST[0]['title']])

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
        page = guided.outputs(project_state.load(self.project)) / 'REPORT.html'
        self.assertTrue(page.is_file(), 'the report is rebuilt in the same call')
        self.assertEqual(agent_tools.status(str(self.project))['next']['tool'], 'run_setup',
                         'no new check is needed after EAOS merged its own fixes')

    def test_a_merge_made_by_hand_is_recorded_its_branch_deleted_and_a_reverted_revert_is_done_again(self):
        self.batch(1, ['TASK-001', 'TASK-002'])
        git(self.project, 'merge', '-q', '--ff-only', 'eaos/wave-1')          # what the other assistant did
        status = agent_tools.status(str(self.project))
        self.assertEqual(self.branches(), [])
        self.assertEqual(project_state.load(self.project)['waves'][0]['status'], 'accepted')
        self.assertEqual((status['progress']['done'], status['progress']['total']), (2, 5))
        history = ledger.load(project_state.load(self.project))['history']
        self.assertEqual((history[0]['event'], history[-1]['event'], history[-1]['closed']), ('baseline', 'merged', 2))
        # A branch an older EAOS left after its merge is deleted; a fix whose revert was reverted is done again.
        self.batch(2, ['TASK-005'])
        git(self.project, 'merge', '-q', '--ff-only', 'eaos/wave-2')
        state = project_state.load(self.project)
        state['waves'][-1]['status'] = 'accepted'
        guided.save(state)
        agent_tools.status(str(self.project))
        self.assertEqual(self.branches(), [])
        for _ in range(2): git(self.project, '-c', 'user.name=t', '-c', 'user.email=t@t', 'revert', '--no-edit', 'HEAD')
        self.assertEqual(ledger.sync(project_state.load(self.project))['totals']['done'], 3)

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
        cards = ledger.load(project_state.load(self.project))['cards'].values()
        self.assertEqual({c['id'] for c in cards if c['state'] == 'done'}, {None}, 'the fixed cards are no longer in the plan')
        self.assertEqual(ledger.load(project_state.load(self.project))['history'][-1]['event'], 'recheck')

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
        cards = {'k': {'state': 'open'}}
        ledger._apply_wave({'status': 'abandoned', 'failed': {'TASK-001': 'a gate refused it'}}, cards, {'TASK-001': 'k'})
        self.assertEqual(cards['k']['state'], 'open', 'an abandoned batch changed nothing: its cards can be picked again')
        cards = {'k': {'state': 'skipped', 'batch': 2, 'why': 'a gate bug'}, 'j': {'state': 'skipped', 'batch': 1, 'why': 'lock'}}
        ledger._apply_wave({'number': 2, 'status': 'abandoned', 'failed': {}}, cards, {})
        self.assertEqual((cards['k']['state'], cards['j']['state']), ('open', 'skipped'), 'and the cards it had skipped open again')
        self.assertEqual(self.branches(), ['eaos/wave-2'], 'a branch that is not merged stays')

    def test_a_batch_opens_for_a_ready_card_closes_cleanly_and_the_next_waits_for_a_decision(self):
        state = project_state.load(self.project)
        state['setup'] = {'commit': state['scanned_commit'], 'ok': True}
        state['consent'] = {'run_and_fix': True}
        state['safety'] = {'commit': state['scanned_commit'], 'screens': 1, 'passed': 1}
        guided.save(state)
        with mock.patch.object(agent_tools.fixing, '_start', return_value={'status': 'started'}) as started:
            self.assertEqual(agent_tools.fix_start(str(self.project), cards=['TASK-001'])['status'], 'started')
        self.assertEqual(started.call_args[0][2], {'cards': ['TASK-001'], 'deliver_as': 'eaos/master/wave-1', 'merge_into': 'master',
                                                         'assistants': 1})
        # A batch whose fix_finish was refused stayed open, and every later fix_start answered "not in batch 1".
        # A batch whose fix_finish was refused stayed open, and every later fix_start answered "not in batch 1".
        state = project_state.load(self.project)
        root = project_state.runtime_of(state) / 'candidates/WAVE-1'
        root.mkdir(parents=True)
        state['open_wave'] = {'number': 1, 'root': str(root), 'base': state['scanned_commit'], 'cards': ['TASK-001'],
                              'kept': {'TASK-001': 'abc'}, 'failed': {}, 'tools': {}}
        guided.save(state)
        head = git(self.project, 'rev-parse', 'HEAD')
        self.assertEqual(agent_tools.fix_abandon(str(self.project))['status'], 'abandoned')
        state = project_state.load(self.project)
        self.assertNotIn('open_wave', state)
        self.assertEqual((state['waves'][-1]['status'], root.exists()), ('abandoned', False))
        self.assertEqual((git(self.project, 'rev-parse', 'HEAD'), git(self.project, 'status', '--porcelain')), (head, ''))
        cards = {'k': {'state': 'open'}}
        ledger._apply_wave({'status': 'abandoned', 'failed': {'TASK-001': 'a gate refused it'}}, cards, {'TASK-001': 'k'})
        self.assertEqual(cards['k']['state'], 'open', 'an abandoned batch changed nothing: its cards can be picked again')
        cards = {'k': {'state': 'skipped', 'batch': 2, 'why': 'a gate bug'}, 'j': {'state': 'skipped', 'batch': 1, 'why': 'lock'}}
        ledger._apply_wave({'number': 2, 'status': 'abandoned', 'failed': {}}, cards, {})
        self.assertEqual((cards['k']['state'], cards['j']['state']), ('open', 'skipped'), 'and the cards it had skipped open again')
        self.batch(1, ['TASK-001'])
        state = project_state.load(self.project)
        state['consent'] = {'run_and_fix': True}
        state['setup'] = {'commit': state['scanned_commit'], 'ok': True}
        state['safety'] = {'commit': state['scanned_commit'], 'screens': 1, 'passed': 1}
        guided.save(state)
        self.assertEqual(agent_tools.fix_start(str(self.project))['status'], 'waiting_decision')

    def test_the_project_is_found_from_a_folder_inside_or_above_and_several_are_never_guessed(self):
        inner = git_project(self.project / 'vendor' / 'lib').parent.parent
        self.assertEqual(agent_tools.locate(inner), self.project)
        plain = Path(self.tmp.name) / 'plain'
        plain.mkdir()
        self.assertEqual(agent_tools.locate(plain), plain, 'nothing under it: the folder stays, and state_of says why')
        above = Path(self.tmp.name)
        self.assertEqual(agent_tools.locate(above), self.project)
        git_project(above / 'other')
        with self.assertRaises(agent_tools.SeveralProjects) as several:
            agent_tools.locate(above)
        self.assertEqual([p.name for p in several.exception.projects], ['other', 'shop'])
        self.assertEqual(agent_tools.status(str(above))['status'], 'needs_project')


class Handover(Base):
    def test_the_next_assistant_and_a_new_session_know_where_the_work_stopped(self):
        from eaos.interfaces.mcp_server import _answer
        state = project_state.load(self.project)
        state['open_wave'] = {'number': 2, 'root': str(self.project), 'base': state['scanned_commit'], 'cards': ['TASK-002', 'TASK-004', 'TASK-005'],
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
        page = (guided.outputs(project_state.load(self.project)) / 'HANDOVER.md').read_text()
        for words in ('Continue from here', 'TASK-005', 'do not ask again', 'deleting it next', 'Codex'):
            self.assertIn(words, page)
        with mock.patch('eaos.journeys.handover.refresh', side_effect=OSError('disk full')):
            answer = json.loads(_answer(agent_tools.plan)(project=str(self.project)))
        self.assertIn('milestones', answer)
        self.assertEqual(answer['progress']['total'], 5)
        # A new session is told where the work stopped and on which card; a broken hook says nothing.
        _answer(agent_tools.finding)(id='TASK-005', project=str(self.project))
        _answer(agent_tools.fix_read)(path='src/a.js', project=str(self.project))
        context = handover.hook_context(self.project / 'src')           # opened in a sub-folder of the project
        for words in ('batch 2 is open', 'Codex was on TASK-005', 'src/a.js', 'call the eaos `status` tool'):
            self.assertIn(words, context)
        self.assertEqual(agent_tools.status(str(self.project))['handover']['in_progress']['card'], 'TASK-005')
        self.assertIsNone(handover.hook_context(Path(self.tmp.name)), 'a folder EAOS knows nothing of adds nothing')
        import io, sys
        from eaos.interfaces import cli
        with mock.patch.object(sys, 'stdin', io.StringIO(json.dumps({'cwd': str(self.project), 'hook_event_name': 'SessionStart'}))), \
                mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            cli.handover_hook(None)
        self.assertEqual(json.loads(out.getvalue())['hookSpecificOutput']['hookEventName'], 'SessionStart')
        for stdin, failing in (('{not json', False), (json.dumps({'cwd': str(self.project)}), True)):
            with mock.patch.object(sys, 'stdin', io.StringIO(stdin)), mock.patch('sys.stdout', new_callable=io.StringIO) as out, \
                    mock.patch('eaos.journeys.handover.brief', side_effect=RuntimeError('broken state')) if failing else mock.patch('os.getcwd', return_value='/'):
                self.assertEqual(cli.handover_hook(None), 0)
            self.assertEqual(out.getvalue(), '', 'nothing printed: the session starts as if EAOS were not there')


if __name__ == '__main__':
    unittest.main()
