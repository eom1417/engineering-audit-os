"""The six-indicator sustainability dashboard and the moves derived from it."""
import json
from pathlib import Path
import tempfile
import unittest
from eaos import sustainability
from eaos.facts.run import collect


SETS = ['syntax', 'structure', 'fingerprint', 'sequences', 'redundancy', 'domain', 'graph', 'metrics', 'flows']


def _make_run(tmp, source='tests/fixtures/sustainability'):
    target = Path(tmp) / 'source'
    target.mkdir(parents=True, exist_ok=True)
    src = Path(source)
    if src.is_dir():
        for child in src.rglob('*'):
            if child.is_file():
                destination = target / child.relative_to(src)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(child.read_bytes())
    collect(target, Path(tmp) / 'out', SETS)
    return Path(tmp) / 'out'


class SustainabilityTests(unittest.TestCase):
    def test_six_indicators_are_computed(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = _make_run(tmp)
            dashboard = sustainability.compute(out)
        rows = dashboard['rows']
        self.assertEqual(len(rows), 6)
        names = {row['indicator'] for row in rows}
        self.assertEqual(names, set(sustainability.INDICATORS))
        for row in rows:
            self.assertIn('value', row); self.assertIn('target', row); self.assertIn('gap', row)

    def test_single_source_indicator_reports_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = _make_run(tmp)
            dashboard = sustainability.compute(out)
        single = next(row for row in dashboard['rows'] if row['indicator'] == 'single_source')
        self.assertGreater(single['value'], 0)

    def test_minimal_path_indicator_reports_redundant_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = _make_run(tmp)
            dashboard = sustainability.compute(out)
        minimal = next(row for row in dashboard['rows'] if row['indicator'] == 'minimal_path')
        self.assertGreater(minimal['value'], 0)

    def test_moves_are_generated_for_nonzero_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = _make_run(tmp)
            result = sustainability.render(out, language='en')
        self.assertGreater(len(result['moves']), 0)
        for move in result['moves']:
            self.assertIn('move', move); self.assertIn('indicator', move); self.assertIn('falsifier', move)

    def test_render_writes_sustainability_md(self):
        tmp = tempfile.mkdtemp()
        try:
            out = _make_run(tmp)
            result = sustainability.render(out, language='en')
            artifact = Path(result['artifact'])
            self.assertTrue(artifact.is_file())
            content = artifact.read_text()
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertIn('# Sustainability dashboard', content)
        # The dashboard renders human-friendly names; assert the names are present.
        for label in ('Single source', 'Minimal path', 'Single owner', 'Honest boundaries',
                       'Verifiable paths', 'Understandable units'):
            self.assertIn(label, content)

    def test_render_arabic_produces_arabic_header(self):
        tmp = tempfile.mkdtemp()
        try:
            out = _make_run(tmp)
            result = sustainability.render(out, language='ar')
            content = Path(result['artifact']).read_text()
            self.assertIn('لوحة الاستدامة', content)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)


    def test_empty_repository_has_only_baseline_indicators(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'source'; repo.mkdir()
            (repo / 'app.py').write_text('x = 1\n')
            collect(repo, Path(tmp) / 'out', SETS)
            dashboard = sustainability.compute(Path(tmp) / 'out')
        # No symbols => the baseline indicators are all 0.
        for indicator in ['single_source', 'understandable_units']:
            row = next(r for r in dashboard['rows'] if r['indicator'] == indicator)
            self.assertEqual(row['value'], 0)

    def test_each_move_carries_a_falsifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = _make_run(tmp)
            result = sustainability.render(out, language='en')
        for move in result['moves']:
            self.assertTrue(move['falsifier'])


class SustainabilityLimitationsTests(unittest.TestCase):
    def test_indicators_are_pure_functions_of_facts(self):
        text = ' '.join(sustainability.LIMITATIONS)
        self.assertIn('function of structural facts', text)


class LedgerIntegrationTests(unittest.TestCase):
    """The sustainability facts must reach the one ledger, not sit in a parallel silo."""

    def repo(self, root):
        repo = Path(root) / 'repo'; repo.mkdir()
        (repo / 'a.py').write_text('def compute_order_total(order):\n'
                                   '    subtotal = sum(l.price * l.qty for l in order.lines)\n'
                                   '    if order.tier == "premium":\n        subtotal = subtotal * 0.9\n'
                                   '    tax = subtotal * 0.15\n    return round(subtotal + tax, 2)\n')
        (repo / 'b.py').write_text('def invoice_amount(invoice):\n'
                                   '    base = sum(i.price * i.qty for i in invoice.lines)\n'
                                   '    if invoice.tier == "premium":\n        base = base * 0.9\n'
                                   '    vat = base * 0.15\n    return round(base + vat, 2)\n')
        return repo

    def test_a_structural_duplicate_becomes_a_claim_a_probe_and_a_card(self):
        from eaos import probes
        from eaos.dossier import assemble
        from eaos.plan import build
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.repo(tmp); out = Path(tmp) / 'out'
            assemble(repo, out)
            claims = json.loads((out / 'dossier.json').read_text())['claims']
            duplicate = next(c for c in claims if 'same structure' in c['statement'])
            self.assertEqual(duplicate['confidence'], 'CONFIRMED')
            self.assertTrue(duplicate['falsifier'])
            probes.run_all(repo, out)
            rows = json.loads((out / 'probes.json').read_text())
            verdict = next(r for r in rows if r['specification'].get('query') == 'duplicate_cluster_present')
            self.assertEqual(verdict['status'], 'CONFIRMED')
            build(repo, out)
            task = next(t for t in json.loads((out / 'plan.json').read_text())['tasks']
                        if t['claim_id'] == duplicate['id'])
            self.assertEqual(task['pattern'], 'canonicalize')
            self.assertEqual(sorted(task['paths']), ['a.py', 'b.py'])
            # After N2.T2 the priority is measured from the graph, not the cluster size.
            # A CONFIRMED duplicate without graph dependents, flows or entry points has zero
            # blast radius and therefore zero priority; the card still exists and the
            # acceptance chain still proves the claim → probe → card path.
            self.assertIn('priority', task)
            self.assertIn('blast_radius', task)
            self.assertEqual(task['blast_radius']['total'], 0)

    def test_a_probe_cannot_refute_a_claim_whose_facts_are_absent(self):
        """Regression: missing fact sets produced REFUTED instead of INCONCLUSIVE."""
        from eaos.probes import run_graph_query
        status, detail = run_graph_query({'query': 'duplicate_cluster_present', 'shape_sha': 'x'}, {})
        self.assertEqual(status, 'INCONCLUSIVE')
        self.assertIn('not present in this run', detail)

    def test_one_canonical_list_of_fact_sets(self):
        """Regression: three modules kept their own copy and a new set was invisible to them."""
        import ast
        from eaos.facts.run import ALL_SETS
        self.assertIn('fingerprint', ALL_SETS)
        self.assertIn('redundancy', ALL_SETS)
        root = Path(__file__).resolve().parents[1] / 'eaos'
        offenders = []
        for path in sorted(root.rglob('*.py')):
            if path.name == 'run.py' and path.parent.name == 'facts': continue  # the definition itself
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if not isinstance(node, ast.List) or len(node.elts) < 6: continue
                values = [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                if {'syntax', 'resolve', 'entrypoints', 'graph'} <= set(values):
                    offenders.append(f'{path.relative_to(root.parent)}:{node.lineno}')
        self.assertEqual(offenders, [], 'the fact-set list belongs in one place only')


class NonDestructiveCommandTests(unittest.TestCase):
    """Regression: a later command re-collected a subset and wiped the flows an earlier one traced."""

    def test_running_the_dashboard_does_not_erase_earlier_facts(self):
        import contextlib, io
        from eaos import cli
        from eaos.dossier import assemble
        from eaos.facts.store import read_set
        fixture = Path(__file__).resolve().parent / 'fixtures/polyglot'
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            assemble(fixture, out)
            before = read_set(out, 'flows')['summary']['flows']
            self.assertGreater(before, 0, 'the fixture must trace some flow for this test to mean anything')
            with contextlib.redirect_stdout(io.StringIO()):
                cli.main(['sustainability', str(fixture), '--out', str(out)])
            after = read_set(out, 'flows')['summary']['flows']
            self.assertEqual(after, before, 'a later command must not degrade an earlier result')

    def test_a_partial_collection_is_never_requested_from_the_cli(self):
        import ast
        source = (Path(__file__).resolve().parents[1] / 'eaos/cli.py').read_text()
        for node in ast.walk(ast.parse(source)):
            if not (isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'collect'): continue
            selected = node.args[2] if len(node.args) > 2 else None
            if isinstance(selected, ast.List) and len(selected.elts) > 3:
                self.fail(f'cli.py:{node.lineno} collects a hand-listed subset; dependent extractors lose their inputs')
