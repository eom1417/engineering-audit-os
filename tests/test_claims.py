"""The claim ledger: attribution, falsifiability and an honest bridge from existing records."""
import json
from pathlib import Path
import tempfile
import unittest
from eaos import claims
from eaos.facts.run import collect
from eaos.facts.store import read_set

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'


class ClaimLedgerTests(unittest.TestCase):
    def valid(self, **overrides):
        row = claims.make(1, 'Pricing rules live in two modules that must agree', 'cause', 'HYPOTHESIS',
                          ['model_inference'], ['SRC-1'], 'A single owner for the rule with the second site removed.')
        row.update(overrides)
        return row

    def test_a_well_formed_claim_passes(self):
        self.assertEqual(claims.errors([self.valid()]), [])

    def test_a_claim_without_a_falsifier_is_rejected(self):
        self.assertIn('CLM-001: a claim must state what would disprove it', claims.errors([self.valid(falsifier='  ')]))

    def test_model_inference_alone_can_never_be_confirmed(self):
        problems = claims.errors([self.valid(confidence='CONFIRMED')])
        self.assertTrue(any('CONFIRMED requires' in problem for problem in problems))
        self.assertEqual(claims.errors([self.valid(confidence='CONFIRMED', method=['test_evidence'])]), [])

    def test_a_claim_without_evidence_or_facts_is_rejected(self):
        self.assertTrue(any('no evidence and no fact' in problem for problem in claims.errors([self.valid(evidence_ids=[])])))

    def test_unknown_evidence_reference_is_caught(self):
        self.assertTrue(any('unknown evidence' in problem for problem in claims.errors([self.valid()], evidence_ids={'SRC-other'})))

    def test_duplicate_ids_are_caught(self):
        self.assertTrue(any('duplicate claim id' in problem for problem in claims.errors([self.valid(), self.valid()])))

    def test_accepted_risk_needs_an_owner_and_a_reason(self):
        risky = self.valid(claim_type='risk', disposition={'kind': 'accepted'})
        self.assertTrue(any('accepted risk needs an owner' in problem for problem in claims.errors([risky])))

    def test_saving_an_invalid_ledger_fails_loudly(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'Claim ledger rejected'):
                claims.save(Path(tmp) / 'claims.json', [self.valid(falsifier='')])

    def test_deterministic_facts_become_confirmed_claims_with_refutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'a.py').write_text('from b import helper\n\n\ndef run():\n    return helper()\n')
            (repo / 'b.py').write_text('import a\n\n\ndef helper():\n    return a\n')
            collect(repo, Path(tmp) / 'out', ['syntax', 'resolve', 'entrypoints', 'config', 'metrics', 'graph'])
            sets = {name: read_set(Path(tmp) / 'out', name) for name in ['graph']}
            rows = claims.from_facts(sets)
            self.assertTrue(rows)
            self.assertEqual(rows[0]['confidence'], 'CONFIRMED')
            self.assertEqual(rows[0]['method'], ['static_fact'])
            self.assertTrue(rows[0]['falsifier'])
            self.assertEqual(claims.errors(rows, fact_ids={f['id'] for f in sets['graph']['facts']}), [])

    def test_legacy_records_bridge_without_gaining_certainty(self):
        finding = {'id': 'F-27-001', 'current_behavior': 'Verification can pass with an unplanned file present',
                   'why_this_matters': 'A delivery can be described as verified when it is not',
                   'claim_status': 'confirmed', 'status': 'open', 'evidence_ids': ['SRC-1'], 'affected_components': ['N-1']}
        model = {'nodes': [{'id': 'N-1', 'name': 'remediate', 'responsibility': 'runs checks', 'evidence_ids': ['SRC-1']}],
                 'contracts': [], 'business_rules': []}
        rows = claims.from_legacy([finding], model, [], [])
        self.assertEqual(rows[0]['confidence'], 'LIKELY')
        self.assertEqual(rows[0]['method'], ['model_inference'])
        self.assertTrue(all(row['falsifier'] for row in rows))
        self.assertEqual(claims.errors(rows, evidence_ids={'SRC-1'}), [])
