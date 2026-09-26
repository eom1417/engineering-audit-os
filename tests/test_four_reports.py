"""The four reports: the blueprint's template, every number with its source, nothing cut without a mark."""
import json
from pathlib import Path

from shared_fixture import Workspace

from eaos.compose.four_reports import NAMES, clip, write


class FourReportsTests(Workspace):
    def report(self, language='en'):
        out = Path(self.tmp)
        (out / 'dossier.json').write_text(json.dumps({'coverage': {'files_parsed': 9, 'source_files': 10, 'not_examined': ['x']}}))
        (out / 'features.json').write_text(json.dumps({'features': [{'name': 'contas', 'critical': True, 'target_component': 'feature:contas'}]}))
        (out / 'debt-register.json').write_text(json.dumps({'items': [
            {'id': 'DEBT-001', 'severity': 'high', 'category': 'security', 'title': 'a key ' * 40}]}))
        (out / 'target-architecture.json').write_text(json.dumps({'reference': 'react-vite-spa-rest', 'forbidden_edges': 2,
            'target_components': [{'name': 'feature:contas', 'layer': 'features', 'files': 3}],
            'infrastructure': [{'area': 'ci', 'present': False, 'decision': 'Introduce CI', 'tool': 'GitHub Actions', 'evidence': '0 steps'}],
            'current_components': [{'origin': 'src', 'relation': 'rebuild', 'target_component': 'feature:contas', 'reason': 'r',
                                    'projection': {'moved': 3}}]}))
        (out / 'plan.json').write_text(json.dumps({'tasks': [{'id': 'T1', 'title': 't', 'effort': 'S', 'section': 'frontend',
                                                              'kind': 'remediate', 'decision': {'readiness': 'ready'}}],
            'milestones': [{'id': 'M01', 'name': 'stabilize', 'goal': 'g', 'exit': 'e', 'goal_ar': 'ج', 'exit_ar': 'خ', 'tasks': ['T1']}],
            'sections': [{'section': 'frontend', 'tasks': ['T1'], 'depends_on': []}]}))
        write(out, language)
        return out

    def test_every_report_follows_the_template(self):
        out = self.report()
        for name in NAMES:
            text = (out / name).read_text()
            for heading in ('## Summary', '### The numbers that matter', '### The largest risks', '## Not examined', '## Appendices'):
                self.assertIn(heading, text, name)

    def test_every_number_names_its_source(self):
        record = json.loads((self.report() / 'reports.json').read_text())
        self.assertEqual(sorted(record['reports']), sorted(NAMES))
        for numbers in record['reports'].values():
            for row in numbers.values(): self.assertTrue(row['source'])

    def test_a_cut_text_shows_it_was_cut_and_lines_fit(self):
        self.assertTrue(clip('word ' * 40, 20).endswith('…'))
        text = (self.report() / 'CURRENT-STATE.md').read_text()
        self.assertIn('…', text)
        for line in text.splitlines():
            self.assertTrue(len(line) <= 80 or ' ' not in line.strip()[:81] or line.startswith('```'), line)

    def test_an_arabic_report_uses_the_arabic_goals(self):
        text = (self.report('ar') / 'EXECUTION-PLAN.md').read_text()
        self.assertIn('ج', text)
        self.assertIn('الخروج: خ', text)
