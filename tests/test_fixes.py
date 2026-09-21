"""Tests for the bugs found in review: None handling, target semantics, direction."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from eaos.audit import run as run_audit
from eaos.sustainability import compute, DEFAULT_TARGETS
from eaos.progress import render as render_progress
from eaos.guarantee import compare as compare_guarantee
from eaos.executive import render as render_executive


class FixVerificationTests(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp()
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)

    def test_verifiable_paths_target_is_zero(self):
        self.assertEqual(DEFAULT_TARGETS['verifiable_paths'], 0.0)

    def test_executive_does_not_show_none_for_unmeasured(self):
        out = Path(self.tmp) / 'out'
        run_audit(Path('examples/benchmark/coupled-billing'), out, language='en')
        result = render_executive(out, language='en')
        content = Path(result['artifact']).read_text()
        self.assertNotIn('current None', content)
        self.assertIn('not measured', content.lower())

    def test_progress_does_not_crash_on_none_values(self):
        a = Path(self.tmp) / 'a'; b = Path(self.tmp) / 'b'
        run_audit(Path('examples/benchmark/coupled-billing'), a, language='en')
        run_audit(Path('examples/benchmark/coupled-billing'), b, language='en')
        result = render_progress(a, b, language='en')  # should not crash
        self.assertIsNotNone(result)
        # The verifiable_paths row should be reported as not measured.
        row = next(r for r in result['rows'] if r['indicator'] == 'verifiable_paths')
        self.assertEqual(row['direction'], 'not measured')
        self.assertFalse(row['measured'])

    def test_progress_reports_unchanged_for_zero_delta(self):
        a = Path(self.tmp) / 'a'; b = Path(self.tmp) / 'b'
        run_audit(Path('examples/benchmark/coupled-billing'), a, language='en')
        run_audit(Path('examples/benchmark/coupled-billing'), b, language='en')
        result = render_progress(a, b, language='en')
        for row in result['rows']:
            if row['measured'] and row['delta'] == 0:
                self.assertEqual(row['direction'], 'unchanged')

    def test_guarantee_returns_summary_with_valid_verdicts(self):
        a = Path(self.tmp) / 'a'; b = Path(self.tmp) / 'b'
        run_audit(Path('examples/benchmark/coupled-billing'), a, language='en')
        run_audit(Path('examples/benchmark/coupled-billing'), b, language='en')
        result = compare_guarantee(a, b, language='en')
        self.assertIn('summary', result)
        for verdict in result['summary']:
            self.assertIn(verdict, {'HONEST', 'OVERSTATED', 'UNDERSTATED'})

    def test_dashboard_render_handles_unmeasured_indicator(self):
        out = Path(self.tmp) / 'out'
        run_audit(Path('examples/benchmark/coupled-billing'), out, language='en')
        from eaos.sustainability import render as render_dashboard
        result = render_dashboard(out, language='en')
        content = Path(result['artifact']).read_text()
        self.assertNotIn('None', content)
