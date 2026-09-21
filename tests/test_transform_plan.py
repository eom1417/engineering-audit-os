"""Machine-executable transform plan: stages, acceptance, rollback, falsifier."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from eaos import transform_plan
from eaos.facts.run import collect


SETS = ['syntax', 'structure', 'fingerprint', 'sequences', 'redundancy',
        'domain', 'graph', 'metrics', 'flows', 'resolve']


def _setup(tmp, source_dir):
    repo = Path(tmp) / 'src'; repo.mkdir()
    src = Path(source_dir)
    for child in src.rglob('*'):
        if child.is_file():
            d = repo / child.relative_to(src)
            d.parent.mkdir(parents=True, exist_ok=True)
            d.write_bytes(child.read_bytes())
    out = Path(tmp) / 'out'
    collect(repo, out, SETS)
    return repo, out


class TransformPlanTests(unittest.TestCase):
    def test_stages_are_self_contained(self):
        tmp = tempfile.mkdtemp()
        try:
            _, out = _setup(tmp, 'tests/fixtures/sustainability')
            plan = transform_plan.build(out)
            self.assertGreater(len(plan['stages']), 0)
            for stage in plan['stages']:
                self.assertIn('stage', stage)
                self.assertIn('move', stage)
                self.assertIn('rollback', stage); self.assertIn('falsifier', stage)
                self.assertIn('acceptance', stage); self.assertIn('predicted', stage)
                self.assertIn('sites', stage)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_canonicalize_stage_carries_canonical_home(self):
        tmp = tempfile.mkdtemp()
        try:
            _, out = _setup(tmp, 'tests/fixtures/sustainability')
            plan = transform_plan.build(out)
            canonicalize = [s for s in plan['stages'] if s['move'] == 'canonicalize']
            self.assertGreater(len(canonicalize), 0)
            for stage in canonicalize:
                self.assertIn('canonical_home', stage)
                self.assertIsNotNone(stage['canonical_home'])
                self.assertIn('all_candidates', stage)
                self.assertGreater(len(stage['all_candidates']), 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_redundancy_stage_carries_kind_and_sites(self):
        tmp = tempfile.mkdtemp()
        try:
            _, out = _setup(tmp, 'tests/fixtures/sustainability')
            plan = transform_plan.build(out)
            redundancy = [s for s in plan['stages'] if s['move'] == 'eliminate_redundancy']
            self.assertGreater(len(redundancy), 0)
            for stage in redundancy:
                self.assertIn('redundancy_kind', stage)
                self.assertIn(stage['redundancy_kind'],
                                {'repeated_call', 'hoistable_call', 'n_plus_one', 'pass_through'})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_every_stage_has_a_nonempty_falsifier(self):
        tmp = tempfile.mkdtemp()
        try:
            _, out = _setup(tmp, 'tests/fixtures/sustainability')
            plan = transform_plan.build(out)
            for stage in plan['stages']:
                self.assertTrue(stage['falsifier'])
                self.assertNotEqual(stage['falsifier'].strip(), '')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_render_writes_json_and_markdown(self):
        tmp = tempfile.mkdtemp()
        try:
            _, out = _setup(tmp, 'tests/fixtures/sustainability')
            plan = transform_plan.build(out)
            result = transform_plan.render(out, plan, language='en')
            self.assertTrue(Path(result['json']).is_file())
            self.assertTrue(Path(result['markdown']).is_file())
            content = Path(result['markdown']).read_text()
            self.assertIn('Machine-executable transform plan', content)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_stages_have_acceptance_criterion(self):
        tmp = tempfile.mkdtemp()
        try:
            _, out = _setup(tmp, 'tests/fixtures/sustainability')
            plan = transform_plan.build(out)
            for stage in plan['stages']:
                self.assertIsNotNone(stage['acceptance'])
                self.assertIn('kind', stage['acceptance'])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TransformPlanLimitationsTests(unittest.TestCase):
    def test_plan_does_not_run_changes(self):
        self.assertIn('proposal, not an executed edit',
                      ' '.join(transform_plan.LIMITATIONS))
