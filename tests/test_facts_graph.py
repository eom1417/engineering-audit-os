"""Dependency graph and attention ranking: structure, cycles, and a declared heuristic."""
import json
from pathlib import Path
import tempfile
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
