"""The screen gate: pinned Playwright + axe and Lighthouse, run for real on small local pages.

Every runner reports a missing tool as `unavailable` with the install command; the tests that need the tools skip,
with that reason, on a computer that has not installed them (python -m eaos tools install --only
playwright,axe-core,lighthouse).
"""
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
    return [row for row in result['rows'] if row['url'].split('#', 1)[0].split('?', 1)[0].endswith(f'/{name}.html')]


BROWSER_MISSING = audit.missing('playwright', 'axe-core')
LIGHTHOUSE_MISSING = audit.missing('playwright', 'lighthouse')


@unittest.skipIf(BROWSER_MISSING, f'screen tools not installed: {BROWSER_MISSING}')
class PageAuditTests(TemporaryWorkspace):
    @classmethod
    def setUpClass(cls):
        cls.out = cls.workspace().name
        # A hash route names its picture (#/problems), as the Studio's screens are reached
        cls.result = audit.page_audit([url(name) + ('#/problems/open' if name == 'clean' else '') for name in PAGES], out=cls.out)

    def observed(self, name):
        return [row for row in rows_of(self.result, name) if row['status'] == 'observed']

    def phone(self, name):
        return next(r for r in self.observed(name) if r['viewport'] == 'phone')

    def test_a_clean_page_passes_every_viewport_in_the_apps_own_theme_with_the_pinned_tools(self):
        self.assertEqual(self.result['status'], 'observed', self.result.get('reason'))
        self.assertEqual((self.result['tools']['playwright'], self.result['tools']['axe-core']), ('1.63.0', '4.13.0'))
        rows = self.observed('clean')
        self.assertEqual(rows[0]['axe']['version'], '4.13.0')
        self.assertEqual(sorted((r['variant'], r['viewport']) for r in rows), sorted(('default', s['name']) for s in audit.VIEWPORTS))
        self.assertEqual([r['failures'] for r in rows], [[]] * 3)
        # The self-check pictured every page light and dark (308 pictures); one theme, the app's own, by default
        self.assertEqual(len(self.result['rows']), len(PAGES) * len(audit.VIEWPORTS))
        phone = self.phone('clean')
        self.assertEqual((phone['mobile'], phone['layout_width']), (True, 390), 'a phone is emulated')
        self.assertEqual((phone['overflow_element_count'], phone['scroll_width']), (0, 390), 'a data-scroll-x scroller is not overflow')
        self.assertEqual(phone['truncated_count'], 0)
        self.assertGreater(phone['page_height'], 300)
        self.assertEqual(audit.failures(phone, height_budget=2), [])
        self.assertTrue(audit.failures(phone, height_budget=0.2)[0].startswith('height:'))
        for row in self.result['rows']:
            if row['status'] == 'observed': self.assertTrue(Path(row['screenshot']).is_file(), row)
        self.assertEqual({Path(r['screenshot']).name.split('-', 1)[1] for r in rows},
                         {f'problems-open-default-{s["name"]}.png' for s in audit.VIEWPORTS})

    def test_layout_faults_fail_where_they_happen_and_only_there(self):
        overflow = {r['viewport']: r for r in self.observed('overflow')}
        self.assertTrue(any(f.startswith('overflow:') for f in overflow['phone']['failures']), overflow['phone']['failures'])
        self.assertGreater(overflow['phone']['scroll_width'], 390)
        self.assertEqual(overflow['desktop']['failures'], [])
        # Under mobile emulation an overflowing page widens innerWidth to its content; the gate judges the configured 390.
        self.assertEqual((overflow['phone']['layout_width'], overflow['phone']['inner_width']), (716, 390))
        self.assertTrue(overflow['phone']['failures'][0].startswith('layout_width: the page laid out 716px'))
        meta = {r['viewport']: r for r in self.observed('no-viewport-meta')}
        self.assertEqual((meta['phone']['layout_width'], meta['phone']['overflow_element_count']), (980, 0))
        self.assertTrue(any(f.startswith('layout_width:') for f in meta['phone']['failures']))
        self.assertEqual((meta['tablet']['failures'], meta['desktop']['failures']), ([], []))
        for row in self.observed('rtl-shifted'):
            self.assertEqual(row['dir'], 'rtl')
            self.assertTrue(any(f.startswith('initial_scroll:') for f in row['failures']), row['failures'])
            self.assertFalse(any(f.startswith('overflow:') for f in row['failures']), row['failures'])
        small = {r['viewport']: r for r in self.observed('small-target')}
        self.assertEqual(small['phone']['small_targets'][0]['width'], 20)
        self.assertTrue(any(f.startswith('targets:') for f in small['phone']['failures']))
        self.assertEqual(small['desktop']['failures'], [])

    def test_missing_labels_are_axe_violations_and_clipped_text_must_keep_a_path_to_its_full_text(self):
        row = self.observed('unlabelled')[0]
        violations = {v['id']: v for v in row['axe']['violations']}
        self.assertLessEqual({'image-alt', 'label'}, set(violations))
        self.assertEqual(violations['image-alt']['targets'], ['img'])
        self.assertTrue(any(f.startswith('axe:') for f in row['failures']))
        for row in self.observed('truncated'):
            self.assertEqual({(t['selector'], t['problem']) for t in row['truncated']},
                             {('p#silent', 'not_marked'), ('p#marked', 'no_full_text')})
            self.assertTrue(any(f.startswith('truncation: 2 ') for f in row['failures']), row['failures'])


