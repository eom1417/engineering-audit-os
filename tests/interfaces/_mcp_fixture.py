"""Shared by the MCP tests: a git project, a wave branch, and the base class with its own home."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def git_project(where):
    where.mkdir(parents=True, exist_ok=True)
    (where / 'package.json').write_text('{"name": "shop", "scripts": {"dev": "vite"}}\n')
    (where / 'src').mkdir()
    (where / 'src/a.js').write_text('export const a = 1;\nexport const b = 2;\n')
    for argv in (['init', '-q'], ['add', '-A'],
                 ['-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'first']):
        subprocess.run(['git', '-C', str(where), *argv], check=True, capture_output=True)
    return where


def wave_branch(project, name='eaos/wave-1', file='src/a.js', text='export const a = 5;\nexport const b = 2;\n'):
    """A batch's branch in the project, one EAOS commit ahead, as fix_finish leaves it; the project stays on its branch.
    """
    run = lambda *argv: subprocess.run(['git', '-C', str(project), *argv], check=True, capture_output=True,
                                       text=True).stdout.strip()
    here = run('rev-parse', '--abbrev-ref', 'HEAD')
    run('checkout', '-q', '-b', name)
    (Path(project) / file).write_text(text)
    run('add', '-A')
    run('-c', 'user.name=EAOS', '-c', 'user.email=eaos@localhost', 'commit', '-qm',
        'Fix a thing\n\nEAOS-Task: TASK-001\nEAOS-Card: 0123456789ab')
    run('checkout', '-q', here)
    return run('rev-parse', name)


class Home(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(self.tmp.name) / 'home')})
        patcher.start(); self.addCleanup(patcher.stop)
        self.project = git_project(Path(self.tmp.name) / 'shop')
