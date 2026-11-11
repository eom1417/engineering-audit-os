"""The guard kit (eaos/templates/guards/check.py): each rule fails on a planted violation, ceilings only fall, and
EAOS's own repository holds its ledger."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / 'eaos' / 'templates' / 'guards' / 'check.py'
CONFIG = {'root': '.', 'ledger': 'ledger.json', 'folders': ['src'], 'exclude': [], 'max_line': 120,
          'history_patterns': ['\\bM-?\\d{1,2}(\\.\\d+)?\\b'], 'env_allowed': ['src/settings.py']}
PLANTED = {
    'long_lines': 'value = 1  # ' + 'x' * 120 + '\n',
    'swallowed_errors': 'try:\n    pass\nexcept Exception:\n    pass\n',
    'commented_code': '# result = compute(value)\nvalue = 1\n',
    'history_comments': '# Added in M12 for the report.\nvalue = 1\n',
    'skipped_tests': 'import unittest\n\n\nclass T(unittest.TestCase):\n    @unittest.skip("later")\n    def test_a(self):\n        pass\n',
    'env_readers': 'import os\n\nHOME = os.environ.get("HOME")\n',
    'suppressions': 'import os  # noqa: F401\n',
}


def run(folder, *flags):
    return subprocess.run([sys.executable, str(KIT), '--config', str(folder / 'config.json'), *flags],
                          capture_output=True, text=True)


class GuardKit(unittest.TestCase):
    def repository(self, files):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        folder = Path(scratch.name)
        (folder / 'config.json').write_text(json.dumps(CONFIG), encoding='utf-8')
        for rel, text in files.items():
            (folder / rel).parent.mkdir(parents=True, exist_ok=True)
            (folder / rel).write_text(text, encoding='utf-8')
        return folder

    def test_each_rule_fails_on_its_planted_violation(self):
        for rule, text in PLANTED.items():
            with self.subTest(rule=rule):
                folder = self.repository({'src/clean.py': 'value = 1\n'})
                self.assertEqual(run(folder, '--record').returncode, 0)
                (folder / 'src' / 'planted.py').write_text(text, encoding='utf-8')
                found = run(folder)
                self.assertEqual(found.returncode, 1, found.stdout)
                self.assertIn(f'{rule} rose in src/planted.py', found.stdout)

    def test_a_junk_file_fails(self):
        folder = self.repository({'src/clean.py': 'value = 1\n'})
        run(folder, '--record')
        (folder / 'src' / 'clean.py.bak').write_text('', encoding='utf-8')
        self.assertIn('junk_files rose', run(folder).stdout)

    def test_the_allowed_file_reads_the_environment(self):
        folder = self.repository({'src/settings.py': PLANTED['env_readers']})
        run(folder, '--record')
        self.assertEqual(json.loads((folder / 'ledger.json').read_text())['env_readers'], {})

    def test_ceilings_only_fall(self):
        folder = self.repository({'src/a.py': PLANTED['suppressions'] * 2})
        self.assertEqual(run(folder, '--record').returncode, 0)
        self.assertNotEqual(run(folder, '--record').returncode, 0)
        (folder / 'src' / 'a.py').write_text(PLANTED['suppressions'], encoding='utf-8')
        self.assertIn('can fall', run(folder).stdout)
        run(folder, '--tighten')
        self.assertEqual(json.loads((folder / 'ledger.json').read_text())['suppressions'], {'src/a.py': 1})
        (folder / 'src' / 'a.py').write_text(PLANTED['suppressions'] * 2, encoding='utf-8')
        self.assertEqual(run(folder).returncode, 1)

    def test_eaos_holds_its_own_ledger(self):
        found = subprocess.run([sys.executable, str(KIT), '--config', str(ROOT / 'tools' / 'guards' / 'config.json')],
                               capture_output=True, text=True)
        self.assertEqual(found.returncode, 0, found.stdout + found.stderr)


if __name__ == '__main__':
    unittest.main()
