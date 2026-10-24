"""The guided way in: every user command ends with the next-step box, errors read in plain words, questions wait for a
yes, the fix step hands over to the person's assistant, and the project folder is never written."""
import io
import json
import os
import subprocess
import tempfile
import sys
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from eaos.journeys import guided
from eaos.interfaces import terminal, terminal_branches  # noqa: F401  (the terminal's check, accept and undo, registered in guided)
from eaos.core import project_state
from eaos.report.start_here import start_here

BOX_END = guided.LINE


def _project(root):
    project = Path(root) / 'shop'
    (project / 'src').mkdir(parents=True)
    (project / 'package.json').write_text('{"name": "shop", "scripts": {"dev": "vite"}}')
    (project / 'src/a.ts').write_text('export const a = 1;\n')
    subprocess.run(['git', 'init', '-q'], cwd=project, check=True)
    subprocess.run(['git', 'add', '-A'], cwd=project, check=True)
    subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'init'], cwd=project, check=True)
    return project


PLAN = {'tasks': [
    {'id': 'TASK-1', 'pattern': 'broken_code', 'kind': 'remediate', 'decision': {'readiness': 'ready'}, 'paths': ['src/a.ts']},
    {'id': 'TASK-2', 'pattern': 'hotspot', 'kind': 'investigate', 'decision': {'readiness': 'blocked'}, 'paths': ['src/b.ts']}]}


NO_ASSISTANT = [{'id': name, 'name': name, 'ready': False, 'installed': False, 'code': f'{name}_not_installed',
                 'reason': {'en': 'not installed', 'ar': 'غير مثبت'}} for name in ('claude', 'codex')]


def _fake_scan(state, args):
    """The audit itself is tested elsewhere; here a report with a plan stands in for it."""
    out = guided.report_of(state)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'plan.json').write_text(json.dumps(PLAN))
    (out / 'run-manifest.json').write_text(json.dumps({'status': 'COMPLETE', 'stages': {}}))
    page = start_here(out, state['lang'], 'shop')
    guided.box(state['lang'], 'scanned', where=page, commands=['eaos next'])
    return 0


def run(command, project=None, **options):
    """(exit, printed) of one guided command, in-process, answered by nobody at a terminal."""
    args = Namespace(command=command, project=str(project) if project else ('.' if command != 'doctor' else None),
                     lang=options.get('lang', 'en'), yes=options.get('yes', False), fix=False,
                     request=options.get('request', ['where', 'are', 'we']), action='install', path=options.get('path'))
    printed = io.StringIO()
    steps = [(i, ar, en, done, _fake_scan if i == 'scan' else step) for i, ar, en, done, step in guided.STEPS]
    # Never the person's real assistants (`eaos assistant install` writes into ~/.claude and ~/.codex), never the Studio,
    # and no version check of every installed tool: the doctor's rows are tested on their own.
    with redirect_stdout(printed), mock.patch.object(guided, 'STEPS', steps), mock.patch.object(guided, 'watch'), \
            mock.patch.dict(guided.TERMINAL, check=lambda args: _fake_scan(project_state.current(args.project), args)), \
            mock.patch.object(sys.stdin, 'isatty', return_value=False), \
            mock.patch('eaos.core.toolchain.doctor', return_value={'tools': []}), \
            mock.patch('eaos.ai.readiness.probe_all', return_value=NO_ASSISTANT), \
            mock.patch('eaos.ai.setup.install', return_value=['Claude Code', 'Codex']):
        code = guided.main(args)
    return code, printed.getvalue()


