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

from eaos import agent_tools, guided, jobs

ROOT = Path(__file__).resolve().parents[1]


def git_project(where):
    where.mkdir(parents=True, exist_ok=True)
    (where / 'package.json').write_text('{"name": "shop", "scripts": {"dev": "vite"}}\n')
    (where / 'src').mkdir()
    (where / 'src/a.js').write_text('export const a = 1;\nexport const b = 2;\n')
    for argv in (['init', '-q'], ['add', '-A'], ['-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'first']):
        subprocess.run(['git', '-C', str(where), *argv], check=True, capture_output=True)
    return where


class Home(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(self.tmp.name) / 'home')})
        patcher.start(); self.addCleanup(patcher.stop)
        self.project = git_project(Path(self.tmp.name) / 'shop')


class ServerTests(Home):
    def test_an_assistant_lists_the_tools_and_calls_one_over_stdio(self):
        from mcp import ClientSession, StdioServerParameters, stdio_client

        async def talk():
            server = StdioServerParameters(command=sys.executable, args=['-m', 'eaos', 'mcp'], cwd=str(self.project),
                                           env={**os.environ, 'PYTHONPATH': str(ROOT)})
            async with stdio_client(server) as (read, write):
                async with ClientSession(read, write) as session:
                    started = await session.initialize()
                    tools = await session.list_tools()
                    prompts = await session.list_prompts()
                    called = await session.call_tool('status', {})
                    return started, tools, prompts, called

        started, tools, prompts, called = asyncio.run(talk())
        self.assertIn('Work on your own until the job is done', started.instructions)
        names = {tool.name for tool in tools.tools}
        self.assertTrue({'status', 'audit', 'wait', 'finding', 'run_setup', 'run_try', 'safety_net', 'fix_start', 'fix_edit',
                         'fix_finish', 'accept', 'undo', 'open_report'} <= names)
        self.assertEqual({p.name for p in prompts.prompts}, {'audit', 'fix', 'status'})
        answer = json.loads(called.content[0].text)
        self.assertEqual((answer['project'], answer['next']['tool']), (str(self.project.resolve()), 'audit'),
                         'the folder the assistant was opened in is the project')

    def test_an_error_reaches_the_assistant_as_words_to_act_on(self):
        from eaos.mcp_server import _answer
        answer = json.loads(_answer(lambda: agent_tools.status(str(Path(self.tmp.name))))())
        self.assertIn('not a project folder', answer['error'])
        self.assertIn('eaos start .', answer['what_now'])


class ToolTests(Home):
    def test_the_assistant_way_never_calls_a_model_itself(self):
        source = (ROOT / 'eaos/agent_tools.py').read_text()
        for call in ('runtime.assistants', 'provider()', '.complete('):
            self.assertNotIn(call, source)
        self.assertIn('change(cards[card_id], root, report, None)', source, 'a codemod card is changed with no model at all')

    def test_nothing_runs_before_the_person_agrees(self):
        answer = agent_tools.run_setup(str(self.project))
        self.assertEqual(answer['status'], 'needs_agreement')
        self.assertIn('separate copy', answer['ask_the_person'])
        self.assertFalse((guided.runtime_of(guided.load(self.project)) / 'authorization.json').exists())
        self.assertEqual(agent_tools.fix_start(str(self.project))['status'], 'needs_agreement')

    def test_an_unsafe_proposal_is_refused_with_its_reason(self):
        state = agent_tools.project_state(str(self.project))
        runtime = guided.runtime_of(state)
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

    def test_a_kept_edit_stays_committed_and_a_failing_one_is_taken_back(self):
        state = agent_tools.project_state(str(self.project))
        report = guided.report_of(state)
        report.mkdir(parents=True)
        card = {'id': 'TASK-001', 'title': 'x', 'paths': ['src/a.js'], 'kind': 'remediate'}
        (report / 'plan.json').write_text(json.dumps({'tasks': [card, {**card, 'id': 'TASK-002'}]}))
        copy = Path(self.tmp.name) / 'copy'
        subprocess.run(['git', 'clone', '-q', str(self.project), str(copy)], check=True)
        base = guided._git(copy, 'rev-parse', 'HEAD').stdout.strip()
        state['open_wave'] = {'number': 1, 'root': str(copy), 'base': base, 'cards': ['TASK-001', 'TASK-002'],
                              'kept': {}, 'failed': {}, 'tools': {}}
        guided.save(state)
        with mock.patch('eaos.facts.run.collect'), \
             mock.patch('eaos.execute.new_breakage', side_effect=[[], ['src/b.js: import of a file that is gone']]), \
             mock.patch('eaos.waves.batch_acceptance', return_value={'TASK-001': 0, 'TASK-002': 0}):
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
        wave = guided.load(self.project)['open_wave']
        self.assertEqual(list(wave['kept']), ['TASK-001'])
        self.assertEqual(agent_tools.fix_finish(str(self.project))['status'], 'cards_left')
        agent_tools.fix_skip('TASK-002', 'needs a product decision', str(self.project))
        self.assertEqual(guided.load(self.project)['open_wave']['failed']['TASK-002'], 'skipped: needs a product decision')

    def test_status_names_the_next_tool_at_each_point(self):
        project = str(self.project)
        self.assertEqual(agent_tools.status(project)['next']['tool'], 'audit')
        state = guided.load(self.project)
        with mock.patch.object(guided, 'scan_done', return_value=True):
            state['scanned_commit'], state['scanned_with'] = agent_tools._head(state), 'an-older-eaos'; guided.save(state)
            self.assertEqual(agent_tools.status(project)['next']['tool'], 'audit', 'a report by an older EAOS is checked again')
            state['scanned_with'] = agent_tools.tool_digest(); guided.save(state)
            self.assertEqual(agent_tools.status(project)['next']['tool'], 'run_setup')
            state['setup'] = {'commit': state['scanned_commit'], 'ok': True}; guided.save(state)
            self.assertEqual(agent_tools.status(project)['next']['tool'], 'safety_net')
            state['safety'] = {'commit': state['scanned_commit']}; guided.save(state)
            self.assertEqual(agent_tools.status(project)['next']['tool'], 'fix_start')
            state['waves'] = [{'number': 1, 'branch': 'eaos/wave-1', 'status': 'applied'}]; guided.save(state)
            self.assertEqual(agent_tools.status(project)['next']['tool'], 'accept or undo')

    def test_accept_waits_for_the_person(self):
        state = agent_tools.project_state(str(self.project))
        state['waves'] = [{'number': 1, 'branch': 'eaos/wave-1', 'status': 'applied'}]
        guided.save(state)
        self.assertEqual(agent_tools.accept(str(self.project))['status'], 'needs_agreement')


