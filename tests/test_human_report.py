"""human/index.html: four reports a person can read, every number with its meaning, in Arabic and English."""
import json
import re
import tempfile
import unittest
from pathlib import Path

from eaos import human_report
from eaos.human_report import readability_problems


def _task(number, pattern, claim, paths, ready=True):
    return {'id': f'TASK-{number}', 'claim_id': claim, 'pattern': pattern, 'title': f'{pattern} in {paths[0]}',
            'kind': 'remediate' if ready else 'investigate', 'paths': paths, 'effort': 'S', 'priority': 0.1 * number,
            'decision': {'readiness': 'ready' if ready else 'needs_review',
                         'allowed_outcomes': [] if ready else ['repair', 'retain', 'blocked_missing_requirement']},
            'options': [{'option': 'Extract the shared part', 'cost': 'medium', 'verdict': 'chosen by default'}]}


def report(root):
    """A small report: six cards in four areas, one failed stage, a two-part target."""
    out = Path(root)
    tasks = [_task(1, 'upgrade_dependency', 'CLM-1', ['package-lock.json']),
             _task(2, 'access_gap', 'CLM-2', ['src/api/users.ts'], ready=False),
             _task(3, 'remove_dead', 'CLM-3', ['src/old.ts']),
             _task(4, 'canonicalize', 'CLM-4', ['src/a.ts', 'src/b.ts']),
             _task(5, 'import_cycle', 'CLM-5', ['src/a.ts', 'src/api/users.ts']),
             _task(6, 'hotspot', 'CLM-6', ['src/api/users.ts'], ready=False)]
    plan = {'tasks': tasks, 'milestones': [
        {'id': 'M01', 'name': 'stabilize', 'goal': 'Nothing broken.', 'goal_ar': 'لا شيء مكسور.', 'exit': 'All pass.',
         'exit_ar': 'كل شيء يمر.', 'tasks': ['TASK-1', 'TASK-2', 'TASK-3']},
        {'id': 'M02', 'name': 'boundaries', 'goal': 'No cycle.', 'goal_ar': 'لا دورة.', 'exit': 'No cycle.',
         'exit_ar': 'لا دورة.', 'tasks': ['TASK-4', 'TASK-5', 'TASK-6']}]}
    confidence = {'CLM-2': 'LIKELY', 'CLM-4': 'LIKELY'}
    claims = [{'id': f'CLM-{n}', 'statement': f'claim {n}', 'confidence': confidence.get(f'CLM-{n}', 'CONFIRMED'),
               'assessment': {'before': f'before {n}', 'after': f'after {n}'}} for n in range(1, 7)]
    dossier = {'claims': claims, 'coverage': {'source_files': 50, 'files_parsed': 50, 'executed_verification': False,
                                              'runtime_confirmation': 0, 'semantic_review': False},
               'provenance': {'generated_at': '2026-09-27T00:00:00'}}
    register = {'items': [{'claim_id': 'CLM-1', 'severity': 'medium', 'category': 'supply_chain'}]}
    manifest = {'target': '/x/shop', 'stages': {'facts': {'status': 'ok'}, 'load': {'status': 'failed'},
                                                 'measure': {'status': 'ok'}, 'verify': {'status': 'unavailable'}}}
    target = {'root': '', 'forbidden_edges': 2,
              'current_components': [{'id': 'T-src', 'name': 'src', 'relation': 'modify', 'files': 3, 'target_component': 'lib',
                                      'paths': ['src/a.ts', 'src/b.ts', 'src/old.ts']},
                                     {'id': 'T-api', 'name': 'src/api', 'relation': 'rebuild', 'files': 1, 'target_component': 'routes',
                                      'paths': ['src/api/users.ts']}],
              'target_components': [{'name': 'routes', 'layer': 'routes', 'files': 1}, {'name': 'lib', 'layer': 'lib', 'files': 3}],
              'gap_matrix': [{'component': 'T-src', 'current_origin': 'src', 'current': {'relation': 'modify'}, 'gap': 'partial',
                              'target_component': 'lib', 'files_to_move': 1, 'forbidden_imports': 0}]}
    for name, record in (('plan.json', plan), ('dossier.json', dossier), ('debt-register.json', register),
                         ('run-manifest.json', manifest), ('target-architecture.json', target)):
        (out / name).write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
    return out


