"""Configuration and size/duplication facts: names without values, signals without verdicts."""
import json
from pathlib import Path
import tempfile
import unittest
from shared_fixture import TemporaryWorkspace
from eaos.facts.run import collect

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/polyglot'


def run_sets(repo, out, sets):
    collect(repo, out, list(sets))
    return {name: json.loads((Path(out) / f'facts/{name}.json').read_text()) for name in sets if name != 'syntax'}


class ConfigFactTests(TemporaryWorkspace):
    def test_environment_reads_are_found_across_languages_without_their_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = run_sets(FIXTURE, Path(tmp) / 'out', ['config'])['config']
        names = {(f['value']['name'], f['value']['language']) for f in data['facts'] if f['kind'] == 'env_read'}
        self.assertTrue({('TAX_RATE', 'python'), ('PORT', 'typescript'), ('AUDIT_SINK', 'typescript')} <= names)
        fact = next(f for f in data['facts'] if f['kind'] == 'env_read' and f['value']['name'] == 'TAX_RATE')
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


class MetricFactTests(unittest.TestCase):
    def test_file_and_symbol_metrics_are_recorded_as_signals_not_verdicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = run_sets(FIXTURE, Path(tmp) / 'out', ['syntax', 'metrics'])['metrics']
        symbol = next(f for f in data['facts'] if f['kind'] == 'metric' and f['location'].get('symbol') == 'price_for')
        self.assertEqual(symbol['value']['scope'], 'function')
        self.assertGreaterEqual(symbol['value']['branches'], 1)
        self.assertTrue(any(f['value']['scope'] == 'file' for f in data['facts']))
        self.assertIn('never severity', data['summary']['interpretation'])

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
