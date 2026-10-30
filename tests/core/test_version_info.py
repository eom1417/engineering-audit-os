"""Which commit EAOS says it is (2026-10-30): pip's record of the commit it was installed from, else EAOS's own checkout;
never the commit of a repository EAOS only happens to sit in (a .venv inside a person's project)."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import eaos

CODE = Path(eaos.__file__).resolve().parent
ASK = 'from eaos.core.system.version_info import commit; print(commit())'


def git(*args, cwd):
    return subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', *args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout.strip()


def said(packages):
    """The commit a fresh Python with EAOS at `packages` says, its pip record aside (none is found there)."""
    return subprocess.run([sys.executable, '-I', '-c', f'import sys; sys.path.insert(0, {str(packages)!r}); {ASK}'],
                          capture_output=True, text=True, check=True, cwd=packages).stdout.strip()


class VersionCommit(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def copy(self, folder):
        shutil.copytree(CODE, folder / 'eaos', ignore=shutil.ignore_patterns('__pycache__'))
        return folder

    def test_inside_a_persons_repository_it_never_says_their_commit(self):
        project = self.tmp / 'project'
        packages = project / '.venv' / 'site-packages'
        packages.mkdir(parents=True)
        git('init', '-q', cwd=project)
        git('commit', '-q', '--allow-empty', '-m', 'the person', cwd=project)
        self.copy(packages)
        self.assertEqual(said(packages), '')

    def test_its_own_checkout_says_its_commit(self):
        checkout = self.copy(self.tmp / 'checkout')
        git('init', '-q', cwd=checkout)
        git('add', 'eaos', cwd=checkout)
        git('commit', '-q', '-m', 'eaos', cwd=checkout)
        self.assertEqual(said(checkout), git('rev-parse', '--short=12', 'HEAD', cwd=checkout))


if __name__ == '__main__':
    unittest.main()
