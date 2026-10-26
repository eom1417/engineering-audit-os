"""The pipeline sheet of the report for people (eaos/report/human_report/pipeline_sheet.py, NS46.T13): drawn from the Studio's
pipeline section, present only when the project holds a pipeline, and the Studio's gallery draws the same fixture."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.report import human_report
from eaos.report.human_report import pipeline_sheet

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/fixtures/studio/v2/pipeline.json'




def fixture():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


class PipelineSheet(unittest.TestCase):
    def test_the_sheet_draws_every_stage_where_eaos_placed_it_with_its_evidence(self):
        data = fixture()
        page = pipeline_sheet.sheet({'ar': data, 'en': data})
        self.assertIn('id="pipeline-sheet"', page)
        main = next(p for p in data['pipelines'] if any(s['label'] == 'claims' for s in data['stages'] if s['pipeline'] == p['id']))
        svg = pipeline_sheet.flowchart(data, main)
        for stage in (s for s in data['stages'] if s['pipeline'] == main['id']):
            x = pipeline_sheet.PAD + stage['layer'] * pipeline_sheet.STEP_X
            if stage['kind'] != 'router':
                self.assertIn(f'x="{x}" y="{pipeline_sheet.PAD + stage["order"] * pipeline_sheet.STEP_Y}"', svg)
            self.assertIn(stage['label'][:17].replace("'", '&#x27;'), svg)
        # The stage table and the gap carry their evidence.
        for g in data['views']['gap']:
            self.assertIn(f"{g['evidence']['path']}:{g['evidence']['line']}", page)
        claims = next(s for s in data['stages'] if s['label'] == 'claims')
        self.assertIn(f"{claims['entry']['path']}:{claims['entry']['line']}", page)     # a stage, by its entry
        # No pipeline means no sheet.
        empty = {**data, 'detected': False, 'pipelines': [], 'stages': []}
        self.assertEqual(pipeline_sheet.sheet({'ar': empty, 'en': empty}), '')
        self.assertEqual(pipeline_sheet.sheet({}), '')

    def test_the_report_page_holds_the_sheet_in_both_languages(self):
        from tests.report.test_human_report import report
        data = fixture()
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(human_report.page, 'pipeline_sections', return_value={'ar': data, 'en': data}):
            out = report(Path(folder))
            page = Path(human_report.write(out, 'en', 'eaos')).read_text(encoding='utf-8')
        self.assertEqual(page.count('id="pipeline-sheet"'), 1)
        self.assertIn('class="l-ar" lang="ar">خط المعالجة', page)


if __name__ == '__main__':
    unittest.main()
