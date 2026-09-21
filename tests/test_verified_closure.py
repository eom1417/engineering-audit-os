"""A case closes only when the checks that closed it are bound to the candidate they ran against."""
import json
import tempfile
import unittest
from pathlib import Path

from eaos import outcomes


def result(**overrides):
    payload = {'project': None, 'changed_paths': ['a.py'], 'patch_complete': True,
               'original_target_unchanged': True,
               'baseline': [{'id': 'G-1', 'phase': 'baseline', 'status': 'pass'}],
               'post_checks': [{'id': 'G-1', 'phase': 'post-change-1', 'status': 'pass'}]}
    payload.update(overrides)
    return payload


class ClosureTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        (Path(self.directory) / 'a.py').write_text('x = 1\n', encoding='utf-8')

    def test_all_checks_passing_closes_the_case(self):
        outcome = outcomes.record('OBS-1', {'kind': 'repair'}, result(project=self.directory))
        self.assertEqual(outcome['closure'], outcomes.RESOLVED)
        self.assertEqual(outcome['blockers'], [])

    def test_a_failing_check_leaves_the_case_open_and_names_it(self):
        failing = result(project=self.directory,
                         post_checks=[{'id': 'G-1', 'phase': 'post-change-1', 'status': 'fail'}])
        outcome = outcomes.record('OBS-1', {'kind': 'repair'}, failing)
        self.assertEqual(outcome['closure'], outcomes.NOT_CLOSED)
        self.assertIn('G-1', outcome['failed_checks'])

    def test_an_incomplete_patch_cannot_close_a_case(self):
        outcome = outcomes.record('OBS-1', {'kind': 'repair'},
                                  result(project=self.directory, patch='p.patch', patch_complete=False))
        self.assertEqual(outcome['closure'], outcomes.NOT_CLOSED)
        self.assertTrue(any('patch' in reason for reason in outcome['blockers']))

    def test_a_changed_original_target_cannot_close_a_case(self):
        outcome = outcomes.record('OBS-1', {'kind': 'repair'},
                                  result(project=self.directory, original_target_unchanged=False))
        self.assertEqual(outcome['closure'], outcomes.NOT_CLOSED)
        self.assertTrue(any('original target' in reason for reason in outcome['blockers']))

    def test_no_checks_at_all_is_not_a_pass(self):
        outcome = outcomes.record('OBS-1', {'kind': 'repair'},
                                  result(project=self.directory, baseline=[], post_checks=[]))
        self.assertEqual(outcome['closure'], outcomes.NOT_CLOSED)
        self.assertIn('no check was executed, so nothing was verified', outcome['blockers'])

    def test_a_required_human_review_holds_the_case_open(self):
        decision = {'kind': 'repair', 'requires_human_review': True}
        outcome = outcomes.record('OBS-1', decision, result(project=self.directory))
        self.assertEqual(outcome['closure'], outcomes.NOT_CLOSED)
        reviewed = outcomes.record('OBS-1', decision, result(project=self.directory), reviewed_by='a.engineer')
        self.assertEqual(reviewed['closure'], outcomes.RESOLVED)

    def test_the_outcome_is_bound_to_the_candidate_it_ran_against(self):
        first = outcomes.record('OBS-1', {'kind': 'repair'}, result(project=self.directory))
        (Path(self.directory) / 'a.py').write_text('x = 2\n', encoding='utf-8')
        second = outcomes.record('OBS-1', {'kind': 'repair'}, result(project=self.directory))
        self.assertNotEqual(first['candidate']['digest'], second['candidate']['digest'],
                            'the same digest for two different candidates would let one pass vouch for another')

    def test_the_outcome_records_the_tools_and_scope_it_was_measured_under(self):
        outcome = outcomes.record('OBS-1', {'kind': 'repair'}, result(project=self.directory),
                                  tools={'eaos': '3.0.0'}, scope={'exclude': 'tests/fixtures'})
        self.assertEqual(outcome['tools'], {'eaos': '3.0.0'})
        self.assertEqual(outcome['scope'], {'exclude': 'tests/fixtures'})

    def test_writing_an_outcome_replaces_the_previous_one_for_that_case(self):
        with tempfile.TemporaryDirectory() as out:
            outcomes.write(out, outcomes.record('OBS-1', {'kind': 'repair'}, result(project=self.directory)))
            outcomes.write(out, outcomes.record('OBS-1', {'kind': 'repair'}, result(project=self.directory)))
            outcomes.write(out, outcomes.record('OBS-2', {'kind': 'repair'}, result(project=self.directory)))
            payload = json.loads((Path(out) / 'outcomes.json').read_text(encoding='utf-8'))
        self.assertEqual([row['case_id'] for row in payload['outcomes']], ['OBS-1', 'OBS-2'])


class DisappearanceTests(unittest.TestCase):
    """A finding that stops appearing has four possible reasons and only one of them is a fix."""

    def _claim(self, uid='obs-1'):
        return {'id': 'CLM-001', 'claim_type': 'structure', 'uid': uid, 'statement': 'a thing'}

    def test_a_changed_scope_is_not_a_repair(self):
        self.assertEqual(outcomes.disappearance(self._claim(), [], 'scope_changed', []), 'scope_changed')

    def test_an_ambiguous_identity_is_not_a_repair(self):
        from eaos.delta import key_of
        claim = self._claim()
        self.assertEqual(outcomes.disappearance(claim, [], 'comparable', [key_of(claim)]), 'ambiguous_identity')

    def test_without_an_outcome_a_disappearance_is_only_unobserved(self):
        self.assertEqual(outcomes.disappearance(self._claim(), [], 'comparable', []), 'unobserved')

    def test_only_a_resolved_outcome_for_that_case_reads_as_healed(self):
        claim = self._claim()
        closed = {'case_id': 'obs-1', 'closure': outcomes.RESOLVED}
        self.assertEqual(outcomes.disappearance(claim, [], 'comparable', [], closed), 'healed')
        other = {'case_id': 'obs-9', 'closure': outcomes.RESOLVED}
        self.assertEqual(outcomes.disappearance(claim, [], 'comparable', [], other), 'unobserved')
        open_case = {'case_id': 'obs-1', 'closure': outcomes.NOT_CLOSED}
        self.assertEqual(outcomes.disappearance(claim, [], 'comparable', [], open_case), 'unobserved')

    def test_every_reason_is_declared(self):
        self.assertEqual(sorted(outcomes.DISAPPEARANCE),
                         ['ambiguous_identity', 'healed', 'scope_changed', 'unobserved'])


class DeltaSeparationTests(unittest.TestCase):
    """delta must not promote a disappearance into a resolution on its own."""

    def test_the_comparison_never_reports_a_claim_as_resolved_by_itself(self):
        from eaos.delta import compare
        before = {'claims': [{'id': 'CLM-001', 'claim_type': 'structure', 'uid': 'a',
                              'statement': 'x', 'confidence': 'CONFIRMED'}], 'coverage': {}}
        after = {'claims': [], 'coverage': {}}
        result = compare(before, after)
        self.assertEqual(result['resolved_claims'], [])
        self.assertEqual(len(result['unobserved_claims']), 1)
