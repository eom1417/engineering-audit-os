"""Packaging completeness: the distributed data set is derived from canonical sources, not observed."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
_spec=importlib.util.spec_from_file_location('eaos_validate_tool',ROOT/'tools/validate.py')
validate=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(validate)


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.data=Path(self.tmp.name)/'data';shutil.copytree(ROOT/'eaos/data',self.data)

    def test_complete_package_reports_no_errors(self):
        self.assertEqual(validate.packaged_errors(ROOT,self.data),[])

    def test_missing_required_schema_is_detected(self):
        (self.data/'schemas/finding.schema.json').unlink()
        self.assertIn('Missing packaged file schemas/finding.schema.json',validate.packaged_errors(ROOT,self.data))

    def test_missing_rendered_module_is_detected(self):
        (self.data/'modules/27.md').unlink()
        self.assertIn('Missing packaged file modules/27.md',validate.packaged_errors(ROOT,self.data))

    def test_stale_packaged_copy_is_detected(self):
        target=self.data/'controls.json';target.write_text(target.read_text()+' ')
        self.assertIn('Stale packaged copy controls.json',validate.packaged_errors(ROOT,self.data))

    def test_leftover_packaged_file_is_detected(self):
        (self.data/'schemas/leftover.schema.json').write_text('{}')
        self.assertIn('Unexpected packaged file schemas/leftover.schema.json',validate.packaged_errors(ROOT,self.data))

    def test_packaging_patterns_cover_every_required_file(self):
        if validate.package_data_patterns(ROOT) is None:self.skipTest('tomllib unavailable on this interpreter')
        self.assertEqual([e for e in validate.packaged_errors(ROOT,self.data) if e.startswith('Packaging pattern')],[])
