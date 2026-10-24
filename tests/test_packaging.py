"""Packaging completeness: the distributed data set is derived from canonical sources, not observed."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('eaos_validate_tool', ROOT / 'tools/validate.py')
validate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate)


class PackagingTests(unittest.TestCase):
    def copy(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        data = Path(tmp.name) / 'data'
        shutil.copytree(ROOT / 'eaos/data', data)
        return data

    def test_the_shipped_package_is_complete_and_every_file_is_packaged(self):
        self.assertEqual(validate.packaged_errors(ROOT, self.copy()), [])

    def test_a_missing_stale_or_unexpected_file_is_detected(self):
        cases = [(lambda data: (data / 'errors.json').unlink(), 'Missing packaged file errors.json'),
                 (lambda data: (data / 'studio-actions.json').write_text((data / 'studio-actions.json').read_text() + ' '),
                  'Stale packaged copy studio-actions.json'),
                 (lambda data: (data / 'leftover.json').write_text('{}'), 'Unexpected packaged file leftover.json')]
        for change, expected in cases:
            with self.subTest(expected):
                data = self.copy()
                change(data)
                self.assertTrue(any(error.startswith(expected) for error in validate.packaged_errors(ROOT, data)))
