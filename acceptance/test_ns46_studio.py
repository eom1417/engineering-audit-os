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
The pipeline map (docs/STUDIO.md D9; written by the planner 2026-10-08 with NS46.T12-T13):
    eaos.facts.pipeline.scan(project) -> record      {detected, confidence, kinds, evidence, looked_for, pipelines, stages,
                                                     edges, routers, fans, control, error_lanes, hidden, unresolved}; every
                                                     stage, edge and branch with its evidence {path, line} in the project
    eaos.facts.pipeline.write(report, record)        facts/pipeline.json of a report, as the facts stage writes it
    eaos.studio.pipeline.section(record, cards=(), plan=None, lang='en') -> the body of studio/pipeline.json
    evaluations/pipelines/<name>.json                hand-written truth files: {name, kind, source, commit, pipelines:
                                                     [{anchor, stages, edges, routers: [{table, branches}]}]}; source null
                                                     is this repository; apps.json lists what each app project holds
    tools/pipeline_truth.py checkout(truth) -> Path | None, compare(truth, record) -> {stages|edges|branches: {recall,
                                                     precision}}, verify(project, record) -> [problems], apps() -> [(name, path)]
    human/index.html                                 a section id="pipeline-sheet" when facts/pipeline.json holds a pipeline
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


RECALL, PRECISION = 0.8, 0.9


def pipeline_truth():
    import pipeline_truth as truth
    return truth


class PipelineEngine(unittest.TestCase):
    """NS46.T12: the engine finds the pipelines as the hand-written truth files say, and invents none."""

    def judge(self, name, scores):
        for part in ('stages', 'edges', 'branches'):
            self.assertGreaterEqual(scores[part]['recall'], RECALL, f'{name}: {part} recall {scores[part]}')
            self.assertGreaterEqual(scores[part]['precision'], PRECISION, f'{name}: {part} precision {scores[part]}')

    def test_eaos_itself_matches_its_hand_written_truth(self):
        from eaos.facts import pipeline
        truth = pipeline_truth()
        record = pipeline.scan(ROOT)
        self.assertTrue(record['detected'])
        self.judge('eaos', truth.compare(truth.load('eaos'), record))
        self.assertEqual(truth.verify(ROOT, record), [])

    def test_two_public_pipelines_of_different_kinds_match_their_truth(self):
        from eaos.facts import pipeline
        truth = pipeline_truth()
        public = [truth.load(path.stem) for path in sorted((ROOT / 'evaluations/pipelines').glob('*.json'))
                  if path.stem not in ('eaos', 'apps')]
        self.assertGreaterEqual(len({t['kind'] for t in public}), 2, 'two public pipelines of different kinds')
        for spec in public:
            self.assertTrue(spec['source'] and spec['commit'], spec['name'])
            where = truth.checkout(spec)
            self.assertIsNotNone(where, f"{spec['name']}: not cloned at {spec['commit']} (python tools/pipeline_truth.py fetch)")
            record = pipeline.scan(where)
            self.judge(spec['name'], truth.compare(spec, record))
            self.assertEqual(truth.verify(where, record), [], spec['name'])

    def test_no_pipeline_is_invented_on_the_app_projects(self):
        from eaos.facts import pipeline
        truth = pipeline_truth()
        expected = truth.load('apps')['projects']
        apps = truth.apps()
        self.assertGreaterEqual(len(apps), 4)
        for name, where in apps:
            record = pipeline.scan(where)
            found = sorted(p['title'] for p in record['pipelines'] if p['role'] == 'product')
            self.assertEqual(found, sorted(expected.get(name, {}).get('product', [])), f'{name}: a product pipeline not in the truth')
            self.assertEqual(truth.verify(where, record), [], name)

    def test_the_section_meets_its_contract_with_its_fixture(self):
        from eaos.facts import pipeline
        from eaos.studio import pipeline as section
        contracts = artifact_contracts.contracts()
        manifest = json.loads((ROOT / 'schemas/artifacts/studio-manifest.schema.json').read_text(encoding='utf-8'))
        self.assertIn('pipeline', manifest['x-sections'])
        source = (ROOT / 'schemas/artifacts/studio-pipeline.schema.json').read_bytes()
        self.assertEqual(source, (ROOT / 'eaos/data/schemas/artifacts/studio-pipeline.schema.json').read_bytes())
        fixture = json.loads((ROOT / 'tests/fixtures/studio/v2/pipeline.json').read_text(encoding='utf-8'))
        self.assertEqual(artifact_contracts.validate(fixture, contracts['studio-pipeline']), [])
        self.assertTrue(fixture['detected'] and fixture['routers'] and fixture['views']['gap'])
        body = {'schema_version': 1, 'contract': 1, 'revision': 2, **section.section(pipeline.scan(ROOT))}
        self.assertEqual(artifact_contracts.validate(body, contracts['studio-pipeline']), [])
        self.assertEqual({r['id'] for r in body['rules']} >= {f'P{n}' for n in range(1, 10)}, True)
        for entry in body['views']['gap']:
            self.assertTrue(entry['evidence']['path'], entry['id'])

    def test_a_1000_stage_synthetic_pipeline_builds_within_its_budget(self):
        import time
        from eaos.facts import pipeline
        from eaos.studio import pipeline as section
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            body = ['def stage_%d(value):\n    return value + %d\n' % (n, n) for n in range(1000)]
            calls = ['    v0 = stage_0(seed)'] + ['    v%d = stage_%d(v%d)' % (n, n, n - 1) for n in range(1, 1000)]
            (project / 'flow.py').write_text('\n'.join(body) + '\n\ndef run_pipeline(seed):\n' + '\n'.join(calls) + '\n    return v999\n',
                                             encoding='utf-8')
            began = time.monotonic()
            record = pipeline.scan(project)
            data = {'schema_version': 1, 'contract': 1, 'revision': 2, **section.section(record)}
            spent = time.monotonic() - began
        self.assertGreaterEqual(len(data['stages']), 1000)
        self.assertGreaterEqual(len(data['edges']), 999)
        self.assertEqual(artifact_contracts.validate(data, artifact_contracts.contracts()['studio-pipeline']), [])
        self.assertLess(spent, 20.0, f'{spent:.1f} s for 1,000 stages')


class PipelinePage(RoutesOfTask, unittest.TestCase):
    """NS46.T13: System -> Pipeline in the Studio, and the pipeline sheet in the report."""
    task = 'NS46.T13'

    def test_the_report_has_the_pipeline_sheet(self):
        sys.path.insert(0, str(ROOT))
        from eaos import human_report
        from eaos.facts import pipeline
        from tests.test_human_report import report
        with tempfile.TemporaryDirectory() as folder:
            out = report(Path(folder))
            pipeline.write(out, pipeline.scan(ROOT))
            page = Path(human_report.write(out, 'en', 'eaos')).read_text(encoding='utf-8')
        self.assertIn('id="pipeline-sheet"', page)
        for stage in ('facts', 'claims', 'compose'):
            self.assertIn(stage, page)


if __name__ == '__main__':
    unittest.main()
