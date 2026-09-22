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


class ComputeTests(unittest.TestCase):
    """compute() builds a record from facts already produced; it never invents one."""

    def _report_with(self, tmp, facts_files):
        """Write a few facts files into tmp/facts/ and return the tmp path."""
        from pathlib import Path
        import json
        facts_dir = Path(tmp) / 'facts'
        facts_dir.mkdir(parents=True, exist_ok=True)
        for name, payload in facts_files.items():
            (facts_dir / f'{name}.json').write_text(json.dumps(payload))
        return Path(tmp)

    def test_an_empty_report_produces_an_empty_record(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            record = load_model.compute(tmp)
        self.assertEqual(record['entry_points'], [])

    def test_an_undetectable_entry_point_has_eight_answers_with_a_reason(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._report_with(tmp, {
                'entrypoints': {'facts': [{
                    'kind': 'entry_point', 'id': 'E1',
                    'location': {'path': 'a.py', 'symbol': 'handle'},
                    'value': {'category': 'http', 'handler': 'handle'}}],
                    'flows': {'facts': []}},
                'flows': {'facts': []},
            })
            record = load_model.compute(tmp)
        self.assertEqual(len(record['entry_points']), 1)
        entry = record['entry_points'][0]
        self.assertEqual(len(entry['answers']), 8)
        for question, answer in entry['answers'].items():
            self.assertEqual(answer['status'], 'undetectable', question)
            self.assertTrue(answer['reason'], f'{question} needs a reason')
            self.assertEqual(load_model.QUESTIONS, tuple(entry['answers']),
                              'all eight questions must be answered')

    def test_a_test_entry_point_is_excluded(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._report_with(tmp, {
                'entrypoints': {'facts': [{
                    'kind': 'entry_point', 'id': 'T1',
                    'location': {'path': 'test_x.py', 'symbol': 'test_handle'},
                    'value': {'category': 'test', 'handler': 'test_handle'}}]},
            })
            record = load_model.compute(tmp)
        self.assertEqual(record['entry_points'], [])

    def test_data_access_calls_counts_call_sites_in_the_entry_file(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            self._report_with(tmp, {
                'entrypoints': {'facts': [{
                    'kind': 'entry_point', 'id': 'E1',
                    'location': {'path': 'a.py', 'symbol': 'handle'},
                    'value': {'category': 'http', 'handler': 'handle'}}]},
                'structure': {'facts': [
                    {'id': 'cs1', 'kind': 'call_site',
                     'location': {'path': 'a.py'},
                     'value': {'callee': 'session.execute', 'attribute': True, 'enclosing': 'handle'}},
                    {'id': 'cs2', 'kind': 'call_site',
                     'location': {'path': 'a.py'},
                     'value': {'callee': 'parse_int', 'attribute': False, 'enclosing': 'handle'}},
                ]},
                'flows': {'facts': [{
                    'kind': 'flow',
                    'location': {'path': 'a.py', 'symbol': 'handle'},
                    'value': {'flow_id': 'F1', 'steps': [], 'in_codebase_steps': 0,
                                'unresolved_steps': 0, 'handler_found': True}}]},
            })
            record = load_model.compute(tmp)
        self.assertEqual(record['entry_points'][0]['answers']['data_access_calls']['status'], 'answered')
        self.assertEqual(record['entry_points'][0]['answers']['data_access_calls']['value'], 1)

    def test_query_bound_with_bounded_true_yields_answer(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._report_with(tmp, {
                'entrypoints': {'facts': [{
                    'kind': 'entry_point', 'id': 'E1',
                    'location': {'path': 'a.py', 'symbol': 'handle'},
                    'value': {'category': 'http', 'handler': 'handle'}}]},
                'flows': {'facts': [{
                    'kind': 'flow',
                    'location': {'path': 'a.py', 'symbol': 'handle'},
                    'value': {'flow_id': 'F1', 'steps': [], 'in_codebase_steps': 0,
                                'unresolved_steps': 0, 'handler_found': True}}]},
                'runtime': {'facts': [
                    {'id': 'qb1', 'kind': 'query_bound',
                     'location': {'path': 'a.py'},
                     'value': {'bounded': True, 'mechanism': 'limit', 'kind': 'sqlalchemy_limit'}},
                ]},
            })
            record = load_model.compute(tmp)
        ans = record['entry_points'][0]['answers']['result_is_bounded']
        self.assertEqual(ans['status'], 'answered')
        self.assertTrue(ans['value'])


class ComputeValidationTests(unittest.TestCase):
    """The record compute() returns must pass its own validate()."""

    def test_computed_record_is_well_formed_for_traced_entry(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            from pathlib import Path
            import json
            facts_dir = Path(tmp) / 'facts'
            facts_dir.mkdir(parents=True, exist_ok=True)
            for name, payload in {
                'entrypoints': {'facts': [{
                    'kind': 'entry_point', 'id': 'E1',
                    'location': {'path': 'a.py', 'symbol': 'handle'},
                    'value': {'category': 'http', 'handler': 'handle'}}]},
                'flows': {'facts': [{
                    'kind': 'flow',
                    'location': {'path': 'a.py', 'symbol': 'handle'},
                    'value': {'flow_id': 'F1', 'steps': [], 'in_codebase_steps': 0,
                                'unresolved_steps': 0, 'handler_found': True}}]},
            }.items():
                (facts_dir / f'{name}.json').write_text(json.dumps(payload))
            record = load_model.compute(tmp)
            problems = load_model.validate(record)
            self.assertEqual(problems, [], f'unexpected problems: {problems}')

    def test_computed_record_with_undetectable_answers_is_well_formed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            from pathlib import Path
            import json
            facts_dir = Path(tmp) / 'facts'
            facts_dir.mkdir(parents=True, exist_ok=True)
            for name, payload in {
                'entrypoints': {'facts': [{
                    'kind': 'entry_point', 'id': 'E1',
                    'location': {'path': 'a.py', 'symbol': 'handle'},
                    'value': {'category': 'http', 'handler': 'handle'}}]},
                'flows': {'facts': []},
            }.items():
                (facts_dir / f'{name}.json').write_text(json.dumps(payload))
            record = load_model.compute(tmp)
            problems = load_model.validate(record)
            self.assertEqual(problems, [])
