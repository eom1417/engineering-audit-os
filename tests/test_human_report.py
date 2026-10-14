"""human/index.html: four reports a person can read, every number with its meaning, in Arabic and English."""
import json
import re
import tempfile
import unittest
from pathlib import Path

from eaos import human_report
from eaos.human_report import priority_words
from eaos.studio import model


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
        self.addCleanup(self.tmp.cleanup)
        self.out = report(self.tmp.name)
        self.page = human_report.write(self.out, 'ar').read_text(encoding='utf-8')

    def test_the_page_is_one_self_contained_bilingual_file_with_the_four_reports(self):
        self.assertTrue((self.out / 'human' / 'index.html').is_file())
        for name in human_report.SECTIONS:
            self.assertIn(f'<section id="{name}" class="report" data-report="{name}">', self.page)
        self.assertNotRegex(self.page, r'(src|href)="https?://')
        self.assertIn('dir="rtl"', self.page)
        for text in ('ملخص المشروع', 'Project summary', 'الخطة والتقدم', 'Plan and progress', 'كيف حسبنا', 'How we computed'):
            self.assertIn(text, self.page)
        self.assertIn("localStorage.setItem('eaos-human-lang'", self.page)
        start = self.page.index('data-legend="severity"')
        legend = self.page[start:self.page.index('<div class="card"', start)]
        for level in ('حرجة', 'عالية', 'متوسطة', 'منخفضة', 'Critical', 'High', 'Medium', 'Low'):
            self.assertIn(level, legend)
        self.assertIn('data-priority="0.6', self.page)       # the raw priority stays in an attribute, out of the text
        summary = section(self.page, 'summary')
        self.assertIn('أقدّر السلوك مع كثرة المستخدمين', summary)      # the failed load stage, in plain words
        self.assertIn('لم تُشغَّل اختبارات المشروع', summary)

    def test_the_score_follows_the_documented_formula_and_a_confirmed_critical_caps_it(self):
        result = human_report.model(self.out)['score']
        areas = {name: area['score'] for name, area in result['areas'].items()}
        # security: medium from the register (2) + critical likely (10 x 0.7) = 9 -> 100 x 20 / 29
        self.assertEqual(areas, {'security': 69, 'quality': 92, 'structure': 91, 'maintainability': 91, 'performance': None, 'ux': None})
        self.assertEqual((result['score'], result['grade'], result['capped']), (86, 'good', False))
        self.assertEqual((result['areas']['security']['light'], result['areas']['performance']['light']), ('red', 'grey'))
        rows = [dict(row, confidence='CONFIRMED') for row in model.problems(self.out)]
        self.assertEqual(model.score(rows, 50)['score'], model.CRITICAL_CAP)
        # A vulnerable library the assistant kept (no fixed version) still weighs: EAOS read security 100 with one known.
        (self.out / 'cards.json').write_text(json.dumps({'closed': [{'card': 'TASK-9', 'claim_id': 'CLM-1', 'title': 'braces'}]}))
        security = human_report.model(self.out)['score']['areas']['security']
        self.assertEqual((security['score'], security['accepted']), (65, 1))     # 9 + the kept medium 2: 100 x 20 / 31
        # A serious problem is never called low priority.
        self.assertIn('Urgent because of its severity', priority_words(90, 'high'))
        self.assertIn('Low priority', priority_words(90, 'low'))
        self.assertIn('Very high priority', priority_words(5, 'high'))

    def test_progress_changes_the_plan_section(self):
        progress = {'waves': [{'number': 1, 'kept': ['TASK-1', 'TASK-3'], 'failed': {'TASK-4': 'the tests failed'},
                               'branch': 'eaos/wave-1', 'status': 'done'}]}
        after = human_report.write(self.out, 'ar', progress=progress).read_text(encoding='utf-8')
        before, now = section(self.page, 'plan'), section(after, 'plan')
        self.assertNotEqual(before, now)
        self.assertIn('eaos/wave-1', now)
        self.assertIn('the tests failed', now)
        self.assertIn('aria-valuenow="67"', now)

    def test_missing_or_broken_records_cost_a_section_not_the_page(self):
        with tempfile.TemporaryDirectory() as empty:
            page = human_report.write(empty, 'en', 'shop').read_text(encoding='utf-8')
        self.assertIn('Not available in this report.', page)
        (self.out / 'plan.json').write_text('{"tasks": [1, {"id": "TASK-9"}], "milestones": "none"}', encoding='utf-8')
        (self.out / 'target-architecture.json').write_text('{"current_components": [{"paths": 7}]', encoding='utf-8')
        (self.out / 'dossier.json').write_text('[]', encoding='utf-8')
        page = human_report.write(self.out, 'ar').read_text(encoding='utf-8')
        for name in human_report.SECTIONS:
            self.assertIn(f'data-report="{name}"', page)
        self.assertIn('غير متاح في هذا التقرير.', page)


if __name__ == '__main__':
    unittest.main()
