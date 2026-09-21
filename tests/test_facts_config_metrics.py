"""Configuration and size/duplication facts: names without values, signals without verdicts."""
import json
from pathlib import Path
import tempfile
import unittest
from shared_fixture import TemporaryWorkspace
from eaos.facts.run import collect

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'


def run_sets(repo, out, sets):
    collect(repo, out, list(sets))
    return {name: json.loads((Path(out) / f'facts/{name}.json').read_text()) for name in sets if name != 'syntax'}


class ConfigFactTests(TemporaryWorkspace):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data = run_sets(FIXTURE, Path(cls.tmp.name) / 'out', ['config'])['config']


    def test_environment_reads_are_found_across_languages(self):
        names = {(f['value']['name'], f['value']['language']) for f in self.data['facts'] if f['kind'] == 'env_read'}
        self.assertIn(('TAX_RATE', 'python'), names)
        self.assertIn(('PORT', 'typescript'), names)
        self.assertIn(('AUDIT_SINK', 'typescript'), names)

    def test_defaults_are_flagged_without_capturing_the_value(self):
        fact = next(f for f in self.data['facts'] if f['kind'] == 'env_read' and f['value']['name'] == 'TAX_RATE')
        self.assertTrue(fact['value']['has_default'])
        self.assertNotIn('0.15', json.dumps(fact))

    def test_sensitive_config_files_are_listed_but_never_opened(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / '.env').write_text('API_TOKEN=SECRET_SENTINEL_VALUE\nDB_HOST=localhost\n')
            (repo / 'app.py').write_text('import os\n\nTOKEN = os.environ["API_TOKEN"]\n')
            data = run_sets(repo, Path(tmp) / 'out', ['config'])['config']
            raw = json.dumps(data)
            self.assertNotIn('SECRET_SENTINEL_VALUE', raw)
            self.assertNotIn('localhost', raw)
            self.assertIn('API_TOKEN', {f['value']['name'] for f in data['facts'] if f['kind'] == 'env_read'})
            self.assertEqual(data['summary']['unread_sensitive_config_files'], ['.env'])
            self.assertEqual([f['value']['reason'] for f in data['facts'] if f['kind'] == 'config_file_unread'],
                             ['Path classified sensitive by the snapshot; contents are never read by any extractor.'])


class MetricFactTests(unittest.TestCase):
    def test_file_and_symbol_metrics_are_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = run_sets(FIXTURE, Path(tmp) / 'out', ['syntax', 'metrics'])['metrics']
            symbol = next(f for f in data['facts'] if f['kind'] == 'metric' and f['location'].get('symbol') == 'price_for')
            self.assertEqual(symbol['value']['scope'], 'function')
            self.assertGreaterEqual(symbol['value']['branches'], 1)
            self.assertTrue(any(f['value']['scope'] == 'file' for f in data['facts']))

    def test_duplicated_block_is_reported_as_a_cluster(self):
        block = ('def compute(order):\n'
                 '    subtotal = sum(line.price for line in order.lines)\n'
                 '    if order.tier == "premium":\n'
                 '        subtotal = subtotal * 0.9\n'
                 '    shipping = 5 if subtotal < 100 else 0\n'
                 '    return round(subtotal + shipping, 2)\n')
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'checkout.py').write_text(block)
            (repo / 'export.py').write_text('# separate module\n' + block)
            data = run_sets(repo, Path(tmp) / 'out', ['syntax', 'metrics'])['metrics']
            clusters = [f for f in data['facts'] if f['kind'] == 'clone_cluster']
            self.assertTrue(clusters)
            self.assertEqual(clusters[0]['value']['files'], ['checkout.py', 'export.py'])

    def test_metrics_never_assert_a_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = run_sets(FIXTURE, Path(tmp) / 'out', ['syntax', 'metrics'])['metrics']
            self.assertIn('never severity', data['summary']['interpretation'])

    def test_both_extractors_are_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_sets(FIXTURE, Path(tmp) / 'a', ['syntax', 'config', 'metrics'])
            run_sets(FIXTURE, Path(tmp) / 'b', ['syntax', 'config', 'metrics'])
            for name in ['config', 'metrics']:
                self.assertEqual((Path(tmp) / f'a/facts/{name}.json').read_bytes(), (Path(tmp) / f'b/facts/{name}.json').read_bytes())