class Journey(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(self.tmp.name) / 'home')})
        patcher.start(); self.addCleanup(patcher.stop)
        self.project = _project(self.tmp.name)

    def saved(self):
        guided.save({'project': str(self.project), 'workspace': str(guided.workspace(self.project)), 'lang': 'en'})
        return project_state.current(self.project)

    def test_every_user_command_ends_with_what_to_copy_next(self):
        ended = set()
        for command in guided.USER_COMMANDS:
            _, printed = run(command, self.project)
            lines = printed.rstrip().splitlines()
            if len(lines) >= 2 and lines[-1] == BOX_END and any('copy and paste' in line for line in lines):
                ended.add(command)
        self.assertEqual(ended, set(guided.USER_COMMANDS))

    def test_start_scans_next_knows_where_the_person_is_and_the_project_folder_is_never_written(self):
        before = subprocess.run(['git', 'status', '--porcelain', '--ignored'], cwd=self.project, capture_output=True, text=True).stdout
        code, printed = run('start', self.project)
        self.assertEqual(code, 0)
        self.assertIn('START-HERE.md', printed)
        run('next', self.project)
        self.assertIn('✅', run('status', self.project)[1])
        self.assertIn('scanned', run('start', self.project, path=['security'])[1], 'a path asked for is a check now, not the next step')
        after = subprocess.run(['git', 'status', '--porcelain', '--ignored'], cwd=self.project, capture_output=True, text=True).stdout
        self.assertEqual(before, after)
        self.assertNotIn(str(self.project), str(guided.workspace(self.project).parent))
        state = project_state.load(self.project)
        self.assertIsNone(guided._saved_note(state))
        (self.project / 'src/a.ts').write_text('export const a = 2;\n')
        self.assertIn('last saved version', guided._saved_note(state), 'unsaved edits are said, never a stop')

    def test_a_folder_that_is_no_project_is_refused_and_says_how_to_start_without_a_log(self):
        empty = Path(self.tmp.name) / 'Downloads'; empty.mkdir()
        (empty / 'notes.txt').write_text('x')
        for folder in (empty, Path.home()):
            code, printed = run('start', folder)
            self.assertEqual(code, 1)
            self.assertIn('not a project', printed)
            self.assertIn('eaos start .', printed)
            self.assertIsNone(project_state.load(folder))
            self.assertNotIn('log', printed.lower())
        self.assertTrue(project_state.looks_like_project(self.project))
        code, printed = run('next', self.project)                    # before start
        self.assertEqual(code, 6)
        self.assertIn('eaos start .', printed)
        self.assertNotIn('log', printed.lower())
        home = Path(self.tmp.name) / 'person'; (home / 'Desktop').mkdir(parents=True)
        with mock.patch.object(guided.Path, 'home', return_value=home):
            guided.save({'project': str(home), 'workspace': str(guided.workspace(home)), 'lang': 'en'})
            code, printed = run('next', home / 'Desktop')
        self.assertEqual(code, 6, 'a record left for the home folder is not gone on with')
        self.assertIn('eaos start .', printed)

    def test_a_question_waits_for_yes_is_kept_and_prints_the_command_that_answers_it(self):
        state = self.saved()
        with mock.patch.object(sys.stdin, 'isatty', return_value=False):
            with self.assertRaises(guided.NeedsAnswer):
                guided.ask(state, 'install_tools', 'Install?')
            self.assertTrue(guided.ask(state, 'install_tools', 'Install?', yes=True))
        kept = project_state.current(self.project)['questions']
        self.assertEqual([(q['id'], q['kind'], q['answer']) for q in kept], [('install_tools', 'yes_no', True)])
        def asks(state, args): guided.ask(state, 'run_app', 'May I run your app?', args.yes); return 0
        printed = io.StringIO()
        with mock.patch.object(guided, 'STEPS', [('x', 'x', 'x', lambda s: False, asks)]), redirect_stdout(printed), \
                mock.patch.object(sys.stdin, 'isatty', return_value=False):
            code = guided.main(Namespace(command='next', project=str(self.project), lang='en', yes=False))
        self.assertEqual(code, 4)
        self.assertIn('eaos next --yes', printed.getvalue())

    def test_a_failure_reads_in_plain_words_and_the_detail_goes_to_a_log(self):
        def breaks(state, args): raise OSError(98, 'Address already in use')
        self.saved()
        printed = io.StringIO()
        with mock.patch.object(guided, 'STEPS', [('x', 'x', 'x', lambda s: False, breaks)]), redirect_stdout(printed):
            code = guided.main(Namespace(command='next', project=str(self.project), lang='en', yes=False))
        self.assertEqual(code, 1)
        self.assertIn('port it needs is used by another program', printed.getvalue())
        self.assertNotIn('Traceback', printed.getvalue())
        log = next((guided.outputs(project_state.load(self.project)) / 'logs').glob('*.log'))
        self.assertIn('Traceback', log.read_text())
        for text, expected in (('fatal: not a git repository (or any parent)', 'not_git'),
                               ('Error: listen EADDRINUSE: address already in use :::5173', 'port_busy'),
                               ('No space left on device', 'no_space'),
                               ('something nobody has seen', 'unknown')):
            self.assertEqual(guided.explain(RuntimeError(text))['id'], expected, text)
        self.assertEqual(guided.explain(KeyboardInterrupt())['id'], 'interrupted')

    def test_the_fix_step_hands_the_fixes_to_the_persons_assistant_and_runs_no_batch(self):
        state = self.saved()
        guided.report_of(state).mkdir(parents=True, exist_ok=True)
        (guided.report_of(state) / 'plan.json').write_text(json.dumps(PLAN))
        printed = io.StringIO()
        with redirect_stdout(printed), mock.patch('eaos.journeys.waves.open_batch') as opened, mock.patch('eaos.journeys.waves.finish_batch') as finished:
            self.assertEqual(guided.fix(state, Namespace(yes=True)), 0)
        opened.assert_not_called()
        finished.assert_not_called()
        self.assertIn('1 fixes are ready', printed.getvalue())
        self.assertIn('/eaos', printed.getvalue())
        self.assertIn('eaos studio', printed.getvalue())
        self.assertFalse(project_state.load(self.project).get('open_wave'))


