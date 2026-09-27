"""Code a project archived is reported as archived: never a product defect, never an automatic repair."""
import unittest

from eaos.debt_register import _severity
from eaos.decisions import decide
from eaos.dossier import archived, origin_of

INDEX = {'F1': 'archive/removed-screens/EventEditor.tsx', 'F2': 'app/src/features/rota/Rota.tsx', 'F3': 'app/tests/a.test.mjs'}


class ArchiveOriginTests(unittest.TestCase):
    def test_only_archived_paths_make_an_archived_claim(self):
        self.assertEqual(origin_of({'fact_ids': ['F1']}, INDEX), 'archive')
        self.assertEqual(origin_of({'fact_ids': ['F1', 'F2']}, INDEX), 'source')
        self.assertEqual(origin_of({'fact_ids': ['F3']}, INDEX), 'test')
        self.assertFalse(archived('src/archivedReports.ts'))   # a name, not a folder

    def test_broken_archived_code_is_a_low_leftover_not_a_high_defect(self):
        broken = {'origin': 'archive', 'claim_type': 'risk', 'render': {'key': 'broken_code'}}
        self.assertEqual(_severity(broken, 'broken_code', None, []), 'low')
        self.assertEqual(_severity({**broken, 'origin': 'source'}, 'broken_code', None, []), 'high')

    def test_the_owner_decides_what_happens_to_archived_code(self):
        claim = {'id': 'CLM-001', 'statement': 's', 'confidence': 'CONFIRMED', 'origin': 'archive', 'fact_ids': ['F1']}
        self.assertEqual(decide(claim)['kind'], 'retain')


if __name__ == '__main__':
    unittest.main()
