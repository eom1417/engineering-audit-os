"""EAOS inside the assistant (docs/MCP.md): the MCP server over stdio, the tools behind it, and its jobs."""
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.journeys import agent_tools, batch_finish, guided, lanes
from eaos.core import jobs
from eaos.core import project_state

ROOT = Path(__file__).resolve().parents[1]


def git_project(where):
    where.mkdir(parents=True, exist_ok=True)
    (where / 'package.json').write_text('{"name": "shop", "scripts": {"dev": "vite"}}\n')
    (where / 'src').mkdir()
    (where / 'src/a.js').write_text('export const a = 1;\nexport const b = 2;\n')
    for argv in (['init', '-q'], ['add', '-A'], ['-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'first']):
        subprocess.run(['git', '-C', str(where), *argv], check=True, capture_output=True)
    return where


def wave_branch(project, name='eaos/wave-1', file='src/a.js', text='export const a = 5;\nexport const b = 2;\n'):
    """A batch's branch in the project, one EAOS commit ahead, as fix_finish leaves it; the project stays on its branch."""
    run = lambda *argv: subprocess.run(['git', '-C', str(project), *argv], check=True, capture_output=True, text=True).stdout.strip()
    here = run('rev-parse', '--abbrev-ref', 'HEAD')
    run('checkout', '-q', '-b', name)
    (Path(project) / file).write_text(text)
    run('add', '-A')
    run('-c', 'user.name=EAOS', '-c', 'user.email=eaos@localhost', 'commit', '-qm', 'TASK-001: a fix\n\nExecuted by EAOS (assistant).\n\nEAOS-Card: 0123456789ab')
    run('checkout', '-q', here)
    return run('rev-parse', name)


class Home(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(self.tmp.name) / 'home')})
        patcher.start(); self.addCleanup(patcher.stop)
        self.project = git_project(Path(self.tmp.name) / 'shop')


