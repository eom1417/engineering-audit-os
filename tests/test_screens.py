"""The screen gate: pinned Playwright + axe, Lighthouse and the CSS analyzer, run for real on small local pages.

Every runner reports a missing tool as `unavailable` with the install command; the tests that need the tools skip,
with that reason, on a computer that has not installed them (python -m eaos tools install --only
playwright,axe-core,lighthouse,css-analyzer).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos import toolchain
from eaos.screens import audit
from shared_fixture import TemporaryWorkspace

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/screens'
PAGES = ('clean', 'overflow', 'rtl-shifted', 'small-target', 'unlabelled', 'truncated', 'no-viewport-meta')


def url(name):
    return (FIXTURES / f'{name}.html').as_uri()


def rows_of(result, name):
    return [row for row in result['rows'] if row['url'].split('?', 1)[0].endswith(f'/{name}.html')]


BROWSER_MISSING = audit.missing('playwright', 'axe-core')


@unittest.skipIf(BROWSER_MISSING, f'screen tools not installed: {BROWSER_MISSING}')
class PageAuditTests(TemporaryWorkspace):
    @classmethod
    def setUpClass(cls):
        cls.out = cls.workspace().name
        cls.result = audit.page_audit([url(name) for name in PAGES], out=cls.out)

    def observed(self, name):
        return [row for row in rows_of(self.result, name) if row['status'] == 'observed']

    def test_the_run_is_observed_with_the_pinned_tools(self):
        self.assertEqual(self.result['status'], 'observed', self.result.get('reason'))
        self.assertEqual(self.result['tools']['playwright'], '1.63.0')
        self.assertEqual(self.result['tools']['axe-core'], '4.13.0')
        self.assertEqual(self.observed('clean')[0]['axe']['version'], '4.13.0')

    def test_a_clean_page_passes_every_viewport_and_its_dark_theme(self):
        rows = self.observed('clean')
        self.assertEqual(sorted({(r['variant'], r['viewport']) for r in rows}),
                         sorted((v, s['name']) for v in ('light', 'dark') for s in audit.VIEWPORTS))
        self.assertEqual([r['failures'] for r in rows], [[]] * 6)

    def test_a_700px_element_at_390_fails_overflow_and_only_there(self):
        rows = {r['viewport']: r for r in self.observed('overflow')}
        self.assertTrue(any(f.startswith('overflow:') for f in rows['phone']['failures']), rows['phone']['failures'])
        self.assertGreater(rows['phone']['scroll_width'], 390)
        self.assertEqual(rows['desktop']['failures'], [])

    def test_a_phone_is_emulated_and_a_widened_layout_viewport_fails(self):
        # Under mobile emulation an overflowing page widens innerWidth to its content; the gate judges the
        # configured 390 and fails the widened layout itself.
        phone = next(r for r in self.observed('overflow') if r['viewport'] == 'phone')
        self.assertTrue(phone['mobile'])
        self.assertEqual((phone['layout_width'], phone['inner_width']), (716, 390))
        self.assertTrue(phone['failures'][0].startswith('layout_width: the page laid out 716px'), phone['failures'])
        clean = next(r for r in self.observed('clean') if r['viewport'] == 'phone')
        self.assertEqual((clean['mobile'], clean['layout_width']), (True, 390))

    def test_a_page_without_a_viewport_meta_fails_at_phone_width_although_its_content_fits(self):
        rows = {r['viewport']: r for r in self.observed('no-viewport-meta')}
        self.assertEqual((rows['phone']['layout_width'], rows['phone']['overflow_element_count']), (980, 0))
        self.assertTrue(any(f.startswith('layout_width:') for f in rows['phone']['failures']))
        self.assertEqual((rows['tablet']['failures'], rows['desktop']['failures']), ([], []))

    def test_a_scroller_marked_data_scroll_x_is_not_overflow(self):
        phone = next(r for r in self.observed('clean') if r['viewport'] == 'phone')
        self.assertEqual((phone['overflow_element_count'], phone['scroll_width']), (0, 390))

    def test_an_rtl_page_that_opens_shifted_fails_initial_scroll(self):
        for row in self.observed('rtl-shifted'):
            self.assertEqual(row['dir'], 'rtl')
            self.assertTrue(any(f.startswith('initial_scroll:') for f in row['failures']), row['failures'])
            self.assertFalse(any(f.startswith('overflow:') for f in row['failures']), row['failures'])

    def test_a_20px_button_fails_targets_at_phone_width_only(self):
        rows = {r['viewport']: r for r in self.observed('small-target')}
        self.assertEqual(rows['phone']['small_targets'][0]['width'], 20)
        self.assertTrue(any(f.startswith('targets:') for f in rows['phone']['failures']))
        self.assertEqual(rows['desktop']['failures'], [])

    def test_missing_alt_and_label_are_axe_violations_with_their_selectors(self):
        row = self.observed('unlabelled')[0]
        violations = {v['id']: v for v in row['axe']['violations']}
        self.assertLessEqual({'image-alt', 'label'}, set(violations))
        self.assertEqual(violations['image-alt']['targets'], ['img'])
        self.assertTrue(any(f.startswith('axe:') for f in row['failures']))

    def test_clipped_text_must_be_marked_and_keep_a_path_to_its_full_text(self):
        for row in self.observed('truncated'):
            self.assertEqual({(t['selector'], t['problem']) for t in row['truncated']},
                             {('p#silent', 'not_marked'), ('p#marked', 'no_full_text')})
            self.assertTrue(any(f.startswith('truncation: 2 ') for f in row['failures']), row['failures'])
        for row in self.observed('clean'):
            self.assertEqual(row['truncated_count'], 0)

    def test_the_page_height_is_measured_for_the_phone_budget(self):
        phone = next(r for r in self.observed('clean') if r['viewport'] == 'phone')
        self.assertGreater(phone['page_height'], 300)
        self.assertEqual(audit.failures(phone, height_budget=2), [])
        self.assertTrue(audit.failures(phone, height_budget=0.2)[0].startswith('height:'))

    def test_a_page_without_a_dark_theme_is_not_audited_dark(self):
        dark = [r for r in rows_of(self.result, 'overflow') if r['variant'] == 'dark']
        self.assertEqual({r['status'] for r in dark}, {'skipped'})

    def test_every_observed_row_has_a_full_page_screenshot(self):
        for row in self.result['rows']:
            if row['status'] == 'observed': self.assertTrue(Path(row['screenshot']).is_file(), row)

    def test_the_browser_reaches_nothing_but_the_tested_page(self):
        with tempfile.TemporaryDirectory() as folder:
            page = Path(folder) / 'remote.html'
            page.write_text('<!doctype html><html lang="en"><head><title>t</title></head><body><main><h1>t</h1>'
                            '<img src="https://example.invalid/pixel.png" alt="pixel"></main></body></html>', encoding='utf-8')
            result = audit.page_audit([page.as_uri()], viewports=audit.VIEWPORTS[:1], page_variants=audit.variants(themes=('light',)))
        self.assertEqual(result['rows'][0]['blocked_requests'], ['https://example.invalid/pixel.png'])

    def test_language_and_theme_are_set_through_the_named_key_and_parameter(self):
        page_variants = audit.variants(lang_key='studio-lang', theme_param='theme')
        self.assertEqual([v['name'] for v in page_variants], ['ar-light', 'en-light', 'ar-dark', 'en-dark'])
        result = audit.page_audit([url('bilingual')], viewports=audit.VIEWPORTS[:1], page_variants=page_variants)
        rows = {r['variant']: r for r in result['rows']}
        self.assertEqual((rows['ar-dark']['lang'], rows['ar-dark']['dir']), ('ar', 'rtl'))
        self.assertEqual((rows['en-light']['lang'], rows['en-light']['dir']), ('en', 'ltr'))
        self.assertIn('theme=dark', rows['ar-dark']['url'])
        self.assertEqual([r['failures'] for r in rows.values()], [[]] * 4)


@unittest.skipIf(BROWSER_MISSING, f'screen tools not installed: {BROWSER_MISSING}')
class PageActionTests(unittest.TestCase):
    """A page given with actions is measured in the state a person reaches: an opened panel, a typed search."""

    @classmethod
    def setUpClass(cls):
        phone, one = audit.VIEWPORTS[:1], audit.variants(themes=('light',))
        page = {'url': url('opened'), 'name': 'opened', 'actions': [{'click': '#open', 'wait': 100}], 'height_budget': 0.1}
        cls.result = audit.page_audit([url('opened'), page], viewports=phone, page_variants=one)

    def test_the_page_as_loaded_passes(self):
        plain = next(r for r in self.result['rows'] if r['page'] is None)
        self.assertEqual(plain['failures'], [])

    def test_the_opened_state_fails_on_what_the_action_revealed(self):
        opened = next(r for r in self.result['rows'] if r['page'] == 'opened')
        self.assertEqual(opened['page_errors'], ['opened with an error'])
        self.assertEqual([s.split(' > ')[-1] for s in opened['arabic_tracking']], ['p.tracked'])
        self.assertEqual(opened['root_attributes'], {'lang': 'ar', 'dir': 'rtl'})
        reasons = {f.split(':')[0] for f in opened['failures']}
        self.assertLessEqual({'overflow', 'arabic_tracking', 'script_errors', 'height'}, reasons)


@unittest.skipIf(BROWSER_MISSING, f'screen tools not installed: {BROWSER_MISSING}')
class PageSubsetTests(unittest.TestCase):
    def test_a_page_is_audited_only_in_its_named_viewports_and_variants(self):
        page = {'url': url('clean'), 'name': 'clean', 'viewports': ['phone'], 'variants': ['dark']}
        result = audit.page_audit([page], page_variants=audit.variants())
        self.assertEqual([(r['viewport'], r['variant']) for r in result['rows']], [('phone', 'dark')])


class ServeTests(unittest.TestCase):
    def test_text_files_are_sent_gzip_compressed_to_a_browser_that_accepts_it(self):
        import gzip
        from urllib.request import Request, urlopen
        with audit.serve(FIXTURES) as base:
            with urlopen(Request(base + 'clean.html', headers={'Accept-Encoding': 'gzip'})) as answer:
                self.assertEqual(answer.headers['Content-Encoding'], 'gzip')
                body = gzip.decompress(answer.read())
            with urlopen(base + 'clean.html') as answer:
                self.assertIsNone(answer.headers['Content-Encoding'])
                self.assertEqual(answer.read(), body)
        self.assertEqual(body, (FIXTURES / 'clean.html').read_bytes())


LIGHTHOUSE_MISSING = audit.missing('playwright', 'lighthouse')


@unittest.skipIf(LIGHTHOUSE_MISSING, f'lighthouse not installed: {LIGHTHOUSE_MISSING}')
class LighthouseTests(unittest.TestCase):
    def test_mobile_scores_lcp_and_cls_of_a_local_page(self):
        with audit.serve(FIXTURES) as base:
            clean, unlabelled = audit.lighthouse(base + 'clean.html'), audit.lighthouse(base + 'unlabelled.html')
        self.assertEqual(clean['status'], 'observed', clean.get('reason'))
        self.assertEqual((clean['version'], clean['form_factor']), ('13.5.0', 'mobile'))
        self.assertEqual(set(clean['scores']), {'performance', 'accessibility', 'best-practices'})
        self.assertIsInstance(clean['lcp_ms'], int)
        self.assertEqual(clean['cls'], 0)
        self.assertLess(unlabelled['scores']['accessibility'], clean['scores']['accessibility'])
        self.assertIn('image-alt', unlabelled['failed_audits']['accessibility'])
        self.assertNotIn('accessibility', clean['failed_audits'])


CSS_MISSING = audit.missing('css-analyzer')


@unittest.skipIf(CSS_MISSING, f'css-analyzer not installed: {CSS_MISSING}')
class CssStatsTests(unittest.TestCase):
    def test_distinct_colors_font_sizes_spacings_and_specificity_of_a_site(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'site.css').write_text('a{color:#111;font-size:14px;margin:4px 8px} #id .x{color:#112;padding:8px;gap:12px}',
                                                encoding='utf-8')
            Path(folder, 'index.html').write_text('<style>p{color:#111;font-size:15px}</style>', encoding='utf-8')
            stats = audit.css_stats(folder)
        self.assertEqual(stats['status'], 'observed', stats.get('reason'))
        self.assertEqual((stats['files'], stats['inline_blocks']), (1, 1))
        self.assertEqual(stats['colors']['unique'], 2)
        self.assertEqual(stats['font_sizes']['unique'], 2)
        self.assertEqual(set(stats['spacings']['values']), {'4px', '8px', '12px'})
        self.assertEqual(stats['specificity']['max'], [1, 1, 0])

    def test_a_folder_without_css_is_not_applicable(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(audit.css_stats(folder)['status'], 'not_applicable')


class UnavailableTests(unittest.TestCase):
    """A runner whose tool is absent returns a structured `unavailable`, with the command that installs it."""

    def test_each_runner_reports_a_missing_tool_instead_of_raising(self):
        with mock.patch.object(toolchain, 'found_version', return_value=(None, 'not installed')):
            results = [audit.page_audit(url('clean')), audit.lighthouse('http://127.0.0.1:9/'), audit.css_stats(FIXTURES)]
        for result in results:
            self.assertEqual(result['status'], 'unavailable')
            self.assertIn('python -m eaos tools install --only', result['reason'])

    def test_no_node_is_said_as_such(self):
        with mock.patch.object(audit.shutil, 'which', return_value=None):
            self.assertIn('Node.js', audit.page_audit(url('clean'))['reason'])

    def test_a_library_tool_is_installed_when_its_package_json_has_the_pinned_version(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {'EAOS_ENGINE_TOOLS': home}):
            tool = next(t for t in toolchain.registry()['tools'] if t['name'] == 'css-analyzer')
            self.assertEqual(toolchain.found_version(tool), (None, 'not installed'))
            manifest = Path(home, 'npm/css-analyzer/node_modules/@projectwallace/css-analyzer/package.json')
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({'version': tool['version']}))
            self.assertEqual(toolchain.found_version(tool), (tool['version'], ''))


class VariantTests(unittest.TestCase):
    def test_language_and_theme_go_through_the_named_key_or_parameter_and_the_theme_always_through_the_color_scheme(self):
        rows = {v['name']: v for v in audit.variants(lang_key='studio-lang', theme_param='theme')}
        self.assertEqual(set(rows), {'ar-light', 'en-light', 'ar-dark', 'en-dark'})
        self.assertEqual((rows['ar-dark']['storage'], rows['ar-dark']['query'], rows['ar-dark']['color_scheme']),
                         ({'studio-lang': 'ar'}, {'theme': 'dark'}, 'dark'))
        self.assertFalse(rows['ar-dark']['if_page_supports_dark'])
        plain = {v['name']: v for v in audit.variants()}
        self.assertEqual(set(plain), {'light', 'dark'})
        self.assertEqual((plain['dark']['storage'], plain['dark']['query'], plain['dark']['color_scheme']), ({}, {}, 'dark'))
        self.assertTrue(plain['dark']['if_page_supports_dark'])


class FailureRuleTests(unittest.TestCase):
    def row(self, **change):
        row = {'status': 'observed', 'url': 'http://127.0.0.1/p.html', 'width': 390, 'inner_width': 390, 'scroll_width': 390,
               'overflow_element_count': 0, 'scroll': {'x': 0, 'y': 0}, 'small_target_count': 0, 'axe': {'violations': []}}
        return {**row, **change}

    def test_moderate_and_minor_axe_findings_are_reported_but_do_not_fail(self):
        minor = [{'id': 'region', 'impact': 'moderate', 'nodes': 1}, {'id': 'x', 'impact': 'minor', 'nodes': 1}]
        self.assertEqual(audit.failures(self.row(axe={'violations': minor})), [])
        self.assertTrue(audit.failures(self.row(axe={'violations': [{'id': 'label', 'impact': 'serious', 'nodes': 2}]})))

    def test_a_layout_viewport_other_than_the_configured_width_fails(self):
        self.assertEqual(audit.failures(self.row(layout_width=390)), [])
        self.assertTrue(audit.failures(self.row(layout_width=980))[0].startswith('layout_width:'))

    def test_a_url_with_a_fragment_may_open_scrolled(self):
        self.assertEqual(audit.failures(self.row(url='http://127.0.0.1/p.html#details', scroll={'x': 0, 'y': 300})), [])
        self.assertTrue(audit.failures(self.row(scroll={'x': -120, 'y': 0})))

    def test_a_hash_route_is_not_an_anchor_and_must_open_at_the_top(self):
        self.assertTrue(audit.failures(self.row(url='http://127.0.0.1/index.html#/problems', scroll={'x': 0, 'y': 300})))
        self.assertEqual(audit.failures(self.row(url='http://127.0.0.1/index.html#/problems')), [])

    def test_arabic_tracking_script_errors_and_blocked_requests_fail(self):
        for change, reason in (({'arabic_tracking_count': 1, 'arabic_tracking': ['p.x']}, 'arabic_tracking:'),
                               ({'page_errors': ['TypeError: x is undefined']}, 'script_errors:'),
                               ({'blocked_requests': ['https://fonts.example/x.woff2']}, 'offline:')):
            self.assertTrue(audit.failures(self.row(**change))[0].startswith(reason), change)

    def test_a_variant_the_page_did_not_apply_fails(self):
        expect = {'dir': 'rtl', 'attributes': {'lang': 'ar', 'data-theme': 'dark'}}
        right = {'dir': 'rtl', 'root_attributes': {'lang': 'ar', 'dir': 'rtl', 'data-theme': 'dark'}}
        self.assertEqual(audit.failures(self.row(expect=expect, **right)), [])
        wrong = audit.failures(self.row(expect=expect, dir='ltr', root_attributes={'lang': 'en', 'data-theme': 'dark'}))
        self.assertEqual(wrong, ["variant: the page did not apply it: dir='ltr' (expected 'rtl'), lang='en' (expected 'ar')"])

    def test_small_targets_count_at_phone_width_only(self):
        self.assertTrue(audit.failures(self.row(small_target_count=2)))
        self.assertEqual(audit.failures(self.row(width=768, inner_width=768, scroll_width=768, small_target_count=2)), [])

    def test_a_phone_page_over_its_height_budget_fails_and_wider_pages_do_not(self):
        self.assertEqual(audit.failures(self.row(height=844, page_height=1600), height_budget=2), [])
        self.assertTrue(audit.failures(self.row(height=844, page_height=1800), height_budget=2)[0].startswith('height:'))
        self.assertEqual(audit.failures(self.row(height=844, page_height=1800)), [])
        self.assertEqual(audit.failures(self.row(width=1440, inner_width=1440, scroll_width=1440, height=900, page_height=9000),
                                        height_budget=2), [])

    def test_lighthouse_scores_under_the_mobile_minimums_fail(self):
        scores = lambda p, a: {'status': 'observed', 'scores': {'performance': p, 'accessibility': a, 'best-practices': 100}}
        self.assertEqual(audit.lighthouse_failures(scores(90, 100)), [])
        self.assertEqual(audit.lighthouse_failures(scores(89, 100)), ['lighthouse: performance 89 under 90'])
        self.assertEqual(audit.lighthouse_failures(scores(95, 98), {'accessibility': 95}), [])
        self.assertTrue(audit.lighthouse_failures({'status': 'error', 'reason': 'x'}))

    def test_a_page_that_did_not_load_fails(self):
        self.assertEqual(audit.failures({'status': 'error', 'reason': 'net::ERR'}), ['error: net::ERR'])


@unittest.skipIf(BROWSER_MISSING, f'screen tools not installed: {BROWSER_MISSING}')
class StudioGateCommandTests(unittest.TestCase):
    def gate(self, *pages, extra=()):
        with tempfile.TemporaryDirectory() as folder:
            for name in pages: shutil.copy(FIXTURES / f'{name}.html', folder)
            out = Path(folder) / 'gate'
            done = subprocess.run([sys.executable, str(ROOT / 'tools/studio_gates.py'), folder, '--out', str(out),
                                   '--viewports', '390x844', '--no-css', *extra], capture_output=True, text=True, timeout=600)
            report = json.loads((out / 'gates.json').read_text(encoding='utf-8'))
            shots = [p for p in (out / 'screenshots').glob('*.png')]
        return done, report, shots

    def test_a_clean_folder_passes_with_its_table_report_and_screenshots(self):
        done, report, shots = self.gate('clean')
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertTrue(report['ok'])
        self.assertEqual(report['summary'], {'rows': 2, 'passed': 2, 'failed': 0, 'skipped': 0, 'lighthouse_failed': 0})
        self.assertEqual(len(shots), 2)
        self.assertIn('clean.html', done.stdout)

    def test_one_failing_page_fails_the_gate(self):
        done, report, _ = self.gate('clean', 'overflow')
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertFalse(report['ok'])
        self.assertIn('FAIL', done.stdout)
        self.assertEqual([r['page'] for r in report['rows'] if r['failures']], ['overflow.html'])

    def test_each_fixture_is_caught_or_passed_by_the_command(self):
        done, report, _ = self.gate(*PAGES, 'bilingual')
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        failing = {r['page'] for r in report['rows'] if r['failures']}
        self.assertEqual(failing, {'overflow.html', 'rtl-shifted.html', 'small-target.html', 'unlabelled.html', 'truncated.html',
                                   'no-viewport-meta.html'})

    def test_a_height_budget_from_the_matrix_fails_a_page_taller_than_it(self):
        matrix = json.dumps({'variants': [{'name': 'en-light'}], 'height_budgets': {'clean.html': 0.2}})
        done, report, _ = self.gate('clean', extra=('--matrix', matrix))
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertTrue(report['rows'][0]['failures'][0].startswith('height:'))

    @unittest.skipIf(LIGHTHOUSE_MISSING, f'lighthouse not installed: {LIGHTHOUSE_MISSING}')
    def test_lighthouse_minimums_decide_the_exit_code(self):
        matrix = json.dumps({'variants': [{'name': 'en-light'}]})
        done, report, _ = self.gate('clean', extra=('--matrix', matrix, '--lighthouse', '--lighthouse-min', 'accessibility=101'))
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertEqual(report['lighthouse']['clean.html']['failures'], ['lighthouse: accessibility 100 under 101'])
        self.assertEqual(report['summary']['lighthouse_failed'], 1)
        self.assertTrue(report['lighthouse']['clean.html']['report'].startswith('lighthouse/'))


if __name__ == '__main__':
    unittest.main()