@unittest.skipIf(BROWSER_MISSING, f'screen tools not installed: {BROWSER_MISSING}')
class PageStateTests(unittest.TestCase):
    """Language, theme, actions and the subset of a page: the page measured in the state a person reaches."""

    def test_language_and_theme_are_set_through_the_named_key_and_parameter(self):
        page_variants = audit.variants(lang_key='studio-lang', theme_param='theme', themes=('light', 'dark'))
        rows = {v['name']: v for v in page_variants}
        self.assertEqual(list(rows), ['ar-light', 'en-light', 'ar-dark', 'en-dark'])
        self.assertEqual((rows['ar-dark']['storage'], rows['ar-dark']['query'], rows['ar-dark']['color_scheme']),
                         ({'studio-lang': 'ar'}, {'theme': 'dark'}, 'dark'))
        self.assertEqual([(v['name'], v['storage'], v['query'], v['color_scheme']) for v in audit.variants(theme_key='t', theme_param='t')],
                         [('default', {}, {}, 'light')], "by default nothing is set: the app's own theme")
        # The theme kept in a key's JSON object (the EAOS Studio's "eaos.studio"): merged in, so dark is pictured
        in_json = audit.variants(lang_key='studio-lang', theme_key='studio', theme_field='theme', themes=('light', 'dark'))
        self.assertEqual({v['name']: v['storage'] for v in in_json}['ar-dark'], {'studio-lang': 'ar', 'studio': {'theme': 'dark'}})
        self.assertEqual(audit.variants(lang_key='p', lang_field='lang', theme_key='p', theme_field='theme', themes=('dark',))[-1]['storage'],
                         {'p': {'lang': 'en', 'theme': 'dark'}})
        result = audit.page_audit([url('bilingual')], viewports=audit.VIEWPORTS[:1], page_variants=in_json)
        found = {r['variant']: r for r in result['rows']}
        self.assertEqual((found['ar-dark']['lang'], found['ar-dark']['dir']), ('ar', 'rtl'))
        self.assertEqual((found['en-light']['lang'], found['en-light']['dir']), ('en', 'ltr'))
        self.assertEqual((found['ar-dark']['root_attributes']['data-theme'], found['en-light']['root_attributes']['data-theme']), ('dark', 'light'))
        self.assertEqual([r['failures'] for r in found.values()], [[]] * 4)

    def test_an_opened_state_fails_on_what_the_action_revealed_a_page_keeps_to_its_subset_and_reaches_nothing_else(self):
        phone, one = audit.VIEWPORTS[:1], audit.variants(themes=('light',))
        page = {'url': url('opened'), 'name': 'opened', 'actions': [{'click': '#open', 'wait': 100}], 'height_budget': 0.1}
        result = audit.page_audit([url('opened'), page], viewports=phone, page_variants=one)
        self.assertEqual(next(r for r in result['rows'] if r['page'] is None)['failures'], [], 'the page as loaded passes')
        opened = next(r for r in result['rows'] if r['page'] == 'opened')
        self.assertEqual(opened['page_errors'], ['opened with an error'])
        self.assertEqual([s.split(' > ')[-1] for s in opened['arabic_tracking']], ['p.tracked'])
        self.assertEqual(opened['root_attributes'], {'lang': 'ar', 'dir': 'rtl'})
        self.assertLessEqual({'overflow', 'arabic_tracking', 'script_errors', 'height'}, {f.split(':')[0] for f in opened['failures']})
        subset = audit.page_audit([{'url': url('clean'), 'name': 'clean', 'viewports': ['phone'], 'variants': ['dark']}],
                                  page_variants=audit.variants(themes=('light', 'dark')))
        self.assertEqual([(r['viewport'], r['variant']) for r in subset['rows']], [('phone', 'dark')])
        with tempfile.TemporaryDirectory() as folder:
            page = Path(folder) / 'remote.html'
            page.write_text('<!doctype html><html lang="en"><head><title>t</title></head><body><main><h1>t</h1>'
                            '<img src="https://example.invalid/pixel.png" alt="pixel"></main></body></html>', encoding='utf-8')
            result = audit.page_audit([page.as_uri()], viewports=audit.VIEWPORTS[:1], page_variants=audit.variants(themes=('light',)))
        self.assertEqual(result['rows'][0]['blocked_requests'], ['https://example.invalid/pixel.png'])

