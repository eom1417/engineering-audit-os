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


def resolve_files(files):
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / 'repo'
        for name, text in files.items():
            (repo / name).parent.mkdir(parents=True, exist_ok=True)
            (repo / name).write_text(text)
        collect(repo, Path(tmp) / 'out', ['syntax', 'resolve'])
        return edges(Path(tmp) / 'out')


class ResolveTests(unittest.TestCase):
    def test_python_and_typescript_imports_resolve_and_third_party_stays_external(self):
        with tempfile.TemporaryDirectory() as tmp:
            collect(FIXTURE, Path(tmp) / 'out', ['syntax', 'resolve'])
            data, found = edges(Path(tmp) / 'out')
        for key, target in [(('cli.py', 'core.pricing'), 'core/pricing.py'),
                            (('core/audit.py', 'pricing'), 'core/pricing.py'),
                            (('api/server.ts', './handlers/orders'), 'api/handlers/orders.ts'),
                            (('api/handlers/orders.ts', '../lib/pricing'), 'api/lib/pricing.ts')]:
            self.assertEqual(found[key]['value']['to_path'], target)
        for key in [('api/server.ts', 'express'), ('core/pricing.py', 'os'), ('worker/tasks.py', 'celery')]:
            self.assertEqual(found[key]['resolution'], 'EXTERNAL')
            self.assertIsNone(found[key]['value']['to_path'])
        self.assertEqual(data['summary']['internal_resolution_rate'], 1.0)
        self.assertEqual(data['summary']['by_resolution']['UNRESOLVED'], 0)

    def test_ambiguous_target_is_never_promoted_to_a_dependency(self):
        files = {'Main.java': 'import com.example.Thing;\npublic class Main { void run() { new Thing(); } }\n'}
        for name in ['one', 'two']:
            files[f'{name}/com/example/Thing.java'] = 'package com.example;\npublic class Thing {}\n'
        _, found = resolve_files(files)
        edge = found[('Main.java', 'com.example.Thing')]
        self.assertEqual(edge['resolution'], 'AMBIGUOUS')
        self.assertIsNone(edge['value']['to_path'])
        self.assertEqual(len(edge['value']['candidates']), 2)

    def test_an_engine_resolved_edge_keeps_its_engine_name_and_is_counted_apart(self):
        from eaos.facts.resolve import run as resolve_run, make, digest
        from eaos.facts.source import Source
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'a.go').write_text('package a\n')
            edge = make('call_edge', 'external', '1', digest(b''), {'path': 'a.go'},
                        {'caller': 'A', 'callee': 'B', 'caller_path': 'a.go', 'callee_path': 'b.go',
                         'line': 1, 'source': 'codegraph', 'engine': 'codegraph'},
                        resolution='RESOLVED_BY_ENGINE', limitations=[])
            result = resolve_run(repo, Source(repo), imports=None, external_edges=[edge])
        engine_edges = [f for f in result['facts'] if f.get('resolution') == 'RESOLVED_BY_ENGINE']
        self.assertEqual([f['value']['engine'] for f in engine_edges], ['codegraph'])
        self.assertIn('resolved_by_us', result['summary'])
        self.assertEqual(result['summary']['resolved_by_engine'], 1)


