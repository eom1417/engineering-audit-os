"""reachability.py: dead code via static import-edge reachability.

Every test runs against an in-memory fact set, so the reachability walk is fully
reproducible without touching the disk. The pipeline integration (the audit
writing these facts through the engine-finding path) is exercised by
tests/test_audit_pipeline.py.
"""
import unittest

from eaos.reachability import (
    build, _entry_seeds, _module_edges, _reachable_from, _is_excluded,
    _declared_symbols, _entry_symbol_seeds,
)


def entry_point(path, surface='page', framework='tanstack_router', category='source',
                handler='handle', fact_id=None):
    return {'id': fact_id or f'FACT-EP-{path}', 'kind': 'entry_point',
            'location': {'path': path, 'line': 1, 'symbol': handler},
            'value': {'surface': surface, 'route': '/' + path, 'http_method': None,
                      'handler': handler, 'framework': framework,
                      'language': 'typescript', 'category': category, 'note': None}}


def module_edge(importer, to_path, resolution='RESOLVED', target_kind='module'):
    return {'id': f'FACT-ME-{importer}->{to_path}', 'kind': 'module_edge',
            'location': {'path': importer, 'line': 1},
            'value': {'module': './'+to_path, 'to_path': to_path,
                      'target_kind': target_kind, 'language': 'typescript'},
            'resolution': resolution}


def source_file(path, language='typescript'):
    return {'id': f'FACT-SF-{path}', 'kind': 'source_file',
            'location': {'path': path, 'line': 1},
            'value': {'language': language, 'parse_status': 'PARSED'}}


def symbol(path, name, line=1):
    return {'id': f'FACT-S-{path}-{name}', 'kind': 'symbol',
            'location': {'path': path, 'line': line, 'symbol': name},
            'value': {'name': name, 'kind': 'function'}}


class ReachabilityTheoryTests(unittest.TestCase):
    """The pure-graph parts of reachability: seed selection, edge reading, BFS."""

    def test_an_entry_point_with_surface_page_is_a_seed(self):
        facts = [entry_point('a.tsx')]
        self.assertEqual(list(_entry_seeds(facts)), ['a.tsx'])

    def test_npm_script_is_not_a_seed(self):
        facts = [entry_point('a.tsx', framework='npm_script')]
        self.assertEqual(list(_entry_seeds(facts)), [])

    def test_test_only_entries_are_not_seeds(self):
        facts = [entry_point('test_x.py', category='test')]
        self.assertEqual(list(_entry_seeds(facts)), [])

    def test_bfs_reaches_only_what_edges_connect(self):
        edges = _module_edges([module_edge('a.tsx', 'b.ts'),
                               module_edge('b.ts', 'c.ts')], [])
        reached = _reachable_from(['a.tsx'], edges)
        self.assertEqual(reached, {'a.tsx', 'b.ts', 'c.ts'})

    def test_bfs_does_not_loop(self):
        edges = _module_edges([module_edge('a.tsx', 'b.ts'),
                               module_edge('b.ts', 'a.tsx')], [])
        self.assertEqual(_reachable_from(['a.tsx'], edges), {'a.tsx', 'b.ts'})

    def test_excluded_paths_are_listed_but_skipped(self):
        self.assertTrue(_is_excluded('tests/test_x.py'))
        self.assertTrue(_is_excluded('webpack.config.js'))
        self.assertTrue(_is_excluded('conftest.py'))
        self.assertFalse(_is_excluded('src/services/orders.ts'))


class BuildTests(unittest.TestCase):
    """build() over a constructed fact set."""

    def test_an_unreachable_module_is_emitted_as_a_finding(self):
        facts = [
            entry_point('main.tsx'),
            module_edge('main.tsx', 'used.ts'),
            source_file('main.tsx'), source_file('used.ts'), source_file('orphan.ts'),
        ]
        results = [r for r in build(facts) if r]
        # The unreachable module must be in the engine_finding output
        all_text = ' '.join(r['message'] for r in results if r)
        self.assertIn('orphan', all_text)
        # The reachable module must not appear as dead
        self.assertNotIn('used.ts', all_text)

    def test_a_reachable_module_is_not_emitted(self):
        facts = [entry_point('main.tsx'),
                 module_edge('main.tsx', 'used.ts'),
                 source_file('main.tsx'), source_file('used.ts')]
        results = [r for r in build(facts) if r]
        all_text = ' '.join(r['message'] for r in results)
        self.assertNotIn('used.ts', all_text)

    def test_an_entry_point_handler_is_not_a_dead_symbol(self):
        facts = [entry_point('app.tsx', handler='handle'),
                 source_file('app.tsx'),
                 symbol('app.tsx', 'handle')]
        results = [r for r in build(facts) if r]
        all_text = ' '.join(r['message'] for r in results)
        self.assertNotIn('handle', all_text)

    def test_output_is_engine_finding_shape_for_pipeline_integration(self):
        facts = [entry_point('main.tsx'),
                 module_edge('main.tsx', 'used.ts'),
                 source_file('main.tsx'), source_file('used.ts'),
                 source_file('orphan.ts'),
                 symbol('orphan.ts', 'never_called')]
        results = [r for r in build(facts) if r]
        self.assertTrue(all(r['kind'] == 'engine_finding' for r in results))
        self.assertTrue(all(r['value']['engine'] == 'reachability' for r in results))
        self.assertTrue(all('unreachable' in r['message'].lower() for r in results))

    def test_test_fixtures_and_configs_are_excluded(self):
        facts = [
            entry_point('src/app.tsx'),
            module_edge('src/app.tsx', 'src/utils.ts'),
            source_file('src/app.tsx'), source_file('src/utils.ts'),
            source_file('tests/test_x.py'),
            source_file('webpack.config.js'),
            symbol('tests/test_x.py', 'test_handle'),
            symbol('webpack.config.js', 'defaultConfig'),
        ]
        results = [r for r in build(facts) if r]
        all_sites = ' '.join(s.get('path', '') for r in results for s in r['value'].get('sites', []))
        self.assertNotIn('tests/test_x.py', all_sites)
        self.assertNotIn('webpack.config.js', all_sites)


class EntrySymbolSeedsTests(unittest.TestCase):
    """Entry-point handlers are excluded from the dead-symbol list."""

    def test_entry_handlers_are_seeds(self):
        facts = [entry_point('a.py', handler='main')]
        seeds = _entry_symbol_seeds(facts)
        self.assertIn('main', seeds)

    def test_test_entries_dont_seed(self):
        facts = [entry_point('test_x.py', category='test', handler='test_handle')]
        seeds = _entry_symbol_seeds(facts)
        self.assertNotIn('test_handle', seeds)
