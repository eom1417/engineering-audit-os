"""End-to-end: collect → dashboard → transform plan on the eaos codebase itself."""
from pathlib import Path
import shutil
import tempfile
import unittest
from eaos.facts.run import collect
from eaos.sustainability import render
from eaos.transform_plan import build, render as render_plan


class SelfSustainabilityTests(unittest.TestCase):
    def test_engine_analyzes_itself(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            collect(Path('eaos'), out,
                     ['syntax', 'structure', 'fingerprint', 'sequences', 'redundancy',
                      'domain', 'graph', 'metrics', 'flows', 'resolve'])
            self.assertTrue((out / 'facts/structure.json').is_file())
            self.assertTrue((out / 'facts/fingerprint.json').is_file())
            self.assertTrue((out / 'facts/redundancy.json').is_file())
            dashboard = render(out, language='en')
            self.assertEqual(len(dashboard['rows']), 6)
            # The engine must always produce the artifacts the contract promises.
            self.assertTrue(Path(dashboard['artifact']).is_file())

    def test_engine_transforms_itself(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            collect(Path('eaos'), out,
                     ['syntax', 'structure', 'fingerprint', 'sequences', 'redundancy',
                      'domain', 'graph', 'metrics', 'flows', 'resolve'])
            plan = build(out)
            self.assertIn('stages', plan); self.assertIn('summary', plan)
            files = render_plan(out, plan, language='en')
            self.assertTrue(Path(files['json']).is_file())
            self.assertTrue(Path(files['markdown']).is_file())
            self.assertGreater(len(plan['stages']), 0)
            # Every stage has a falsifier, an acceptance criterion, and a rollback.
            for stage in plan['stages']:
                self.assertTrue(stage['falsifier'])
                self.assertIsNotNone(stage['acceptance'])
                self.assertTrue(stage['rollback'])


class ExternalProjectTests(unittest.TestCase):
    def test_coupled_billing_fixture(self):
        """The doctrine's reference example (duplicated-rule benchmark)."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            target = Path('examples/benchmark/coupled-billing')
            collect(target, out,
                     ['syntax', 'structure', 'fingerprint', 'sequences', 'redundancy',
                      'domain', 'graph', 'metrics', 'flows', 'resolve'])
            dashboard = render(out, language='en')
            single_source = next(row for row in dashboard['rows'] if row['indicator'] == 'single_source')
            self.assertGreater(single_source['value'], 0)
            plan = build(out)
            self.assertGreater(len(plan['stages']), 0)
            # At least one stage is a canonicalize move on the duplicated rule.
            canonical = [s for s in plan['stages'] if s['move'] == 'canonicalize']
            self.assertGreater(len(canonical), 0)


class LayoutTests(unittest.TestCase):
    def test_sustainability_md_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            collect(Path('examples/benchmark/coupled-billing'), out,
                     ['syntax', 'structure', 'fingerprint', 'sequences', 'redundancy',
                      'domain', 'graph', 'metrics', 'flows'])
            result = render(out, language='en')
            content = Path(result['artifact']).read_text()
            self.assertIn('## Indicators', content)
            self.assertIn('## Proposed moves', content)
            self.assertIn('## Details', content)
            self.assertIn('## Limits', content)

    def test_transform_plan_md_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            collect(Path('examples/benchmark/coupled-billing'), out,
                     ['syntax', 'structure', 'fingerprint', 'sequences', 'redundancy',
                      'domain', 'graph', 'metrics', 'flows', 'resolve'])
            plan = build(out)
            files = render_plan(out, plan, language='en')
            content = Path(files['markdown']).read_text()
            self.assertIn('## Summary', content)
            self.assertIn('## Stage 1', content)