class ServerTests(Home):
    def test_an_assistant_lists_the_tools_chooses_the_branch_leaves_a_note_and_reads_errors_as_words_over_stdio(self):
        from mcp import ClientSession, StdioServerParameters, stdio_client
        run = lambda *argv: subprocess.run(['git', '-C', str(self.project), '-c', 'user.name=t', '-c', 'user.email=t@t', *argv],
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
                    chosen = await session.call_tool('choose_branch', {'branch': 'develop', 'person_said': 'الفرع اللي تنصح فيه'})
                    noted = await session.call_tool('note', {'text': 'develop is where the work goes on; checking it next.'})
                    after = await session.call_tool('status', {})
                    return started, tools, prompts, [json.loads(r.content[0].text) for r in (asked, listed, chosen, noted, after)]

        started, tools, prompts, (asked, listed, chosen, noted, after) = asyncio.run(talk())
        self.assertIn('Work on your own until the job is done', started.instructions)
        names = {tool.name for tool in tools.tools}
        self.assertTrue({'status', 'audit', 'wait', 'finding', 'run_setup', 'run_try', 'safety_net', 'fix_start', 'fix_edit',
                         'fix_finish', 'fix_abandon', 'accept', 'undo', 'open_report', 'blueprint_start', 'blueprint_spec',
                         'blueprint_design', 'build_start', 'build_edit', 'build_finish'} <= names)
        self.assertEqual({p.name for p in prompts.prompts}, {'audit', 'fix', 'status', 'build', 'continue', 'report', 'tasks', 'ask', 'tools'})
        self.assertEqual(asked['project'], str(self.project.resolve()), 'the folder the assistant was opened in is the project')
        self.assertEqual((asked['next']['tool'], asked['recommended']), ('choose_branch', 'develop'))
        self.assertEqual({b['name'] for b in listed['branches']}, {'develop', 'master'})
        self.assertEqual((chosen['status'], after['branch'], after['next']['tool']), ('chosen', 'develop', 'audit'))
        self.assertTrue(noted['noted'])
        self.assertEqual(after['handover']['notes'][-1]['by'], 'Codex')
        self.assertEqual([s['tool'] for s in after['handover']['last_steps']], ['choose_branch', 'note'])
        from eaos.interfaces.mcp_server import _answer
        empty = Path(self.tmp.name) / 'empty'                 # no project file and no repository under it
        empty.mkdir()
        answer = json.loads(_answer(lambda: agent_tools.status(str(empty)))())
        self.assertIn('not a project folder', answer['error'])
        self.assertIn('eaos start .', answer['what_now'])

class ToolTests(Home):
    def test_every_answer_in_a_studio_run_carries_the_persons_language(self):
        # A real build from the Studio: after its first notes the assistant wrote 67 of 69 notes in English.
        from eaos.interfaces import mcp_server
        def status(project=None): return {'next': 'audit'}
        with mock.patch.dict(os.environ, {'EAOS_STUDIO_LANG': 'ar'}):
            self.assertTrue(json.loads(mcp_server._answer(status)(str(self.project)))['notes_language'].startswith('Arabic'))
        self.assertNotIn('notes_language', json.loads(mcp_server._answer(status)(str(self.project))), 'outside a Studio run, nothing')

    def test_the_assistant_way_never_calls_a_model_itself(self):
        source = (ROOT / 'eaos/journeys/agent_tools.py').read_text()
        for call in ('from .assistants import provider', 'provider()', '.complete('):
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
        answer = agent_tools.run_try({'env': {'DATABASE_URL': 'postgres://u@db.prod.example.com/x'}, 'start': ['bash', '-c', 'x']},
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
                    [{'path': 'src/a.js', 'find': 'b = 2', 'replace': 'b = 5'}, {'path': 'src/none.js', 'find': 'x', 'replace': 'y'}]):
            with self.assertRaises(ValueError): agent_tools._apply(root, bad)
        self.assertEqual((root / 'src/a.js').read_text(), before, 'a refused set of edits changes nothing')

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
        with mock.patch('eaos.facts.run.collect'), \
             mock.patch('eaos.journeys.execute.new_breakage', side_effect=[[], ['src/b.js: import of a file that is gone']]), \
             mock.patch('eaos.journeys.waves.batch_acceptance', return_value={'TASK-001': 0, 'TASK-002': 0}):
            kept = agent_tools._fix_edit_job(str(self.project), {'card': 'TASK-001', 'edits': [
                {'path': 'src/a.js', 'find': 'a = 1', 'replace': 'a = 3'}]}, lambda *_: None)
            broke = agent_tools._fix_edit_job(str(self.project), {'card': 'TASK-002', 'edits': [
                {'path': 'src/a.js', 'find': 'b = 2', 'replace': 'b = 4'}]}, lambda *_: None)
        self.assertTrue(kept['kept'])
        self.assertEqual(kept['left'], ['TASK-002'])
        self.assertFalse(broke['kept'])
        self.assertIn('import of a file that is gone', broke['why'])
        text = (copy / 'src/a.js').read_text()
        self.assertEqual(('a = 3' in text, 'b = 2' in text), (True, True), 'the failing change is gone, the kept one stays')
        wave = project_state.load(self.project)['open_wave']
        self.assertEqual(list(wave['kept']), ['TASK-001'])
        self.assertEqual(agent_tools.fix_finish(str(self.project))['status'], 'cards_left')
        agent_tools.fix_skip('TASK-002', 'needs a product decision', str(self.project))
        self.assertEqual(project_state.load(self.project)['open_wave']['failed']['TASK-002'], 'skipped: needs a product decision')
        with mock.patch('eaos.journeys.waves.batch_acceptance', return_value={'TASK-001': 0}), \
                mock.patch('eaos.journeys.waves.original_checks', return_value=[]), mock.patch('eaos.journeys.waves.gates', return_value=''):
            done = batch_finish.finish_job(str(self.project), {}, lambda *_: None)
        self.assertEqual((done['branch'], done['kept']), ('eaos/wave-1', ['TASK-001']))
        self.assertIn('a = 3', guided._git(self.project, 'show', 'eaos/wave-1:src/a.js').stdout, 'the fix arrives as a branch')
        self.assertEqual((self.project / 'src/a.js').read_text(), 'export const a = 1;\nexport const b = 2;\n',
                         "the person's own files are not touched")
        state = project_state.load(self.project)
        self.assertEqual((state['waves'][-1]['status'], state.get('open_wave')), ('applied', None))
        state['open_wave'] = {'number': 2, 'root': str(copy), 'base': base, 'cards': ['TASK-002'], 'kept': {}, 'failed': {}, 'tools': {}}
        guided.save(state)
        self.assertEqual(agent_tools.fix_abandon(str(self.project))['status'], 'abandoned')
        state = project_state.load(self.project)
        self.assertEqual((state['waves'][-1]['status'], state.get('open_wave')), ('abandoned', None))

    def test_assistants_fixing_one_batch_at_once_keep_to_their_own_files_and_it_is_handed_over_once_all_are_done(self):
        # speed mode: one batch, one copy and branch, two assistants; a change to a file the other one holds is never tried
        state = agent_tools.state_of(str(self.project))
        report = guided.report_of(state)
        report.mkdir(parents=True)
        tasks = {'TASK-001': ['src/a.js'], 'TASK-002': ['src/b.js'], 'TASK-003': ['src/a.js']}
        cards = {id: {'id': id, 'title': id, 'paths': paths, 'kind': 'remediate'} for id, paths in tasks.items()}
        (report / 'plan.json').write_text(json.dumps({'tasks': list(cards.values())}))
        copy = Path(self.tmp.name) / 'copy'
        subprocess.run(['git', 'clone', '-q', str(self.project), str(copy)], check=True)
        wave = {'number': 1, 'root': str(copy), 'base': guided._git(copy, 'rev-parse', 'HEAD').stdout.strip(), 'cards': list(tasks),
                'kept': {}, 'failed': {}, 'tools': {}}
        with mock.patch.dict(os.environ, EAOS_STUDIO_RUN='first'):
            self.assertEqual(lanes.open_lanes(wave, cards, 2), [['TASK-002']], 'the cards sharing a file stay with the first')
        waits = {'id': 'TASK-009', 'paths': ['src/c.js'], 'prerequisites': [{'task_id': 'TASK-002', 'reason': 'its function first'}]}
        self.assertEqual(lanes.deal([*cards.values(), waits], 3), [['TASK-001', 'TASK-003'], ['TASK-002', 'TASK-009']],
                         'a card waiting for another one goes with it')
        wave['helpers'] = {'second': 1}
        state['open_wave'] = wave
        guided.save(state)
        as_second, as_first = mock.patch.dict(os.environ, EAOS_STUDIO_RUN='second'), mock.patch.dict(os.environ, EAOS_STUDIO_RUN='first')
        with as_second:
            later = agent_tools.fix_edit('TASK-002', [{'path': './src/a.js', 'find': 'a = 1', 'replace': 'a = 2'}], project=str(self.project))
            self.assertEqual((later['later'], later['why']), (True, 'another assistant of this batch is changing src/a.js'))
            self.assertEqual(agent_tools.fix_finish(str(self.project))['status'], 'not_yours', 'only the first one hands it over')
        self.assertIn('a = 1', (copy / 'src/a.js').read_text(), 'the refused change was never tried')
        with as_first, mock.patch.object(lanes, 'WAIT', 0):
            self.assertEqual(lanes.mine(project_state.load(self.project)['open_wave'], list(tasks)), ['TASK-001', 'TASK-002', 'TASK-003'])
            with mock.patch('eaos.facts.run.collect'), mock.patch('eaos.journeys.execute.new_breakage', return_value=[]), \
                    mock.patch('eaos.journeys.waves.batch_acceptance', return_value={'TASK-001': 0}):
                kept = agent_tools._fix_edit_job(str(self.project), {'card': 'TASK-001', 'edits': [
                    {'path': 'src/a.js', 'find': 'a = 1', 'replace': 'a = 3'}]}, lambda *_: None)
            self.assertEqual(kept['left'], ['TASK-003'], 'its own: the card left for the end comes with fix_finish')
            self.assertEqual(agent_tools.fix_finish(str(self.project))['status'], 'cards_left')
        state = project_state.load(self.project)
        state['open_wave']['later'] = []                           # the second assistant's card back in its lane
        guided.save(state)
        with as_first, mock.patch.object(lanes, 'WAIT', 0):
            self.assertEqual(agent_tools.fix_finish(str(self.project)), {'status': 'others_fixing', 'cards': ['TASK-002'], 'what_now': mock.ANY})
            with lanes.changing(str(self.project)) as state: lanes.release(state['open_wave'], 1)    # its assistant stopped
            self.assertEqual(agent_tools.fix_finish(str(self.project))['left'], ['TASK-002', 'TASK-003'])

    def test_status_names_the_next_tool_at_each_point(self):
        project = str(self.project)
        self.assertEqual(agent_tools.status(project)['next']['tool'], 'audit')
        state = project_state.load(self.project)
        with mock.patch.object(guided, 'scan_done', return_value=True):
            state['scanned_commit'], state['scanned_with'] = agent_tools._head(state), 'an-older-eaos'; guided.save(state)
            older = agent_tools.status(project)
            self.assertEqual((older['next']['tool'], older['older_check']), ('run_setup', True),
                             'a report by an older EAOS stands: a new check runs only when the person asks')
            with mock.patch.object(agent_tools, 'overview', return_value={}), mock.patch.object(jobs, 'start') as started:
                self.assertTrue(agent_tools.audit(project)['already_checked'])
            started.assert_not_called()
            state['scanned_with'] = agent_tools.tool_digest(); guided.save(state)
            self.assertEqual(agent_tools.status(project)['next']['tool'], 'run_setup')
            self.assertNotIn('older_check', agent_tools.status(project))
            state['setup'] = {'commit': state['scanned_commit'], 'ok': True}; guided.save(state)
            self.assertEqual(agent_tools.status(project)['next']['tool'], 'safety_net')
            state['safety'] = {'commit': state['scanned_commit'], 'screens': 54, 'passed': 0}; guided.save(state)
            self.assertEqual(agent_tools.status(project)['next']['tool'], 'none', 'a safety net that recorded nothing opens no batch')
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
        self.assertIn('REPORT.html', (folder / 'README.md').read_text())
        other = git_project(Path(self.tmp.name) / 'elsewhere' / 'shop')
        self.assertEqual(guided.outputs(agent_tools.state_of(str(other))), guided.outputs_root() / 'shop-2',
                         'another project with the same name gets its own folder')
        self.assertNotIn(str(self.project), str(folder), 'nothing is written into the project')
        self.assertFalse(str(folder).startswith(str(Path.home() / 'EAOS')), 'a test never writes into the real home')
        old = Path(state['workspace']) / 'report'
        old.mkdir(parents=True)
        (old / 'plan.json').write_text('{"tasks": []}')
        self.assertTrue((guided.report_of(state) / 'plan.json').is_file(), 'a report an older EAOS left is moved into the folder')
        self.assertFalse(old.exists())
        wave = {'number': 1, 'kept': ['TASK-001'], 'failed': {'TASK-002': 'its problem is still there'}, 'branch': 'eaos/wave-1',
                'stat': '1 file changed'}
        target = guided.publish_fixes(state, wave)
        summary = (target / 'SUMMARY.md').read_text()
        self.assertIn('eaos/wave-1', summary)
        self.assertIn('TASK-002: its problem is still there', summary)
        self.assertEqual(target, guided.outputs(state) / 'fixes' / 'wave-1')
        answer = agent_tools.open_report(str(self.project), show=False)
        self.assertEqual(answer['outputs_folder'], str(guided.outputs(state)))

    def test_a_page_that_cannot_be_built_never_stops_the_step_and_every_page_names_the_eaos_that_made_it(self):
        state = agent_tools.state_of(str(self.project))
        guided.report_of(state).mkdir(parents=True)
        with mock.patch('eaos.report.human_report.write', side_effect=RuntimeError('broken record')):
            page = guided.publish(state)                           # the step goes on
        self.assertEqual(page, guided.outputs(state) / 'REPORT.html')
        self.assertIn('broken record', page.read_text(), 'the page says why, instead of an old page left in silence')
        self.assertIn('page: RuntimeError: broken record', guided.report_stamp(state)['errors'])
        self.assertTrue(list((guided.outputs(state) / 'logs').glob('*.log')))
        from eaos.core.build_info import digest
        guided.publish(state)
        made = guided.report_stamp(state)
        self.assertEqual((made['digest'], made['version'], made['errors']), (digest(), __import__('eaos').__version__, []))
        (guided.outputs(state) / '.report.json').write_text(json.dumps({**made, 'digest': 'an-older-eaos'}))
        report = agent_tools._fresh_report(state)
        self.assertTrue(report['rebuilt'])
        self.assertEqual(guided.report_stamp(state)['digest'], digest())
        self.assertFalse(agent_tools._fresh_report(state)['rebuilt'], 'a page this EAOS made is not rebuilt again')

class JobTests(Home):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(jobs.subprocess, 'Popen', return_value=mock.Mock(pid=os.getpid()))
        patcher.start(); self.addCleanup(patcher.stop)

    def test_work_sent_while_other_work_runs_waits_its_turn(self):
        # the assistants of one batch (eaos/journeys/lanes.py) send their changes at once: one is checked at a time
        import threading
        state = {'project': str(self.project)}
        first = agent_tools._start('fix_edit', state, {}, seconds=0)
        self.assertEqual(first['status'], 'running')
        busy = agent_tools._start('fix_edit', state, {}, seconds=0)
        self.assertEqual((busy['status'], busy['job']), ('busy', first['job']))
        ends = lambda: jobs._write({**jobs.read(first['job'], str(self.project)), 'status': 'done', 'result': {}})
        threading.Timer(0.5, ends).start()
        second = agent_tools._start('fix_edit', state, {}, seconds=5)
        self.assertNotEqual(second['job'], first['job'], 'it started once the first one ended')

    def test_a_job_runs_on_its_own_is_read_back_stops_as_an_interrupt_and_a_dead_one_has_failed(self):
        project = str(self.project)
        job = jobs.start('audit', project, {})
        record = json.loads((jobs.folder(project) / f'{job}.json').read_text())
        self.assertEqual((record['status'], record['kind']), ('running', 'audit'))
        given = jobs.subprocess.Popen.call_args.kwargs['env']['EAOS_ENGINE_CACHE']
        self.assertEqual(given, str(jobs.cache(project)), "the analyzers' caches are the project's own")
        jobs.cache(project).mkdir()
        with mock.patch.dict(agent_tools.JOBS, {'audit': lambda project, arguments, progress: progress(1, 2, 'half') or {'ok': True}}):
            jobs.run(job, project)
        self.assertFalse(jobs.cache(project).exists(), 'and go when the job ends')
        self.assertEqual((jobs.read(job, project)['status'], jobs.read(job, project)['result']), ('done', {'ok': True}))
        self.assertEqual(jobs.read(job, project)['progress'], {'done': 1, 'total': 2, 'stage': 'half'})
        with self.assertRaises(ValueError): jobs.read('../state', project)
        job = jobs.start('audit', project, {})
        record = json.loads((jobs.folder(project) / f'{job}.json').read_text())
        record.update(status='running', pid=2 ** 22 + 12345)
        (jobs.folder(project) / f'{job}.json').write_text(json.dumps(record))
        self.assertEqual(jobs.read(job, project)['status'], 'failed')
        self.assertIn('start it again', jobs.read(job, project)['error'])
        import signal
        import time
        job = jobs.start('audit', project, {})
        self.addCleanup(signal.signal, signal.SIGTERM, signal.getsignal(signal.SIGTERM))
        def work(project, arguments, progress):
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(5)
        with mock.patch.dict(agent_tools.JOBS, {'audit': work}):
            self.assertEqual(jobs.run(job, project), 1)
        self.assertIn('KeyboardInterrupt', jobs.read(job, project)['error'])

    def test_a_project_reads_only_its_own_jobs_and_keeps_only_its_last_ones(self):
        other = Path(self.tmp.name) / 'other'
        other.mkdir()
        (other / 'package.json').write_text('{}')
        theirs = jobs.start('audit', str(other), {})
        os.chdir(self.project)
        self.addCleanup(os.chdir, ROOT)
        self.assertIn(theirs, agent_tools.wait(theirs, 0, str(other))['job'])
        for read in (lambda: agent_tools.wait(theirs, 0), lambda: jobs.read(theirs, str(self.project))):
            with self.assertRaisesRegex(ValueError, 'no job named'): read()
        legacy = jobs.folder(str(self.project)).parent.parent.parent / 'jobs'
        legacy.mkdir()
        (legacy / 'audit-old.json').write_text('{}')
        os.utime(legacy / 'audit-old.json', (0, 0))
        with mock.patch.object(jobs, 'KEEP', 2), mock.patch.dict(agent_tools.JOBS, {'audit': lambda *given: {}}):
            for _ in range(3): jobs.run(jobs.start('audit', str(self.project), {}), str(self.project))
        self.assertEqual(len(list(jobs.folder(str(self.project)).glob('*.json'))), 2, 'a project keeps its last jobs only')
        self.assertFalse(legacy.exists(), "the folder older versions shared between projects goes")

class QuestionTests(Home):
    """The person's questions about their code: impact, ask and tools_check."""

    def call(self, name, arguments):
        from eaos.interfaces.mcp_server import build
        os.chdir(self.project)
        self.addCleanup(os.chdir, ROOT)
        return json.loads(asyncio.run(build().call_tool(name, arguments)).content[0].text)

    def test_questions_wait_for_a_check_then_answer_from_its_facts(self):
        import shutil
        from eaos.analysis.dossier import assemble
        self.assertIn('audit', self.call('impact', {'target': 'src/a.js'})['error'])
        self.assertIn('audit', self.call('ask', {'question': 'pricing'})['error'])
        project = Path(self.tmp.name) / 'polyglot'
        shutil.copytree(ROOT / 'tests/fixtures/polyglot', project)
        git_project(project)
        self.project = project
        report = guided.report_of(agent_tools.state_of(str(project)))
        assemble(project, report)
        (report / 'plan.json').write_text('{}')
        touched = self.call('impact', {'target': 'core/pricing.py'})
        self.assertEqual(sorted(touched['direct_dependents']), ['cli.py', 'core/audit.py', 'worker/tasks.py'])
        self.assertTrue(touched['limits'], 'what the answer cannot see is said with it')
        found = self.call('ask', {'question': 'price_for'})
        self.assertEqual(found['status'], 'ANSWERED')
        self.assertTrue(all(answer.get('id') for answer in found['answers']))

    def test_the_tools_say_this_version_and_what_this_project_needs(self):
        from eaos import __version__
        checked = self.call('tools_check', {})
        self.assertEqual(checked['eaos']['version'], __version__)
        self.assertEqual(checked['total'], len(checked['tools']))
        needed = {row['name']: row['needed_here'] for row in checked['tools']}
        self.assertFalse(needed['sqlfluff'], 'a project without SQL does not need the SQL linter')
        self.assertNotIn('sqlfluff', checked['for_the_check']['needed'])
        if checked['for_the_check']['failed']:
            self.assertEqual(checked['install'], 'eaos tools install')


if __name__ == '__main__':
    unittest.main()


class PersonOnly(Home):
    """What only the person decides, from a terminal and from the governance tools: refused without their word, and
    refused inside a Studio run even with it (eaos/interfaces/govern.py, eaos/interfaces/terminal.py, eaos/interfaces/mcp_govern.py)."""

    def setUp(self):
        super().setUp()
        from eaos.interfaces import govern
        govern._core.cache_clear()
        self.addCleanup(govern._core.cache_clear)
        wave_branch(self.project)
        state = agent_tools.state_of(str(self.project))
        state['waves'] = [{'number': 1, 'branch': 'eaos/wave-1', 'status': 'applied'}]
        guided.save(state)

    def eaos(self, *argv, studio_run=False):
        """(exit, printed) of one eaos command, nobody at the terminal."""
        import contextlib, io
        from eaos.interfaces import cli
        env = {'EAOS_STUDIO_RUN': 'r1'} if studio_run else {}
        with contextlib.redirect_stdout(io.StringIO()) as printed, mock.patch.dict(os.environ, env), \
                mock.patch('sys.stdin.isatty', return_value=False):
            code = cli.main([*argv, '--lang', 'en'])
        return code, printed.getvalue()

    def has(self, branch):
        return subprocess.run(['git', '-C', str(self.project), 'rev-parse', '--verify', '-q', branch], capture_output=True).returncode == 0

    def test_accept_and_undo_say_what_happens_and_wait_for_a_yes_never_given_inside_a_studio_run(self):
        code, printed = self.eaos('accept', str(self.project))
        self.assertEqual(code, 4)
        self.assertIn('merges eaos/wave-1 into', printed)
        self.assertIn('eaos accept', printed.split('copy and paste')[-1])
        self.assertEqual(self.eaos('accept', str(self.project), '--yes', studio_run=True)[0], 3)
        self.assertEqual(self.eaos('undo', str(self.project), '--yes', studio_run=True)[0], 3)
        with mock.patch('sys.stdin.isatty', return_value=True), mock.patch('builtins.input', side_effect=EOFError):
            from eaos.interfaces import cli
            self.assertEqual(cli.main(['accept', str(self.project), '--lang', 'en']), 5, 'the input ended: a no, never a traceback')
        self.assertEqual(agent_tools.undo(str(self.project))['status'], 'needs_agreement', 'the tool waits for the person too')
        self.assertTrue(self.has('eaos/wave-1'), 'nothing happened without the person')
        code, printed = self.eaos('undo', str(self.project), '--yes')
        self.assertEqual(code, 0, printed)
        self.assertFalse(self.has('eaos/wave-1'))

    def test_branch_changes_answers_and_a_fix_that_accepts_itself_need_the_persons_word_and_never_in_a_studio_run(self):
        from eaos.interfaces import govern, mcp_govern
        subprocess.run(['git', '-C', str(self.project), 'branch', 'feature'], check=True)
        for argv in (('branch', 'eaos/wave-1', '--yes'), ('branches', 'delete', 'feature', '--yes'), ('answer', 'q1', 'yes'),
                     ('fix', 'TASK-001', '--auto-accept', '--yes')):
            self.assertEqual(self.eaos(*argv, '--project', str(self.project), studio_run=True)[0], 3, argv)
        with mock.patch.dict(os.environ, {'EAOS_STUDIO_RUN': 'r1'}):
            for call in (lambda: mcp_govern.branch_op('delete', 'feature', project=str(self.project)),
                         lambda: mcp_govern.waiting_op('answer', 'q1', 'yes', person_said='yes', project=str(self.project)),
                         lambda: mcp_govern.act_op('fix', ['TASK-001'], op='start', auto_accept=True, person_agreed=True, project=str(self.project))):
                self.assertRaises(PermissionError, call)
        self.assertEqual(self.eaos('branches', 'delete', 'feature', '--project', str(self.project))[0], 4)
        shown = mcp_govern.branch_op('delete', 'feature', project=str(self.project))
        asked = mcp_govern.branch_op('delete', 'feature', confirm=shown['confirm'], project=str(self.project))
        self.assertEqual(asked['status'], 'needs_the_person')
        self.assertTrue(self.has('feature'), 'a confirm token proves a preview was seen, not that the person agreed')
        mcp_govern.branch_op('delete', 'feature', confirm=shown['confirm'], person_agreed=True, project=str(self.project))
        self.assertFalse(self.has('feature'))
        kept = govern.core(str(self.project)).branches.recoveries()[-1]['id']
        self.assertEqual(self.eaos('branches', 'restore', kept, '--project', str(self.project), '--yes', studio_run=True)[0], 3)
        with mock.patch.dict(os.environ, {'EAOS_STUDIO_RUN': 'r1'}):
            self.assertRaises(PermissionError, lambda: mcp_govern.branch_op('restore', kept, person_agreed=True, project=str(self.project)))
        self.assertEqual(self.eaos('branches', 'restore', kept, '--project', str(self.project))[0], 4)
        self.assertEqual(mcp_govern.branch_op('restore', kept, project=str(self.project))['status'], 'needs_the_person')
        self.assertFalse(self.has('feature'), 'a deleted branch comes back only with the person\'s yes')
        self.assertEqual(mcp_govern.act_op('fix', ['TASK-001'], op='start', auto_accept=True, project=str(self.project))['status'], 'needs_the_person')
        self.assertIn('no reply', mcp_govern.waiting_op('answer', 'q1', 'yes', project=str(self.project))['why'])
        govern.shown('q1')
        self.assertIn('not answered yet', mcp_govern.waiting_op('answer', 'q1', 'yes', person_said='yes', project=str(self.project))['why'])
        govern._SHOWN['q1'] -= agent_tools.ANSWER_SECONDS
        with mock.patch.object(govern, 'answer', return_value={'status': 'answered'}) as answered:
            self.assertEqual(mcp_govern.waiting_op('answer', 'q1', 'yes', person_said='نعم', project=str(self.project))['status'], 'answered')
        answered.assert_called_once()

    def test_the_mcp_wait_follows_a_job_of_the_project_it_names(self):
        from eaos.interfaces import mcp_server
        with mock.patch.object(agent_tools, 'wait', return_value={'status': 'running'}) as waited:
            mcp_server.functions()['wait'](job='audit-1', seconds=0, project=str(self.project))
        waited.assert_called_once_with('audit-1', 0, str(self.project))
