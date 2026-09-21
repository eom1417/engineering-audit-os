"""Realistic scenario: a Flask app with the exact patterns from the doctrine."""
from pathlib import Path
import shutil
import tempfile
import unittest
from shared_fixture import Workspace
from eaos.facts.run import collect
from eaos.sustainability import render
from eaos.transform_plan import build, render as render_plan


class RealisticScenarioTests(Workspace):

    def _make_repo(self):
        repo = Path(self.tmp) / 'app'; repo.mkdir()
        # The doctrine's reference: same pricing rule in two modules with different names.
        (repo / 'orders').mkdir()
        (repo / 'billing').mkdir()
        (repo / 'orders' / 'service.py').write_text(
            "def order_total(amount, tier):\n"
            "    subtotal = amount\n"
            "    if tier == 'premium':\n"
            "        subtotal = subtotal * 0.9\n"
            "    tax = subtotal * 0.15\n"
            "    return round(subtotal + tax, 2)\n"
        )
        (repo / 'billing' / 'service.py').write_text(
            "def invoice_amount(amount, tier):\n"
            "    base = amount\n"
            "    if tier == 'premium':\n"
            "        base = base * 0.9\n"
            "    vat = base * 0.15\n"
            "    return round(base + vat, 2)\n"
        )
        # Same coordination sequence in three places.
        (repo / 'orders' / 'controller.py').write_text(
            "def create(req):\n    validate(req)\n    save(req)\n    notify(req)\n    return req\n"
            "def update(req):\n    validate(req)\n    save(req)\n    notify(req)\n    return req\n"
            "def cancel(req):\n    validate(req)\n    save(req)\n    notify(req)\n    return req\n"
        )
        # N+1 in a list endpoint.
        (repo / 'orders' / 'report.py').write_text(
            "def list_for(orders):\n    totals = []\n"
            "    for order in orders:\n        totals.append(order.get_total())\n"
            "    return totals\n"
        )
        # Pass-through layer.
        (repo / 'billing' / 'facade.py').write_text(
            "def charge(payload):\n    return invoice(payload)\n"
        )
        # Hoistable call.
        (repo / 'orders' / 'audit.py').write_text(
            "def record(events):\n    for ev in events:\n"
            "        constant()\n        store(ev)\n    return events\n"
        )
        return repo

    def test_realistic_app_produces_a_dashboard_with_moves(self):
        repo = self._make_repo()
        out = Path(self.tmp) / 'out'
        collect(repo, out, ['syntax', 'structure', 'fingerprint', 'sequences', 'redundancy',
                              'domain', 'graph', 'metrics', 'flows'])
        dashboard = render(out, language='en')
        # We expect indicators with gaps.
        single_source = next(r for r in dashboard['rows'] if r['indicator'] == 'single_source')
        minimal_path = next(r for r in dashboard['rows'] if r['indicator'] == 'minimal_path')
        self.assertGreater(single_source['gap'], 0)
        self.assertGreater(minimal_path['gap'], 0)
        # The plan should propose moves for both indicators.
        plan = build(out)
        kinds = {stage['move'] for stage in plan['stages']}
        self.assertIn('canonicalize', kinds)
        self.assertIn('eliminate_redundancy', kinds)

    def test_realistic_app_transform_plan_is_executable_spec(self):
        repo = self._make_repo()
        out = Path(self.tmp) / 'out'
        collect(repo, out, ['syntax', 'structure', 'fingerprint', 'sequences', 'redundancy',
                              'domain', 'graph', 'metrics', 'flows', 'resolve'])
        plan = build(out)
        files = render_plan(out, plan, language='en')
        # Every stage in a realistic app must carry everything a model or human needs.
        for stage in plan['stages']:
            self.assertIn('stage', stage); self.assertIn('move', stage); self.assertIn('sites', stage)
            self.assertTrue(stage['falsifier'])
            self.assertTrue(stage['rollback'])
            self.assertIn('acceptance', stage)
        # The JSON plan must be parseable.
        import json
        reparsed = json.loads(Path(files['json']).read_text())
        self.assertEqual(len(reparsed['stages']), len(plan['stages']))
