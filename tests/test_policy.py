"""The declared architecture as a checked contract."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from eaos import cli
from eaos.facts.run import collect
from eaos.policy import check, init, load_policy

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
        'layers': {'facts': ['app/facts/**'], 'runtime': ['app/runtime/**']},
        'rules': [{'deny': {'from': 'facts', 'to': 'runtime'},
                   'reason': 'the deterministic layer must run without the model path'}]}))
    return repo


class PolicyTests(unittest.TestCase):
    def prepared(self, tmp, violating):
        repo = layered_repo(tmp, violating)
        out = Path(tmp) / 'out'
        collect(repo, out, SETS)
        return repo, out

    def test_a_clean_project_passes_its_own_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, out = self.prepared(tmp, violating=False)
            result = check(repo, out)
            self.assertEqual(result['status'], 'OK')
            self.assertEqual(result['violations'], 0)

    def test_a_forbidden_edge_is_reported_with_its_location_and_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, out = self.prepared(tmp, violating=True)
            result = check(repo, out)
            self.assertEqual(result['status'], 'VIOLATED')
            self.assertEqual(result['violations'], 1)
            text = (out / 'POLICY.md').read_text()
            self.assertIn('app/facts/reader.py', text)
            self.assertIn('without the model path', text)

    def test_the_gate_exits_nonzero_on_a_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, out = self.prepared(tmp, violating=True)
            with contextlib.redirect_stdout(io.StringIO()):
                code = cli.main(['policy', 'check', str(repo), '--out', str(out)])
            self.assertEqual(code, 2)

    def test_a_project_without_a_policy_is_told_how_to_get_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, out = self.prepared(tmp, violating=False)
            (repo / 'eaos.policy.json').unlink()
            result = check(repo, out)
            self.assertEqual(result['status'], 'NO_POLICY')
            self.assertIn('eaos policy init', (out / 'POLICY.md').read_text())

    def test_scaffolding_produces_layers_from_the_current_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, out = self.prepared(tmp, violating=False)
            (repo / 'eaos.policy.json').unlink()
            created = init(repo, out)
            self.assertTrue(Path(created['created']).is_file())
            policy, _ = load_policy(repo)
            self.assertTrue(policy['layers'])
            self.assertEqual(policy['rules'], [], 'a scaffold declares structure, never rules nobody agreed to')

    def test_a_rule_without_a_reason_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, out = self.prepared(tmp, violating=False)
            (repo / 'eaos.policy.json').write_text(json.dumps({
                'schema_version': 1, 'layers': {'a': ['**']}, 'rules': [{'deny': {'from': 'a', 'to': 'a'}}]}))
            with self.assertRaisesRegex(ValueError, 'reason'):
                check(repo, out)

    def test_this_repository_satisfies_its_own_declared_policy(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            collect(root, out, SETS)
            result = check(root, out)
            self.assertEqual(result['status'], 'OK', 'the project must obey the layering it declares')
