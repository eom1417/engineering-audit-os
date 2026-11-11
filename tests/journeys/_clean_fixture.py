"""Shared by the clean tests: a git helper and the base class with its copies."""
import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from eaos.kernel.project import state as project_state
from eaos.doors import cli
from eaos.features.guided.interface import agent_tools
UNIQUE = 'written nowhere else\n'


UNIQUE = 'written nowhere else\n'


def git(where, *argv):
    return subprocess.run(['git', '-C', str(where), '-c', 'user.name=t', '-c', 'user.email=t@t', *argv], check=True,
                          capture_output=True, text=True).stdout.strip()


class Clean(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        env = mock.patch.dict(os.environ,
                              {'EAOS_HOME': str(self.root / 'home'), 'EAOS_OUTPUT': str(self.root / 'out'),
                               'EAOS_ASSISTANT': 'none'})
        env.start()
        self.addCleanup(env.stop)
        self.project = self.make('shop')

    def make(self, name):
        project = self.root / name
        project.mkdir()
        (project / 'app.py').write_text('print(1)\n')
        (project / '.gitignore').write_text('node_modules/\n')
        git(project, 'init', '-q', '-b', 'main')
        git(project, 'add', '-A')
        git(project, 'commit', '-qm', 'first')
        agent_tools.state_of(str(project))
        agent_tools.choose_branch('main', str(project), 'the work goes on here')
        return project

    def state(self, project=None):
        return project_state.load(project or self.project)

    def copy(self, name='WAVE-1', project=None, runtime='runtime'):
        project = project or self.project
        where = Path(self.state(project)['workspace']) / runtime / 'candidates' / name
        where.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'clone', '-q', '--no-hardlinks', str(project), str(where)], check=True,
                       capture_output=True)
        return where

    def clean(self, *argv):
        said = io.StringIO()
        with contextlib.redirect_stdout(said):
            self.assertEqual(cli.main(['clean', '--lang', 'en', *argv]), 0)
        return said.getvalue()

    def assertKept(self, copy, said):
        self.assertTrue(copy.is_dir(), f'{copy.name} was removed')
        self.assertIn(str(copy), said, 'what stays is named, not counted as cleaned')

    def assertRemoved(self, copy):
        self.assertFalse(copy.exists(), f'{copy.name} stayed')
