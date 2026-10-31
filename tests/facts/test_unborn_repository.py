"""A repository with no commit yet is a project whose history is not there: the check reads everything else and says why."""
import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.facts.code import history
from eaos.interfaces import cli


class NoCommitYet(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.project = self.root / 'app'
        self.project.mkdir()
        (self.project / 'ok.py').write_text('def good():\n    return 2\n', encoding='utf-8')
        subprocess.run(['git', '-C', str(self.project), 'init', '-q'], check=True)

    def said(self, *argv):
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(list(argv))
        return code, out.getvalue()

    def test_facts_are_read_and_the_history_says_why_it_is_not_there(self):
        code, _ = self.said('facts', str(self.project), '--out', str(self.root / 'facts'))
        self.assertEqual(code, 0)
        history = json.loads((self.root / 'facts' / 'facts' / 'history.json').read_text(encoding='utf-8'))
        self.assertEqual((history['available'], history['facts']), (False, []))
        self.assertIn('no commit yet', history['reason'])
        syntax = json.loads((self.root / 'facts' / 'facts' / 'syntax.json').read_text(encoding='utf-8'))
        self.assertIn('good', json.dumps(syntax['facts']))


    def test_the_check_goes_on_as_for_a_project_with_no_git_at_all(self):
        no_git = self.root / 'plain'
        no_git.mkdir()
        (no_git / 'ok.py').write_text('def good():\n    return 2\n', encoding='utf-8')
        manifests = []
        for project, out in ((self.project, 'a'), (no_git, 'b')):
            self.said('audit', str(project), '--out', str(self.root / out), '--skip', 'engines', '--lang', 'en')
            manifests.append(json.loads((self.root / out / 'run-manifest.json').read_text(encoding='utf-8')))
        unborn, plain = manifests
        self.assertEqual(unborn['stages']['reports']['status'], 'ok')
        self.assertEqual(unborn['status'], plain['status'])
        self.assertEqual({name: row['status'] for name, row in unborn['stages'].items()}, {name: row['status'] for name, row in plain['stages'].items()})

    def test_a_git_that_truly_fails_is_still_said(self):
        with mock.patch.object(history, 'git', side_effect=[mock.Mock(returncode=0, stdout='true\n'), mock.Mock(returncode=0, stdout='abc\n'), mock.Mock(returncode=128, stdout='')]):
            with self.assertRaises(ValueError):
                history.run(self.project)


if __name__ == '__main__':
    unittest.main()
