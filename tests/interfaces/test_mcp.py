"""EAOS inside the assistant (docs/MCP.md): the MCP server over stdio and the tools behind it."""
import asyncio
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock
from eaos.features.guided.interface import agent_tools
from eaos.features.guided import journey as guided
from eaos.features.fix.journey import finish as batch_finish, lanes
from eaos.kernel.project import jobs
from eaos.kernel.project import state as project_state
ROOT = Path(__file__).resolve().parents[2]
from tests.interfaces._mcp_fixture import Home, git_project, wave_branch


class ServerTests(Home):
    def test_an_assistant_lists_the_tools_chooses_the_branch_leaves_a_note_and_reads_errors_as_words_over_stdio(self):
        from mcp import ClientSession, StdioServerParameters, stdio_client
        run = lambda *argv: subprocess.run(['git', '-C', str(self.project), '-c', 'user.name=t', '-c', 'user.email=t@t',
                                            *argv],
                                           check=True, capture_output=True)
        run('checkout', '-q', '-b', 'develop'); (self.project / 'src/a.js').write_text('export const a = 9;\n')
        run('commit', '-qam', 'work'); run('checkout', '-q', '-')

        async def talk():
            server = StdioServerParameters(command=sys.executable, args=['-m', 'eaos', 'mcp'], cwd=str(self.project),
                                           env={**os.environ, 'PYTHONPATH': str(ROOT), 'EAOS_ASSISTANT': 'Codex',
                                                'EAOS_ANSWER_SECONDS': '0'})
            async with stdio_client(server) as (read, write):
                async with ClientSession(read, write) as session:
                    started = await session.initialize()
                    tools = await session.list_tools()
                    prompts = await session.list_prompts()
                    asked = await session.call_tool('status', {})
                    listed = await session.call_tool('branches', {})
                    chosen = await session.call_tool('choose_branch',
                                                     {'branch': 'develop', 'person_said': 'الفرع اللي تنصح فيه'})
                    noted = await session.call_tool('note',
                                                    {'text': 'develop is where the work goes on; checking it next.'})
                    after = await session.call_tool('status', {})
                    return started, tools, prompts, [json.loads(r.content[0].text)
                                                     for r in (asked, listed, chosen, noted, after)]

        started, tools, prompts, (asked, listed, chosen, noted, after) = asyncio.run(talk())
        self.assertIn('Work on your own until the job is done', started.instructions)
        names = {tool.name for tool in tools.tools}
        self.assertTrue({'status', 'audit', 'wait', 'finding', 'run_setup', 'run_try', 'safety_net', 'fix_start',
                         'fix_edit',
                         'fix_finish', 'fix_abandon', 'accept', 'undo', 'open_report'} <= names)
        self.assertEqual({p.name for p in prompts.prompts},
                         {'audit', 'fix', 'status', 'continue', 'report', 'tasks', 'ask', 'tools'})
        self.assertEqual(asked['project'], str(self.project.resolve()),
                         'the folder the assistant was opened in is the project')
        self.assertEqual((asked['next']['tool'], asked['recommended']), ('choose_branch', 'develop'))
        self.assertEqual({b['name'] for b in listed['branches']}, {'develop', 'master'})
        self.assertEqual((chosen['status'], after['branch'], after['next']['tool']), ('chosen', 'develop', 'audit'))
        self.assertTrue(noted['noted'])
        self.assertEqual(after['handover']['notes'][-1]['by'], 'Codex')
        self.assertEqual([s['tool'] for s in after['handover']['last_steps']], ['choose_branch', 'note'])
        from eaos.doors.mcp_server.server import _answer
        empty = Path(self.tmp.name) / 'empty'                 # no project file and no repository under it
        empty.mkdir()
        answer = json.loads(_answer(lambda: agent_tools.status(str(empty)))())
        self.assertIn('not a project folder', answer['error'])
        self.assertIn('eaos start .', answer['what_now'])


