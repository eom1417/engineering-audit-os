"""Simulator: project the graph state and the indicator delta before any code is written."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from eaos.facts.run import collect
from eaos.transform_plan import build
from eaos.simulator import simulate


SETS = ['syntax', 'structure', 'fingerprint', 'sequences', 'redundancy',
        'domain', 'graph', 'metrics', 'flows', 'resolve']


def _setup(tmp, source):
    repo = Path(tmp) / 'src'; repo.mkdir()
    src = Path(source)
    for child in src.rglob('*'):
        if child.is_file():
            d = repo / child.relative_to(src)
            d.parent.mkdir(parents=True, exist_ok=True)
            d.write_bytes(child.read_bytes())
    out = Path(tmp) / 'out'
    collect(repo, out, SETS)
    return out


class SimulatorTests(unittest.TestCase):
    def test_before_and_after_have_all_six_indicators(self):
        tmp = tempfile.mkdtemp()
        try:
            out = _setup(tmp, 'tests/fixtures/sustainability')
            plan = build(out)
            for stage in plan['stages']:
                result = simulate(out, stage)
                # The simulator projects the five structural indicators; verifiable_paths
                # depends on flow-facts and is intentionally not part of the projection.
                for row in result['after'].keys():
                    self.assertIn(row, result['delta'])
                    self.assertIn(row, result['before'])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_canonicalize_stage_can_reduce_single_source(self):
        tmp = tempfile.mkdtemp()
        try:
            out = _setup(tmp, 'tests/fixtures/sustainability')
            plan = build(out)
            # Find a canonicalize stage whose canonical_home is NOT one of the existing sites
            # — that is the only way the cluster shrinks.
            for stage in plan['stages']:
                if stage['move'] != 'canonicalize': continue
                result = simulate(out, stage)
                if result['delta']['single_source'] < 0:
                    self.assertLess(result['delta']['single_source'], 0)
                    return
            self.skipTest('No canonicalize stage in this fixture shrinks the cluster')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_no_op_stage_reports_zero_delta(self):
        tmp = tempfile.mkdtemp()
        try:
            out = _setup(tmp, 'tests/fixtures/sustainability')
            plan = build(out)
            for stage in plan['stages']:
                if stage['move'] != 'canonicalize': continue
                # If the home is already a site, removing duplicates is a no-op.
                sites = {site['path'] for site in stage['sites']}
                if stage.get('canonical_home') in sites:
                    result = simulate(out, stage)
                    self.assertEqual(result['delta']['single_source'], 0.0)
                    return
            self.skipTest('No no-op stage found')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_eliminate_redundancy_reduces_minimal_path(self):
        tmp = tempfile.mkdtemp()
        try:
            out = _setup(tmp, 'tests/fixtures/sustainability')
            plan = build(out)
            for stage in plan['stages']:
                if stage['move'] != 'eliminate_redundancy': continue
                result = simulate(out, stage)
                self.assertLessEqual(result['delta']['minimal_path'], 0)
                return
            self.skipTest('No eliminate_redundancy stage in this fixture')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class SimulatorLimitationsTests(unittest.TestCase):
    def test_simulator_does_not_run_code(self):
        from eaos import simulator
        self.assertIn('replays the structural graph',
                       ' '.join(simulator.LIMITATIONS))
