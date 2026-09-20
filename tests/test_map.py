"""`eaos map`: a usable structural picture with no model call and a bounded size."""
import contextlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from eaos import cli
from eaos.map import build

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'
STAMP = re.compile(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC')


class MapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / 'map'
        cls.result = build(FIXTURE, cls.out)
        cls.system = (cls.out / 'SYSTEM-MAP.md').read_text()

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def test_three_artifacts_are_produced_without_any_model_call(self):
        self.assertEqual(self.result['model_calls'], 0)
        for name in ['SYSTEM-MAP.md', 'COUPLING-ATLAS.md', 'EVOLUTION.md']:
            self.assertTrue((self.out / name).is_file(), name)

    def test_entry_points_and_dependencies_reach_the_reader(self):
        self.assertIn('/orders', self.system)
        self.assertIn('createOrder', self.system)
        self.assertIn('core/pricing.py', (self.out / 'COUPLING-ATLAS.md').read_text())

    def test_coverage_and_unexamined_scope_are_stated_up_front(self):
        self.assertIn('التغطية', self.system)
        self.assertIn('ما لم يُفحص', self.system)

    def test_output_stays_small_enough_to_read(self):
        total = sum((self.out / name).read_text().count('\n') for name in ['SYSTEM-MAP.md', 'COUPLING-ATLAS.md', 'EVOLUTION.md'])
        self.assertLess(total, 900)

    def test_english_rendering_uses_english_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(FIXTURE, Path(tmp) / 'en', language='en')
            text = (Path(tmp) / 'en/SYSTEM-MAP.md').read_text()
            self.assertIn('Entry points', text)
            self.assertNotIn('نقاط الدخول', text)

    def test_rendering_is_deterministic_apart_from_the_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(FIXTURE, Path(tmp) / 'again')
            for name in ['SYSTEM-MAP.md', 'COUPLING-ATLAS.md']:
                first = STAMP.sub('T', (self.out / name).read_text())
                second = STAMP.sub('T', (Path(tmp) / 'again' / name).read_text())
                self.assertEqual(first, second, name)

    def test_project_without_history_still_maps(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'app.py').write_text('def main():\n    return 1\n')
            build(repo, Path(tmp) / 'out')
            self.assertIn('unavailable', (Path(tmp) / 'out/EVOLUTION.md').read_text())

    def test_cli_exposes_the_command(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as printed:
            self.assertEqual(cli.main(['map', str(FIXTURE), '--out', str(Path(tmp) / 'cli-out')]), 0)
        self.assertEqual(json.loads(printed.getvalue())['model_calls'], 0)

    def test_budget_violation_fails_loudly_instead_of_overflowing(self):
        from eaos.compose import Document
        document = Document('budget probe', 'en', budget_lines=3)
        document.section('one'); document.text('x' * 10); document.section('two'); document.text('y')
        with self.assertRaisesRegex(ValueError, 'over a budget'):
            document.render()


class ExclusionTests(unittest.TestCase):
    """Excluding a path must remove it from analysis and say so in the output."""

    def test_excluded_paths_are_left_out_and_reported(self):
        from eaos.dossier import assemble
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; (repo / 'thirdparty').mkdir(parents=True)
            (repo / 'app.py').write_text('RATE = 0.1\n\n\ndef total(x):\n    return x * RATE\n')
            (repo / 'thirdparty/copy.py').write_text('RATE = 0.1\n\n\ndef total(x):\n    return x * RATE\n')
            with_all = assemble(repo, Path(tmp) / 'all')
            without = assemble(repo, Path(tmp) / 'filtered', exclude=['thirdparty'])
            self.assertGreater(json.loads((Path(tmp) / 'all/dossier.json').read_text())['claims'].__len__(), 0)
            filtered = json.loads((Path(tmp) / 'filtered/dossier.json').read_text())
            self.assertEqual(filtered['claims'], [])
            self.assertEqual(filtered['provenance']['excluded_patterns'], ['thirdparty'])
            self.assertEqual(with_all['status'], 'READY')
            self.assertEqual(without['status'], 'READY')