class ToolTests(Home):
    def test_every_answer_in_a_studio_run_carries_the_persons_language(self):
        # Every answer in a run of the run engine carries the person's language, so all notes are written in it.
        from eaos.doors.mcp_server import server as mcp_server
        def status(project=None): return {'next': 'audit'}
        with mock.patch.dict(os.environ, {'EAOS_STUDIO_LANG': 'ar'}):
            self.assertTrue(json.loads(mcp_server._answer(status)(str(self.project)))['notes_language']
                            .startswith('Arabic'))
        self.assertNotIn('notes_language', json.loads(mcp_server._answer(status)(str(self.project))),
                         'outside a Studio run, nothing')

    def test_the_assistant_way_never_calls_a_model_itself(self):
        source = ''.join(path.read_text() for path in sorted((ROOT / 'eaos/features/guided/interface/agent_tools').glob('*.py')))
        for call in ('import provider', 'provider()', '.complete('):
            self.assertNotIn(call, source)

    def test_nothing_runs_or_is_taken_in_before_the_person_agrees_and_an_unsafe_proposal_is_refused(self):
        answer = agent_tools.run_setup(str(self.project))
        self.assertEqual(answer['status'], 'needs_agreement')
        self.assertIn('separate copy', answer['ask_the_person'])
        self.assertFalse((project_state.runtime_of(project_state.load(self.project)) / 'authorization.json').exists())
        self.assertEqual(agent_tools.fix_start(str(self.project))['status'], 'needs_agreement')
        state = project_state.load(self.project)
        wave_branch(self.project)
        state['waves'] = [{'number': 1, 'branch': 'eaos/wave-1', 'status': 'applied'}]
        guided.save(state)
        self.assertEqual(agent_tools.accept(str(self.project))['status'], 'needs_agreement')
        state = agent_tools.state_of(str(self.project))
        runtime = project_state.runtime_of(state)
        runtime.mkdir(parents=True)
        (runtime / 'run.json').write_text('{}')
        answer = agent_tools.run_try({'env': {'DATABASE_URL': 'postgres://u@db.prod.example.com/x'},
                                      'start': ['bash', '-c', 'x']},
                                     project=str(self.project))
        self.assertEqual(answer['status'], 'refused')
        self.assertTrue(any('db.prod.example.com' in r for r in answer['reasons']))
        self.assertTrue(any('bash' in r for r in answer['reasons']))

    def test_edits_replace_once_write_whole_files_delete_and_stay_inside_the_copy(self):
        root = self.project
        changed = agent_tools._apply(root, [{'path': 'src/a.js', 'find': 'a = 1', 'replace': 'a = 3'},
                                            {'path': 'src/shared/c.js', 'content': 'export const c = 1;\n'},
                                            {'path': 'package.json', 'delete': True}])
        self.assertEqual(changed, ['package.json', 'src/a.js', 'src/shared/c.js'])
        self.assertIn('a = 3', (root / 'src/a.js').read_text())
        self.assertTrue((root / 'src/shared/c.js').is_file())
        self.assertFalse((root / 'package.json').exists())
        before = (root / 'src/a.js').read_text()
        for bad in ([{'path': '../outside.js', 'content': 'x'}], [{'path': '.git/config', 'content': 'x'}],
                    [{'path': 'src/a.js', 'find': 'export', 'replace': 'x'}],
                    [{'path': 'src/a.js', 'find': 'b = 2', 'replace': 'b = 5'},
                     {'path': 'src/none.js', 'find': 'x', 'replace': 'y'}]):
            with self.assertRaises(ValueError): agent_tools._apply(root, bad)
        self.assertEqual((root / 'src/a.js').read_text(), before, 'a refused set of edits changes nothing')
        # a Windows file: fix_read shows its lines without \r, and the text copied from them is found
        (root / 'src/win.js').write_bytes(b'const a = 1;\r\nconst b = 2;\r\n')
        agent_tools._apply(root,
                           [{'path': 'src/win.js', 'find': 'const a = 1;\nconst b = 2;',
                             'replace': 'const a = 1;\nconst b = 3;'}])
        self.assertEqual((root / 'src/win.js').read_bytes(), b'const a = 1;\r\nconst b = 3;\r\n')
        with self.assertRaisesRegex(ValueError, 'read those lines again with fix_read'):
            agent_tools._apply(root, [{'path': 'src/win.js', 'find': 'const c', 'replace': 'x'}])

    def test_a_kept_edit_stays_a_failing_one_is_taken_back_and_the_batch_is_handed_over_or_abandoned(self):
        state = agent_tools.state_of(str(self.project))
        report = guided.report_of(state)
        report.mkdir(parents=True)
        card = {'id': 'TASK-001', 'title': 'x', 'paths': ['src/a.js'], 'kind': 'remediate'}
        (report / 'plan.json').write_text(json.dumps({'tasks': [card, {**card, 'id': 'TASK-002'}]}))
        copy = Path(self.tmp.name) / 'copy'
        subprocess.run(['git', 'clone', '-q', str(self.project), str(copy)], check=True)
        guided._git(copy, 'checkout', '-q', '-b', 'eaos/wave-1')
        base = guided._git(copy, 'rev-parse', 'HEAD').stdout.strip()
        state['open_wave'] = {'number': 1, 'root': str(copy), 'base': base, 'cards': ['TASK-001', 'TASK-002'],
                              'kept': {}, 'failed': {}, 'tools': {}}
        guided.save(state)
        with mock.patch('eaos.kernel.facts.run.collect'), \
             mock.patch('eaos.features.fix.journey.execute.new_breakage',
                        side_effect=[[], ['src/b.js: import of a file that is gone']]), \
             mock.patch('eaos.features.fix.journey.waves.batch.batch_acceptance', return_value={'TASK-001': 0, 'TASK-002': 0}):
            kept = agent_tools._fix_edit_job(str(self.project), {'card': 'TASK-001', 'edits': [
                {'path': 'src/a.js', 'find': 'a = 1', 'replace': 'a = 3'}]}, lambda *_: None)
            broke = agent_tools._fix_edit_job(str(self.project), {'card': 'TASK-002', 'edits': [
                {'path': 'src/a.js', 'find': 'b = 2', 'replace': 'b = 4'}]}, lambda *_: None)
        self.assertTrue(kept['kept'])
        self.assertEqual(kept['left'], ['TASK-002'])
        self.assertFalse(broke['kept']); self.assertIn('import of a file that is gone', broke['why'])
        text = (copy / 'src/a.js').read_text()
        self.assertEqual(('a = 3' in text, 'b = 2' in text), (True, True),
                         'the failing change is gone, the kept one stays')
        wave = project_state.load(self.project)['open_wave']
        self.assertEqual(list(wave['kept']), ['TASK-001'])
        self.assertEqual(agent_tools.fix_finish(str(self.project))['status'], 'cards_left')
        agent_tools.fix_skip('TASK-002', 'needs a product decision', str(self.project))
        self.assertEqual(project_state.load(self.project)['open_wave']['failed']['TASK-002'],
                         'skipped: needs a product decision')
        with mock.patch('eaos.features.fix.journey.waves.batch.batch_acceptance', return_value={'TASK-001': 0}), \
                mock.patch('eaos.features.fix.journey.waves.batch.original_checks',
                           return_value=[]), mock.patch('eaos.features.fix.journey.waves.batch.gates', return_value=''):
            done = batch_finish.finish_job(str(self.project), {}, lambda *_: None)
        self.assertEqual((done['branch'], done['kept']), ('eaos/wave-1', ['TASK-001']))
        self.assertIn('a = 3', guided._git(self.project, 'show', 'eaos/wave-1:src/a.js').stdout,
                      'the fix arrives as a branch')
        self.assertEqual((self.project / 'src/a.js').read_text(), 'export const a = 1;\nexport const b = 2;\n',
                         "the person's own files are not touched")
        state = project_state.load(self.project)
        self.assertEqual((state['waves'][-1]['status'], state.get('open_wave')), ('applied', None))
        state['open_wave'] = {'number': 2, 'root': str(copy), 'base': base, 'cards': ['TASK-002'], 'kept': {},
                              'failed': {}, 'tools': {}}
        guided.save(state)
        self.assertEqual(agent_tools.fix_abandon(str(self.project))['status'], 'abandoned')
        state = project_state.load(self.project)
        self.assertEqual((state['waves'][-1]['status'], state.get('open_wave')), ('abandoned', None))

    def test_a_change_beyond_its_cards_files_is_kept_only_with_why(self):
        # A change to files beyond the card's own is kept only with a reason; a card about one dialog must not change
        # other files unnamed.
        state = agent_tools.state_of(str(self.project))
        report = guided.report_of(state)
        report.mkdir(parents=True)
        (report / 'plan.json').write_text(json.dumps({'tasks': [{'id': 'TASK-001', 'title': 'Split the dialog',
                                                                 'paths': ['src/a.js']}]}))
        copy = Path(self.tmp.name) / 'copy'
        subprocess.run(['git', 'clone', '-q', str(self.project), str(copy)], check=True)
        base = guided._git(copy, 'rev-parse', 'HEAD').stdout.strip()
        state['open_wave'] = {'number': 1, 'root': str(copy), 'base': base, 'cards': ['TASK-001'], 'kept': {},
                              'failed': {}, 'tools': {}}
        guided.save(state)
        edits = [{'path': 'src/a.js', 'find': 'a = 1', 'replace': 'a = 3'},
                 {'path': 'src/b.js', 'content': 'export const c = 1;\n'}]
        edit = lambda **more: agent_tools._fix_edit_job(str(self.project),
                                                        {'card': 'TASK-001', 'edits': edits,
                                                         'summary': 'Split the dialog', **more}, lambda *_: None)
        with mock.patch('eaos.kernel.facts.run.collect'), mock.patch('eaos.features.fix.journey.execute.new_breakage',
                                                              return_value=[]), \
                mock.patch('eaos.features.fix.journey.waves.batch.batch_acceptance', return_value={'TASK-001': 0}):
            refused = edit()
            self.assertEqual((refused['kept'], refused['beyond_the_card']), (False, ['src/b.js']))
            self.assertIn('beyond_why', refused['what_now'])
            self.assertEqual((guided._git(copy, 'rev-parse', 'HEAD').stdout.strip(), (copy / 'src/b.js').exists()),
                             (base, False))
            kept = edit(beyond_why='the one-source gate made it move the shared constant')
        self.assertTrue(kept['kept'])
        self.assertEqual(project_state.load(self.project)['open_wave']['beyond'],
                         {'TASK-001': {'files': ['src/b.js'],
                                       'why': 'the one-source gate made it move the shared constant'}})
        self.assertIn('src/b.js: the one-source gate made it move the shared constant',
                      guided._git(copy, 'log', '-1', '--format=%B').stdout)

    def test_assistants_fixing_one_batch_at_once_keep_to_their_own_files_and_it_is_handed_over_once_all_are_done(self):
        # speed mode: one batch, one copy and branch, two assistants; a change to a file the other one holds is never
        # tried
        state = agent_tools.state_of(str(self.project))
        report = guided.report_of(state); report.mkdir(parents=True)
        tasks = {'TASK-001': ['src/a.js'], 'TASK-002': ['src/b.js'], 'TASK-003': ['src/a.js']}
        cards = {id: {'id': id, 'title': id, 'paths': paths, 'kind': 'remediate'} for id, paths in tasks.items()}
        (report / 'plan.json').write_text(json.dumps({'tasks': list(cards.values())}))
        copy = Path(self.tmp.name) / 'copy'
        subprocess.run(['git', 'clone', '-q', str(self.project), str(copy)], check=True)
        wave = {'number': 1, 'root': str(copy), 'base': guided._git(copy, 'rev-parse', 'HEAD').stdout.strip(),
                'cards': list(tasks), 'kept': {}, 'failed': {}, 'tools': {}}
        with mock.patch.dict(os.environ, EAOS_STUDIO_RUN='first'):
            self.assertEqual(lanes.open_lanes(wave, cards, 2), [['TASK-002']],
                             'the cards sharing a file stay with the first')
        waits = {'id': 'TASK-009', 'paths': ['src/c.js'],
                 'prerequisites': [{'task_id': 'TASK-002', 'reason': 'its function first'}]}
        self.assertEqual(lanes.deal([*cards.values(), waits], 3), [['TASK-001', 'TASK-003'], ['TASK-002', 'TASK-009']],
                         'a card waiting for another one goes with it')
        wave['helpers'] = {'second': 1}
        state['open_wave'] = wave; guided.save(state)
        as_second = mock.patch.dict(os.environ, EAOS_STUDIO_RUN='second')
        as_first = mock.patch.dict(os.environ, EAOS_STUDIO_RUN='first')
        with as_second:
            later = agent_tools.fix_edit('TASK-002', [{'path': './src/a.js', 'find': 'a = 1', 'replace': 'a = 2'}],
                                         project=str(self.project))
            self.assertEqual((later['later'], later['why']),
                             (True, 'another assistant of this batch is changing src/a.js'))
            self.assertEqual(agent_tools.fix_finish(str(self.project))['status'], 'not_yours',
                             'only the first one hands it over')
        self.assertIn('a = 1', (copy / 'src/a.js').read_text(), 'the refused change was never tried')
        with as_first, mock.patch.object(lanes, 'WAIT', 0):
            self.assertEqual(lanes.mine(project_state.load(self.project)['open_wave'], list(tasks)),
                             ['TASK-001', 'TASK-002', 'TASK-003'])
            with mock.patch('eaos.kernel.facts.run.collect'), \
                    mock.patch('eaos.features.fix.journey.execute.new_breakage', return_value=[]), \
                    mock.patch('eaos.features.fix.journey.waves.batch.batch_acceptance', return_value={'TASK-001': 0}):
                kept = agent_tools._fix_edit_job(str(self.project), {'card': 'TASK-001', 'edits': [
                    {'path': 'src/a.js', 'find': 'a = 1', 'replace': 'a = 3'}]}, lambda *_: None)
            self.assertEqual(kept['left'], ['TASK-003'], 'its own: the card left for the end comes with fix_finish')
            self.assertEqual(agent_tools.fix_finish(str(self.project))['status'], 'cards_left')
        state = project_state.load(self.project)
        state['open_wave']['later'] = []                           # the second assistant's card back in its lane
        guided.save(state)
        with as_first, mock.patch.object(lanes, 'WAIT', 0):
            self.assertEqual(agent_tools.fix_finish(str(self.project)),
                             {'status': 'others_fixing', 'cards': ['TASK-002'], 'what_now': mock.ANY})
            with lanes.changing(str(self.project)) as state:
                lanes.release(state['open_wave'], 1)                     # its assistant stopped
            self.assertEqual(agent_tools.fix_finish(str(self.project))['left'], ['TASK-002', 'TASK-003'])

    def test_status_names_the_next_tool_at_each_point(self):
        project = str(self.project)
        self.assertEqual(agent_tools.status(project)['next']['tool'], 'audit')
        state = project_state.load(self.project)
        with mock.patch.object(guided, 'scan_done', return_value=True):
            state['scanned_commit'], state['scanned_with'] = agent_tools._head(state), 'an-older-eaos'
            guided.save(state)
            older = agent_tools.status(project)
            self.assertEqual((older['next']['tool'], older['older_check']), ('run_setup', True),
                             'a report by an older EAOS stands: a new check runs only when the person asks')
            with mock.patch.object(agent_tools.checking, 'overview',
                                   return_value={}), mock.patch.object(jobs, 'start') as started:
                self.assertTrue(agent_tools.audit(project)['already_checked'])
            started.assert_not_called()
            state['scanned_with'] = agent_tools.tool_digest(); guided.save(state)
            self.assertEqual(agent_tools.status(project)['next']['tool'], 'run_setup')
            self.assertNotIn('older_check', agent_tools.status(project))
            state['setup'] = {'commit': state['scanned_commit'], 'ok': True}; guided.save(state)
            self.assertEqual(agent_tools.status(project)['next']['tool'], 'safety_net')
            state['safety'] = {'commit': state['scanned_commit'], 'screens': 54, 'passed': 0}; guided.save(state)
            self.assertEqual(agent_tools.status(project)['next']['tool'], 'none',
                             'a safety net that recorded nothing opens no batch')
            self.assertEqual(agent_tools._no_safety_net(project_state.load(self.project))['recorded'], 0)
            state['safety'] = {'commit': state['scanned_commit'], 'screens': 54, 'passed': 54}; guided.save(state)
            self.assertEqual(agent_tools.status(project)['next']['tool'], 'fix_start')
            wave_branch(self.project)
            state['waves'] = [{'number': 1, 'branch': 'eaos/wave-1', 'status': 'applied'}]; guided.save(state)
            self.assertEqual(agent_tools.status(project)['next']['tool'], 'accept or undo')


