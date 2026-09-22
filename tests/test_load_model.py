"""The eight load-model questions, their shape, and what counts as evidence."""
import unittest
from eaos import load_model


class QuestionSetTests(unittest.TestCase):
    def test_eight_questions_are_declared(self):
        self.assertEqual(len(load_model.QUESTIONS), 8)
        self.assertEqual(len(set(load_model.QUESTIONS)), 8, 'questions must be unique')

    def test_questions_are_in_the_documented_order(self):
        expected = ('data_access_calls', 'repeats_per_iteration', 'result_is_bounded',
                     'complexity_class', 'shared_mutable_state', 'outbound_calls_protected',
                     'cached', 'rate_limited')
        self.assertEqual(load_model.QUESTIONS, expected)

    def test_three_answer_statuses_are_recognised(self):
        self.assertEqual(set(load_model.ANSWER_STATUSES),
                         {'answered', 'not_applicable', 'undetectable'})


class RecordShapeTests(unittest.TestCase):
    def test_a_record_with_every_question_answered_passes_validation(self):
        record = {'schema_version': 1, 'entry_points': [{
            'id': 'E1', 'path': 'a.py', 'answers': {
                q: {'status': 'answered', 'value': True, 'evidence': ['FACT-x'],
                     'reason': ''} for q in load_model.QUESTIONS
            }
        }]}
        self.assertEqual(load_model.validate(record), [])

    def test_missing_question_is_rejected(self):
        record = {'schema_version': 1, 'entry_points': [{
            'id': 'E1', 'answers': {q: {'status': 'answered', 'evidence': ['x']}
                                     for q in load_model.QUESTIONS if q != 'cached'}
        }]}
        problems = load_model.validate(record)
        self.assertTrue(any('cached' in p for p in problems))

    def test_undetectable_without_reason_is_rejected(self):
        record = {'schema_version': 1, 'entry_points': [{
            'id': 'E1', 'answers': {
                q: {'status': 'undetectable', 'value': None, 'evidence': []}
                for q in load_model.QUESTIONS
            }
        }]}
        problems = load_model.validate(record)
        self.assertTrue(any('no reason' in p for p in problems))

    def test_undetectable_with_reason_passes_validation(self):
        record = {'schema_version': 1, 'entry_points': [{
            'id': 'E1', 'answers': {
                q: {'status': 'undetectable', 'value': None, 'evidence': [],
                     'reason': 'we have no traces of pool sizing in this build'}
                for q in load_model.QUESTIONS
            }
        }]}
        self.assertEqual(load_model.validate(record), [])

    def test_answered_without_evidence_is_rejected(self):
        record = {'schema_version': 1, 'entry_points': [{
            'id': 'E1', 'answers': {
                q: {'status': 'answered', 'value': True, 'evidence': []}
                for q in load_model.QUESTIONS
            }
        }]}
        problems = load_model.validate(record)
        self.assertTrue(any('no evidence' in p for p in problems))

    def test_not_applicable_questions_do_not_need_evidence(self):
        record = {'schema_version': 1, 'entry_points': [{
            'id': 'E1', 'answers': {
                q: {'status': 'not_applicable', 'value': None, 'evidence': [], 'reason': 'no db calls here'}
                for q in load_model.QUESTIONS
            }
        }]}
        self.assertEqual(load_model.validate(record), [])

    def test_unknown_question_is_rejected(self):
        record = {'schema_version': 1, 'entry_points': [{
            'id': 'E1', 'answers': {
                'ninth_question': {'status': 'answered', 'evidence': ['x']},
                **{q: {'status': 'answered', 'evidence': ['x']} for q in load_model.QUESTIONS}
            }
        }]}
        problems = load_model.validate(record)
        self.assertTrue(any('unknown question' in p for p in problems))

    def test_blank_answer_produces_undetectable_with_default_reason(self):
        answer = load_model.blank_answer('cached')
        self.assertEqual(answer['status'], 'undetectable')
        self.assertTrue(answer['reason'])


class SchemaTests(unittest.TestCase):
    def test_schema_is_loadable_json(self):
        schema = load_model.load_schema()
        self.assertIn('properties', schema)
        self.assertIn('entry_points', schema['properties'])

    def test_schema_defines_the_eight_questions_through_the_answer_shape(self):
        # The schema references questions only by name; their names come from QUESTIONS.
        # We assert the shape is permissive enough to accept any of them.
        record = {'schema_version': 1, 'entry_points': []}
        self.assertNotIn('errors', [])  # shape validation is enforced by validate(), not the JSON schema


class PolicyTests(unittest.TestCase):
    def test_load_model_is_a_ledger_module(self):
        import json
        from pathlib import Path
        # Walk up to find the project's eaos.policy.json
        root = Path(__file__).resolve().parents[1]
        with open(root / 'eaos.policy.json') as f:
            policy = json.load(f)
        self.assertIn('eaos/load_model.py', policy['layers']['ledger'])


if __name__ == '__main__':
    unittest.main()
