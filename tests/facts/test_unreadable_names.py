"""A file whose name is not valid UTF-8 never stops a check: everything else is read, the file is named as not read, the check
says PARTIAL, and the project is left byte for byte as it was."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from eaos.core.system.process import run_command
from eaos.engines.process import state_digest
from eaos.facts.run import ORDER, collect
from eaos.interfaces import cli

BAD = os.fsdecode(b'caf\xe9.py')
SHOWN = 'caf\\xe9.py'


def _git(project, *argv):
    return subprocess.run(['git', '-C', str(project), '-c', 'user.name=t', '-c', 'user.email=t@t', *argv],
                          check=True, capture_output=True).stdout


def _project(where, layout):
    """A project of one good source file and one badly named, committed, not committed, or with no git at all."""
    where.mkdir()
    try: (where / BAD).write_bytes(b'def bad():\n    return 1\n')
    except OSError as refused: raise unittest.SkipTest(f'this file system refuses such a name: {refused}')
    (where / 'ok.py').write_text('def good():\n    return 2\n', encoding='utf-8')
    if layout == 'no git': return where
    _git(where, 'init', '-q')
    _git(where, 'add', '-A' if layout == 'committed' else 'ok.py')
    _git(where, 'commit', '-qm', 'first')
    return where


def _tree(project):
    return sorted((path.relative_to(project).as_posix().encode('utf-8', 'surrogateescape'), path.read_bytes())
                  for path in project.rglob('*') if path.is_file() and '.git' not in path.parts)


class Facts(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)

    def _collected(self, layout):
        project = _project(self.root / layout.replace(' ', '-'), layout)
        before = _tree(project)
        done = collect(project, self.root / f'{layout}-facts', list(ORDER))
        self.assertEqual(_tree(project), before, 'the project is never changed')
        return project, done

    def test_each_layout_reads_the_good_file_and_names_the_other_as_not_read(self):
        for layout in ('committed', 'not committed', 'no git'):
            with self.subTest(layout):
                _, done = self._collected(layout)
                self.assertEqual([row['path'] for row in done['unread_names']], [SHOWN])
                syntax = json.loads((self.root / f'{layout}-facts' / 'facts' / 'syntax.json').read_text(encoding='utf-8'))
                said = json.dumps(syntax['facts'])
                self.assertIn('good', said)
                self.assertNotIn('bad', said, 'a file not read has no facts of a clean file')

    def test_the_commits_history_still_reads_and_the_record_keeps_the_original_bytes(self):
        _, done = self._collected('committed')
        history = json.loads((self.root / 'committed-facts' / 'facts' / 'history.json').read_text(encoding='utf-8'))
        self.assertEqual(history['summary']['commits_analysed'], 1)
        index = json.loads((self.root / 'committed-facts' / 'facts' / 'index.json').read_text(encoding='utf-8'))
        self.assertEqual(index['unread_names'], done['unread_names'])
        self.assertEqual(done['unread_names'][0]['raw_base64'], 'Y2Fm6S5weQ==')

    def test_a_folder_so_named_is_said_with_what_it_holds_unread(self):
        project = _project(self.root / 'folder', 'no git')
        (project / os.fsdecode(b'old\xff')).mkdir()
        (project / os.fsdecode(b'old\xff') / 'inner.py').write_text('x = 1\n', encoding='utf-8')
        done = collect(project, self.root / 'folder-facts', list(ORDER))
        self.assertEqual(sorted(row['path'] for row in done['unread_names']), [SHOWN, 'old\\xff'])


class TheEngines(unittest.TestCase):
    def test_a_change_to_such_a_file_is_still_seen_and_a_tool_naming_it_is_still_read(self):
        with tempfile.TemporaryDirectory() as scratch:
            project = _project(Path(scratch) / 'app', 'no git')
            before = state_digest(project)
            (project / BAD).write_bytes(b'def bad():\n    return 22222\n')
            self.assertNotEqual(state_digest(project), before, 'the proof no analyzer edited the project covers this file too')
        said = run_command([sys.executable, '-c', r"import sys; sys.stdout.buffer.write(b'caf\xe9.py')"], 30)
        self.assertEqual((said.returncode, said.stdout), (0, SHOWN))


class TheCheck(unittest.TestCase):
    def test_the_check_goes_on_is_never_complete_and_says_it_in_red(self):
        for layout in ('committed', 'not committed', 'no git'):
            with self.subTest(layout), tempfile.TemporaryDirectory() as scratch:
                root = Path(scratch)
                project = _project(root / 'app', layout)
                before = _tree(project)
                with open(os.devnull, 'w') as quiet, unittest.mock.patch('sys.stdout', quiet):
                    cli.main(['audit', str(project), '--out', str(root / 'out'), '--skip', 'engines'])
                manifest = json.loads((root / 'out' / 'run-manifest.json').read_text(encoding='utf-8'))
                self.assertEqual(_tree(project), before)
                self.assertEqual(manifest['status'], 'PARTIAL')
                self.assertEqual(manifest['stages']['facts']['status'], 'ok')
                self.assertEqual(manifest['stages']['reports']['status'], 'ok')
                self.assertTrue(next(row for row in manifest['coverage'] if row['loop'] == 'understand')['big'])
                for page in ('RUN.md', 'START-HERE.md'):
                    self.assertIn(SHOWN, (root / 'out' / page).read_text(encoding='utf-8'), page)


if __name__ == '__main__':
    unittest.main()
