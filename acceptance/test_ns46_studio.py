"""NS46 — Studio first (docs/STUDIO.md D7): the acceptance of each task of the phase, one class per task.

Written by the planner with the plan (2026-10-08, docs/north-star.json NS46), before the pages; most fail today.
Run one task's class: python tools/acceptance.py test ns46_studio.<Class>.

Interface the phase must provide:
    schemas/artifacts/studio-<section>.schema.json   for functions, screens, gaps, operations, history, quality and
                                                     coverage: "x-revision": 2, "contract" const 1, "revision" const 2,
                                                     a byte-identical packaged copy, and listed in the manifest's x-sections
    tests/fixtures/studio/v2/<section>.json          a small fixture per v2 section, valid
    tools/studio_synthetic.py build(cards, components) -> {section: data}; write(folder, sections) -> [problems]
    <report>/studio/coverage.json                    in every corpus report, valid
    docs/studio-routes.json                          the routes, each with the task that builds it (`task`)
    tools/north_star_studio.py route_status(reports, routes) -> {route id: (ok, why)}
    $EAOS_MEASURE/studio-gates/budgets.json          {"studio_source_sha256", "filter_5000_ms", "home_interactive_ms"}
    docs/STUDIO-REVIEW.md                            the self-review: every project of docs/studio-routes.json, and a line
                                                     "Owner verdict (YYYY-MM-DD): ..." the owner gave
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

from eaos import artifact_contracts

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
V2 = ('functions', 'screens', 'gaps', 'operations', 'history', 'quality', 'coverage')


def reports():
    import dev_paths
    return dev_paths.MEASURE


def routes_of(task):
    import north_star_studio
    routes = [route for route in north_star_studio.registry()['routes'] if route['task'] == task]
    return routes, north_star_studio.route_status(reports(), routes)


class RoutesOfTask:
    task = None

    def test_every_route_of_the_task_is_shown_and_passes_its_gates(self):
        routes, status = routes_of(self.task)
        self.assertTrue(routes, f'docs/studio-routes.json names no route for {self.task}')
        failing = {name: why for name, (ok, why) in status.items() if not ok}
        self.assertEqual(failing, {}, f'{self.task}: routes not shown with real data or a coverage state')


class ContractV2(unittest.TestCase):
    def test_every_v2_section_has_its_schema_and_packaged_copy(self):
        manifest = json.loads((ROOT / 'schemas/artifacts/studio-manifest.schema.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['properties']['contract'], {'const': 1})
        for name in V2:
            self.assertIn(name, manifest['x-sections'])
            source = (ROOT / f'schemas/artifacts/studio-{name}.schema.json').read_bytes()
            self.assertEqual(source, (ROOT / f'eaos/data/schemas/artifacts/studio-{name}.schema.json').read_bytes(), name)
            schema = json.loads(source)
            self.assertEqual((schema['x-revision'], schema['properties']['contract'], schema['properties']['revision']),
                             (2, {'const': 1}, {'const': 2}), name)

    def test_every_v2_section_has_a_valid_small_fixture(self):
        contracts = artifact_contracts.contracts()
        for name in V2:
            data = json.loads((ROOT / f'tests/fixtures/studio/v2/{name}.json').read_text(encoding='utf-8'))
            self.assertEqual(artifact_contracts.validate(data, contracts[f'studio-{name}']), [], name)

    def test_the_synthetic_project_holds_5000_cards_and_1000_components(self):
        import studio_synthetic
        sections = studio_synthetic.build(cards=5000, components=1000)
        self.assertEqual(len(sections['cards']['cards']), 5000)
        self.assertEqual(len(sections['story']['current']['components']), 1000)
        self.assertTrue(set(V2) <= set(sections))
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(studio_synthetic.write(folder, sections), [])

    def test_every_corpus_report_says_what_it_has_not_measured(self):
        contracts = artifact_contracts.contracts()
        record = json.loads((ROOT / 'docs/north-star.json').read_text(encoding='utf-8'))
        for spec in record['corpus']:
            path = reports() / spec['name'] / 'studio/coverage.json'
            self.assertTrue(path.is_file(), f'{spec["name"]}: no studio/coverage.json')
            data = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(artifact_contracts.validate(data, contracts['studio-coverage']), [], spec['name'])
            for row in data['sections']:
                if row['state'] in ('not_measured', 'failed'): self.assertTrue(row['step'] and row['detail'], row['section'])


class Problems(RoutesOfTask, unittest.TestCase):
    task = 'NS46.T2'

    def test_5000_cards_filter_within_100_ms_on_the_shipped_build(self):
        import north_star_studio
        budgets = json.loads((reports() / 'studio-gates/budgets.json').read_text(encoding='utf-8'))
        self.assertEqual(budgets.get('studio_source_sha256'), north_star_studio.shipped())
        self.assertLessEqual(budgets['filter_5000_ms'], 100)


class Change(RoutesOfTask, unittest.TestCase):
    task = 'NS46.T3'


class LibraryHistoryQuality(RoutesOfTask, unittest.TestCase):
    task = 'NS46.T4'


class FunctionsScreens(RoutesOfTask, unittest.TestCase):
    task = 'NS46.T5'


class Maps(RoutesOfTask, unittest.TestCase):
    task = 'NS46.T6'


class SelfReview(unittest.TestCase):
    def test_the_review_covers_every_project_and_records_the_owner_verdict(self):
        import north_star_studio
        text = (ROOT / 'docs/STUDIO-REVIEW.md').read_text(encoding='utf-8')
        for project in north_star_studio.registry()['projects']:
            self.assertIn(project['name'].split(' (')[0], text)
        self.assertRegex(text, re.compile(r'(?m)^Owner verdict \(\d{4}-\d{2}-\d{2}\): \S'))


if __name__ == '__main__':
    unittest.main()
