"""Dependency graph and attention ranking: structure, cycles, and a declared heuristic."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from eaos.facts.run import collect

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'
SETS = ['syntax', 'resolve', 'entrypoints', 'config', 'metrics', 'history', 'graph']


def graph_of(repo, out):
    collect(repo, out, SETS)
    return json.loads((Path(out) / 'facts/graph.json').read_text())


class GraphTests(unittest.TestCase):
    def test_fan_in_entry_distance_and_an_explained_attention_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = graph_of(FIXTURE, Path(tmp) / 'out')
        nodes = {f['location']['path']: f['value'] for f in data['facts'] if f['kind'] == 'graph_node'}
        self.assertEqual(nodes['core/pricing.py']['fan_in'], 3)
        self.assertIn('core/pricing.py', nodes['cli.py']['depends_on'])
        self.assertEqual(nodes['cli.py']['entry_distance'], 0)
        self.assertEqual(nodes['core/pricing.py']['entry_distance'], 1)
        top = data['summary']['attention_order'][0]
        self.assertEqual(set(top['factors']), {'centrality', 'change', 'complexity', 'entry_proximity'})
        self.assertEqual(data['summary']['cycles'], 0)

    def test_cycles_are_reported_as_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'a.py').write_text('from b import helper\n\n\ndef run():\n    return helper()\n')
            (repo / 'b.py').write_text('import a\n\n\ndef helper():\n    return a\n')
            data = graph_of(repo, Path(tmp) / 'out')
        self.assertEqual(data['summary']['cycles'], 1)
        self.assertEqual([f['value']['members'] for f in data['facts'] if f['kind'] == 'graph_cycle'], [['a.py', 'b.py']])

    def test_engine_resolved_edges_are_labelled_and_counted_apart_from_our_own(self):
        from eaos.facts.resolve import make as fact_make, digest, run as resolve_run
        from eaos.facts.source import Source
        from eaos.facts.graph import run as graph_run
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            for name in 'abc':
                (repo / f'{name}.go').write_text(f'package {name}\n')
            src = Source(repo)
            own = fact_make('call_edge', 'resolve', '1', digest(b''), {'path': 'a.go'},
                            {'caller': 'A', 'callee': 'B', 'caller_path': 'a.go', 'callee_path': 'b.go', 'line': 1},
                            resolution='RESOLVED', limitations=[])
            engine = fact_make('call_edge', 'external', '1', digest(b''), {'path': 'a.go'},
                               {'caller': 'A', 'callee': 'C', 'caller_path': 'a.go', 'callee_path': 'c.go',
                                'line': 1, 'source': 'codegraph', 'engine': 'codegraph'},
                               resolution='RESOLVED_BY_ENGINE', limitations=[])
            resolved = resolve_run(repo, src, imports=None, external_edges=[engine])
            resolved['facts'].append(own)
            graph = graph_run(repo, src, edges=resolved['facts'], entry_points=[], metrics=[], history=[])
        self.assertEqual((graph['summary']['own_edges'], graph['summary']['engine_edges'], graph['summary']['edges']),
                         (1, 1, 2))
        nodes = {f['location']['path']: f['value'] for f in graph['facts'] if f['kind'] == 'graph_node'}
        sources = {d['path']: d['source'] for d in nodes['a.go']['depends_on_with_source']}
        self.assertEqual(sources['c.go'], 'engine:codegraph')


class AttentionBudgetTests(unittest.TestCase):
    """The declared attention budget must defer files visibly, never silently."""

    def test_deferred_files_are_recorded_as_omissions(self):
        from eaos.core.repo_context import Context
        from eaos.core.workspace import inventory, write
        with tempfile.TemporaryDirectory() as tmp:
            target, run = Path(tmp) / 'target', Path(tmp) / 'run'
            shutil.copytree(FIXTURE, target); run.mkdir()
            write(run / 'inventory.json', inventory(target))
            write(run / 'evidence.json', [])
            context = Context(run, {'target': str(target), 'revision': 'r1'}, 96000)
            order = ['core/pricing.py', 'cli.py']
            batches, omissions = context.chunks(order, max_files=2)
            inspected = [block['path'] for batch in batches for block in batch]
        self.assertEqual(sorted(set(inspected)), sorted(order))
        deferred = [row['path'] for row in omissions if 'attention budget' in row['reason']]
        self.assertIn('api/server.ts', deferred)
        self.assertNotIn('core/pricing.py', deferred)
