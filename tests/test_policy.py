"""The declared architecture as a checked contract."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import shared_fixture  # noqa: F401  (runs without measured detector verdicts)
from eaos import cli
from eaos.dossier import assemble
from eaos.facts.run import collect
from eaos.policy import check, declared_exclusions, init, load_policy

SETS = ['syntax', 'resolve', 'entrypoints', 'config', 'metrics', 'domain', 'history', 'graph', 'flows']


def layered_repo(root, violating=False):
    repo = Path(root) / 'repo'
    (repo / 'app/facts').mkdir(parents=True)
    (repo / 'app/runtime').mkdir(parents=True)
    (repo / 'app/facts/__init__.py').write_text('')
    (repo / 'app/runtime/__init__.py').write_text('')
    (repo / 'app/runtime/engine.py').write_text('def start():\n    return 1\n')
    body = 'from app.runtime.engine import start\n\n\ndef collect():\n    return start()\n' if violating \
        else 'def collect():\n    return 1\n'
    (repo / 'app/facts/reader.py').write_text(body)
    (repo / 'app/__init__.py').write_text('')
    (repo / 'eaos.policy.json').write_text(json.dumps({
        'schema_version': 1,
        'layers': {'facts': ['app/facts/**'], 'runtime': ['app/runtime/**'], 'core': ['app/__init__.py']},
        'rules': [{'deny': {'from': 'facts', 'to': 'runtime'},
                   'reason': 'the deterministic layer must run without the model path'}]}))
    return repo


class PolicyTests(unittest.TestCase):
    def prepared(self, tmp, violating, drop_core=False, remove=False):
        repo = layered_repo(tmp, violating)
        out = Path(tmp) / 'out'
        collect(repo, out, SETS)
        if drop_core:
            policy = json.loads((repo / 'eaos.policy.json').read_text())
            del policy['layers']['core']
            (repo / 'eaos.policy.json').write_text(json.dumps(policy))
        if remove:
            (repo / 'eaos.policy.json').unlink()
        return repo, out

    def test_the_check_reports_the_honest_status(self):
        # A file outside every layer is unchecked: reporting OK would call unexamined code safe.
        cases = [(False, False, False, 'OK', 0, None), (False, True, False, 'INCOMPLETE', 0, 'app/__init__.py'),
                 (True, True, False, 'VIOLATED', 1, None), (True, False, False, 'VIOLATED', 1, 'without the model path'),
                 (False, False, True, 'NO_POLICY', 0, 'eaos policy init')]
        for violating, drop_core, remove, status, violations, shown in cases:
            with self.subTest(status=status, drop_core=drop_core), tempfile.TemporaryDirectory() as tmp:
                repo, out = self.prepared(tmp, violating, drop_core, remove)
                result = check(repo, out)
                self.assertEqual(result['status'], status)
                if status != 'NO_POLICY':
                    self.assertEqual(result['violations'], violations)
                if status == 'OK':
                    self.assertEqual(result['unclassified_count'], 0)
                if shown:
                    self.assertIn(shown, (out / 'POLICY.md').read_text(encoding='utf-8'))
                if status == 'VIOLATED' and not drop_core:
                    self.assertIn('app/facts/reader.py', (out / 'POLICY.md').read_text(encoding='utf-8'))

    def test_the_gate_exits_nonzero_on_a_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, out = self.prepared(tmp, violating=True)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(['policy', 'check', str(repo), '--out', str(out)]), 2)

    def test_a_scaffold_declares_structure_and_a_rule_needs_a_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, out = self.prepared(tmp, violating=False, remove=True)
            self.assertTrue(Path(init(repo, out)['created']).is_file())
            policy, _ = load_policy(repo)
            self.assertTrue(policy['layers'])
            self.assertEqual(policy['rules'], [], 'a scaffold declares structure, never rules nobody agreed to')
            (repo / 'eaos.policy.json').write_text(json.dumps({
                'schema_version': 1, 'layers': {'a': ['**']}, 'rules': [{'deny': {'from': 'a', 'to': 'a'}}]}))
            with self.assertRaisesRegex(ValueError, 'reason'):
                check(repo, out)

    def test_a_violation_cites_the_module_edge_fact_it_was_derived_from(self):
        fixture = Path(__file__).resolve().parent / 'fixtures/benchmarks/policy-violation'
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            collect(fixture, out, SETS)
            check(fixture, out)
            resolve = json.loads((out / 'facts/resolve.json').read_text())
            policy = json.loads((out / 'facts/policy.json').read_text())
        edges = {f['id'] for f in resolve['facts'] if f['kind'] == 'module_edge'}
        violations = [f for f in policy['facts'] if f['kind'] == 'policy_violation']
        self.assertTrue(violations, 'the fixture must produce a violation')
        for fact in violations:
            self.assertIn(fact['value'].get('edge_fact_id'), edges)

    def test_this_repository_satisfies_its_own_declared_policy(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            collect(root, out, SETS)
            self.assertEqual(check(root, out)['status'], 'OK', 'the project must obey the layering it declares')


class DeclaredExclusionTests(unittest.TestCase):
    """What counts as the system under review is the project's decision, declared in its policy."""

    def repo_with(self, root, exclude):
        repo = Path(root) / 'repo'; (repo / 'samples').mkdir(parents=True)
        (repo / 'app.py').write_text('RATE = 0.1\n\n\ndef total(x):\n    return x * RATE\n')
        (repo / 'samples/copy.py').write_text('RATE = 0.1\n\n\ndef total(x):\n    return x * RATE\n')
        policy = {'schema_version': 1, 'layers': {'app': ['app.py']}, 'rules': []}
        if exclude is not None: policy['analysis'] = {'exclude': exclude}
        (repo / 'eaos.policy.json').write_text(json.dumps(policy))
        return repo

    def test_declared_exclusions_are_honoured_and_nothing_is_excluded_silently(self):
        for exclude, rate_claims in ((['samples'], False), (None, True)):
            with self.subTest(exclude=exclude), tempfile.TemporaryDirectory() as tmp:
                assemble(self.repo_with(tmp, exclude), Path(tmp) / 'out')
                dossier = json.loads((Path(tmp) / 'out/dossier.json').read_text())
                excluded = dossier['provenance']['excluded_patterns']
                self.assertTrue('samples' in excluded if exclude else excluded)
                self.assertEqual(bool([c for c in dossier['claims'] if 'RATE' in c['statement']]), rate_claims)
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.repo_with(tmp, 'tests')
            with self.assertRaisesRegex(ValueError, 'analysis.exclude'):
                declared_exclusions(repo)