class Bulk(unittest.TestCase):
    def test_a_new_check_replaces_the_previous_checks_bulky_data_and_clean_deletes_old_pictures_on_request(self):
        # EAOS's own report kept 230 MB of pictures and 130 MB of the assistant's raw runs from check to check
        from eaos.pipeline import run as pipeline
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(folder) / 'home')}):
            report = guided.outputs_root() / 'shop/technical'
            bulky = ['live/screens/screenshots/00-index-dark-phone.png', 'live/screens.json', 'live/crawl/x/thumb.jpg',
                     'nodes/visual_reviewer/runs/r1/prompt.txt', 'nodes/card_triage/cache/k.json', 'engines/gitnexus/copy/a.ts']
            kept = ['dossier.json', 'studio/screens.json', 'nodes/visual_reviewer/findings.json', 'live/setup.json', 'engines/engines.json']
            for name in bulky + kept:
                (report / name).parent.mkdir(parents=True, exist_ok=True)
                (report / name).write_text('x')
            with mock.patch.object(pipeline, 'execute', return_value={'status': 'COMPLETE'}):
                pipeline.check(_project(folder), report, language='en', only=['facts'])
                self.assertTrue(all((report / name).exists() for name in bulky), 'a run of some stages keeps them')
                pipeline.check(_project(Path(folder) / 'b'), report, language='en')
            self.assertEqual([name for name in bulky + kept if (report / name).exists()], kept)
            for name in ('live/screens/screenshots/00-index-default-phone.png', 'nodes/visual_reviewer/runs/r2/prompt.txt',
                         'branches/fix/technical/live/crawl/lighthouse/00/lighthouse.json'):
                path = report / name if not name.startswith('branches') else report.parent / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('x')
            with redirect_stdout(io.StringIO()):
                guided.clean(Namespace(lang='en', pictures=False, project='.'))
                self.assertTrue((report / 'live/screens').exists(), 'pictures go only when asked')
                guided.clean(Namespace(lang='en', pictures=True, project='.'))
            self.assertEqual([p for p in ('technical/live/screens', 'technical/nodes/visual_reviewer/runs', 'branches/fix/technical/live/crawl')
                              if (report.parent / p).exists()], [])
            self.assertTrue((report / 'nodes/visual_reviewer/findings.json').is_file())