def section(page, name):
    return re.search(rf'<section id="{name}".*?</section>', page, re.S).group(0)


class HumanReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = report(self.tmp.name)
        self.page = human_report.write(self.out, 'ar').read_text(encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_page_is_one_self_contained_file_with_the_four_reports(self):
        self.assertTrue((self.out / 'human' / 'index.html').is_file())
        for name in human_report.SECTIONS:
            self.assertIn(f'<section id="{name}" class="report" data-report="{name}">', self.page)
        self.assertNotRegex(self.page, r'(src|href)="https?://')
        self.assertIn('dir="rtl"', self.page)

    def test_the_severity_legend_defines_every_level(self):
        start = self.page.index('data-legend="severity"')
        legend = self.page[start:self.page.index('<div class="card"', start)]
        for level in ('حرجة', 'عالية', 'متوسطة', 'منخفضة', 'Critical', 'High', 'Medium', 'Low'):
            self.assertIn(level, legend)

    def test_the_score_follows_the_documented_formula(self):
        result = human_report.model(self.out)['score']
        areas = {name: area['score'] for name, area in result['areas'].items()}
        # security: medium from the register (2) + critical likely (10 x 0.7) = 9 -> 100 x 20 / 29
        self.assertEqual(areas, {'security': 69, 'quality': 92, 'structure': 91, 'maintainability': 91, 'performance': None})
        self.assertEqual((result['score'], result['grade'], result['capped']), (86, 'good', False))
        self.assertEqual(result['areas']['security']['light'], 'red')
        self.assertEqual(result['areas']['performance']['light'], 'grey')

    def test_a_confirmed_critical_problem_caps_the_score(self):
        rows = [dict(row, confidence='CONFIRMED') for row in human_report.problems(self.out)]
        self.assertEqual(human_report.score(rows, 50)['score'], human_report.CRITICAL_CAP)

    def test_no_number_stands_alone(self):
        self.assertEqual(readability_problems(self.page), [])
        self.assertIn('data-priority="0.6', self.page)       # the raw priority stays in an attribute, out of the text

    def test_the_indicator_catches_a_bare_score_and_a_missing_section(self):
        page = ('<section id="summary" data-report="summary"><p class="l-ar">الأولوية 0.79</p><p class="l-en">12 files</p></section>')
        found = readability_problems(page)
        self.assertTrue(any('raw decimal' in p for p in found), found)
        self.assertTrue(any('no stated meaning' in p for p in found), found)
        self.assertIn('missing report section: plan', found)
        self.assertIn('no severity legend', found)

    def test_both_languages_are_in_the_page(self):
        for text in ('ملخص المشروع', 'Project summary', 'الخطة والتقدم', 'Plan and progress', 'كيف حسبنا', 'How we computed'):
            self.assertIn(text, self.page)
        self.assertIn("localStorage.setItem('eaos-human-lang'", self.page)

    def test_progress_changes_the_plan_section(self):
        progress = {'waves': [{'number': 1, 'kept': ['TASK-1', 'TASK-3'], 'failed': {'TASK-4': 'the tests failed'},
                               'branch': 'eaos/wave-1', 'status': 'done'}]}
        after = human_report.write(self.out, 'ar', progress=progress).read_text(encoding='utf-8')
        before, now = section(self.page, 'plan'), section(after, 'plan')
        self.assertNotEqual(before, now)
        self.assertIn('eaos/wave-1', now)
        self.assertIn('the tests failed', now)
        self.assertIn('aria-valuenow="67"', now)
        self.assertEqual(readability_problems(after), [])

    def test_what_was_not_checked_is_said(self):
        summary = section(self.page, 'summary')
        self.assertIn('أقدّر السلوك مع كثرة المستخدمين', summary)      # the failed load stage, in plain words
        self.assertIn('لم تُشغَّل اختبارات المشروع', summary)

    def test_a_report_with_no_records_still_gets_a_page_that_says_not_available(self):
        with tempfile.TemporaryDirectory() as empty:
            page = human_report.write(empty, 'en', 'shop').read_text(encoding='utf-8')
        self.assertIn('Not available in this report.', page)
        self.assertEqual(readability_problems(page), [])


if __name__ == '__main__':
    unittest.main()
