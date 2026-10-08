"""studio/: every section the Studio reads, written from the one model, valid against its contract (NS36.T2)."""
import json
import unittest

from eaos import artifact_contracts
from eaos.studio import export, model
from tests.shared_fixture import Workspace
from tests.test_human_report import report

SECTIONS = ('meta', 'head', 'health', 'cards', 'evidence', 'story', 'docs', 'plans', 'decisions', 'media')


class Export(Workspace):
    def setUp(self):
        super().setUp()
        self.out = report(self.tmp)
        (self.out / 'START-HERE.md').write_text('# Start here\n\nSix problems.\n', encoding='utf-8')
        self.result = export.export(self.out, 'en', 'shop')
        self.folder = self.out / 'studio'

    def load(self, name):
        return json.loads((self.folder / f'{name}.json').read_text(encoding='utf-8'))

    def test_every_section_and_the_manifest_meet_their_contract(self):
        self.assertEqual(self.result['errors'], [])
        self.assertEqual(self.result['written'], [*SECTIONS, 'coverage'])
        contracts = artifact_contracts.contracts()
        for name in ('manifest', *SECTIONS, 'coverage'):
            self.assertEqual(artifact_contracts.validate(self.load(name), contracts[f'studio-{name}']), [], name)

    def test_the_manifest_fingerprints_what_was_written(self):
        import hashlib
        for entry in self.load('manifest')['sections']:
            blob = (self.folder / entry['file']).read_bytes()
            self.assertEqual(entry['sha256'], hashlib.sha256(blob).hexdigest(), entry['name'])
            self.assertEqual(entry['bytes'], len(blob))

    def test_each_section_has_a_js_twin_for_a_page_opened_from_a_file(self):
        for name in ('manifest', *SECTIONS):
            text = (self.folder / f'{name}.js').read_text(encoding='utf-8')
            prefix = f'(window.EAOS_STUDIO=window.EAOS_STUDIO||{{}})["{name}"]='
            self.assertTrue(text.startswith(prefix), name)
            self.assertEqual(json.loads(text[len(prefix):].rstrip().rstrip(';')), self.load(name))

    def test_the_studio_and_the_report_show_the_same_score(self):
        m = model.records(self.out)
        self.assertEqual(self.load('health')['score']['value'], m['score']['score'] / 100)
        areas = {d['id']: d['score']['value'] for d in self.load('health')['domains']}
        self.assertIsNone(areas['performance'])          # its stage failed: not measured, not zero

    def test_cards_carry_their_state_and_whether_they_need_a_person(self):
        cards = {c['id']: c for c in self.load('cards')['cards']}
        self.assertEqual(len(cards), 6)
        self.assertTrue(cards['TASK-1']['fixable'])
        self.assertTrue(cards['TASK-2']['needs_decision'])
        self.assertEqual({c['state'] for c in cards.values()}, {'open'})

    def test_the_ledger_moves_the_plan_and_the_decisions(self):
        ledger = {'cards': [{'id': 'TASK-1', 'key': 'k1', 'state': 'done'}, {'id': 'TASK-2', 'key': 'k2', 'state': 'open'}]}
        export.export(self.out, 'en', 'shop', progress={'ledger': ledger})
        plan = self.load('plans')['plans'][0]
        self.assertEqual(plan['state'], 'active')
        self.assertAlmostEqual(plan['progress']['value'], 1 / 6, places=3)
        first = plan['steps'][0]
        self.assertEqual(first['state'], 'active')
        self.assertEqual(first['tasks'][0]['state'], 'done')
        decision = self.load('decisions')['decisions'][0]
        self.assertEqual(decision['id'], 'investigations')
        self.assertEqual(set(decision['blocks']), {'TASK-2', 'TASK-6'})

    def test_no_path_outside_the_project_is_written(self):
        self.assertIsNone(export.rel('/etc/passwd'))
        self.assertIsNone(export.rel('../secret'))
        self.assertIsNone(export.rel('~/x'))
        self.assertEqual(export.rel('src/a.ts'), 'src/a.ts')
        text = ''.join((self.folder / f'{n}.json').read_text(encoding='utf-8') for n in SECTIONS)
        self.assertNotIn(self.tmp, text)

    def test_the_documents_are_listed_in_reading_order(self):
        docs = {d['path']: d for d in self.load('docs')['docs']}
        self.assertEqual(docs['START-HERE.md']['group'], 'start')
        self.assertEqual(docs['START-HERE.md']['title'], 'Start here')

    def test_a_section_that_fails_is_named_and_the_rest_is_written(self):
        from unittest import mock
        with mock.patch.object(export, 'media', side_effect=ValueError('no folder')):
            result = export.export(self.out, 'en', 'shop')
        self.assertEqual(result['errors'], [{'section': 'media', 'error': 'ValueError: no folder'}])
        self.assertEqual(result['written'], [name for name in SECTIONS if name != 'media'] + ['coverage'])
        self.assertNotIn('media', {entry['name'] for entry in self.load('manifest')['sections']})
        rows = {row['section']: row for row in self.load('coverage')['sections']}
        self.assertEqual((rows['media']['state'], rows['media']['reason']), ('failed', 'section_error'))

    def test_records_that_cannot_be_read_name_the_failure_and_leave_no_manifest(self):
        from unittest import mock
        with mock.patch.object(model, 'records', side_effect=OSError('disk gone')):
            result = export.export(self.out, 'en', 'shop')
        self.assertEqual(result, {'written': [], 'errors': [{'section': 'records', 'error': 'OSError: disk gone'}]})
        self.assertFalse((self.folder / 'manifest.json').exists())
        self.assertEqual(json.loads((self.folder / 'errors.json').read_text(encoding='utf-8')), result['errors'])

if __name__ == '__main__':
    unittest.main()