class Pages(unittest.TestCase):
    def test_the_first_page_says_repair_or_rebuild_from_the_target_with_each_options_effort_and_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            components = [{'files': 30, 'relation': 'rebuild'}, {'files': 10, 'relation': 'retain'}]
            (Path(tmp) / 'target-architecture.json').write_text(json.dumps({'current_components': components}))
            (Path(tmp) / 'plan.json').write_text(json.dumps({'tasks': [{'pattern': 'remove_dead', 'effort': 'S', 'paths': ['a.ts']}] * 2}))
            text = start_here(tmp, 'en', 'shop').read_text()
            self.assertIn('**I recommend: rebuild.** The target rebuilds or deletes 30', text)
            self.assertIn('- Repair: 2 cards (2 small, 0 medium, 0 large), touching 1 files, about 11–31 minutes.', text)
            self.assertIn('- Rebuild: 40 files in 2 parts written anew, about 4–11 hours.', text)
            components[0]['relation'] = 'modify'
            (Path(tmp) / 'target-architecture.json').write_text(json.dumps({'current_components': components}))
            self.assertIn('**أنصح بـالإصلاح.**', start_here(tmp, 'ar', 'shop').read_text())

    def test_the_first_page_counts_from_the_plan_in_the_persons_language_and_the_run_says_which_stage_it_is_on(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'plan.json').write_text(json.dumps({'tasks': [
                *[{'pattern': 'remove_dead', 'kind': 'remediate', 'decision': {'readiness': 'ready'}, 'paths': ['a.ts']}] * 5,
                {'pattern': 'broken_code', 'kind': 'remediate', 'decision': {'readiness': 'ready'}, 'paths': ['b.ts']},
                {'pattern': 'hotspot', 'kind': 'investigate', 'decision': {'readiness': 'blocked'}, 'paths': ['c.ts']}]}))
            text = start_here(tmp, 'en', 'shop').read_text()
            self.assertIn('I found **7** problems', text)
            self.assertIn('**6** of them EAOS can fix automatically', text)
            self.assertLess(text.index('Broken code'), text.index('Dead code'))
            self.assertIn('eaos next', text)
            (Path(tmp) / 'plan.json').write_text(json.dumps({'tasks': [
                {'pattern': 'canonicalize', 'kind': 'remediate', 'decision': {'readiness': 'ready'}, 'paths': ['a.ts']}]}))
            text = start_here(tmp, 'ar', 'shop').read_text()
        self.assertIn('كود منسوخ', text)
        self.assertNotIn('Copied code', text)
        from eaos.pipeline import execute
        seen = []
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / 'p'; project.mkdir(); (project / 'a.py').write_text('x = 1\n')
            execute(project, Path(tmp) / 'out', only=('facts',), progress=lambda done, total, stage: seen.append((done, total, stage)))
        self.assertEqual(seen, [(0, 1, 'facts')])

if __name__ == '__main__':
    unittest.main()


class RunConsent(unittest.TestCase):
    def test_a_yes_given_in_the_studio_or_to_the_assistant_lets_the_check_run_the_app(self):
        """The self-check of 2026-10-12: the owner agreed in the Studio (run_setup, consent run_and_fix), yet the check
        read only the terminal's question run_app and said the person had not agreed, so nothing ran."""
        with mock.patch.object(guided.checking, 'runtime_of', return_value='runtime'):
            self.assertIsNone(guided.check_runtime({'questions': []}))
            self.assertEqual(guided.check_runtime({'questions': [], 'consent': {'run_and_fix': True}}), 'runtime')
            self.assertEqual(guided.check_runtime({'questions': [{'id': 'run_app', 'answer': True}]}), 'runtime')
