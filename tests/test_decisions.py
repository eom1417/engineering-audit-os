"""Decision contract: a declared-policy violation must be treatable as a repair."""
import json
from pathlib import Path
import tempfile
import unittest

from eaos.analysis.claims import from_facts
from eaos.core.decisions import check_errors, decide
from eaos.facts.run import collect
from eaos.analysis.policy_assessment import build_assessment
from eaos.analysis.policy import FILENAME as POLICY_FILENAME, check as check_policy

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
        check_policy(repo, out)
        return repo, out

    def _policy_claim(self, claims):
        return next(c for c in claims if (c.get('render') or {}).get('key') == 'policy')

    def _claims(self, tmp, violating):
        repo, out = self._prepared(tmp, violating)
        sets = {'policy': json.loads((out / 'facts/policy.json').read_text()),
                'resolve': json.loads((out / 'facts/resolve.json').read_text())}
        return sets, from_facts(sets, target=repo)

    def test_no_repair_without_a_target_or_a_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            sets, _ = self._claims(tmp, violating=True)
            self.assertIsNone(build_assessment({'render': {'key': 'policy'}, 'fact_ids': [], 'evidence_ids': []}, sets, target=None))
        with tempfile.TemporaryDirectory() as tmp:
            _, claims = self._claims(tmp, violating=False)
            self.assertFalse([c for c in claims if (c.get('render') or {}).get('key') == 'policy'])

    def test_a_violation_becomes_a_ready_repair_with_a_bound_check_and_cited_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            sets, claims = self._claims(tmp, violating=True)
        claim = self._policy_claim(claims)
        decision = decide(claim)
        self.assertEqual((decision['kind'], decision['readiness'], decision['blockers']), ('repair', 'ready', []))
        for check in claim['checks']:
            self.assertEqual(check_errors(check), [], check)
            self.assertEqual((check['expected_exit'], check['cwd']), (0, '.'))
            self.assertTrue(check['argv'])
            self.assertFalse(any(x in {'dossier', 'facts', 'tasks'} for x in check['argv'][:3]),
                             'argv must not be report regeneration: ' + str(check['argv']))
            self.assertTrue(check['source_revision'], 'source_revision must be bound')
        assessment = claim['assessment']
        known = {row['id'] for row in sets['policy']['facts']} | {row['id'] for row in sets['resolve']['facts']}
        self.assertTrue(set(assessment['requirement_refs']) | set(assessment['evidence_refs']) <= known)
        self.assertIn(POLICY_FILENAME, assessment['reviewed_by'])
        for field in ('before', 'after', 'violated_invariant', 'proposed_change'):
            self.assertTrue(assessment[field].strip(), field)

    def test_each_policy_claim_is_assessed_against_its_own_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _policy_repo(tmp, violating=True)
            (repo / 'app/facts/second.py').write_text(
                'from app.runtime.engine import start\n\n\ndef again():\n    return start()\n')
            out = Path(tmp) / 'out'
            collect(repo, out, SETS)
            check_policy(repo, out)
            policy = json.loads((out / 'facts/policy.json').read_text())
            resolve = json.loads((out / 'facts/resolve.json').read_text())
            claims = from_facts({'policy': policy, 'resolve': resolve}, target=repo)
        policy_claims = [c for c in claims if (c.get('render') or {}).get('key') == 'policy']
        self.assertEqual(len(policy_claims), 2)
        for claim in policy_claims:
            self.assertEqual(claim['assessment']['requirement_refs'], claim['fact_ids'])
            self.assertIn(claim['render']['params']['path'], claim['assessment']['before'])
        self.assertEqual(len({c['checks'][0]['id'] for c in policy_claims}), 2)
