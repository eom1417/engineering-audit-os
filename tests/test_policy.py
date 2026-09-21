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
        'layers': {'facts': ['app/facts/**'], 'runtime': ['app/runtime/**'], 'core': ['app/__init__.py']},
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
            self.assertEqual(result['unclassified_count'], 0)

    def test_a_policy_that_leaves_files_uncovered_is_incomplete_not_clean(self):
        """A file outside every layer is unchecked; reporting OK would call unexamined code safe."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, out = self.prepared(tmp, violating=False)
            policy = json.loads((repo / 'eaos.policy.json').read_text())
            del policy['layers']['core']
            (repo / 'eaos.policy.json').write_text(json.dumps(policy))
            result = check(repo, out)
            self.assertEqual(result['status'], 'INCOMPLETE')
            self.assertEqual(result['violations'], 0)
            self.assertEqual(result['unclassified_count'], 1)
            self.assertIn('app/__init__.py', (out / 'POLICY.md').read_text(encoding='utf-8'))

    def test_a_violation_outranks_an_incomplete_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, out = self.prepared(tmp, violating=True)
            policy = json.loads((repo / 'eaos.policy.json').read_text())
            del policy['layers']['core']
            (repo / 'eaos.policy.json').write_text(json.dumps(policy))
            self.assertEqual(check(repo, out)['status'], 'VIOLATED')

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

    def test_declared_exclusions_are_honoured_without_a_flag(self):
        from eaos.dossier import assemble
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.repo_with(tmp, ['samples'])
            assemble(repo, Path(tmp) / 'out')
            dossier = json.loads((Path(tmp) / 'out/dossier.json').read_text())
            self.assertIn('samples', dossier['provenance']['excluded_patterns'])
            self.assertEqual([c for c in dossier['claims'] if 'RATE' in c['statement']], [])

    def test_without_a_declaration_nothing_is_excluded_silently(self):
        from eaos.dossier import assemble
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.repo_with(tmp, None)
            assemble(repo, Path(tmp) / 'out')
            dossier = json.loads((Path(tmp) / 'out/dossier.json').read_text())
            self.assertEqual(dossier['provenance']['excluded_patterns'], [])
            self.assertTrue([c for c in dossier['claims'] if 'RATE' in c['statement']])

    def test_a_malformed_exclusion_list_is_rejected(self):
        from eaos.policy import declared_exclusions
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.repo_with(tmp, None)
            policy = json.loads((repo / 'eaos.policy.json').read_text())
            policy['analysis'] = {'exclude': 'tests'}
            (repo / 'eaos.policy.json').write_text(json.dumps(policy))
            with self.assertRaisesRegex(ValueError, 'analysis.exclude'):
                declared_exclusions(repo)
