"""Dependency graph and attention ranking: structure, cycles, and a declared heuristic."""
import json
from pathlib import Path
import tempfile
import shutil
import unittest
from shared_fixture import TemporaryWorkspace
from eaos.facts.run import collect

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'
SETS = ['syntax', 'resolve', 'entrypoints', 'config', 'metrics', 'history', 'graph']


def graph_of(repo, out):
    collect(repo, out, SETS)
    return json.loads((Path(out) / 'facts/graph.json').read_text())


class GraphTests(TemporaryWorkspace):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data = graph_of(FIXTURE, Path(cls.tmp.name) / 'out')
        cls.nodes = {f['location']['path']: f['value'] for f in cls.data['facts'] if f['kind'] == 'graph_node'}


    def test_shared_module_shows_real_fan_in(self):
        self.assertEqual(self.nodes['core/pricing.py']['fan_in'], 3)
        self.assertIn('core/pricing.py', self.nodes['cli.py']['depends_on'])

    def test_entry_distance_is_measured_from_detected_entry_points(self):
        self.assertEqual(self.nodes['cli.py']['entry_distance'], 0)
        self.assertEqual(self.nodes['core/pricing.py']['entry_distance'], 1)

    def test_attention_ranking_exposes_its_factors(self):
        top = self.data['summary']['attention_order'][0]
        self.assertEqual(set(top['factors']), {'centrality', 'change', 'complexity', 'entry_proximity'})
        self.assertEqual(self.data['summary']['weights']['centrality'], 0.3)
        self.assertIn('never a verdict', self.data['summary']['interpretation'].replace('not a verdict', 'never a verdict'))

    def test_cycles_are_reported_as_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'a.py').write_text('from b import helper\n\n\ndef run():\n    return helper()\n')
            (repo / 'b.py').write_text('import a\n\n\ndef helper():\n    return a\n')
            data = graph_of(repo, Path(tmp) / 'out')
            self.assertEqual(data['summary']['cycles'], 1)
            members = [f['value']['members'] for f in data['facts'] if f['kind'] == 'graph_cycle']
            self.assertEqual(members, [['a.py', 'b.py']])

    def test_a_clean_tree_reports_no_cycle(self):
        self.assertEqual(self.data['summary']['cycles'], 0)

    def test_graph_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = graph_of(FIXTURE, Path(tmp) / 'a'); second = graph_of(FIXTURE, Path(tmp) / 'b')
            self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))


class AttentionBudgetTests(unittest.TestCase):
    """The declared attention budget must defer files visibly, never silently."""

    def test_deferred_files_are_recorded_as_omissions(self):
        import contextlib, io
        from eaos import cli, workflow
        from eaos.runtime.context import Context
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / 'run'
            with contextlib.redirect_stdout(io.StringIO()):
                cli.main(['init', str(FIXTURE), '--out', str(run)])
            workflow.initialize(run)
            state = json.loads((run / 'run.json').read_text())
            context = Context(run, state, 96000)
            order = ['core/pricing.py', 'cli.py']
            batches, omissions = context.chunks(order, max_files=2)
            inspected = [block['path'] for batch in batches for block in batch]
            self.assertEqual(sorted(set(inspected)), sorted(order))
            deferred = [row['path'] for row in omissions if 'attention budget' in row['reason']]
            self.assertIn('api/server.ts', deferred)
            self.assertNotIn('core/pricing.py', deferred)


class EngineEdgesInGraphTests(TemporaryWorkspace):
    """Edges an external engine resolved must show up in the graph, but labelled with their engine."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = cls.workspace()

    def test_engine_resolved_edges_appear_in_the_graph_with_source_label(self):
        """When an engine provides an edge, the graph records it under 'engine:<name>' and counts it."""
        from eaos.facts.resolve import make as fact_make, digest
        from eaos.facts.source import Source
        from eaos.facts.graph import run as graph_run
        from eaos.facts.resolve import run as resolve_run
        from pathlib import Path
        tmp = tempfile.mkdtemp()
        try:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'a.go').write_text('package a\n')
            (repo / 'b.go').write_text('package b\n')
            src = Source(repo)
            engine_edge = fact_make('call_edge', 'external', '1', digest(b''),
                                     {'path': 'a.go'},
                                     {'caller': 'A', 'callee': 'B',
                                      'caller_path': 'a.go', 'callee_path': 'b.go',
                                      'line': 1, 'source': 'codegraph', 'engine': 'codegraph'},
                                     resolution='RESOLVED_BY_ENGINE', limitations=[])
            resolved = resolve_run(repo, src, imports=None, external_edges=[engine_edge])
            graph = graph_run(repo, src, edges=resolved['facts'], entry_points=[], metrics=[], history=[])
            self.assertEqual(graph['summary']['engine_edges'], 1)
            self.assertEqual(graph['summary']['own_edges'], 0)
            nodes = {f['location']['path']: f['value'] for f in graph['facts'] if f['kind'] == 'graph_node'}
            self.assertIn('b.go', nodes['a.go']['depends_on'])
            source_map = {d['path']: d['source'] for d in nodes['a.go']['depends_on_with_source']}
            self.assertEqual(source_map['b.go'], 'engine:codegraph')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_own_and_engine_edges_are_counted_separately(self):
        """An engine edge alongside our own resolver's edge yields both counters non-zero."""
        from eaos.facts.resolve import make as fact_make, digest
        from eaos.facts.source import Source
        from eaos.facts.graph import run as graph_run
        from eaos.facts.resolve import run as resolve_run
        from pathlib import Path
        tmp = tempfile.mkdtemp()
        try:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'a.go').write_text('package a\n')
            (repo / 'b.go').write_text('package b\n')
            (repo / 'c.go').write_text('package c\n')
            src = Source(repo)
            own_edge = fact_make('call_edge', 'resolve', '1', digest(b''),
                                 {'path': 'a.go'},
                                 {'caller': 'A', 'callee': 'B',
                                  'caller_path': 'a.go', 'callee_path': 'b.go',
                                  'line': 1},
                                 resolution='RESOLVED', limitations=[])
            engine_edge = fact_make('call_edge', 'external', '1', digest(b''),
                                     {'path': 'a.go'},
                                     {'caller': 'A', 'callee': 'C',
                                      'caller_path': 'a.go', 'callee_path': 'c.go',
                                      'line': 1, 'source': 'codegraph', 'engine': 'codegraph'},
                                     resolution='RESOLVED_BY_ENGINE', limitations=[])
            resolved = resolve_run(repo, src, imports=None, external_edges=[engine_edge])
            # Inject the own edge into the resolved facts
            resolved['facts'].append(own_edge)
            graph = graph_run(repo, src, edges=resolved['facts'], entry_points=[], metrics=[], history=[])
            self.assertEqual(graph['summary']['own_edges'], 1)
            self.assertEqual(graph['summary']['engine_edges'], 1)
            self.assertEqual(graph['summary']['edges'], 2)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
