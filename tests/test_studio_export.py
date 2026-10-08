"""studio/: every section the Studio reads, written from the one model, valid against its contract (NS36.T2)."""
import json
from pathlib import Path
import unittest

from eaos import artifact_contracts
from eaos.studio import export, model
from tests.shared_fixture import Workspace
from tests.test_human_report import report

SECTIONS = ('meta', 'head', 'health', 'cards', 'evidence', 'story', 'docs', 'plans', 'decisions', 'media', 'system', 'paths')
SECTIONS_V2 = ('journeys', 'hidden', 'data_paths', 'infra')          # the v2 maps, written before coverage


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
        self.assertEqual(self.result['written'], [*SECTIONS, *SECTIONS_V2, 'coverage'])
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

    def test_the_version_shown_is_the_installed_eaos(self):
        from eaos import __version__
        self.assertEqual(self.load('manifest')['built']['version'], __version__)
        self.assertEqual(self.load('head')['eaos']['version'], __version__)

    def test_no_arabic_numeral_is_glued_to_a_one_letter_prefix(self):
        import re
        export.export(self.out, 'ar', 'shop')
        head = self.load('head')
        for text in (head['verdict'], head['next']['action']):
            self.assertIsNone(re.search(r'(?:^|\s)[\u0644\u0628\u0643\u0648\u0641]\u0640?\d', text), text)

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
        self.assertEqual(result['written'], [name for name in SECTIONS if name != 'media'] + [*SECTIONS_V2, 'coverage'])
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


class Evidence(unittest.TestCase):
    """NS46.T2: a card says why it matters in both languages; a fact carries the code around its line, never a secret."""

    TEXT = 'import a\n\nconst KEY = "sk_live_123"\nfunction f() {\n  return 1\n}\n'

    def source(self, path):
        return {'src/a.ts': self.TEXT, 'bin.dat': 'x\0y'}.get(path)

    def test_the_code_around_the_line_is_written_with_its_numbers(self):
        code = export.code_excerpt(self.source, 'src/a.ts', 5, 'complexity')
        self.assertEqual(code, {'start': 3, 'line': 5, 'lines': ['const KEY = "sk_live_123"', 'function f() {', '  return 1', '}'], 'hidden': []})
        self.assertEqual(export.code_excerpt(self.source, 'src/a.ts', 1, 'complexity')['lines'][0], 'import a')
        long = export.code_excerpt(lambda path: 'x' * 1000, 'min.js', 1, 'complexity')
        self.assertEqual(len(long['lines'][0]), export.CODE_WIDTH)

    def test_no_code_for_a_secret_a_missing_line_or_a_file_not_read(self):
        self.assertIsNone(export.code_excerpt(self.source, 'src/a.ts', 3, 'secret'))
        self.assertIsNone(export.code_excerpt(self.source, 'src/a.ts', None, 'complexity'))
        self.assertIsNone(export.code_excerpt(self.source, 'src/a.ts', 99, 'complexity'))
        self.assertIsNone(export.code_excerpt(self.source, 'gone.ts', 1, 'complexity'))
        self.assertIsNone(export.code_excerpt(self.source, 'bin.dat', 1, 'complexity'))

    def test_a_line_where_any_fact_found_a_secret_is_hidden_in_every_excerpt(self):
        code = export.code_excerpt(self.source, 'src/a.ts', 4, 'complexity', {('src/a.ts', 3)})
        self.assertEqual(code['hidden'], [3])
        self.assertEqual(code['lines'][code['hidden'][0] - code['start']], '')
        self.assertNotIn('sk_live', ''.join(code['lines']))

    def test_the_evidence_section_hides_secret_lines_and_meets_its_contract(self):
        from unittest import mock
        facts = [{'id': 'F1', 'kind': 'engine_finding', 'location': {'path': 'src/a.ts', 'line': 4}, 'value': {'kind': 'complexity', 'message': 'complex'}},
                 {'id': 'F2', 'kind': 'engine_finding', 'location': {'path': 'src/a.ts'}, 'value': {'kind': 'secret', 'sites': [{'path': 'src/a.ts', 'line': 3}]}}]
        with mock.patch.object(export.indicators, 'facts', return_value=facts):
            rows = {f['id']: f for f in export.evidence('report', {'F1', 'F2'}, self.source)}
        self.assertEqual(rows['F1']['line'], 4)
        self.assertEqual(rows['F1']['code']['hidden'], [3])
        self.assertIsNone(rows['F2']['code'])
        self.assertNotIn('sk_live', json.dumps(rows))
        body = {'schema_version': 1, 'contract': 1, 'facts': list(rows.values())}
        self.assertEqual(artifact_contracts.validate(body, artifact_contracts.contracts()['studio-evidence']), [])

    def test_files_are_read_at_the_scanned_commit_and_never_outside_the_project(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder) / 'p'
            (project / 'src').mkdir(parents=True)
            (Path(folder) / 'outside.txt').write_text('secret', encoding='utf-8')
            (project / 'src/a.ts').write_text('old\n', encoding='utf-8')
            git = lambda *a: subprocess.run(['git', '-C', str(project), *a], check=True, capture_output=True)
            git('init', '-q'); git('add', '.'); git('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'one')
            commit = subprocess.run(['git', '-C', str(project), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
            (project / 'src/a.ts').write_text('new\n', encoding='utf-8')
            self.assertEqual(export.sources(project, commit)('src/a.ts'), 'old\n')
            self.assertEqual(export.sources(project, None)('src/a.ts'), 'new\n')
            self.assertIsNone(export.sources(project, None)('../outside.txt'))
            self.assertIsNone(export.sources(None, None)('src/a.ts'))

    def test_why_a_card_matters_is_written_in_both_languages_from_its_render_key(self):
        why = export.why_of({'impact': 'Code nobody runs is still read.', 'impact_render': {'key': 'dead_code', 'params': {}}})['why']
        self.assertEqual(set(why), {'ar', 'en'})
        self.assertRegex(why['ar'], '[\u0600-\u06FF]')
        self.assertEqual(export.why_of({}), {})


if __name__ == '__main__':
    unittest.main()
