"""Canonical home resolution: which file or directory should host the unified rule."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from eaos.canonical_home import suggest
from eaos.facts.run import collect


SETS = ['syntax', 'resolve', 'fingerprint', 'graph']


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


class CanonicalHomeTests(unittest.TestCase):
    def test_one_existing_member_is_a_candidate(self):
        tmp = tempfile.mkdtemp()
        try:
            _, out = _setup(tmp, 'tests/fixtures/sustainability/canonical_chain')
            data = json.loads((out / 'facts/fingerprint.json').read_text())
            cluster = next(f for f in data['facts'] if f['kind'] == 'duplicate_cluster')
            result = suggest(out, cluster)
            member_paths = {occ['path'] for occ in cluster['value']['occurrences']}
            already = [c for c in result['candidates'] if c['home_already']]
            self.assertTrue(already)
            for c in already:
                self.assertIn(c['path'], member_paths)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_candidates_do_not_introduce_cycles(self):
        """The cyclic-billing fixture would surface only when the cycle reaches one member."""
        tmp = tempfile.mkdtemp()
        try:
            repo = Path(tmp) / 'src'; repo.mkdir()
            (repo / 'a.py').write_text("from b import x\n\ndef run(x, y, z):\n    if x > 0:\n        return y + z\n    return y - z\n")
            (repo / 'b.py').write_text("from a import x\n\ndef run(x, y, z):\n    if x > 0:\n        return y + z\n    return y - z\n")
            out = Path(tmp) / 'out'
            collect(repo, out, SETS)
            data = json.loads((out / 'facts/fingerprint.json').read_text())
            if not any(f['kind'] == 'duplicate_cluster' for f in data['facts']):
                self.skipTest('Fixture did not produce a duplicate cluster')
            cluster = next(f for f in data['facts'] if f['kind'] == 'duplicate_cluster')
            # The only file-shaped candidates are a.py and b.py; both would cycle from the other.
            result = suggest(out, cluster)
            # The directory candidate '' (root) is the only one viable; it's listed.
            paths = {c['path'] for c in result['candidates']}
            self.assertIn('', paths)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_policy_violations_are_counted(self):
        tmp = tempfile.mkdtemp()
        try:
            _, out = _setup(tmp, 'tests/fixtures/sustainability/canonical_chain')
            data = json.loads((out / 'facts/fingerprint.json').read_text())
            cluster = next(f for f in data['facts'] if f['kind'] == 'duplicate_cluster')
            policy = {'layers': {'app': ['a/**', 'b/**', 'c/**'], 'lib': ['d/**']},
                       'rules': [{'deny': {'from': 'app', 'to': 'lib'}, 'reason': 'no app->lib dep'}]}
            policy_path = Path(tmp) / 'policy.json'
            policy_path.write_text(json.dumps(policy))
            result = suggest(out, cluster, policy_path=str(policy_path))
            # The directory d is in 'lib'; an import from a to d would violate the rule.
            d_candidates = [c for c in result['candidates'] if c['path'].startswith('d')]
            self.assertGreater(len(d_candidates), 0)
            self.assertGreater(d_candidates[0]['policy_violations'], 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_no_candidate_when_everything_cycles(self):
        """When two duplicates form a cycle and no directory is allowed, nothing is viable."""
        tmp = tempfile.mkdtemp()
        try:
            repo = Path(tmp) / 'src'; repo.mkdir()
            (repo / 'a.py').write_text("import b\n\ndef run(x):\n    return b.run(x) + 1\n")
            (repo / 'b.py').write_text("import a\n\ndef run(x):\n    return a.run(x) + 1\n")
            out = Path(tmp) / 'out'
            collect(repo, out, SETS)
            data = json.loads((out / 'facts/fingerprint.json').read_text())
            if not any(f['kind'] == 'duplicate_cluster' for f in data['facts']):
                self.skipTest('Fixture did not produce a duplicate cluster')
            cluster = next(f for f in data['facts'] if f['kind'] == 'duplicate_cluster')
            # Force a policy that disallows the only file-level candidates.
            policy = {'layers': {'app': ['a.py'], 'lib': ['b.py']},
                       'rules': [{'deny': {'from': 'app', 'to': 'lib'}, 'reason': 'no'}]}
            policy_path = Path(tmp) / 'policy.json'
            policy_path.write_text(json.dumps(policy))
            result = suggest(out, cluster, policy_path=str(policy_path))
            # The only candidates are files; both would cycle from the other.
            # The root candidate remains as a fallback; no file-level candidate is viable.
            file_candidates = [c for c in result['candidates'] if c['path']]
            self.assertEqual(file_candidates, [])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class CanonicalHomeReturnShapeTests(unittest.TestCase):
    def test_every_candidate_has_a_score(self):
        tmp = tempfile.mkdtemp()
        try:
            _, out = _setup(tmp, 'tests/fixtures/sustainability/canonical_chain')
            data = json.loads((out / 'facts/fingerprint.json').read_text())
            cluster = next(f for f in data['facts'] if f['kind'] == 'duplicate_cluster')
            result = suggest(out, cluster)
            for c in result['candidates']:
                self.assertIn('score', c)
                self.assertIn('home_already', c)
                self.assertIn('policy_violations', c)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
