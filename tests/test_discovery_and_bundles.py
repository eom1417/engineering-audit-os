"""Discovery documents and bundle generation: every artifact the engine can write."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from eaos import discover, bundles
from eaos.audit import run as run_audit


SETS = ['syntax', 'structure', 'fingerprint', 'sequences', 'redundancy', 'runtime',
        'resolve', 'entrypoints', 'config', 'metrics', 'domain', 'graph', 'flows']


def _setup(tmp, source='examples/benchmark/coupled-billing'):
    out = Path(tmp) / 'out'
    run_audit(Path(source), out, language='en')
    return out


class DiscoveryTests(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp()
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)

    def test_write_all_returns_eight_files(self):
        out = _setup(self.tmp)
        # write_all was called by audit; the files should exist.
        for name in ['SYSTEM-MAP.md', 'FLOWS.md', 'DATA-MODEL.md', 'CONTRACTS.md',
                      'DEPLOYMENT.md', 'OBSERVABILITY.md', 'SECURITY-SURFACE.md', 'EVOLUTION.md']:
            self.assertTrue((out / name).exists(), name)

    def test_system_map_has_nodes(self):
        out = _setup(self.tmp)
        content = (out / 'SYSTEM-MAP.md').read_text()
        self.assertTrue('System map' in content or 'خريطة النظام' in content)

    def test_arabic_discovery_has_arabic_header(self):
        out = _setup(self.tmp)
        # Re-run with Arabic
        run_audit(Path('examples/benchmark/coupled-billing'), out, language='ar')
        content = (out / 'SYSTEM-MAP.md').read_text()
        self.assertIn('خريطة النظام', content)


class BundlesGenerationTests(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp()
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)

    def test_every_bundle_has_at_least_one_file(self):
        out = _setup(self.tmp)
        result = bundles.build(out)
        bundles_dir = Path(result['bundles_dir'])
        for bundle in result['bundles']:
            bundle_dir = bundles_dir / bundle
            files = list(bundle_dir.rglob('*'))
            # We allow empty bundles only if there are no underlying facts.
            self.assertGreater(len(files), 0, f'{bundle} is empty')

    def test_canonical_homes_md_is_generated(self):
        out = _setup(self.tmp)
        result = bundles.build(out)
        bundles_dir = Path(result['bundles_dir'])
        self.assertTrue((bundles_dir / '03-TARGET' / 'CANONICAL-HOMES.md').is_file())

    def test_kpi_md_is_generated(self):
        out = _setup(self.tmp)
        result = bundles.build(out)
        bundles_dir = Path(result['bundles_dir'])
        self.assertTrue((bundles_dir / '04-TRANSFORM' / 'KPI.md').is_file())

    def test_gap_matrix_json_is_valid_json(self):
        out = _setup(self.tmp)
        result = bundles.build(out)
        bundles_dir = Path(result['bundles_dir'])
        path = bundles_dir / '03-TARGET' / 'gap-matrix.json'
        data = json.loads(path.read_text())
        self.assertIn('covered', data); self.assertIn('total', data)

    def test_stages_md_lists_each_stage(self):
        out = _setup(self.tmp)
        result = bundles.build(out)
        bundles_dir = Path(result['bundles_dir'])
        content = (bundles_dir / '04-TRANSFORM' / 'STAGES.md').read_text()
        self.assertIn('## Stage 1', content)
