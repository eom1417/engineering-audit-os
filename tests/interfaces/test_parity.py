"""Parity with the Studio (M8.1): every Studio action has an MCP tool, and the whole journey runs from the terminal alone."""
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
from pathlib import Path

from eaos.core.project.runs import contract
from eaos.interfaces.mcp_server import studio_parity
from eaos.interfaces.mcp_server.govern import every
from eaos.interfaces.mcp_server.server import build
from eaos.interfaces.studio_actions.runs import PLANNERS

ROOT = Path(__file__).resolve().parents[2]


def studio_endpoints():
    """Every endpoint of the Studio, from its code: the read server's routes and the action API's contract."""
    from eaos.interfaces.studio_server.server import create_app
    with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, {'EAOS_HOME': folder}):
        app = create_app(folder, project=folder, mounts=[], watch=False)     # a project: its sign-in routes too
    found = {f"{'POST' if 'POST' in (route.methods or ()) else 'GET'} {route.path}" for route in app.routes
             if route.path.startswith(('/api/', '/report/')) and route.path != '/api/{rest:path}'}
    return found | {f"{row['method']} {row['path']}" for row in contract()['endpoints']}


class StudioActionsHaveTools(unittest.TestCase):
    def test_every_studio_endpoint_and_action_maps_to_a_registered_tool(self):
        tools = {tool.name for tool in build(every)._tool_manager.list_tools()}
        endpoints = studio_endpoints()
        self.assertEqual(sorted(endpoints - set(studio_parity.PARITY) - set(studio_parity.NO_TOOL)), [], 'a Studio endpoint with no row')
        self.assertEqual(sorted((set(studio_parity.PARITY) | set(studio_parity.NO_TOOL)) - endpoints), [], 'a row of no endpoint')
        self.assertFalse(set(studio_parity.PARITY) & set(studio_parity.NO_TOOL))
        for endpoint, (named, _) in studio_parity.PARITY.items():
            self.assertTrue(named and set(named) <= tools, (endpoint, set(named) - tools))
        actions = {action['id'] for action in contract()['actions'] if action['tool'] or action['id'] in PLANNERS}
        self.assertEqual(sorted(actions - tools), [], 'an action the Studio runs that no tool runs')

    def test_what_only_the_person_decides_stays_theirs(self):
        tools = {tool.name: tool.fn for tool in build(every)._tool_manager.list_tools()}
        self.assertIn('needs_the_person', tools['sign_in_forget']())
        with mock.patch.dict(os.environ, {'EAOS_STUDIO_RUN': 'r1'}):
            self.assertIn("the person's decision", tools['sign_in_forget'](person_agreed=True))


class JourneyFromTheTerminal(unittest.TestCase):
    """check, the question it asks, what it found, status, a Fix queued for the person's assistant, stopped: the eaos
    command alone, no Studio, no AI."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = Path(tmp.name) / 'tiny'
        self.project.mkdir()
        (self.project / 'app.py').write_text('import store\n\n\ndef main():\n    return store.load()\n')
        (self.project / 'store.py').write_text('def load():\n    return 1\n\n\ndef unused():\n    return 2\n')
        for argv in (['init', '-q'], ['add', '-A'], ['-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'init']):
            subprocess.run(['git', *argv], cwd=self.project, check=True)
        self.env = {**os.environ, 'EAOS_DETECTOR_VERDICTS': '', 'EAOS_HOME': str(Path(tmp.name) / 'home'), 'EAOS_HOST_IDLE': '2', 'PYTHONPATH': str(ROOT)}
        self.env.pop('EAOS_STUDIO_RUN', None)

    def eaos(self, *argv, project=True):
        done = subprocess.run([sys.executable, '-m', 'eaos', *argv, *(['--project', str(self.project)] if project else []), '--lang', 'en'],
                              cwd=self.project, env=self.env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
        return done.returncode, done.stdout

    def until(self, *argv, wanted, seconds=120):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            printed = self.eaos(*argv)[1]
            if re.search(wanted, printed): return printed
            time.sleep(1)
        self.fail(f'eaos {" ".join(argv)} never said {wanted}: {printed}')

    def test_the_whole_journey_from_the_terminal_alone(self):
        code, printed = self.eaos('check', '--assistant', 'none', '--path', 'code')
        self.assertEqual(code, 0, printed)
        self.assertIn('Started in the background', printed)
        self.until('runs', '--all', wanted=r'Waiting for your answer|Done')
        asked = re.search(r'❓ (\S+-q\d+):', self.eaos('waiting')[1])
        if asked: self.assertEqual(self.eaos('answer', asked.group(1), 'no')[0], 0)
        self.assertIn('The run ended', self.eaos('watch')[1])
        self.assertIn('TASK-001', self.eaos('problems')[1])
        self.assertIn('store.unused', self.eaos('problem', 'TASK-001')[1])
        self.assertIn('✅ Check the project', self.eaos('status', str(self.project), project=False)[1])
        code, printed = self.eaos('fix', 'TASK-001', '--assistant', 'handoff', '--yes')
        self.assertEqual(code, 0, printed)
        self.assertIn('Queued: Fix: TASK-001', printed)
        self.assertIn('Fix: TASK-001', self.eaos('runs')[1])
        self.assertIn('Stopped', self.eaos('stop')[1])
        self.assertIn('1 check(s) on record', self.eaos('history')[1])
        self.assertIn('tiny', self.eaos('projects')[1])
        self.assertEqual(self.eaos('branches')[0], 0)


if __name__ == '__main__':
    unittest.main()
