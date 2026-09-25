"""Confirmed dead code, under the engagement rule, becomes a ready removal card whose check really decides."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from shared_fixture import Workspace

ROOT = Path(__file__).resolve().parents[1]
APP = {'app/__main__.py': 'from app import core\ncore.run()\n',
       'app/core.py': 'def run():\n    return 1\n\n\ndef forgotten():\n    return 2\n'}


def audit(repo, out):
    done = subprocess.run([sys.executable, '-m', 'eaos', 'audit', str(repo), '--out', str(out), '--skip', 'site'],
                          cwd=ROOT, capture_output=True, text=True)
    return json.loads((out / 'plan.json').read_text()) if (out / 'plan.json').is_file() else {'tasks': [], 'error': done.stderr}


class RemoveDeadTests(Workspace):
    def setUp(self):
        super().setUp()
        self.repo = Path(self.tmp) / 'repo'
        for name, text in APP.items():
            (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / name).write_text(text)

    def card(self):
        plan = audit(self.repo, Path(self.tmp) / 'out')
        cards = [t for t in plan['tasks'] if t['pattern'] == 'remove_dead']
        self.assertEqual(len(cards), 1, plan.get('error') or [t['title'] for t in plan['tasks']])
        return cards[0]

    def test_a_confirmed_dead_function_gets_a_ready_card_whose_check_decides(self):
        card = self.card()
        self.assertEqual((card['kind'], card['decision']['readiness']), ('remediate', 'ready'))
        self.assertNotIn('human review', json.dumps(card['acceptance']))
        argv = card['decision']['checks'][0]['argv']
        run = lambda: subprocess.run(argv, cwd=self.repo, capture_output=True, text=True, env={'PYTHONPATH': str(ROOT), 'PATH': '/usr/bin:/bin'}).returncode
        self.assertEqual(run(), 1, 'the check must fail while the dead function is still there')
        (self.repo / 'app/core.py').write_text('def run():\n    return 1\n')
        self.assertEqual(run(), 0, 'the check must pass once it is removed')

    def test_the_project_can_turn_the_rule_off(self):
        (self.repo / 'eaos.engagement.json').write_text(json.dumps({'rules': {'remove_dead_code': False}}))
        plan = audit(self.repo, Path(self.tmp) / 'out2')
        self.assertFalse([t for t in plan['tasks'] if t['decision']['readiness'] == 'ready'])


if __name__ == '__main__':
    unittest.main()
