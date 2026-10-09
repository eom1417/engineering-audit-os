"""Contract v2 of the Studio (docs/STUDIO.md D7, NS46.T1): additive sections, their fixtures, and the coverage section."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from eaos import artifact_contracts
from eaos.studio import coverage, export
from tests.shared_fixture import Workspace
from tests.test_human_report import report

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import studio_synthetic  # noqa: E402

V1 = ('meta', 'head', 'health', 'cards', 'evidence', 'story', 'docs', 'plans', 'decisions', 'media')
V2 = ('functions', 'screens', 'gaps', 'operations', 'history', 'quality', 'paths', 'coverage', 'journeys', 'hidden', 'data_paths', 'infra',
      'pipeline', 'library')
ORDER = ('functions', 'screens', 'gaps', 'operations', 'history', 'quality', 'paths', 'journeys', 'hidden', 'data_paths', 'infra',
         'pipeline', 'library', 'coverage')   # coverage last
FIXTURES = ROOT / 'tests/fixtures/studio/v2'


class Schemas(unittest.TestCase):
    def schema(self, folder, name):
        return json.loads((ROOT / folder / f'studio-{name}.schema.json').read_text(encoding='utf-8'))

    def test_every_v2_section_has_its_schema_and_packaged_copy(self):
        for name in V2:
            source = (ROOT / f'schemas/artifacts/studio-{name}.schema.json').read_bytes()
            self.assertEqual(source, (ROOT / f'eaos/data/schemas/artifacts/studio-{name}.schema.json').read_bytes(), name)
            schema = json.loads(source)
            self.assertEqual(schema['x-artifact'], f'studio/{name}.json')
            self.assertEqual(schema['x-revision'], 2)
            self.assertEqual(schema['properties']['contract'], {'const': 1}, 'a v2 section must not break a v1 reader')
            self.assertEqual(schema['properties']['revision'], {'const': 2})

    def test_the_manifest_lists_the_v2_sections_without_raising_the_contract(self):
        manifest = self.schema('schemas/artifacts', 'manifest')
        self.assertEqual(manifest['x-sections'][:len(V1)], list(V1))
        self.assertTrue(set(V2) <= set(manifest['x-sections']))
        self.assertTrue(set(V2) <= set(manifest['properties']['sections']['items']['properties']['name']['enum']))
        self.assertEqual(manifest['properties']['contract'], {'const': 1})

    def test_the_v1_schemas_are_unchanged_by_v2(self):
        for name in V1:
            self.assertNotIn('touch', self.schema('schemas/artifacts', name)['$defs'], name)


class Fixtures(unittest.TestCase):
    def setUp(self):
        self.contracts = artifact_contracts.contracts()

    def load(self, name):
        return json.loads((FIXTURES / f'{name}.json').read_text(encoding='utf-8'))

    def test_every_v2_section_has_a_small_fixture_that_meets_its_contract(self):
        self.assertEqual(sorted(p.stem for p in FIXTURES.glob('*.json')), sorted(V2))
        for name in V2:
            self.assertEqual(artifact_contracts.validate(self.load(name), self.contracts[f'studio-{name}']), [], name)

    def test_the_contract_refuses_what_the_studio_must_never_show(self):
        def broken(name, change):
            data = copy.deepcopy(self.load(name))
            change(data)
            return artifact_contracts.validate(data, self.contracts[f'studio-{name}'])
        self.assertTrue(broken('coverage', lambda d: d['sections'][0].update(state='coming_soon')))
        self.assertTrue(broken('coverage', lambda d: d['sections'][2].update(step='later')))
        self.assertTrue(broken('coverage', lambda d: d['sections'][0].pop('reason')))
        self.assertTrue(broken('functions', lambda d: d['functions'][0].update(module='/home/me/app/api.ts')))
        self.assertTrue(broken('functions', lambda d: d['modules'][0].update(id='../outside.ts')))
        self.assertTrue(broken('gaps', lambda d: d['gaps'][0]['closed'].update(value=1.5)))
        self.assertTrue(broken('gaps', lambda d: d['gaps'][0].update(operation='modify')))
        self.assertTrue(broken('history', lambda d: d['scans'][0].update(score=60)))
        self.assertTrue(broken('screens', lambda d: d['screens'][0]['issues'][0]['box'].update(x=-1)))
        self.assertTrue(broken('operations', lambda d: d.update(revision=1)))

    def test_what_was_not_measured_is_null_not_zero(self):
        rows = {row['section']: row for row in self.load('coverage')['sections']}
        self.assertIsNone(rows['screens']['count']['value'])
        self.assertIsNone(self.load('quality')['detectors'][1]['precision']['value'])


class Synthetic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sections = studio_synthetic.build(cards=5000, components=1000)

    def test_the_scale_the_studio_must_hold(self):
        self.assertEqual(len(self.sections['cards']['cards']), 5000)
        self.assertEqual(len(self.sections['story']['current']['components']), 1000)
        self.assertEqual(len(self.sections['gaps']['gaps']), 1000)
        self.assertGreaterEqual(len(self.sections['functions']['functions']), 1000)

    def test_every_section_and_the_manifest_meet_their_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(studio_synthetic.write(folder, self.sections), [])
            manifest = json.loads((Path(folder) / 'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual([e['name'] for e in manifest['sections']], [*V1, *ORDER])
            for entry in manifest['sections']:
                self.assertEqual(entry['sha256'], hashlib.sha256((Path(folder) / entry['file']).read_bytes()).hexdigest())
            self.assertTrue((Path(folder) / 'cards.js').is_file())

    def test_every_reference_resolves(self):
        s = self.sections
        facts = {f['id'] for f in s['evidence']['facts']}
        cards = {c['id'] for c in s['cards']['cards']}
        functions = {f['id'] for f in s['functions']['functions']}
        operations = {o['id'] for o in s['operations']['operations']}
        steps = {step['id'] for plan in s['plans']['plans'] for step in plan['steps']}
        self.assertTrue(all(set(c['evidence']) <= facts for c in s['cards']['cards']))
        self.assertTrue(all(set(f['callers']) | set(f['callees']) <= functions for f in s['functions']['functions']))
        self.assertTrue(all(set(g['operations']) <= operations and set(g['cards']) <= cards for g in s['gaps']['gaps']))
        self.assertTrue(all(o['step'] in steps and set(o['after']) <= operations for o in s['operations']['operations']))
        self.assertTrue(all(set(d['blocks']) <= cards for d in s['decisions']['decisions']))

    def test_the_same_seed_gives_the_same_folder(self):
        again = studio_synthetic.build(cards=50, components=10)
        self.assertEqual(json.dumps(again, sort_keys=True), json.dumps(studio_synthetic.build(cards=50, components=10), sort_keys=True))


class ExportedCoverage(Workspace):
    def setUp(self):
        super().setUp()
        self.out = report(self.tmp)
        self.result = export.export(self.out, 'en', 'shop')
        self.rows = {row['section']: row for row in
                     json.loads((self.out / 'studio/coverage.json').read_text(encoding='utf-8'))['sections']}

    def test_the_exporter_writes_coverage_last_and_lists_it(self):
        self.assertEqual(self.result['written'][-1], 'coverage')
        manifest = json.loads((self.out / 'studio/manifest.json').read_text(encoding='utf-8'))
        self.assertEqual((manifest['contract'], manifest['revision']), (1, 2))
        self.assertEqual(manifest['sections'][-1]['name'], 'coverage')

    def test_every_planned_section_has_a_row_and_no_row_is_optimistic(self):
        self.assertEqual(list(self.rows)[:len(coverage.PLANNED)], list(coverage.PLANNED))
        for name in V1:
            self.assertIn(self.rows[name]['state'], ('measured', 'empty'), name)
        for name in ('history', 'quality', 'library'):
            self.assertEqual(self.rows[name]['state'], 'measured', name)
        for name in ('functions', 'screens', 'gaps', 'operations'):
            row = self.rows[name]
            self.assertEqual(row['state'], 'not_measured', name)
            self.assertRegex(row['step'], r'^NS\d+\.T\d+$', name)
            self.assertTrue(row['detail'], name)

    def test_a_section_counts_as_measured_only_when_it_was_written(self):
        built = {'cards': [{'id': 'TASK-1'}], 'functions': {'functions': [{'id': 'f'}]}}
        rows = {row['section']: row for row in coverage.coverage(self.out, built, ['cards'], [{'section': 'media', 'error': 'broken'}], 'en')['sections']}
        self.assertEqual(rows['cards']['state'], 'measured')
        self.assertEqual(rows['functions']['state'], 'not_measured', 'built but not written is not measured')
        self.assertEqual(rows['media']['state'], 'failed', 'a section that broke its contract is not measured')
        self.assertEqual(rows['evidence']['state'], 'not_measured')

    def test_the_not_measured_count_matches_the_rows(self):
        data = json.loads((self.out / 'studio/coverage.json').read_text(encoding='utf-8'))
        self.assertEqual(data['not_measured']['value'], sum(r['state'] in ('not_measured', 'failed') for r in data['sections']))

    def test_the_text_follows_the_report_language(self):
        export.export(self.out, 'ar', 'shop')
        data = json.loads((self.out / 'studio/coverage.json').read_text(encoding='utf-8'))
        quality = next(r for r in data['sections'] if r['section'] == 'quality')
        self.assertRegex(quality['detail'], '[؀-ۿ]')


if __name__ == '__main__':
    unittest.main()
