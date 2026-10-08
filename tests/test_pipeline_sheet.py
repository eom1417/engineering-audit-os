"""The pipeline sheet of the report for people (eaos/compose/pipeline_sheet.py, NS46.T13): drawn from the Studio's
pipeline section, present only when the project holds a pipeline, and the Studio's gallery draws the same fixture."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos import human_report
from eaos.compose import pipeline_sheet

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / 'tests/fixtures/studio/v2/pipeline.json'


def fixture():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


class PipelineSheet(unittest.TestCase):
    def test_the_sheet_draws_every_stage_of_a_short_pipeline_where_eaos_placed_it(self):
        data = fixture()
        page = pipeline_sheet.sheet({'ar': data, 'en': data})
        self.assertIn('id="pipeline-sheet"', page)
        main = next(p for p in data['pipelines'] if p['id'] == 'main')
        svg = pipeline_sheet.flowchart(data, main)
        for stage in (s for s in data['stages'] if s['pipeline'] == 'main'):
            x = pipeline_sheet.PAD + stage['layer'] * pipeline_sheet.STEP_X
            if stage['kind'] != 'router':
                self.assertIn(f'x="{x}" y="{pipeline_sheet.PAD + stage["order"] * pipeline_sheet.STEP_Y}"', svg)
            self.assertIn(stage['label'][:17].replace("'", '&#x27;'), svg)

    def test_the_stage_table_and_the_gap_carry_their_evidence(self):
        data = fixture()
        page = pipeline_sheet.sheet({'ar': data, 'en': data})
        for g in data['views']['gap']:
            self.assertIn(f"{g['evidence']['path']}:{g['evidence']['line']}", page)
        self.assertIn('eaos/pipeline/runners.py:80', page)     # claims, by its entry

    def test_no_pipeline_means_no_sheet(self):
        data = {**fixture(), 'detected': False, 'pipelines': [], 'stages': []}
        self.assertEqual(pipeline_sheet.sheet({'ar': data, 'en': data}), '')
        self.assertEqual(pipeline_sheet.sheet({}), '')

    def test_the_report_page_holds_the_sheet_in_both_languages(self):
        from tests.test_human_report import report
        data = fixture()
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(human_report, 'pipeline_sections', return_value={'ar': data, 'en': data}):
            out = report(Path(folder))
            page = Path(human_report.write(out, 'en', 'eaos')).read_text(encoding='utf-8')
        self.assertEqual(page.count('id="pipeline-sheet"'), 1)
        self.assertIn('class="l-ar" lang="ar">خط المعالجة', page)

    def test_the_studio_gallery_draws_the_contract_fixture(self):
        self.assertEqual((ROOT / 'studio/src/pages/pipeline/fixture.json').read_bytes(), FIXTURE.read_bytes())


if __name__ == '__main__':
    unittest.main()
