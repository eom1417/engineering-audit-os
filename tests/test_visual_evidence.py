"""Visual evidence in the check: the assistant may open the screen pictures and nothing else, each finding names its
picture and a region inside it and becomes a design card; the architecture map, the crawl and the journeys go
through their pinned tools and say why when they cannot."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos import plan as plan_module
from eaos.behavior_lock import JOURNEY_HOOKS, playwright_spec
from eaos.engines import architecture
from eaos.pipeline.run import execute
from eaos.screens import crawl
from eaos.studio.actions import adapters
from eaos.studio.nodes import core

ROOT = Path(__file__).resolve().parents[1]
PNG = bytes.fromhex('89504e470d0a1a0a0000000d4948445200000001000000010806000000'
                    '1f15c4890000000d49444154789c6360000000000300015d0b4b1c0000000049454e44ae426082')


def region(x, y, width, height):
    return {'x': x, 'y': y, 'width': width, 'height': height}


class Reviewer:
    """Sees a crowded header on the first picture, a region outside the second, and nothing on the rest."""
    assistant, model, cost_usd = 'Claude Code', 'test-model', None

    def __call__(self, name, prompt, schema):
        ids = schema['properties']['decisions']['items']['properties']['subject']['enum']
        finding = lambda box: {'title': 'Crowded header', 'kind': 'crowding', 'severity': 'high', 'region': box,
                               'why': 'Four buttons share one line at phone width'}
        rows = [{'subject': ids[0], 'decision': 'cards', 'detail': {'findings': [finding(region(0, 0, 1, 0.2))]}},
                {'subject': ids[1], 'decision': 'cards', 'detail': {'findings': [finding(region(0.5, 0.9, 0.8, 0.3))]}}]
        rows += [{'subject': i, 'decision': 'clean', 'detail': {'findings': []}} for i in ids[2:]]
        return {'summary': '', 'decisions': [{'options': [], 'evidence': [row['subject']], 'confidence': 0.8, 'why': 'seen',
                                              'open_questions': [], **row} for row in rows]}


class VisualReviewer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        target = base / 'shop'
        shutil.copytree(ROOT / 'tests/fixtures/sustainability/redundant', target)
        cls.out = base / 'out'
        shots = cls.out / 'live/screens/screenshots'
        shots.mkdir(parents=True)
        rows = []
        for n, (viewport, theme) in enumerate((('phone', 'light'), ('desktop', 'light'), ('phone', 'dark'))):
            (shots / f'0{n}-index-{theme}-{viewport}.png').write_bytes(PNG)
            rows.append({'url': 'http://127.0.0.1:9/', 'viewport': viewport, 'variant': theme, 'failures': [],
                         'axe': {'violations': [{'id': 'color-contrast', 'help': 'Elements must meet contrast'}]},
                         'screenshot': f'live/screens/screenshots/0{n}-index-{theme}-{viewport}.png'})
        (cls.out / 'live/screens.json').write_text(json.dumps({'rows': rows}), encoding='utf-8')
        made = []
        def launcher(adapter, folder, cancel=None, started=None, images=()):
            made.append(list(images))
            return Reviewer()
        with mock.patch.object(core, 'pick', return_value=object()), mock.patch.object(core, 'AdapterLauncher', side_effect=launcher), \
                mock.patch('eaos.pipeline.runners._ran', side_effect=lambda context, name: name in ('screens', 'visual')):
            cls.manifest = execute(target, cls.out, language='en', provider=object(), skip=['semantic', 'triage', 'ideal', 'order', 'pipeline_gaps'])
        cls.images = made

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_assistant_may_open_exactly_the_pictures(self):
        self.assertEqual(self.manifest['stages']['visual']['status'], 'ok')
        self.assertEqual(sorted(Path(p).name for p in self.images[0]), sorted(p.name for p in (self.out / 'live/screens/screenshots').glob('*.png')))
        argv = adapters.ClaudeCode().ask_argv({}, self.out, self.images[0])
        allowed = argv[argv.index('--allowedTools') + 1:argv.index('--permission-mode')]
        self.assertEqual((argv[argv.index('--tools') + 1], allowed), ('Read', [f'Read({p})' for p in self.images[0]]))
        self.assertEqual(adapters.ClaudeCode().ask_argv({}, self.out)[-4:-2], ['--tools', ''])

    def test_a_finding_outside_its_picture_is_dropped_and_each_other_becomes_a_design_card(self):
        record = json.loads((self.out / 'nodes/visual_reviewer/last.json').read_text(encoding='utf-8'))
        self.assertEqual([row['why'] for row in record['dropped']], ['a finding names a region outside its picture'])
        findings = json.loads((self.out / 'nodes/visual_reviewer/findings.json').read_text(encoding='utf-8'))['findings']
        self.assertEqual([(f['image'], f['file'], f['region']) for f in findings],
                         [('IMG-001', 'live/screens/screenshots/00-index-light-phone.png', region(0, 0, 1, 0.2))])
        plan = json.loads((self.out / 'plan.json').read_text(encoding='utf-8'))
        card = next(t for t in plan['tasks'] if t['id'] == 'TASK-V001')
        self.assertEqual((card['origin'], card['evidence']['images'], card['evidence']['region']),
                         ('visual_review', ['live/screens/screenshots/00-index-light-phone.png'], region(0, 0, 1, 0.2)))
        self.assertIn('TASK-V001', [task for wave in plan['waves'] for task in wave['tasks']])
        self.assertEqual(json.loads((self.out / 'cards.json').read_text(encoding='utf-8'))['design'], ['TASK-V001'])


    def test_the_gallery_draws_each_finding_on_its_picture(self):
        page = (self.out / 'gallery/index.html').read_text(encoding='utf-8')
        self.assertIn('src="../live/screens/screenshots/00-index-light-phone.png"', page)
        self.assertEqual(page.count('class="box high"'), 1)
        self.assertIn('left:0.0%;top:0.0%;width:100.0%;height:20.0%', page)


class Gallery(unittest.TestCase):
    def test_the_city_is_a_rectangle_per_file_sized_by_its_lines(self):
        from eaos.compose import gallery
        city = {'files': [{'id': 'r', 'name': 'root', 'type': 'Folder', 'children': [
                    {'id': 'a', 'name': 'a.py', 'type': 'File'}, {'id': 'b', 'name': 'b.py', 'type': 'File'}]}],
                'lenses': {'metrics': {'attributes': {'a': {'rloc': 300, 'number_of_commits': 9, 'complexity': 12},
                                                      'b': {'rloc': 100, 'number_of_commits': 1, 'complexity': 2}}}}}
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'architecture').mkdir()
            (Path(folder) / 'architecture/city.cc.json').write_text(json.dumps(city), encoding='utf-8')
            page = gallery.city(Path(folder), ar=False)
        self.assertIn('width="1000.00" height="450.00"', page)
        self.assertIn('root/a.py: 300 lines, 9 changes, complexity 12', page)
        self.assertIn('width="1000.00" height="150.00"', page)


class Tools(unittest.TestCase):
    def test_a_tool_that_is_not_installed_is_unavailable_with_its_install_command(self):
        with mock.patch.object(architecture, 'which', return_value=None), tempfile.TemporaryDirectory() as folder:
            self.assertIn('--only codecharta', architecture.city(ROOT / 'tests/fixtures/polyglot', Path(folder))['reason'])
            self.assertIn('--only emerge', architecture.clusters(ROOT / 'tests/fixtures/polyglot', Path(folder))['reason'])
        with mock.patch.object(crawl, 'which', return_value=None):
            self.assertEqual(crawl.crawl('http://127.0.0.1:9', '/nonexistent')['status'], 'unavailable')

    def test_emerge_reads_one_analysis_per_language_of_the_project(self):
        text = architecture._config(Path('/p'), Path('/o'), ['python', 'typescript'])
        self.assertEqual([line for line in text.splitlines() if line.startswith('- analysis_name')],
                         ['- analysis_name: python', '- analysis_name: typescript'])
        self.assertIn('  - directory: "/o/typescript"', text)

    def test_a_crawled_page_is_read_from_its_lighthouse_report(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / 'unlighthouse/reports/about/lighthouse.json'
            report.parent.mkdir(parents=True)
            report.write_text(json.dumps({'finalDisplayedUrl': 'http://127.0.0.1:9/about', 'categories': {'performance': {'score': 0.91}},
                                          'audits': {'largest-contentful-paint': {'numericValue': 1234.4}}}), encoding='utf-8')
            self.assertEqual(crawl.route_of(report, Path(folder)),
                             {'path': '/about', 'scores': {'performance': 91, 'accessibility': None, 'best-practices': None, 'seo': None},
                              'lcp_ms': 1234, 'cls': None, 'report': 'unlighthouse/reports/about/lighthouse.json'})

    def test_only_a_feature_with_pages_records_its_journey(self):
        page, _ = playwright_spec({'name': 'Shop'}, [('/', ('page', 'GET', 'app.ts'))])
        api, _ = playwright_spec({'name': 'Api'}, [('/api/items', ('http', 'GET', 'api.ts'))])
        self.assertIn(JOURNEY_HOOKS[0], page)
        self.assertNotIn(JOURNEY_HOOKS[0], api)


if __name__ == '__main__':
    unittest.main()