class OutputsTests(Home):
    def test_every_output_is_in_one_folder_named_after_the_project(self):
        state = agent_tools.project_state(str(self.project))
        folder = guided.outputs(state)
        self.assertEqual(folder, guided.outputs_root() / 'shop')
        self.assertEqual(guided.report_of(state), folder / 'technical')
        self.assertIn('REPORT.html', (folder / 'README.md').read_text())
        other = git_project(Path(self.tmp.name) / 'elsewhere' / 'shop')
        self.assertEqual(guided.outputs(agent_tools.project_state(str(other))), guided.outputs_root() / 'shop-2',
                         'another project with the same name gets its own folder')
        self.assertNotIn(str(self.project), str(folder), 'nothing is written into the project')
        self.assertFalse(str(folder).startswith(str(Path.home() / 'EAOS')), 'a test never writes into the real home')

    def test_a_report_page_that_cannot_be_built_never_stops_the_step(self):
        state = agent_tools.project_state(str(self.project))
        guided.report_of(state).mkdir(parents=True)
        with mock.patch('eaos.human_report.write', side_effect=RuntimeError('broken record')):
            self.assertEqual(guided.publish(state), guided.report_of(state) / 'START-HERE.md')

    def test_a_report_an_older_eaos_left_is_moved_into_the_folder(self):
        state = agent_tools.project_state(str(self.project))
        old = Path(state['workspace']) / 'report'
        old.mkdir(parents=True)
        (old / 'plan.json').write_text('{"tasks": []}')
        self.assertTrue((guided.report_of(state) / 'plan.json').is_file())
        self.assertFalse(old.exists())

    def test_a_batch_of_fixes_is_published_with_a_summary_and_the_report_opens(self):
        state = agent_tools.project_state(str(self.project))
        (guided.report_of(state)).mkdir(parents=True)
        (guided.report_of(state) / 'plan.json').write_text('{"tasks": []}')
        wave = {'number': 1, 'kept': ['TASK-001'], 'failed': {'TASK-002': 'its problem is still there'}, 'branch': 'eaos/wave-1',
                'stat': '1 file changed'}
        target = guided.publish_fixes(state, wave)
        summary = (target / 'SUMMARY.md').read_text()
        self.assertIn('eaos/wave-1', summary)
        self.assertIn('TASK-002: its problem is still there', summary)
        self.assertEqual(target, guided.outputs(state) / 'fixes' / 'wave-1')
        answer = agent_tools.open_report(str(self.project), show=False)
        self.assertEqual(answer['outputs_folder'], str(guided.outputs(state)))


class JobTests(Home):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(jobs.subprocess, 'Popen', return_value=mock.Mock(pid=os.getpid()))
        patcher.start(); self.addCleanup(patcher.stop)

    def test_a_job_runs_on_its_own_and_its_result_is_read_back(self):
        job = jobs.start('audit', str(self.project), {})
        record = json.loads((jobs.folder() / f'{job}.json').read_text())
        self.assertEqual((record['status'], record['kind']), ('running', 'audit'))
        with mock.patch.dict(agent_tools.JOBS, {'audit': lambda project, arguments, progress: progress(1, 2, 'half') or {'ok': True}}):
            jobs.run(job)
        self.assertEqual((jobs.read(job)['status'], jobs.read(job)['result']), ('done', {'ok': True}))
        self.assertEqual(jobs.read(job)['progress'], {'done': 1, 'total': 2, 'stage': 'half'})

    def test_a_job_whose_process_died_is_said_to_have_failed(self):
        job = jobs.start('audit', str(self.project), {})
        record = json.loads((jobs.folder() / f'{job}.json').read_text())
        record.update(status='running', pid=2 ** 22 + 12345)
        (jobs.folder() / f'{job}.json').write_text(json.dumps(record))
        self.assertEqual(jobs.read(job)['status'], 'failed')
        self.assertIn('start it again', jobs.read(job)['error'])

    def test_a_job_name_cannot_reach_outside_the_jobs_folder(self):
        with self.assertRaises(ValueError): jobs.read('../state')


if __name__ == '__main__':
    unittest.main()
