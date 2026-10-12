"""The guided way in: every user command ends with the next-step box, errors read in plain words, questions wait for a
yes, the fix step hands over to the person's assistant, and the project folder is never written."""
import io
import json
import os
import subprocess
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from eaos import guided

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
    page = guided.start_here(out, state['lang'], 'shop')
    guided.box(state['lang'], 'scanned', where=page, commands=['eaos next'])
    return 0


def run(command, project=None, **options):
    """(exit, printed) of one guided command, in-process, answered by nobody at a terminal."""
    args = Namespace(command=command, project=str(project) if project else ('.' if command != 'doctor' else None),
                     lang=options.get('lang', 'en'), yes=options.get('yes', False), fix=False,
                     request=options.get('request', ['where', 'are', 'we']), action='install')
    printed = io.StringIO()
    steps = [(i, ar, en, done, _fake_scan if i == 'scan' else step) for i, ar, en, done, step in guided.STEPS]
    # Never the person's real assistants (`eaos assistant install` writes into ~/.claude and ~/.codex), never the Studio,
    # and no version check of every installed tool: the doctor's rows are tested on their own.
    with redirect_stdout(printed), mock.patch.object(guided, 'STEPS', steps), mock.patch.object(guided, 'watch'), \
            mock.patch.object(guided.sys.stdin, 'isatty', return_value=False), \
            mock.patch('eaos.toolchain.doctor', return_value={'tools': []}), \
            mock.patch('eaos.assistants.readiness.probe_all', return_value=NO_ASSISTANT), \
            mock.patch('eaos.assistant_setup.install', return_value=['Claude Code', 'Codex']):
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
        return guided.current(self.project)

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
        after = subprocess.run(['git', 'status', '--porcelain', '--ignored'], cwd=self.project, capture_output=True, text=True).stdout
        self.assertEqual(before, after)
        self.assertNotIn(str(self.project), str(guided.workspace(self.project).parent))
        state = guided.load(self.project)
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
            self.assertIsNone(guided.load(folder))
            self.assertNotIn('log', printed.lower())
        self.assertTrue(guided.looks_like_project(self.project))
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
        with mock.patch.object(guided.sys.stdin, 'isatty', return_value=False):
            with self.assertRaises(guided.NeedsAnswer):
                guided.ask(state, 'install_tools', 'Install?')
            self.assertTrue(guided.ask(state, 'install_tools', 'Install?', yes=True))
        kept = guided.current(self.project)['questions']
        self.assertEqual([(q['id'], q['kind'], q['answer']) for q in kept], [('install_tools', 'yes_no', True)])
        def asks(state, args): guided.ask(state, 'run_app', 'May I run your app?', args.yes); return 0
        printed = io.StringIO()
        with mock.patch.object(guided, 'STEPS', [('x', 'x', 'x', lambda s: False, asks)]), redirect_stdout(printed), \
                mock.patch.object(guided.sys.stdin, 'isatty', return_value=False):
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
        log = next((guided.outputs(guided.load(self.project)) / 'logs').glob('*.log'))
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
        with redirect_stdout(printed), mock.patch('eaos.waves.open_batch') as opened, mock.patch('eaos.waves.finish_batch') as finished:
            self.assertEqual(guided.fix(state, Namespace(yes=True)), 0)
        opened.assert_not_called()
        finished.assert_not_called()
        self.assertIn('1 fixes are ready', printed.getvalue())
        self.assertIn('/eaos', printed.getvalue())
        self.assertIn('eaos studio', printed.getvalue())
        self.assertFalse(guided.load(self.project).get('open_wave'))


class Pages(unittest.TestCase):
    def test_the_first_page_counts_from_the_plan_in_the_persons_language_and_the_run_says_which_stage_it_is_on(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'plan.json').write_text(json.dumps({'tasks': [
                *[{'pattern': 'remove_dead', 'kind': 'remediate', 'decision': {'readiness': 'ready'}, 'paths': ['a.ts']}] * 5,
                {'pattern': 'broken_code', 'kind': 'remediate', 'decision': {'readiness': 'ready'}, 'paths': ['b.ts']},
                {'pattern': 'hotspot', 'kind': 'investigate', 'decision': {'readiness': 'blocked'}, 'paths': ['c.ts']}]}))
            text = guided.start_here(tmp, 'en', 'shop').read_text()
            self.assertIn('I found **7** problems', text)
            self.assertIn('**6** of them EAOS can fix automatically', text)
            self.assertLess(text.index('Broken code'), text.index('Dead code'))
            self.assertIn('eaos next', text)
            (Path(tmp) / 'plan.json').write_text(json.dumps({'tasks': [
                {'pattern': 'canonicalize', 'kind': 'remediate', 'decision': {'readiness': 'ready'}, 'paths': ['a.ts']}]}))
            text = guided.start_here(tmp, 'ar', 'shop').read_text()
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
