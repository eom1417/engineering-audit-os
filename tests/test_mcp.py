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
                         'fix_finish', 'accept', 'undo', 'open_report', 'blueprint_start', 'blueprint_spec', 'blueprint_design',
                         'build_start', 'build_edit', 'build_finish'} <= names)
        self.assertEqual({p.name for p in prompts.prompts}, {'audit', 'fix', 'status', 'build', 'continue', 'report', 'tasks', 'ask', 'tools'})
        answer = json.loads(called.content[0].text)
        self.assertEqual((answer['project'], answer['next']['tool']), (str(self.project.resolve()), 'audit'),
                         'the folder the assistant was opened in is the project')

    def test_the_branch_is_chosen_and_a_note_left_over_stdio(self):
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
                    await session.initialize()
                    asked = await session.call_tool('status', {})
                    listed = await session.call_tool('branches', {})
                    chosen = await session.call_tool('choose_branch', {'branch': 'develop', 'person_said': 'الفرع اللي تنصح فيه'})
                    noted = await session.call_tool('note', {'text': 'develop is where the work goes on; checking it next.'})
                    after = await session.call_tool('status', {})
                    return [json.loads(r.content[0].text) for r in (asked, listed, chosen, noted, after)]

        asked, listed, chosen, noted, after = asyncio.run(talk())
        self.assertEqual((asked['next']['tool'], asked['recommended']), ('choose_branch', 'develop'))
        self.assertEqual({b['name'] for b in listed['branches']}, {'develop', 'master'})
        self.assertEqual((chosen['status'], after['branch'], after['next']['tool']), ('chosen', 'develop', 'audit'))
        self.assertTrue(noted['noted'])
        self.assertEqual(after['handover']['notes'][-1]['by'], 'Codex')
        self.assertEqual([s['tool'] for s in after['handover']['last_steps']], ['choose_branch', 'note'])

    def test_an_error_reaches_the_assistant_as_words_to_act_on(self):
        from eaos.mcp_server import _answer
        empty = Path(self.tmp.name) / 'empty'                 # no project file and no repository under it
        empty.mkdir()
        answer = json.loads(_answer(lambda: agent_tools.status(str(empty)))())
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
            state['safety'] = {'commit': state['scanned_commit']}; guided.save(state)
            self.assertEqual(agent_tools.status(project)['next']['tool'], 'fix_start')
            wave_branch(self.project)
            state['waves'] = [{'number': 1, 'branch': 'eaos/wave-1', 'status': 'applied'}]; guided.save(state)
            self.assertEqual(agent_tools.status(project)['next']['tool'], 'accept or undo')

    def test_accept_waits_for_the_person(self):
        state = agent_tools.project_state(str(self.project))
        wave_branch(self.project)
        state['waves'] = [{'number': 1, 'branch': 'eaos/wave-1', 'status': 'applied'}]
        guided.save(state)
        self.assertEqual(agent_tools.accept(str(self.project))['status'], 'needs_agreement')


class ExecutionRecordTests(Home):
    def test_a_card_the_assistant_fixed_is_recorded_like_any_other(self):
        """The trial of 2026-09-29: fix_finish failed on 'assistant' not in ['codemod', 'model'] for every batch with an
        assistant's fix."""
        from eaos.execute import record
        runtime = Path(self.tmp.name) / 'runtime'
        for tool in ('codemod', 'model', 'assistant'):
            record(runtime, {'id': f'TASK-{tool}', 'tool': tool, 'status': 'VERIFIED_IN_ISOLATED_COPY', 'acceptance_exit': 0,
                             'result': 'wave 1'})
        self.assertEqual(len(json.loads((runtime / 'runtime/execution.json').read_text())['tasks']), 3)


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
            page = guided.publish(state)                           # the step goes on
        self.assertEqual(page, guided.outputs(state) / 'REPORT.html')
        self.assertIn('broken record', page.read_text(), 'the page says why, instead of an old page left in silence')
        self.assertIn('page: RuntimeError: broken record', guided.report_stamp(state)['errors'])
        self.assertTrue(list((guided.outputs(state) / 'logs').glob('*.log')))

    def test_every_page_says_which_eaos_made_it_and_is_rebuilt_after_an_update(self):
        from eaos.build_info import digest
        state = agent_tools.project_state(str(self.project))
        guided.report_of(state).mkdir(parents=True)
        guided.publish(state)
        made = guided.report_stamp(state)
        self.assertEqual((made['digest'], made['version'], made['errors']), (digest(), __import__('eaos').__version__, []))
        (guided.outputs(state) / '.report.json').write_text(json.dumps({**made, 'digest': 'an-older-eaos'}))
        report = agent_tools._fresh_report(state)
        self.assertTrue(report['rebuilt'])
        self.assertEqual(guided.report_stamp(state)['digest'], digest())
        self.assertFalse(agent_tools._fresh_report(state)['rebuilt'], 'a page this EAOS made is not rebuilt again')

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

    def test_a_stop_ends_the_work_as_an_interrupt_so_what_it_started_ends_with_it(self):
        import signal
        import time
        job = jobs.start('audit', str(self.project), {})
        self.addCleanup(signal.signal, signal.SIGTERM, signal.getsignal(signal.SIGTERM))
        def work(project, arguments, progress):
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(5)
        with mock.patch.dict(agent_tools.JOBS, {'audit': work}):
            self.assertEqual(jobs.run(job), 1)
        self.assertIn('KeyboardInterrupt', jobs.read(job)['error'])

    def test_a_job_name_cannot_reach_outside_the_jobs_folder(self):
        with self.assertRaises(ValueError): jobs.read('../state')



class MenuAndQuestionTests(Home):
    """/eaos alone, and the person's questions about their code (eaos/menu.py; impact, ask and tools_check)."""

    def call(self, name, arguments):
        from eaos.mcp_server import build
        os.chdir(self.project)
        self.addCleanup(os.chdir, ROOT)
        return json.loads(asyncio.run(build().call_tool(name, arguments)).content[0].text)

    def test_the_menu_offers_the_check_first_on_a_project_never_checked(self):
        offered = self.call('menu', {'lang': 'ar'})
        first = offered['pages'][0][0]
        self.assertEqual((first['id'], first['label']), ('audit', 'افحص المشروع (موصى به)'))
        self.assertLessEqual(len(offered['pages'][0]), 4)

    def test_questions_wait_for_a_check_then_answer_from_its_facts(self):
        import shutil
        from eaos.dossier import assemble
        self.assertIn('audit', self.call('impact', {'target': 'src/a.js'})['error'])
        self.assertIn('audit', self.call('ask', {'question': 'pricing'})['error'])
        project = Path(self.tmp.name) / 'polyglot'
        shutil.copytree(ROOT / 'tests/fixtures/polyglot', project)
        git_project(project)
        self.project = project
        report = guided.report_of(agent_tools.project_state(str(project)))
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
