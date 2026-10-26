"""A batch of the assistants' context (M8.6), from the trim in a copy to the person's accept: the context is lighter on
a branch of its own, every instruction still said once, and nothing reaches the project before the person takes it in."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from analysis.test_context_trim import FILES
from eaos.core.project import state as project_state
from eaos.journeys import agent_tools, guided
from eaos.journeys.agent_tools import tidying
from eaos.journeys.fix import context_batch


def git(root, *argv):
    return subprocess.run(['git', '-C', str(root), '-c', 'user.name=t', '-c', 'user.email=t@t', *argv],
                          check=True, capture_output=True, text=True).stdout.strip()


class ContextBatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for patch in (mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(self.tmp.name) / 'home')}),
                      mock.patch('eaos.live.isolation.sandbox.refusal', return_value=''), mock.patch.object(guided, 'publish')):
            patch.start()
            self.addCleanup(patch.stop)
        self.project = p = Path(self.tmp.name) / 'shop'
        for name, text in FILES.items():
            (p / name).parent.mkdir(parents=True, exist_ok=True)
            (p / name).write_text(text, encoding='utf-8')
        git(p, 'init', '-q', '-b', 'main')
        git(p, 'add', '-A')
        git(p, 'commit', '-qm', 'one')
        guided.save({'project': str(p), 'workspace': str(guided.workspace(p)), 'lang': 'en', 'branch': 'main'})
        runtime = project_state.runtime_of(project_state.load(p))
        runtime.mkdir(parents=True, exist_ok=True)
        (runtime / 'authorization.json').write_text(json.dumps({'commit': git(p, 'rev-parse', 'HEAD')}))

    def test_the_trim_waits_on_its_own_branch_and_reaches_the_project_only_when_the_person_accepts_it(self):
        drawn = context_batch.proposal(self.project)
        self.assertEqual(drawn['archive'], ['- [x] Build the login page with the session cookie'])
        self.assertLess(drawn['tokens_after'], drawn['tokens_before'])
        answer = tidying._context_job(str(self.project), {'private_to': 'DEVELOPING.md'}, lambda *_: None)
        self.assertEqual(answer['branch'], 'eaos/main/context-1')
        self.assertIn('- [x] Build the login page', (self.project / 'AGENTS.md').read_text(), 'nothing changed before the decision')
        self.assertIn('DEVELOPING.md', git(self.project, 'show', '--name-only', '--format=', answer['branch']).split())
        self.assertEqual(agent_tools.accept(str(self.project), person_agreed=True)['status'], 'accepted')
        self.assertNotIn('- [x]', (self.project / 'AGENTS.md').read_text())
        self.assertIn('I want every answer in Arabic, short.', (self.project / 'DEVELOPING.md').read_text())

    def test_a_private_place_outside_the_repository_or_in_an_assistants_folder_is_refused(self):
        for place in ('../notes.md', '/root/notes.md', '.claude/notes.md'):
            summary = context_batch.make({'target': self.project, 'runtime': project_state.runtime_of(project_state.load(self.project)),
                                          'number': 1, 'private_to': place})
            self.assertEqual(summary['kept'], [])
            self.assertTrue(summary['refused'][0].endswith(('outside the repository', "an assistant's own folder")), summary['refused'])
