"""A protocol fixed before the run, or no claim about the result."""
import tempfile
import unittest
from pathlib import Path

from eaos import evaluation_protocol as protocol


def cases(**overrides):
    rows = [{'id': 'C1', 'kind': 'healthy', 'split': 'holdout'},
            {'id': 'C2', 'kind': 'defective', 'split': 'holdout'},
            {'id': 'C3', 'kind': 'ambiguous', 'split': 'development'}]
    for row in rows:
        row.update(overrides)
    return rows


HYPOTHESIS = 'EAOS surfaces the planted defect in more holdout cases than a plain agent does'


class ProtocolTests(unittest.TestCase):
    def test_a_complete_protocol_is_valid(self):
        record = protocol.protocol(HYPOTHESIS, {'detection_rate': 0.6}, cases(),
                                   adjudicator='reviewer', authored_by='author')
        self.assertTrue(record['valid'], record['problems'])
        self.assertTrue(record['independent'])

    def test_a_vague_hypothesis_is_refused(self):
        record = protocol.protocol('it is better', {'detection_rate': 0.6}, cases())
        self.assertIn('state the hypothesis as a sentence that could turn out false', record['problems'])

    def test_thresholds_must_be_numbers_chosen_in_advance(self):
        record = protocol.protocol(HYPOTHESIS, {'detection_rate': 'high'}, cases())
        self.assertTrue(any('decided in advance' in problem for problem in record['problems']))

    def test_a_corpus_without_a_defective_case_proves_nothing(self):
        only_healthy = [{'id': 'C1', 'kind': 'healthy', 'split': 'holdout'}]
        record = protocol.protocol(HYPOTHESIS, {'detection_rate': 0.6}, only_healthy)
        self.assertTrue(any('no defective case' in problem for problem in record['problems']))

    def test_a_corpus_without_a_healthy_case_proves_nothing_either(self):
        only_broken = [{'id': 'C1', 'kind': 'defective', 'split': 'holdout'}]
        record = protocol.protocol(HYPOTHESIS, {'detection_rate': 0.6}, only_broken)
        self.assertTrue(any('no healthy case' in problem for problem in record['problems']))

    def test_a_holdout_case_whose_answers_are_visible_is_not_holdout(self):
        rows = cases()
        rows[0]['answers_visible_to_analyser'] = True
        record = protocol.protocol(HYPOTHESIS, {'detection_rate': 0.6}, rows)
        self.assertTrue(any('not holdout' in problem for problem in record['problems']))

    def test_an_adjudicator_who_wrote_the_answers_is_not_independent(self):
        record = protocol.protocol(HYPOTHESIS, {'detection_rate': 0.6}, cases(),
                                   adjudicator='same', authored_by='same')
        self.assertFalse(record['valid'])
        self.assertTrue(any('not independent' in problem for problem in record['problems']))

    def test_every_arm_is_declared(self):
        self.assertEqual(sorted(protocol.ARMS), ['eaos_with_model', 'facts_only', 'plain_agent'])


class VerdictTests(unittest.TestCase):
    def _record(self, **overrides):
        options = {'adjudicator': 'reviewer', 'authored_by': 'author'}
        options.update(overrides)
        return protocol.protocol(HYPOTHESIS, {'detection_rate': 0.6}, cases(), **options)

    def test_a_result_above_the_declared_threshold_supports_the_hypothesis(self):
        result = protocol.verdict(self._record(), {'detection_rate': 0.8})
        self.assertEqual(result['verdict'], 'supported')

    def test_a_result_below_the_threshold_does_not(self):
        result = protocol.verdict(self._record(), {'detection_rate': 0.4})
        self.assertEqual(result['verdict'], 'not_supported')
        self.assertEqual(result['failed'], ['detection_rate'])

    def test_an_unmeasured_threshold_counts_as_a_failure_not_a_pass(self):
        result = protocol.verdict(self._record(), {})
        self.assertEqual(result['verdict'], 'not_supported')
        self.assertEqual(result['unmeasured'], ['detection_rate'])

    def test_without_an_independent_adjudicator_the_verdict_is_blocked(self):
        result = protocol.verdict(self._record(adjudicator=None), {'detection_rate': 0.9})
        self.assertEqual(result['verdict'], 'blocked')
        self.assertIn('independent', result['reason'])

    def test_an_invalid_protocol_blocks_any_verdict(self):
        record = protocol.protocol('short', {}, [])
        self.assertEqual(protocol.verdict(record, {'detection_rate': 1.0})['verdict'], 'blocked')


class RecordTests(unittest.TestCase):
    def test_a_protocol_can_be_written_and_read_back(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'protocol.json'
            record = protocol.protocol(HYPOTHESIS, {'detection_rate': 0.6}, cases(),
                                       adjudicator='reviewer', authored_by='author')
            protocol.write(path, record)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['hypothesis'], HYPOTHESIS)
