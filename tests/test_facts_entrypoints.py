"""Entry-point detection: matched surfaces only, and undetectable ones declared as gaps."""
import json
from pathlib import Path
import tempfile
import unittest
from eaos.facts.run import collect

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'


def load(root, repo, sets=('syntax', 'entrypoints')):
    collect(repo, Path(root) / 'out', list(sets))
    return json.loads((Path(root) / 'out/facts/entrypoints.json').read_text())


class EntryPointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data = load(cls.tmp.name, FIXTURE)
        cls.rows = [f['value'] | {'path': f['location']['path'], 'resolution': f['resolution']} for f in cls.data['facts']]

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def routes(self, surface): return {(r['http_method'], r['route']) for r in self.rows if r['surface'] == surface}

    def test_http_routes_are_found_across_languages(self):
        self.assertIn(('GET', '/orders'), self.routes('http'))
        self.assertIn(('POST', '/orders'), self.routes('http'))
        self.assertIn(('DELETE', '/orders/:id'), self.routes('http'))
        self.assertIn(('ANY', '/health'), self.routes('http'))

    def test_handlers_are_linked_to_real_symbols(self):
        handler = next(r for r in self.rows if r['route'] == '/orders' and r['http_method'] == 'POST')
        self.assertEqual(handler['handler'], 'createOrder')
        self.assertEqual(handler['resolution'], 'RESOLVED')

    def test_cli_jobs_and_manifest_surfaces_are_covered(self):
        self.assertIn(('polyglot', 'argparse'), {(r['route'], r['framework']) for r in self.rows})
        self.assertIn(('recalculate', 'celery'), {(r['route'], r['framework']) for r in self.rows})
        self.assertIn('npm run start', {r['route'] for r in self.rows})

    def test_nothing_is_invented_for_a_project_without_entry_points(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'lib.py').write_text('VALUE = 1\n\n\ndef helper():\n    return VALUE\n')
            data = load(tmp, repo)
            self.assertEqual(data['facts'], [])
            self.assertEqual(data['summary']['entry_points'], 0)

    def test_runtime_registered_commands_are_declared_as_gaps_not_hidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'tool.py').write_text(
                'import argparse\n\n\ndef main():\n    parser = argparse.ArgumentParser(prog="tool")\n'
                '    sub = parser.add_subparsers()\n    for command in ["a", "b"]:\n        sub.add_parser(command)\n')
            data = load(tmp, repo)
            dynamic = [f for f in data['facts'] if f['value']['framework'] == 'argparse_dynamic']
            self.assertEqual(len(dynamic), 1)
            self.assertIsNone(dynamic[0]['value']['route'])
            self.assertEqual(dynamic[0]['resolution'], 'UNRESOLVED')
            self.assertIn('built at runtime', dynamic[0]['value']['note'])

    def test_dockerfile_and_makefile_surfaces_are_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'Dockerfile').write_text('FROM python:3.12\nCMD ["python", "-m", "app"]\n')
            (repo / 'Makefile').write_text('.PHONY: test\ntest:\n\tpytest\n')
            rows = [f['value'] for f in load(tmp, repo)['facts']]
            self.assertIn('container', {r['surface'] for r in rows})
            self.assertIn('make test', {r['route'] for r in rows})

    def test_detection_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            collect(FIXTURE, Path(tmp) / 'a', ['syntax', 'entrypoints']); collect(FIXTURE, Path(tmp) / 'b', ['syntax', 'entrypoints'])
            self.assertEqual((Path(tmp) / 'a/facts/entrypoints.json').read_bytes(), (Path(tmp) / 'b/facts/entrypoints.json').read_bytes())