class OutputsTests(Home):
    def test_every_output_and_each_batch_summary_is_in_one_folder_named_after_the_project(self):
        state = agent_tools.state_of(str(self.project))
        folder = guided.outputs(state)
        self.assertEqual(folder, guided.outputs_root() / 'shop')
        self.assertEqual(guided.report_of(state), folder / 'technical')
        self.assertIn('technical/START-HERE.md', (folder / 'README.md').read_text())
        other = git_project(Path(self.tmp.name) / 'elsewhere' / 'shop')
        self.assertEqual(guided.outputs(agent_tools.state_of(str(other))), guided.outputs_root() / 'shop-2',
                         'another project with the same name gets its own folder')
        self.assertNotIn(str(self.project), str(folder), 'nothing is written into the project')
        self.assertFalse(str(folder).startswith(str(Path.home() / 'EAOS')), 'a test never writes into the real home')
        old = Path(state['workspace']) / 'report'
        old.mkdir(parents=True)
        (old / 'plan.json').write_text('{"tasks": []}')
        self.assertTrue((guided.report_of(state) / 'plan.json').is_file(),
                        'a report an older EAOS left is moved into the folder')
        self.assertFalse(old.exists())
        wave = {'number': 1, 'kept': ['TASK-001'], 'failed': {'TASK-002': 'its problem is still there'},
                'branch': 'eaos/wave-1',
                'stat': '1 file changed'}
        target = guided.publish_fixes(state, wave)
        summary = (target / 'SUMMARY.md').read_text()
        self.assertIn('eaos/wave-1', summary)
        self.assertIn('TASK-002: its problem is still there', summary)
        self.assertEqual(target, guided.outputs(state) / 'fixes' / 'wave-1')
        answer = agent_tools.open_report(str(self.project), show=False)
        self.assertEqual(answer['outputs_folder'], str(guided.outputs(state)))

    def test_a_part_that_cannot_be_built_never_stops_the_step_and_every_report_names_the_eaos_that_made_it(self):
        state = agent_tools.state_of(str(self.project))
        guided.report_of(state).mkdir(parents=True)
        def broken(state): raise RuntimeError('broken record')
        with mock.patch.dict(guided.REPORT_PARTS, {'broken': broken}):
            page = guided.publish(state)                           # the step goes on
        self.assertEqual(page, guided.report_of(state) / 'START-HERE.md')
        self.assertIn('broken: RuntimeError: broken record', guided.report_stamp(state)['errors'])
        self.assertTrue(list((guided.outputs(state) / 'logs').glob('*.log')))
        from eaos.kernel.system.version_info import digest
        guided.publish(state)
        made = guided.report_stamp(state)
        self.assertEqual((made['digest'], made['version'], made['errors']),
                         (digest(), __import__('eaos').__version__, []))
        (guided.outputs(state) / '.report.json').write_text(json.dumps({**made, 'digest': 'an-older-eaos'}))
        report = agent_tools._fresh_report(state)
        self.assertTrue(report['rebuilt'])
        self.assertEqual(guided.report_stamp(state)['digest'], digest())
        self.assertFalse(agent_tools._fresh_report(state)['rebuilt'], 'a page this EAOS made is not rebuilt again')


if __name__ == '__main__':
    unittest.main()
