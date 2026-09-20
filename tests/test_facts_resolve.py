"""Resolved dependency edges: concrete targets only, everything else stays declared."""
import json
from pathlib import Path
import tempfile
import unittest
from eaos.facts.run import collect

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'


def edges(out):
    data = json.loads((Path(out) / 'facts/resolve.json').read_text())
    return data, {(f['location']['path'], f['value']['module']): f for f in data['facts']}


class ResolveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        collect(FIXTURE, Path(cls.tmp.name) / 'out', ['syntax', 'resolve'])
        cls.data, cls.edges = edges(Path(cls.tmp.name) / 'out')

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def test_python_package_and_relative_imports_resolve_to_files(self):
        self.assertEqual(self.edges[('cli.py', 'core.pricing')]['value']['to_path'], 'core/pricing.py')
        self.assertEqual(self.edges[('core/audit.py', 'pricing')]['value']['to_path'], 'core/pricing.py')

    def test_typescript_relative_imports_resolve_across_extensions(self):
        self.assertEqual(self.edges[('api/server.ts', './handlers/orders')]['value']['to_path'], 'api/handlers/orders.ts')
        self.assertEqual(self.edges[('api/handlers/orders.ts', '../lib/pricing')]['value']['to_path'], 'api/lib/pricing.ts')

    def test_third_party_and_standard_library_are_external_not_invented(self):
        for key in [('api/server.ts', 'express'), ('core/pricing.py', 'os'), ('worker/tasks.py', 'celery')]:
            self.assertEqual(self.edges[key]['resolution'], 'EXTERNAL')
            self.assertIsNone(self.edges[key]['value']['to_path'])

    def test_every_internal_edge_in_the_fixture_resolves(self):
        self.assertEqual(self.data['summary']['internal_resolution_rate'], 1.0)
        self.assertEqual(self.data['summary']['by_resolution']['UNRESOLVED'], 0)

    def test_ambiguous_target_is_never_promoted_to_a_dependency(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; (repo / 'pkg').mkdir(parents=True)
            (repo / 'shared.java').write_text('package app;\n')
            (repo / 'pkg/app').mkdir(parents=True)
            for name in ['one', 'two']:
                folder = repo / name / 'com/example'; folder.mkdir(parents=True)
                (folder / 'Thing.java').write_text('package com.example;\npublic class Thing {}\n')
            (repo / 'Main.java').write_text('import com.example.Thing;\npublic class Main { void run() { new Thing(); } }\n')
            collect(repo, Path(tmp) / 'out', ['syntax', 'resolve'])
            _, found = edges(Path(tmp) / 'out')
            edge = found[('Main.java', 'com.example.Thing')]
            self.assertEqual(edge['resolution'], 'AMBIGUOUS')
            self.assertIsNone(edge['value']['to_path'])
            self.assertEqual(len(edge['value']['candidates']), 2)

    def test_go_module_paths_resolve_through_go_mod(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; (repo / 'internal/store').mkdir(parents=True)
            (repo / 'go.mod').write_text('module example.com/app\n\ngo 1.21\n')
            (repo / 'internal/store/store.go').write_text('package store\n\nfunc Load() string { return "x" }\n')
            (repo / 'main.go').write_text('package main\n\nimport (\n\t"example.com/app/internal/store"\n)\n\nfunc main() { store.Load() }\n')
            collect(repo, Path(tmp) / 'out', ['syntax', 'resolve'])
            data, found = edges(Path(tmp) / 'out')
            self.assertEqual(data['summary']['go_module'], 'example.com/app')
            self.assertEqual(found[('main.go', 'example.com/app/internal/store')]['value']['to_path'], 'internal/store/store.go')

    def test_resolution_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            collect(FIXTURE, Path(tmp) / 'a', ['syntax', 'resolve']); collect(FIXTURE, Path(tmp) / 'b', ['syntax', 'resolve'])
            self.assertEqual((Path(tmp) / 'a/facts/resolve.json').read_bytes(), (Path(tmp) / 'b/facts/resolve.json').read_bytes())
