"""A repository with no commit yet is a project whose history is not there: the check reads everything else and says
why."""
import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

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
        record = json.loads((self.root / 'facts' / 'facts' / 'history.json').read_text(encoding='utf-8'))
        self.assertEqual((record['available'], record['facts']), (False, []))
        self.assertIn('no commit yet', record['reason'])
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

    def test_a_broken_ref_is_said_as_a_failure_never_as_no_commit_yet(self):
        (self.project / '.git/refs/heads').mkdir(parents=True, exist_ok=True)
        branch = subprocess.run(['git', '-C', str(self.project), 'symbolic-ref', '--short', 'HEAD'], check=True, capture_output=True, text=True).stdout.strip()
        (self.project / '.git/refs/heads' / branch).write_text('not a commit\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            history.run(self.project)


if __name__ == '__main__':
    unittest.main()
