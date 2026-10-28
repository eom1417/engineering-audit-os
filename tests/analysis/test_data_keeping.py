"""How the data is saved and kept (M14), sorted into cards: from the code, and from what the running copy showed."""
import json
import unittest
from pathlib import Path

from eaos.analysis.assessments import data_keeping
from eaos.analysis.claims import from_keeping
from eaos.engines.code import ast_grep
from eaos.facts.run import collect, read_available
from shared_fixture import scratch

BASELINE = Path(__file__).resolve().parents[1] / 'fixtures/baseline-app'
COPY = {'database': {'kind': 'postgres', 'tables': {'orders': 300}},
        'writes': [{'page': '/', 'path': '/api/state', 'method': 'POST', 'bytes': 900, 'kind': 'resends', 'read': '/api/report', 'records': 3}],
        'writes_before': {'pages': 2},
        'stored': {'columns': [{'table': 'brands', 'column': 'logo', 'type': 'text', 'rows': 30, 'average': 3000, 'largest': 3100, 'images': 30},
                               {'table': 'orders', 'column': 'note', 'type': 'text', 'rows': 30, 'average': 40, 'largest': 90, 'images': 0}],
                   'shared': []},
        'restore': {'how': 'project', 'source': 'scripts/backup.sh', 'tables': [], 'missing': ['notes'], 'differ': []},
        'files': [{'path': 'state.json', 'bytes': 900}],
        'lost_update': [{'route': '/api/notes/:id', 'lost': True, 'steps': []}, {'route': '/api/tags/:id', 'lost': False}]}


class FromTheCopy(unittest.TestCase):
    def test_what_the_copy_showed_is_one_confirmed_card_each_in_both_languages(self):
        out = Path(scratch('eaos-keeping-out-'))
        (out / 'live').mkdir()
        (out / 'live/keeping.json').write_text(json.dumps(COPY), encoding='utf-8')
        claims = from_keeping.keeping_claims(out, {}, None, 0)
        kinds = sorted(c['render']['params']['kind'] for c in claims)
        self.assertEqual(kinds, ['lost_update', 'pictures_in_rows', 'restore_misses', 'save_resends', 'two_places'])
        self.assertTrue(all(c['confidence'] == 'CONFIRMED' for c in claims))
        lost = next(c for c in claims if c['render']['params']['kind'] == 'lost_update')['render']['params']
        self.assertEqual(lost['severity'], 'high'); self.assertIn('يضيع تعديل', lost['ar'])

    def test_what_was_not_measured_is_said(self):
        self.assertEqual(data_keeping.unmeasured({'database': {'why': 'no database of its own'}, 'writes_before': {'pages': 1}}),
                         ['no database of its own'])
        self.assertIn('did not run', data_keeping.unmeasured(None)[0])


class FromTheCode(unittest.TestCase):
    def test_the_baseline_s_saves_pictures_and_backup_are_found_and_what_must_stay_is_left(self):
        if ast_grep.version() != ast_grep.PINNED: self.skipTest('ast-grep is not installed at its pin')
        out = Path(scratch('eaos-keeping-facts-'))
        collect(BASELINE, out, ['syntax'], engines=['ast-grep'])
        found, _ = data_keeping.findings(out, read_available(out), BASELINE)
        kinds = {(f['kind'], f['place']) for f in found}
        self.assertTrue({('whole_state_local', 'web/save.js'), ('whole_state_request', 'web/save.js'), ('growing_queue', 'web/save.js'),
                         ('told_early', 'web/save.js'), ('pictures_in_sql', 'supabase/migrations/20261028000000_brands.sql'),
                         ('backup_skips', 'scripts/backup.sh')} <= kinds, kinds)
        self.assertEqual(len([f for f in found if f['place'] == 'web/save.js']), 4)        # not the theme, not the order


if __name__ == '__main__':
    unittest.main()