class ServeAndLighthouseTests(unittest.TestCase):
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

    @unittest.skipIf(LIGHTHOUSE_MISSING, f'lighthouse not installed: {LIGHTHOUSE_MISSING}')
    def test_mobile_scores_lcp_and_cls_of_a_local_page(self):
        with audit.serve(FIXTURES) as base:
            found = audit.lighthouse(base + 'unlabelled.html')
        self.assertEqual(found['status'], 'observed', found.get('reason'))
        self.assertEqual((found['version'], found['form_factor']), ('13.5.0', 'mobile'))
        self.assertEqual(set(found['scores']), {'performance', 'accessibility', 'best-practices'})
        self.assertIsInstance(found['lcp_ms'], int)
        self.assertEqual(found['cls'], 0)
        self.assertLess(found['scores']['accessibility'], 100)
        self.assertIn('image-alt', found['failed_audits']['accessibility'])

    def test_a_missing_tool_or_node_is_unavailable_with_the_command_that_installs_it(self):
        with mock.patch.object(toolchain, 'found_version', return_value=(None, 'not installed')):
            results = [audit.page_audit(url('clean')), audit.lighthouse('http://127.0.0.1:9/')]
        for result in results:
            self.assertEqual(result['status'], 'unavailable')
            self.assertIn('python -m eaos tools install --only', result['reason'])
        with mock.patch.object(audit.shutil, 'which', return_value=None):
            self.assertIn('Node.js', audit.page_audit(url('clean'))['reason'])


class DistinctPagesTests(unittest.TestCase):
    def test_pages_of_one_template_with_other_data_are_pictured_once(self):
        # The self-check pictured 77 routes of the Studio, 8 task pages and 8 flow pages among them, each light and dark
        from eaos.screens.crawl import distinct
        crawled = ['/', '/#/', '/#/problems', '/#/problems?severity=low', '/#/tasks/TASK-001', '/#/tasks/TASK-004',
                   '/#/plans/fix', '/#/plans/fix/M01', '/#/plans/fix/M02', '/#/system/f/eaos%2Fplan.py%23confirm',
                   '/#/system/functions', '/#/system/paths', '/#/system/pipeline', '/#/history', '/#/history/e8fb378a06cc',
                   '/#/change', '/#/change/gaps', '/#/change/ideal', '/about#team', '/items/1', '/items/2', '/index.html']
        crawled += [f'/#/flows/{name}' for name in ('cli', 'main', 'root-shell', 'codex-adapter-main', 'contracts-main')]
        crawled += [f'/#/change/gaps/{name}' for name in ('eaos', 'eaos%2Fstudio', '(root)', 'eaos%2Ffacts', 'eaos%2Fengines')]
        found = distinct(crawled)
        self.assertEqual(list(found), ['/', '/#/problems', '/#/tasks/:id', '/#/plans/fix', '/#/plans/fix/:id', '/#/system/f/:id',
                                       '/#/system/functions', '/#/system/paths', '/#/system/pipeline', '/#/history', '/#/history/:id',
                                       '/#/change', '/#/change/gaps', '/#/change/ideal', '/about', '/items/:id', '/#/flows/:id',
                                       '/#/change/gaps/:id'])
        self.assertEqual((found['/'], found['/#/tasks/:id'][0], len(found['/#/flows/:id'])), (['/', '/#/', '/index.html'], '/#/tasks/TASK-001', 5))


