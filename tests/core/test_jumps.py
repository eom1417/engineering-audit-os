"""A package moved several major versions to reach its fix is said at the hand-over (for example 3 -> 11)."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from eaos.core.project.jumps import big_jumps


def lock(versions):
    return json.dumps({'packages': {'': {'name': 'icons'}, **{f'node_modules/{n}': {'version': v} for n, v in versions.items()}}})


class JumpTests(unittest.TestCase):
    def test_only_a_move_of_two_majors_or_more_is_said(self):
        with tempfile.TemporaryDirectory() as tmp:
            git = lambda *a: subprocess.run(['git', '-C', tmp, '-c', 'user.name=t', '-c', 'user.email=t@t', *a], check=True, capture_output=True)
            git('init', '-q', '-b', 'main')
            (Path(tmp) / 'package-lock.json').write_text(lock({'minimatch': '3.1.2', 'glob': '10.3.3', 'ip': '2.0.0'}))
            git('add', '.'); git('commit', '-qm', 'base')
            git('switch', '-qc', 'fix')
            (Path(tmp) / 'package-lock.json').write_text(lock({'minimatch': '11.0.1', 'glob': '11.0.0', 'ip': '2.0.1'}))
            git('commit', '-qam', 'fix')
            self.assertEqual(big_jumps(tmp, 'main', 'fix'), ['minimatch 3.1.2 -> 11.0.1 (package-lock.json)'])


if __name__ == '__main__':
    unittest.main()
