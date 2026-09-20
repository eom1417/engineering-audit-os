"""The model layer: interpretation that must point at facts and can never confirm itself."""
import json
from pathlib import Path
import tempfile
import unittest
from eaos.dossier import assemble
from eaos.semantic import digest_of, errors_in, run

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'


class ScriptedSemanticProvider:
    """A scripted responder, not a live model: it exercises the contract, not the judgement."""

    def __init__(self, builder): self.builder = builder; self.calls = 0; self.last_feedback = None

    def identity(self): return {'kind': 'SCRIPTED_TEST_FIXTURE', 'stage': 'semantic'}

    def complete(self, messages):
        self.calls += 1
        payload = json.loads(messages[1]['content'])
        self.last_feedback = payload['instructions']['feedback']
        return self.builder(payload['instructions']['digest'], self.calls)


def grounded(digest, call):
    fact = digest['components'][0]['fact_id']
    return {'claims': [{'statement': 'The pricing module owns the discount rule for every entry path',
                        'claim_type': 'responsibility', 'fact_ids': [fact],
                        'falsifier': 'A second module applying a different discount without importing this one',
                        'reasoning': 'highest fan-in among pricing files'}],
            'questions': ['Which component owns tax, if any?']}


class SemanticTests(unittest.TestCase):
    def prepared(self, tmp):
        out = Path(tmp) / 'out'
        assemble(FIXTURE, out)
        return out

    def test_a_grounded_interpretation_is_accepted_as_a_hypothesis(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.prepared(tmp)
            result = run(FIXTURE, out, ScriptedSemanticProvider(grounded))
            self.assertEqual(result['claims'], 1)
            claims = json.loads((out / 'dossier.json').read_text())['claims']
            added = next(claim for claim in claims if claim['claim_type'] == 'responsibility')
            self.assertEqual(added['confidence'], 'HYPOTHESIS')
            self.assertEqual(added['method'], ['model_inference'])
            self.assertTrue(added['falsifier'])

    def test_model_inference_can_never_reach_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.prepared(tmp)
            run(FIXTURE, out, ScriptedSemanticProvider(grounded))
            claims = json.loads((out / 'dossier.json').read_text())['claims']
            for claim in claims:
                if claim['method'] == ['model_inference']:
                    self.assertNotEqual(claim['confidence'], 'CONFIRMED')

    def test_an_invented_fact_id_is_rejected_and_fed_back(self):
        def invented(digest, call):
            if call == 1:
                return {'claims': [{'statement': 'Something is wrong somewhere in the system',
                                    'claim_type': 'cause', 'fact_ids': ['FACT-doesnotexist'],
                                    'falsifier': 'evidence to the contrary'}], 'questions': []}
            return grounded(digest, call)
        with tempfile.TemporaryDirectory() as tmp:
            out = self.prepared(tmp)
            provider = ScriptedSemanticProvider(invented)
            run(FIXTURE, out, provider)
            self.assertEqual(provider.calls, 2)
            self.assertTrue(any('unknown fact ids' in message for message in provider.last_feedback))

    def test_a_claim_without_a_falsifier_is_rejected(self):
        self.assertTrue(any('disprove' in problem for problem in errors_in(
            {'claims': [{'statement': 'a statement long enough', 'claim_type': 'cause',
                         'fact_ids': ['FACT-1'], 'falsifier': ''}]}, {'FACT-1'})))

    def test_a_persistently_invalid_response_fails_loudly(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.prepared(tmp)
            broken = ScriptedSemanticProvider(lambda digest, call: {'claims': [{'statement': 'x'}], 'questions': []})
            with self.assertRaisesRegex(ValueError, 'Semantic pass rejected'):
                run(FIXTURE, out, broken)

    def test_the_digest_carries_facts_not_raw_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.prepared(tmp)
            from eaos.facts.store import read_set
            sets = {name: read_set(out, name) for name in ['syntax', 'graph', 'entrypoints', 'domain', 'flows']}
            digest = digest_of(sets, json.loads((out / 'dossier.json').read_text()))
            serialised = json.dumps(digest)
            self.assertIn('components', digest)
            self.assertNotIn('def price_for', serialised, 'the model must not receive raw file contents here')
            self.assertTrue(all(component['fact_id'] for component in digest['components']))

    def test_questions_from_the_model_are_kept_as_questions(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.prepared(tmp)
            run(FIXTURE, out, ScriptedSemanticProvider(grounded))
            dossier = json.loads((out / 'dossier.json').read_text())
            self.assertTrue(any(row['source'] == 'semantic pass' for row in dossier['questions']))
            self.assertIn('الطبقة الدلالية', (out / 'SEMANTIC.md').read_text())
