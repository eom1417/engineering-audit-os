"""The same finding across two runs, and two findings that merely read alike."""
import unittest

from eaos import identity


def claim(identifier, uid=None, kind='structure', statement='a thing', paths=(), symbol=None, aliases=()):
    row = {'id': identifier, 'claim_type': kind, 'statement': statement,
           'priority_factors': {'paths': list(paths)}}
    if uid:
        row['uid'] = uid
    if aliases:
        row['aliases'] = list(aliases)
    if symbol:
        row['probe_spec'] = {'probe_type': 'graph_query', 'specification': {'symbol': symbol}}
    return row


class MigrationTests(unittest.TestCase):
    def test_a_stable_uid_matches_across_runs(self):
        result = identity.migrate([claim('CLM-001', uid='u1')], [claim('CLM-009', uid='u1')])
        self.assertEqual(result['matched'], [{'before': 'CLM-001', 'after': 'CLM-009', 'matched_by': 'uid'}])
        self.assertEqual(result['unmatched_before'], [])

    def test_a_recorded_alias_matches_a_changed_uid(self):
        result = identity.migrate([claim('CLM-001', uid='old')],
                                  [claim('CLM-009', uid='new', aliases=['old'])])
        self.assertEqual(result['matched'][0]['matched_by'], 'alias')

    def test_a_renamed_file_follows_its_finding_when_the_rename_is_recorded(self):
        before = [claim('CLM-001', paths=['old/a.py'], symbol='mod.fn')]
        after = [claim('CLM-009', paths=['new/a.py'], symbol='mod.fn')]
        self.assertEqual(identity.migrate(before, after)['unmatched_before'], ['CLM-001'])
        followed = identity.migrate(before, after, renames={'old/a.py': 'new/a.py'})
        self.assertEqual(followed['matched'][0]['matched_by'], 'rename_evidence')

    def test_without_a_recorded_rename_a_move_is_a_new_finding_not_a_guess(self):
        before = [claim('CLM-001', paths=['old/a.py'], symbol='mod.fn')]
        after = [claim('CLM-009', paths=['new/a.py'], symbol='mod.fn')]
        result = identity.migrate(before, after)
        self.assertEqual(result['unmatched_before'], ['CLM-001'])
        self.assertEqual(result['unmatched_after'], ['CLM-009'])

    def test_the_same_symbol_in_the_same_place_matches_without_a_uid(self):
        before = [claim('CLM-001', paths=['a.py'], symbol='mod.fn')]
        after = [claim('CLM-009', paths=['a.py'], symbol='mod.fn')]
        self.assertEqual(identity.migrate(before, after)['matched'][0]['matched_by'], 'symbol_and_path')

    def test_two_findings_of_different_types_never_match(self):
        before = [claim('CLM-001', paths=['a.py'], symbol='mod.fn', kind='risk')]
        after = [claim('CLM-009', paths=['a.py'], symbol='mod.fn', kind='structure')]
        self.assertEqual(identity.migrate(before, after)['unmatched_before'], ['CLM-001'])

    def test_one_claim_is_matched_at_most_once(self):
        before = [claim('CLM-001', paths=['a.py'], symbol='mod.fn'),
                  claim('CLM-002', paths=['a.py'], symbol='mod.fn')]
        after = [claim('CLM-009', paths=['a.py'], symbol='mod.fn')]
        result = identity.migrate(before, after)
        self.assertEqual(len(result['matched']), 1)
        self.assertEqual(result['unmatched_before'], ['CLM-002'])


class LookAlikeTests(unittest.TestCase):
    def test_similar_wording_is_reported_and_never_merged(self):
        rows = identity.look_alikes([claim('CLM-001', uid='a', statement='the rule is defined in two places'),
                                     claim('CLM-002', uid='b', statement='the rule is defined in 2 places')])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['kept_separate_because'], identity.SENTENCE_IS_NOT_EVIDENCE)
        self.assertGreater(rows[0]['similarity'], 0.9)

    def test_similarity_never_appears_as_a_match_reason(self):
        before = [claim('CLM-001', statement='the rule is defined in two places')]
        after = [claim('CLM-009', statement='the rule is defined in 2 places')]
        result = identity.migrate(before, after)
        self.assertEqual(result['matched'], [])
        for pair in result['matched']:
            self.assertNotEqual(pair['matched_by'], identity.SENTENCE_IS_NOT_EVIDENCE)

    def test_two_records_of_one_finding_are_not_reported_as_look_alikes(self):
        rows = identity.look_alikes([claim('CLM-001', uid='same', statement='x y z'),
                                     claim('CLM-002', uid='same', statement='x y z')])
        self.assertEqual(rows, [])
