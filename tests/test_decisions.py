"""Decision contract: a declared-policy violation must be treatable as a repair."""
import json
from pathlib import Path
import tempfile
import unittest

from eaos import cli
from eaos.claims import from_facts
from eaos.decisions import check_errors, decide
from eaos.facts.run import collect
from eaos.policy_assessment import build_assessment
from eaos.policy import FILENAME as POLICY_FILENAME

SETS = ['syntax', 'resolve', 'entrypoints', 'config', 'metrics', 'domain', 'history', 'graph', 'flows']


def _policy_repo(root, violating):
    repo = Path(root) / 'repo'
    (repo / 'app/facts').mkdir(parents=True)
    (repo / 'app/runtime').mkdir(parents=True)
    (repo / 'app/facts/__init__.py').write_text('')
    (repo / 'app/runtime/__init__.py').write_text('')
    (repo / 'app/runtime/engine.py').write_text('def start():\n    return 1\n')
    body = ('from app.runtime.engine import start\n\n\ndef collect():\n    return start()\n'
            if violating else 'def collect():\n    return 1\n')
    (repo / 'app/facts/reader.py').write_text(body)
    (repo / 'app/__init__.py').write_text('')
    (repo / POLICY_FILENAME).write_text(json.dumps({
        'schema_version': 1,
        'layers': {'facts': ['app/facts/**'], 'runtime': ['app/runtime/**'], 'core': ['app/__init__.py']},
        'rules': [{'deny': {'from': 'facts', 'to': 'runtime'},
                   'reason': 'the deterministic layer must run without the model path'}]}))
    return repo


class PolicyAssessmentTests(unittest.TestCase):
    """The only claim class that ships a project-authored requirement must be a real repair."""

    def _prepared(self, tmp, violating):
        repo = _policy_repo(tmp, violating)
        out = Path(tmp) / 'out'
        collect(repo, out, SETS)
        from eaos.policy import check as check_policy
        check_policy(repo, out)
        return repo, out

    def _policy_claim(self, claims):
        return next(c for c in claims if (c.get('render') or {}).get('key') == 'policy')

    def test_build_assessment_returns_none_without_a_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, out = self._prepared(tmp, violating=True)
            policy = json.loads((out / 'facts/policy.json').read_text())
            resolve = json.loads((out / 'facts/resolve.json').read_text())
            sets = {'policy': policy, 'resolve': resolve}
            claim = {'render': {'key': 'policy'}, 'fact_ids': [], 'evidence_ids': []}
            self.assertIsNone(build_assessment(claim, sets, target=None))

    def test_build_assessment_produces_a_decide_ready_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, out = self._prepared(tmp, violating=True)
            policy = json.loads((out / 'facts/policy.json').read_text())
            resolve = json.loads((out / 'facts/resolve.json').read_text())
            sets = {'policy': policy, 'resolve': resolve}
            claims = from_facts(sets, target=repo)
            claim = self._policy_claim(claims)
            self.assertIn('assessment', claim, 'assessment must be attached to policy claim')
            self.assertIn('checks', claim, 'checks must be attached to policy claim')
            decision = decide(claim)
            self.assertEqual(decision['kind'], 'repair')
            self.assertEqual(decision['readiness'], 'ready')
            self.assertFalse(decision['blockers'], decision['blockers'])

    def test_each_check_satisfies_check_errors_and_carries_a_real_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, out = self._prepared(tmp, violating=True)
            policy = json.loads((out / 'facts/policy.json').read_text())
            resolve = json.loads((out / 'facts/resolve.json').read_text())
            sets = {'policy': policy, 'resolve': resolve}
            claims = from_facts(sets, target=repo)
            claim = self._policy_claim(claims)
            for check in claim['checks']:
                self.assertEqual(check_errors(check), [], check)
                self.assertEqual(check['expected_exit'], 0)
                self.assertEqual(check['cwd'], '.')
                argv = check['argv']
                self.assertTrue(argv)
                self.assertFalse(any(x in {'dossier', 'facts', 'tasks'} for x in argv[:3]),
                                'argv must not be report regeneration: ' + str(argv))
                self.assertTrue(check['source_revision'], 'source_revision must be bound')

    def test_assessment_cites_known_facts_for_requirement_and_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, out = self._prepared(tmp, violating=True)
            policy = json.loads((out / 'facts/policy.json').read_text())
            resolve = json.loads((out / 'facts/resolve.json').read_text())
            sets = {'policy': policy, 'resolve': resolve}
            claims = from_facts(sets, target=repo)
            claim = self._policy_claim(claims)
            assessment = claim['assessment']
            known = {row['id'] for row in policy['facts']} | {row['id'] for row in resolve['facts']}
            for ref in assessment['requirement_refs']:
                self.assertIn(ref, known, 'requirement_refs must cite a known fact: ' + ref)
            for ref in assessment['evidence_refs']:
                self.assertIn(ref, known, 'evidence_refs must cite a known fact: ' + ref)
            self.assertTrue(assessment['reviewed_by'].strip(), 'reviewed_by is the policy file itself')
            self.assertIn(POLICY_FILENAME, assessment['reviewed_by'])
            self.assertTrue(assessment['before'].strip())
            self.assertTrue(assessment['after'].strip())
            self.assertTrue(assessment['violated_invariant'].strip())
            self.assertTrue(assessment['proposed_change'].strip())

    def test_a_clean_project_does_not_get_a_repair_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, out = self._prepared(tmp, violating=False)
            policy = json.loads((out / 'facts/policy.json').read_text())
            resolve = json.loads((out / 'facts/resolve.json').read_text())
            sets = {'policy': policy, 'resolve': resolve}
            claims = from_facts(sets, target=repo)
            for claim in claims:
                if (claim.get('render') or {}).get('key') == 'policy':
                    self.fail('a clean project must not produce a policy claim')