class GoResolutionTests(unittest.TestCase):
    """A Go import points at a package (a directory) resolved through go.mod, not at a single file."""

    def test_go_imports_resolve_to_their_package_folder_with_a_non_test_stand_in(self):
        main = ('package main\n\nimport (\n\t"example.com/app/internal/store"\n\t"example.com/app/internal/config"\n'
                '\t"example.com/app/internal/engine"\n\t"example.com/app/internal/only"\n)\n\n'
                'func main() { store.Load(); _ = config.A; _ = engine.E; _ = only.A }\n')
        data, found = resolve_files({
            'go.mod': 'module example.com/app\n\ngo 1.21\n', 'main.go': main,
            'internal/store/store.go': 'package store\n\nfunc Load() string { return "x" }\n',
            'internal/config/config.go': 'package config\n\nvar A = 1\n',
            'internal/config/loader.go': 'package config\n\nvar B = 2\n',
            'internal/engine/append_replace_test.go': 'package engine\n\nvar T = 1\n',
            'internal/engine/engine.go': 'package engine\n\nvar E = 2\n',
            'internal/only/a_test.go': 'package only\n\nvar A = 1\n',
            'internal/only/b_test.go': 'package only\n\nvar B = 2\n'})
        self.assertEqual(data['summary']['go_module'], 'example.com/app')
        edge = lambda name: found[('main.go', f'example.com/app/internal/{name}')]
        self.assertEqual(edge('store')['value']['to_path'], 'internal/store/store.go')
        config = edge('config')
        self.assertEqual((config['resolution'], config['value']['target_kind'], config['value']['package_path']),
                         ('RESOLVED', 'package', 'internal/config'))
        self.assertEqual(set(config['value']['candidates']), {'internal/config/config.go', 'internal/config/loader.go'})
        # A fixture never stands in for a package; an all-test package still resolves rather than losing the edge.
        self.assertEqual(edge('engine')['value']['to_path'], 'internal/engine/engine.go')
        self.assertEqual(edge('only')['resolution'], 'RESOLVED')
        self.assertTrue(edge('only')['value']['to_path'].endswith('_test.go'))

    def test_real_ambiguity_across_folders_stays_ambiguous(self):
        from eaos.facts import resolve as resolve_mod
        from eaos.facts.source import Source
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            for folder in ('one', 'two', 'three'):
                (repo / 'pkg' / folder).mkdir(parents=True)
                (repo / 'pkg' / folder / 'util.go').write_text('package util\n')
            (repo / 'go.mod').write_text('module example.com/app\n\ngo 1.21\n')
            (repo / 'main.go').write_text('package main\n')
            import_edge = resolve_mod.make('import_edge', 'syntax', '1', 'sha', {'path': 'main.go', 'start_line': 1},
                                           {'module': 'example.com/app/pkg', 'language': 'go',
                                            'names': [], 'level': 0, 'style': 'import'}, limitations=[])
            result = resolve_mod.run(repo, Source(repo), imports=[import_edge])
        matching = [e for e in result['facts'] if e['value'].get('module') == 'example.com/app/pkg']
        self.assertTrue(any(e['resolution'] == 'AMBIGUOUS' for e in matching), matching)


class PathAliasTests(unittest.TestCase):
    """`@/x` in a Vite or Next project is the project's own src/x, never an npm package."""

    def resolve(self, files):
        _, found = resolve_files(files)
        return {key: (f['resolution'], f['value']['to_path'], f['value'].get('target_kind'))
                for key, f in found.items() if f['kind'] == 'module_edge'}

    def test_a_tsconfig_path_alias_resolves_to_the_file(self):
        found = self.resolve({'tsconfig.json': '{\n  // comments are allowed here\n  "compilerOptions": {"baseUrl": ".", '
                                               '"paths": {"@app/*": ["./src/app/*"],},},\n}\n',
                              'src/app/orders.ts': 'export const x = 1;\n',
                              'src/main.ts': 'import { x } from "@app/orders";\nimport React from "react";\n'})
        self.assertEqual(found[('src/main.ts', '@app/orders')][:2], ('RESOLVED', 'src/app/orders.ts'))
        self.assertEqual(found[('src/main.ts', 'react')][0], 'EXTERNAL')

    def test_at_slash_and_js_specifiers_resolve_without_any_config(self):
        found = self.resolve({
            'src/services/Orders.ts': 'export class Orders {}\n', 'src/hooks/index.ts': 'export const h = 1;\n',
            'src/components/ui/button.tsx': 'export const Button = 1;\n',
            'src/pages/Home.tsx': 'import { Orders } from "@/services/Orders";\nimport { h } from "@/hooks";\n'
                                  'import raw from "@/services/Orders?raw";\nimport { api } from "@/lib/serviceHistoryApi";\n'
                                  'import { Button } from "@/components/ui/button";\n',
            'server/src/env.ts': 'export const env = {};\n', 'server/src/view.tsx': 'export const v = 1;\n',
            'server/src/index.ts': 'import { env } from "./env.js";\nimport { v } from "./view.jsx";\n'
                                   'import { gone } from "./gone.js";\n'})
        home = lambda module: found[('src/pages/Home.tsx', module)]
        self.assertEqual(home('@/services/Orders')[:2], ('RESOLVED', 'src/services/Orders.ts'))
        self.assertEqual(home('@/hooks')[:2], ('RESOLVED', 'src/hooks/index.ts'))
        self.assertEqual(home('@/services/Orders?raw')[:2], ('RESOLVED', 'src/services/Orders.ts'))
        self.assertEqual(home('@/lib/serviceHistoryApi')[0], 'UNRESOLVED', 'a missing aliased file is not external')
        self.assertEqual(home('@/components/ui/button'), ('EXTERNAL', None, 'excluded'))
        self.assertEqual(found[('server/src/index.ts', './env.js')][:2], ('RESOLVED', 'server/src/env.ts'))
        self.assertEqual(found[('server/src/index.ts', './view.jsx')][:2], ('RESOLVED', 'server/src/view.tsx'))
        self.assertNotEqual(found[('server/src/index.ts', './gone.js')][0], 'RESOLVED')