class FailureRuleTests(unittest.TestCase):
    def row(self, **change):
        row = {'status': 'observed', 'url': 'http://127.0.0.1/p.html', 'width': 390, 'inner_width': 390, 'scroll_width': 390,
               'overflow_element_count': 0, 'scroll': {'x': 0, 'y': 0}, 'small_target_count': 0, 'axe': {'violations': []}}
        return {**row, **change}

    def test_what_fails_a_row_and_what_does_not_and_a_variant_the_page_did_not_apply_says_how(self):
        minor = [{'id': 'region', 'impact': 'moderate', 'nodes': 1}, {'id': 'x', 'impact': 'minor', 'nodes': 1}]
        wide = {'width': 768, 'inner_width': 768, 'scroll_width': 768}
        passing = (({'axe': {'violations': minor}}, None), ({'layout_width': 390}, None),
                   ({'url': 'http://127.0.0.1/p.html#details', 'scroll': {'x': 0, 'y': 300}}, None),     # an anchor may open scrolled
                   ({'url': 'http://127.0.0.1/index.html#/problems'}, None),
                   ({**wide, 'small_target_count': 2}, None),
                   ({'height': 844, 'page_height': 1600}, 2), ({'height': 844, 'page_height': 1800}, None),
                   ({'width': 1440, 'inner_width': 1440, 'scroll_width': 1440, 'height': 900, 'page_height': 9000}, 2))
        for change, budget in passing:
            with self.subTest(change=change):
                self.assertEqual(audit.failures(self.row(**change), height_budget=budget), [])
        failing = (({'axe': {'violations': [{'id': 'label', 'impact': 'serious', 'nodes': 2}]}}, 'axe:', None),
                   ({'layout_width': 980}, 'layout_width:', None),
                   ({'scroll': {'x': -120, 'y': 0}}, 'initial_scroll:', None),
                   ({'url': 'http://127.0.0.1/index.html#/problems', 'scroll': {'x': 0, 'y': 300}}, 'initial_scroll:', None),  # a hash route
                   ({'small_target_count': 2}, 'targets:', None),
                   ({'height': 844, 'page_height': 1800}, 'height:', 2),
                   ({'arabic_tracking_count': 1, 'arabic_tracking': ['p.x']}, 'arabic_tracking:', None),
                   ({'page_errors': ['TypeError: x is undefined']}, 'script_errors:', None),
                   ({'blocked_requests': ['https://fonts.example/x.woff2']}, 'offline:', None))
        for change, reason, budget in failing:
            with self.subTest(change=change):
                self.assertTrue(audit.failures(self.row(**change), height_budget=budget)[0].startswith(reason))
        self.assertEqual(audit.failures({'status': 'error', 'reason': 'net::ERR'}), ['error: net::ERR'])
        expect = {'dir': 'rtl', 'attributes': {'lang': 'ar', 'data-theme': 'dark'}}
        right = {'dir': 'rtl', 'root_attributes': {'lang': 'ar', 'dir': 'rtl', 'data-theme': 'dark'}}
        self.assertEqual(audit.failures(self.row(expect=expect, **right)), [])
        wrong = audit.failures(self.row(expect=expect, dir='ltr', root_attributes={'lang': 'en', 'data-theme': 'dark'}))
        self.assertEqual(wrong, ["variant: the page did not apply it: dir='ltr' (expected 'rtl'), lang='en' (expected 'ar')"])

if __name__ == '__main__':
    unittest.main()
